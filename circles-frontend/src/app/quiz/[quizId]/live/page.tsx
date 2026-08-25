"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/AuthContext";
import { getIdToken } from "@/lib/firebase";
import { quizApi, Quiz, Question, getQuestionLanguage } from "@/lib/api";
import { SoundToggle } from "@/components/SoundToggle";
import { PigLoader } from "@/components/PigLoader";
import { AnimalMascot } from "@/components/AnimalMascot";
import type { AnimalName } from "@/components/animalArt";
import { MathText } from "@/components/MathText";
import { playSound } from "@/lib/sound";

const LANGUAGE_LABELS: Record<string, string> = {
  en: "English",
  tl: "Filipino",
  zh: "Chinese",
};

const TIME_LIMIT_OPTIONS = [10, 20, 30, 60];
const DEFAULT_TIME_LIMIT = 20;
const TIMEOUT_SENTINEL = "__TIMEOUT__";
// One mascot per answer slot, so an option is identifiable by its animal as
// well as its text. The pig stays the app's own mascot and isn't in the set.
const TILE_ANIMALS: AnimalName[] = ["dog", "cat", "rabbit", "bear"];

type Phase = "lobby" | "question" | "rest" | "finished";

interface Participant { user_id: string; display_name: string; }
interface LeaderboardEntry { user_id: string; display_name: string; score: number; }
interface ChatMsg { user_id: string; display_name: string; text: string; }

function initials(name: string): string {
  return (name || "?")[0].toUpperCase();
}

