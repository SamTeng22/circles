import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from app.api.routes import auth, circles, notes, quiz, live, flashcards, conflicts
from app.core.config import settings
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.db.database import get_pool, init_db

logger = logging.getLogger("uvicorn.error")

app = FastAPI(title="Circles API", version="1.0.0")

# Rate limiting: the limiter is discovered via app.state by slowapi's decorator,
# and RateLimitExceeded is turned into a clean 429 instead of a 500.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Turn unhandled errors into a normal 500 response.

    Without this, an unhandled exception is caught by Starlette's outermost
    ServerErrorMiddleware, which sits *outside* CORSMiddleware — so the 500 it
    returns has no Access-Control-Allow-Origin header. Browsers then report
    that as a CORS failure, masking the real error. Registering a handler here
    routes it through ExceptionMiddleware instead, which is inside
    CORSMiddleware, so the response gets CORS headers like any other.
    """
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    await init_db()

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(circles.router, prefix="/api/circles", tags=["circles"])
app.include_router(notes.router, prefix="/api/notes", tags=["notes"])
app.include_router(quiz.router, prefix="/api/quiz", tags=["quiz"])
app.include_router(flashcards.router, prefix="/api/flashcards", tags=["flashcards"])
app.include_router(live.router, prefix="/api/live", tags=["live"])
app.include_router(conflicts.router, prefix="/api/conflicts", tags=["conflicts"])

@app.get("/")
def root():
    return {"message": "Circles API is running"}

@app.get("/health/db")
async def health_db():
    """Round-trips Postgres so latency/connectivity checks reflect the real
    Railway-to-Neon path, not just the app server responding."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.fetchval("SELECT 1")
    return {"status": "ok"}
