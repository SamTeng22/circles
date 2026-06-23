"use client";
import { useState, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { useAuth } from "@/lib/AuthContext";
import { signInWithGoogle, signUpWithEmail } from "@/lib/firebase";
import { circlesApi } from "@/lib/api";
import { BrandGlyphLight } from "@/components/BrandGlyph";

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48">
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3c-1.6 4.7-6.1 8-11.3 8-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.6 4.1 29.6 2 24 2 11.8 2 2 11.8 2 24s9.8 22 22 22 22-9.8 22-22c0-1.3-.1-2.3-.4-3.5z" />
      <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.6 4.1 29.6 2 24 2 16.3 2 9.7 6.3 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 46c5.5 0 10.5-2.1 14.3-5.6l-6.6-5.6C29.6 36.4 26.9 37.5 24 37.5c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.6 41.6 16.2 46 24 46z" />
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4 5.6l6.6 5.6C41.4 36 44 30.5 44 24c0-1.3-.1-2.3-.4-3.5z" />
    </svg>
  );
}

const pwMeta = [
  { pct: 0, col: "", txt: "Use 8+ characters with a number or symbol." },
  { pct: 30, col: "#FF5A47", txt: "Weak — add more characters." },
  { pct: 55, col: "#F5A524", txt: "Getting there — add a number." },
  { pct: 80, col: "#3F3AE6", txt: "Good password." },
  { pct: 100, col: "#0CB78D", txt: "Strong password 💪" },
];

function scorePassword(v: string) {
  let s = 0;
  if (v.length >= 8) s++;
  if (/[A-Z]/.test(v)) s++;
  if (/[0-9]/.test(v)) s++;
  if (/[^A-Za-z0-9]/.test(v)) s++;
  return s;
}

function getAuthError(code: string): string {
  switch (code) {
    case "auth/email-already-in-use":
      return "An account with this email already exists. Try logging in.";
    case "auth/invalid-email":
      return "Please enter a valid email address.";
    case "auth/weak-password":
      return "Password is too weak. Use at least 6 characters.";
    case "auth/too-many-requests":
      return "Too many attempts. Try again later.";
    case "auth/network-request-failed":
      return "Network error. Check your connection.";
    default:
      return "Something went wrong. Please try again.";
  }
}

