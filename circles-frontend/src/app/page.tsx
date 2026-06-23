"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/AuthContext";
import { BrandGlyph } from "@/components/BrandGlyph";

function StepRings() {
  return (
    <svg viewBox="0 0 120 84" style={{ width: "100%", height: "100%" }}>
      <circle cx="48" cy="40" r="24" fill="#FF5A47" opacity=".4" style={{ mixBlendMode: "multiply" }} />
      <circle cx="72" cy="40" r="24" fill="#3F3AE6" opacity=".4" style={{ mixBlendMode: "multiply" }} />
      <circle cx="60" cy="54" r="24" fill="#0CB78D" opacity=".4" style={{ mixBlendMode: "multiply" }} />
    </svg>
  );
}

const scattered = [
  { l: 12, t: 14 }, { l: 70, t: 10 }, { l: 78, t: 62 }, { l: 16, t: 66 }, { l: 44, t: 30 },
];
const clustered = [
  { l: 40, t: 40 }, { l: 60, t: 40 }, { l: 62, t: 60 }, { l: 38, t: 60 }, { l: 50, t: 50 },
];
const noteData = [
  { color: "#FF5A47", label: "SAM" },
  { color: "#3F3AE6", label: "MAYA" },
  { color: "#0CB78D", label: "DIEGO" },
  { color: "#F5A524", label: "PRIYA" },
  { color: "#7C5CFF", label: "THEO" },
];

