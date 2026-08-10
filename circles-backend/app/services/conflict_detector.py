"""Find chunks from different users in a circle that contradict each other.

Two passes, because embedding similarity alone doesn't mean disagreement — two
chunks that are near-duplicates in vector space are usually two people saying
the *same* thing about a topic:

1. Cheap: pgvector ANN search pulls each new chunk's nearest neighbours that
   were written by somebody else in the circle.
2. Expensive: Gemini classifies each surviving pair as agreement /
   contradiction / unrelated, and only contradictions are persisted.

Detection is scoped to one note's chunks vs. the rest of the circle, so an
upload costs O(new chunks) ANN queries rather than a full pairwise recompute.
"""
import asyncio
import json
import google.generativeai as genai
from app.core.config import settings
from app.db.database import get_pool

genai.configure(api_key=settings.GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

# Cosine distance below which two chunks are considered to be about the same
# thing and worth paying for an LLM check. 0.25 ~= cosine similarity 0.75.
SIMILARITY_THRESHOLD = 0.25
# Nearest neighbours to pull per new chunk before threshold filtering.
NEIGHBORS_PER_CHUNK = 5
# Hard ceiling on Gemini calls per note so a large upload into a large circle
# can't run up an unbounded bill.
MAX_PAIRS_PER_NOTE = 40


def _strip_code_fence(text: str) -> str:
    """Gemini often wraps JSON in a ```json ... ``` fence; unwrap it."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return text.strip()


def _classify_sync(text_a: str, text_b: str) -> dict:
    prompt = f"""You are checking two excerpts from different students' study notes on the same course.

Classify the relationship between them:
- "agreement": they state compatible facts, or one restates/expands the other.
- "contradiction": they state facts that cannot both be true (different dates, values, definitions, causes, or outcomes for the same thing).
- "unrelated": they are about different things, or too vague to compare.

Be strict: only use "contradiction" for a genuine factual conflict, not for a difference in wording, emphasis, or level of detail.

Return ONLY valid JSON, no markdown, no extra text:
{{
  "classification": "agreement|contradiction|unrelated",
  "explanation": "one sentence naming the specific facts that conflict, or an empty string if not a contradiction"
}}

Excerpt A:
{text_a}

Excerpt B:
{text_b}
"""
    response = model.generate_content(prompt)
    return json.loads(_strip_code_fence(response.text))


async def classify_pair(text_a: str, text_b: str) -> dict:
    """Classify one chunk pair. Returns {} if Gemini errors or replies unparseably.

    A bad reply on one pair shouldn't abort detection for the whole note, so
    failures degrade to "no conflict found" rather than raising.
    """
    try:
        # generate_content is a blocking network call; keep it off the loop.
        result = await asyncio.to_thread(_classify_sync, text_a, text_b)
    except Exception as e:
        print(f"Conflict classification failed: {e}")
        return {}
    return result if isinstance(result, dict) else {}


async def detect_conflicts_for_note(note_id: str, circle_id: str) -> int:
    """Compare one note's chunks against the circle's other users' chunks.

    Returns the number of contradictions persisted.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        new_chunks = await conn.fetch(
            """
            SELECT id, user_id, content, embedding::text AS embedding
            FROM note_chunks
            WHERE note_id = $1
            """,
            note_id,
        )
        if not new_chunks:
            return 0

        # Gather candidates first so all the ANN queries share one connection.
        candidates = []
        for chunk in new_chunks:
            neighbors = await conn.fetch(
                """
                SELECT id, note_id, user_id, content,
                       embedding <-> $2::vector AS distance
                FROM note_chunks
                WHERE circle_id = $1
                  AND note_id != $3
                  AND user_id != $4
                ORDER BY embedding <-> $2::vector
                LIMIT $5
                """,
                circle_id, chunk["embedding"], note_id, chunk["user_id"],
                NEIGHBORS_PER_CHUNK,
            )
            for other in neighbors:
                # Embeddings are L2-normalized (see services/embedding.py), so
                # l2^2 == 2 * cosine_distance. We order by `<->` to hit the
                # hnsw vector_l2_ops index, then convert for the threshold.
                cosine_distance = (other["distance"] ** 2) / 2
                if cosine_distance <= SIMILARITY_THRESHOLD:
                    candidates.append((chunk, other))

    candidates.sort(key=lambda pair: pair[1]["distance"])
    candidates = candidates[:MAX_PAIRS_PER_NOTE]
    if not candidates:
        return 0

    conflicts = []
    for chunk, other in candidates:
        result = await classify_pair(chunk["content"], other["content"])
        if result.get("classification") != "contradiction":
            continue
        explanation = (result.get("explanation") or "").strip()
        if not explanation:
            explanation = "These notes appear to state conflicting facts."
        conflicts.append((
            circle_id,
            chunk["id"], other["id"],
            note_id, other["note_id"],
            chunk["user_id"], other["user_id"],
            explanation[:1000],
        ))

    if not conflicts:
        return 0

    async with pool.acquire() as conn:
        await conn.executemany(
            """
            INSERT INTO conflicts
                (circle_id, chunk_a_id, chunk_b_id, note_a_id, note_b_id,
                 user_a_id, user_b_id, explanation)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (chunk_a_id, chunk_b_id) DO NOTHING
            """,
            conflicts,
        )
    print(f"Recorded {len(conflicts)} conflicts for note {note_id}")
    return len(conflicts)
