"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/AuthContext";
import { circlesApi, notesApi, Circle, Note } from "@/lib/api";
import { Sidebar } from "@/components/Sidebar";
import { PigLoader } from "@/components/PigLoader";
import { PigProcessing } from "@/components/PigProcessing";
import { MathText } from "@/components/MathText";
import { MathToolbar } from "@/components/MathToolbar";
import { insertSnippet, type MathSnippet } from "@/lib/mathSnippets";
import { timeAgo } from "@/lib/format";

export default function NoteDetailPage() {
  const { id, noteId } = useParams<{ id: string; noteId: string }>();
  const { user, loading } = useAuth();
  const router = useRouter();

  const [allCircles, setAllCircles] = useState<Circle[]>([]);
  const [circle, setCircle] = useState<Circle | null>(null);
  const [note, setNote] = useState<Note | null>(null);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  const [editing, setEditing] = useState(false);
  const [editContent, setEditContent] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");

  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const editorRef = useRef<HTMLTextAreaElement>(null);
  function autoResizeEditor() {
    const el = editorRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }
  useEffect(() => {
    if (editing) autoResizeEditor();
  }, [editing]);

  function handleInsertSnippet(snippet: MathSnippet) {
    const el = editorRef.current;
    if (!el) return;
    const { newValue, caretStart, caretEnd } = insertSnippet(el, editContent, snippet);
    setEditContent(newValue);
    requestAnimationFrame(() => {
      el.focus();
      el.selectionStart = caretStart;
      el.selectionEnd = caretEnd;
      autoResizeEditor();
    });
  }

  useEffect(() => {
    if (!loading && !user) router.push("/login");
  }, [user, loading, router]);

  useEffect(() => {
    if (!user || !id || !noteId) return;
    let cancelled = false;
    setPageLoading(true);
    setLoadError("");
    Promise.all([circlesApi.get(id), notesApi.detail(noteId), circlesApi.list()])
      .then(([c, n, all]) => {
        if (cancelled) return;
        if (n.circle_id !== id) {
          setLoadError("This note doesn't belong to this circle.");
          return;
        }
        setCircle(c);
        setNote(n);
        setEditContent(n.content ?? "");
        setAllCircles(all);
      })
      .catch((e: any) => {
        if (!cancelled) setLoadError(e.message || "Couldn't load this note.");
      })
      .finally(() => {
        if (!cancelled) setPageLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user, id, noteId]);

  const members = circle?.members ?? [];
  const myId = useMemo(
    () => members.find((m) => m.email === user?.email)?.id ?? null,
    [members, user?.email]
  );
  const canDelete = myId != null && note != null && (note.user_id === myId || circle?.owner_id === myId);

  function backToCircle() {
    router.push(`/circles/${id}`);
  }

  async function openFile() {
    if (!note) return;
    try {
      const { url } = await notesApi.fileUrl(note.id);
      window.open(url, "_blank", "noopener");
    } catch {
      /* file may not exist for older text-only notes */
    }
  }

  async function save() {
    if (!note || saving) return;
    setSaving(true);
    setSaveError("");
    try {
      await notesApi.updateContent(id, note.id, editContent);
      backToCircle();
    } catch (e: any) {
      setSaveError(e.message || "Failed to save changes.");
    } finally {
      setSaving(false);
    }
  }

  async function confirmedDelete() {
    if (!note || deleting) return;
    setDeleting(true);
    try {
      await notesApi.delete(id, note.id);
      backToCircle();
    } catch (e: any) {
      setSaveError(e.message || "Failed to delete note.");
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  if (loading || !user || pageLoading) {
    return <PigLoader />;
  }

  if (loadError || !circle || !note) {
    return (
      <div className="app">
        <Sidebar user={user} circles={allCircles} activeCircleId={id} />
        <main className="main">
          <div className="empty">
            <h3>Note not available</h3>
            <p>{loadError || "This note doesn't exist or you don't have access."}</p>
            <button className="btn btn-primary btn-sm" onClick={() => router.push(`/circles/${id}`)}>
              Back to circle
            </button>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="app">
      <Sidebar user={user} circles={allCircles} activeCircleId={id} />

      <main className="main">
        <div className="doc-shell">
          <div className="doc-toolbar">
            <button className="btn btn-ghost btn-sm" onClick={backToCircle}>
              ← Back to {circle.name}
            </button>
            <div className="doc-toolbar-actions">
              {note.status === "processing" && <PigProcessing />}
              {note.status === "ready" && <span className="chip chip-jade">ready</span>}
              {note.status === "failed" && (
                <span className="chip chip-flag" title={note.error ?? "Extraction failed"}>
                  failed
                </span>
              )}
              {editing ? (
                <>
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() => {
                      setEditing(false);
                      setEditContent(note.content ?? "");
                    }}
                    disabled={saving}
                  >
                    Cancel
                  </button>
                  <button className="btn btn-primary btn-sm" onClick={save} disabled={saving}>
                    {saving ? "Saving…" : "Save & re-embed"}
                  </button>
                </>
              ) : (
                canDelete && (
                  <>
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => setConfirmDelete(true)}
                      disabled={deleting}
                    >
                      Delete
                    </button>
                    <button className="btn btn-primary btn-sm" onClick={() => setEditing(true)}>
                      Edit
                    </button>
                  </>
                )
              )}
            </div>
          </div>

          <div className="doc-heading">
            <h1>
              {note.s3_key ? (
                <span className="note-link" onClick={openFile} title="Open original">
                  {note.filename}
                </span>
              ) : (
                note.filename
              )}
            </h1>
            <p className="doc-meta">
              {note.uploader_name} · {timeAgo(note.created_at)}
              {note.edited_at && <> · edited {timeAgo(note.edited_at)}</>}
              {" — "}what the system extracted and uses for quizzes.
            </p>
          </div>

          {saveError && (
            <div className="auth-error" style={{ marginBottom: 16 }}>
              {saveError}
            </div>
          )}

          <div className="doc-page">
            {editing ? (
              <>
                <MathToolbar onInsert={handleInsertSnippet} />
                <p className="math-editor-hint">
                  Wrap math in $…$ (inline) or $$…$$ (block); use \$ for a literal dollar sign.
                </p>
                <textarea
                  ref={editorRef}
                  className="doc-editor"
                  value={editContent}
                  onChange={(e) => {
                    setEditContent(e.target.value);
                    autoResizeEditor();
                  }}
                  disabled={saving}
                  autoFocus
                />
                {editContent.trim() && (
                  <div className="doc-live-preview">
                    <span className="math-toolbar-label">Preview</span>
                    <div className="doc-text">
                      <MathText text={editContent} />
                    </div>
                  </div>
                )}
              </>
            ) : editContent.trim() ? (
              <div className="doc-text">
                <MathText text={editContent} />
              </div>
            ) : (
              <p className="sub" style={{ fontSize: 13.5 }}>
                No extracted text yet{note.status === "failed" ? " — extraction failed for this file." : "."}
              </p>
            )}
          </div>
        </div>
      </main>

      {confirmDelete && (
        <div className="modal-overlay" onClick={() => !deleting && setConfirmDelete(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Delete note</h3>
            <p className="sub" style={{ fontSize: 13.5, margin: "0 0 4px" }}>
              Delete <b>{note.filename}</b> from the pool? This removes its text and embeddings and
              can&apos;t be undone.
            </p>
            <div className="modal-actions">
              <button className="btn btn-ghost btn-sm" onClick={() => setConfirmDelete(false)} disabled={deleting}>
                Cancel
              </button>
              <button className="btn btn-primary btn-sm" onClick={confirmedDelete} disabled={deleting}>
                {deleting ? "Deleting…" : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
