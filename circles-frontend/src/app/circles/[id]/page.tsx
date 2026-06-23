"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/AuthContext";
import { circlesApi, notesApi, quizApi, Circle, Note, Quiz } from "@/lib/api";
import { Sidebar } from "@/components/Sidebar";
import { circleColor, initials } from "@/lib/circleStyle";
import { timeAgo } from "@/lib/format";

type Tab = "consensus" | "notes" | "quizzes" | "flashcards";

// Fixed cluster positions for the decorative consensus lens (overlapping blobs).
const LENS_POS = [
  { x: 38, y: 34, r: 130 },
  { x: 62, y: 36, r: 132 },
  { x: 50, y: 60, r: 128 },
  { x: 36, y: 58, r: 116 },
  { x: 64, y: 58, r: 116 },
];

export default function CircleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user, loading } = useAuth();
  const router = useRouter();

  const [allCircles, setAllCircles] = useState<Circle[]>([]);
  const [circle, setCircle] = useState<Circle | null>(null);
  const [notes, setNotes] = useState<Note[]>([]);
  const [quizzes, setQuizzes] = useState<Quiz[]>([]);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [tab, setTab] = useState<Tab>("notes");

  // Notes upload
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");

  // Quiz generation
  const [showGen, setShowGen] = useState(false);
  const [genTitle, setGenTitle] = useState("");
  const [genTopic, setGenTopic] = useState("");
  const [genNum, setGenNum] = useState(5);
  const [genBusy, setGenBusy] = useState(false);
  const [genError, setGenError] = useState("");

  const [copied, setCopied] = useState(false);

  // Deleting notes
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [noteToDelete, setNoteToDelete] = useState<Note | null>(null);

  useEffect(() => {
    if (!loading && !user) router.push("/login");
  }, [user, loading, router]);

  useEffect(() => {
    if (!user || !id) return;
    let cancelled = false;
    setPageLoading(true);
    setLoadError("");
    Promise.all([
      circlesApi.get(id),
      notesApi.list(id),
      quizApi.list(id),
      circlesApi.list(),
    ])
      .then(([c, n, q, all]) => {
        if (cancelled) return;
        setCircle(c);
        setNotes(n);
        setQuizzes(q);
        setAllCircles(all);
      })
      .catch((e: any) => {
        if (!cancelled) setLoadError(e.message || "Failed to load this circle.");
      })
      .finally(() => {
        if (!cancelled) setPageLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user, id]);

  // While any note is still processing, poll the list until it settles.
  useEffect(() => {
    if (!notes.some((n) => n.status === "processing")) return;
    const t = setInterval(() => {
      notesApi.list(id).then(setNotes).catch(() => {});
    }, 3000);
    return () => clearInterval(t);
  }, [notes, id]);

  const members = circle?.members ?? [];

  // Resolve the current user's DB id (members carry it, Firebase only gives email).
  const myId = useMemo(
    () => members.find((m) => m.email === user?.email)?.id ?? null,
    [members, user?.email]
  );

  function canDelete(n: Note) {
    return myId != null && (n.user_id === myId || circle?.owner_id === myId);
  }

  async function confirmDelete() {
    const n = noteToDelete;
    if (!n || deletingId) return;
    setDeletingId(n.id);
    try {
      await notesApi.delete(id, n.id);
      setNotes((prev) => prev.filter((x) => x.id !== n.id));
      setNoteToDelete(null);
    } catch (e: any) {
      setUploadError(e.message || "Failed to delete note.");
    } finally {
      setDeletingId(null);
    }
  }

  async function refreshNotes() {
    try {
      setNotes(await notesApi.list(id));
    } catch {
      /* keep existing list on refresh failure */
    }
  }

  async function openNoteFile(noteId: string) {
    try {
      const { url } = await notesApi.fileUrl(noteId);
      window.open(url, "_blank", "noopener");
    } catch {
      /* file may not exist for older text-only notes */
    }
  }

  async function uploadFile(file: File) {
    setUploadError("");
    setUploading(true);
    try {
      await notesApi.upload(id, file);
      await refreshNotes();
    } catch (e: any) {
      setUploadError(e.message || "Upload failed.");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) uploadFile(file);
  }

  async function handleGenerate() {
    if (!genTitle.trim()) return;
    setGenBusy(true);
    setGenError("");
    try {
      const quiz = await quizApi.generate(id, genTitle.trim(), genTopic.trim() || undefined, genNum);
      setQuizzes([quiz, ...quizzes]);
      setShowGen(false);
      setGenTitle("");
      setGenTopic("");
      setGenNum(5);
    } catch (e: any) {
      setGenError(e.message || "Generation failed.");
    } finally {
      setGenBusy(false);
    }
  }

  function copyCode() {
    if (!circle) return;
    navigator.clipboard?.writeText(circle.invite_code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  function startLiveQuiz() {
    if (quizzes.length > 0) router.push(`/quiz/${quizzes[0].id}/live`);
    else setTab("quizzes");
  }

  if (loading || !user || pageLoading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh" }}>
        Loading…
      </div>
    );
  }

  if (loadError || !circle) {
    return (
      <div className="app">
        <Sidebar user={user} circles={allCircles} activeCircleId={id} />
        <main className="main">
          <div className="empty">
            <h3>Circle not available</h3>
            <p>{loadError || "This circle doesn't exist or you're not a member."}</p>
            <button className="btn btn-primary btn-sm" onClick={() => router.push("/dashboard")}>
              Back to dashboard
            </button>
          </div>
        </main>
      </div>
    );
  }

  const badgeColor = circleColor(circle.id);

  return (
    <div className="app">
      <Sidebar user={user} circles={allCircles} activeCircleId={id} />

      <main className="main">
        <div className="topbar">
          <div className="crumbs">
            <span style={{ cursor: "pointer" }} onClick={() => router.push("/dashboard")}>
              Circles
            </span>{" "}
            / <b>{circle.name}</b>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={() => router.push("/dashboard")}>
            ← Back
          </button>
        </div>

        {/* Header */}
        <div className="circ-head">
          <div className="circ-title">
            <div className="circ-badge" style={{ background: badgeColor }}>
              {initials(circle.name)}
            </div>
            <div>
              <h1>{circle.name}</h1>
              <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                <div className="stack">
                  {members.slice(0, 5).map((m) => (
                    <span key={m.id} className="av" style={{ background: circleColor(m.id) }} title={m.display_name}>
                      {initials(m.display_name)}
                    </span>
                  ))}
                  {members.length > 5 && <span className="av more">+{members.length - 5}</span>}
                </div>
                <span className="sub" style={{ fontSize: 13 }}>
                  {members.length} member{members.length === 1 ? "" : "s"}
                </span>
              </div>
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 10 }}>
            <div className="join-code" onClick={copyCode} title="Click to copy">
              {copied ? "copied!" : (
                <>
                  join code <b>{circle.invite_code}</b>
                </>
              )}
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn btn-ghost btn-sm" onClick={() => setTab("notes")}>
                Upload notes
              </button>
              <button className="btn btn-primary btn-sm" onClick={startLiveQuiz}>
                Start live quiz
              </button>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="tabs">
          <button className={`tab${tab === "consensus" ? " active" : ""}`} onClick={() => setTab("consensus")}>
            Consensus
          </button>
          <button className={`tab${tab === "notes" ? " active" : ""}`} onClick={() => setTab("notes")}>
            Notes · {notes.length}
          </button>
          <button className={`tab${tab === "quizzes" ? " active" : ""}`} onClick={() => setTab("quizzes")}>
            Quizzes · {quizzes.length}
          </button>
          <button className={`tab${tab === "flashcards" ? " active" : ""}`} onClick={() => setTab("flashcards")}>
            Flashcards
          </button>
        </div>

        {/* Consensus (placeholder) */}
        {tab === "consensus" && (
          <div className="consensus">
            <div>
              <div className="lens-wrap">
                <div className="lens">
                  {members.slice(0, 5).map((m, i) => {
                    const pos = LENS_POS[i];
                    return (
                      <div
                        key={m.id}
                        className="blob"
                        style={{ width: pos.r, height: pos.r, background: circleColor(m.id), left: `${pos.x}%`, top: `${pos.y}%` }}
                      />
                    );
                  })}
                  <div className="lens-core">
                    <div>
                      <b>—</b>
                      <span>not computed</span>
                    </div>
                  </div>
                </div>
                <div className="lens-legend">
                  {members.map((m) => (
                    <span key={m.id}>
                      <span className="dot" style={{ background: circleColor(m.id) }} /> {m.display_name}
                    </span>
                  ))}
                </div>
              </div>
              <p className="sub" style={{ fontSize: 13, marginTop: 12, padding: "0 4px" }}>
                Each circle is one member&apos;s notes. Where they overlap, the group agrees — that
                dense centre would become your verified set.
              </p>
            </div>
            <div className="panel">
              <div className="panel-h">
                <h3>Disagreements &amp; gaps</h3>
                <span className="chip chip-line">soon</span>
              </div>
              <div className="panel-b">
                <p>
                  The consensus engine isn&apos;t available yet. Once uploaded notes are compared,
                  this is where agreements, conflicts (with the majority answer kept), and gaps
                  nobody covered will appear.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Notes (real) */}
        {tab === "notes" && (
          <div>
            <input
              ref={fileRef}
              type="file"
              accept=".txt,.md,.pdf,image/*,application/pdf,text/plain,text/markdown"
              style={{ display: "none" }}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) uploadFile(file);
              }}
            />
            <div
              className={`dropzone${dragging ? " drag" : ""}`}
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
            >
              <div className="dz-ico">📄</div>
              <h3>Drop your notes to pool them</h3>
              <p className="sub" style={{ fontSize: 13.5, margin: "0 0 16px" }}>
                PDF, images, or text (.txt, .md). We extract the text and embed it for quiz
                generation.
              </p>
              <button className="btn btn-dark btn-sm" onClick={() => fileRef.current?.click()} disabled={uploading}>
                {uploading ? "Uploading…" : "Upload notes"}
              </button>
              {uploadError && (
                <div className="auth-error" style={{ marginTop: 16 }}>
                  {uploadError}
                </div>
              )}
            </div>

            <div className="section-head">
              <h2 style={{ fontSize: 17 }}>Pooled notes</h2>
            </div>
            {notes.length === 0 ? (
              <div className="empty">
                <h3>No notes yet</h3>
                <p>Upload the first set of notes to get started.</p>
              </div>
            ) : (
              <div className="grid">
                {notes.map((n) => (
                  <div key={n.id} className="card note-card">
                    <span className="eyebrow">
                      {n.uploader_name} · {timeAgo(n.created_at)}
                    </span>
                    <h3>
                      {n.s3_key ? (
                        <span className="note-link" onClick={() => openNoteFile(n.id)} title="Open original">
                          {n.filename}
                        </span>
                      ) : (
                        n.filename
                      )}
                    </h3>
                    <div
                      className="ccard-foot"
                      style={{ marginTop: 10, display: "flex", alignItems: "center", justifyContent: "space-between" }}
                    >
                      <span>
                        {n.status === "processing" && <span className="chip chip-cobalt">processing…</span>}
                        {n.status === "ready" && <span className="chip chip-jade">ready</span>}
                        {n.status === "failed" && (
                          <span className="chip chip-flag" title={n.error ?? "Extraction failed"}>
                            failed
                          </span>
                        )}
                      </span>
                      {canDelete(n) && (
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={() => setNoteToDelete(n)}
                          disabled={deletingId === n.id}
                          title="Delete note"
                        >
                          {deletingId === n.id ? "Deleting…" : "Delete"}
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Quizzes (real) */}
        {tab === "quizzes" && (
          <div>
            <div className="section-head">
              <h2 style={{ fontSize: 17 }}>Quizzes</h2>
              <button className="btn btn-primary btn-sm" onClick={() => setShowGen(true)}>
                Generate quiz
              </button>
            </div>
            {quizzes.length === 0 ? (
              <div className="empty">
                <h3>No quizzes yet</h3>
                <p>Generate one from this circle&apos;s notes.</p>
                <button className="btn btn-primary btn-sm" onClick={() => setShowGen(true)}>
                  Generate quiz
                </button>
              </div>
            ) : (
              <div className="grid">
                {quizzes.map((q) => (
                  <div key={q.id} className="card quiz-card">
                    <span className="eyebrow">Generated · ready</span>
                    <h3>{q.title}</h3>
                    <p className="sub" style={{ fontSize: 13.5 }}>
                      {q.questions.length} question{q.questions.length === 1 ? "" : "s"}
                    </p>
                    <div className="quiz-actions">
                      <button
                        className="btn btn-ghost btn-sm"
                        style={{ flex: 1 }}
                        onClick={() => router.push(`/quiz/${q.id}/solo`)}
                      >
                        Solo practice
                      </button>
                      <button
                        className="btn btn-primary btn-sm"
                        style={{ flex: 1 }}
                        onClick={() => router.push(`/quiz/${q.id}/live`)}
                      >
                        Run live
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Flashcards (placeholder) */}
        {tab === "flashcards" && (
          <div className="placeholder">
            <div className="ph-ico">🃏</div>
            <h3>Flashcards are coming soon</h3>
            <p>
              Once flashcard generation is built, decks created from this circle&apos;s verified
              notes will live here.
            </p>
          </div>
        )}
      </main>

      {/* Generate quiz modal */}
      {showGen && (
        <div className="modal-overlay" onClick={() => !genBusy && setShowGen(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Generate a quiz</h3>
            {genError && <div className="auth-error">{genError}</div>}
            <div className="field">
              <input
                className="tinp"
                placeholder="Quiz title"
                value={genTitle}
                onChange={(e) => setGenTitle(e.target.value)}
                autoFocus
              />
            </div>
            <div className="field">
              <input
                className="tinp"
                placeholder="Topic to focus on (optional)"
                value={genTopic}
                onChange={(e) => setGenTopic(e.target.value)}
              />
            </div>
            <div className="field">
              <input
                className="tinp"
                type="number"
                min={1}
                max={20}
                value={genNum}
                onChange={(e) => setGenNum(Math.max(1, Math.min(20, Number(e.target.value) || 1)))}
              />
              <p className="sub" style={{ fontSize: 12, margin: "6px 0 0" }}>Number of questions (1–20)</p>
            </div>
            <div className="modal-actions">
              <button className="btn btn-ghost btn-sm" onClick={() => setShowGen(false)} disabled={genBusy}>
                Cancel
              </button>
              <button className="btn btn-primary btn-sm" onClick={handleGenerate} disabled={genBusy || !genTitle.trim()}>
                {genBusy ? "Generating…" : "Generate"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete note confirmation modal */}
      {noteToDelete && (
        <div className="modal-overlay" onClick={() => !deletingId && setNoteToDelete(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Delete note</h3>
            <p className="sub" style={{ fontSize: 13.5, margin: "0 0 4px" }}>
              Delete <b>{noteToDelete.filename}</b> from the pool? This removes its text and
              embeddings and can&apos;t be undone.
            </p>
            <div className="modal-actions">
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => setNoteToDelete(null)}
                disabled={!!deletingId}
              >
                Cancel
              </button>
              <button className="btn btn-dark btn-sm" onClick={confirmDelete} disabled={!!deletingId}>
                {deletingId ? "Deleting…" : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
