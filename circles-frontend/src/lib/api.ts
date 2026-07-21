import { getIdToken } from "./firebase";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  formData?: FormData
): Promise<T> {
  const token = await getIdToken();
  const headers: HeadersInit = {
    Authorization: `Bearer ${token}`,
  };
  if (body) headers["Content-Type"] = "application/json";

  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: formData ?? (body ? JSON.stringify(body) : undefined),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "Request failed");
  }
  return res.json();
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body: unknown) => request<T>("POST", path, body),
  del: <T>(path: string) => request<T>("DELETE", path),
  upload: <T>(path: string, formData: FormData) =>
    request<T>("POST", path, undefined, formData),
};

// Typed helpers
export const circlesApi = {
  list: () => api.get<Circle[]>("/api/circles/"),
  get: (id: string) => api.get<Circle>(`/api/circles/${id}`),
  create: (name: string, description?: string) =>
    api.post<Circle>("/api/circles/", { name, description }),
  join: (invite_code: string) =>
    api.post<Circle>("/api/circles/join", { invite_code }),
  leave: (id: string) =>
    api.del<{ left: boolean; circle_deleted: boolean }>(`/api/circles/${id}/leave`),
  removeMember: (id: string, userId: string) =>
    api.del<{ removed: boolean }>(`/api/circles/${id}/members/${userId}`),
  rename: (id: string, name: string) =>
    request<Circle>("PATCH", `/api/circles/${id}`, { name }),
  delete: (id: string) => api.del<{ deleted: boolean }>(`/api/circles/${id}`),
  regenerateInvite: (id: string) =>
    request<Circle>("POST", `/api/circles/${id}/regenerate-invite`),
};

export const notesApi = {
  list: (circleId: string) => api.get<Note[]>(`/api/notes/${circleId}`),
  upload: (circleId: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return api.upload<{ note_id: string; status: string }>(
      `/api/notes/${circleId}/upload`,
      fd
    );
  },
  fileUrl: (noteId: string) =>
    api.get<{ url: string; filename: string }>(`/api/notes/file/${noteId}`),
  detail: (noteId: string) => api.get<Note>(`/api/notes/detail/${noteId}`),
  updateContent: (circleId: string, noteId: string, content: string) =>
    request<{ note_id: string; status: string }>(
      "PUT",
      `/api/notes/${circleId}/${noteId}/content`,
      { content }
    ),
  delete: (circleId: string, noteId: string) =>
    api.del<{ deleted: string }>(`/api/notes/${circleId}/${noteId}`),
};

export const quizApi = {
  list: (circleId: string) => api.get<Quiz[]>(`/api/quiz/${circleId}`),
  getById: (quizId: string) => api.get<Quiz>(`/api/quiz/detail/${quizId}`),
  generate: (circleId: string, title: string, topic?: string, num?: number) =>
    api.post<Quiz>("/api/quiz/generate", {
      circle_id: circleId,
      title,
      topic: topic ?? "",
      num_questions: num ?? 5,
    }),
  submit: (quizId: string, answers: Record<string, string>) =>
    api.post<{ score: number; total: number }>(`/api/quiz/${quizId}/submit`, answers),
};

export const flashcardsApi = {
  list: (circleId: string) => api.get<FlashcardDeck[]>(`/api/flashcards/${circleId}`),
  getById: (deckId: string) => api.get<FlashcardDeck>(`/api/flashcards/detail/${deckId}`),
  generate: (circleId: string, title: string, topic?: string, num?: number) =>
    api.post<FlashcardDeck>("/api/flashcards/generate", {
      circle_id: circleId,
      title,
      topic: topic ?? "",
      num_cards: num ?? 10,
    }),
};

// Types
export interface Circle {
  id: string;
  name: string;
  description: string;
  invite_code: string;
  owner_id: string;
  members?: { id: string; display_name: string; email: string }[];
  created_at: string;
}

export type NoteStatus = "processing" | "ready" | "failed";

export interface Note {
  id: string;
  circle_id: string;
  user_id: string;
  filename: string;
  uploader_name: string;
  content?: string | null;
  status: NoteStatus;
  s3_key: string | null;
  content_type: string | null;
  size_bytes: number | null;
  error: string | null;
  created_at: string;
  edited_at?: string | null;
}

export interface Quiz {
  id: string;
  circle_id: string;
  title: string;
  questions: Question[];
  created_at: string;
}

export interface Question {
  question: string;
  options: string[];
  correct_answer: string;
  bloom_level: string;
  explanation: string;
}

export interface Flashcard {
  front: string;
  back: string;
  hint?: string;
}

export interface FlashcardDeck {
  id: string;
  circle_id: string;
  title: string;
  cards: Flashcard[];
  created_at: string;
}
