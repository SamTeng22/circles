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
