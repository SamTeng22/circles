"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/AuthContext";
import { signInWithGoogle, signInWithEmail, resetPassword } from "@/lib/firebase";
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

function getAuthError(code: string): string {
  switch (code) {
    case "auth/user-not-found":
    case "auth/wrong-password":
    case "auth/invalid-credential":
      return "Incorrect email or password.";
    case "auth/invalid-email":
      return "Please enter a valid email address.";
    case "auth/too-many-requests":
      return "Too many attempts. Try again later.";
    case "auth/network-request-failed":
      return "Network error. Check your connection.";
    default:
      return "Something went wrong. Please try again.";
  }
}

export default function LoginPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "forgot">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [remember, setRemember] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    if (!loading && user) router.push("/dashboard");
  }, [user, loading, router]);

  async function handleGoogle() {
    setError("");
    setBusy(true);
    try {
      await signInWithGoogle();
      router.push("/dashboard");
    } catch (e: any) {
      if (e?.code !== "auth/popup-closed-by-user") {
        setError(getAuthError(e?.code ?? ""));
      }
    } finally {
      setBusy(false);
    }
  }

  async function handleEmailLogin(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await signInWithEmail(email, password);
      router.push("/dashboard");
    } catch (e: any) {
      setError(getAuthError(e?.code ?? ""));
    } finally {
      setBusy(false);
    }
  }

  async function handleForgot(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSuccess("");
    setBusy(true);
    try {
      await resetPassword(email);
      setSuccess("Check your inbox — we sent a reset link.");
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
          <h2>Welcome back to your circles.</h2>
          <p>Pick up where your group left off — verified notes, fresh quizzes, and whoever's online for a live round.</p>
          <div className="auth-quote">
            <p>"We stopped arguing over whose notes were right. Circles just shows us the split and we move on."</p>
            <div className="by">
              <span className="av">MA</span>
              <div>
                <div style={{ fontSize: "13px", fontWeight: 600 }}>Maya A.</div>
                <small>Cell Biology circle</small>
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

          {mode === "login" ? (
            <>
              <h1>Log in</h1>
              <p className="lead">Welcome back. Let's get you to your circles.</p>

              {error && <div className="auth-error">{error}</div>}

              <div className="oauth">
                <button className="oauth-btn" onClick={handleGoogle} disabled={busy}>
                  <GoogleIcon /> Continue with Google
                </button>
              </div>

              <div className="divider">or with email</div>

              <form onSubmit={handleEmailLogin}>
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
                <div className="field">
                  <label>Password</label>
                  <div className="inp">
                    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <rect x="4" y="11" width="16" height="9" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" />
                    </svg>
                    <input
                      type={showPw ? "text" : "password"}
                      placeholder="••••••••"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                    />
                    <span className="toggle" onClick={() => setShowPw(!showPw)}>
                      {showPw ? "HIDE" : "SHOW"}
                    </span>
                  </div>
                </div>

                <div className="row-between">
                  <label className="check">
                    <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
                    Keep me logged in
                  </label>
                  <span className="link-ps" onClick={() => { setMode("forgot"); setError(""); setSuccess(""); }}>
                    Forgot password?
                  </span>
                </div>

                <button type="submit" className="btn btn-primary btn-block btn-lg" disabled={busy}>
                  {busy ? "Logging in…" : "Log in"}
                </button>
              </form>

              <p className="auth-foot">
                New to Circles? <a href="/signup">Create an account</a>
              </p>
            </>
          ) : (
            <>
              <h1>Reset password</h1>
              <p className="lead">Enter your email and we'll send you a link.</p>

              {error && <div className="auth-error">{error}</div>}
              {success && <div className="auth-success">{success}</div>}

              {!success && (
                <form onSubmit={handleForgot}>
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
                  <button type="submit" className="btn btn-primary btn-block btn-lg" disabled={busy}>
                    {busy ? "Sending…" : "Send reset link"}
                  </button>
                </form>
              )}

              <p className="auth-foot">
                <a onClick={() => { setMode("login"); setError(""); setSuccess(""); }}>← Back to log in</a>
              </p>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
