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


MC_ONLY = {"multiple_choice": 5, "true_false": 0, "fill_in_blank": 0, "matching": 0}


def _counts(**overrides):
    return {**MC_ONLY, **overrides}


# --- generate_quiz_questions -------------------------------------------------

async def test_returns_empty_when_no_notes(monkeypatch):
    # The model must not be called when there's nothing to build questions from.
    def _boom(prompt):
        raise AssertionError("model should not be called without notes")
    _patch(monkeypatch, raw="")
    monkeypatch.setattr(qg.model, "generate_content", _boom)

    assert await qg.generate_quiz_questions([], MC_ONLY) == []


async def test_returns_empty_when_no_types_requested(monkeypatch):
    def _boom(prompt):
        raise AssertionError("model should not be called with an empty type mix")
    _patch(monkeypatch, raw="")
    monkeypatch.setattr(qg.model, "generate_content", _boom)

    empty_counts = {"multiple_choice": 0, "true_false": 0, "fill_in_blank": 0, "matching": 0}
    assert await qg.generate_quiz_questions(
        [{"filename": "n.txt", "content": "c"}], empty_counts
    ) == []


async def test_parses_plain_json(monkeypatch):
    raw = (
        '[{"question_type": "multiple_choice", "question": "What is X?", '
        '"options": ["A. x", "B. y"], "correct_answer": "A. x", '
        '"bloom_level": "remembering", "explanation": "e"}]'
    )
    _patch(monkeypatch, raw=raw)

    questions = await qg.generate_quiz_questions(
        [{"filename": "notes.txt", "content": "some note text"}], MC_ONLY
    )

    assert questions == [{
        "question_type": "multiple_choice",
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
        [{"filename": "notes.txt", "content": "tagalog notes"}], _counts(multiple_choice=1)
    )

    assert questions[0]["language"] == "tl"


async def test_clamps_unrecognized_language_code(monkeypatch):
    raw = (
        '[{"question": "Q", "options": ["A", "B"], "correct_answer": "A", '
        '"bloom_level": "remembering", "explanation": "", "language": "french"}]'
    )
    _patch(monkeypatch, raw=raw)

    questions = await qg.generate_quiz_questions(
        [{"filename": "notes.txt", "content": "notes"}], _counts(multiple_choice=1)
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
        [{"filename": "notes.txt", "content": "fractions"}], _counts(multiple_choice=1)
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
        [{"filename": "notes.txt", "content": "photosynthesis basics"}], _counts(multiple_choice=3)
    )

    assert questions[0]["question"] == "Q"
    assert questions[0]["correct_answer"] == "A"


# --- difficulty ---------------------------------------------------------------

async def test_defaults_to_medium_difficulty(monkeypatch):
    raw = '[{"question": "Q", "options": ["A", "B"], "correct_answer": "A", "bloom_level": "remembering", "explanation": ""}]'
    captured = _patch_capturing_prompt(monkeypatch, raw=raw)

    await qg.generate_quiz_questions([{"filename": "n.txt", "content": "c"}], _counts(multiple_choice=1))

    assert "Difficulty: MEDIUM" in captured["prompt"]


@pytest.mark.parametrize("difficulty,label", [("easy", "EASY"), ("hard", "HARD")])
async def test_passes_difficulty_into_prompt(monkeypatch, difficulty, label):
    raw = '[{"question": "Q", "options": ["A", "B"], "correct_answer": "A", "bloom_level": "remembering", "explanation": ""}]'
    captured = _patch_capturing_prompt(monkeypatch, raw=raw)

    await qg.generate_quiz_questions(
        [{"filename": "n.txt", "content": "c"}], _counts(multiple_choice=1), difficulty=difficulty
    )

    assert f"Difficulty: {label}" in captured["prompt"]


async def test_unrecognized_difficulty_falls_back_to_medium(monkeypatch):
    raw = '[{"question": "Q", "options": ["A", "B"], "correct_answer": "A", "bloom_level": "remembering", "explanation": ""}]'
    captured = _patch_capturing_prompt(monkeypatch, raw=raw)

    await qg.generate_quiz_questions(
        [{"filename": "n.txt", "content": "c"}], _counts(multiple_choice=1), difficulty="extreme"
    )

    assert "Difficulty: MEDIUM" in captured["prompt"]


# --- question type mix in the prompt -----------------------------------------

async def test_prompt_includes_only_requested_type_blocks(monkeypatch):
    raw = '[{"question": "Q", "options": ["A", "B"], "correct_answer": "A", "bloom_level": "remembering", "explanation": ""}]'
    captured = _patch_capturing_prompt(monkeypatch, raw=raw)

    await qg.generate_quiz_questions(
        [{"filename": "n.txt", "content": "c"}],
        {"multiple_choice": 3, "true_false": 2, "fill_in_blank": 0, "matching": 0},
    )

    prompt = captured["prompt"]
    assert "3 multiple choice question(s)" in prompt
    assert "2 true/false question(s)" in prompt
    assert '"question_type": "true_false"' in prompt
    assert '"question_type": "fill_in_blank"' not in prompt
    assert '"question_type": "matching"' not in prompt


async def test_prompt_includes_fill_in_blank_and_matching_blocks(monkeypatch):
    raw = '[{"question": "Q", "options": ["A", "B"], "correct_answer": "A", "bloom_level": "remembering", "explanation": ""}]'
    captured = _patch_capturing_prompt(monkeypatch, raw=raw)

    await qg.generate_quiz_questions(
        [{"filename": "n.txt", "content": "c"}],
        {"multiple_choice": 0, "true_false": 0, "fill_in_blank": 2, "matching": 1},
    )

    prompt = captured["prompt"]
    assert '"question_type": "fill_in_blank"' in prompt
    assert '"question_type": "matching"' in prompt
    assert '"question_type": "multiple_choice"' not in prompt
    assert "_____" in prompt


# --- per-type normalization ---------------------------------------------------

async def test_defaults_missing_question_type_to_multiple_choice(monkeypatch):
    raw = '[{"question": "Q", "options": ["A", "B"], "correct_answer": "A", "bloom_level": "remembering", "explanation": ""}]'
    _patch(monkeypatch, raw=raw)

    questions = await qg.generate_quiz_questions([{"filename": "n.txt", "content": "c"}], _counts(multiple_choice=1))

    assert questions[0]["question_type"] == "multiple_choice"


async def test_true_false_options_and_answer_are_pinned(monkeypatch):
    raw = (
        '[{"question_type": "true_false", "question": "Is the sky blue?", '
        '"options": ["yes", "no"], "correct_answer": "true", '
        '"bloom_level": "remembering", "explanation": ""}]'
    )
    _patch(monkeypatch, raw=raw)

    questions = await qg.generate_quiz_questions(
        [{"filename": "n.txt", "content": "c"}], _counts(multiple_choice=0, true_false=1)
    )

    assert questions[0]["options"] == ["True", "False"]
    assert questions[0]["correct_answer"] == "True"


async def test_true_false_handles_boolean_model_output(monkeypatch):
    raw = (
        '[{"question_type": "true_false", "question": "Is the sky blue?", '
        '"correct_answer": false, "bloom_level": "remembering", "explanation": ""}]'
    )
    _patch(monkeypatch, raw=raw)

    questions = await qg.generate_quiz_questions(
        [{"filename": "n.txt", "content": "c"}], _counts(multiple_choice=0, true_false=1)
    )

    assert questions[0]["correct_answer"] == "False"


async def test_fill_in_blank_auto_appends_blank_marker(monkeypatch):
    raw = (
        '[{"question_type": "fill_in_blank", "question": "The powerhouse of the cell is the mitochondria.", '
        '"accepted_answers": ["mitochondria"], "correct_answer": "mitochondria", '
        '"bloom_level": "remembering", "explanation": ""}]'
    )
    _patch(monkeypatch, raw=raw)

    questions = await qg.generate_quiz_questions(
        [{"filename": "n.txt", "content": "c"}], _counts(multiple_choice=0, fill_in_blank=1)
    )

    assert questions[0]["question"].endswith("_____")


async def test_fill_in_blank_keeps_existing_blank_marker(monkeypatch):
    raw = (
        '[{"question_type": "fill_in_blank", "question": "The _____ is the powerhouse of the cell.", '
        '"accepted_answers": ["mitochondria"], "correct_answer": "mitochondria", '
        '"bloom_level": "remembering", "explanation": ""}]'
    )
    _patch(monkeypatch, raw=raw)

    questions = await qg.generate_quiz_questions(
        [{"filename": "n.txt", "content": "c"}], _counts(multiple_choice=0, fill_in_blank=1)
    )

    assert questions[0]["question"] == "The _____ is the powerhouse of the cell."


async def test_fill_in_blank_falls_back_accepted_answers_to_correct_answer(monkeypatch):
    raw = (
        '[{"question_type": "fill_in_blank", "question": "The _____ is the powerhouse of the cell.", '
        '"correct_answer": "mitochondria", "bloom_level": "remembering", "explanation": ""}]'
    )
    _patch(monkeypatch, raw=raw)

    questions = await qg.generate_quiz_questions(
        [{"filename": "n.txt", "content": "c"}], _counts(multiple_choice=0, fill_in_blank=1)
    )

    assert questions[0]["accepted_answers"] == ["mitochondria"]


async def test_matching_pairs_pass_through_untouched(monkeypatch):
    raw = (
        '[{"question_type": "matching", "question": "Match them.", '
        '"pairs": [{"left": "A", "right": "1"}, {"left": "B", "right": "2"}], '
        '"bloom_level": "understanding", "explanation": ""}]'
    )
    _patch(monkeypatch, raw=raw)

    questions = await qg.generate_quiz_questions(
        [{"filename": "n.txt", "content": "c"}], _counts(multiple_choice=0, matching=1)
    )

    assert questions[0]["pairs"] == [{"left": "A", "right": "1"}, {"left": "B", "right": "2"}]


# --- build_context -----------------------------------------------------------

def test_build_context_joins_notes_with_filename_headers():
    notes = [
        {"filename": "a.txt", "content": "chunk one"},
        {"filename": "b.txt", "content": "chunk two"},
    ]

    context = qg.build_context(notes)

    assert context == "### a.txt\nchunk one\n\n### b.txt\nchunk two"
