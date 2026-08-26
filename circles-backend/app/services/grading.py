from typing import Any


def grade_question(question: dict, submitted: Any) -> bool:
    """True iff `submitted` is a fully-correct answer for `question`.

    Missing/unrecognized question_type defaults to "multiple_choice" so
    pre-existing rows (generated before question_type existed) keep grading
    the way they always have.
    """
    qtype = question.get("question_type") or "multiple_choice"
    if qtype in ("multiple_choice", "true_false"):
        return submitted == question.get("correct_answer")
    if qtype == "fill_in_blank":
        return _grade_fill_in_blank(question, submitted)
    if qtype == "matching":
        return _grade_matching(question, submitted)
    return False


def _normalize(s: str) -> str:
    return " ".join(s.strip().lower().split())


def _grade_fill_in_blank(question: dict, submitted: Any) -> bool:
    if not isinstance(submitted, str):
        return False
    accepted = question.get("accepted_answers") or (
        [question["correct_answer"]] if question.get("correct_answer") else []
    )
    accepted_norm = {_normalize(a) for a in accepted if isinstance(a, str)}
    return _normalize(submitted) in accepted_norm


def _grade_matching(question: dict, submitted: Any) -> bool:
    if not isinstance(submitted, dict):
        return False
    pairs = question.get("pairs") or []
    if not pairs or len(submitted) != len(pairs):
        return False
    return all(submitted.get(p.get("left")) == p.get("right") for p in pairs)
