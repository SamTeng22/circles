from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from typing import Dict, Set
import json
import asyncio
import time

from app.core.firebase import resolve_user_from_token
from app.db.database import get_pool
from app.services.authz import assert_member

router = APIRouter()

ALLOWED_TIME_LIMITS = {10, 20, 30, 60}
DEFAULT_TIME_LIMIT = 20
REST_DURATION = 15

# Room state per quiz_id
class RoomState:
    def __init__(self):
        self.connections: Dict[str, WebSocket] = {}      # user_id -> ws
        self.display_names: Dict[str, str] = {}          # user_id -> name
        self.scores: Dict[str, int] = {}                 # user_id -> score
        self.streaks: Dict[str, int] = {}                 # user_id -> consecutive correct answers
        self.answered: Set[str] = set()                   # user_ids who answered the current question
        self.answers: Dict[str, Dict[str, str]] = {}      # user_id -> {question_index_str: submitted_answer}
        self.ready: Set[str] = set()                     # user_ids who clicked Ready
        self.phase: str = "lobby"                        # lobby | question | rest | finished
        self.current_question: int = 0
        self.host_id: str = None
        self.next_question_task: asyncio.Task = None
        self.question_timer_task: asyncio.Task = None
        self.language: str | None = None                 # locked in by host on start_quiz
        self.raw_questions: list = []                     # full question set for this quiz, fetched once
        self.questions: list = []                          # language-filtered subset, locked in at start_quiz
        self.total_questions: int = 0
        self.time_limit: int = DEFAULT_TIME_LIMIT          # seconds per question, locked in by host
        self.question_started_at: float = None             # time.monotonic() timestamp
        self.rest_started_at: float = None                 # time.monotonic() timestamp

rooms: Dict[str, RoomState] = {}


