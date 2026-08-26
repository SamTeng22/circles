"""Tests for the live-quiz WebSocket route in app/api/routes/live.py.

The route now verifies a Firebase-token-verified identity and fetches the
quiz (for membership checks + the answer key) from the DB, so both
`live.resolve_user_from_token` and `live.get_pool` are faked here -- the same
pattern used by the other route tests (see test_circles_routes.py): a fake
DB via conftest.py's `fake_pool`/`fake_conn`, and identity stubbed directly
(there's no `Authorization` header on a WebSocket handshake, so this route
doesn't use FastAPI's `Depends(get_current_user)` -- instead it reads a
`?token=` query param and resolves it itself).

Room state is still a module-global in-memory dict keyed by quiz_id, so each
test uses its own unique quiz_id to avoid bleeding into other tests.
"""
import asyncio
import uuid

import pytest
from fastapi import FastAPI, HTTPException, WebSocketDisconnect
from fastapi.testclient import TestClient

from app.api.routes import live

_REAL_SLEEP = asyncio.sleep


def _patch_instant_rest_sleep(monkeypatch):
    """Accelerate only the 15s rest-phase auto-advance sleep. Stage 2 added a
    second `asyncio.sleep`-based timer (the per-question countdown) that
    shares the same `asyncio.sleep` -- other delays fall through to the real
    sleep so that timer doesn't fire early and race with tests that aren't
    exercising it (it just sits harmlessly in the background, never firing
    within a test's short lifetime).
    """
    async def _sleep(seconds):
        if seconds == 15:
            return None
        await _REAL_SLEEP(seconds)
    monkeypatch.setattr(live.asyncio, "sleep", _sleep)


class _FakeClock:
    """A controllable stand-in for time.monotonic() so answer-speed scoring
    and the sync_state time-remaining fields can be tested deterministically
    instead of racing real wall-clock time.
    """
    def __init__(self, start: float = 1000.0):
        self.now = start

    def tick(self, seconds: float):
        self.now += seconds

    def monotonic(self) -> float:
        return self.now


def _freeze_time(monkeypatch, start: float = 1000.0) -> _FakeClock:
    clock = _FakeClock(start)
    monkeypatch.setattr(live.time, "monotonic", clock.monotonic)
    return clock

EN_QUESTIONS = [
    {"question": "2+2?", "options": ["3", "4"], "correct_answer": "4", "language": "en"},
    {"question": "3+3?", "options": ["5", "6"], "correct_answer": "6", "language": "en"},
]
TL_QUESTIONS = [
    {"question": "Ilang araw sa isang linggo?", "options": ["6", "7"], "correct_answer": "7", "language": "tl"},
    {"question": "Kabisera ng Pilipinas?", "options": ["Cebu", "Manila"], "correct_answer": "Manila", "language": "tl"},
]
DEFAULT_QUESTIONS = EN_QUESTIONS + TL_QUESTIONS


def _client(monkeypatch, fake_pool) -> TestClient:
    async def _get_pool():
        return fake_pool
    monkeypatch.setattr(live, "get_pool", _get_pool)

    async def _resolve_user_from_token(token: str) -> dict:
        if token == "bad-token":
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return {"id": token.removeprefix("token-")}
    monkeypatch.setattr(live, "resolve_user_from_token", _resolve_user_from_token)

    app = FastAPI()
    app.include_router(live.router, prefix="/api/live")
    return TestClient(app)


def _quiz_id() -> str:
    return f"live-quiz-{uuid.uuid4()}"


def _queue_auth(fake_conn, questions=None, circle_id="circle-1", member=True):
    """Queue the two DB reads `_authorize` makes for one connection attempt:
    the quiz lookup, then (only if the quiz was found) the membership check.
    """
    fake_conn.queue_fetchrow({"circle_id": circle_id, "questions": questions if questions is not None else DEFAULT_QUESTIONS})
    fake_conn.queue_fetchrow(1 if member else None)


def _ws(client, fake_conn, quiz_id, user_id, questions=None):
    _queue_auth(fake_conn, questions=questions)
    return client.websocket_connect(f"/api/live/ws/{quiz_id}?token=token-{user_id}")


def _join(ws):
    """Every connection gets a private 'connected' then 'sync_state' message
    before any user_joined broadcast -- drain both here."""
    ws.receive_json()  # connected
    ws.receive_json()  # sync_state


# --- single user / lobby ----------------------------------------------------

