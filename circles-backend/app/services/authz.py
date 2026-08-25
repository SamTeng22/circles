from fastapi import HTTPException


async def assert_member(conn, circle_id, user_id) -> None:
    member = await conn.fetchrow(
        "SELECT 1 FROM circle_members WHERE circle_id = $1 AND user_id = $2",
        circle_id, user_id,
    )
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this circle")
