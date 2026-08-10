"""Rate-limiting tests.

Hammer a rate-limited endpoint past its per-user limit and confirm the caller
gets a clean 429 (not a 500). Also confirms the limit is keyed per user: a
second user is unaffected by the first user's exhausted quota.

The DB pool and the LLM generator are faked so the test exercises only the
limiter, and the limit is turned down to a small number via settings so we don't
have to send hundreds of requests.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import config
from app.core.firebase import get_current_user
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.api.routes import quiz
from slowapi.errors import RateLimitExceeded


class _AlwaysConn:
    """A fake connection whose fetch* always returns a usable row.

    Enough for generate_quiz: the membership check sees a truthy row and the
    INSERT ... RETURNING sees a dict that `dict(quiz)` can consume.
    """

    _row = {"id": "q1", "circle_id": "c1", "title": "t", "questions": []}

    async def execute(self, *a):
        return "OK"

    async def fetchrow(self, *a):
        return dict(self._row)

    async def fetch(self, *a):
        return []


class _Acquire:
    async def __aenter__(self):
        return _AlwaysConn()

    async def __aexit__(self, *exc):
        return False


class _AlwaysPool:
    def acquire(self):
        return _Acquire()


def _client(monkeypatch, user_holder) -> TestClient:
    async def _get_pool():
        return _AlwaysPool()

    async def _fake_generate(**kwargs):
        return []

    monkeypatch.setattr(quiz, "get_pool", _get_pool)
    monkeypatch.setattr(quiz, "generate_quiz_questions", _fake_generate)

    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.include_router(quiz.router, prefix="/api")
    # identify_user depends on get_current_user, so overriding the latter feeds
    # the faked user through and still lets identify_user stamp request.state.
    app.dependency_overrides[get_current_user] = lambda: {"id": user_holder["id"]}
    return TestClient(app, raise_server_exceptions=True)


def _generate(client: TestClient):
    return client.post(
        "/api/generate",
        json={"circle_id": "c1", "title": "t", "num_questions": 1},
    )


def test_generate_quiz_rate_limited_per_user(monkeypatch):
    # Turn the limit right down so a handful of requests trips it.
    monkeypatch.setattr(config.settings, "QUIZ_GENERATION_RATE_LIMIT", "3/hour")
    limiter.reset()  # clear counters from any earlier test in this process

    user_holder = {"id": "rl-user-1"}
    client = _client(monkeypatch, user_holder)

    # First 3 requests are within the limit.
    for _ in range(3):
        assert _generate(client).status_code == 200

    # The 4th trips the limit -> a clean 429, not a generic 500.
    blocked = _generate(client)
    assert blocked.status_code == 429
    assert "Rate limit exceeded" in blocked.json()["detail"]

    # A different user is unaffected -> the limit is keyed per user, not global/IP.
    user_holder["id"] = "rl-user-2"
    assert _generate(client).status_code == 200