function SignupForm() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const prefilledCode = searchParams.get("code") ?? "";

  const [segMode, setSegMode] = useState<"start" | "join">(prefilledCode ? "join" : "start");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState(prefilledCode.toUpperCase());
  const [password, setPassword] = useState("");
  const [pwScore, setPwScore] = useState(0);
  const [showPw, setShowPw] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!loading && user) router.push("/dashboard");
  }, [user, loading, router]);

  async function handleGoogle() {
    setError("");
    setBusy(true);
    try {
      await signInWithGoogle();
      if (segMode === "join" && code.trim()) {
        await circlesApi.join(code.trim());
      }
      router.push("/dashboard");
    } catch (e: any) {
      if (e?.code !== "auth/popup-closed-by-user") {
        setError(getAuthError(e?.code ?? ""));
      }
    } finally {
      setBusy(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!name.trim()) { setError("Please enter your full name."); return; }
    if (segMode === "join" && !code.trim()) { setError("Please enter your circle code."); return; }
    setBusy(true);
    try {
      await signUpWithEmail(email, password, name.trim());
      if (segMode === "join" && code.trim()) {
        await circlesApi.join(code.trim()).catch(() => {
          // Non-fatal: user created, circle join failed (bad code)
          setError("Account created, but the circle code wasn't recognised. You can join from your dashboard.");
        });
      }
      router.push("/dashboard");
    } catch (e: any) {
      setError(getAuthError(e?.code ?? ""));
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh" }}>
        Loading…
      </div>
    );
  }

  const pw = pwMeta[pwScore];

  return (
    <div className="auth">
      {/* LEFT ASIDE */}
      <aside className="auth-aside">
        <div className="stage-grid" />
        <svg className="auth-aside-rings" viewBox="0 0 200 200">
          <circle cx="80" cy="80" r="55" fill="#FF5A47" opacity=".5" style={{ mixBlendMode: "screen" }} />
          <circle cx="120" cy="80" r="55" fill="#3F3AE6" opacity=".5" style={{ mixBlendMode: "screen" }} />
          <circle cx="100" cy="120" r="55" fill="#0CB78D" opacity=".5" style={{ mixBlendMode: "screen" }} />
        </svg>
        <a className="auth-brand" href="/">
          <BrandGlyphLight />
          <span className="brand-name">Circ<b style={{ color: "var(--persimmon)" }}>l</b>es</span>
        </a>
        <div className="auth-aside-body">
          <h2>One account.<br />Every study group you're in.</h2>
          <p>Create a circle for each class, pool notes with your group, and never study from one person's half-finished notes again.</p>
          <div className="auth-quote">
            <p>"Set up our first circle in a minute, uploaded notes, and had a live quiz running before our study session even started."</p>
            <div className="by">
              <span className="av" style={{ background: "var(--violet)" }}>DG</span>
              <div>
                <div style={{ fontSize: "13px", fontWeight: 600 }}>Diego G.</div>
                <small>Organic Chem circle</small>
              </div>
            </div>
          </div>
        </div>
        <div style={{ position: "relative", zIndex: 2, fontFamily: "var(--font-mono), ui-monospace, monospace", fontSize: "11.5px", color: "rgba(255,255,255,.45)" }}>
          © 2026 Circles
        </div>
      </aside>

      {/* RIGHT MAIN */}
      <main className="auth-main">
        <div className="auth-card">
          <a className="back" href="/">← Back home</a>
          <h1>Create your account</h1>
          <p className="lead">Free for students. No card required.</p>

          {/* SEGMENT TOGGLE */}
          <div className="seg">
            <button className={segMode === "start" ? "on" : ""} onClick={() => setSegMode("start")}>
              Start a circle
            </button>
            <button className={segMode === "join" ? "on" : ""} onClick={() => setSegMode("join")}>
              Join with a code
            </button>
          </div>

          {error && <div className="auth-error">{error}</div>}

          <div className="oauth">
            <button className="oauth-btn" onClick={handleGoogle} disabled={busy}>
              <GoogleIcon /> Sign up with Google
            </button>
          </div>

          <div className="divider">or with email</div>

          <form onSubmit={handleSubmit}>
            <div className="field">
              <label>Full name</label>
              <div className="inp">
                <input
                  type="text"
                  placeholder="Sam Teng"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </div>
            </div>

            <div className="field">
              <label>School email</label>
              <div className="inp">
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="3" y="5" width="18" height="14" rx="2" /><path d="M3 7l9 6 9-6" />
                </svg>
                <input
                  type="email"
                  placeholder="you@university.edu"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>
            </div>

            {segMode === "join" && (
              <div className="field">
                <label>Circle code</label>
                <div className="inp">
                  <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="9" cy="9" r="5" /><circle cx="15" cy="15" r="5" />
                  </svg>
                  <input
                    type="text"
                    placeholder="BIO·742"
                    maxLength={7}
                    value={code}
                    onChange={(e) => setCode(e.target.value.toUpperCase())}
                    style={{ textTransform: "uppercase", letterSpacing: ".1em", fontFamily: "var(--font-mono), ui-monospace, monospace" }}
                  />
                </div>
                <div className="pw-hint">Ask your group for the 6-character code on their circle.</div>
              </div>
            )}

            <div className="field">
              <label>Password</label>
              <div className="inp">
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="4" y="11" width="16" height="9" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" />
                </svg>
                <input
                  type={showPw ? "text" : "password"}
                  placeholder="At least 8 characters"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    setPwScore(scorePassword(e.target.value));
                  }}
                  required
                />
                <span className="toggle" onClick={() => setShowPw(!showPw)}>
                  {showPw ? "HIDE" : "SHOW"}
                </span>
              </div>
              <div className="meter-pw">
                <i style={{ width: pw.pct + "%", background: pw.col }} />
              </div>
              <div className="pw-hint">{pw.txt}</div>
            </div>

            <button type="submit" className="btn btn-primary btn-block btn-lg" style={{ marginTop: "6px" }} disabled={busy}>
              {busy ? "Creating account…" : "Create account"}
            </button>
          </form>

          <p className="legal">
            By creating an account you agree to our <a href="#">Terms</a> and <a href="#">Privacy Policy</a>.
          </p>
          <p className="auth-foot">
            Already have an account? <a href="/login">Log in</a>
          </p>
        </div>
      </main>
    </div>
  );
}

export default function SignupPage() {
  return (
    <Suspense>
      <SignupForm />
    </Suspense>
  );
}
