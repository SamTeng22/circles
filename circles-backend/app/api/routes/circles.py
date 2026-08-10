from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.firebase import get_current_user
from app.db.database import get_pool
import secrets

router = APIRouter()

class CreateCircleRequest(BaseModel):
    name: str
    description: str = ""

class JoinCircleRequest(BaseModel):
    invite_code: str

class UpdateCircleRequest(BaseModel):
    name: str

async def _assert_owner(conn, circle_id: str, user_id) -> dict:
    circle = await conn.fetchrow("SELECT * FROM circles WHERE id = $1", circle_id)
    if not circle:
        raise HTTPException(status_code=404, detail="Circle not found")
    if circle["owner_id"] != user_id:
        raise HTTPException(status_code=403, detail="Only the circle owner can do this")
    return circle

@router.post("/")
async def create_circle(
    body: CreateCircleRequest,
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    invite_code = secrets.token_urlsafe(6).upper()
    async with pool.acquire() as conn:
        circle = await conn.fetchrow(
            """
            INSERT INTO circles (name, description, invite_code, owner_id)
            VALUES ($1, $2, $3, $4) RETURNING *
            """,
            body.name, body.description, invite_code, current_user["id"],
        )
        await conn.execute(
            "INSERT INTO circle_members (circle_id, user_id) VALUES ($1, $2)",
            circle["id"], current_user["id"],
        )
    return dict(circle)

@router.post("/join")
async def join_circle(
    body: JoinCircleRequest,
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        circle = await conn.fetchrow(
            "SELECT * FROM circles WHERE invite_code = $1", body.invite_code
        )
        if not circle:
            raise HTTPException(status_code=404, detail="Circle not found")
        existing = await conn.fetchrow(
            "SELECT * FROM circle_members WHERE circle_id = $1 AND user_id = $2",
            circle["id"], current_user["id"],
        )
        if existing:
            raise HTTPException(status_code=400, detail="Already a member")
        await conn.execute(
            "INSERT INTO circle_members (circle_id, user_id) VALUES ($1, $2)",
            circle["id"], current_user["id"],
        )
    return dict(circle)

@router.get("/")
async def list_my_circles(current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT c.* FROM circles c
            JOIN circle_members cm ON cm.circle_id = c.id
            WHERE cm.user_id = $1
            ORDER BY c.created_at DESC
            """,
            current_user["id"],
        )
    return [dict(r) for r in rows]

@router.get("/{circle_id}")
async def get_circle(
    circle_id: str,
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        circle = await conn.fetchrow("SELECT * FROM circles WHERE id = $1", circle_id)
        if not circle:
            raise HTTPException(status_code=404, detail="Circle not found")
        member = await conn.fetchrow(
            "SELECT * FROM circle_members WHERE circle_id = $1 AND user_id = $2",
            circle_id, current_user["id"],
        )
        if not member:
            raise HTTPException(status_code=403, detail="Not a member of this circle")
        members = await conn.fetch(
            """
            SELECT u.id, u.display_name, u.email FROM users u
            JOIN circle_members cm ON cm.user_id = u.id
            WHERE cm.circle_id = $1
            """,
            circle_id,
        )
    return {**dict(circle), "members": [dict(m) for m in members]}

@router.delete("/{circle_id}/leave")
async def leave_circle(
    circle_id: str,
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        circle = await conn.fetchrow("SELECT * FROM circles WHERE id = $1", circle_id)
        if not circle:
            raise HTTPException(status_code=404, detail="Circle not found")
        member = await conn.fetchrow(
            "SELECT * FROM circle_members WHERE circle_id = $1 AND user_id = $2",
            circle_id, current_user["id"],
        )
        if not member:
            raise HTTPException(status_code=403, detail="Not a member of this circle")

        await conn.execute(
            "DELETE FROM circle_members WHERE circle_id = $1 AND user_id = $2",
            circle_id, current_user["id"],
        )
        remaining = await conn.fetchrow(
            "SELECT 1 FROM circle_members WHERE circle_id = $1", circle_id
        )
        if not remaining:
            # Last member leaving deletes the circle rather than leaving a
            # memberless circle (and its notes/quizzes/decks) orphaned forever.
            await conn.execute("DELETE FROM circles WHERE id = $1", circle_id)
            return {"left": True, "circle_deleted": True}
    return {"left": True, "circle_deleted": False}

@router.delete("/{circle_id}/members/{user_id}")
async def remove_member(
    circle_id: str,
    user_id: str,
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _assert_owner(conn, circle_id, current_user["id"])
        member = await conn.fetchrow(
            "SELECT * FROM circle_members WHERE circle_id = $1 AND user_id = $2",
            circle_id, user_id,
        )
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")

        await conn.execute(
            "DELETE FROM circle_members WHERE circle_id = $1 AND user_id = $2",
            circle_id, user_id,
        )
    return {"removed": True}

@router.patch("/{circle_id}")
async def update_circle(
    circle_id: str,
    body: UpdateCircleRequest,
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _assert_owner(conn, circle_id, current_user["id"])
        circle = await conn.fetchrow(
            "UPDATE circles SET name = $1 WHERE id = $2 RETURNING *",
            body.name, circle_id,
        )
    return dict(circle)

@router.delete("/{circle_id}")
async def delete_circle(
    circle_id: str,
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _assert_owner(conn, circle_id, current_user["id"])
        # circle_members/notes/note_chunks/conflicts/quizzes/flashcard_decks all
        # have ON DELETE CASCADE on circle_id (quiz_scores cascades transitively
        # via quiz_id), so deleting the circle row cleans up everything.
        await conn.execute("DELETE FROM circles WHERE id = $1", circle_id)
    return {"deleted": True}

@router.post("/{circle_id}/regenerate-invite")
async def regenerate_invite(
    circle_id: str,
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _assert_owner(conn, circle_id, current_user["id"])
        invite_code = secrets.token_urlsafe(6).upper()
        circle = await conn.fetchrow(
            "UPDATE circles SET invite_code = $1 WHERE id = $2 RETURNING *",
            invite_code, circle_id,
        )
    return dict(circle)
