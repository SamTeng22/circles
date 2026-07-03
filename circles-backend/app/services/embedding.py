import asyncio
import math
import google.generativeai as genai
from app.core.config import settings
from app.db.database import get_pool

genai.configure(api_key=settings.GEMINI_API_KEY)

# gemini-embedding-001 defaults to 3072 dims; we pin to 768 to match the
# note_chunks.embedding vector(768) column. Reduced-dimension outputs aren't
# pre-normalized, so we L2-normalize for stable similarity search.
EMBED_MODEL = "models/gemini-embedding-001"
EMBED_DIMS = 768
# Max inputs to send to embed_content in a single request.
EMBED_BATCH = 100


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec] if norm else vec

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

def _embed_sync(text: str) -> list[float]:
    result = genai.embed_content(
        model=EMBED_MODEL,
        content=text,
        task_type="retrieval_document",
        output_dimensionality=EMBED_DIMS,
    )
    return _normalize(result["embedding"])

async def embed_text(text: str) -> list[float]:
    # genai.embed_content is a blocking network call; run it off the event loop
    # so background embedding never stalls the API server.
    return await asyncio.to_thread(_embed_sync, text)

def _embed_batch_sync(texts: list[str]) -> list[list[float]]:
    result = genai.embed_content(
        model=EMBED_MODEL,
        content=texts,
        task_type="retrieval_document",
        output_dimensionality=EMBED_DIMS,
    )
    return [_normalize(v) for v in result["embedding"]]

async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed many chunks with as few Gemini round-trips as possible.

    embed_content takes a list, so a whole note is one request instead of one
    per chunk; we still chunk into EMBED_BATCH-sized requests to stay within the
    API's per-request input cap.
    """
    if not texts:
        return []
    vectors: list[list[float]] = []
    for start in range(0, len(texts), EMBED_BATCH):
        batch = texts[start : start + EMBED_BATCH]
        vectors.extend(await asyncio.to_thread(_embed_batch_sync, batch))
    return vectors

async def chunk_and_embed(
    note_id: str,
    circle_id: str,
    user_id: str,
    content: str,
):
    chunks = semantic_chunk(content)
    if not chunks:
        print(f"No embeddable chunks for note {note_id}")
        return

    embeddings = await embed_batch(chunks)
    rows = [
        (
            note_id, circle_id, user_id, chunk_text,
            "[" + ",".join(str(x) for x in embedding) + "]",
        )
        for chunk_text, embedding in zip(chunks, embeddings)
    ]

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.executemany(
            """
            INSERT INTO note_chunks (note_id, circle_id, user_id, content, embedding)
            VALUES ($1, $2, $3, $4, $5::vector)
            """,
            rows,
        )
    print(f"Stored {len(chunks)} chunks for note {note_id}")
