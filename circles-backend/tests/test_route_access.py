"""Access-control tests for the by-ID detail endpoints.

These endpoints fetch a row by id and must reject callers who aren't members
of the row's circle (otherwise any authenticated user could read another
circle's quiz/deck by id). The DB is faked; membership is scripted per test.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.firebase import get_current_user
from app.api.routes import quiz, flashcards


def _client(monkeypatch, module, fake_pool) -> TestClient:
    """Build an isolated app for one route module with auth + pool faked."""
    async def _get_pool():
        return fake_pool
    monkeypatch.setattr(module, "get_pool", _get_pool)

    app = FastAPI()
    app.include_router(module.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1"}
    return TestClient(app)


# --- quiz detail -----------------------------------------------------------

def test_quiz_detail_forbidden_for_non_member(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, quiz, fake_pool)
    # The quiz exists (in some circle) but the caller isn't a member.
    fake_conn.queue_fetchrow({"id": "q1", "circle_id": "cx", "title": "t", "questions": []})
    fake_conn.queue_fetchrow(None)

    assert client.get("/api/detail/q1").status_code == 403


def test_quiz_detail_ok_for_member(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, quiz, fake_pool)
    fake_conn.queue_fetchrow({"id": "q1", "circle_id": "cx", "title": "t", "questions": []})
    fake_conn.queue_fetchrow({"?column?": 1})  # membership row present

    res = client.get("/api/detail/q1")
    assert res.status_code == 200
    assert res.json()["id"] == "q1"


def test_quiz_detail_404_when_missing(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, quiz, fake_pool)
    fake_conn.queue_fetchrow(None)  # no quiz

    assert client.get("/api/detail/q1").status_code == 404


# --- flashcard deck detail -------------------------------------------------

def test_deck_detail_forbidden_for_non_member(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, flashcards, fake_pool)
    fake_conn.queue_fetchrow({"id": "d1", "circle_id": "cx", "title": "t", "cards": []})
    fake_conn.queue_fetchrow(None)

    assert client.get("/api/detail/d1").status_code == 403


def test_deck_detail_ok_for_member(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, flashcards, fake_pool)
    fake_conn.queue_fetchrow({"id": "d1", "circle_id": "cx", "title": "t", "cards": []})
    fake_conn.queue_fetchrow({"?column?": 1})

    res = client.get("/api/detail/d1")
    assert res.status_code == 200
    assert res.json()["id"] == "d1"
