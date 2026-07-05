"""Tests for the circle CRUD/membership endpoints in app/api/routes/circles.py.

The DB is faked (see conftest.py); auth is overridden via FastAPI's
dependency_overrides, matching the pattern in test_route_access.py.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.firebase import get_current_user
from app.api.routes import circles


def _client(monkeypatch, fake_pool, user_id="user-1") -> TestClient:
    async def _get_pool():
        return fake_pool
    monkeypatch.setattr(circles, "get_pool", _get_pool)

    app = FastAPI()
    app.include_router(circles.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: {"id": user_id}
    return TestClient(app)


# --- create circle -----------------------------------------------------------

def test_create_circle_assigns_current_user_as_owner(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool, user_id="user-1")
    fake_conn.queue_fetchrow({
        "id": "c1",
        "name": "Study Group",
        "description": "",
        "invite_code": "ABC123",
        "owner_id": "user-1",
    })

    res = client.post("/api/", json={"name": "Study Group"})

    assert res.status_code == 200
    assert res.json()["owner_id"] == "user-1"

    insert_sql, insert_args = fake_conn.calls[0]
    assert "INSERT INTO circles" in insert_sql
    assert insert_args[0] == "Study Group"
    assert insert_args[3] == "user-1"  # owner_id bound to the authenticated caller

    member_inserts = fake_conn.statements_matching("INSERT INTO circle_members")
    assert len(member_inserts) == 1
    assert member_inserts[0][1] == ("c1", "user-1")


# --- join circle ---------------------------------------------------------------

def test_join_circle_with_valid_code(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool, user_id="user-2")
    fake_conn.queue_fetchrow({
        "id": "c1", "name": "Study Group", "description": "",
        "invite_code": "ABC123", "owner_id": "user-1",
    })
    fake_conn.queue_fetchrow(None)  # not already a member

    res = client.post("/api/join", json={"invite_code": "ABC123"})

    assert res.status_code == 200
    assert res.json()["id"] == "c1"

    member_inserts = fake_conn.statements_matching("INSERT INTO circle_members")
    assert member_inserts[0][1] == ("c1", "user-2")


def test_join_circle_with_invalid_code_fails_cleanly(monkeypatch, fake_conn, fake_pool):
    # No expiry column exists on circles (schema only has invite_code), so an
    # "expired" code and an unrecognized one are indistinguishable at this
    # layer -- both simply fail the invite_code lookup.
    client = _client(monkeypatch, fake_pool)
    fake_conn.queue_fetchrow(None)  # no circle matches this code

    res = client.post("/api/join", json={"invite_code": "DOES-NOT-EXIST"})

    assert res.status_code == 404
    assert not fake_conn.ran("INSERT INTO circle_members")


# --- list circles --------------------------------------------------------------

def test_list_circles_only_returns_member_circles(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool, user_id="user-1")
    fake_conn.queue_fetch([
        {"id": "c1", "name": "A", "description": "", "invite_code": "X", "owner_id": "user-1"},
    ])

    res = client.get("/api/")

    assert res.status_code == 200
    assert [c["id"] for c in res.json()] == ["c1"]

    sql, args = fake_conn.calls[0]
    assert "circle_members" in sql
    assert args == ("user-1",)  # scoped to the calling user, not all circles


# --- get circle detail -----------------------------------------------------------

def test_get_circle_forbidden_for_non_member(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool, user_id="user-2")
    fake_conn.queue_fetchrow({
        "id": "c1", "name": "Study Group", "description": "",
        "invite_code": "ABC123", "owner_id": "user-1",
    })  # circle exists
    fake_conn.queue_fetchrow(None)  # but the caller isn't a member

    res = client.get("/api/c1")

    assert res.status_code == 403


def test_get_circle_404_for_nonexistent_circle(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool, user_id="user-2")
    fake_conn.queue_fetchrow(None)  # no circle with this id

    res = client.get("/api/does-not-exist")

    assert res.status_code == 404
    # Existence is checked before membership, so the membership query never runs.
    assert not fake_conn.ran("circle_members")
