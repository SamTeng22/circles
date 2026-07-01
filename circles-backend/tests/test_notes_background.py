"""Tests for the note-processing background tasks.

These cover `_process_note` (runs after upload) and `_reembed_note` (runs after
an edit): the extract -> embed -> mark-ready pipeline and its failure handling.
The status transitions here are exactly what left a note stuck at "processing"
when the embedding step blocked/crashed, so they're worth pinning down.
"""
import pytest

from app.api.routes import notes


@pytest.fixture(autouse=True)
def patch_pool(monkeypatch, fake_pool):
    """Point the notes module's get_pool at the in-memory fake pool."""
    async def _get_pool():
        return fake_pool
    monkeypatch.setattr(notes, "get_pool", _get_pool)
    return fake_pool


def _patch_extract(monkeypatch, *, returns=None, raises=None):
    def _extract(data, content_type, filename=""):
        if raises:
            raise raises
        return returns
    monkeypatch.setattr(notes.extract, "extract_text", _extract)


def _patch_embed(monkeypatch, *, raises=None):
    calls = []
    async def _embed(**kwargs):
        calls.append(kwargs)
        if raises:
            raise raises
    monkeypatch.setattr(notes, "chunk_and_embed", _embed)
    return calls


def _final_status(conn):
    """Return the status set by the last `UPDATE notes SET status = ...` call."""
    updates = conn.statements_matching("SET status")
    assert updates, "expected a status update"
    sql = updates[-1][0]
    if "'ready'" in sql:
        return "ready"
    if "'failed'" in sql:
        return "failed"
    return None


# --- _process_note ---------------------------------------------------------

async def test_process_note_success(monkeypatch, fake_conn):
    _patch_extract(monkeypatch, returns="extracted body text")
    embed_calls = _patch_embed(monkeypatch)

    await notes._process_note(
        "note-1", "circle-1", "user-1", b"raw", "text/plain", "a.txt"
    )

    # Extracted text is persisted...
    content_updates = fake_conn.statements_matching("SET content")
    assert content_updates and content_updates[0][1][0] == "extracted body text"
    # ...embedding runs on that text...
    assert embed_calls and embed_calls[0]["content"] == "extracted body text"
    # ...and the note lands "ready".
    assert _final_status(fake_conn) == "ready"
    assert not fake_conn.ran("'failed'")


async def test_process_note_marks_failed_when_extract_raises(monkeypatch, fake_conn):
    _patch_extract(monkeypatch, raises=ValueError("corrupt pdf"))
    embed_calls = _patch_embed(monkeypatch)

    await notes._process_note(
        "note-1", "circle-1", "user-1", b"raw", "application/pdf", "a.pdf"
    )

    # Embedding never runs if extraction blew up.
    assert embed_calls == []
    assert _final_status(fake_conn) == "failed"
    # The error message is recorded for the UI.
    failed = fake_conn.statements_matching("status = 'failed'")[0]
    assert "corrupt pdf" in failed[1][0]


async def test_process_note_marks_failed_when_embed_raises(monkeypatch, fake_conn):
    _patch_extract(monkeypatch, returns="some text")
    _patch_embed(monkeypatch, raises=RuntimeError("embedding API down"))

    await notes._process_note(
        "note-1", "circle-1", "user-1", b"raw", "text/plain", "a.txt"
    )

    assert _final_status(fake_conn) == "failed"
    failed = fake_conn.statements_matching("status = 'failed'")[0]
    assert "embedding API down" in failed[1][0]


# --- _reembed_note ---------------------------------------------------------

async def test_reembed_note_success(monkeypatch, fake_conn):
    embed_calls = _patch_embed(monkeypatch)

    await notes._reembed_note("note-1", "circle-1", "user-1", "edited content")

    # Old chunks are cleared before re-embedding the edited text.
    assert fake_conn.ran("DELETE FROM note_chunks")
    assert embed_calls and embed_calls[0]["content"] == "edited content"
    assert _final_status(fake_conn) == "ready"
    assert not fake_conn.ran("'failed'")


async def test_reembed_note_marks_failed_when_embed_raises(monkeypatch, fake_conn):
    _patch_embed(monkeypatch, raises=RuntimeError("boom"))

    await notes._reembed_note("note-1", "circle-1", "user-1", "edited content")

    assert _final_status(fake_conn) == "failed"
    failed = fake_conn.statements_matching("status = 'failed'")[0]
    assert "boom" in failed[1][0]
