"use client";
import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/AuthContext";
import {
  quizApi,
  Quiz,
  Question,
  QuizAnswerValue,
  MatchingQuestion,
  getQuestionType,
} from "@/lib/api";
import { isAnswerCorrect } from "@/lib/grading";
import { PigLoader } from "@/components/PigLoader";
import { MathText } from "@/components/MathText";
import { SoundToggle } from "@/components/SoundToggle";
import { playSound } from "@/lib/sound";

function shuffled<T>(items: T[]): T[] {
  const arr = [...items];
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

function renderReview(qq: Question, your: QuizAnswerValue | undefined) {
  const qtype = getQuestionType(qq);

  if (qtype === "multiple_choice" || qtype === "true_false") {
    const options = (qq as { options: string[] }).options;
    const correctAnswer = (qq as { correct_answer: string }).correct_answer;
    return (
      <div className="solo-opts">
        {options.map((opt) => {
          const isCorrect = opt === correctAnswer;
          const isYourWrong = opt === your && your !== correctAnswer;
          return (
            <div key={opt} className={`solo-opt${isCorrect ? " correct" : ""}${isYourWrong ? " wrong" : ""}`}>
              <span><MathText text={opt} /></span>
              {isCorrect && <span className="mark" style={{ color: "var(--jade)" }}>✓</span>}
              {isYourWrong && <span className="mark" style={{ color: "var(--persimmon)" }}>your answer</span>}
            </div>
          );
        })}
      </div>
    );
  }

  if (qtype === "fill_in_blank") {
    const q = qq as { accepted_answers: string[]; correct_answer: string };
    const yourText = typeof your === "string" ? your : "";
    const correct = isAnswerCorrect(qq, your);
    return (
      <div className="solo-opts">
        <div className={`solo-opt${yourText ? (correct ? " correct" : " wrong") : ""}`}>
          <span>Your answer: {yourText || "(blank)"}</span>
        </div>
        {!correct && (
          <div className="solo-opt correct">
            <span>Correct answer: {q.accepted_answers?.[0] ?? q.correct_answer}</span>
          </div>
        )}
      </div>
    );
  }

  if (qtype === "matching") {
    const q = qq as MatchingQuestion;
    const yourMap = your && typeof your === "object" ? (your as Record<string, string>) : {};
    return (
      <div className="solo-match">
        {q.pairs.map((pair) => {
          const yourRight = yourMap[pair.left];
          const rowCorrect = yourRight === pair.right;
          return (
            <div key={pair.left} className={`solo-match-row${rowCorrect ? " correct" : " wrong"}`}>
              <span className="solo-match-left"><MathText text={pair.left} /></span>
              <span className="solo-match-right">
                <MathText text={yourRight ?? "(no match)"} />
                {!rowCorrect && (
                  <span className="solo-match-hint"> → <MathText text={pair.right} /></span>
                )}
              </span>
            </div>
          );
        })}
      </div>
    );
  }

  return null;
}

export default function SoloQuizPage() {
  const { quizId } = useParams<{ quizId: string }>();
  const { user, loading } = useAuth();
  const router = useRouter();

  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  const [current, setCurrent] = useState(0);
  const [answers, setAnswers] = useState<Record<string, QuizAnswerValue>>({});
  const [phase, setPhase] = useState<"quiz" | "results">("quiz");
  const [submitting, setSubmitting] = useState(false);
  const [score, setScore] = useState<number | null>(null);

  useEffect(() => {
    if (!loading && !user) router.push("/login");
  }, [user, loading, router]);

  useEffect(() => {
    if (!user || !quizId) return;
    let cancelled = false;
    setPageLoading(true);
    quizApi
      .getById(quizId)
      .then((q) => {
        if (!cancelled) setQuiz(q);
      })
      .catch((e: any) => {
        if (!cancelled) setLoadError(e.message || "Couldn't load this quiz.");
      })
      .finally(() => {
        if (!cancelled) setPageLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user, quizId]);

  const questions = quiz?.questions ?? [];
  const total = questions.length;
  const q = questions[current];
  const selected = answers[current];
  const qType = q ? getQuestionType(q) : undefined;

  const matchRights = useMemo(() => {
    if (!q || getQuestionType(q) !== "matching") return [];
    return shuffled((q as MatchingQuestion).pairs.map((p) => p.right));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [quiz, current]);

  function chooseOption(option: string) {
    setAnswers((prev) => ({ ...prev, [current]: option }));
  }

  function chooseFillIn(text: string) {
    setAnswers((prev) => ({ ...prev, [current]: text }));
  }

  function chooseMatch(left: string, right: string) {
    setAnswers((prev) => {
      const existing = prev[current];
      const map = existing && typeof existing === "object" ? (existing as Record<string, string>) : {};
      return { ...prev, [current]: { ...map, [left]: right } };
    });
  }

  async function finish() {
    setSubmitting(true);
    try {
      const res = await quizApi.submit(quizId, answers);
      setScore(res.score);
    } catch {
      // Fall back to a locally computed score if the submit call fails.
      setScore(questions.filter((qq, i) => isAnswerCorrect(qq, answers[i])).length);
    } finally {
      setSubmitting(false);
      setPhase("results");
      playSound("complete");
      window.scrollTo(0, 0);
    }
  }

  function retry() {
    setAnswers({});
    setCurrent(0);
    setScore(null);
    setPhase("quiz");
    window.scrollTo(0, 0);
  }

  function leave() {
    router.push(quiz ? `/circles/${quiz.circle_id}` : "/dashboard");
  }

  if (loading || !user || pageLoading) {
    return <PigLoader />;
  }

  if (loadError || !quiz) {
    return (
      <div className="solo">
        <div className="solo-shell">
          <div className="empty">
            <h3>Quiz not available</h3>
            <p>{loadError || "This quiz doesn't exist."}</p>
            <button className="btn btn-primary btn-sm" onClick={() => router.push("/dashboard")}>
              Back to dashboard
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (total === 0) {
    return (
      <div className="solo">
        <div className="solo-shell">
          <div className="empty">
            <h3>{quiz.title}</h3>
            <p>This quiz has no questions yet.</p>
            <button className="btn btn-primary btn-sm" onClick={leave}>
              Back to circle
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ---- Results ----
  if (phase === "results") {
    const finalScore = score ?? 0;
    return (
      <div className="solo">
        <div className="solo-shell">
          <div className="solo-top">
            <div>
              <h1>{quiz.title}</h1>
              <div className="solo-progress">Solo practice · complete</div>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <SoundToggle />
              <button className="btn btn-ghost btn-sm" onClick={leave}>
                Back to circle
              </button>
            </div>
          </div>

          <div className="solo-card">
            <div className="solo-score">
              <div className="big">
                {finalScore} / {total}
              </div>
              <div className="lbl">{Math.round((finalScore / total) * 100)}% correct</div>
            </div>
          </div>

          <div className="solo-review">
            {questions.map((qq, i) => {
              const your = answers[i];
              return (
                <div key={i} className="review-item">
                  <p className="rq">
                    {i + 1}. <MathText text={qq.question} />
                  </p>
                  {renderReview(qq, your)}
                  {your === undefined && (
                    <p className="review-expl" style={{ color: "var(--ink-3)" }}>You skipped this question.</p>
                  )}
                  {qq.explanation && (
                    <p className="review-expl">
                      <b>Why:</b> <MathText text={qq.explanation} />
                    </p>
                  )}
                </div>
              );
            })}
          </div>

          <div className="solo-nav">
            <button className="btn btn-ghost" onClick={leave}>
              Back to circle
            </button>
            <button className="btn btn-primary" onClick={retry}>
              Try again
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ---- Quiz ----
  const isLast = current === total - 1;
  return (
    <div className="solo">
      <div className="solo-shell">
        <div className="solo-top">
          <div>
            <h1>{quiz.title}</h1>
            <div className="solo-progress">
              Question {current + 1} of {total}
            </div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <SoundToggle />
            <button className="btn btn-ghost btn-sm" onClick={leave}>
              Leave
            </button>
          </div>
        </div>

        <div className="solo-bar">
          <i style={{ width: `${((current + 1) / total) * 100}%` }} />
        </div>

        <div className="solo-card">
          <p className="solo-q"><MathText text={q.question} /></p>
          {(qType === "multiple_choice" || qType === "true_false") && (
            <div className="solo-opts">
              {(q as { options: string[] }).options.map((opt) => (
                <button
                  key={opt}
                  className={`solo-opt${selected === opt ? " selected" : ""}`}
                  onClick={() => chooseOption(opt)}
                >
                  <span><MathText text={opt} /></span>
                  {selected === opt && <span className="mark" style={{ color: "var(--cobalt)" }}>●</span>}
                </button>
              ))}
            </div>
          )}
          {qType === "fill_in_blank" && (
            <div className="solo-fillin">
              <input
                type="text"
                placeholder="Type your answer…"
                value={typeof selected === "string" ? selected : ""}
                onChange={(e) => chooseFillIn(e.target.value)}
              />
            </div>
          )}
          {qType === "matching" && (
            <div className="solo-match">
              {(q as MatchingQuestion).pairs.map((pair) => {
                const yourMap = selected && typeof selected === "object" ? (selected as Record<string, string>) : {};
                return (
                  <div key={pair.left} className="solo-match-row">
                    <span className="solo-match-left"><MathText text={pair.left} /></span>
                    <select
                      value={yourMap[pair.left] ?? ""}
                      onChange={(e) => chooseMatch(pair.left, e.target.value)}
                    >
                      <option value="" disabled>
                        Choose a match…
                      </option>
                      {matchRights.map((right) => (
                        <option key={right} value={right}>
                          {right}
                        </option>
                      ))}
                    </select>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="solo-nav">
          <button
            className="btn btn-ghost"
            onClick={() => setCurrent((c) => Math.max(0, c - 1))}
            disabled={current === 0}
          >
            ← Back
          </button>
          {isLast ? (
            <button className="btn btn-primary" onClick={finish} disabled={submitting}>
              {submitting ? "Submitting…" : "Finish"}
            </button>
          ) : (
            <button className="btn btn-primary" onClick={() => setCurrent((c) => Math.min(total - 1, c + 1))}>
              Next →
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
