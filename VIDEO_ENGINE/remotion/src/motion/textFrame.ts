import type { CSSProperties } from "react";
import type { FontKind } from "../fonts";
import { type Dir, EASE, breakLines, clamp01, fitSize, graphemes, isIndic, prog, rnd } from "./core";
import { type Run, layoutPhrase } from "./phrase";
import { EMPHASIS_PRESETS, EXIT_PRESETS, type TextPreset, TEXT_PRESETS, easeFor } from "./textPresets";

export interface TextParams {
  text: string;
  preset?: string;
  exit?: string;
  emphasis?: string;
  at: number;            // seconds on the audio timeline: the entrance starts
  dur?: number;          // seconds of one unit's entrance (preset default)
  until?: number;        // seconds on the audio timeline: the exit starts (never = stays)
  exitDur?: number;
  size: number;          // font size px
  fontId?: string;       // a registered font of the Resource Library (its stack ends with the default one); fontSha = the hash the layer was built with
  fontSha?: string;
  weight?: number;
  maxWidth: number;      // px
  maxLines?: number;
  dir?: Dir;
  k?: number;            // intensity
  seed?: string | number;
  stagger?: number;      // frames between units (preset default)
  mark?: string;         // important words (space separated)
  emphasisAt?: number[]; // seconds the marked words are spoken (one per marked word, in order)
  accent: string;
  color?: string;
  fps: number;
  font?: FontKind;       // the style kit's family for the whole text (English only)
  runs?: Run[];          // a phrase (motion/phrase.ts): words with their own font, size, colour and marker; `text` is the same words joined. Word presets only (any other preset becomes word-reveal).
  flat?: boolean;        // no soft shadow (a light background)
}

interface CharF { text: string; style: CSSProperties }
export interface WordF { text: string; style: CSSProperties; chars?: CharF[]; marked: boolean; e: number; emph: CSSProperties; emphDeco?: "underline" | "stroke" | "mask"; run?: Run }
export interface LineF { style: CSSProperties; words: WordF[] }
export interface TextFrame {
  preset: TextPreset;
  exitId: string;
  size: number;
  lines: LineF[];
  block: CSSProperties;
  blockP: number;                 // entrance progress of the block (for decorations)
  deco: { kind?: TextPreset["deco"]; u: number; sweep: number; caret: { on: boolean; after: number } };
  enterEnd: number;               // frame where the last unit has finished entering
  hidden: boolean;                // before the entrance (nothing is drawn) or after the exit
}

const clean = (w: string) => w.toLowerCase().replace(/[^\wఀ-౿]/g, "");
/** Resolve a preset id; a preset that is unsuitable for this text (Telugu with per-letter motion) falls back along its `fallback` chain. */
export function resolvePreset(id: string | undefined, text: string): TextPreset {
  let p = TEXT_PRESETS[id ?? ""] ?? TEXT_PRESETS["cinematic-fade"];
  for (let i = 0; i < 4 && isIndic(text) && !p.indic; i++) p = TEXT_PRESETS[p.fallback] ?? TEXT_PRESETS["cinematic-fade"];
  return p;
}

