"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/AuthContext";
import { quizApi, Quiz } from "@/lib/api";

export default function SoloQuizPage() {
  const { quizId } = useParams<{ quizId: string }>();
  const { user, loading } = useAuth();
  const router = useRouter();

  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  const [current, setCurrent] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
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

  function choose(option: string) {
    setAnswers((prev) => ({ ...prev, [current]: option }));
  }

  async function finish() {
    setSubmitting(true);
    try {
      const res = await quizApi.submit(quizId, answers);
      setScore(res.score);
    } catch {
      // Fall back to a locally computed score if the submit call fails.
      setScore(questions.filter((qq, i) => answers[i] === qq.correct_answer).length);
    } finally {
      setSubmitting(false);
      setPhase("results");
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
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh" }}>
        Loading…
      </div>
    );
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
            <button className="btn btn-ghost btn-sm" onClick={leave}>
              Back to circle
            </button>
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
                    {i + 1}. {qq.question}
                  </p>
                  <div className="solo-opts">
                    {qq.options.map((opt) => {
                      const isCorrect = opt === qq.correct_answer;
                      const isYourWrong = opt === your && your !== qq.correct_answer;
                      return (
                        <div
                          key={opt}
                          className={`solo-opt${isCorrect ? " correct" : ""}${isYourWrong ? " wrong" : ""}`}
                        >
                          <span>{opt}</span>
                          {isCorrect && <span className="mark" style={{ color: "var(--jade)" }}>✓</span>}
                          {isYourWrong && <span className="mark" style={{ color: "var(--persimmon)" }}>your answer</span>}
                        </div>
                      );
                    })}
                  </div>
                  {your === undefined && (
                    <p className="review-expl" style={{ color: "var(--ink-3)" }}>You skipped this question.</p>
                  )}
                  {qq.explanation && (
                    <p className="review-expl">
                      <b>Why:</b> {qq.explanation}
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
          <button className="btn btn-ghost btn-sm" onClick={leave}>
            Leave
          </button>
        </div>

        <div className="solo-bar">
          <i style={{ width: `${((current + 1) / total) * 100}%` }} />
        </div>

        <div className="solo-card">
          <p className="solo-q">{q.question}</p>
          <div className="solo-opts">
            {q.options.map((opt) => (
              <button
                key={opt}
                className={`solo-opt${selected === opt ? " selected" : ""}`}
                onClick={() => choose(opt)}
              >
                <span>{opt}</span>
                {selected === opt && <span className="mark" style={{ color: "var(--cobalt)" }}>●</span>}
              </button>
            ))}
          </div>
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
