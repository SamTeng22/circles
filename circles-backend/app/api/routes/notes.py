from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from pydantic import BaseModel
from app.core.firebase import get_current_user
from app.db.database import get_pool
from app.services.embedding import chunk_and_embed
from app.services import storage, extract

router = APIRouter()


class NoteContentUpdate(BaseModel):
    content: str


async def _assert_member(conn, circle_id: str, user_id) -> None:
    member = await conn.fetchrow(
        "SELECT 1 FROM circle_members WHERE circle_id = $1 AND user_id = $2",
        circle_id, user_id,
    )
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this circle")


@router.post("/{circle_id}/upload")
async def upload_notes(
    circle_id: str,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _assert_member(conn, circle_id, current_user["id"])

    data = await file.read()
    content_type = file.content_type or "application/octet-stream"

    # 1. Store the original file in object storage (source of truth).
    key = storage.put_object(data, content_type, circle_id, file.filename)

    # 2. Record the note immediately as "processing" (text/embeddings come later).
    async with pool.acquire() as conn:
        note = await conn.fetchrow(
            """
            INSERT INTO notes
                (circle_id, user_id, filename, content, s3_key, content_type, size_bytes, status)
            VALUES ($1, $2, $3, NULL, $4, $5, $6, 'processing')
            RETURNING *
            """,
            circle_id, current_user["id"], file.filename, key, content_type, len(data),
        )

    # 3. Extract text + embed off the request path so the response returns now.
    background.add_task(
        _process_note,
        str(note["id"]), circle_id, str(current_user["id"]),
        data, content_type, file.filename,
    )

    return {"note_id": str(note["id"]), "status": "processing"}


async def _process_note(
    note_id: str,
    circle_id: str,
    user_id: str,
    data: bytes,
    content_type: str,
    filename: str,
):
    pool = await get_pool()
    try:
        text = extract.extract_text(data, content_type, filename)
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE notes SET content = $1 WHERE id = $2", text, note_id
            )
        await chunk_and_embed(
            note_id=note_id, circle_id=circle_id, user_id=user_id, content=text
        )
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE notes SET status = 'ready', error = NULL WHERE id = $1", note_id
            )
    except Exception as e:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE notes SET status = 'failed', error = $1 WHERE id = $2",
                str(e)[:500], note_id,
            )
        print(f"Note processing failed for {note_id}: {e}")


@router.get("/file/{note_id}")
async def get_note_file(
    note_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Return a short-lived URL to download/view the note's original file."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        note = await conn.fetchrow(
            "SELECT circle_id, s3_key, filename FROM notes WHERE id = $1", note_id
        )
        if not note:
            raise HTTPException(status_code=404, detail="Note not found")
        await _assert_member(conn, str(note["circle_id"]), current_user["id"])

    if not note["s3_key"]:
        # Older text-only notes have no stored original file.
        raise HTTPException(status_code=404, detail="No stored file for this note")

    return {"url": storage.presigned_get(note["s3_key"]), "filename": note["filename"]}


@router.get("/detail/{note_id}")
async def get_note_detail(
    note_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Return a single note including its extracted text content.

    The content is the text the system pulled from the uploaded file and uses
    for embeddings/quiz generation — i.e. "what the computer knows".
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        note = await conn.fetchrow(
            """
            SELECT n.*, u.display_name as uploader_name
            FROM notes n JOIN users u ON u.id = n.user_id
            WHERE n.id = $1
            """,
            note_id,
        )
        if not note:
            raise HTTPException(status_code=404, detail="Note not found")
        await _assert_member(conn, str(note["circle_id"]), current_user["id"])
    return dict(note)


async def _reembed_note(note_id: str, circle_id: str, user_id: str, content: str):
    """Replace a note's chunks/embeddings from edited content, then mark ready."""
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM note_chunks WHERE note_id = $1", note_id)
        await chunk_and_embed(
            note_id=note_id, circle_id=circle_id, user_id=user_id, content=content
        )
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE notes SET status = 'ready', error = NULL WHERE id = $1", note_id
            )
    except Exception as e:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE notes SET status = 'failed', error = $1 WHERE id = $2",
                str(e)[:500], note_id,
            )
        print(f"Note re-embedding failed for {note_id}: {e}")


@router.put("/{circle_id}/{note_id}/content")
async def update_note_content(
    circle_id: str,
    note_id: str,
    body: NoteContentUpdate,
    background: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """Edit a note's extracted text. Allowed for the uploader or circle owner.

    Saves the new content immediately and re-chunks/re-embeds off the request
    path (status flips to 'processing' until the new embeddings land).
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _assert_member(conn, circle_id, current_user["id"])
        note = await conn.fetchrow(
            "SELECT user_id FROM notes WHERE id = $1 AND circle_id = $2",
            note_id, circle_id,
        )
        if not note:
            raise HTTPException(status_code=404, detail="Note not found")

        owner = await conn.fetchrow(
            "SELECT owner_id FROM circles WHERE id = $1", circle_id
        )
        is_uploader = note["user_id"] == current_user["id"]
        is_circle_owner = owner and owner["owner_id"] == current_user["id"]
        if not (is_uploader or is_circle_owner):
            raise HTTPException(
                status_code=403,
                detail="Only the uploader or circle owner can edit this note",
            )

        await conn.execute(
            "UPDATE notes SET content = $1, status = 'processing', edited_at = now() WHERE id = $2",
            body.content, note_id,
        )

    background.add_task(
        _reembed_note, note_id, circle_id, str(note["user_id"]), body.content
    )
    return {"note_id": note_id, "status": "processing"}


@router.delete("/{circle_id}/{note_id}")
async def delete_note(
    circle_id: str,
    note_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a pooled note. Allowed for the uploader or the circle owner.

    Removes the note row (note_chunks cascade via FK) and the stored file.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _assert_member(conn, circle_id, current_user["id"])
        note = await conn.fetchrow(
            "SELECT user_id, s3_key FROM notes WHERE id = $1 AND circle_id = $2",
            note_id, circle_id,
        )
        if not note:
            raise HTTPException(status_code=404, detail="Note not found")

        owner = await conn.fetchrow(
            "SELECT owner_id FROM circles WHERE id = $1", circle_id
        )
        is_uploader = note["user_id"] == current_user["id"]
        is_circle_owner = owner and owner["owner_id"] == current_user["id"]
        if not (is_uploader or is_circle_owner):
            raise HTTPException(
                status_code=403,
                detail="Only the uploader or circle owner can delete this note",
            )

        await conn.execute("DELETE FROM notes WHERE id = $1", note_id)

    # Best-effort: drop the original file once the row is gone.
    if note["s3_key"]:
        try:
            storage.delete_object(note["s3_key"])
        except Exception as e:
            print(f"Failed to delete object {note['s3_key']}: {e}")

    return {"deleted": note_id}


@router.get("/{circle_id}")
async def list_circle_notes(
    circle_id: str,
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _assert_member(conn, circle_id, current_user["id"])
        notes = await conn.fetch(
            """
            SELECT n.*, u.display_name as uploader_name
            FROM notes n JOIN users u ON u.id = n.user_id
            WHERE n.circle_id = $1
            ORDER BY n.created_at DESC
            """,
            circle_id,
        )
    return [dict(n) for n in notes]
