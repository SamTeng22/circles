import json
import google.generativeai as genai
from app.core.config import settings
# Reuse the same retrieval-over-note-chunks logic the quiz generator uses so
# flashcards are grounded in the circle's pooled notes.
from app.services.quiz_generator import retrieve_chunks

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
    circle_id: str,
    topic: str,
    num_cards: int,
) -> list[dict]:
    chunks = await retrieve_chunks(circle_id, topic)
    if not chunks:
        return []

    context = "\n\n".join(chunks)
    prompt = f"""You are a flashcard generator for students. Based on the study notes below, generate {num_cards} flashcards.

Each flashcard has a short prompt on the front and a concise, self-contained answer on the back. Favor one idea per card: key terms, definitions, cause/effect, and important facts. Keep fronts under ~15 words and backs under ~40 words.

Return ONLY a valid JSON array with this exact format, no markdown, no extra text:
[
  {{
    "front": "...",
    "back": "...",
    "hint": "..."
  }}
]

The "hint" is optional context (leave as an empty string if not useful).

Study notes:
{context}
"""
    response = model.generate_content(prompt)
    return json.loads(_strip_code_fence(response.text))
