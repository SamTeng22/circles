"""
Times a single asyncpg connection + trivial query against DATABASE_URL, run
three times in a row (sequentially, not concurrently).

Isolates raw per-connection latency from the concurrency test's "~20
connections opened at once" effect, to figure out whether the 4-5s seen
there is an inherent per-connection cost (compute wake, network/region,
DNS) or a burst/contention cost specific to opening many connections at
the same time.

Usage:
    DATABASE_URL=<pooled staging url> python scripts/single_connection_test.py
"""
import asyncio
import time

import asyncpg

from app.core.config import settings


async def main():
    for i in range(3):
        start = time.monotonic()
        conn = await asyncpg.connect(settings.DATABASE_URL, statement_cache_size=0)
        connected = time.monotonic()
        await conn.fetchval("SELECT 1")
        queried = time.monotonic()
        await conn.close()
        print(
            f"attempt {i}: connect={connected - start:.2f}s  "
            f"query={queried - connected:.2f}s"
        )


if __name__ == "__main__":
    asyncio.run(main())
