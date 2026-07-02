"""Tests for the flashcard generator service.

These pin the parsing contract: chunks are retrieved from the circle's notes,
the model's JSON reply is parsed, and Gemini's markdown code-fence wrapping is
stripped. Retrieval and the model are faked so no DB or network is needed.
"""
import pytest

from app.services import flashcard_generator as fg


class FakeResponse:
    def __init__(self, text):
        self.text = text


def _patch(monkeypatch, *, chunks, raw):
    """Fake retrieve_chunks -> chunks and model.generate_content -> raw text."""
    async def _retrieve(circle_id, topic, k=10):
        return chunks
    monkeypatch.setattr(fg, "retrieve_chunks", _retrieve)

    class FakeModel:
        def generate_content(self, prompt):
            return FakeResponse(raw)
    monkeypatch.setattr(fg, "model", FakeModel())


async def test_returns_empty_when_no_chunks(monkeypatch):
    # The model must not be called when there's nothing to build cards from.
    def _boom(prompt):
        raise AssertionError("model should not be called without chunks")
    _patch(monkeypatch, chunks=[], raw="")
    monkeypatch.setattr(fg.model, "generate_content", _boom)

    assert await fg.generate_flashcards("circle-1", "", 5) == []


async def test_parses_plain_json(monkeypatch):
    raw = '[{"front": "What is X?", "back": "X is Y", "hint": ""}]'
    _patch(monkeypatch, chunks=["some note text"], raw=raw)

    cards = await fg.generate_flashcards("circle-1", "", 5)

    assert cards == [{"front": "What is X?", "back": "X is Y", "hint": ""}]


async def test_strips_markdown_code_fence(monkeypatch):
    raw = '```json\n[{"front": "Q", "back": "A", "hint": "h"}]\n```'
    _patch(monkeypatch, chunks=["ctx"], raw=raw)

    cards = await fg.generate_flashcards("circle-1", "photosynthesis", 3)

    assert cards[0]["front"] == "Q"
    assert cards[0]["back"] == "A"


def test_strip_code_fence_passes_through_bare_json():
    assert fg._strip_code_fence('  [{"front":"a"}] ') == '[{"front":"a"}]'
