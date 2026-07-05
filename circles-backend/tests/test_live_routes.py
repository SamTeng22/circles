"""Characterization tests for the live-quiz WebSocket route in
app/api/routes/live.py.

These lock in *current* observable behavior (messages sent/received over the
socket, resulting state) as a regression safety net ahead of the planned
Redis-backed state refactor. They deliberately avoid asserting on the exact
shape of the in-memory `rooms` dict / `RoomState` object, since that's exactly
what the refactor is expected to replace -- only what a connected client can
observe is asserted on.

live.py has no DB or auth dependency (room state is a plain in-memory dict
keyed by quiz_id), so no fakes/overrides are needed here, unlike the other
route tests. Room state is module-global, so each test uses its own unique
quiz_id to avoid bleeding into other tests.
"""
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import live


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(live.router, prefix="/api/live")
    return TestClient(app)


def _quiz_id() -> str:
    return f"live-quiz-{uuid.uuid4()}"


def _ws(client, quiz_id, user_id):
    return client.websocket_connect(f"/api/live/ws/{quiz_id}/{user_id}")


# --- single user / lobby ----------------------------------------------------

def test_single_user_joins_lobby_and_receives_initial_state():
    client = _client()
    quiz_id = _quiz_id()

    with _ws(client, quiz_id, "user-1") as ws:
        msg = ws.receive_json()

        assert msg["type"] == "user_joined"
        assert msg["phase"] == "lobby"
        assert msg["host_id"] == "user-1"  # first joiner becomes host
        assert msg["participants"] == [{"user_id": "user-1", "display_name": ""}]
        assert msg["scores"] == {"user-1": 0}


def test_second_user_joining_is_seen_by_both_and_is_not_host():
    client = _client()
    quiz_id = _quiz_id()

    with _ws(client, quiz_id, "user-1") as host:
        host.receive_json()  # user-1's own join

        with _ws(client, quiz_id, "user-2") as guest:
            join_seen_by_host = host.receive_json()
            join_seen_by_guest = guest.receive_json()

            for msg in (join_seen_by_host, join_seen_by_guest):
                assert msg["type"] == "user_joined"
                assert msg["host_id"] == "user-1"  # host unchanged by a second joiner
                assert {p["user_id"] for p in msg["participants"]} == {"user-1", "user-2"}


# --- answering / score reflected in leaderboard -----------------------------

def test_answer_updates_score_reflected_in_leaderboard():
    client = _client()
    quiz_id = _quiz_id()

    with _ws(client, quiz_id, "user-1") as host, _ws(client, quiz_id, "user-2") as guest:
        host.receive_json()   # host's own join
        host.receive_json()   # guest's join, seen by host
        guest.receive_json()  # guest's own join (same broadcast)

        host.send_json({"type": "start_quiz"})
        host.receive_json()   # question_start
        guest.receive_json()

        # Note: "correct" is entirely self-reported by the submitting client
        # -- the server has no copy of the quiz questions/answer key, so it
        # just trusts whatever the client sends. That's the current design,
        # not something this test introduces.
        guest.send_json({
            "type": "answer",
            "question_index": 0,
            "answer": "A",
            "correct": True,
        })
        host.receive_json()   # answer_received
        guest.receive_json()

        host.send_json({"type": "question_end"})
        rest_for_host = host.receive_json()
        rest_for_guest = guest.receive_json()

        for msg in (rest_for_host, rest_for_guest):
            assert msg["type"] == "rest_phase"
            leaderboard = {e["user_id"]: e["score"] for e in msg["leaderboard"]}
            assert leaderboard == {"user-1": 0, "user-2": 1}


# --- auto-advance after the rest-phase timer --------------------------------

def test_phase_auto_advances_after_question_end_delay(monkeypatch):
    # The rest-phase auto-advance delay is a hardcoded `asyncio.sleep(15)`
    # inside question_end's handler (live.py), not a configurable parameter.
    # Rather than waiting 15 real seconds, patch asyncio.sleep to resolve
    # near-instantly so the test exercises the same code path (schedule a
    # delayed task -> it fires -> _advance_question runs) without the wait.
    async def _instant_sleep(seconds):
        return None
    monkeypatch.setattr(live.asyncio, "sleep", _instant_sleep)

    client = _client()
    quiz_id = _quiz_id()

    with _ws(client, quiz_id, "user-1") as host, _ws(client, quiz_id, "user-2") as guest:
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

def test_disconnect_mid_game_reflected_without_crashing_other_clients():
    client = _client()
    quiz_id = _quiz_id()

    with _ws(client, quiz_id, "user-1") as host:
        host.receive_json()  # host's own join

        with _ws(client, quiz_id, "user-2") as guest:
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
            "answer": "A",
            "correct": True,
        })
        answer_msg = host.receive_json()
        assert answer_msg["type"] == "answer_received"
        assert answer_msg["user_id"] == "user-1"


# --- final leaderboard -------------------------------------------------------

def test_leaderboard_at_final_question_reflects_correct_cumulative_scores():
    # live.py's RoomState.phase comment lists "finished" as a phase, but
    # nothing in this file ever assigns it -- _advance_question always
    # broadcasts "question_start", forever incrementing question_index with
    # no notion of a quiz's total question count (the backend doesn't know
    # it). The frontend infers "finished" once question_index reaches the
    # real question count. So the closest thing this backend has to a
    # "finished-phase leaderboard" is the leaderboard carried on the
    # question_start broadcast after the last real question ends -- this
    # test locks in that the cumulative scores are correct at that point.
    client = _client()
    quiz_id = _quiz_id()

    with _ws(client, quiz_id, "user-1") as host, _ws(client, quiz_id, "user-2") as guest:
        host.receive_json()
        host.receive_json()
        guest.receive_json()

        host.send_json({"type": "start_quiz"})
        host.receive_json()   # question_start index 0
        guest.receive_json()

        # Round 1: user-1 correct, user-2 wrong.
        host.send_json({"type": "answer", "question_index": 0, "answer": "A", "correct": True})
        host.receive_json()
        guest.receive_json()
        guest.send_json({"type": "answer", "question_index": 0, "answer": "B", "correct": False})
        host.receive_json()
        guest.receive_json()

        host.send_json({"type": "question_end"})
        host.receive_json()   # rest_phase
        guest.receive_json()

        host.send_json({"type": "force_next"})
        host.receive_json()   # question_start index 1
        guest.receive_json()

        # Round 2: user-2 answers correctly, user-1 doesn't answer this round.
        guest.send_json({"type": "answer", "question_index": 1, "answer": "A", "correct": True})
        host.receive_json()
        guest.receive_json()

        host.send_json({"type": "question_end"})
        host.receive_json()   # rest_phase
        guest.receive_json()

        host.send_json({"type": "force_next"})
        final_for_host = host.receive_json()  # question_start "past" the last question
        guest.receive_json()

        assert final_for_host["type"] == "question_start"
        leaderboard = {e["user_id"]: e["score"] for e in final_for_host["leaderboard"]}
        assert leaderboard == {"user-1": 1, "user-2": 1}
