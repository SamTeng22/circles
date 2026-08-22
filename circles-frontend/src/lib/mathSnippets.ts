export type MathSnippet = {
  label: string;
  title: string;
  /** Text inserted before the (possibly-empty) selection. */
  before: string;
  /** Text inserted after the selection. */
  after: string;
  /** Where to place the caret when nothing was selected, relative to `before`'s start. Defaults to before.length. */
  caretOffset?: number;
  /**
   * If true, insert `before`/`after` exactly as given, with no automatic
   * $...$ wrapping. Used only by the two snippets that *are* the math
   * delimiters themselves ("Inline math" / "Block math") - every other
   * snippet is LaTeX that only renders inside a $...$ span, so it gets
   * auto-wrapped unless the cursor is already inside one.
   */
  raw?: boolean;
};

export const MATH_SNIPPET_GROUPS: { name: string; snippets: MathSnippet[] }[] = [
  {
    name: "Basics",
    snippets: [
      { label: "$x$", title: "Inline math", before: "$", after: "$", raw: true },
      { label: "$$x$$", title: "Block math", before: "$$", after: "$$", raw: true },
      { label: "a/b", title: "Fraction", before: "\\frac{", after: "}{}" },
      { label: "√", title: "Square root", before: "\\sqrt{", after: "}" },
      { label: "xⁿ", title: "Superscript", before: "^{", after: "}" },
      { label: "xₙ", title: "Subscript", before: "_{", after: "}" },
    ],
  },
  {
    name: "Calculus",
    snippets: [
      { label: "d/dx", title: "Derivative", before: "\\frac{d}{dx}", after: "" },
      { label: "∂", title: "Partial derivative", before: "\\partial", after: "" },
      { label: "∫", title: "Integral", before: "\\int_{", after: "}^{} \\, dx" },
      { label: "Σ", title: "Summation", before: "\\sum_{", after: "}^{}" },
      { label: "lim", title: "Limit", before: "\\lim_{x \\to ", after: "}" },
      { label: "∞", title: "Infinity", before: "\\infty", after: "" },
    ],
  },
  {
    name: "Greek",
    snippets: [
      { label: "α", title: "alpha", before: "\\alpha", after: "" },
      { label: "β", title: "beta", before: "\\beta", after: "" },
      { label: "θ", title: "theta", before: "\\theta", after: "" },
      { label: "π", title: "pi", before: "\\pi", after: "" },
      { label: "σ", title: "sigma", before: "\\sigma", after: "" },
      { label: "μ", title: "mu", before: "\\mu", after: "" },
      { label: "Δ", title: "Delta", before: "\\Delta", after: "" },
    ],
  },
];

/** Whether `pos` falls inside an already-open (unclosed) $ or $$ span, by
 * parity of unescaped `$` characters before it. */
function isInsideMath(value: string, pos: number): boolean {
  let count = 0;
  for (let i = 0; i < pos; i++) {
    if (value[i] === "$" && value[i - 1] !== "\\") count++;
  }
  return count % 2 === 1;
}

/**
 * Inserts a snippet at the textarea's cursor, wrapping the current selection
 * (if any) between `before` and `after`. LaTeX snippets are automatically
 * wrapped in $...$ unless the cursor is already inside a math span, so a
 * button like "Superscript" produces math that actually renders instead of
 * dropping bare LaTeX into plain text. Returns the new field value and where
 * the caret should end up.
 */
export function insertSnippet(
  textarea: HTMLTextAreaElement,
  value: string,
  snippet: MathSnippet
): { newValue: string; caretStart: number; caretEnd: number } {
  const start = textarea.selectionStart ?? value.length;
  const end = textarea.selectionEnd ?? value.length;
  const selected = value.slice(start, end);

  const wrap = !snippet.raw && !isInsideMath(value, start);
  const before = wrap ? "$" + snippet.before : snippet.before;
  const after = wrap ? snippet.after + "$" : snippet.after;
  const caretOffset = (snippet.caretOffset ?? snippet.before.length) + (wrap ? 1 : 0);

  const newValue = value.slice(0, start) + before + selected + after + value.slice(end);

  if (selected) {
    const caretStart = start + before.length;
    const caretEnd = caretStart + selected.length;
    return { newValue, caretStart, caretEnd };
  }

  const caret = start + caretOffset;
  return { newValue, caretStart: caret, caretEnd: caret };
}
