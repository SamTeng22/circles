import json
import google.generativeai as genai
from app.core.config import settings
from app.db.database import get_pool
from app.services.embedding import embed_text

genai.configure(api_key=settings.GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

async def retrieve_chunks(circle_id: str, topic: str, k: int = 10) -> list[str]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        if topic:
            query_embedding = await embed_text(topic)
            embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
            rows = await conn.fetch(
                """
                SELECT content FROM note_chunks
                WHERE circle_id = $1
                ORDER BY embedding <-> $2::vector
                LIMIT $3
                """,
                circle_id, embedding_str, k,
            )
        else:
            rows = await conn.fetch(
                "SELECT content FROM note_chunks WHERE circle_id = $1 LIMIT $2",
                circle_id, k,
            )
    return [r["content"] for r in rows]

async def generate_quiz_questions(
    circle_id: str,
    topic: str,
    num_questions: int,
) -> list[dict]:
    chunks = await retrieve_chunks(circle_id, topic)
    if not chunks:
        return []

    context = "\n\n".join(chunks)
    prompt = f"""You are a quiz generator. Based on the study notes below, generate {num_questions} multiple choice questions.

Use a mix of Bloom's taxonomy levels:
- Remembering: recall facts
- Understanding: explain concepts
- Applying: use knowledge in a new situation

Return ONLY a valid JSON array with this exact format, no markdown, no extra text:
[
  {{
    "question": "...",
    "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
    "correct_answer": "A. ...",
    "bloom_level": "remembering|understanding|applying",
    "explanation": "..."
  }}
]

Study notes:
{context}
"""
    response = model.generate_content(prompt)
    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)
