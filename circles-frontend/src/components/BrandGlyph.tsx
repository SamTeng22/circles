export function BrandGlyph() {
  return (
    <svg className="brand-glyph" viewBox="0 0 40 40">
      <circle cx="15" cy="16" r="11" fill="#FF5A47" opacity=".85" style={{ mixBlendMode: "multiply" }} />
      <circle cx="25" cy="16" r="11" fill="#3F3AE6" opacity=".85" style={{ mixBlendMode: "multiply" }} />
      <circle cx="20" cy="25" r="11" fill="#0CB78D" opacity=".85" style={{ mixBlendMode: "multiply" }} />
    </svg>
  );
}

export function BrandGlyphLight() {
  return (
    <svg className="brand-glyph" viewBox="0 0 40 40">
      <circle cx="15" cy="16" r="11" fill="#FF5A47" style={{ mixBlendMode: "screen" }} />
      <circle cx="25" cy="16" r="11" fill="#3F3AE6" style={{ mixBlendMode: "screen" }} />
      <circle cx="20" cy="25" r="11" fill="#0CB78D" style={{ mixBlendMode: "screen" }} />
    </svg>
  );
}
