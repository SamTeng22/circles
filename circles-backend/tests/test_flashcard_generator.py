"""Tests for the flashcard generator service.

These pin the parsing contract: selected notes are joined into context, the
model's JSON reply is parsed, and Gemini's markdown code-fence wrapping is
stripped. The model is faked so no DB or network is needed.
"""
import pytest

from app.services import flashcard_generator as fg


class FakeResponse:
    def __init__(self, text):
        self.text = text


def _patch(monkeypatch, *, raw):
    class FakeModel:
        def generate_content(self, prompt):
            return FakeResponse(raw)
    monkeypatch.setattr(fg, "model", FakeModel())


async def test_returns_empty_when_no_notes(monkeypatch):
    # The model must not be called when there's nothing to build cards from.
    def _boom(prompt):
        raise AssertionError("model should not be called without notes")
    _patch(monkeypatch, raw="")
    monkeypatch.setattr(fg.model, "generate_content", _boom)

    assert await fg.generate_flashcards([], 5) == []


async def test_parses_plain_json(monkeypatch):
    raw = '[{"front": "What is X?", "back": "X is Y", "hint": ""}]'
    _patch(monkeypatch, raw=raw)

    cards = await fg.generate_flashcards(
        [{"filename": "notes.txt", "content": "some note text"}], 5
    )

    assert cards == [{"front": "What is X?", "back": "X is Y", "hint": "", "language": "en"}]


async def test_clamps_unrecognized_language_code(monkeypatch):
    raw = '[{"front": "Q", "back": "A", "hint": "", "language": "french"}]'
    _patch(monkeypatch, raw=raw)

    cards = await fg.generate_flashcards(
        [{"filename": "notes.txt", "content": "notes"}], 1
    )

    assert cards[0]["language"] == "en"


async def test_strips_markdown_code_fence(monkeypatch):
    raw = '```json\n[{"front": "Q", "back": "A", "hint": "h"}]\n```'
    _patch(monkeypatch, raw=raw)

    cards = await fg.generate_flashcards(
        [{"filename": "notes.txt", "content": "ctx"}], 3
    )

    assert cards[0]["front"] == "Q"
    assert cards[0]["back"] == "A"


async def test_repairs_unescaped_latex_backslashes(monkeypatch):
    raw = r'[{"front": "Derivative of $x^3$?", "back": "$\frac{d}{dx} x^3 = 3x^2$", "hint": ""}]'
    _patch(monkeypatch, raw=raw)

    cards = await fg.generate_flashcards(
        [{"filename": "notes.txt", "content": "calc notes"}], 1
    )

    assert cards[0]["back"] == r"$\frac{d}{dx} x^3 = 3x^2$"
