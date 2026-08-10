"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/AuthContext";
import { circlesApi, notesApi, quizApi, flashcardsApi, Circle, Note, Quiz, FlashcardDeck } from "@/lib/api";
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
  const [decks, setDecks] = useState<FlashcardDeck[]>([]);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [tab, setTab] = useState<Tab>("notes");

  // Notes upload
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");

  // Quiz / flashcard generation (one modal, switched by genMode)
  const [genMode, setGenMode] = useState<"quiz" | "flashcards">("quiz");
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

  // Circle management (settings surface)
  const [showSettings, setShowSettings] = useState(false);
  const [settingsError, setSettingsError] = useState("");
  const [renaming, setRenaming] = useState(false);
  const [nameInput, setNameInput] = useState("");
  const [savingName, setSavingName] = useState(false);
  const [regenNotice, setRegenNotice] = useState(false); // highlights the freshly issued code
  // Confirmation flows (each destructive action requires an explicit confirm step)
  const [confirmLeave, setConfirmLeave] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const [confirmRegen, setConfirmRegen] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [memberToRemove, setMemberToRemove] = useState<{ id: string; display_name: string; email: string } | null>(null);
  const [removingMemberId, setRemovingMemberId] = useState<string | null>(null);
  const [confirmDeleteCircle, setConfirmDeleteCircle] = useState(false);
  const [deletingCircle, setDeletingCircle] = useState(false);

  // Viewing / editing a note's extracted text
  const [viewNote, setViewNote] = useState<Note | null>(null);
  const [viewLoading, setViewLoading] = useState(false);
  const [viewError, setViewError] = useState("");
  const [editing, setEditing] = useState(false);
  const [editContent, setEditContent] = useState("");
  const [savingContent, setSavingContent] = useState(false);

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
      flashcardsApi.list(id),
      circlesApi.list(),
    ])
      .then(([c, n, q, d, all]) => {
        if (cancelled) return;
        setCircle(c);
        setNotes(n);
        setQuizzes(q);
        setDecks(d);
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

  const isOwner = myId != null && circle?.owner_id === myId;

  function canDelete(n: Note) {
    return myId != null && (n.user_id === myId || circle?.owner_id === myId);
  }

  function openSettings() {
    setNameInput(circle?.name ?? "");
    setRenaming(false);
    setRegenNotice(false);
    setSettingsError("");
    setShowSettings(true);
  }

  function closeSettings() {
    // Block closing while an irreversible action is mid-flight.
    if (savingName || leaving || regenerating || removingMemberId || deletingCircle) return;
    setShowSettings(false);
  }

  async function saveName() {
    const name = nameInput.trim();
    if (!circle || savingName) return;
    if (!name || name === circle.name) {
      setRenaming(false);
      return;
    }
    setSavingName(true);
    setSettingsError("");
    try {
      const updated = await circlesApi.rename(circle.id, name);
      setCircle((prev) => (prev ? { ...prev, name: updated.name } : prev));
      setAllCircles((prev) => prev.map((c) => (c.id === circle.id ? { ...c, name: updated.name } : c)));
      setRenaming(false);
    } catch (e: any) {
      setSettingsError(e.message || "Failed to rename circle.");
    } finally {
      setSavingName(false);
    }
  }

  async function doRegenerate() {
    if (!circle || regenerating) return;
    setRegenerating(true);
    setSettingsError("");
    try {
      const updated = await circlesApi.regenerateInvite(circle.id);
      setCircle((prev) => (prev ? { ...prev, invite_code: updated.invite_code } : prev));
      setConfirmRegen(false);
      setRegenNotice(true);
    } catch (e: any) {
      setSettingsError(e.message || "Failed to regenerate invite code.");
    } finally {
      setRegenerating(false);
    }
  }

  async function doRemoveMember() {
    const m = memberToRemove;
    if (!circle || !m || removingMemberId) return;
    setRemovingMemberId(m.id);
    setSettingsError("");
    try {
      await circlesApi.removeMember(circle.id, m.id);
      setCircle((prev) =>
        prev ? { ...prev, members: (prev.members ?? []).filter((x) => x.id !== m.id) } : prev
      );
      setMemberToRemove(null);
    } catch (e: any) {
      setSettingsError(e.message || "Failed to remove member.");
    } finally {
      setRemovingMemberId(null);
    }
  }

  async function doLeave() {
    if (!circle || leaving) return;
    setLeaving(true);
    setSettingsError("");
    try {
      await circlesApi.leave(circle.id);
      // No longer a member — the circle page would 403, so send them home.
      router.push("/dashboard");
    } catch (e: any) {
      setSettingsError(e.message || "Failed to leave circle.");
      setLeaving(false);
    }
  }

  async function doDeleteCircle() {
    if (!circle || deletingCircle) return;
    setDeletingCircle(true);
    setSettingsError("");
    try {
      await circlesApi.delete(circle.id);
      // The circle no longer exists — redirect since this page can't render.
      router.push("/dashboard");
    } catch (e: any) {
      setSettingsError(e.message || "Failed to delete circle.");
      setDeletingCircle(false);
    }
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

  async function openNoteView(note: Note) {
    setViewNote(note);
    setEditing(false);
    setViewError("");
    setEditContent("");
    setViewLoading(true);
    try {
      const full = await notesApi.detail(note.id);
      setViewNote(full);
      setEditContent(full.content ?? "");
    } catch (e: any) {
      setViewError(e.message || "Couldn't load this note's contents.");
    } finally {
      setViewLoading(false);
    }
  }

  function closeNoteView() {
    if (savingContent) return;
    setViewNote(null);
    setEditing(false);
    setViewError("");
    setEditContent("");
  }

  async function saveNoteContent() {
    if (!viewNote || savingContent) return;
    setSavingContent(true);
    setViewError("");
    try {
      await notesApi.updateContent(id, viewNote.id, editContent);
      // Content flips to "processing" while it re-embeds; reflect that locally.
      setNotes((prev) =>
        prev.map((x) =>
          x.id === viewNote.id
            ? { ...x, status: "processing", content: editContent, edited_at: new Date().toISOString() }
            : x
        )
      );
      setViewNote(null);
      setEditing(false);
    } catch (e: any) {
      setViewError(e.message || "Failed to save changes.");
    } finally {
      setSavingContent(false);
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

  function openGen(mode: "quiz" | "flashcards") {
    setGenMode(mode);
    setGenTitle("");
    setGenTopic("");
    setGenNum(mode === "quiz" ? 5 : 10);
    setGenError("");
    setShowGen(true);
  }

  async function handleGenerate() {
    if (!genTitle.trim()) return;
    setGenBusy(true);
    setGenError("");
    try {
      if (genMode === "quiz") {
        const quiz = await quizApi.generate(id, genTitle.trim(), genTopic.trim() || undefined, genNum);
        setQuizzes([quiz, ...quizzes]);
      } else {
        const deck = await flashcardsApi.generate(id, genTitle.trim(), genTopic.trim() || undefined, genNum);
        setDecks([deck, ...decks]);
      }
      setShowGen(false);
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
              <button className="btn btn-ghost btn-sm" onClick={openSettings}>
                Settings
              </button>
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
            Flashcards · {decks.length}
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
                      {n.edited_at && (
                        <> · edited {timeAgo(n.edited_at)}</>
                      )}
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
                      <span style={{ display: "flex", gap: 8 }}>
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={() => openNoteView(n)}
                          disabled={n.status === "processing"}
                          title="See the text the system extracted from this note"
                        >
                          View / Edit
                        </button>
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
                      </span>
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
              <button className="btn btn-primary btn-sm" onClick={() => openGen("quiz")}>
                Generate quiz
              </button>
            </div>
            {quizzes.length === 0 ? (
              <div className="empty">
                <h3>No quizzes yet</h3>
                <p>Generate one from this circle&apos;s notes.</p>
                <button className="btn btn-primary btn-sm" onClick={() => openGen("quiz")}>
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

        {/* Flashcards (real) */}
        {tab === "flashcards" && (
          <div>
            <div className="section-head">
              <h2 style={{ fontSize: 17 }}>Flashcard decks</h2>
              <button className="btn btn-primary btn-sm" onClick={() => openGen("flashcards")}>
                Generate deck
              </button>
            </div>
            {decks.length === 0 ? (
              <div className="empty">
                <h3>No flashcard decks yet</h3>
                <p>Generate a deck from this circle&apos;s pooled notes to study.</p>
                <button className="btn btn-primary btn-sm" onClick={() => openGen("flashcards")}>
                  Generate deck
                </button>
              </div>
            ) : (
              <div className="grid">
                {decks.map((d) => (
                  <div key={d.id} className="card quiz-card">
                    <span className="eyebrow">Generated · {timeAgo(d.created_at)}</span>
                    <h3>{d.title}</h3>
                    <p className="sub" style={{ fontSize: 13.5 }}>
                      {d.cards.length} card{d.cards.length === 1 ? "" : "s"}
                    </p>
                    <div className="quiz-actions">
                      <button
                        className="btn btn-primary btn-sm"
                        style={{ flex: 1 }}
                        onClick={() => router.push(`/flashcards/${d.id}`)}
                      >
                        Study deck
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </main>

      {/* Generate quiz modal */}
      {showGen && (
        <div className="modal-overlay" onClick={() => !genBusy && setShowGen(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>{genMode === "quiz" ? "Generate a quiz" : "Generate a flashcard deck"}</h3>
            {genError && <div className="auth-error">{genError}</div>}
            <div className="field">
              <input
                className="tinp"
                placeholder={genMode === "quiz" ? "Quiz title" : "Deck title"}
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
                max={genMode === "quiz" ? 20 : 30}
                value={genNum}
                onChange={(e) => {
                  const max = genMode === "quiz" ? 20 : 30;
                  setGenNum(Math.max(1, Math.min(max, Number(e.target.value) || 1)));
                }}
              />
              <p className="sub" style={{ fontSize: 12, margin: "6px 0 0" }}>
                {genMode === "quiz" ? "Number of questions (1–20)" : "Number of cards (1–30)"}
              </p>
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

      {/* View / edit note contents modal */}
      {viewNote && (
        <div className="modal-overlay" onClick={closeNoteView}>
          <div
            className="modal"
            style={{ maxWidth: 720, width: "min(720px, 92vw)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ marginBottom: 2 }}>{viewNote.filename}</h3>
            <p className="sub" style={{ fontSize: 12.5, margin: "0 0 12px" }}>
              This is the text the system extracted and uses for quizzes — what the computer
              knows about this note.
            </p>

            {viewError && <div className="auth-error" style={{ marginBottom: 12 }}>{viewError}</div>}

            {viewLoading ? (
              <p className="sub" style={{ fontSize: 13.5 }}>Loading contents…</p>
            ) : editing ? (
              <textarea
                className="tinp"
                style={{ width: "100%", minHeight: 320, resize: "vertical", fontFamily: "inherit", lineHeight: 1.5 }}
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                disabled={savingContent}
              />
            ) : editContent.trim() ? (
              <div
                style={{
                  maxHeight: 420,
                  overflowY: "auto",
                  whiteSpace: "pre-wrap",
                  fontSize: 13.5,
                  lineHeight: 1.55,
                  padding: 14,
                  borderRadius: 10,
                  background: "var(--panel, #f6f6f8)",
                  border: "1px solid rgba(0,0,0,0.08)",
                }}
              >
                {editContent}
              </div>
            ) : (
              <p className="sub" style={{ fontSize: 13.5 }}>
                No extracted text yet
                {viewNote.status === "failed" ? " — extraction failed for this file." : "."}
              </p>
            )}

            <div className="modal-actions">
              {editing ? (
                <>
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() => setEditing(false)}
                    disabled={savingContent}
                  >
                    Cancel
                  </button>
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={saveNoteContent}
                    disabled={savingContent}
                  >
                    {savingContent ? "Saving…" : "Save & re-embed"}
                  </button>
                </>
              ) : (
                <>
                  <button className="btn btn-ghost btn-sm" onClick={closeNoteView}>
                    Close
                  </button>
                  {canDelete(viewNote) && !viewLoading && (
                    <button className="btn btn-primary btn-sm" onClick={() => setEditing(true)}>
                      Edit text
                    </button>
                  )}
                </>
              )}
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

      {/* Circle settings / management modal */}
      {showSettings && circle && (
        <div className="modal-overlay" onClick={closeSettings}>
          <div
            className="modal"
            style={{ maxWidth: 520, width: "min(520px, 92vw)", maxHeight: "88vh", overflowY: "auto" }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3>Circle settings</h3>
            {settingsError && <div className="auth-error">{settingsError}</div>}

            {/* Name */}
            <div className="field">
              <label>Name</label>
              {isOwner && renaming ? (
                <div style={{ display: "flex", gap: 8 }}>
                  <input
                    className="tinp"
                    value={nameInput}
                    onChange={(e) => setNameInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && saveName()}
                    disabled={savingName}
                    autoFocus
                  />
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={saveName}
                    disabled={savingName || !nameInput.trim()}
                  >
                    {savingName ? "Saving…" : "Save"}
                  </button>
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() => {
                      setRenaming(false);
                      setNameInput(circle.name);
                    }}
                    disabled={savingName}
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                  <span style={{ fontWeight: 600 }}>{circle.name}</span>
                  {isOwner && (
                    <button className="btn btn-ghost btn-sm" onClick={() => setRenaming(true)}>
                      Rename
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* Invite code */}
            <div className="field">
              <label>Invite code</label>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                <span className="mono" style={{ fontWeight: 700, letterSpacing: ".12em", fontSize: 15 }}>
                  {circle.invite_code}
                </span>
                {isOwner && (
                  <button className="btn btn-ghost btn-sm" onClick={() => setConfirmRegen(true)}>
                    Regenerate
                  </button>
                )}
              </div>
              {regenNotice && (
                <p className="sub" style={{ fontSize: 12.5, margin: "8px 0 0", color: "var(--jade)" }}>
                  New code issued — the previous one no longer works.
                </p>
              )}
            </div>

            {/* Members (owner only) */}
            {isOwner && (
              <div className="field">
                <label>Members · {members.length}</label>
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {members.map((m) => (
                    <div
                      key={m.id}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 10,
                        padding: "8px 10px",
                        borderRadius: 12,
                        border: "1px solid var(--line)",
                        background: "var(--paper)",
                      }}
                    >
                      <span
                        className="av"
                        style={{
                          width: 30,
                          height: 30,
                          borderRadius: "50%",
                          display: "grid",
                          placeItems: "center",
                          fontSize: 11,
                          fontWeight: 700,
                          color: "#fff",
                          fontFamily: "var(--font-mono), ui-monospace, monospace",
                          flex: "none",
                          background: circleColor(m.id),
                        }}
                      >
                        {initials(m.display_name)}
                      </span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontWeight: 600, fontSize: 14, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                          {m.display_name}
                          {m.id === circle.owner_id && (
                            <span className="mono" style={{ fontSize: 10.5, color: "var(--ink-3)", marginLeft: 8, letterSpacing: ".1em" }}>
                              OWNER
                            </span>
                          )}
                        </div>
                        <small className="mono" style={{ fontSize: 11, color: "var(--ink-3)" }}>{m.email}</small>
                      </div>
                      {m.id !== circle.owner_id && (
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={() => setMemberToRemove(m)}
                          disabled={removingMemberId === m.id}
                        >
                          {removingMemberId === m.id ? "Removing…" : "Remove"}
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Danger zone */}
            <div style={{ marginTop: 18, borderTop: "1px solid var(--line)", paddingTop: 16 }}>
              <div className="eyebrow">Danger zone</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 12 }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontWeight: 600, fontSize: 14 }}>Leave circle</div>
                    <small className="sub" style={{ fontSize: 12.5 }}>
                      You&apos;ll lose access to this circle&apos;s pooled notes.
                    </small>
                  </div>
                  <button className="btn btn-ghost btn-sm" onClick={() => setConfirmLeave(true)}>
                    Leave
                  </button>
                </div>
                {isOwner && (
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontWeight: 600, fontSize: 14 }}>Delete circle</div>
                      <small className="sub" style={{ fontSize: 12.5 }}>
                        Permanently removes the circle and all its notes, quizzes and decks.
                      </small>
                    </div>
                    <button className="btn btn-dark btn-sm" onClick={() => setConfirmDeleteCircle(true)}>
                      Delete
                    </button>
                  </div>
                )}
              </div>
            </div>

            <div className="modal-actions">
              <button
                className="btn btn-ghost btn-sm"
                onClick={closeSettings}
                disabled={!!(savingName || leaving || regenerating || removingMemberId || deletingCircle)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Regenerate invite confirmation */}
      {confirmRegen && (
        <div className="modal-overlay" onClick={() => !regenerating && setConfirmRegen(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Regenerate invite code</h3>
            <p className="sub" style={{ fontSize: 13.5, margin: "0 0 4px" }}>
              This issues a brand-new code and <b>invalidates the current one</b>. Anyone with the old
              code won&apos;t be able to join until you share the new one.
            </p>
            <div className="modal-actions">
              <button className="btn btn-ghost btn-sm" onClick={() => setConfirmRegen(false)} disabled={regenerating}>
                Cancel
              </button>
              <button className="btn btn-dark btn-sm" onClick={doRegenerate} disabled={regenerating}>
                {regenerating ? "Regenerating…" : "Regenerate"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Remove member confirmation */}
      {memberToRemove && (
        <div className="modal-overlay" onClick={() => !removingMemberId && setMemberToRemove(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Remove member</h3>
            <p className="sub" style={{ fontSize: 13.5, margin: "0 0 4px" }}>
              Remove <b>{memberToRemove.display_name}</b> from this circle? They&apos;ll lose access
              until they rejoin with the invite code.
            </p>
            <div className="modal-actions">
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => setMemberToRemove(null)}
                disabled={!!removingMemberId}
              >
                Cancel
              </button>
              <button className="btn btn-dark btn-sm" onClick={doRemoveMember} disabled={!!removingMemberId}>
                {removingMemberId ? "Removing…" : "Remove"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Leave circle confirmation */}
      {confirmLeave && (
        <div className="modal-overlay" onClick={() => !leaving && setConfirmLeave(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Leave circle</h3>
            <p className="sub" style={{ fontSize: 13.5, margin: "0 0 4px" }}>
              Leave <b>{circle.name}</b>? You&apos;ll lose access to its pooled notes, quizzes and
              decks. You can rejoin later with the invite code.
              {isOwner && (
                <> As the owner, note you won&apos;t be able to manage the circle after leaving.</>
              )}
            </p>
            <div className="modal-actions">
              <button className="btn btn-ghost btn-sm" onClick={() => setConfirmLeave(false)} disabled={leaving}>
                Cancel
              </button>
              <button className="btn btn-dark btn-sm" onClick={doLeave} disabled={leaving}>
                {leaving ? "Leaving…" : "Leave circle"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete circle confirmation */}
      {confirmDeleteCircle && (
        <div className="modal-overlay" onClick={() => !deletingCircle && setConfirmDeleteCircle(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Delete circle</h3>
            <p className="sub" style={{ fontSize: 13.5, margin: "0 0 4px" }}>
              Permanently delete <b>{circle.name}</b>? This removes the circle and <b>all</b> of its
              notes, quizzes and flashcard decks for every member. This can&apos;t be undone.
            </p>
            <div className="modal-actions">
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => setConfirmDeleteCircle(false)}
                disabled={deletingCircle}
              >
                Cancel
              </button>
              <button className="btn btn-dark btn-sm" onClick={doDeleteCircle} disabled={deletingCircle}>
                {deletingCircle ? "Deleting…" : "Delete circle"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
