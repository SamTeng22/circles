import google.generativeai as genai
from app.core.config import settings
from app.db.database import get_pool

genai.configure(api_key=settings.GEMINI_API_KEY)

def semantic_chunk(text: str, chunk_size: int = 400, overlap: int = 50) -> list[str]:
    """Simple sliding window chunker. Replace with semantic chunker later."""
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return [c for c in chunks if len(c.strip()) > 50]

async def embed_text(text: str) -> list[float]:
    result = genai.embed_content(
        model="models/text-embedding-004",
        content=text,
        task_type="retrieval_document",
    )
    return result["embedding"]

async def chunk_and_embed(
    note_id: str,
    circle_id: str,
    user_id: str,
    content: str,
):
    chunks = semantic_chunk(content)
    pool = await get_pool()
    async with pool.acquire() as conn:
        for chunk_text in chunks:
            embedding = await embed_text(chunk_text)
            embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
            await conn.execute(
                """
                INSERT INTO note_chunks (note_id, circle_id, user_id, content, embedding)
                VALUES ($1, $2, $3, $4, $5::vector)
                """,
                note_id, circle_id, user_id, chunk_text, embedding_str,
            )
    print(f"Stored {len(chunks)} chunks for note {note_id}")