def test_single_user_joins_lobby_and_receives_initial_state(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()

    with _ws(client, fake_conn, quiz_id, "user-1") as ws:
        connected = ws.receive_json()
        assert connected == {"type": "connected", "user_id": "user-1"}

        sync = ws.receive_json()
        assert sync["type"] == "sync_state"
        assert sync["phase"] == "lobby"

        msg = ws.receive_json()
        assert msg["type"] == "user_joined"
        assert msg["phase"] == "lobby"
        assert msg["host_id"] == "user-1"  # first joiner becomes host
        assert msg["participants"] == [{"user_id": "user-1", "display_name": ""}]
        assert msg["scores"] == {"user-1": 0}


def test_new_connection_supersedes_stale_one_for_same_identity(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()

    with _ws(client, fake_conn, quiz_id, "user-1") as first:
        _join(first)
        first.receive_json()  # own join

        with _ws(client, fake_conn, quiz_id, "user-1") as second:
            second.receive_json()  # connected
            second.receive_json()  # sync_state

            # The old connection for the same identity gets closed server-side
            # rather than being left as a zombie that can still send commands
            # but never receives broadcasts.
            with pytest.raises(WebSocketDisconnect):
                first.receive_json()


def test_second_user_joining_is_seen_by_both_and_is_not_host(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()

    with _ws(client, fake_conn, quiz_id, "user-1") as host:
        _join(host)
        host.receive_json()  # user-1's own join

        with _ws(client, fake_conn, quiz_id, "user-2") as guest:
            _join(guest)
            join_seen_by_host = host.receive_json()
            join_seen_by_guest = guest.receive_json()

            for msg in (join_seen_by_host, join_seen_by_guest):
                assert msg["type"] == "user_joined"
                assert msg["host_id"] == "user-1"  # host unchanged by a second joiner
                assert {p["user_id"] for p in msg["participants"]} == {"user-1", "user-2"}


# --- rejected connections -----------------------------------------------------

def test_connection_rejected_with_no_token(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/api/live/ws/{quiz_id}") as ws:
            ws.receive_json()
    assert exc_info.value.code == 4401


def test_connection_rejected_with_invalid_token(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/api/live/ws/{quiz_id}?token=bad-token") as ws:
            ws.receive_json()
    assert exc_info.value.code == 4401


def test_connection_rejected_when_quiz_not_found(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()
    # No fetchrow queued -> the quiz lookup returns None.

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/api/live/ws/{quiz_id}?token=token-user-1") as ws:
            ws.receive_json()
    assert exc_info.value.code == 4404


def test_connection_rejected_for_non_circle_member(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()
    _queue_auth(fake_conn, member=False)

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/api/live/ws/{quiz_id}?token=token-user-1") as ws:
            ws.receive_json()
    assert exc_info.value.code == 4403


def test_connection_rejected_for_quiz_with_fill_in_blank_question(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()
    questions = EN_QUESTIONS + [
        {"question_type": "fill_in_blank", "question": "The _____ is red.", "accepted_answers": ["sky"], "language": "en"}
    ]
    _queue_auth(fake_conn, questions=questions)

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/api/live/ws/{quiz_id}?token=token-user-1") as ws:
            ws.receive_json()
    assert exc_info.value.code == 4422


def test_connection_rejected_for_quiz_with_matching_question(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()
    questions = EN_QUESTIONS + [
        {
            "question_type": "matching",
            "question": "Match them.",
            "pairs": [{"left": "A", "right": "1"}],
            "language": "en",
        }
    ]
    _queue_auth(fake_conn, questions=questions)

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/api/live/ws/{quiz_id}?token=token-user-1") as ws:
            ws.receive_json()
    assert exc_info.value.code == 4422


def test_mixed_multiple_choice_and_true_false_quiz_connects_and_plays(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()
    questions = [
        {"question_type": "multiple_choice", "question": "2+2?", "options": ["3", "4"], "correct_answer": "4", "language": "en"},
        {"question_type": "true_false", "question": "Sky is blue.", "options": ["True", "False"], "correct_answer": "True", "language": "en"},
    ]

    with _ws(client, fake_conn, quiz_id, "user-1", questions=questions) as host:
        _join(host)
        host.receive_json()  # own join

        host.send_json({"type": "start_quiz"})
        host.receive_json()  # question_start

        host.send_json({"type": "answer", "question_index": 1, "answer": "True"})
        answer_msg = host.receive_json()
        assert answer_msg["correct"] is True


# --- answering / server-computed correctness --------------------------------

def test_answer_updates_score_reflected_in_leaderboard(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()
    _freeze_time(monkeypatch)  # elapsed=0 -> a correct first answer scores exactly 1000

    with _ws(client, fake_conn, quiz_id, "user-1") as host, _ws(client, fake_conn, quiz_id, "user-2") as guest:
        _join(host)
        _join(guest)
        host.receive_json()   # host's own join
        host.receive_json()   # guest's join, seen by host
        guest.receive_json()  # guest's own join (same broadcast)

        host.send_json({"type": "start_quiz"})
        host.receive_json()   # question_start
        guest.receive_json()

        # The server now looks up the answer key itself instead of trusting
        # a client-supplied "correct" flag.
        guest.send_json({
            "type": "answer",
            "question_index": 0,
            "answer": "4",
        })
        host.receive_json()   # answer_received
        answer_msg = guest.receive_json()
        assert answer_msg["correct"] is True
        assert answer_msg["points"] == 1000
        assert answer_msg["streak"] == 1

        host.send_json({"type": "question_end"})
        rest_for_host = host.receive_json()
        rest_for_guest = guest.receive_json()

        for msg in (rest_for_host, rest_for_guest):
            assert msg["type"] == "rest_phase"
            leaderboard = {e["user_id"]: e["score"] for e in msg["leaderboard"]}
            assert leaderboard == {"user-1": 0, "user-2": 1000}


def test_server_ignores_client_claimed_correct_flag(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()

    with _ws(client, fake_conn, quiz_id, "user-1") as host:
        _join(host)
        host.receive_json()  # own join

        host.send_json({"type": "start_quiz"})
        host.receive_json()  # question_start

        # "3" is wrong for "2+2?" -- claiming correct=True should be ignored.
        host.send_json({
            "type": "answer",
            "question_index": 0,
            "answer": "3",
            "correct": True,
        })
        answer_msg = host.receive_json()
        assert answer_msg["correct"] is False


def test_duplicate_answer_for_same_question_is_ignored(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()
    _freeze_time(monkeypatch)

    with _ws(client, fake_conn, quiz_id, "user-1") as host, _ws(client, fake_conn, quiz_id, "user-2") as guest:
        _join(host)
        _join(guest)
        host.receive_json()
        host.receive_json()
        guest.receive_json()

        host.send_json({"type": "start_quiz"})
        host.receive_json()  # question_start
        guest.receive_json()

        host.send_json({"type": "answer", "question_index": 0, "answer": "4"})
        first = host.receive_json()
        guest.receive_json()
        assert first["points"] == 1000

        # A second "answer" for the same question from the same user (e.g.
        # from a mid-question reconnect) should be silently ignored -- no
        # broadcast, no double-scoring.
        host.send_json({"type": "answer", "question_index": 0, "answer": "4"})
        guest.send_json({"type": "answer", "question_index": 0, "answer": "6"})
        next_for_host = host.receive_json()
        # If the duplicate had been processed, this would be a second
        # broadcast for user-1 instead of guest's answer.
        assert next_for_host["user_id"] == "user-2"


# --- auto-advance after the rest-phase timer --------------------------------

def test_phase_auto_advances_after_question_end_delay(monkeypatch, fake_conn, fake_pool):
    # The rest-phase auto-advance delay is a hardcoded `asyncio.sleep(15)`
    # inside _end_question (live.py), not a configurable parameter. Rather
    # than waiting 15 real seconds, patch asyncio.sleep to resolve
    # near-instantly so the test exercises the same code path (schedule a
    # delayed task -> it fires -> _advance_question runs) without the wait.
    _patch_instant_rest_sleep(monkeypatch)

    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()

    with _ws(client, fake_conn, quiz_id, "user-1") as host, _ws(client, fake_conn, quiz_id, "user-2") as guest:
        _join(host)
        _join(guest)
        host.receive_json()
        host.receive_json()
        guest.receive_json()

        host.send_json({"type": "start_quiz"})
        host.receive_json()   # question_start (index 0)
        guest.receive_json()

        host.send_json({"type": "question_end"})
        host.receive_json()   # rest_phase
        guest.receive_json()

        # Nobody marks ready and nobody sends force_next -- the only way
        # forward from here is the auto-advance task scheduled by question_end.
        advanced_for_host = host.receive_json()
        advanced_for_guest = guest.receive_json()

        for msg in (advanced_for_host, advanced_for_guest):
            assert msg["type"] == "question_start"
            assert msg["phase"] == "question"
            assert msg["question_index"] == 1


# --- disconnect mid-game -----------------------------------------------------

def test_disconnect_mid_game_reflected_without_crashing_other_clients(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()

    with _ws(client, fake_conn, quiz_id, "user-1") as host:
        _join(host)
        host.receive_json()  # host's own join

        with _ws(client, fake_conn, quiz_id, "user-2") as guest:
            _join(guest)
            host.receive_json()   # guest joined
            guest.receive_json()

            host.send_json({"type": "start_quiz"})
            host.receive_json()
            guest.receive_json()
        # guest's `with` block exits here -> socket closes -> server sees a
        # disconnect while the quiz is mid-question.

        left_msg = host.receive_json()
        assert left_msg["type"] == "user_left"
        assert left_msg["user_id"] == "user-2"
        assert {p["user_id"] for p in left_msg["participants"]} == {"user-1"}
        assert left_msg["host_id"] == "user-1"  # host survives the other player leaving

        # The remaining connection must still be fully functional afterward.
        host.send_json({
            "type": "answer",
            "question_index": 0,
            "answer": "4",
        })
        answer_msg = host.receive_json()
        assert answer_msg["type"] == "answer_received"
        assert answer_msg["user_id"] == "user-1"
        assert answer_msg["correct"] is True


def test_host_disconnect_promotes_next_connected_user(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()

    # Opened/closed manually (not via `with`) so the host can be disconnected
    # at a precise point while the guest connection stays open to observe it.
    host_cm = _ws(client, fake_conn, quiz_id, "user-1")
    host = host_cm.__enter__()
    _join(host)
    host.receive_json()  # own join

    with _ws(client, fake_conn, quiz_id, "user-2") as guest:
        _join(guest)
        host.receive_json()   # guest's join, seen by host
        guest.receive_json()  # guest's own join

        host_cm.__exit__(None, None, None)  # host disconnects

        left_msg = guest.receive_json()
        assert left_msg["type"] == "user_left"
        assert left_msg["user_id"] == "user-1"
        assert left_msg["host_id"] == "user-2"  # promoted

        # The newly-promoted host can drive the game.
        guest.send_json({"type": "start_quiz"})
        started = guest.receive_json()
        assert started["type"] == "question_start"


# --- host controls: kick + force-end -----------------------------------------

def test_kick_player_removes_target_and_notifies_others(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()

    with _ws(client, fake_conn, quiz_id, "user-1") as host, _ws(client, fake_conn, quiz_id, "user-2") as guest:
        _join(host)
        _join(guest)
        host.receive_json()   # host's own join
        host.receive_json()   # guest's join
        guest.receive_json()  # same broadcast

        host.send_json({"type": "kick_player", "user_id": "user-2"})

        kicked_msg = guest.receive_json()
        assert kicked_msg == {"type": "kicked"}

        with pytest.raises(WebSocketDisconnect):
            guest.receive_json()  # the connection close that follows

        left_msg = host.receive_json()
        assert left_msg["type"] == "user_left"
        assert left_msg["user_id"] == "user-2"


def test_kick_player_ignored_for_non_host(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()

    with _ws(client, fake_conn, quiz_id, "user-1") as host, _ws(client, fake_conn, quiz_id, "user-2") as guest:
        _join(host)
        _join(guest)
        host.receive_json()
        host.receive_json()
        guest.receive_json()

        guest.send_json({"type": "kick_player", "user_id": "user-1"})  # guest isn't host

        # Prove the host's connection is untouched: it can still act normally.
        host.send_json({"type": "set_name", "name": "Still Here"})
        confirm = host.receive_json()
        assert confirm["type"] == "name_updated"


def test_end_quiz_broadcasts_quiz_finished_mid_question(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()

    with _ws(client, fake_conn, quiz_id, "user-1") as host, _ws(client, fake_conn, quiz_id, "user-2") as guest:
        _join(host)
        _join(guest)
        host.receive_json()
        host.receive_json()
        guest.receive_json()

        host.send_json({"type": "start_quiz"})
        host.receive_json()  # question_start
        guest.receive_json()

        host.send_json({"type": "end_quiz"})
        finished_for_host = host.receive_json()
        finished_for_guest = guest.receive_json()

        assert finished_for_host["type"] == "quiz_finished"
        assert finished_for_guest["type"] == "quiz_finished"


def test_end_quiz_ignored_for_non_host(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()

    with _ws(client, fake_conn, quiz_id, "user-1") as host, _ws(client, fake_conn, quiz_id, "user-2") as guest:
        _join(host)
        _join(guest)
        host.receive_json()
        host.receive_json()
        guest.receive_json()

        host.send_json({"type": "start_quiz"})
        host.receive_json()  # question_start
        guest.receive_json()

        guest.send_json({"type": "end_quiz"})  # guest isn't host

        # Prove the quiz is still running by successfully answering.
        host.send_json({"type": "answer", "question_index": 0, "answer": "4"})
        answer_msg = host.receive_json()
        assert answer_msg["type"] == "answer_received"


# --- late joiners catch up via sync_state ------------------------------------

def test_late_joiner_receives_sync_state_mid_question(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()
    _freeze_time(monkeypatch)

    with _ws(client, fake_conn, quiz_id, "user-1") as host:
        _join(host)
        host.receive_json()  # own join

        host.send_json({"type": "start_quiz", "time_limit": 20})
        host.receive_json()  # question_start

        with _ws(client, fake_conn, quiz_id, "user-2") as guest:
            connected = guest.receive_json()
            assert connected["type"] == "connected"

            sync = guest.receive_json()
            assert sync["type"] == "sync_state"
            assert sync["phase"] == "question"
            assert sync["question_index"] == 0
            assert sync["time_limit"] == 20
            assert sync["time_remaining"] == 20  # frozen clock -> no time has passed


def test_late_joiner_receives_sync_state_mid_rest(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()
    _freeze_time(monkeypatch)

    with _ws(client, fake_conn, quiz_id, "user-1") as host:
        _join(host)
        host.receive_json()  # own join

        host.send_json({"type": "start_quiz"})
        host.receive_json()  # question_start

        host.send_json({"type": "question_end"})
        host.receive_json()  # rest_phase

        with _ws(client, fake_conn, quiz_id, "user-2") as guest:
            guest.receive_json()  # connected

            sync = guest.receive_json()
            assert sync["type"] == "sync_state"
            assert sync["phase"] == "rest"
            assert sync["rest_time_remaining"] == 15  # frozen clock


# --- multilingual quizzes: host-picked session language ---------------------

def test_start_quiz_broadcasts_host_picked_language(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()

    with _ws(client, fake_conn, quiz_id, "user-1") as host, _ws(client, fake_conn, quiz_id, "user-2") as guest:
        _join(host)
        _join(guest)
        host.receive_json()
        host.receive_json()
        guest.receive_json()

        host.send_json({"type": "start_quiz", "language": "tl"})
        question_for_host = host.receive_json()
        question_for_guest = guest.receive_json()

        for msg in (question_for_host, question_for_guest):
            assert msg["type"] == "question_start"
            assert msg["language"] == "tl"


def test_start_quiz_defaults_language_to_en_when_omitted(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()

    with _ws(client, fake_conn, quiz_id, "user-1") as host:
        _join(host)
        host.receive_json()  # own join

        host.send_json({"type": "start_quiz"})
        msg = host.receive_json()

        assert msg["language"] == "en"


def test_late_joiner_learns_room_language_from_user_joined(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()

    with _ws(client, fake_conn, quiz_id, "user-1") as host:
        _join(host)
        host.receive_json()  # own join

        host.send_json({"type": "start_quiz", "language": "zh"})
        host.receive_json()  # question_start

        with _ws(client, fake_conn, quiz_id, "user-2") as guest:
            _join(guest)
            join_seen_by_guest = guest.receive_json()
            host.receive_json()  # same broadcast, seen by host too

            assert join_seen_by_guest["type"] == "user_joined"
            assert join_seen_by_guest["language"] == "zh"


def test_advance_question_carries_the_locked_in_language(monkeypatch, fake_conn, fake_pool):
    _patch_instant_rest_sleep(monkeypatch)

    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()

    with _ws(client, fake_conn, quiz_id, "user-1") as host:
        _join(host)
        host.receive_json()  # own join

        host.send_json({"type": "start_quiz", "language": "tl"})
        host.receive_json()  # question_start index 0

        host.send_json({"type": "question_end"})
        host.receive_json()  # rest_phase

        advanced = host.receive_json()  # auto-advance
        assert advanced["type"] == "question_start"
        assert advanced["language"] == "tl"


# --- explicit finished phase --------------------------------------------------

def test_quiz_finished_emitted_after_last_question_with_correct_scores(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()
    _freeze_time(monkeypatch)  # elapsed=0 -> every correct first-of-streak answer scores 1000

    with _ws(client, fake_conn, quiz_id, "user-1") as host, _ws(client, fake_conn, quiz_id, "user-2") as guest:
        _join(host)
        _join(guest)
        host.receive_json()
        host.receive_json()
        guest.receive_json()

        host.send_json({"type": "start_quiz"})  # "en" -> 2 questions total
        host.receive_json()   # question_start index 0
        guest.receive_json()

        # Round 1: user-1 correct ("4"), user-2 wrong ("3"). Both answering
        # triggers the auto early-end -- no manual question_end needed.
        host.send_json({"type": "answer", "question_index": 0, "answer": "4"})
        host.receive_json()   # answer_received (host's)
        guest.receive_json()
        guest.send_json({"type": "answer", "question_index": 0, "answer": "3"})
        host.receive_json()   # answer_received (guest's)
        host.receive_json()   # rest_phase (auto early-end)
        guest.receive_json()  # answer_received (own)
        guest.receive_json()  # rest_phase

        host.send_json({"type": "force_next"})
        host.receive_json()   # question_start index 1
        guest.receive_json()

        # Round 2: user-2 answers correctly ("6"), user-1 doesn't answer.
        guest.send_json({"type": "answer", "question_index": 1, "answer": "6"})
        host.receive_json()
        guest.receive_json()

        host.send_json({"type": "question_end"})
        host.receive_json()   # rest_phase
        guest.receive_json()

        host.send_json({"type": "force_next"})
        final_for_host = host.receive_json()  # past the last question
        final_for_guest = guest.receive_json()

        for msg in (final_for_host, final_for_guest):
            assert msg["type"] == "quiz_finished"
            leaderboard = {e["user_id"]: e["score"] for e in msg["leaderboard"]}
            # user-1's one correct answer (streak 1) and user-2's one correct
            # answer (streak reset to 1 after their earlier wrong answer)
            # both score the same first-of-streak 1000 with elapsed frozen at 0.
            assert leaderboard == {"user-1": 1000, "user-2": 1000}


# --- speed-based scoring + streaks -------------------------------------------

def test_faster_answer_scores_more_than_a_slower_one(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()
    clock = _freeze_time(monkeypatch)

    with _ws(client, fake_conn, quiz_id, "user-1") as host, _ws(client, fake_conn, quiz_id, "user-2") as guest:
        _join(host)
        _join(guest)
        host.receive_json()
        host.receive_json()
        guest.receive_json()

        host.send_json({"type": "start_quiz", "time_limit": 20})
        host.receive_json()   # question_start
        guest.receive_json()

        # user-1 answers instantly (elapsed 0/20).
        host.send_json({"type": "answer", "question_index": 0, "answer": "4"})
        fast_answer = host.receive_json()
        guest.receive_json()
        assert fast_answer["points"] == 1000  # 500 base + full 500 speed bonus

        # 18 of the 20 seconds pass before user-2 answers -- also correct, so
        # the only difference from user-1's answer is how much time was left.
        clock.tick(18)
        guest.send_json({"type": "answer", "question_index": 0, "answer": "4"})
        host.receive_json()
        slow_answer = guest.receive_json()
        assert slow_answer["points"] == 550  # 500 base + 10% of the 500 speed bonus

        assert fast_answer["points"] > slow_answer["points"]


def test_streak_bonus_on_second_consecutive_correct_answer(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()
    _freeze_time(monkeypatch)
    _patch_instant_rest_sleep(monkeypatch)

    with _ws(client, fake_conn, quiz_id, "user-1") as host:
        _join(host)
        host.receive_json()

        host.send_json({"type": "start_quiz"})
        host.receive_json()   # question_start index 0

        # A solo room means "everyone's answered" is true the instant the
        # only player answers -- that auto-ends the question, and with the
        # rest-phase sleep accelerated, auto-advances straight to question 1
        # without any manual question_end/force_next.
        host.send_json({"type": "answer", "question_index": 0, "answer": "4"})
        first = host.receive_json()   # answer_received
        assert first["streak"] == 1
        assert first["points"] == 1000  # no streak bonus yet
        host.receive_json()   # rest_phase (auto early-end)
        host.receive_json()   # question_start index 1 (auto-advance)

        host.send_json({"type": "answer", "question_index": 1, "answer": "6"})
        second = host.receive_json()
        assert second["streak"] == 2
        assert second["points"] == 1050  # 1000 base + 50 streak bonus


def test_wrong_answer_resets_streak_to_zero(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()
    _freeze_time(monkeypatch)
    _patch_instant_rest_sleep(monkeypatch)

    with _ws(client, fake_conn, quiz_id, "user-1") as host:
        _join(host)
        host.receive_json()

        host.send_json({"type": "start_quiz"})
        host.receive_json()   # question_start index 0

        host.send_json({"type": "answer", "question_index": 0, "answer": "4"})
        correct = host.receive_json()   # answer_received
        assert correct["streak"] == 1
        host.receive_json()   # rest_phase (solo room -> auto early-end)
        host.receive_json()   # question_start index 1 (auto-advance)

        # Wrong answer on question 1 (correct_answer is "6") -- streak resets.
        host.send_json({"type": "answer", "question_index": 1, "answer": "5"})
        wrong = host.receive_json()   # answer_received
        assert wrong["correct"] is False
        assert wrong["streak"] == 0
        assert wrong["points"] == 0


# --- timer-driven auto-advance -----------------------------------------------

def test_question_auto_ends_when_time_limit_expires(monkeypatch, fake_conn, fake_pool):
    async def _instant_sleep(seconds):
        return None
    monkeypatch.setattr(live.asyncio, "sleep", _instant_sleep)

    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()

    with _ws(client, fake_conn, quiz_id, "user-1") as host:
        _join(host)
        host.receive_json()

        host.send_json({"type": "start_quiz", "time_limit": 10})
        host.receive_json()   # question_start

        # Nobody answers and nobody ends the question manually -- the only
        # way a rest_phase shows up is the per-question timer firing.
        rest = host.receive_json()
        assert rest["type"] == "rest_phase"


def test_question_ends_early_once_everyone_has_answered(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()

    with _ws(client, fake_conn, quiz_id, "user-1") as host, _ws(client, fake_conn, quiz_id, "user-2") as guest:
        _join(host)
        _join(guest)
        host.receive_json()
        host.receive_json()
        guest.receive_json()

        host.send_json({"type": "start_quiz"})  # default 20s time_limit, not accelerated
        host.receive_json()   # question_start
        guest.receive_json()

        host.send_json({"type": "answer", "question_index": 0, "answer": "4"})
        host.receive_json()   # answer_received (host's)
        guest.receive_json()

        # Everyone's answered before either the (real, unaccelerated) timer
        # or a manual question_end -- this should trigger _end_question itself.
        guest.send_json({"type": "answer", "question_index": 0, "answer": "6"})
        answer_for_host = host.receive_json()   # answer_received (guest's)
        rest_for_host = host.receive_json()     # rest_phase (early end)
        answer_for_guest = guest.receive_json()  # answer_received (own)
        rest_for_guest = guest.receive_json()    # rest_phase

        assert answer_for_host["type"] == "answer_received"
        assert answer_for_guest["type"] == "answer_received"
        assert rest_for_host["type"] == "rest_phase"
        assert rest_for_guest["type"] == "rest_phase"


# --- persisting results to quiz_scores ---------------------------------------

def test_quiz_finish_persists_one_row_per_participant(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()
    _freeze_time(monkeypatch)  # elapsed=0 -> a correct first answer scores exactly 1000

    with _ws(client, fake_conn, quiz_id, "user-1") as host, _ws(client, fake_conn, quiz_id, "user-2") as guest:
        _join(host)
        _join(guest)
        host.receive_json()
        host.receive_json()
        guest.receive_json()

        host.send_json({"type": "start_quiz"})  # "en" -> 2 questions total
        host.receive_json()   # question_start index 0
        guest.receive_json()

        host.send_json({"type": "answer", "question_index": 0, "answer": "4"})
        host.receive_json()
        guest.receive_json()
        guest.send_json({"type": "answer", "question_index": 0, "answer": "3"})
        host.receive_json()
        host.receive_json()   # rest_phase (auto early-end)
        guest.receive_json()
        guest.receive_json()

        host.send_json({"type": "force_next"})
        host.receive_json()   # question_start index 1
        guest.receive_json()

        host.send_json({"type": "end_quiz"})  # force straight to results
        host.receive_json()   # quiz_finished
        guest.receive_json()

    inserts = fake_conn.statements_matching("INSERT INTO quiz_scores")
    assert len(inserts) == 2
    by_user = {args[1]: args for _, args in inserts}

    assert by_user["user-1"][0] == quiz_id
    assert by_user["user-1"][2] == 1000  # one fast correct answer
    assert by_user["user-1"][3] == {"0": "4"}

    assert by_user["user-2"][2] == 0  # answered wrong on question 0, never answered question 1
    assert by_user["user-2"][3] == {"0": "3"}


def test_end_quiz_from_lobby_does_not_persist(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()

    with _ws(client, fake_conn, quiz_id, "user-1") as host:
        _join(host)
        host.receive_json()  # own join

        # Never sent start_quiz -- total_questions is still 0.
        host.send_json({"type": "end_quiz"})
        finished = host.receive_json()
        assert finished["type"] == "quiz_finished"

    assert fake_conn.statements_matching("INSERT INTO quiz_scores") == []


async def test_finish_quiz_does_not_persist_twice(monkeypatch, fake_conn, fake_pool):
    _client(monkeypatch, fake_pool)  # wires live.get_pool -> fake_pool
    quiz_id = _quiz_id()

    room = live.RoomState()
    room.total_questions = 1
    room.scores = {"user-1": 500}

    await live._finish_quiz(quiz_id, room)
    await live._finish_quiz(quiz_id, room)  # already finished -- must be a no-op

    assert len(fake_conn.statements_matching("INSERT INTO quiz_scores")) == 1


def test_abandoned_game_still_persists_results(monkeypatch, fake_conn, fake_pool):
    # If a game is abandoned mid-play (nobody ever sends end_quiz and it
    # never reaches the last question), results must still be saved when
    # the last connection drops -- not silently discarded.
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()
    _freeze_time(monkeypatch)

    with _ws(client, fake_conn, quiz_id, "user-1") as host:
        _join(host)
        host.receive_json()  # own join

        host.send_json({"type": "start_quiz"})
        host.receive_json()  # question_start

        host.send_json({"type": "answer", "question_index": 0, "answer": "4"})
        host.receive_json()  # answer_received
        host.receive_json()  # rest_phase (solo room -> auto early-end)
    # host's `with` block exits here -> last connection drops -> room torn
    # down, even though the quiz never reached "finished".

    inserts = fake_conn.statements_matching("INSERT INTO quiz_scores")
    assert len(inserts) == 1
    _, args = inserts[0]
    assert args[1] == "user-1"
    assert args[2] == 1000
    assert args[3] == {"0": "4"}


# --- phase guards on host actions ---------------------------------------------

def test_force_next_ignored_outside_rest_phase(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()

    with _ws(client, fake_conn, quiz_id, "user-1") as host:
        _join(host)
        host.receive_json()

        host.send_json({"type": "start_quiz"})
        host.receive_json()  # question_start index 0

        host.send_json({"type": "force_next"})  # wrong phase -- ignored

        # Prove nothing advanced: question_index 0 is still answerable and
        # the very next message is its answer_received, not a stray
        # question_start from a wrongly-processed force_next.
        host.send_json({"type": "answer", "question_index": 0, "answer": "4"})
        answer_msg = host.receive_json()
        assert answer_msg["type"] == "answer_received"
        assert answer_msg["question_index"] == 0


def test_question_end_ignored_outside_question_phase(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()

    with _ws(client, fake_conn, quiz_id, "user-1") as host:
        _join(host)
        host.receive_json()

        host.send_json({"type": "start_quiz"})
        host.receive_json()  # question_start

        host.send_json({"type": "question_end"})
        host.receive_json()  # rest_phase

        host.send_json({"type": "question_end"})  # already in rest -- ignored

        # Prove nothing stray got queued: force_next (valid now) advances
        # exactly once, straight to question_start index 1.
        host.send_json({"type": "force_next"})
        advanced = host.receive_json()
        assert advanced["type"] == "question_start"
        assert advanced["question_index"] == 1


# --- misc hardening -------------------------------------------------------------

def test_display_name_is_length_capped(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()

    with _ws(client, fake_conn, quiz_id, "user-1") as host:
        _join(host)
        host.receive_json()  # own join

        host.send_json({"type": "set_name", "name": "x" * 200})
        msg = host.receive_json()
        assert msg["type"] == "name_updated"
        assert len(msg["display_name"]) == 50


def test_reconnect_sync_state_reports_already_answered(monkeypatch, fake_conn, fake_pool):
    client = _client(monkeypatch, fake_pool)
    quiz_id = _quiz_id()

    with _ws(client, fake_conn, quiz_id, "user-1") as host, _ws(client, fake_conn, quiz_id, "user-2") as guest:
        _join(host)
        _join(guest)
        host.receive_json()
        host.receive_json()
        guest.receive_json()

        host.send_json({"type": "start_quiz"})
        host.receive_json()  # question_start
        guest.receive_json()

        host.send_json({"type": "answer", "question_index": 0, "answer": "4"})
        host.receive_json()  # answer_received
        guest.receive_json()
        # guest never answers -> phase stays "question" (no early-end).

        with _ws(client, fake_conn, quiz_id, "user-1") as reconnected:
            reconnected.receive_json()  # connected
            sync = reconnected.receive_json()
            assert sync["type"] == "sync_state"
            assert sync["phase"] == "question"
            assert sync["already_answered"] is True
            assert sync["your_answer"] == "4"
