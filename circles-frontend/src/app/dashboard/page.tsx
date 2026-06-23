"use client";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/AuthContext";
import { circlesApi, Circle } from "@/lib/api";
import { Sidebar } from "@/components/Sidebar";
import { MiniViz } from "@/components/MiniViz";
import { circleColor, initials } from "@/lib/circleStyle";

export default function DashboardPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  const [circles, setCircles] = useState<Circle[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");

  const [showCreate, setShowCreate] = useState(false);
  const [showJoin, setShowJoin] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.push("/login");
  }, [user, loading, router]);

  useEffect(() => {
    if (user) {
      circlesApi.list().then(setCircles).catch((e) => setError(e.message));
    }
  }, [user]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return circles;
    return circles.filter(
      (c) => c.name.toLowerCase().includes(q) || (c.description || "").toLowerCase().includes(q)
    );
  }, [circles, query]);

  async function handleCreate() {
    if (!newName.trim()) return;
    setBusy(true);
    setError("");
    try {
      const circle = await circlesApi.create(newName.trim(), newDesc.trim() || undefined);
      setCircles([circle, ...circles]);
      setShowCreate(false);
      setNewName("");
      setNewDesc("");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleJoin() {
    if (!inviteCode.trim()) return;
    setBusy(true);
    setError("");
    try {
      const circle = await circlesApi.join(inviteCode.trim().toUpperCase());
      setCircles([circle, ...circles.filter((c) => c.id !== circle.id)]);
      setShowJoin(false);
      setInviteCode("");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (loading || !user) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh" }}>
        Loading…
      </div>
    );
  }

  const firstName = (user.displayName || "there").split(" ")[0];

  return (
    <div className="app">
      <Sidebar user={user} circles={circles} />

      <main className="main">
        <div className="topbar">
          <div className="crumbs">
            <b>Home</b>
          </div>
          <div className="search">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="7" />
              <path d="M21 21l-4-4" />
            </svg>
            <input
              placeholder="Search your circles…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
        </div>

        <div className="hero">
          <svg className="hero-rings" viewBox="0 0 200 200">
            <circle cx="80" cy="80" r="55" fill="#FF5A47" opacity=".5" style={{ mixBlendMode: "screen" }} />
            <circle cx="120" cy="80" r="55" fill="#3F3AE6" opacity=".5" style={{ mixBlendMode: "screen" }} />
            <circle cx="100" cy="120" r="55" fill="#0CB78D" opacity=".5" style={{ mixBlendMode: "screen" }} />
          </svg>
          <div className="hero-l">
            <h1>Welcome back, {firstName}.</h1>
            <p>
              Pool your group&apos;s notes into one verified set, then quiz each other live. Start a new
              circle or join one with a code.
            </p>
            <div className="hero-actions">
              <button
                className="btn btn-primary"
                onClick={() => {
                  setError("");
                  setShowCreate(true);
                }}
              >
                New circle
              </button>
              <button
                className="btn btn-ghost"
                style={{ background: "rgba(255,255,255,.1)", color: "#fff", borderColor: "rgba(255,255,255,.2)" }}
                onClick={() => {
                  setError("");
                  setShowJoin(true);
                }}
              >
                Join with a code
              </button>
            </div>
          </div>
        </div>

        {error && <div className="auth-error">{error}</div>}

        <div className="section-head">
          <h2>Your circles</h2>
        </div>

        {filtered.length === 0 ? (
          <div className="empty">
            {circles.length === 0 ? (
              <>
                <h3>No circles yet</h3>
                <p>Create one or join your group with an invite code.</p>
                <div style={{ display: "flex", gap: 8, justifyContent: "center" }}>
                  <button className="btn btn-primary btn-sm" onClick={() => setShowCreate(true)}>
                    New circle
                  </button>
                  <button className="btn btn-ghost btn-sm" onClick={() => setShowJoin(true)}>
                    Join
                  </button>
                </div>
              </>
            ) : (
              <>
                <h3>No matches</h3>
                <p>No circles match &ldquo;{query}&rdquo;.</p>
              </>
            )}
          </div>
        ) : (
          <div className="grid">
            {filtered.map((c) => {
              const memberCount = c.members?.length ?? 1;
              return (
                <div key={c.id} className="card ccard" onClick={() => router.push(`/circles/${c.id}`)}>
                  <div className="ccard-top">
                    <div className="ccard-badge" style={{ background: circleColor(c.id) }}>
                      {initials(c.name)}
                    </div>
                    <div>
                      <h3>{c.name}</h3>
                      <span className="ccard-sub">
                        {memberCount} member{memberCount === 1 ? "" : "s"}
                      </span>
                    </div>
                  </div>
                  <MiniViz />
                  {c.description && (
                    <p className="sub" style={{ fontSize: 13.5, margin: "0 0 12px" }}>
                      {c.description}
                    </p>
                  )}
                  <div className="ccard-foot">
                    <span className="chip chip-line">code {c.invite_code}</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>

      {showCreate && (
        <div className="modal-overlay" onClick={() => setShowCreate(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Create a circle</h3>
            <div className="field">
              <input
                className="tinp"
                placeholder="Circle name"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                autoFocus
              />
            </div>
            <div className="field">
              <input
                className="tinp"
                placeholder="Description (optional)"
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
              />
            </div>
            <div className="modal-actions">
              <button className="btn btn-ghost btn-sm" onClick={() => setShowCreate(false)}>
                Cancel
              </button>
              <button className="btn btn-primary btn-sm" onClick={handleCreate} disabled={busy || !newName.trim()}>
                {busy ? "Creating…" : "Create"}
              </button>
            </div>
          </div>
        </div>
      )}

      {showJoin && (
        <div className="modal-overlay" onClick={() => setShowJoin(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Join a circle</h3>
            <div className="field">
              <input
                className="tinp"
                placeholder="Invite code"
                value={inviteCode}
                onChange={(e) => setInviteCode(e.target.value.toUpperCase())}
                style={{ textTransform: "uppercase", letterSpacing: ".1em" }}
                autoFocus
              />
            </div>
            <div className="modal-actions">
              <button className="btn btn-ghost btn-sm" onClick={() => setShowJoin(false)}>
                Cancel
              </button>
              <button className="btn btn-primary btn-sm" onClick={handleJoin} disabled={busy || !inviteCode.trim()}>
                {busy ? "Joining…" : "Join"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
