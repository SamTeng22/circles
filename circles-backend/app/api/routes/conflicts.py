from fastapi import APIRouter, Depends, HTTPException
from app.core.firebase import get_current_user
from app.db.database import get_pool

router = APIRouter()


async def _assert_member(conn, circle_id, user_id) -> None:
    member = await conn.fetchrow(
        "SELECT 1 FROM circle_members WHERE circle_id = $1 AND user_id = $2",
        circle_id, user_id,
    )
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this circle")


@router.get("/{circle_id}")
async def list_circle_conflicts(
    circle_id: str,
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _assert_member(conn, circle_id, current_user["id"])
        conflicts = await conn.fetch(
            """
            SELECT c.*,
                na.filename AS note_a_filename, nb.filename AS note_b_filename,
                ua.display_name AS user_a_name, ub.display_name AS user_b_name
            FROM conflicts c
            JOIN notes na ON na.id = c.note_a_id
            JOIN notes nb ON nb.id = c.note_b_id
            JOIN users ua ON ua.id = c.user_a_id
            JOIN users ub ON ub.id = c.user_b_id
            WHERE c.circle_id = $1
            ORDER BY c.created_at DESC
            """,
            circle_id,
        )
    return [dict(c) for c in conflicts]
