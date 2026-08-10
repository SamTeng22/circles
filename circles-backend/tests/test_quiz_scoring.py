"""Tests for POST /{quiz_id}/submit in app/api/routes/quiz.py.

Covers score calculation and the resubmission/scoping behavior actually
implemented by submit_quiz (read from the handler, not assumed): there is no
re-submission guard or upsert -- every submit is a plain INSERT, so the same
user submitting twice produces two separate quiz_scores rows rather than an
overwrite.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.firebase import get_current_user
from app.api.routes import quiz


def _client(monkeypatch, fake_pool, user_id="user-1") -> TestClient:
    async def _get_pool():
        return fake_pool
    monkeypatch.setattr(quiz, "get_pool", _get_pool)

    app = FastAPI()
    app.include_router(quiz.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: {"id": user_id}
    return TestClient(app)


def _queue_submit(fake_conn, *, questions, member=True, result_id="score-1"):
    fake_conn.queue_fetchrow({"id": "q1", "circle_id": "cx", "questions": questions})
    fake_conn.queue_fetchrow({"?column?": 1} if member else None)
    fake_conn.queue_fetchrow({"id": result_id})


def test_submit_quiz_scores_mixed_answers(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    questions = [
        {"correct_answer": "A"},
        {"correct_answer": "B"},
        {"correct_answer": "C"},
    ]
    _queue_submit(fake_conn, questions=questions)

    res = client.post("/api/q1/submit", json={"0": "A", "1": "X", "2": "C"})

    assert res.status_code == 200
    body = res.json()
    assert body["score"] == 2  # question 0 and 2 correct, question 1 wrong
    assert body["total"] == 3


def test_submit_quiz_resubmission_inserts_a_new_row_each_time(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    questions = [{"correct_answer": "A"}]

    _queue_submit(fake_conn, questions=questions, result_id="score-1")
    first = client.post("/api/q1/submit", json={"0": "A"})
    assert first.json()["result_id"] == "score-1"

    _queue_submit(fake_conn, questions=questions, result_id="score-2")
    second = client.post("/api/q1/submit", json={"0": "X"})
    assert second.json()["result_id"] == "score-2"

    # No re-submission guard in submit_quiz: it always INSERTs, never
    # overwrites the prior row -- confirmed by reading the handler.
    inserts = fake_conn.statements_matching("INSERT INTO quiz_scores")
    assert len(inserts) == 2
    assert inserts[0][1][2] == 1  # first submission: correct
    assert inserts[1][1][2] == 0  # second submission: wrong


def test_submit_quiz_scopes_score_to_submitting_user(monkeypatch, fake_conn, fake_pool):
    questions = [{"correct_answer": "A"}]

    client1 = _client(monkeypatch, fake_pool, user_id="user-1")
    _queue_submit(fake_conn, questions=questions, result_id="score-1")
    client1.post("/api/q1/submit", json={"0": "A"})

    client2 = _client(monkeypatch, fake_pool, user_id="user-2")
    _queue_submit(fake_conn, questions=questions, result_id="score-2")
    client2.post("/api/q1/submit", json={"0": "A"})

    inserts = fake_conn.statements_matching("INSERT INTO quiz_scores")
    # user_id bound on each insert matches whichever caller made that
    # request -- no cross-user contamination.
    assert inserts[0][1][1] == "user-1"
    assert inserts[1][1][1] == "user-2"
