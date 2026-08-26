from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from google.api_core.exceptions import GoogleAPICallError
from pydantic import BaseModel, Field
from app.core.config import settings
from app.core.firebase import get_current_user
from app.core.gemini_errors import friendly_gemini_error
from app.core.rate_limit import limiter, identify_user, flashcard_generation_limit
from app.db.database import get_pool
from app.services.flashcard_generator import generate_flashcards

router = APIRouter()


async def _assert_member(conn, circle_id, user_id) -> None:
    member = await conn.fetchrow(
        "SELECT 1 FROM circle_members WHERE circle_id = $1 AND user_id = $2",
        circle_id, user_id,
    )
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this circle")


async def _fetch_selected_notes(conn, circle_id: str, note_ids: list[str]) -> list[dict]:
    rows = await conn.fetch(
        """
        SELECT id, filename, content FROM notes
        WHERE circle_id = $1 AND id = ANY($2::uuid[]) AND status = 'ready'
        """,
        circle_id, note_ids,
    )
    found_ids = {str(r["id"]) for r in rows}
    missing = [nid for nid in note_ids if nid not in found_ids]
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Note(s) not found or not ready: {', '.join(missing)}",
        )
    total_chars = sum(len(r["content"] or "") for r in rows)
    if total_chars > settings.GENERATION_CONTEXT_CHAR_LIMIT:
        raise HTTPException(
            status_code=400,
            detail="Selected notes are too large — remove some and try again",
        )
    return [dict(r) for r in rows]


class GenerateDeckRequest(BaseModel):
    circle_id: str
    title: str
    num_cards: int = Field(default=10, ge=1, le=50)
    note_ids: list[str] = Field(min_length=1)
    difficulty: Literal["easy", "medium", "hard"] = "medium"

@router.post("/generate")
@limiter.limit(flashcard_generation_limit)
async def generate_deck(
    request: Request,
    body: GenerateDeckRequest,
    current_user: dict = Depends(identify_user),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _assert_member(conn, body.circle_id, current_user["id"])
        notes = await _fetch_selected_notes(conn, body.circle_id, body.note_ids)

    try:
        cards = await generate_flashcards(
            notes=notes,
            num_cards=body.num_cards,
            difficulty=body.difficulty,
        )
    except GoogleAPICallError as e:
        raise HTTPException(status_code=503, detail=friendly_gemini_error(e))
    if not cards:
        raise HTTPException(
            status_code=400,
            detail="No notes to build flashcards from. Upload notes to this circle first.",
        )

    async with pool.acquire() as conn:
        deck = await conn.fetchrow(
            """
            INSERT INTO flashcard_decks (circle_id, created_by, title, cards)
            VALUES ($1, $2, $3, $4::jsonb) RETURNING *
            """,
            body.circle_id, current_user["id"], body.title, cards,
        )
    return dict(deck)

@router.get("/detail/{deck_id}")
async def get_deck(
    deck_id: str,
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        deck = await conn.fetchrow("SELECT * FROM flashcard_decks WHERE id = $1", deck_id)
        if not deck:
            raise HTTPException(status_code=404, detail="Deck not found")
        await _assert_member(conn, deck["circle_id"], current_user["id"])
    return dict(deck)

@router.get("/{circle_id}")
async def list_circle_decks(
    circle_id: str,
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _assert_member(conn, circle_id, current_user["id"])
        decks = await conn.fetch(
            "SELECT * FROM flashcard_decks WHERE circle_id = $1 ORDER BY created_at DESC",
            circle_id,
        )
    return [dict(d) for d in decks]
