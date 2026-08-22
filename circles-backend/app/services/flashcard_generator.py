import json
import google.generativeai as genai
from app.core.config import settings
# Reuse the same context-building helper the quiz generator uses so flashcards
# are grounded in the same selected notes format.
from app.services.quiz_generator import build_context

genai.configure(api_key=settings.GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")


def _strip_code_fence(text: str) -> str:
    """Gemini often wraps JSON in a ```json ... ``` fence; unwrap it."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return text.strip()


async def generate_flashcards(
    notes: list[dict],
    num_cards: int,
) -> list[dict]:
    if not notes:
        return []

    context = build_context(notes)
    prompt = f"""You are a flashcard generator for students. Based on the study notes below, generate {num_cards} flashcards.

Each flashcard has a short prompt on the front and a concise, self-contained answer on the back. Favor one idea per card: key terms, definitions, cause/effect, and important facts. Keep fronts under ~15 words and backs under ~40 words.

Language rules:
- Each note below is written in one of: English, Tagalog, or Chinese.
- Write each flashcard (front, back, hint) in the SAME language as the note it is drawn from.
- Tag every flashcard with a "language" field using EXACTLY one of these codes: "en" (English), "tl" (Tagalog/Filipino), "zh" (Chinese). Do not use any other code or a language name.
- It is fine and expected for different flashcards in the same output to use different languages if the source notes differ in language.

Return ONLY a valid JSON array with this exact format, no markdown, no extra text:
[
  {{
    "front": "...",
    "back": "...",
    "hint": "...",
    "language": "en|tl|zh"
  }}
]

The "hint" is optional context (leave as an empty string if not useful).

Study notes:
{context}
"""
    response = model.generate_content(prompt)
    cards = json.loads(_strip_code_fence(response.text))
    for c in cards:
        if c.get("language") not in ("en", "tl", "zh"):
            c["language"] = "en"
    return cards
