// The phrase composer (kinetic typography): ONE sentence drawn as runs of words, each run with its own font, weight, size, colour and highlight
// ("so you can SEE how CAPABLE": small dim lead-in, a giant hero word; "You create." in bold sans + italic serif; a marker box on the key words).
// Pure functions: no DOM, no clock, no Math.random. Every word of the text is in the layout, in order; the runs only change HOW it looks.
import type { FontKind } from "../fonts";
import { estWidth, hash, isIndic, wordsOf } from "./core";

export interface Run {
  text: string;
  font?: FontKind;       // sans (default) | serif | mono: ENGLISH only
  weight?: number;
  italic?: boolean;
  scale?: number;        // font size relative to the layer's size (default 1)
  color?: string;
  hl?: boolean;          // a marker box behind the words, drawn when they are emphasised
  hlColor?: string;      // the text colour while the marker is drawn
  upper?: boolean;
  track?: number;        // letter spacing in em
}
export interface PWord { text: string; run: Run }

export const phraseText = (runs: Run[]): string => runs.flatMap((r) => wordsOf(r.text)).join(" ");
export const phraseWords = (runs: Run[]): PWord[] => runs.flatMap((r) => wordsOf(r.text).map((text) => ({ text, run: r })));

const GAP = 0.28;                                                    // the space between two words, in em of the layer's size (as the renderer's marginRight)
const wordW = (w: PWord, size: number, base: number): number => {
  const s = size * (w.run.scale ?? 1);
  return estWidth(w.run.upper ? w.text.toUpperCase() : w.text, s, w.run.weight ?? base) + (w.run.track ?? 0) * w.text.length * s;
};

export interface PhraseLayout { size: number; lines: PWord[][]; width: number; height: number }
/** Greedy line breaking with the width estimate (an upper bound, like core.estWidth); the size shrinks (never below 55 %) until the phrase fits `maxLines` lines and no word is wider than the box. */
export function layoutPhrase(runs: Run[], size: number, baseWeight: number, maxWidth: number, maxLines = 3): PhraseLayout {
  const words = phraseWords(runs);
  const brk = (s: number): PWord[][] => {
    const lines: PWord[][] = [[]];
    let cur = 0;
    for (const w of words) {
      const ww = wordW(w, s, baseWeight);
      const line = lines[lines.length - 1];
      if (line.length && cur + GAP * s + ww > maxWidth) { lines.push([w]); cur = ww; } else { cur += (line.length ? GAP * s : 0) + ww; line.push(w); }
    }
    return lines;
  };
  const lineW = (l: PWord[], s: number) => l.reduce((a, w, i) => a + wordW(w, s, baseWeight) + (i ? GAP * s : 0), 0);
  let s = size, lines = brk(s);
  while (s > size * 0.55 && (lines.length > maxLines || lines.some((l) => lineW(l, s) > maxWidth))) { s *= 0.94; lines = brk(s); }
  const width = Math.max(0, ...lines.map((l) => lineW(l, s)));
  const height = lines.reduce((a, l) => a + Math.max(...l.map((w) => w.run.scale ?? 1)) * s * 1.12, 0);
  return { size: s, lines, width: Math.min(width, maxWidth), height };
}

export interface KitColors { fg: string; accent: string; dim: string; bg: string }
const STOP = new Set(["the", "a", "an", "of", "to", "in", "on", "and", "or", "is", "are", "was", "it", "for", "with", "as", "at", "by", "that", "this", "we", "you", "your", "our", "than", "us", "so", "how", "can"]);
const clean = (w: string) => w.toLowerCase().replace(/[^a-z0-9]/g, "");

/** The word the phrase is about: the marked keyword if there is one, else the longest word that is not a filler (the last one wins a tie). */
export function pickHero(words: string[], mark?: string): number {
  const m = clean(mark ?? "");
  if (m) { const i = words.findIndex((w) => clean(w) && (clean(w).includes(m) || m.includes(clean(w)))); if (i >= 0) return i; }
  let best = -1;
  words.forEach((w, i) => { const c = clean(w); if (c && !STOP.has(c) && (best < 0 || c.length >= clean(words[best]).length)) best = i; });
  return best >= 0 ? best : words.length - 1;
}

const readable = (bg: string, a = "#111111", b = "#ffffff"): string => {
  const lum = (h: string) => { const f = (v: number) => ((v /= 255) <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4); const x = h.replace("#", ""); return 0.2126 * f(parseInt(x.slice(0, 2), 16)) + 0.7152 * f(parseInt(x.slice(2, 4), 16)) + 0.0722 * f(parseInt(x.slice(4, 6), 16)); };
  const c = (p: string) => { const [u, v] = [lum(p), lum(bg)].sort((m, n) => n - m); return (u + 0.05) / (v + 0.05); };
  return c(a) >= c(b) ? a : b;
};

export type Recipe = "lead-hero" | "sans-serif" | "marker";
export interface Phrase { runs: Run[]; recipe: Recipe; emphasis?: string }

/** A phrase from a plain text. English only (a Telugu text keeps the classic layer), 2 to 10 words. The recipe is a seeded pick among those that fit the text; the same text and seed give the same runs. */
export function makeRuns(text: string, o: { mark?: string; seed: string | number; colors: KitColors }): Phrase | null {
  const words = wordsOf(text);
  if (words.length < 2 || words.length > 10 || isIndic(text) || /[^\x20-\x7E‘-”–—…]/.test(text)) return null;
  const c = o.colors;
  const hero = pickHero(words, o.mark);
  const recipes: Recipe[] = words.length >= 3 ? ["lead-hero", "sans-serif", "marker"] : ["sans-serif", "marker"];
  const recipe = recipes[hash(`${o.seed}:${text}`) % recipes.length];
  const cut = (a: number, b: number) => words.slice(a, b).join(" ");
  const runs: Run[] = [];
  const add = (r: Run) => { if (r.text) runs.push(r); };
  if (recipe === "lead-hero") {
    add({ text: cut(0, hero), scale: 0.5, weight: 600, color: c.dim });
    add({ text: words[hero], scale: 1.6, weight: 800, color: c.accent, hlColor: readable(c.accent) });      // if the keyword is also marked (a highlighter box in the accent), the text turns to the colour that reads on it
    add({ text: cut(hero + 1, words.length), scale: 0.5, weight: 600, color: c.dim });
    return { runs, recipe };
  }
  if (recipe === "sans-serif") {
    const n = words.length >= 4 ? 2 : 1;
    add({ text: cut(0, words.length - n), weight: 800, color: c.fg });
    add({ text: cut(words.length - n, words.length), font: "serif", italic: true, weight: 400, scale: 1.18, color: c.fg });
    return { runs, recipe };
  }
  add({ text: cut(0, hero), weight: 800, color: c.fg });
  add({ text: words[hero], weight: 800, color: c.fg, hl: true, hlColor: readable(c.accent) });
  add({ text: cut(hero + 1, words.length), weight: 800, color: c.fg });
  return { runs, recipe, emphasis: "stroke" };
}