/** Everything that is drawn for a text at one frame: pure, deterministic, no DOM. */
export function textFrame(a: TextParams, frame: number): TextFrame {
  const preset0 = resolvePreset(a.preset, a.text);
  const preset = a.runs && preset0.unit !== "word" ? TEXT_PRESETS["word-reveal"] : preset0;       // a phrase is revealed word by word
  const weight = a.weight ?? 800;
  const pl = a.runs ? layoutPhrase(a.runs, a.size, weight, a.maxWidth, a.maxLines ?? 3) : null;
  const size = pl ? pl.size : fitSize(a.text, a.size, weight, a.maxWidth, a.maxLines ?? 3);
  const lineWords = pl ? pl.lines.map((l) => l.map((w) => w.text)) : breakLines(a.text, size, weight, a.maxWidth);
  const dir = a.dir ?? "up";
  const k = a.k ?? 1;
  const seed = a.seed ?? a.text;
  const start = a.at * a.fps;
  const durF = (a.dur ?? preset.dur) * a.fps;
  const stagger = a.stagger ?? preset.stagger;
  const nWords = lineWords.reduce((s, l) => s + l.length, 0);
  const wordChars = lineWords.map((l) => l.map((w) => graphemes(w)));
  const nChars = wordChars.reduce((s, l) => s + l.reduce((q, w) => q + w.length, 0), 0);
  const n = preset.unit === "block" ? 1 : preset.unit === "line" ? lineWords.length : preset.unit === "word" ? nWords : nChars;
  const unitP = (i: number) => easeFor(preset, prog(frame, start + i * stagger, durF));
  const ctx = (i: number, p: number) => ({ p, i, n, dir, k, r: rnd(seed, i), r2: rnd(seed, i + 7919), size });
  const enterEnd = start + (n - 1) * stagger + durF;

  // keyword emphasis: the marked words, in order, each starting when it is spoken (or when the text has finished entering)
  const marks = (a.mark ?? "").trim().split(/\s+/).map(clean).filter(Boolean);
  const emph = EMPHASIS_PRESETS[a.emphasis ?? "scale"] ?? EMPHASIS_PRESETS.scale;
  let markNo = 0, wi = 0, ci = 0;
  const lines: LineF[] = lineWords.map((ws, li) => ({
    style: preset.unit === "line" ? preset.enter(ctx(li, unitP(li))) : {},
    words: ws.map((w, k2) => {
      const cw = clean(w);
      const run = pl?.lines[li][k2].run;
      const marked = !!run?.hl || (!!cw && marks.some((m) => cw.includes(m) || m.includes(cw)));
      let e = 0, emphStyle: CSSProperties = {};
      if (marked) {
        const te = a.emphasisAt?.[markNo] ?? enterEnd / a.fps;
        markNo++;
        e = EASE.outCubic(prog(frame, te * a.fps, 0.45 * a.fps));
        emphStyle = emph.apply(e, { accent: a.accent, size, k, chars: graphemes(cw).length });
        if (run?.hlColor && e > 0.6) emphStyle = { ...emphStyle, color: run.hlColor };       // the text colour that reads on the marker
      }
      const word: WordF = { text: w, marked, e, emph: emphStyle, emphDeco: marked ? emph.deco : undefined, style: preset.unit === "word" ? preset.enter(ctx(wi, unitP(wi))) : {}, ...(run ? { run } : {}) };
      if (preset.unit === "char") word.chars = wordChars[li][k2].map((g) => { const s = preset.enter(ctx(ci, unitP(ci))); ci++; return { text: g, style: s }; });
      wi++;
      return word;
    }),
  }));

  // block level: the entrance (block presets) and the exit
  const blockP = preset.unit === "block" ? unitP(0) : clamp01(prog(frame, start, enterEnd - start));
  const block: CSSProperties = preset.unit === "block" ? preset.enter(ctx(0, blockP)) : {};
  const exitId = a.exit && EXIT_PRESETS[a.exit] ? a.exit : "fade-out";
  let hidden = frame < start - 0.001;
  if (a.until !== undefined) {
    const q = EASE.inOutSine(prog(frame, a.until * a.fps, (a.exitDur ?? 0.5) * a.fps));
    if (q > 0) Object.assign(block, mergeExit(block, EXIT_PRESETS[exitId].exit(q, { dir, k, size })));
    if (q >= 1) hidden = true;
  }
  const endF = enterEnd;
  const caretOn = preset.deco === "caret" && frame >= start && frame < endF + 1.6 * a.fps && (frame < endF || Math.floor((frame - endF) / (0.5 * a.fps)) % 2 === 0);
  return {
    preset, exitId, size, lines, block, blockP, enterEnd, hidden,
    deco: {
      kind: preset.deco, u: EASE.outQuart(prog(frame, endF - 0.15 * a.fps, 0.6 * a.fps)), sweep: prog(frame, endF + 0.1 * a.fps, 0.9 * a.fps),
      caret: { on: caretOn, after: Math.min(nChars, Math.floor(Math.max(0, frame - start) / Math.max(0.0001, stagger)) + 1) },
    },
  };
}

/** The exit adds to the entrance style (opacity multiplies, transforms are joined). */
function mergeExit(b: CSSProperties, x: CSSProperties): CSSProperties {
  const o: CSSProperties = { ...x };
  if (b.opacity !== undefined && x.opacity !== undefined) o.opacity = Number(b.opacity) * Number(x.opacity);
  if (b.transform && x.transform) o.transform = `${b.transform} ${x.transform}`;
  if (b.filter && x.filter && b.filter !== "none" && x.filter !== "none") o.filter = `${b.filter} ${x.filter}`;
  return o;
}

