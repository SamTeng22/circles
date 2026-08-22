"""Access-control and shape tests for GET /api/conflicts/{circle_id}."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.firebase import get_current_user
from app.api.routes import conflicts


def _client(monkeypatch, fake_pool) -> TestClient:
    async def _get_pool():
        return fake_pool
    monkeypatch.setattr(conflicts, "get_pool", _get_pool)

    app = FastAPI()
    app.include_router(conflicts.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1"}
    return TestClient(app)


def test_list_conflicts_forbidden_for_non_member(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    fake_conn.queue_fetchrow(None)  # membership check fails

    res = client.get("/api/circle-1")

    assert res.status_code == 403
    assert not fake_conn.ran("FROM conflicts")


def test_list_conflicts_ok_for_member(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    fake_conn.queue_fetchrow({"?column?": 1})  # membership row present
    fake_conn.queue_fetch([
        {
            "id": "c1",
            "circle_id": "circle-1",
            "chunk_a_id": "chunk-a",
            "chunk_b_id": "chunk-b",
            "note_a_id": "note-a",
            "note_b_id": "note-b",
            "user_a_id": "user-a",
            "user_b_id": "user-b",
            "explanation": "These notes disagree on the deadline.",
            "resolved": False,
            "created_at": "2026-08-01T00:00:00Z",
            "note_a_filename": "lecture1.pdf",
            "note_b_filename": "lecture2.pdf",
            "user_a_name": "Alice",
            "user_b_name": "Bob",
        }
    ])

    res = client.get("/api/circle-1")

    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert body[0]["id"] == "c1"
    assert body[0]["note_a_filename"] == "lecture1.pdf"
    assert body[0]["user_b_name"] == "Bob"


def test_list_conflicts_empty_circle_returns_empty_list(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    fake_conn.queue_fetchrow({"?column?": 1})  # membership row present
    fake_conn.queue_fetch([])  # no conflicts

    res = client.get("/api/circle-1")

    assert res.status_code == 200
    assert res.json() == []
