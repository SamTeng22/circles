// Mirrors circles-backend/app/services/grading.py's grade_question — kept in
// sync manually since the two apps share no code. Used for the results/review
// view and the local-fallback scorer, both of which need per-question-type
// correctness without waiting on the server's aggregate score.
import { Question, QuestionType, QuizAnswerValue, getQuestionType } from "./api";

function normalize(s: string): string {
  return s.trim().toLowerCase().split(/\s+/).join(" ");
}

export function isAnswerCorrect(question: Question, submitted: QuizAnswerValue | undefined): boolean {
  const qtype: QuestionType = getQuestionType(question);

  if (qtype === "multiple_choice" || qtype === "true_false") {
    return submitted === (question as { correct_answer: string }).correct_answer;
  }

  if (qtype === "fill_in_blank") {
    if (typeof submitted !== "string") return false;
    const q = question as { accepted_answers: string[]; correct_answer: string };
    const accepted = q.accepted_answers?.length ? q.accepted_answers : [q.correct_answer];
    const acceptedNorm = new Set(accepted.filter((a) => typeof a === "string").map(normalize));
    return acceptedNorm.has(normalize(submitted));
  }

  if (qtype === "matching") {
    if (!submitted || typeof submitted !== "object") return false;
    const q = question as { pairs: { left: string; right: string }[] };
    const pairs = q.pairs ?? [];
    if (pairs.length === 0 || Object.keys(submitted).length !== pairs.length) return false;
    return pairs.every((p) => submitted[p.left] === p.right);
  }

  return false;
}
