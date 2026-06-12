from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Set
import json
import asyncio

router = APIRouter()

# Room state per quiz_id
class RoomState:
    def __init__(self):
        self.connections: Dict[str, WebSocket] = {}      # user_id -> ws
        self.display_names: Dict[str, str] = {}          # user_id -> name
        self.scores: Dict[str, int] = {}                 # user_id -> score
        self.ready: Set[str] = set()                     # user_ids who clicked Ready
        self.phase: str = "lobby"                        # lobby | question | rest | finished
        self.current_question: int = 0
        self.host_id: str = None
        self.next_question_task: asyncio.Task = None

rooms: Dict[str, RoomState] = {}

@router.websocket("/ws/{quiz_id}/{user_id}")
async def live_quiz_ws(websocket: WebSocket, quiz_id: str, user_id: str):
    await websocket.accept()

    if quiz_id not in rooms:
        rooms[quiz_id] = RoomState()

    room = rooms[quiz_id]

    # First to join is host
    if not room.host_id:
        room.host_id = user_id

    room.connections[user_id] = websocket
    room.scores.setdefault(user_id, 0)

    await broadcast(quiz_id, {
        "type": "user_joined",
        "user_id": user_id,
        "display_name": room.display_names.get(user_id, ""),
        "participants": _participants(room),
        "scores": room.scores,
        "phase": room.phase,
        "host_id": room.host_id,
    })

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            mtype = message.get("type")

            # --- Identity ---
            if mtype == "set_name":
                room.display_names[user_id] = message.get("name", "")
                await broadcast(quiz_id, {
                    "type": "name_updated",
                    "user_id": user_id,
                    "display_name": room.display_names[user_id],
                    "participants": _participants(room),
                })

            # --- Host starts quiz ---
            elif mtype == "start_quiz" and user_id == room.host_id:
                room.phase = "question"
                room.current_question = 0
                room.ready.clear()
                await broadcast(quiz_id, {
                    "type": "question_start",
                    "question_index": room.current_question,
                    "phase": "question",
                })

            # --- Player submits answer ---
            elif mtype == "answer":
                correct = message.get("correct", False)
                if correct:
                    room.scores[user_id] = room.scores.get(user_id, 0) + 1
                await broadcast(quiz_id, {
                    "type": "answer_received",
                    "user_id": user_id,
                    "question_index": message.get("question_index"),
                    "answer": message.get("answer"),
                    "correct": correct,
                })

            # --- Host ends a question → show leaderboard + start rest phase ---
            elif mtype == "question_end" and user_id == room.host_id:
                room.phase = "rest"
                room.ready.clear()
                await broadcast(quiz_id, {
                    "type": "rest_phase",
                    "phase": "rest",
                    "leaderboard": _leaderboard(room),
                    "question_index": room.current_question,
                })
                # Auto-advance after 15 seconds
                if room.next_question_task:
                    room.next_question_task.cancel()
                room.next_question_task = asyncio.create_task(
                    _auto_advance(quiz_id, room, delay=15)
                )

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
            elif mtype == "force_next" and user_id == room.host_id:
                if room.next_question_task:
                    room.next_question_task.cancel()
                await _advance_question(quiz_id, room)

    except WebSocketDisconnect:
        room.connections.pop(user_id, None)
        room.ready.discard(user_id)
        await broadcast(quiz_id, {
            "type": "user_left",
            "user_id": user_id,
            "participants": _participants(room),
            "scores": room.scores,
        })
        if not room.connections:
            if room.next_question_task:
                room.next_question_task.cancel()
            del rooms[quiz_id]


async def _auto_advance(quiz_id: str, room: RoomState, delay: int):
    await asyncio.sleep(delay)
    if quiz_id in rooms:
        await _advance_question(quiz_id, room)


async def _advance_question(quiz_id: str, room: RoomState):
    room.current_question += 1
    room.ready.clear()
    room.phase = "question"
    await broadcast(quiz_id, {
        "type": "question_start",
        "question_index": room.current_question,
        "phase": "question",
        "leaderboard": _leaderboard(room),
    })


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