async def _authorize(quiz_id: str, user_id: str) -> list:
    """Fetch the quiz and verify the user is a member of its circle.

    Returns the quiz's full question list. Raises HTTPException(404) if the
    quiz doesn't exist, or HTTPException(403) if the user isn't a member.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        quiz = await conn.fetchrow(
            "SELECT circle_id, questions FROM quizzes WHERE id = $1", quiz_id
        )
        if not quiz:
            raise HTTPException(status_code=404, detail="Quiz not found")
        await assert_member(conn, quiz["circle_id"], user_id)
    return json.loads(quiz["questions"]) if isinstance(quiz["questions"], str) else quiz["questions"]


@router.websocket("/ws/{quiz_id}")
async def live_quiz_ws(websocket: WebSocket, quiz_id: str):
    await websocket.accept()

    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401)
        return

    try:
        user = await resolve_user_from_token(token)
    except HTTPException:
        await websocket.close(code=4401)
        return

    user_id = str(user["id"])

    try:
        raw_questions = await _authorize(quiz_id, user_id)
    except HTTPException as e:
        await websocket.close(code=4403 if e.status_code == 403 else 4404)
        return

    if quiz_id not in rooms:
        rooms[quiz_id] = RoomState()
        rooms[quiz_id].raw_questions = raw_questions

    room = rooms[quiz_id]

    # First to join is host
    if not room.host_id:
        room.host_id = user_id

    # If this identity already has a live connection (e.g. a new tab/refresh
    # races ahead of the old one noticing it's gone), supersede it -- only
    # the newest connection for a given user_id should be able to act or
    # receive broadcasts. The old connection's own eventual disconnect is a
    # safe no-op once room.connections[user_id] no longer points at it (see
    # the WebSocketDisconnect handler below).
    stale_ws = room.connections.get(user_id)
    room.connections[user_id] = websocket
    room.scores.setdefault(user_id, 0)

    if stale_ws is not None and stale_ws is not websocket:
        try:
            await stale_ws.close(code=4000)
        except Exception:
            pass

    # Let this socket know its authoritative identity before anything else.
    await websocket.send_text(json.dumps({
        "type": "connected",
        "user_id": user_id,
    }))

    # Catch up a (re)connecting socket on the room's actual live state --
    # harmless on a normal first join (phase is just "lobby").
    await websocket.send_text(json.dumps({
        "type": "sync_state",
        "phase": room.phase,
        "question_index": room.current_question,
        "time_limit": room.time_limit,
        "time_remaining": _time_remaining(room),
        "rest_time_remaining": _rest_time_remaining(room),
        "leaderboard": _leaderboard(room),
        "ready": list(room.ready),
        "language": room.language,
        "already_answered": user_id in room.answered,
        "your_answer": room.answers.get(user_id, {}).get(str(room.current_question)),
    }))

    await broadcast(quiz_id, {
        "type": "user_joined",
        "user_id": user_id,
        "display_name": room.display_names.get(user_id, ""),
        "participants": _participants(room),
        "scores": room.scores,
        "phase": room.phase,
        "host_id": room.host_id,
        "language": room.language,
    })

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            mtype = message.get("type")

            # --- Identity ---
            if mtype == "set_name":
                room.display_names[user_id] = message.get("name", "")[:50]  # cap length
                await broadcast(quiz_id, {
                    "type": "name_updated",
                    "user_id": user_id,
                    "display_name": room.display_names[user_id],
                    "participants": _participants(room),
                    "host_id": room.host_id,
                })

            # --- Host starts quiz ---
            elif mtype == "start_quiz" and user_id == room.host_id:
                room.current_question = 0
                room.language = message.get("language") or "en"
                requested_limit = message.get("time_limit")
                room.time_limit = (
                    requested_limit if requested_limit in ALLOWED_TIME_LIMITS else DEFAULT_TIME_LIMIT
                )
                room.questions = [
                    q for q in room.raw_questions
                    if (q.get("language") or "en") == room.language
                ]
                room.total_questions = len(room.questions)
                room.streaks.clear()
                room.ready.clear()
                await _begin_question(quiz_id, room)

            # --- Player submits answer ---
            elif mtype == "answer" and user_id not in room.answered:
                question_index = message.get("question_index")
                submitted_answer = message.get("answer")
                correct = (
                    isinstance(question_index, int)
                    and 0 <= question_index < len(room.questions)
                    and submitted_answer == room.questions[question_index].get("correct_answer")
                )
                elapsed = _elapsed_seconds(room)
                if correct:
                    streak = room.streaks.get(user_id, 0) + 1
                    room.streaks[user_id] = streak
                    points = _calculate_points(elapsed, room.time_limit, streak)
                else:
                    room.streaks[user_id] = 0
                    points = 0
                room.scores[user_id] = room.scores.get(user_id, 0) + points
                room.answered.add(user_id)
                room.answers.setdefault(user_id, {})[str(question_index)] = submitted_answer
                await broadcast(quiz_id, {
                    "type": "answer_received",
                    "user_id": user_id,
                    "question_index": question_index,
                    "answer": submitted_answer,
                    "correct": correct,
                    "points": points,
                    "streak": room.streaks.get(user_id, 0),
                })
                # Everyone's answered -> end the question early, no need to
                # wait for the timer.
                if room.phase == "question" and room.answered >= set(room.connections.keys()):
                    if room.question_timer_task:
                        room.question_timer_task.cancel()
                    await _end_question(quiz_id, room)

            # --- Host ends a question → show leaderboard + start rest phase ---
            elif mtype == "question_end" and user_id == room.host_id and room.phase == "question":
                if room.question_timer_task:
                    room.question_timer_task.cancel()
                await _end_question(quiz_id, room)

            # --- Player marks ready during rest ---
            elif mtype == "player_ready" and room.phase == "rest":
                room.ready.add(user_id)
                await broadcast(quiz_id, {
                    "type": "ready_update",
                    "ready": list(room.ready),
                    "total": len(room.connections),
                })
                # All ready → advance early
                if room.ready >= set(room.connections.keys()):
                    if room.next_question_task:
                        room.next_question_task.cancel()
                    await _advance_question(quiz_id, room)

            # --- Chat message during rest ---
            elif mtype == "chat_message":
                await broadcast(quiz_id, {
                    "type": "chat_message",
                    "user_id": user_id,
                    "display_name": room.display_names.get(user_id, "Someone"),
                    "text": message.get("text", "")[:300],  # cap length
                    "timestamp": message.get("timestamp"),
                })

            # --- Host manually advances ---
            elif mtype == "force_next" and user_id == room.host_id and room.phase == "rest":
                if room.next_question_task:
                    room.next_question_task.cancel()
                if room.question_timer_task:
                    room.question_timer_task.cancel()
                await _advance_question(quiz_id, room)

            # --- Host removes a player ---
            elif mtype == "kick_player" and user_id == room.host_id:
                target_id = message.get("user_id")
                target_ws = room.connections.get(target_id)
                if target_ws and target_id != user_id:
                    await target_ws.send_text(json.dumps({"type": "kicked"}))
                    # Clean up and broadcast immediately rather than relying
                    # on the target's own receive loop to notice the close --
                    # its exception handler below is guarded to skip a user
                    # that's already been removed, so this doesn't double up.
                    room.connections.pop(target_id, None)
                    room.ready.discard(target_id)
                    await broadcast(quiz_id, {
                        "type": "user_left",
                        "user_id": target_id,
                        "participants": _participants(room),
                        "scores": room.scores,
                        "host_id": room.host_id,
                    })
                    await target_ws.close(code=4403)

            # --- Host force-ends the quiz straight to results ---
            elif mtype == "end_quiz" and user_id == room.host_id:
                if room.next_question_task:
                    room.next_question_task.cancel()
                if room.question_timer_task:
                    room.question_timer_task.cancel()
                await _finish_quiz(quiz_id, room)

    except WebSocketDisconnect:
        # If a newer connection for this user_id has since taken over (e.g. a
        # refresh opened a second socket before the first noticed it closed,
        # or this user was kicked -- see kick_player above, which already
        # pops the mapping before closing the socket), room.connections[user_id]
        # no longer points at *this* websocket -- this stale disconnect must
        # be a no-op so it can't clobber the newer connection's bookkeeping.
        if room.connections.get(user_id) is websocket:
            room.connections.pop(user_id, None)
            room.ready.discard(user_id)
            if user_id == room.host_id and room.connections:
                room.host_id = next(iter(room.connections))
            await broadcast(quiz_id, {
                "type": "user_left",
                "user_id": user_id,
                "participants": _participants(room),
                "scores": room.scores,
                "host_id": room.host_id,
            })
        if not room.connections:
            if room.next_question_task:
                room.next_question_task.cancel()
            if room.question_timer_task:
                room.question_timer_task.cancel()
            # The game may be abandoned mid-play (nobody sent end_quiz and it
            # never reached the last question) -- persist whatever progress
            # exists rather than silently losing it. _persist_results is a
            # no-op if the quiz never actually started.
            if room.phase != "finished" and room.total_questions > 0:
                await _persist_results(quiz_id, room)
            rooms.pop(quiz_id, None)


async def _auto_advance(quiz_id: str, room: RoomState, delay: int):
    await asyncio.sleep(delay)
    if quiz_id in rooms:
        await _advance_question(quiz_id, room)


async def _advance_question(quiz_id: str, room: RoomState):
    room.current_question += 1
    room.ready.clear()

    if room.current_question >= room.total_questions:
        await _finish_quiz(quiz_id, room)
        return

    await _begin_question(quiz_id, room, extra={"leaderboard": _leaderboard(room)})


async def _finish_quiz(quiz_id: str, room: RoomState):
    if room.phase == "finished":
        return  # already finished -- avoid double-persisting on a race
    room.phase = "finished"
    await broadcast(quiz_id, {
        "type": "quiz_finished",
        "leaderboard": _leaderboard(room),
    })
    await _persist_results(quiz_id, room)


async def _persist_results(quiz_id: str, room: RoomState):
    if room.total_questions == 0:
        return  # quiz was never actually started (e.g. end_quiz sent from the lobby)
    pool = await get_pool()
    async with pool.acquire() as conn:
        for user_id, score in room.scores.items():
            await conn.execute(
                """
                INSERT INTO quiz_scores (quiz_id, user_id, score, answers)
                VALUES ($1, $2, $3, $4::jsonb)
                """,
                quiz_id, user_id, score, room.answers.get(user_id, {}),
            )


async def _begin_question(quiz_id: str, room: RoomState, extra: dict | None = None):
    if room.question_timer_task:
        room.question_timer_task.cancel()
    room.phase = "question"
    room.answered.clear()
    room.question_started_at = time.monotonic()
    message = {
        "type": "question_start",
        "question_index": room.current_question,
        "phase": "question",
        "language": room.language,
        "time_limit": room.time_limit,
    }
    if extra:
        message.update(extra)
    await broadcast(quiz_id, message)
    room.question_timer_task = asyncio.create_task(
        _auto_end_question(quiz_id, room, room.time_limit)
    )


async def _auto_end_question(quiz_id: str, room: RoomState, delay: int):
    await asyncio.sleep(delay)
    if quiz_id in rooms and room.phase == "question":
        await _end_question(quiz_id, room)


async def _end_question(quiz_id: str, room: RoomState):
    room.phase = "rest"
    room.ready.clear()
    room.rest_started_at = time.monotonic()
    await broadcast(quiz_id, {
        "type": "rest_phase",
        "phase": "rest",
        "leaderboard": _leaderboard(room),
        "question_index": room.current_question,
    })
    if room.next_question_task:
        room.next_question_task.cancel()
    room.next_question_task = asyncio.create_task(
        _auto_advance(quiz_id, room, delay=REST_DURATION)
    )


def _elapsed_seconds(room: RoomState) -> float:
    if room.question_started_at is None:
        return 0.0
    elapsed = time.monotonic() - room.question_started_at
    return max(0.0, min(elapsed, float(room.time_limit)))


def _time_remaining(room: RoomState) -> int:
    if room.phase != "question":
        return room.time_limit
    return max(0, round(room.time_limit - _elapsed_seconds(room)))


def _rest_time_remaining(room: RoomState) -> int:
    if room.phase != "rest" or room.rest_started_at is None:
        return REST_DURATION
    elapsed = time.monotonic() - room.rest_started_at
    return max(0, round(REST_DURATION - elapsed))


def _calculate_points(elapsed: float, time_limit: int, streak: int) -> int:
    remaining_fraction = 1 - (elapsed / time_limit) if time_limit > 0 else 0.0
    base = 500 + round(500 * remaining_fraction)
    streak_bonus = min(50 * (streak - 1), 250)
    return base + streak_bonus


def _leaderboard(room: RoomState) -> list:
    return sorted(
        [
            {
                "user_id": uid,
                "display_name": room.display_names.get(uid, ""),
                "score": score,
            }
            for uid, score in room.scores.items()
        ],
        key=lambda x: x["score"],
        reverse=True,
    )


def _participants(room: RoomState) -> list:
    return [
        {
            "user_id": uid,
            "display_name": room.display_names.get(uid, ""),
        }
        for uid in room.connections
    ]


async def broadcast(quiz_id: str, message: dict):
    if quiz_id not in rooms:
        return
    dead = []
    for uid, ws in rooms[quiz_id].connections.items():
        try:
            await ws.send_text(json.dumps(message))
        except Exception:
            dead.append(uid)
    for uid in dead:
        rooms[quiz_id].connections.pop(uid, None)
