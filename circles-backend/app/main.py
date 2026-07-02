from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import auth, circles, notes, quiz, live, flashcards
from app.db.database import init_db

app = FastAPI(title="Circles API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://your-vercel-app.vercel.app"],
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