export default function LiveQuizPage() {
  const { quizId } = useParams<{ quizId: string }>();
  const { user } = useAuth();
  const router = useRouter();

  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const [phase, setPhase] = useState<Phase>("lobby");
  const [questionIndex, setQuestionIndex] = useState(0);
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [readyIds, setReadyIds] = useState<string[]>([]);
  const [selectedAnswer, setSelectedAnswer] = useState<string | null>(null);
  const [answerResult, setAnswerResult] = useState<"correct" | "wrong" | "timeout" | null>(null);
  const [earnedPoints, setEarnedPoints] = useState(0);
  const [streak, setStreak] = useState(0);
  const [chatMessages, setChatMessages] = useState<ChatMsg[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatOpen, setChatOpen] = useState(false);
  const [unreadChat, setUnreadChat] = useState(false);
  const [countdown, setCountdown] = useState(15);
  const [timeLimit, setTimeLimit] = useState(DEFAULT_TIME_LIMIT);
  const [questionTimeLeft, setQuestionTimeLeft] = useState(DEFAULT_TIME_LIMIT);
  const [pickedTimeLimit, setPickedTimeLimit] = useState(DEFAULT_TIME_LIMIT);
  const [hostId, setHostId] = useState<string | null>(null);
  const [showLeaderboard, setShowLeaderboard] = useState(false);
  const [language, setLanguage] = useState<string | null>(null);
  const [myUserId, setMyUserId] = useState("");
  const [connectionError, setConnectionError] = useState(false);
  const [kicked, setKicked] = useState(false);
  const [pendingKick, setPendingKick] = useState<Participant | null>(null);
  const [pendingEndQuiz, setPendingEndQuiz] = useState(false);

  const ws = useRef<WebSocket | null>(null);
  const countdownRef = useRef<NodeJS.Timeout | null>(null);
  const questionCountdownRef = useRef<NodeJS.Timeout | null>(null);
  const chatBottomRef = useRef<HTMLDivElement>(null);
  const hasConnectedRef = useRef(false);
  // handleMessage is bound once to the socket's onmessage handler, so it
  // closes over myUserId from that render (empty string, pre-connect) --
  // this ref stays current for it to read instead, same trick as quizRef.
  const myUserIdRef = useRef("");
  const chatOpenRef = useRef(false);

  // Firebase uid only gates *whether* we attempt to connect; the server is
  // the source of truth for our identity within the room (see the
  // "connected" message below) since it resolves the token to its own
  // internal users.id, which isn't necessarily the Firebase uid string.
  const firebaseUid = user?.uid ?? "";
  const userId = myUserId;
  const isHost = userId === hostId;

  const distinctLanguages = useMemo(
    () => Array.from(new Set((quiz?.questions ?? []).map(getQuestionLanguage))),
    [quiz]
  );

  const filteredQuestions: Question[] = useMemo(() => {
    if (!quiz) return [];
    const target = language ?? getQuestionLanguage(quiz.questions[0]);
    return quiz.questions.filter((q) => getQuestionLanguage(q) === target);
  }, [quiz, language]);

  const currentQuestion = filteredQuestions[questionIndex];
  const totalQuestions = filteredQuestions.length;

  function countForLanguage(q: Quiz | null, lang: string | null): number {
    if (!q || q.questions.length === 0) return 0;
    const target = lang ?? getQuestionLanguage(q.questions[0]);
    return q.questions.filter((question) => getQuestionLanguage(question) === target).length;
  }

  // Load quiz data
  useEffect(() => {
    quizApi.getById(quizId).then(setQuiz).catch(console.error);
  }, [quizId]);

  // Connect WebSocket
  useEffect(() => {
    if (!firebaseUid) return;
    let cancelled = false;
    let socket: WebSocket | null = null;
    hasConnectedRef.current = false;

    (async () => {
      const token = await getIdToken();
      if (!token || cancelled) return;

      const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
      const wsUrl = apiUrl.replace(/^http/, "ws");
      socket = new WebSocket(`${wsUrl}/api/live/ws/${quizId}?token=${encodeURIComponent(token)}`);
      ws.current = socket;

      socket.onmessage = (e) => {
        const msg = JSON.parse(e.data);
        handleMessage(msg);
      };

      socket.onopen = () => {
        send({ type: "set_name", name: user?.displayName ?? "Student" });
      };

      socket.onclose = () => {
        if (!hasConnectedRef.current) setConnectionError(true);
      };
    })();

    return () => {
      cancelled = true;
      socket?.close();
    };
  }, [firebaseUid]);

  // Scroll chat to bottom
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  // Keep the ref in sync for handleMessage's closure, and clear the unread
  // dot as soon as the drawer is opened.
  useEffect(() => {
    chatOpenRef.current = chatOpen;
    if (chatOpen) setUnreadChat(false);
  }, [chatOpen]);

  // Tick sound for the last few seconds of a question -- questionTimeLeft
  // only changes once per second (see startQuestionCountdown), so this
  // fires exactly once per remaining second, not on every render.
  useEffect(() => {
    if (phase === "question" && questionTimeLeft > 0 && questionTimeLeft <= 3) {
      playSound("tick");
    }
  }, [phase, questionTimeLeft]);

  function send(msg: object) {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(msg));
    }
  }

  function handleMessage(msg: any) {
    switch (msg.type) {
      case "connected":
        hasConnectedRef.current = true;
        myUserIdRef.current = msg.user_id;
        setMyUserId(msg.user_id);
        break;

      case "sync_state": {
        if (msg.phase) setPhase(msg.phase);
        setQuestionIndex(msg.question_index ?? 0);
        if (msg.language) setLanguage(msg.language);
        setLeaderboard(msg.leaderboard ?? []);
        setReadyIds(msg.ready ?? []);
        if (msg.phase === "question") {
          startQuestionCountdown(msg.time_limit ?? DEFAULT_TIME_LIMIT, msg.time_remaining ?? DEFAULT_TIME_LIMIT);
          // Reconnected after already answering this question -- lock the
          // options instead of showing an interactive-looking UI that would
          // silently no-op (the server ignores a second answer).
          if (msg.already_answered) {
            setSelectedAnswer(msg.your_answer ?? TIMEOUT_SENTINEL);
          }
        } else if (msg.phase === "rest") {
          setShowLeaderboard(true);
          startCountdown(msg.rest_time_remaining ?? 15);
        }
        break;
      }

      case "kicked":
        setKicked(true);
        break;

      case "user_joined":
      case "user_left":
      case "name_updated":
        setParticipants(msg.participants ?? []);
        setHostId(msg.host_id ?? null);
        if (msg.phase) setPhase(msg.phase);
        if (msg.language) setLanguage(msg.language);
        break;

      case "question_start": {
        if (msg.language) setLanguage(msg.language);
        setPhase("question");
        setQuestionIndex(msg.question_index);
        setSelectedAnswer(null);
        setAnswerResult(null);
        setEarnedPoints(0);
        setReadyIds([]);
        setShowLeaderboard(false);
        if (msg.leaderboard) setLeaderboard(msg.leaderboard);
        stopCountdown();
        startQuestionCountdown(msg.time_limit ?? DEFAULT_TIME_LIMIT);
        playSound("start");
        break;
      }

      case "quiz_finished":
        playSound("complete");
        setPhase("finished");
        setLeaderboard(msg.leaderboard ?? []);
        stopCountdown();
        stopQuestionCountdown();
        break;

      case "answer_received":
        if (msg.user_id === myUserIdRef.current) {
          setAnswerResult(msg.correct ? "correct" : "wrong");
          setEarnedPoints(msg.points ?? 0);
          setStreak(msg.streak ?? 0);
          playSound(msg.correct ? "correct" : "wrong");
          stopQuestionCountdown();
        }
        break;

      case "rest_phase":
        setPhase("rest");
        setLeaderboard(msg.leaderboard ?? []);
        setShowLeaderboard(true);
        stopQuestionCountdown();
        startCountdown(15);
        break;

      case "ready_update":
        setReadyIds(msg.ready ?? []);
        break;

      case "chat_message":
        setChatMessages((prev) => [...prev, msg]);
        if (msg.user_id !== myUserIdRef.current && !chatOpenRef.current) setUnreadChat(true);
        break;
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

  function startQuestionCountdown(limitSeconds: number, startAt: number = limitSeconds) {
    setTimeLimit(limitSeconds);
    setQuestionTimeLeft(startAt);
    stopQuestionCountdown();
    questionCountdownRef.current = setInterval(() => {
      setQuestionTimeLeft((t) => {
        if (t <= 1) { stopQuestionCountdown(); return 0; }
        return t - 1;
      });
    }, 1000);
  }

  function stopQuestionCountdown() {
    if (questionCountdownRef.current) clearInterval(questionCountdownRef.current);
  }

  // Time's up and nothing was picked -- lock the UI and let the server know
  // so the streak resets like a normal wrong answer would.
  useEffect(() => {
    if (phase !== "question" || questionTimeLeft > 0 || selectedAnswer) return;
    setSelectedAnswer(TIMEOUT_SENTINEL);
    setAnswerResult("timeout");
    send({
      type: "answer",
      question_index: questionIndex,
      answer: null,
    });
  }, [questionTimeLeft, phase, selectedAnswer, questionIndex]);

  function submitAnswer(answer: string) {
    if (selectedAnswer || !currentQuestion) return;
    setSelectedAnswer(answer);
    // The server looks up the correct answer itself now -- we just report
    // which option was picked.
    send({
      type: "answer",
      question_index: questionIndex,
      answer,
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

  function startQuiz(pickedLanguage?: string) {
    const lang = pickedLanguage ?? distinctLanguages[0] ?? "en";
    send({ type: "start_quiz", language: lang, time_limit: pickedTimeLimit });
  }

  function confirmKick() {
    if (!pendingKick) return;
    send({ type: "kick_player", user_id: pendingKick.user_id });
    setPendingKick(null);
  }

  function confirmEndQuiz() {
    send({ type: "end_quiz" });
    setPendingEndQuiz(false);
  }

  const isReady = readyIds.includes(userId);

  // ── Kicked ─────────────────────────────────────────────────────────
  if (kicked) {
    return (
      <div className="live">
        <div className="live-shell" style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "60vh" }}>
          <div className="live-card" style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12, maxWidth: 380, textAlign: "center" }}>
            <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600, color: "var(--ink)" }}>You were removed from this game</h2>
            <p style={{ margin: 0, fontSize: 14, color: "var(--ink-3)" }}>The host removed you from this session.</p>
            <button
              className="btn btn-primary btn-sm"
              onClick={() => router.push(quiz ? `/circles/${quiz.circle_id}` : "/dashboard")}
            >
              Back to circle
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── Connection failed ─────────────────────────────────────────────
  if (connectionError) {
    return (
      <div className="live">
        <div className="live-shell" style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "60vh" }}>
          <div className="live-card" style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12, maxWidth: 380, textAlign: "center" }}>
            <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600, color: "var(--ink)" }}>Couldn't join this quiz</h2>
            <p style={{ margin: 0, fontSize: 14, color: "var(--ink-3)" }}>
              You may not have access to this quiz, or your session expired. Try refreshing the page.
            </p>
            <button
              className="btn btn-primary btn-sm"
              onClick={() => router.push(quiz ? `/circles/${quiz.circle_id}` : "/dashboard")}
            >
              Back to circle
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── Loading ────────────────────────────────────────────────────────
  if (!quiz) {
    return <PigLoader />;
  }

  // ── Lobby ──────────────────────────────────────────────────────────
  if (phase === "lobby") {
    return (
      <div className="live">
        <div className="live-shell" style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 24 }}>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
            <span className="live-badge"><span className="dot" />LIVE</span>
            <h1 style={{ margin: 0, fontSize: 24, fontWeight: 600, textAlign: "center", color: "var(--ink)" }}>{quiz.title}</h1>
          </div>
          <div className="live-card" style={{ width: "100%", maxWidth: 380 }}>
            <p style={{ margin: "0 0 12px", fontSize: 14, color: "var(--ink-3)" }}>Waiting for players ({participants.length})</p>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {participants.map((p) => (
                <div key={p.user_id} className="live-player-row">
                  <div className="live-av">{initials(p.display_name)}</div>
                  {p.display_name || "Joining..."}
                  {p.user_id === hostId && <span className="host-tag">host</span>}
                  {isHost && p.user_id !== hostId && (
                    <button
                      onClick={() => setPendingKick(p)}
                      className="btn btn-ghost btn-sm"
                      style={{ marginLeft: "auto" }}
                    >
                      Remove
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
          {isHost && (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8, width: "100%", maxWidth: 320 }}>
              <p style={{ margin: 0, fontSize: 14, color: "var(--ink-3)" }}>Seconds per question</p>
              <div className="seg" style={{ width: "100%" }}>
                {TIME_LIMIT_OPTIONS.map((secs) => (
                  <button
                    key={secs}
                    onClick={() => setPickedTimeLimit(secs)}
                    className={pickedTimeLimit === secs ? "on" : ""}
                  >
                    {secs}s
                  </button>
                ))}
              </div>
            </div>
          )}
          {isHost && distinctLanguages.length > 1 && (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
              <p style={{ margin: 0, fontSize: 14, color: "var(--ink-3)" }}>This quiz has multiple languages — play with:</p>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "center" }}>
                {distinctLanguages.map((code) => {
                  const count = countForLanguage(quiz, code);
                  return (
                    <button
                      key={code}
                      onClick={() => startQuiz(code)}
                      disabled={participants.length < 1}
                      className="btn btn-primary btn-lg"
                    >
                      {LANGUAGE_LABELS[code] ?? code} ({count})
                    </button>
                  );
                })}
              </div>
            </div>
          )}
          {isHost && distinctLanguages.length <= 1 && (
            <button
              onClick={() => startQuiz()}
              disabled={participants.length < 1}
              className="btn btn-primary btn-lg"
            >
              Start quiz
            </button>
          )}
          {!isHost && <p style={{ margin: 0, fontSize: 14, color: "var(--ink-3)" }}>Waiting for host to start...</p>}
        </div>

        {pendingKick && (
          <div className="live-modal-overlay" onClick={() => setPendingKick(null)}>
            <div className="live-modal" onClick={(e) => e.stopPropagation()}>
              <h3>Remove player?</h3>
              <p>Remove {pendingKick.display_name || "this player"} from the game? They won't be able to rejoin this session.</p>
              <div className="live-modal-actions">
                <button className="btn btn-ghost btn-sm" onClick={() => setPendingKick(null)}>Cancel</button>
                <button className="btn btn-primary btn-sm" onClick={confirmKick}>Remove</button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ── Finished ───────────────────────────────────────────────────────
  if (phase === "finished") {
    const top3 = leaderboard.slice(0, 3);
    const showPodium = top3.length === 3;
    const podiumOrder = showPodium ? [
      { entry: top3[1], place: "second" as const },
      { entry: top3[0], place: "first" as const },
      { entry: top3[2], place: "third" as const },
    ] : [];
    const restEntries = showPodium ? leaderboard.slice(3) : leaderboard;

    const rankClass = (rank: number) => (rank === 1 ? "gold" : rank === 2 ? "silver" : rank === 3 ? "bronze" : "");

    return (
      <div className="live">
        <div className="live-shell" style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 24 }}>
          <h2 style={{ margin: 0, fontSize: 24, fontWeight: 600, color: "var(--ink)" }}>Final scores</h2>

          {showPodium && (
            <div className="live-podium">
              {podiumOrder.map(({ entry, place }) => (
                <div key={entry.user_id} className={`live-podium-slot ${place}`}>
                  <div className="live-podium-name">{entry.display_name || "Player"}</div>
                  <div className="live-podium-block">
                    {place === "first" ? "🥇" : place === "second" ? "🥈" : "🥉"}
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="live-lb" style={{ width: "100%", maxWidth: 380 }}>
            {restEntries.map((entry) => {
              const rank = leaderboard.indexOf(entry) + 1;
              return (
                <div
                  key={entry.user_id}
                  className={`live-lb-row${entry.user_id === userId ? " me" : ""}`}
                >
                  <span className={`live-lb-rank ${rankClass(rank)}`}>{rank}</span>
                  <span className="live-lb-name">{entry.display_name || "Player"}</span>
                  <span className="live-lb-score">{entry.score} pts</span>
                </div>
              );
            })}
          </div>

          <button className="btn btn-primary btn-sm" onClick={() => router.push(`/circles/${quiz.circle_id}`)}>
            Back to circle
          </button>
        </div>
      </div>
    );
  }

  // ── Question + Rest ────────────────────────────────────────────────
  return (
    <div className="live" style={{ minHeight: "100vh" }}>
      {/* Top bar */}
      <div className="live-top">
        <div className="live-top-title">
          <span className="live-badge"><span className="dot" />LIVE</span>
          <span>{quiz.title}</span>
        </div>
        <div className="live-top-actions">
          {isHost && (
            <button
              onClick={() => setPendingEndQuiz(true)}
              className="btn btn-ghost btn-sm"
            >
              End quiz
            </button>
          )}
          <SoundToggle />
          <button
            className="live-chat-toggle"
            onClick={() => setChatOpen((v) => !v)}
            aria-label="Toggle chat"
          >
            💬
            {unreadChat && <span className="unread-dot" />}
          </button>
          <span className="live-progress">
            {questionIndex + 1} / {totalQuestions}
          </span>
        </div>
      </div>

      <div className="live-body">
        {/* Main area */}
        <div className="live-main">

          {/* Leaderboard overlay (rest phase) */}
          {phase === "rest" && showLeaderboard && (
            <div className="live-card">
              <div className="live-lb-header">
                <h3 style={{ margin: 0, fontWeight: 600, fontSize: 14, color: "var(--ink)" }}>Leaderboard</h3>
                <div className="live-lb-stats">
                  <span style={{ fontSize: 14, color: "var(--ink-3)" }}>
                    Next in <span style={{ fontWeight: 600, color: "var(--ink-2)" }}>{countdown}s</span>
                  </span>
                  <span style={{ fontSize: 12, color: "var(--ink-3)" }}>
                    {readyIds.length}/{participants.length} ready
                  </span>
                </div>
              </div>
              <div className="live-lb">
                {leaderboard.map((entry, i) => {
                  const medal = ["🥇", "🥈", "🥉"][i] ?? `${i + 1}`;
                  const rankClass = i === 0 ? "gold" : i === 1 ? "silver" : i === 2 ? "bronze" : "";
                  return (
                    <div
                      key={entry.user_id}
                      className={`live-lb-row${entry.user_id === userId ? " me" : ""}`}
                    >
                      <span className={`live-lb-rank ${rankClass}`}>{medal}</span>
                      <span className="live-lb-name">{entry.display_name || "Player"}</span>
                      <span className="live-lb-score">{entry.score} pts</span>
                    </div>
                  );
                })}
              </div>
              <div className="live-lb-actions">
                {!isReady && (
                  <button onClick={markReady} className="btn btn-primary btn-sm" style={{ flex: 1 }}>
                    Ready ✓
                  </button>
                )}
                {isReady && (
                  <div style={{ flex: 1, padding: "9px 0", borderRadius: 12, fontSize: 14, textAlign: "center", background: "var(--paper)", color: "var(--ink-3)" }}>
                    Waiting for others...
                  </div>
                )}
                {isHost && (
                  <button
                    onClick={() => send({ type: "force_next" })}
                    className="btn btn-ghost btn-sm"
                  >
                    Skip wait
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Question card */}
          {phase === "question" && currentQuestion && (
            <div className="live-card live-question-card">
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <div className="solo-bar" style={{ marginBottom: 0 }}>
                  <i style={{
                    width: `${(questionTimeLeft / timeLimit) * 100}%`,
                    background: questionTimeLeft <= 5 ? "var(--persimmon)" : "var(--ink)",
                  }} />
                </div>
                <span style={{ alignSelf: "flex-end", fontSize: 12, color: "var(--ink-3)" }}>{questionTimeLeft}s</span>
              </div>
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
                <p style={{ margin: 0, fontWeight: 500, fontSize: 16, lineHeight: 1.4, flex: 1, color: "var(--ink)" }}>
                  <MathText text={currentQuestion.question} />
                </p>
                <span className="chip chip-cobalt" style={{ flexShrink: 0 }}>
                  {currentQuestion.bloom_level}
                </span>
              </div>
              <div className="live-tile-grid">
                {currentQuestion.options.map((opt, i) => {
                  const isCorrect = opt === currentQuestion.correct_answer;
                  const isPicked = opt === selectedAnswer;
                  const animal = TILE_ANIMALS[i % TILE_ANIMALS.length];
                  let stateClass = "";
                  if (selectedAnswer) {
                    if (isCorrect) stateClass = "correct";
                    else if (isPicked) stateClass = "wrong";
                    else stateClass = "dim";
                  }
                  return (
                    <button
                      key={opt}
                      onClick={() => submitAnswer(opt)}
                      disabled={!!selectedAnswer}
                      className={`live-tile live-tile-${animal} ${stateClass}`}
                    >
                      <span className="icon">
                        <AnimalMascot animal={animal} size={30} bob={false} />
                      </span>
                      <span><MathText text={opt} /></span>
                    </button>
                  );
                })}
              </div>
              {answerResult && (
                <p
                  key={answerResult}
                  className="live-points-pop"
                  style={{ margin: 0, fontSize: 14, fontWeight: 600, color: answerResult === "correct" ? "var(--jade)" : "var(--persimmon)" }}
                >
                  {answerResult === "correct" && (
                    <>Correct! +{earnedPoints} pts{streak > 1 ? <span className="live-streak-flicker"> 🔥 x{streak}</span> : null}</>
                  )}
                  {answerResult === "wrong" && (
                    <>Wrong. Answer: <MathText text={currentQuestion.correct_answer} /></>
                  )}
                  {answerResult === "timeout" && (
                    <>Time's up! Answer: <MathText text={currentQuestion.correct_answer} /></>
                  )}
                </p>
              )}
              {isHost && (
                <button
                  onClick={endQuestion}
                  className="btn btn-dark btn-sm"
                  style={{ alignSelf: "flex-end", marginTop: 4 }}
                >
                  End question →
                </button>
              )}
            </div>
          )}
        </div>

        {/* Chat backdrop (mobile only, shown while drawer is open) */}
        {chatOpen && (
          <div className="live-chat-backdrop" onClick={() => setChatOpen(false)} />
        )}

        {/* Chat sidebar / drawer */}
        <div className={`live-chat${chatOpen ? " open" : ""}`}>
          <div className="live-chat-head">Chat</div>
          <div className="live-chat-body">
            {chatMessages.length === 0 && (
              <p style={{ margin: "16px 0 0", fontSize: 12, textAlign: "center", color: "var(--ink-3)" }}>No messages yet</p>
            )}
            {chatMessages.map((msg, i) => (
              <div key={i} className={`live-chat-msg${msg.user_id === userId ? " me" : ""}`}>
                <span className="who">{msg.display_name}</span>
                <div className="bubble">{msg.text}</div>
              </div>
            ))}
            <div ref={chatBottomRef} />
          </div>
          <div className="live-chat-foot">
            <input
              placeholder={phase === "rest" ? "Chat..." : "Rest phase only"}
              value={chatInput}
              disabled={phase !== "rest"}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendChat()}
            />
            <button
              onClick={sendChat}
              disabled={phase !== "rest" || !chatInput.trim()}
              className="btn btn-dark btn-sm"
            >
              ↑
            </button>
          </div>
        </div>
      </div>

      {pendingEndQuiz && (
        <div className="live-modal-overlay" onClick={() => setPendingEndQuiz(false)}>
          <div className="live-modal" onClick={(e) => e.stopPropagation()}>
            <h3>End the quiz?</h3>
            <p>This ends the game for everyone right now and jumps straight to final scores.</p>
            <div className="live-modal-actions">
              <button className="btn btn-ghost btn-sm" onClick={() => setPendingEndQuiz(false)}>Cancel</button>
              <button className="btn btn-primary btn-sm" onClick={confirmEndQuiz}>End quiz</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
