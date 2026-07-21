"""Per-user rate limiting for the expensive endpoints.

The costly routes (LLM quiz/flashcard generation and OCR-backed note uploads)
are all authenticated, so we key limits on the Firebase-verified DB user id
rather than the caller's IP. `identify_user` runs as a dependency on the limited
routes and stashes the id on `request.state` so the limiter's key function can
read it; if for some reason it's missing we fall back to the client IP so the
limit still applies.

Limits themselves live in `app.core.config` settings (strings like "10/hour"),
so they can be retuned via environment variables without a code change. The
limit values below are passed as callables so each request re-reads the current
setting.
"""
from fastapi import Depends, Request
from starlette.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.firebase import get_current_user


def user_id_key(request: Request) -> str:
    """Limiter key: the authenticated user id when known, else the client IP."""
    key = getattr(request.state, "rate_limit_key", None)
    return key or get_remote_address(request)


# headers_enabled stays off: slowapi can only inject X-RateLimit headers when the
# endpoint returns a starlette Response, and ours return plain dicts. The 429 body
# below already tells the caller what happened, which is what we need.
limiter = Limiter(
    key_func=user_id_key,
    enabled=settings.RATE_LIMIT_ENABLED,
)


async def identify_user(
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Authenticate the caller and expose their id to the limiter key function.

    Used in place of `get_current_user` on rate-limited routes. FastAPI resolves
    this dependency before the endpoint body (where slowapi's check runs), so the
    id is on `request.state` by the time `user_id_key` is consulted.
    """
    request.state.rate_limit_key = f"user:{current_user['id']}"
    return current_user


# Limit values as callables so the current setting is read per request (retunable
# via env without a redeploy). `*_` swallows whatever slowapi passes the provider.
def quiz_generation_limit(*_) -> str:
    return settings.QUIZ_GENERATION_RATE_LIMIT


def flashcard_generation_limit(*_) -> str:
    return settings.FLASHCARD_GENERATION_RATE_LIMIT


def note_upload_limit(*_) -> str:
    return settings.NOTE_UPLOAD_RATE_LIMIT


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return a clear 429 (not a generic 500) with the app's usual `detail` shape."""
    response = JSONResponse(
        status_code=429,
        content={
            "detail": (
                "Rate limit exceeded — you've made too many requests for this "
                f"action (limit: {exc.detail}). Please wait a while and try again."
            )
        },
    )
    # Attach the standard X-RateLimit / Retry-After headers when available.
    try:
        response = request.app.state.limiter._inject_headers(
            response, request.state.view_rate_limit
        )
    except Exception:
        pass
    return response
