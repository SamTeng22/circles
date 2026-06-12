from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import firebase_admin
from firebase_admin import auth, credentials
from app.core.config import settings
from app.db.database import get_pool

bearer_scheme = HTTPBearer()

if not firebase_admin._apps:
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred, {"projectId": settings.FIREBASE_PROJECT_ID})

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    token = credentials.credentials
    try:
        decoded = auth.verify_id_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE firebase_uid = $1", decoded["uid"]
        )
        if not user:
            # Auto-register on first login
            user = await conn.fetchrow(
                """
                INSERT INTO users (firebase_uid, email, display_name)
                VALUES ($1, $2, $3)
                RETURNING *
                """,
                decoded["uid"],
                decoded.get("email"),
                decoded.get("name"),
            )
    return dict(user)
