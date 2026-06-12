"use client";
import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { useAuth } from "@/lib/AuthContext";
import { quizApi, Quiz } from "@/lib/api";

type Phase = "lobby" | "question" | "rest" | "finished";

interface Participant { user_id: string; display_name: string; }
interface LeaderboardEntry { user_id: string; display_name: string; score: number; }
interface ChatMsg { user_id: string; display_name: string; text: string; }

export default function LiveQuizPage() {
  const { quizId } = useParams<{ quizId: string }>();
  const { user } = useAuth();

  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const [phase, setPhase] = useState<Phase>("lobby");
  const [questionIndex, setQuestionIndex] = useState(0);
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [readyIds, setReadyIds] = useState<string[]>([]);
  const [selectedAnswer, setSelectedAnswer] = useState<string | null>(null);
  const [answerResult, setAnswerResult] = useState<"correct" | "wrong" | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMsg[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [countdown, setCountdown] = useState(15);
  const [hostId, setHostId] = useState<string | null>(null);
  const [showLeaderboard, setShowLeaderboard] = useState(false);

  const ws = useRef<WebSocket | null>(null);
  const countdownRef = useRef<NodeJS.Timeout | null>(null);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  const userId = user?.uid ?? "";
  const isHost = userId === hostId;
  const currentQuestion = quiz?.questions?.[questionIndex];
  const totalQuestions = quiz?.questions?.length ?? 0;

  // Load quiz data
  useEffect(() => {
    quizApi.getById(quizId).then(setQuiz).catch(console.error);
  }, [quizId]);

  // Connect WebSocket
  useEffect(() => {
    if (!userId) return;
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const wsUrl = apiUrl.replace(/^http/, "ws");
    const socket = new WebSocket(`${wsUrl}/api/live/ws/${quizId}/${userId}`);
    ws.current = socket;

    socket.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      handleMessage(msg);
    };

    socket.onopen = () => {
      send({ type: "set_name", name: user?.displayName ?? "Student" });
    };

    return () => socket.close();
  }, [userId]);

  // Scroll chat to bottom
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  function send(msg: object) {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(msg));
    }
  }

  function handleMessage(msg: any) {
    switch (msg.type) {
      case "user_joined":
      case "user_left":
      case "name_updated":
        setParticipants(msg.participants ?? []);
        setHostId(msg.host_id ?? null);
        if (msg.phase) setPhase(msg.phase);
        break;

      case "question_start":
        setPhase("question");
        setQuestionIndex(msg.question_index);
        setSelectedAnswer(null);
        setAnswerResult(null);
        setReadyIds([]);
        setShowLeaderboard(false);
        if (msg.leaderboard) setLeaderboard(msg.leaderboard);
        stopCountdown();
        break;

      case "answer_received":
        if (msg.user_id === userId) {
          setAnswerResult(msg.correct ? "correct" : "wrong");
        }
        break;

      case "rest_phase":
        setPhase("rest");
        setLeaderboard(msg.leaderboard ?? []);
        setShowLeaderboard(true);
        startCountdown(15);
        break;

      case "ready_update":
        setReadyIds(msg.ready ?? []);
        break;

      case "chat_message":
        setChatMessages((prev) => [...prev, msg]);
        break;

      case "question_start":
        setPhase("finished");
        setLeaderboard(msg.leaderboard ?? []);
        break;
    }

    // Detect finished (past last question)
    if (msg.type === "question_start" && msg.question_index >= totalQuestions) {
      setPhase("finished");
    }
  }

  function startCountdown(seconds: number) {
    setCountdown(seconds);
    stopCountdown();
    countdownRef.current = setInterval(() => {
      setCountdown((c) => {
        if (c <= 1) { stopCountdown(); return 0; }
        return c - 1;
      });
    }, 1000);
  }

  function stopCountdown() {
    if (countdownRef.current) clearInterval(countdownRef.current);
  }

  function submitAnswer(answer: string) {
    if (selectedAnswer || !currentQuestion) return;
    setSelectedAnswer(answer);
    const correct = answer === currentQuestion.correct_answer;
    send({
      type: "answer",
      question_index: questionIndex,
      answer,
      correct,
    });
  }

  function markReady() {
    send({ type: "player_ready" });
  }

  function sendChat() {
    if (!chatInput.trim()) return;
    send({
      type: "chat_message",
      text: chatInput.trim(),
      timestamp: new Date().toISOString(),
    });
    setChatInput("");
  }

  function endQuestion() {
    send({ type: "question_end" });
  }

  function startQuiz() {
    send({ type: "start_quiz" });
  }

  const isReady = readyIds.includes(userId);

  // ── Lobby ──────────────────────────────────────────────────────────
  if (phase === "lobby") {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center gap-6 px-4">
        <h1 className="text-2xl font-semibold">{quiz?.title ?? "Loading..."}</h1>
        <div className="bg-white border border-gray-100 rounded-2xl p-6 w-full max-w-sm">
          <p className="text-sm text-gray-500 mb-3">Waiting for players ({participants.length})</p>
          <div className="flex flex-col gap-2">
            {participants.map((p) => (
              <div key={p.user_id} className="flex items-center gap-2 text-sm">
                <div className="w-7 h-7 rounded-full bg-purple-100 text-purple-700 flex items-center justify-center font-medium text-xs">
                  {(p.display_name || "?")[0].toUpperCase()}
                </div>
                {p.display_name || "Joining..."}
                {p.user_id === hostId && <span className="text-xs text-gray-400 ml-auto">host</span>}
              </div>
            ))}
          </div>
        </div>
        {isHost && (
          <button
            onClick={startQuiz}
            disabled={participants.length < 1}
            className="px-6 py-3 bg-black text-white rounded-xl font-medium hover:bg-gray-800 disabled:opacity-40"
          >
            Start quiz
          </button>
        )}
        {!isHost && <p className="text-sm text-gray-400">Waiting for host to start...</p>}
      </div>
    );
  }

  // ── Finished ───────────────────────────────────────────────────────
  if (phase === "finished") {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center gap-6 px-4">
        <h2 className="text-2xl font-semibold">Final scores</h2>
        <div className="w-full max-w-sm flex flex-col gap-2">
          {leaderboard.map((entry, i) => (
            <div
              key={entry.user_id}
              className={`flex items-center gap-3 bg-white border rounded-xl px-4 py-3 ${entry.user_id === userId ? "border-purple-300" : "border-gray-100"}`}
            >
              <span className="text-lg font-semibold w-6 text-gray-400">{i + 1}</span>
              <span className="flex-1 text-sm font-medium">{entry.display_name || "Player"}</span>
              <span className="text-sm font-semibold">{entry.score} pts</span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // ── Question + Rest ────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Top bar */}
      <div className="bg-white border-b px-4 py-3 flex items-center justify-between">
        <span className="text-sm font-medium">{quiz?.title}</span>
        <span className="text-sm text-gray-400">
          {questionIndex + 1} / {totalQuestions}
        </span>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Main area */}
        <div className="flex-1 flex flex-col p-4 gap-4 overflow-y-auto">

          {/* Leaderboard overlay (rest phase) */}
          {phase === "rest" && showLeaderboard && (
            <div className="bg-white border border-gray-100 rounded-2xl p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-sm">Leaderboard</h3>
                <div className="flex items-center gap-3">
                  <span className="text-sm text-gray-400">
                    Next in <span className="font-medium text-gray-700">{countdown}s</span>
                  </span>
                  <span className="text-xs text-gray-400">
                    {readyIds.length}/{participants.length} ready
                  </span>
                </div>
              </div>
              <div className="flex flex-col gap-2">
                {leaderboard.map((entry, i) => {
                  const medal = ["🥇", "🥈", "🥉"][i] ?? `${i + 1}.`;
                  return (
                    <div
                      key={entry.user_id}
                      className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-all ${
                        entry.user_id === userId
                          ? "bg-purple-50 border border-purple-200"
                          : "bg-gray-50"
                      }`}
                    >
                      <span className="w-6 text-center">{medal}</span>
                      <span className="flex-1 font-medium">{entry.display_name || "Player"}</span>
                      <span className="font-semibold">{entry.score} pts</span>
                    </div>
                  );
                })}
              </div>
              <div className="mt-4 flex gap-2">
                {!isReady && (
                  <button
                    onClick={markReady}
                    className="flex-1 py-2 bg-black text-white rounded-lg text-sm font-medium hover:bg-gray-800"
                  >
                    Ready ✓
                  </button>
                )}
                {isReady && (
                  <div className="flex-1 py-2 bg-gray-100 text-gray-500 rounded-lg text-sm text-center">
                    Waiting for others...
                  </div>
                )}
                {isHost && (
                  <button
                    onClick={() => send({ type: "force_next" })}
                    className="px-4 py-2 border border-gray-200 rounded-lg text-sm hover:bg-gray-50"
                  >
                    Skip wait
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Question card */}
          {phase === "question" && currentQuestion && (
            <div className="bg-white border border-gray-100 rounded-2xl p-5 flex flex-col gap-4">
              <div className="flex items-start justify-between gap-3">
                <p className="font-medium text-base leading-snug flex-1">
                  {currentQuestion.question}
                </p>
                <span className="text-xs px-2 py-1 rounded-full bg-purple-50 text-purple-700 shrink-0">
                  {currentQuestion.bloom_level}
                </span>
              </div>
              <div className="grid grid-cols-1 gap-2">
                {currentQuestion.options.map((opt) => {
                  let style = "border-gray-200 hover:border-gray-400 hover:bg-gray-50";
                  if (selectedAnswer) {
                    if (opt === currentQuestion.correct_answer)
                      style = "border-green-400 bg-green-50 text-green-800";
                    else if (opt === selectedAnswer)
                      style = "border-red-300 bg-red-50 text-red-700";
                    else style = "border-gray-100 opacity-50";
                  }
                  return (
                    <button
                      key={opt}
                      onClick={() => submitAnswer(opt)}
                      disabled={!!selectedAnswer}
                      className={`text-left px-4 py-3 border rounded-xl text-sm transition ${style}`}
                    >
                      {opt}
                    </button>
                  );
                })}
              </div>
              {answerResult && (
                <p className={`text-sm font-medium ${answerResult === "correct" ? "text-green-600" : "text-red-500"}`}>
                  {answerResult === "correct" ? "Correct! +1 point" : `Wrong. Answer: ${currentQuestion.correct_answer}`}
                </p>
              )}
              {isHost && (
                <button
                  onClick={endQuestion}
                  className="mt-1 self-end px-4 py-2 bg-black text-white rounded-lg text-sm hover:bg-gray-800"
                >
                  End question →
                </button>
              )}
            </div>
          )}
        </div>

        {/* Chat sidebar */}
        <div className="w-64 border-l bg-white flex flex-col shrink-0">
          <div className="px-4 py-3 border-b text-sm font-medium text-gray-700">Chat</div>
          <div className="flex-1 overflow-y-auto px-3 py-2 flex flex-col gap-2">
            {chatMessages.length === 0 && (
              <p className="text-xs text-gray-400 text-center mt-4">No messages yet</p>
            )}
            {chatMessages.map((msg, i) => (
              <div key={i} className={`flex flex-col gap-0.5 ${msg.user_id === userId ? "items-end" : "items-start"}`}>
                <span className="text-xs text-gray-400">{msg.display_name}</span>
                <div
                  className={`px-3 py-2 rounded-2xl text-sm max-w-full break-words ${
                    msg.user_id === userId
                      ? "bg-black text-white rounded-tr-sm"
                      : "bg-gray-100 text-gray-800 rounded-tl-sm"
                  }`}
                >
                  {msg.text}
                </div>
              </div>
            ))}
            <div ref={chatBottomRef} />
          </div>
          <div className="p-3 border-t flex gap-2">
            <input
              className="flex-1 border rounded-lg px-3 py-2 text-sm"
              placeholder={phase === "rest" ? "Chat..." : "Rest phase only"}
              value={chatInput}
              disabled={phase !== "rest"}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendChat()}
            />
            <button
              onClick={sendChat}
              disabled={phase !== "rest" || !chatInput.trim()}
              className="px-3 py-2 bg-black text-white rounded-lg text-sm disabled:opacity-30"
            >
              ↑
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