export default function LandingPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [merged, setMerged] = useState(false);
  const [stageTitle, setStageTitle] = useState("5 students uploaded notes");
  const [stageSub, setStageSub] = useState("scattered, overlapping, contradicting");
  const [joinCode, setJoinCode] = useState("");
  const noteRefs = useRef<(HTMLDivElement | null)[]>([]);
  const mergeTimer = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    if (!loading && user) router.push("/dashboard");
  }, [user, loading, router]);

  const place = useCallback((arr: typeof scattered) => {
    noteRefs.current.forEach((n, i) => {
      if (n) {
        n.style.left = arr[i].l + "%";
        n.style.top = arr[i].t + "%";
        n.style.transform = "translate(-50%,-50%)";
      }
    });
  }, []);

  const runMerge = useCallback(
    (force = false) => {
      if (window.matchMedia("(prefers-reduced-motion:reduce)").matches) {
        place(clustered);
        setMerged(true);
        setStageTitle("1 verified set");
        setStageSub("87% agreed · 3 flagged for review");
        return;
      }
      setMerged(false);
      place(scattered);
      setStageTitle("5 students uploaded notes");
      setStageSub("scattered, overlapping, contradicting");
      clearTimeout(mergeTimer.current);
      mergeTimer.current = setTimeout(() => {
        place(clustered);
        setMerged(true);
        setStageTitle("1 verified set");
        setStageSub("87% agreed · 3 flagged for review");
      }, force ? 500 : 900);
    },
    [place]
  );

  useEffect(() => {
    place(scattered);
    const t = setTimeout(() => runMerge(false), 600);
    return () => clearTimeout(t);
  }, [place, runMerge]);


  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh" }}>
        Loading…
      </div>
    );
  }

  return (
    <>
      {/* NAV */}
      <nav className="nav">
        <div className="nav-in">
          <div className="brand">
            <BrandGlyph />
            <span className="brand-name">Circ<b>l</b>es</span>
          </div>
          <div className="nav-links">
            <a href="#how">How it works</a>
            <a href="#consensus">Verified notes</a>
            <a href="#live">Live quizzes</a>
          </div>
          <div className="nav-cta">
            <a className="nav-login" href="/login">Log in</a>
            <button className="btn btn-dark" onClick={() => router.push("/signup")}>Get started</button>
          </div>
        </div>
      </nav>

      {/* HERO */}
      <header className="hero">
        <div className="hero-l">
          <div className="hero-pill">
            <span className="d" />
            Built for study groups, not solo cramming
          </div>
          <h1 className="hero-title">
            Five sets of notes.<br />
            One <span className="ink-mix">verified</span> truth.
          </h1>
          <p className="hero-lead">
            Join a circle, pool everyone's notes, and let Circles merge them into one set — keeping what the group agrees on and flagging what they don't. Then quiz each other live.
          </p>
          <div className="hero-actions">
            <button className="btn btn-primary btn-lg" onClick={() => router.push("/signup")}>
              Start a circle — free
            </button>
            <button
              className="btn btn-ghost btn-lg"
              onClick={() => document.getElementById("how")?.scrollIntoView({ behavior: "smooth" })}
            >
              See how it works
            </button>
          </div>
          <div className="hero-note">
            No card needed · <b>Join with a code</b> if your group already has a circle
          </div>
        </div>

        <div className="stage-wrap">
          <div className={`stage${merged ? " merged" : ""}`}>
            <div className="stage-grid" />
            {noteData.map((note, i) => (
              <div
                key={i}
                className="note"
                ref={(el) => { noteRefs.current[i] = el; }}
                style={{ background: note.color }}
              >
                <span className="lab">{note.label}</span>
              </div>
            ))}
            <div className="stage-core">
              <b>87%</b>
              <span>agreed core</span>
            </div>
            <div className="stage-cap">
              <div className="t">
                {stageTitle}
                <small>{stageSub}</small>
              </div>
              <button className="replay" onClick={() => runMerge(true)}>↻ Replay</button>
            </div>
          </div>
        </div>
      </header>

      {/* TRUST ROW */}
      <div className="trust">
        <span><b>4,200+</b> study circles</span>
        <span className="sep" />
        <span><b>11</b> universities piloting</span>
        <span className="sep" />
        <span><b>320k</b> notes merged this term</span>
      </div>

      {/* HOW IT WORKS */}
      <section className="block" id="how">
        <div className="sec-head">
          <span className="eyebrow">How it works</span>
          <h2>Three steps from messy notes to a study set you trust.</h2>
          <p>Each step builds on the last — that's why the order matters.</p>
        </div>
        <div className="steps">
          <div className="step">
            <span className="step-n">STEP 01</span>
            <h3>Join a circle</h3>
            <p>Make a circle for your class or join an existing one with a 6-character code. Everyone in it is a contributor.</p>
            <div className="step-art">
              <StepRings />
            </div>
          </div>
          <div className="step">
            <span className="step-n">STEP 02</span>
            <h3>Pool your notes</h3>
            <p>Upload PDFs, photos, or typed notes. Circles merges them automatically, keeping the majority and flagging conflicts.</p>
            <div className="step-art">
              <StepRings />
            </div>
          </div>
          <div className="step">
            <span className="step-n">STEP 03</span>
            <h3>Quiz together</h3>
            <p>Generate flashcards and quizzes from the verified set — then run a live, timed quiz with the whole circle.</p>
            <div className="step-art">
              <StepRings />
            </div>
          </div>
        </div>
      </section>

      {/* CONSENSUS FEATURE */}
      <section className="block" id="consensus">
        <div className="feat">
          <div className="feat-copy">
            <span className="eyebrow">Verified notes</span>
            <h2>It keeps what the group got right — and shows its work.</h2>
            <p>When notes disagree, Circles doesn't guess. It goes with the majority, tells you the split, and lets the overruled student contest it.</p>
            <ul className="feat-list">
              <li>
                <span className="ic" style={{ background: "var(--persimmon)" }}>!</span>
                <div><b>Flags every disagreement</b> with the vote count, so nothing silently slips through.</div>
              </li>
              <li>
                <span className="ic" style={{ background: "var(--cobalt)" }}>+</span>
                <div><b>Surfaces gaps</b> nobody covered, so the set is complete before exam week.</div>
              </li>
              <li>
                <span className="ic" style={{ background: "var(--jade)" }}>✓</span>
                <div><b>Builds quizzes from verified facts only</b> — flagged answers are excluded until resolved.</div>
              </li>
            </ul>
          </div>
          <div className="demo-card">
            <div className="demo-h">
              <b>Cell Biology · disagreements</b>
              <span className="chip chip-flag">3 to resolve</span>
            </div>
            <div className="recon">
              <span className="recon-ic" style={{ background: "var(--persimmon)" }}>!</span>
              <div>
                <p>Where does the Krebs cycle happen? <b>4 of 5</b> say mitochondrial matrix; 1 says inner membrane.</p>
                <p className="kept">kept: <b>mitochondrial matrix</b> · 1 note overruled</p>
              </div>
            </div>
            <div className="recon">
              <span className="recon-ic" style={{ background: "var(--persimmon)" }}>!</span>
              <div>
                <p>Net ATP per glucose — 3 say ~30–32, 2 say 36–38.</p>
                <p className="kept">kept: <b>30–32 ATP</b> · current estimate</p>
              </div>
            </div>
            <div className="recon">
              <span className="recon-ic" style={{ background: "var(--cobalt)" }}>+</span>
              <div>
                <p>The electron transport chain is missing — the pathway stops at the Krebs cycle.</p>
                <p className="kept" style={{ color: "var(--cobalt)" }}>gap: someone should add a note</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* LIVE QUIZ FEATURE */}
      <section className="block" id="live">
        <div className="live-feat">
          <div>
            <span className="eyebrow">Live quizzes</span>
            <h2>Turn revision into a 6-person race.</h2>
            <p>Everyone answers the same timed question at once. The leaderboard reshuffles after each one, and between rounds you chat, regroup, and ready up for the next.</p>
            <div className="feat-tags">
              <span className="feat-tag">⏱ Timed questions</span>
              <span className="feat-tag">📊 Live leaderboard</span>
              <span className="feat-tag">💬 Break-time chat</span>
              <span className="feat-tag">🏆 Top-3 podium</span>
            </div>
          </div>
          <div className="lb-mini">
            <div className="lb-row lead">
              <span className="lb-rank">1</span>
              <span className="lb-av" style={{ background: "#3F3AE6" }}>MA</span>
              <span className="lb-name">Maya<span className="lb-delta">▲1</span></span>
              <span className="lb-score">2,140</span>
            </div>
            <div className="lb-row me">
              <span className="lb-rank">2</span>
              <span className="lb-av" style={{ background: "#FF5A47" }}>YOU</span>
              <span className="lb-name">You<span className="lb-delta">▲2</span></span>
              <span className="lb-score">1,980</span>
            </div>
            <div className="lb-row">
              <span className="lb-rank">3</span>
              <span className="lb-av" style={{ background: "#F5A524" }}>PR</span>
              <span className="lb-name">Priya</span>
              <span className="lb-score">1,720</span>
            </div>
            <div className="lb-row">
              <span className="lb-rank">4</span>
              <span className="lb-av" style={{ background: "#0CB78D" }}>DG</span>
              <span className="lb-name">Diego</span>
              <span className="lb-score">1,610</span>
            </div>
            <div className="lb-row">
              <span className="lb-rank">5</span>
              <span className="lb-av" style={{ background: "#7C5CFF" }}>TH</span>
              <span className="lb-name">Theo</span>
              <span className="lb-score">1,205</span>
            </div>
          </div>
        </div>
      </section>

      {/* FINAL CTA */}
      <div className="cta-band">
        <div className="cta-inner">
          <svg className="cta-rings" viewBox="0 0 1180 300" preserveAspectRatio="xMidYMid slice">
            <circle cx="540" cy="150" r="120" fill="#FF5A47" opacity=".1" style={{ mixBlendMode: "multiply" }} />
            <circle cx="640" cy="150" r="120" fill="#3F3AE6" opacity=".1" style={{ mixBlendMode: "multiply" }} />
            <circle cx="590" cy="210" r="120" fill="#0CB78D" opacity=".1" style={{ mixBlendMode: "multiply" }} />
          </svg>
          <h2>Your group already has the answers.</h2>
          <p>Circles just puts them in one place. Free for students.</p>
          <div className="cta-actions">
            <button className="btn btn-primary btn-lg" onClick={() => router.push("/signup")}>
              Create your circle
            </button>
            <div className="join-inline">
              <input
                placeholder="Have a code?"
                maxLength={7}
                value={joinCode}
                onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
              />
              <button
                className="btn btn-dark"
                onClick={() => {
                  const code = joinCode.trim();
                  router.push(code ? `/signup?code=${code}` : "/signup");
                }}
              >
                Join
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* FOOTER */}
      <footer>
        <div className="foot-in">
          <div style={{ maxWidth: "260px" }}>
            <div className="brand" style={{ marginBottom: "12px" }}>
              <BrandGlyph />
              <span className="brand-name">Circ<b>l</b>es</span>
            </div>
            <p style={{ fontSize: "13.5px", color: "var(--ink-2)", margin: 0 }}>
              Study together, verified together. Built by students, for study groups.
            </p>
          </div>
          <div className="foot-cols">
            <div className="foot-col">
              <h4>Product</h4>
              <a href="#how">How it works</a>
              <a href="#consensus">Verified notes</a>
              <a href="#live">Live quizzes</a>
              <a href="#">Flashcards</a>
            </div>
            <div className="foot-col">
              <h4>Company</h4>
              <a href="#">About</a>
              <a href="#">Students</a>
              <a href="#">Contact</a>
            </div>
            <div className="foot-col">
              <h4>Legal</h4>
              <a href="#">Privacy</a>
              <a href="#">Terms</a>
            </div>
          </div>
        </div>
        <div className="foot-bottom">
          <span>© 2026 Circles</span>
          <span>Made for late-night study sessions ☕</span>
        </div>
      </footer>
    </>
  );
}
