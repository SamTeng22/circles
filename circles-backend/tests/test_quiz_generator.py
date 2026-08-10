"""Tests for the quiz generator service.

Mirrors test_flashcard_generator.py's structure (Gemini and retrieval are
faked so no DB or network is needed), plus direct coverage of retrieve_chunks
itself, which flashcard_generator only reuses rather than redefining.
"""
import pytest

from app.services import quiz_generator as qg


class FakeResponse:
    def __init__(self, text):
        self.text = text


def _patch(monkeypatch, *, chunks, raw):
    """Fake retrieve_chunks -> chunks and model.generate_content -> raw text."""
    async def _retrieve(circle_id, topic, k=10):
        return chunks
    monkeypatch.setattr(qg, "retrieve_chunks", _retrieve)

    class FakeModel:
        def generate_content(self, prompt):
            return FakeResponse(raw)
    monkeypatch.setattr(qg, "model", FakeModel())


# --- generate_quiz_questions -------------------------------------------------

async def test_returns_empty_when_no_chunks(monkeypatch):
    # The model must not be called when there's nothing to build questions from.
    def _boom(prompt):
        raise AssertionError("model should not be called without chunks")
    _patch(monkeypatch, chunks=[], raw="")
    monkeypatch.setattr(qg.model, "generate_content", _boom)

    assert await qg.generate_quiz_questions("circle-1", "", 5) == []


async def test_parses_plain_json(monkeypatch):
    raw = (
        '[{"question": "What is X?", "options": ["A. x", "B. y"], '
        '"correct_answer": "A. x", "bloom_level": "remembering", "explanation": "e"}]'
    )
    _patch(monkeypatch, chunks=["some note text"], raw=raw)

    questions = await qg.generate_quiz_questions("circle-1", "", 5)

    assert questions == [{
        "question": "What is X?",
        "options": ["A. x", "B. y"],
        "correct_answer": "A. x",
        "bloom_level": "remembering",
        "explanation": "e",
    }]


async def test_strips_markdown_code_fence(monkeypatch):
    raw = (
        '```json\n[{"question": "Q", "options": ["A", "B"], "correct_answer": "A", '
        '"bloom_level": "understanding", "explanation": ""}]\n```'
    )
    _patch(monkeypatch, chunks=["ctx"], raw=raw)

    questions = await qg.generate_quiz_questions("circle-1", "photosynthesis", 3)

    assert questions[0]["question"] == "Q"
    assert questions[0]["correct_answer"] == "A"


# --- retrieve_chunks ---------------------------------------------------------

async def test_retrieve_chunks_without_topic_skips_embedding(monkeypatch, fake_pool, fake_conn):
    async def _get_pool():
        return fake_pool
    monkeypatch.setattr(qg, "get_pool", _get_pool)

    async def _boom(text):
        raise AssertionError("embed_text should not be called without a topic")
    monkeypatch.setattr(qg, "embed_text", _boom)

    fake_conn.queue_fetch([{"content": "chunk one"}, {"content": "chunk two"}])

    chunks = await qg.retrieve_chunks("circle-1", "", k=10)

    assert chunks == ["chunk one", "chunk two"]
    sql, args = fake_conn.calls[0]
    assert "note_chunks" in sql
    assert "embedding" not in sql
    assert args == ("circle-1", 10)


async def test_retrieve_chunks_with_topic_embeds_and_orders_by_similarity(monkeypatch, fake_pool, fake_conn):
    async def _get_pool():
        return fake_pool
    monkeypatch.setattr(qg, "get_pool", _get_pool)

    async def _fake_embed(text):
        assert text == "photosynthesis"
        return [0.1, 0.2, 0.3]
    monkeypatch.setattr(qg, "embed_text", _fake_embed)

    fake_conn.queue_fetch([{"content": "relevant chunk"}])

    chunks = await qg.retrieve_chunks("circle-1", "photosynthesis", k=5)

    assert chunks == ["relevant chunk"]
    sql, args = fake_conn.calls[0]
    assert "ORDER BY embedding <-> $2::vector" in sql
    assert args == ("circle-1", "[0.1,0.2,0.3]", 5)
