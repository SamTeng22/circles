from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from app.core.firebase import get_current_user
from app.db.database import get_pool
from app.services.embedding import chunk_and_embed

router = APIRouter()

@router.post("/{circle_id}/upload")
async def upload_notes(
    circle_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        member = await conn.fetchrow(
            "SELECT * FROM circle_members WHERE circle_id = $1 AND user_id = $2",
            circle_id, current_user["id"],
        )
        if not member:
            raise HTTPException(status_code=403, detail="Not a member of this circle")

    content_bytes = await file.read()
    content = content_bytes.decode("utf-8", errors="ignore")

    async with pool.acquire() as conn:
        note = await conn.fetchrow(
            """
            INSERT INTO notes (circle_id, user_id, filename, content)
            VALUES ($1, $2, $3, $4) RETURNING *
            """,
            circle_id, current_user["id"], file.filename, content,
        )

    # Chunk and embed in background
    await chunk_and_embed(
        note_id=str(note["id"]),
        circle_id=circle_id,
        user_id=str(current_user["id"]),
        content=content,
    )

    return {"message": "Notes uploaded and processing started", "note_id": str(note["id"])}

@router.get("/{circle_id}")
async def list_circle_notes(
    circle_id: str,
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        member = await conn.fetchrow(
            "SELECT * FROM circle_members WHERE circle_id = $1 AND user_id = $2",
            circle_id, current_user["id"],
        )
        if not member:
            raise HTTPException(status_code=403, detail="Not a member of this circle")
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
