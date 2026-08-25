// Companion mascots to the pig (see pigArt.ts), drawn in the same style:
// every part is an SVG arc/segment path so it can be stroke-drawn with a
// dashoffset animation or rendered filled, colours come from the same
// six-colour brand palette, and each animal shares the pig's 240x232 frame
// so they line up when rendered side by side.
//
// The pig stays the app's own mascot (loading states, branding); these four
// are the interchangeable set used for live-quiz answer options.

import {
  circleD,
  ellipseD,
  PIG_EYES,
  PIG_FILL_ORDER,
  PIG_LINES,
  PIG_PARTS,
  PIG_VIEWBOX,
  type PigPart,
} from "./pigArt";

export type AnimalEye = { id: string; cx: number; cy: number; r: number };

export type AnimalSpec = {
  /** Stroke/fill shapes, in draw order: details first, big shapes last. */
  parts: PigPart[];
  /** Paint order for the fills (back to front) -- ids from `parts`. */
  fillOrder: string[];
  eyes: AnimalEye[];
  /** Decorative single-stroke details (mouth, whiskers, tail). */
  lines: PigPart[];
  viewBox: string;
};

export type AnimalName = "pig" | "dog" | "cat" | "rabbit" | "bear";

// Floppy side ears + a wide muzzle.
const DOG: AnimalSpec = {
  parts: [
    { id: "nose", d: ellipseD(120, 140, 10, 7), col: "ink", solid: true, fo: 0.7, thin: true, dur: 0.3 },
    { id: "snout", d: ellipseD(120, 152, 31, 24), col: "violet", big: true, dur: 0.5 },
    { id: "ear-l", d: ellipseD(62, 124, 20, 42), col: "cobalt", dur: 0.5 },
    { id: "ear-r", d: ellipseD(178, 124, 20, 42), col: "cobalt", dur: 0.5 },
    { id: "head", d: circleD(120, 120, 70), col: "gold", big: true, dur: 0.62 },
  ],
  fillOrder: ["ear-l", "ear-r", "head", "snout", "nose"],
  eyes: [
    { id: "eye-l", cx: 100, cy: 106, r: 6 },
    { id: "eye-r", cx: 140, cy: 106, r: 6 },
  ],
  lines: [
    { id: "mouth", d: "M108 158 Q120 170 132 158", col: "ink", thin: true, dur: 0.4 },
    { id: "tongue", d: "M114 168 Q120 182 126 168", col: "persimmon", thin: true, dur: 0.35 },
    { id: "tail", d: "M188 152 C 202 146 210 158 202 168", col: "gold", thin: true, dur: 0.45 },
  ],
  viewBox: PIG_VIEWBOX,
};

// Pointed ears + whiskers.
const CAT: AnimalSpec = {
  parts: [
    { id: "nose", d: ellipseD(120, 146, 8, 6), col: "ink", solid: true, fo: 0.7, thin: true, dur: 0.3 },
    { id: "muzzle", d: ellipseD(120, 158, 26, 18), col: "gold", dur: 0.45 },
    { id: "ear-l", d: "M 76 84 L 90 28 L 126 66 Z", col: "jade", dur: 0.45 },
    { id: "ear-r", d: "M 164 84 L 150 28 L 114 66 Z", col: "jade", dur: 0.45 },
    { id: "head", d: circleD(120, 126, 70), col: "violet", big: true, dur: 0.62 },
  ],
  fillOrder: ["ear-l", "ear-r", "head", "muzzle", "nose"],
  eyes: [
    { id: "eye-l", cx: 100, cy: 116, r: 6 },
    { id: "eye-r", cx: 140, cy: 116, r: 6 },
  ],
  lines: [
    { id: "mouth", d: "M110 162 Q120 172 130 162", col: "ink", thin: true, dur: 0.35 },
    { id: "whisk-l", d: "M90 150 L 40 140 M90 158 L 38 160", col: "ink", thin: true, dur: 0.3 },
    { id: "whisk-r", d: "M150 150 L 200 140 M150 158 L 202 160", col: "ink", thin: true, dur: 0.3 },
    { id: "tail", d: "M186 168 C 204 166 210 148 198 140", col: "violet", thin: true, dur: 0.45 },
  ],
  viewBox: PIG_VIEWBOX,
};

// Tall upright ears + buck teeth.
const RABBIT: AnimalSpec = {
  parts: [
    { id: "nose", d: ellipseD(120, 149, 7.5, 5.5), col: "ink", solid: true, fo: 0.7, thin: true, dur: 0.3 },
    { id: "muzzle", d: ellipseD(120, 160, 24, 17), col: "gold", dur: 0.45 },
    { id: "ear-l", d: ellipseD(97, 50, 15, 46), col: "persimmon", dur: 0.5 },
    { id: "ear-r", d: ellipseD(143, 50, 15, 46), col: "persimmon", dur: 0.5 },
    { id: "head", d: circleD(120, 132, 66), col: "cobalt", big: true, dur: 0.62 },
  ],
  fillOrder: ["ear-l", "ear-r", "head", "muzzle", "nose"],
  eyes: [
    { id: "eye-l", cx: 101, cy: 124, r: 6 },
    { id: "eye-r", cx: 139, cy: 124, r: 6 },
  ],
  lines: [
    { id: "mouth", d: "M120 155 Q112 166 104 160 M120 155 Q128 166 136 160", col: "ink", thin: true, dur: 0.4 },
    { id: "teeth", d: "M115 169 L 115 180 M125 169 L 125 180", col: "ink", thin: true, dur: 0.3 },
  ],
  viewBox: PIG_VIEWBOX,
};

// Wide-set round ears + a big round muzzle.
const BEAR: AnimalSpec = {
  parts: [
    { id: "nose", d: ellipseD(120, 143, 11, 8), col: "ink", solid: true, fo: 0.72, thin: true, dur: 0.3 },
    { id: "muzzle", d: ellipseD(120, 156, 30, 22), col: "persimmon", big: true, dur: 0.5 },
    { id: "ear-l", d: circleD(66, 74, 25), col: "gold", dur: 0.48 },
    { id: "ear-r", d: circleD(174, 74, 25), col: "gold", dur: 0.48 },
    { id: "head", d: circleD(120, 128, 70), col: "jade", big: true, dur: 0.62 },
  ],
  fillOrder: ["ear-l", "ear-r", "head", "muzzle", "nose"],
  eyes: [
    { id: "eye-l", cx: 100, cy: 118, r: 6 },
    { id: "eye-r", cx: 140, cy: 118, r: 6 },
  ],
  lines: [
    { id: "mouth", d: "M120 151 L 120 162", col: "ink", thin: true, dur: 0.25 },
    { id: "smile", d: "M106 162 Q120 176 134 162", col: "ink", thin: true, dur: 0.4 },
  ],
  viewBox: PIG_VIEWBOX,
};

const PIG: AnimalSpec = {
  parts: PIG_PARTS,
  fillOrder: PIG_FILL_ORDER,
  eyes: PIG_EYES,
  lines: PIG_LINES,
  viewBox: PIG_VIEWBOX,
};

export const ANIMALS: Record<AnimalName, AnimalSpec> = {
  pig: PIG,
  dog: DOG,
  cat: CAT,
  rabbit: RABBIT,
  bear: BEAR,
};
