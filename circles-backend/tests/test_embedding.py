"""Tests for the embedding service used by the background tasks."""
import asyncio
import threading

import pytest

from app.services import embedding


async def test_embed_text_runs_off_the_event_loop(monkeypatch):
    """The Gemini call is blocking; it must run in a worker thread so it can't
    stall the asyncio event loop (the cause of the earlier UI freeze)."""
    loop_thread = threading.current_thread()
    seen = {}

    def fake_embed_content(**kwargs):
        seen["thread"] = threading.current_thread()
        return {"embedding": [3.0, 4.0]}  # deliberately un-normalized

    monkeypatch.setattr(embedding.genai, "embed_content", fake_embed_content)

    vec = await embedding.embed_text("hello world")

    # Ran somewhere other than the event loop thread.
    assert seen["thread"] is not loop_thread
    # Result is L2-normalized: [3, 4] -> [0.6, 0.8].
    assert vec == pytest.approx([0.6, 0.8])


async def test_embed_text_does_not_block_the_loop(monkeypatch):
    """While embed_text is awaiting, other coroutines should still make progress."""
    release = threading.Event()

    def blocking_embed(**kwargs):
        release.wait(timeout=2)  # block the worker thread, not the loop
        return {"embedding": [1.0, 0.0]}

    monkeypatch.setattr(embedding.genai, "embed_content", blocking_embed)

    progressed = False

    async def other_work():
        nonlocal progressed
        await asyncio.sleep(0.05)
        progressed = True
        release.set()  # let the blocked embed finish

    _, vec = await asyncio.gather(other_work(), embedding.embed_text("x"))

    assert progressed  # the loop kept running while embed was blocked
    assert vec == pytest.approx([1.0, 0.0])


async def test_chunk_and_embed_inserts_one_row_per_chunk(monkeypatch, fake_pool, fake_conn):
    async def _get_pool():
        return fake_pool
    monkeypatch.setattr(embedding, "get_pool", _get_pool)

    async def fake_embed_text(text):
        return [0.1, 0.2, 0.3]
    monkeypatch.setattr(embedding, "embed_text", fake_embed_text)

    # ~450 words -> two sliding-window chunks (size 400, overlap 50).
    content = " ".join(f"word{i}" for i in range(450))

    await embedding.chunk_and_embed(
        note_id="note-1", circle_id="circle-1", user_id="user-1", content=content
    )

    inserts = fake_conn.statements_matching("INSERT INTO note_chunks")
    assert len(inserts) == 2
    # note_id is the first bound parameter on each insert.
    assert all(args[0] == "note-1" for _, args in inserts)


def test_semantic_chunk_drops_tiny_fragments():
    # A short string (<50 chars after joining) produces no chunks worth embedding.
    assert embedding.semantic_chunk("too short") == []
