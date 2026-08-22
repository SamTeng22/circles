import { MATH_SNIPPET_GROUPS, type MathSnippet } from "@/lib/mathSnippets";

export function MathToolbar({ onInsert }: { onInsert: (snippet: MathSnippet) => void }) {
  return (
    <div className="math-toolbar">
      {MATH_SNIPPET_GROUPS.map((group) => (
        <div className="math-toolbar-group" key={group.name}>
          <span className="math-toolbar-label">{group.name}</span>
          {group.snippets.map((s) => (
            <button
              key={s.label}
              type="button"
              className="btn btn-ghost btn-sm math-toolbar-btn"
              title={s.title}
              onClick={() => onInsert(s)}
            >
              {s.label}
            </button>
          ))}
        </div>
      ))}
    </div>
  );
}
