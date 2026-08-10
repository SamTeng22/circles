"""
Concurrency smoke test against a real (staging) database + connection pool.
Bypasses Firebase token verification only; the DB pool, pooled Neon
connection, and parameterized queries in get_current_user are all real.

Usage:
    DATABASE_URL=<pooled staging url> python scripts/concurrency_test.py
"""
import asyncio
import logging
import time
from unittest.mock import patch

import httpx

from app.main import app
from app.db.database import init_db

logging.basicConfig(level=logging.INFO)

N_CONCURRENT = 30


def fake_verify_id_token(token, *a, **kw):
    return {"uid": token, "email": f"{token}@loadtest.local", "name": token}


async def hit(client: httpx.AsyncClient, i: int):
    token = f"loadtest-user-{i}"
    start = time.monotonic()
    resp = await client.get(
        "/api/notes/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {token}"},
    )
    return i, resp.status_code, time.monotonic() - start


async def main():
    await init_db()  # ensures the pool is initialized; tables already exist
    with patch("firebase_admin.auth.verify_id_token", side_effect=fake_verify_id_token):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            start = time.monotonic()
            results = await asyncio.gather(*[hit(client, i) for i in range(N_CONCURRENT)])
            total = time.monotonic() - start

    for i, status, dur in sorted(results):
        print(f"user-{i}: {status} in {dur:.2f}s")
    print(f"\n{N_CONCURRENT} concurrent requests finished in {total:.2f}s")

    bad = [r for r in results if r[1] not in (200, 403, 404)]
    if bad:
        print(f"\n{len(bad)} unexpected responses (likely pool/pooling errors): {bad}")


if __name__ == "__main__":
    asyncio.run(main())