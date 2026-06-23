import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.firebase import get_current_user
from app.db.database import get_pool
from app.services.quiz_generator import generate_quiz_questions

router = APIRouter()

class GenerateQuizRequest(BaseModel):
    circle_id: str
    title: str
    num_questions: int = 5
    topic: str = ""

@router.post("/generate")
async def generate_quiz(
    body: GenerateQuizRequest,
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        member = await conn.fetchrow(
            "SELECT * FROM circle_members WHERE circle_id = $1 AND user_id = $2",
            body.circle_id, current_user["id"],
        )
        if not member:
            raise HTTPException(status_code=403, detail="Not a member of this circle")

    questions = await generate_quiz_questions(
        circle_id=body.circle_id,
        topic=body.topic,
        num_questions=body.num_questions,
    )

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
    return dict(quiz)

@router.get("/{circle_id}")
async def list_circle_quizzes(
    circle_id: str,
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        member = await conn.fetchrow(
            "SELECT * FROM circle_members WHERE circle_id = $1 AND user_id = $2",
            circle_id, current_user["id"],
        )
        if not member:
            raise HTTPException(status_code=403, detail="Not a member of this circle")
        quizzes = await conn.fetch(
            "SELECT * FROM quizzes WHERE circle_id = $1 ORDER BY created_at DESC",
            circle_id,
        )
    return [dict(q) for q in quizzes]

@router.post("/{quiz_id}/submit")
async def submit_quiz(
    quiz_id: str,
    answers: dict,
    current_user: dict = Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        quiz = await conn.fetchrow("SELECT * FROM quizzes WHERE id = $1", quiz_id)
        if not quiz:
            raise HTTPException(status_code=404, detail="Quiz not found")
        questions = json.loads(quiz["questions"]) if isinstance(quiz["questions"], str) else quiz["questions"]
        score = sum(
            1 for i, q in enumerate(questions)
            if answers.get(str(i)) == q.get("correct_answer")
        )
        result = await conn.fetchrow(
            """
            INSERT INTO quiz_scores (quiz_id, user_id, score, answers)
            VALUES ($1, $2, $3, $4::jsonb) RETURNING *
            """,
            quiz_id, current_user["id"], score, answers,
        )
    return {"score": score, "total": len(questions), "result_id": str(result["id"])}
