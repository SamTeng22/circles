from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from app.api.routes import auth, circles, notes, quiz, live, flashcards
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.db.database import init_db

app = FastAPI(title="Circles API", version="1.0.0")

# Rate limiting: the limiter is discovered via app.state by slowapi's decorator,
# and RateLimitExceeded is turned into a clean 429 instead of a 500.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://circles-9ez5.vercel.app", "https://staging-circles-sam-9d919e89.vercel.app", "circles-mocha-tau.vercel.app"],
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

@app.get("/")
def root():
    return {"message": "Circles API is running"}
