import { Fragment } from "react";
import katex from "katex";

type Segment = { kind: "text" | "inline" | "block"; value: string };

// $$...$$ blocks first, then $...$ inline spans in what's left. The inline
// delimiter can't be adjacent to whitespace or contain a bare "$", which is
// the usual heuristic for telling "$x^2$" apart from "costs $5 and $10".
const BLOCK_RE = /\$\$([\s\S]+?)\$\$/g;
const INLINE_RE = /(?<!\\)\$([^\s$](?:[^$]*[^\s$])?)\$/g;

function unescapeDollars(text: string): string {
  return text.replace(/\\\$/g, "$");
}

function splitInline(text: string): Segment[] {
  const segments: Segment[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  INLINE_RE.lastIndex = 0;
  while ((m = INLINE_RE.exec(text))) {
    if (m.index > last) segments.push({ kind: "text", value: unescapeDollars(text.slice(last, m.index)) });
    segments.push({ kind: "inline", value: m[1] });
    last = INLINE_RE.lastIndex;
  }
  if (last < text.length) segments.push({ kind: "text", value: unescapeDollars(text.slice(last)) });
  return segments;
}

function tokenize(text: string): Segment[] {
  const segments: Segment[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  BLOCK_RE.lastIndex = 0;
  while ((m = BLOCK_RE.exec(text))) {
    if (m.index > last) segments.push(...splitInline(text.slice(last, m.index)));
    segments.push({ kind: "block", value: m[1] });
    last = BLOCK_RE.lastIndex;
  }
  if (last < text.length) segments.push(...splitInline(text.slice(last)));
  return segments;
}

function renderKatex(latex: string, displayMode: boolean): string {
  try {
    return katex.renderToString(latex, { throwOnError: false, displayMode, strict: "ignore" });
  } catch {
    return latex;
  }
}

/**
 * Renders text that may contain LaTeX math delimited by $...$ (inline) or
 * $$...$$ (block); everything outside those delimiters is shown as-is. Drop
 * this in wherever note/quiz/flashcard text is interpolated directly.
 */
export function MathText({ text }: { text?: string | null }) {
  if (!text) return null;
  const segments = tokenize(text);
  return (
    <>
      {segments.map((seg, i) => {
        if (seg.kind === "text") return <Fragment key={i}>{seg.value}</Fragment>;
        const html = renderKatex(seg.value, seg.kind === "block");
        return seg.kind === "block" ? (
          <span key={i} className="math-block" dangerouslySetInnerHTML={{ __html: html }} />
        ) : (
          <span key={i} dangerouslySetInnerHTML={{ __html: html }} />
        );
      })}
    </>
  );
}
