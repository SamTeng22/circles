"""Tests for the quiz generator service.

Mirrors test_flashcard_generator.py's structure (Gemini is faked so no DB or
network is needed), plus direct coverage of build_context, which
flashcard_generator reuses rather than redefining.
"""
import pytest

from app.services import quiz_generator as qg


class FakeResponse:
    def __init__(self, text):
        self.text = text


def _patch(monkeypatch, *, raw):
    class FakeModel:
        def generate_content(self, prompt):
            return FakeResponse(raw)
    monkeypatch.setattr(qg, "model", FakeModel())


def _patch_capturing_prompt(monkeypatch, *, raw):
    captured = {}
    class FakeModel:
        def generate_content(self, prompt):
            captured["prompt"] = prompt
            return FakeResponse(raw)
    monkeypatch.setattr(qg, "model", FakeModel())
    return captured


# --- generate_quiz_questions -------------------------------------------------

async def test_returns_empty_when_no_notes(monkeypatch):
    # The model must not be called when there's nothing to build questions from.
    def _boom(prompt):
        raise AssertionError("model should not be called without notes")
    _patch(monkeypatch, raw="")
    monkeypatch.setattr(qg.model, "generate_content", _boom)

    assert await qg.generate_quiz_questions([], 5) == []


async def test_parses_plain_json(monkeypatch):
    raw = (
        '[{"question": "What is X?", "options": ["A. x", "B. y"], '
        '"correct_answer": "A. x", "bloom_level": "remembering", "explanation": "e"}]'
    )
    _patch(monkeypatch, raw=raw)

    questions = await qg.generate_quiz_questions(
        [{"filename": "notes.txt", "content": "some note text"}], 5
    )

    assert questions == [{
        "question": "What is X?",
        "options": ["A. x", "B. y"],
        "correct_answer": "A. x",
        "bloom_level": "remembering",
        "explanation": "e",
        "language": "en",
    }]


async def test_keeps_valid_language_code(monkeypatch):
    raw = (
        '[{"question": "Ano ito?", "options": ["A", "B"], "correct_answer": "A", '
        '"bloom_level": "remembering", "explanation": "", "language": "tl"}]'
    )
    _patch(monkeypatch, raw=raw)

    questions = await qg.generate_quiz_questions(
        [{"filename": "notes.txt", "content": "tagalog notes"}], 1
    )

    assert questions[0]["language"] == "tl"


async def test_clamps_unrecognized_language_code(monkeypatch):
    raw = (
        '[{"question": "Q", "options": ["A", "B"], "correct_answer": "A", '
        '"bloom_level": "remembering", "explanation": "", "language": "french"}]'
    )
    _patch(monkeypatch, raw=raw)

    questions = await qg.generate_quiz_questions(
        [{"filename": "notes.txt", "content": "notes"}], 1
    )

    assert questions[0]["language"] == "en"


async def test_repairs_unescaped_latex_backslashes(monkeypatch):
    raw = (
        r'[{"question": "What is $\frac{1}{2} + \frac{1}{3}$?", '
        r'"options": ["A. $\frac{5}{6}$", "B. $\frac{2}{5}$"], '
        r'"correct_answer": "A. $\frac{5}{6}$", "bloom_level": "applying", "explanation": ""}]'
    )
    _patch(monkeypatch, raw=raw)

    questions = await qg.generate_quiz_questions(
        [{"filename": "notes.txt", "content": "fractions"}], 1
    )

    assert questions[0]["question"] == r"What is $\frac{1}{2} + \frac{1}{3}$?"
    assert questions[0]["correct_answer"] == r"A. $\frac{5}{6}$"


async def test_strips_markdown_code_fence(monkeypatch):
    raw = (
        '```json\n[{"question": "Q", "options": ["A", "B"], "correct_answer": "A", '
        '"bloom_level": "understanding", "explanation": ""}]\n```'
    )
    _patch(monkeypatch, raw=raw)

    questions = await qg.generate_quiz_questions(
        [{"filename": "notes.txt", "content": "photosynthesis basics"}], 3
    )

    assert questions[0]["question"] == "Q"
    assert questions[0]["correct_answer"] == "A"


# --- difficulty ---------------------------------------------------------------

async def test_defaults_to_medium_difficulty(monkeypatch):
    raw = '[{"question": "Q", "options": ["A", "B"], "correct_answer": "A", "bloom_level": "remembering", "explanation": ""}]'
    captured = _patch_capturing_prompt(monkeypatch, raw=raw)

    await qg.generate_quiz_questions([{"filename": "n.txt", "content": "c"}], 1)

    assert "Difficulty: MEDIUM" in captured["prompt"]


@pytest.mark.parametrize("difficulty,label", [("easy", "EASY"), ("hard", "HARD")])
async def test_passes_difficulty_into_prompt(monkeypatch, difficulty, label):
    raw = '[{"question": "Q", "options": ["A", "B"], "correct_answer": "A", "bloom_level": "remembering", "explanation": ""}]'
    captured = _patch_capturing_prompt(monkeypatch, raw=raw)

    await qg.generate_quiz_questions(
        [{"filename": "n.txt", "content": "c"}], 1, difficulty=difficulty
    )

    assert f"Difficulty: {label}" in captured["prompt"]


async def test_unrecognized_difficulty_falls_back_to_medium(monkeypatch):
    raw = '[{"question": "Q", "options": ["A", "B"], "correct_answer": "A", "bloom_level": "remembering", "explanation": ""}]'
    captured = _patch_capturing_prompt(monkeypatch, raw=raw)

    await qg.generate_quiz_questions(
        [{"filename": "n.txt", "content": "c"}], 1, difficulty="extreme"
    )

    assert "Difficulty: MEDIUM" in captured["prompt"]


# --- build_context -----------------------------------------------------------

def test_build_context_joins_notes_with_filename_headers():
    notes = [
        {"filename": "a.txt", "content": "chunk one"},
        {"filename": "b.txt", "content": "chunk two"},
    ]

    context = qg.build_context(notes)

    assert context == "### a.txt\nchunk one\n\n### b.txt\nchunk two"
