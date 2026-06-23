const PALETTE = ["#FF5A47", "#3F3AE6", "#0CB78D", "#F5A524", "#7C5CFF"];

/** Deterministic brand color for a circle, derived from a stable seed (its id). */
export function circleColor(seed: string): string {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  return PALETTE[h % PALETTE.length];
}

/** 1–2 letter initials from a circle or person name. */
export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}
