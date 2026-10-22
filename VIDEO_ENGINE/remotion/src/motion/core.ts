// Core helpers of the motion library. Everything here is a pure function of (frame, parameters): no clock, no Math.random, no DOM,
// so the same frame always gives the same result (Remotion renders frames in any order and in parallel).

export const clamp01 = (x: number): number => (x < 0 ? 0 : x > 1 ? 1 : x);
export const lerp = (a: number, b: number, t: number): number => a + (b - a) * t;
/** 0..1 progress of `frame` inside [start, start + dur] (a zero duration is a cut). */
export const prog = (frame: number, start: number, dur: number): number => (dur <= 0 ? (frame >= start ? 1 : 0) : clamp01((frame - start) / dur));

// ---------- easings (own implementations; every one maps 0 -> 0 and 1 -> 1) ----------
const outBounce = (t: number): number => {
  const n = 7.5625, d = 2.75;
  if (t < 1 / d) return n * t * t;
  if (t < 2 / d) return n * (t -= 1.5 / d) * t + 0.75;
  if (t < 2.5 / d) return n * (t -= 2.25 / d) * t + 0.9375;
  return n * (t -= 2.625 / d) * t + 0.984375;
};
export const EASE = {
  linear: (t: number) => t,
  inCubic: (t: number) => t * t * t,
  outCubic: (t: number) => 1 - (1 - t) ** 3,
  outQuart: (t: number) => 1 - (1 - t) ** 4,
  outExpo: (t: number) => (t >= 1 ? 1 : 1 - 2 ** (-10 * t)),
  inExpo: (t: number) => (t <= 0 ? 0 : 2 ** (10 * t - 10)),
  inOutCubic: (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2),
  inOutSine: (t: number) => -(Math.cos(Math.PI * t) - 1) / 2,
  smooth: (t: number) => t * t * (3 - 2 * t),
  outBack: (t: number) => 1 + 2.70158 * (t - 1) ** 3 + 1.70158 * (t - 1) ** 2,
  outElastic: (t: number) => (t <= 0 ? 0 : t >= 1 ? 1 : 2 ** (-10 * t) * Math.sin(((t * 10 - 0.75) * (2 * Math.PI)) / 3) + 1),
  outBounce,
} as const;
export type EaseName = keyof typeof EASE;
export const ease = (name: EaseName | undefined, t: number): number => EASE[name ?? "outCubic"](clamp01(t));

// ---------- deterministic variation ----------
/** 32-bit hash of a string or number (xmur3-style): the seed of every "random" choice. */
export function hash(seed: string | number): number {
  const s = String(seed);
  let h = 1779033703 ^ s.length;
  for (let i = 0; i < s.length; i++) {
    h = Math.imul(h ^ s.charCodeAt(i), 3432918353);
    h = (h << 13) | (h >>> 19);
  }
  h = Math.imul(h ^ (h >>> 16), 2246822507);
  h = Math.imul(h ^ (h >>> 13), 3266489909);
  return (h ^ (h >>> 16)) >>> 0;
}
/** A float in [0, 1) that depends only on (seed, index): the same everywhere, in any order. */
export const rnd = (seed: string | number, i = 0): number => hash(`${seed}:${i}`) / 4294967296;
/** A float in [-1, 1) */
export const srnd = (seed: string | number, i = 0): number => rnd(seed, i) * 2 - 1;

// ---------- text segmentation (Telugu safe) ----------
export const isIndic = (s: string): boolean => /[ఀ-౿]/.test(s);
/** Grapheme clusters: a Telugu consonant with its vowel sign / virama conjunct stays ONE unit. Falls back to code points. */
export function graphemes(s: string): string[] {
  const Seg = (Intl as unknown as { Segmenter?: new (l?: string, o?: object) => { segment(x: string): Iterable<{ segment: string }> } }).Segmenter;
  return Seg ? [...new Seg("und", { granularity: "grapheme" }).segment(s)].map((x) => x.segment) : Array.from(s);
}
export const wordsOf = (s: string): string[] => s.split(/\s+/).filter(Boolean);

/** Estimated advance of a text in px (an upper-bound estimate, not a measurement): Latin ~0.6 em, a space 0.3 em, a Telugu cluster 1.2 em (1.3 em bold).
 *  The Telugu figures come from real renders of Noto Sans Telugu (measured 1.15 to 1.23 em per cluster; it varies a lot with the vowel signs and conjuncts),
 *  so a line is wrapped or shrunk before it can run out of its box. */
export function estWidth(text: string, size: number, weight = 600): number {
  const latin = weight >= 700 ? 0.64 : 0.6;
  const indic = weight >= 700 ? 1.3 : 1.2;
  let w = 0;
  for (const g of graphemes(text)) w += (/\s/.test(g) ? 0.3 : isIndic(g) ? indic : /[A-Z0-9]/.test(g) ? latin * 1.08 : latin) * size;
  return w;
}

/** Greedy line breaking with the width estimate; never breaks inside a word. Returns lines of words (all words, in order). */
export function breakLines(text: string, size: number, weight: number, maxWidth: number): string[][] {
  const lines: string[][] = [[]];
  for (const w of wordsOf(text)) {
    const cur = lines[lines.length - 1];
    if (cur.length && estWidth([...cur, w].join(" "), size, weight) > maxWidth) lines.push([w]);
    else cur.push(w);
  }
  return lines.filter((l) => l.length);
}

/** The largest size <= `size` (never below `floor` x size) that keeps the text in `maxLines` lines inside maxWidth. */
export function fitSize(text: string, size: number, weight: number, maxWidth: number, maxLines = 2, floor = 0.55): number {
  let s = size;
  while (s > size * floor && breakLines(text, s, weight, maxWidth).length > maxLines) s *= 0.94;
  return Math.max(size * floor, s);
}

/** The widest a text may be: `boxW`, but a positioned text (left edge, or middle when `center`) only has the room from its position to the safe margin, so it wraps or shrinks instead of leaving the frame. */
export function textRoom(boxW: number, frameW: number, safe: number, pos?: [number, number], center?: boolean): number {
  if (!pos) return boxW;
  const edge = frameW * (1 - safe);
  const room = center ? 2 * Math.min(pos[0] - frameW * safe, edge - pos[0]) : edge - pos[0];
  return Math.min(boxW, Math.max(room, frameW * 0.2));      // a position already outside the margin keeps a usable width (the layout check still reports it)
}

// ---------- geometry ----------
export type Dir = "left" | "right" | "up" | "down";
/** Unit vector of a direction ("left" = comes from / moves toward the left). */
export const dirVec = (d: Dir): { x: number; y: number } => ({ left: { x: -1, y: 0 }, right: { x: 1, y: 0 }, up: { x: 0, y: -1 }, down: { x: 0, y: 1 } })[d];
export const DIRS: Dir[] = ["left", "right", "up", "down"];
export type Box = [number, number, number, number]; // x, y, width, height (px)
export const inside = (b: Box, w: number, h: number, m = 0): boolean => b[0] >= m && b[1] >= m && b[0] + b[2] <= w - m && b[1] + b[3] <= h - m;
export const overlaps = (a: Box, b: Box, pad = 0): boolean => a[0] < b[0] + b[2] + pad && b[0] < a[0] + a[2] + pad && a[1] < b[1] + b[3] + pad && b[1] < a[1] + a[3] + pad;
