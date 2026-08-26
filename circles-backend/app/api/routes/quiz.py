import json
from typing import Literal, Union
from fastapi import APIRouter, Depends, HTTPException, Request
from google.api_core.exceptions import GoogleAPICallError
from pydantic import BaseModel, Field, model_validator
from app.core.config import settings
from app.core.firebase import get_current_user
from app.core.gemini_errors import friendly_gemini_error
from app.core.rate_limit import limiter, identify_user, quiz_generation_limit
from app.db.database import get_pool
from app.services.authz import assert_member
from app.services.grading import grade_question
from app.services.quiz_generator import generate_quiz_questions

router = APIRouter()


async def _fetch_selected_notes(conn, circle_id: str, note_ids: list[str]) -> list[dict]:
    rows = await conn.fetch(
        """
        SELECT id, filename, content FROM notes
        WHERE circle_id = $1 AND id = ANY($2::uuid[]) AND status = 'ready'
        """,
        circle_id, note_ids,
    )
    found_ids = {str(r["id"]) for r in rows}
    missing = [nid for nid in note_ids if nid not in found_ids]
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Note(s) not found or not ready: {', '.join(missing)}",
        )
    total_chars = sum(len(r["content"] or "") for r in rows)
    if total_chars > settings.GENERATION_CONTEXT_CHAR_LIMIT:
        raise HTTPException(
            status_code=400,
            detail="Selected notes are too large — remove some and try again",
        )
    return [dict(r) for r in rows]


class QuestionTypeCounts(BaseModel):
    multiple_choice: int = Field(default=0, ge=0, le=30)
    true_false: int = Field(default=0, ge=0, le=30)
    fill_in_blank: int = Field(default=0, ge=0, le=30)
    matching: int = Field(default=0, ge=0, le=30)

    @model_validator(mode="after")
    def _check_total(self):
        total = self.multiple_choice + self.true_false + self.fill_in_blank + self.matching
        if not (1 <= total <= 30):
            raise ValueError("Total question count must be between 1 and 30")
        return self


class GenerateQuizRequest(BaseModel):
    circle_id: str
    title: str
    note_ids: list[str] = Field(min_length=1)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    question_types: QuestionTypeCounts

@router.post("/generate")
@limiter.limit(quiz_generation_limit)
async def generate_quiz(
    request: Request,
    body: GenerateQuizRequest,
    current_user: dict = Depends(identify_user),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await assert_member(conn, body.circle_id, current_user["id"])
        notes = await _fetch_selected_notes(conn, body.circle_id, body.note_ids)

    try:
        questions = await generate_quiz_questions(
            notes=notes,
            question_type_counts=body.question_types.model_dump(),
            difficulty=body.difficulty,
        )
    except GoogleAPICallError as e:
        raise HTTPException(status_code=503, detail=friendly_gemini_error(e))

    async with pool.acquire() as conn:
        quiz = await conn.fetchrow(
            """
            INSERT INTO quizzes (circle_id, created_by, title, questions)
            VALUES ($1, $2, $3, $4::jsonb) RETURNING *
            """,
            body.circle_id, current_user["id"], body.title, questions,
        )
    return dict(quiz)

@router.get("/detail/{quiz_id}")
async def get_quiz(
    quiz_id: str,
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        quiz = await conn.fetchrow("SELECT * FROM quizzes WHERE id = $1", quiz_id)
        if not quiz:
            raise HTTPException(status_code=404, detail="Quiz not found")
        await assert_member(conn, quiz["circle_id"], current_user["id"])
    return dict(quiz)

@router.get("/{circle_id}")
async def list_circle_quizzes(
    circle_id: str,
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await assert_member(conn, circle_id, current_user["id"])
        quizzes = await conn.fetch(
            "SELECT * FROM quizzes WHERE circle_id = $1 ORDER BY created_at DESC",
            circle_id,
        )
    return [dict(q) for q in quizzes]

AnswerValue = Union[str, dict[str, str]]


def _valid_answer_value(v: AnswerValue) -> bool:
    if isinstance(v, str):
        return len(v) <= 1000
    if isinstance(v, dict):
        return len(v) <= 50 and all(
            isinstance(k, str) and len(k) <= 500 and isinstance(val, str) and len(val) <= 500
            for k, val in v.items()
        )
    return False


@router.post("/{quiz_id}/submit")
async def submit_quiz(
    quiz_id: str,
    answers: dict[str, AnswerValue],  # raw body: mapping of question index to submitted answer
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        quiz = await conn.fetchrow("SELECT * FROM quizzes WHERE id = $1", quiz_id)
        if not quiz:
            raise HTTPException(status_code=404, detail="Quiz not found")
        await assert_member(conn, quiz["circle_id"], current_user["id"])
        questions = json.loads(quiz["questions"]) if isinstance(quiz["questions"], str) else quiz["questions"]

        if len(answers) > len(questions) or any(not _valid_answer_value(v) for v in answers.values()):
            raise HTTPException(status_code=400, detail="Invalid answers payload")

        score = sum(
            1 for i, q in enumerate(questions)
            if grade_question(q, answers.get(str(i)))
        )
        result = await conn.fetchrow(
            """
            INSERT INTO quiz_scores (quiz_id, user_id, score, answers)
            VALUES ($1, $2, $3, $4::jsonb) RETURNING *
            """,
            quiz_id, current_user["id"], score, answers,
        )
    return {"score": score, "total": len(questions), "result_id": str(result["id"])}
