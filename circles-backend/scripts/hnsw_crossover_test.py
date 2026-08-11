"""
Finds the chunk-count crossover where the HNSW index (note_chunks_embedding_idx)
starts beating a plain sequential scan for the conflict-detector neighbor query,
so SMALL_CIRCLE_CHUNK_THRESHOLD can be picked from a measurement instead of a
guess.

Seeds one synthetic circle (two users, two notes) and grows its chunk count
through SIZES, timing the real neighbor query at each size with the HNSW index
available vs. forced off (enable_indexscan/enable_bitmapscan = off), so the
only thing that changes between the two numbers is whether the vector index
gets consulted.

Everything runs inside a single transaction that's rolled back at the end (see
`finally`), so no synthetic rows or index growth survive the run even if it
errors partway through - safe to point at a real staging DB.

Usage:
    DATABASE_URL=<pooled staging url> python scripts/hnsw_crossover_test.py
"""
import asyncio
import random
import time
import uuid

import asyncpg

from app.core.config import settings
from app.services.conflict_detector import EF_SEARCH, NEIGHBORS_PER_CHUNK

# Chunk counts to test. 1660 is roughly the max a single circle can ever hold
# under CIRCLE_STORAGE_QUOTA_BYTES (12MB) today; 5000 is included past that
# ceiling just to see how the curve keeps moving.
SIZES = [100, 500, 1000, 1660, 5000]
EMBED_DIMS = 768
REPEATS = 5  # timed repetitions per size/plan, after one untimed warmup


def _random_unit_vector() -> list[float]:
    vec = [random.gauss(0, 1) for _ in range(EMBED_DIMS)]
    norm = sum(x * x for x in vec) ** 0.5
    return [x / norm for x in vec]


def _to_pgvector(vec: list[float]) -> str:
    return "[" + ",".join(str(x) for x in vec) + "]"


async def _insert_chunks(conn, circle_id: str, note_id: str, user_id: str, n: int):
    rows = [
        (note_id, circle_id, user_id, f"benchmark chunk {i}", _to_pgvector(_random_unit_vector()))
        for i in range(n)
    ]
    await conn.executemany(
        """
        INSERT INTO note_chunks (note_id, circle_id, user_id, content, embedding)
        VALUES ($1, $2, $3, $4, $5::vector)
        """,
        rows,
    )


NEIGHBOR_QUERY = """
    SELECT id, embedding <-> $2::vector AS distance
    FROM note_chunks
    WHERE circle_id = $1
      AND note_id != $3
      AND user_id != $4
    ORDER BY embedding <-> $2::vector
    LIMIT $5
"""


async def _time_query(conn, args: tuple, label: str) -> float:
    await conn.fetch(NEIGHBOR_QUERY, *args)  # warmup, discarded
    start = time.monotonic()
    for _ in range(REPEATS):
        await conn.fetch(NEIGHBOR_QUERY, *args)
    avg = (time.monotonic() - start) / REPEATS
    print(f"    {label}: {avg * 1000:.2f}ms avg over {REPEATS} runs")
    return avg


async def main():
    conn = await asyncpg.connect(settings.DATABASE_URL, statement_cache_size=0)
    tr = conn.transaction()
    await tr.start()
    try:
        circle_id, query_note_id, other_note_id = (str(uuid.uuid4()) for _ in range(3))
        querying_user_id, other_user_id = str(uuid.uuid4()), str(uuid.uuid4())

        await conn.executemany(
            "INSERT INTO users (id, firebase_uid, email) VALUES ($1, $2, $3)",
            [
                (querying_user_id, f"bench-{querying_user_id}", f"{querying_user_id}@bench.local"),
                (other_user_id, f"bench-{other_user_id}", f"{other_user_id}@bench.local"),
            ],
        )
        await conn.execute(
            "INSERT INTO circles (id, name, invite_code, owner_id) VALUES ($1, $2, $3, $4)",
            circle_id, "hnsw-crossover-benchmark", f"bench-{circle_id[:8]}", querying_user_id,
        )
        await conn.executemany(
            "INSERT INTO notes (id, circle_id, user_id, filename) VALUES ($1, $2, $3, $4)",
            [
                (query_note_id, circle_id, querying_user_id, "query-note.txt"),
                (other_note_id, circle_id, other_user_id, "other-note.txt"),
            ],
        )

        query_vec = _to_pgvector(_random_unit_vector())
        query_args = (circle_id, query_vec, query_note_id, querying_user_id, NEIGHBORS_PER_CHUNK)

        inserted = 0
        for size in SIZES:
            await _insert_chunks(conn, circle_id, other_note_id, other_user_id, size - inserted)
            inserted = size
            await conn.execute("ANALYZE note_chunks")
            print(f"\n{size} chunks:")

            await conn.execute("SET LOCAL enable_indexscan = on")
            await conn.execute("SET LOCAL enable_bitmapscan = on")
            await conn.execute(f"SET LOCAL hnsw.ef_search = {EF_SEARCH}")
            indexed = await _time_query(conn, query_args, "HNSW index scan (planner's choice)")

            await conn.execute("SET LOCAL enable_indexscan = off")
            await conn.execute("SET LOCAL enable_bitmapscan = off")
            sequential = await _time_query(conn, query_args, "forced sequential scan")

            winner = "HNSW" if indexed < sequential else "sequential scan"
            print(f"    -> {winner} faster at {size} chunks")
    finally:
        await tr.rollback()
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
