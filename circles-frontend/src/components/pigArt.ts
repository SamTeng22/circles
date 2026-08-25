// Shared geometry for the Circles pig mascot, drawn as hand-traced discs.
// Ported from the circles-loader concept: each part is an SVG arc path so it
// can be "drawn" with a stroke-dashoffset animation in PigLoader, or rendered
// fully filled/static in PigMascot.

export function circleD(cx: number, cy: number, r: number) {
  const t = cy - r;
  return `M ${cx} ${t} A ${r} ${r} 0 1 1 ${cx} ${cy + r} A ${r} ${r} 0 1 1 ${cx} ${t}`;
}

export function ellipseD(cx: number, cy: number, rx: number, ry: number) {
  const t = cy - ry;
  return `M ${cx} ${t} A ${rx} ${ry} 0 1 1 ${cx} ${cy + ry} A ${rx} ${ry} 0 1 1 ${cx} ${t}`;
}

export type PigColor = "persimmon" | "cobalt" | "jade" | "gold" | "violet" | "ink";

export const PIG_FILL: Record<PigColor, string> = {
  persimmon: "#FF5A47",
  cobalt: "#3F3AE6",
  jade: "#0CB78D",
  gold: "#F5A524",
  violet: "#7C5CFF",
  ink: "#15132A",
};

export const PIG_STROKE: Record<PigColor, string> = {
  persimmon: "#E8412F",
  cobalt: "#2A25C4",
  jade: "#08916F",
  gold: "#D6870F",
  violet: "#5E43D6",
  ink: "#221C40",
};

export type PigPart = {
  id: string;
  d: string;
  col: PigColor;
  solid?: boolean;
  fo?: number;
  thin?: boolean;
  big?: boolean;
  dur?: number;
};

// line 1 = snout (nostril, nostril, big snout) · line 2 = head (ear, ear, big head)
export const PIG_PARTS: PigPart[] = [
  { id: "nos-l", d: ellipseD(112, 153, 4.5, 7), col: "ink", solid: true, fo: 0.62, thin: true, dur: 0.32 },
  { id: "nos-r", d: ellipseD(128, 153, 4.5, 7), col: "ink", solid: true, fo: 0.62, thin: true, dur: 0.32 },
  { id: "snout", d: ellipseD(120, 152, 33, 24), col: "gold", big: true, dur: 0.5 },
  { id: "ear-l", d: circleD(78, 66, 27), col: "cobalt", dur: 0.48 },
  { id: "ear-r", d: circleD(162, 66, 27), col: "jade", dur: 0.48 },
  { id: "head", d: circleD(120, 126, 72), col: "persimmon", big: true, dur: 0.62 },
];

export const PIG_FILL_ORDER = ["ear-l", "ear-r", "head", "snout", "nos-l", "nos-r"];

export const PIG_EYES = [
  { id: "eye-l", cx: 102, cy: 114, r: 6 },
  { id: "eye-r", cx: 138, cy: 114, r: 6 },
];

export const PIG_LINES: PigPart[] = [
  { id: "tail", d: "M190 150 C 200 140 208 152 201 161 C 196 168 187 163 191 155", col: "persimmon", thin: true, dur: 0.5 },
  { id: "smile", d: "M108 176 Q120 188 132 176", col: "ink", thin: true, dur: 0.4 },
];

export const PIG_VIEWBOX = "0 0 240 232";
