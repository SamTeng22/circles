"use client";
import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/AuthContext";
import { flashcardsApi, FlashcardDeck } from "@/lib/api";

export default function StudyDeckPage() {
  const { deckId } = useParams<{ deckId: string }>();
  const { user, loading } = useAuth();
  const router = useRouter();

  const [deck, setDeck] = useState<FlashcardDeck | null>(null);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  // Study state
  const [order, setOrder] = useState<number[]>([]);
  const [pos, setPos] = useState(0);
  const [flipped, setFlipped] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.push("/login");
  }, [user, loading, router]);

  useEffect(() => {
    if (!user || !deckId) return;
    let cancelled = false;
    setPageLoading(true);
    flashcardsApi
      .getById(deckId)
      .then((d) => {
        if (cancelled) return;
        setDeck(d);
        setOrder(d.cards.map((_, i) => i));
      })
      .catch((e: any) => {
        if (!cancelled) setLoadError(e.message || "Couldn't load this deck.");
      })
      .finally(() => {
        if (!cancelled) setPageLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user, deckId]);

  const cards = deck?.cards ?? [];
  const total = order.length;
  const card = total > 0 ? cards[order[pos]] : undefined;

  const next = useCallback(() => {
    setFlipped(false);
    setPos((p) => Math.min(total - 1, p + 1));
  }, [total]);

  const prev = useCallback(() => {
    setFlipped(false);
    setPos((p) => Math.max(0, p - 1));
  }, []);

  function shuffle() {
    const shuffled = [...order];
    for (let i = shuffled.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
    }
    setOrder(shuffled);
    setPos(0);
    setFlipped(false);
  }

  function restart() {
    setOrder(cards.map((_, i) => i));
    setPos(0);
    setFlipped(false);
  }

  function leave() {
    router.push(deck ? `/circles/${deck.circle_id}` : "/dashboard");
  }

  // Keyboard: space/enter flips, arrows navigate.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === " " || e.key === "Enter") {
        e.preventDefault();
        setFlipped((f) => !f);
      } else if (e.key === "ArrowRight") {
        next();
      } else if (e.key === "ArrowLeft") {
        prev();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [next, prev]);

  if (loading || !user || pageLoading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh" }}>
        Loading…
      </div>
    );
  }

  if (loadError || !deck) {
    return (
      <div className="solo">
        <div className="solo-shell">
          <div className="empty">
            <h3>Deck not available</h3>
            <p>{loadError || "This deck doesn't exist."}</p>
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
            <h3>{deck.title}</h3>
            <p>This deck has no cards yet.</p>
            <button className="btn btn-primary btn-sm" onClick={leave}>
              Back to circle
            </button>
          </div>
        </div>
      </div>
    );
  }

  const isLast = pos === total - 1;

  return (
    <div className="solo">
      <div className="solo-shell">
        <div className="solo-top">
          <div>
            <h1>{deck.title}</h1>
            <div className="solo-progress">
              Card {pos + 1} of {total}
            </div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-ghost btn-sm" onClick={shuffle}>
              Shuffle
            </button>
            <button className="btn btn-ghost btn-sm" onClick={leave}>
              Leave
            </button>
          </div>
        </div>

        <div className="solo-bar">
          <i style={{ width: `${((pos + 1) / total) * 100}%` }} />
        </div>

        {/* Flip card */}
        <button
          onClick={() => setFlipped((f) => !f)}
          title="Click or press space to flip"
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: 14,
            width: "100%",
            minHeight: 300,
            padding: "40px 28px",
            margin: "10px 0",
            textAlign: "center",
            cursor: "pointer",
            borderRadius: 16,
            border: "1px solid rgba(0,0,0,0.10)",
            background: flipped ? "var(--panel, #f6f6f8)" : "var(--paper, #fff)",
            boxShadow: "0 2px 14px rgba(0,0,0,0.06)",
            transition: "background 120ms ease",
          }}
        >
          <span
            className="eyebrow"
            style={{ color: flipped ? "var(--jade)" : "var(--cobalt)" }}
          >
            {flipped ? "Answer" : "Prompt"}
          </span>
          <span style={{ fontSize: 22, lineHeight: 1.4, fontWeight: flipped ? 400 : 600 }}>
            {flipped ? card?.back : card?.front}
          </span>
          {!flipped && card?.hint ? (
            <span className="sub" style={{ fontSize: 13 }}>
              Hint: {card.hint}
            </span>
          ) : null}
          <span className="sub" style={{ fontSize: 12, marginTop: 6 }}>
            {flipped ? "Click to see prompt" : "Click to reveal answer"}
          </span>
        </button>

        <div className="solo-nav">
          <button className="btn btn-ghost" onClick={prev} disabled={pos === 0}>
            ← Back
          </button>
          {isLast ? (
            <button className="btn btn-primary" onClick={restart}>
              Restart
            </button>
          ) : (
            <button className="btn btn-primary" onClick={next}>
              Next →
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
