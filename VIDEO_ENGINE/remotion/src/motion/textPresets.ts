import type { CSSProperties } from "react";
import { type Dir, type EaseName, EASE, clamp01, dirVec, lerp } from "./core";

export type Unit = "block" | "line" | "word" | "char";
export type TextCategory = "entrance" | "reveal" | "typography" | "kinetic" | "depth" | "exit";
export type Deco = "caret" | "underline" | "sweep" | "layered" | "stroke-fill" | "split";

/** What a preset sees for ONE unit (the whole block, a line, a word or a character) at one frame. p is already eased (it may overshoot 1 for back/elastic). */
export interface UnitCtx {
  p: number;      // eased entrance progress of this unit
  i: number;      // index of the unit
  n: number;      // number of units
  dir: Dir;       // direction the motion comes from
  k: number;      // intensity multiplier (1 = default)
  r: number;      // deterministic random in [0, 1) for this unit
  r2: number;     // a second independent one
  size: number;   // font size in px
}

export interface TextPreset {
  id: string;
  label: string;
  category: TextCategory;
  unit: Unit;
  /** frames between the starts of consecutive units */
  stagger: number;
  /** default length in seconds of one unit's entrance */
  dur: number;
  ease: EaseName;
  enter: (c: UnitCtx) => CSSProperties;
  deco?: Deco;
  /** false: do not use on Telugu (spacing or per-letter motion would break the shaping); `fallback` is used instead */
  indic: boolean;
  fallback: string;
  desc: string;
}

const t = (x = 0, y = 0, s = 1, r = 0) => `translate(${x.toFixed(2)}px, ${y.toFixed(2)}px) scale(${s.toFixed(4)}) rotate(${r.toFixed(3)}deg)`;
const op = (p: number, speed = 1) => clamp01(p * speed);
const blur = (px: number): string => (px > 0.05 ? `blur(${px.toFixed(2)}px)` : "none");
const inset = (dir: Dir, p: number): string => {
  const o = ((1 - clamp01(p)) * 100).toFixed(2);
  return p >= 1 ? "none" : { left: `inset(0 ${o}% 0 0)`, right: `inset(0 0 0 ${o}%)`, up: `inset(0 0 ${o}% 0)`, down: `inset(${o}% 0 0 0)` }[dir];
};
const maskDir: Record<Dir, string> = { left: "to right", right: "to left", up: "to bottom", down: "to top" };
const wipeMask = (dir: Dir, p: number, soft = 22): CSSProperties => {
  if (p >= 1) return {};
  const a = p * (100 + soft) - soft;
  const m = `linear-gradient(${maskDir[dir]}, #000 ${a.toFixed(2)}%, transparent ${(a + soft).toFixed(2)}%)`;
  return { WebkitMaskImage: m, maskImage: m } as CSSProperties;
};

const P = (id: string, label: string, category: TextCategory, unit: Unit, enter: TextPreset["enter"], o: Partial<TextPreset> & { desc: string }): TextPreset => ({
  id, label, category, unit, enter, stagger: unit === "block" ? 0 : unit === "char" ? 1.5 : unit === "word" ? 4 : 6, dur: unit === "block" ? 0.8 : 0.5,
  ease: "outCubic", indic: true, fallback: "cinematic-fade", ...o,
});

const list: TextPreset[] = [
  // ----- entrances (the whole text at once) -----
  P("cinematic-fade", "Cinematic fade", "entrance", "block", (c) => ({ opacity: op(c.p), transform: t(0, (1 - c.p) * 16 * c.k), letterSpacing: `${((1 - c.p) * 0.05 * c.k).toFixed(4)}em` }),
    { dur: 1.0, ease: "outQuart", desc: "slow fade with a small rise and tracking settle; the calm default" }),
  P("blur-reveal", "Blur reveal", "entrance", "block", (c) => ({ opacity: op(c.p, 1.5), filter: blur((1 - c.p) * 20 * c.k), transform: t(0, 0, 1 + (1 - c.p) * 0.05 * c.k) }),
    { dur: 0.9, desc: "comes into focus from a heavy blur" }),
  P("scale-reveal", "Scale reveal", "entrance", "block", (c) => ({ opacity: op(c.p, 2), transform: t(0, 0, lerp(1 - 0.18 * c.k, 1, c.p)) }),
    { dur: 0.7, ease: "outExpo", desc: "grows from slightly smaller with a fast settle" }),
  P("zoom-in", "Zoom in", "entrance", "block", (c) => ({ opacity: op(c.p, 2), filter: blur((1 - c.p) * 8 * c.k), transform: t(0, 0, 1 + (1 - c.p) * 0.9 * c.k) }),
    { dur: 0.8, ease: "outExpo", desc: "flies in from large (camera pushes through the text)" }),
  P("zoom-out", "Zoom out", "entrance", "block", (c) => ({ opacity: op(c.p, 2), filter: blur((1 - c.p) * 10 * c.k), transform: t(0, 0, lerp(0.45, 1, c.p)) }),
    { dur: 0.8, ease: "outExpo", desc: "grows from small and blurred" }),
  ...(["left", "right", "up", "down"] as Dir[]).map((d) =>
    P(`slide-${d}`, `Slide from ${d}`, "entrance", "block", (c) => {
      const v = dirVec(d);
      return { opacity: op(c.p, 2), transform: t(v.x * (1 - c.p) * c.size * 3 * c.k, v.y * (1 - c.p) * c.size * 1.6 * c.k) };
    }, { dur: 0.7, ease: "outQuart", desc: `slides in from the ${d}` })),
  P("bounce", "Bounce", "entrance", "block", (c) => ({ opacity: op(c.p, 6), transform: t(0, -(1 - c.p) * c.size * 2.2 * c.k) }),
    { dur: 0.9, ease: "outBounce", desc: "drops in and bounces to rest" }),
  P("elastic", "Elastic", "entrance", "block", (c) => ({ opacity: op(c.p, 6), transform: t(0, 0, Math.max(0, c.p)) }),
    { dur: 1.1, ease: "outElastic", desc: "scales up with an elastic overshoot" }),
  P("rotate-in", "Rotate in", "entrance", "block", (c) => ({ opacity: op(c.p, 2), transform: t(0, 0, lerp(0.8, 1, c.p), (1 - c.p) * -24 * c.k) }),
    { dur: 0.8, ease: "outBack", desc: "turns upright while scaling up" }),
  P("flip-x", "Flip (horizontal axis)", "entrance", "block", (c) => ({ opacity: c.p > 0.04 ? 1 : 0, transform: `perspective(900px) rotateX(${((1 - c.p) * 90 * c.k).toFixed(2)}deg)` }),
    { dur: 0.8, ease: "outCubic", desc: "flips up around the horizontal axis" }),
  P("flip-y", "Flip (vertical axis)", "entrance", "block", (c) => ({ opacity: c.p > 0.04 ? 1 : 0, transform: `perspective(900px) rotateY(${((1 - c.p) * -90 * c.k).toFixed(2)}deg)` }),
    { dur: 0.8, ease: "outCubic", desc: "flips around the vertical axis" }),
  // ----- reveals with masks -----
  P("mask-reveal", "Mask reveal", "reveal", "block", (c) => ({ clipPath: inset(c.dir, c.p) }), { dur: 0.8, ease: "inOutCubic", desc: "a hard-edged mask opens from one side" }),
  P("clip-reveal", "Circular clip reveal", "reveal", "block", (c) => ({ clipPath: c.p >= 1 ? "none" : `circle(${(c.p * 78).toFixed(2)}% at 50% 50%)` }),
    { dur: 0.9, ease: "inOutCubic", desc: "an iris opens from the centre" }),
  P("wipe", "Soft wipe", "reveal", "block", (c) => wipeMask(c.dir, c.p), { dur: 0.9, ease: "inOutSine", desc: "a soft-edged wipe" }),
  P("directional-reveal", "Directional reveal", "reveal", "block", (c) => {
    const v = dirVec(c.dir);
    return { clipPath: inset(c.dir, c.p), transform: t(v.x * (1 - c.p) * -c.size * 0.8, v.y * (1 - c.p) * -c.size * 0.5) };
  }, { dur: 0.9, ease: "outQuart", desc: "mask opens while the text travels with it" }),
  P("split-reveal", "Split reveal", "reveal", "block", (c) => ({ opacity: op(c.p, 3) }), { deco: "split", dur: 0.9, ease: "outQuart", desc: "the top half slides in from one side and the bottom half from the other" }),
  // ----- typography: characters (Telugu falls back to words) -----
  P("char-reveal", "Character reveal", "typography", "char", (c) => ({ opacity: op(c.p, 2), transform: t(0, (1 - c.p) * c.size * 0.35 * c.k) }), { stagger: 1.6, dur: 0.45, indic: false, fallback: "word-reveal", desc: "letters appear one after another" }),
  P("char-blur", "Character blur-in", "typography", "char", (c) => ({ opacity: op(c.p, 2), filter: blur((1 - c.p) * 10 * c.k) }), { stagger: 1.8, dur: 0.6, indic: false, fallback: "word-blur", desc: "letters sharpen one after another" }),
  P("char-drop", "Character drop", "typography", "char", (c) => ({ opacity: op(c.p, 6), transform: t(0, -(1 - c.p) * c.size * 0.9 * c.k) }), { stagger: 1.8, dur: 0.7, ease: "outBounce", indic: false, fallback: "word-pop", desc: "letters drop and bounce" }),
  P("char-rotate", "Character rotate", "typography", "char", (c) => ({ opacity: op(c.p, 3), transform: t(0, 0, lerp(0.6, 1, c.p), (c.r - 0.5) * 80 * (1 - c.p) * c.k) }), { stagger: 1.6, dur: 0.6, ease: "outBack", indic: false, fallback: "word-pop", desc: "each letter turns into place from its own angle" }),
  P("char-scale", "Character pop", "typography", "char", (c) => ({ opacity: op(c.p, 4), transform: t(0, 0, Math.max(0, c.p)) }), { stagger: 1.6, dur: 0.55, ease: "outBack", indic: false, fallback: "word-pop", desc: "letters pop up with a small overshoot" }),
  P("typewriter", "Typewriter", "typography", "char", (c) => ({ opacity: c.p > 0 ? 1 : 0 }), { deco: "caret", stagger: 2.2, dur: 0.001, ease: "linear", indic: false, fallback: "word-reveal", desc: "letters appear instantly one by one with a blinking caret" }),
  P("kinetic", "Kinetic typography", "kinetic", "char", (c) => ({ opacity: op(c.p, 4), transform: t((c.r - 0.5) * c.size * 2.4 * (1 - c.p) * c.k, (c.r2 - 0.5) * c.size * 2.4 * (1 - c.p) * c.k, lerp(0.4 + c.r * 0.6, 1, c.p), (c.r2 - 0.5) * 120 * (1 - c.p) * c.k) }),
    { stagger: 1.2, dur: 0.8, ease: "outBack", indic: false, fallback: "word-pop", desc: "letters scatter in from seeded positions and settle" }),
  P("split-reassemble", "Split and reassemble", "kinetic", "char", (c) => ({ opacity: op(c.p, 5), transform: t((c.r - 0.5) * 1400 * (1 - c.p) * c.k, (c.r2 - 0.5) * 500 * (1 - c.p) * c.k, 1, (c.r - 0.5) * 360 * (1 - c.p) * c.k) }),
    { stagger: 0.8, dur: 1.0, ease: "outExpo", indic: false, fallback: "word-slide", desc: "letters fly in from far away and reassemble into the line" }),
  P("tracking-expand", "Tracking expansion", "typography", "block", (c) => ({ opacity: op(c.p, 2), letterSpacing: `${(c.p * 0.07 * c.k).toFixed(4)}em` }), { dur: 1.2, ease: "outQuart", indic: false, fallback: "cinematic-fade", desc: "letter spacing opens up while the text fades in" }),
  P("tracking-compress", "Tracking compression", "typography", "block", (c) => ({ opacity: op(c.p, 2), letterSpacing: `${((1 - c.p) * 0.55 * c.k).toFixed(4)}em` }), { dur: 1.1, ease: "outQuart", indic: false, fallback: "cinematic-fade", desc: "wide-set letters pull together into place" }),
  // ----- typography: words and lines (safe for Telugu) -----
  P("word-reveal", "Word by word", "typography", "word", (c) => ({ opacity: op(c.p, 2), transform: t(0, (1 - c.p) * c.size * 0.4 * c.k) }), { stagger: 5, dur: 0.5, desc: "words rise in one after another" }),
  P("word-slide", "Word slide", "typography", "word", (c) => { const v = dirVec(c.dir); return { opacity: op(c.p, 2), transform: t(v.x * (1 - c.p) * c.size * 1.6 * c.k, v.y * (1 - c.p) * c.size * 0.9 * c.k) }; }, { stagger: 4, dur: 0.55, ease: "outQuart", desc: "words slide in from a side" }),
  P("word-blur", "Word blur-in", "typography", "word", (c) => ({ opacity: op(c.p, 2), filter: blur((1 - c.p) * 12 * c.k) }), { stagger: 5, dur: 0.6, desc: "words come into focus one by one" }),
  P("word-pop", "Word pop", "typography", "word", (c) => ({ opacity: op(c.p, 4), transform: t(0, 0, Math.max(0, c.p)) }), { stagger: 5, dur: 0.5, ease: "outBack", desc: "words pop with a small overshoot" }),
  P("line-reveal", "Line by line", "typography", "line", (c) => ({ opacity: op(c.p, 2), clipPath: c.p >= 1 ? "none" : `inset(0 0 ${((1 - c.p) * 100).toFixed(1)}% 0)`, transform: t(0, (1 - c.p) * c.size * 0.5) }), { stagger: 9, dur: 0.7, desc: "each line is unmasked from its top while rising" }),
  P("line-slide", "Line slide", "typography", "line", (c) => { const v = dirVec(c.dir); return { opacity: op(c.p, 2), transform: t(v.x * (1 - c.p) * c.size * 4 * c.k, v.y * (1 - c.p) * c.size * 1.2 * c.k) }; }, { stagger: 8, dur: 0.7, ease: "outQuart", desc: "lines slide in one after another" }),
  P("line-cascade", "Multi-line cascade", "typography", "line", (c) => ({ opacity: op(c.p, 2), transform: t((c.i % 2 ? 1 : -1) * (1 - c.p) * c.size * 3.5 * c.k, 0) }), { stagger: 10, dur: 0.8, ease: "outQuart", desc: "lines enter alternately from the left and the right" }),
  P("line-fade", "Staggered lines", "typography", "line", (c) => ({ opacity: op(c.p), filter: blur((1 - c.p) * 4 * c.k) }), { stagger: 14, dur: 0.9, ease: "outCubic", desc: "lines fade in with a long stagger (calm, for quotes)" }),
  // ----- depth and fills -----
  P("layered-depth", "Layered depth", "depth", "block", (c) => ({ opacity: op(c.p, 2), transform: t(0, (1 - c.p) * 14) }), { deco: "layered", dur: 1.0, ease: "outQuart", desc: "a darker accent copy sits behind and drifts with parallax" }),
  P("outline-to-solid", "Outline to solid", "depth", "block", (c) => ({ opacity: op(c.p, 6), WebkitTextStroke: `${(2.5 * (1 - clamp01((c.p - 0.55) / 0.45)) + 0.01).toFixed(2)}px currentColor`, color: `rgba(255,255,255,${clamp01((c.p - 0.5) / 0.5).toFixed(3)})` } as CSSProperties),
    { deco: "stroke-fill", dur: 1.1, ease: "linear", desc: "outlined letters fill with colour" }),
  P("gradient-sweep", "Gradient sweep", "depth", "block", (c) => ({ opacity: op(c.p, 2), transform: t(0, (1 - c.p) * 10) }), { deco: "sweep", dur: 0.8, desc: "a light band sweeps across the text after it appears" }),
  P("underline-draw", "Underline draw", "depth", "block", (c) => ({ opacity: op(c.p, 2), transform: t(0, (1 - c.p) * 12) }), { deco: "underline", dur: 0.9, ease: "outQuart", desc: "text rises in, then an underline is drawn beneath it" }),
];

export const TEXT_PRESETS: Record<string, TextPreset> = Object.fromEntries(list.map((p) => [p.id, p]));
export const TEXT_PRESET_IDS = list.map((p) => p.id);

// ---------- exits (q = eased exit progress, 0 = fully shown, 1 = gone) ----------
export interface ExitPreset { id: string; label: string; exit: (q: number, c: { dir: Dir; k: number; size: number }) => CSSProperties }
const ex = (id: string, label: string, exit: ExitPreset["exit"]): ExitPreset => ({ id, label, exit });
const exitList: ExitPreset[] = [
  ex("fade-out", "Smooth fade", (q) => ({ opacity: 1 - q })),
  ex("slide-out", "Slide out", (q, c) => { const v = dirVec(c.dir); return { opacity: 1 - q, transform: t(-v.x * q * c.size * 2 * c.k, -v.y * q * c.size) }; }),
  ex("blur-out", "Blur out", (q, c) => ({ opacity: 1 - q, filter: blur(q * 14 * c.k) })),
  ex("scale-out", "Scale out", (q, c) => ({ opacity: 1 - q, transform: t(0, 0, 1 - 0.25 * q * c.k) })),
  ex("grow-out", "Grow out", (q, c) => ({ opacity: 1 - q, transform: t(0, 0, 1 + 0.35 * q * c.k) })),
  ex("wipe-out", "Wipe out", (q, c) => wipeMask(({ left: "right", right: "left", up: "down", down: "up" } as Record<Dir, Dir>)[c.dir], 1 - q)),
  ex("tracking-out", "Tracking out", (q, c) => ({ opacity: 1 - q, letterSpacing: `${(q * 0.25 * c.k).toFixed(4)}em` })),
  ex("drop-out", "Drop out", (q, c) => ({ opacity: 1 - q * q, transform: t(0, q * q * c.size * 1.2 * c.k) })),
];
export const EXIT_PRESETS: Record<string, ExitPreset> = Object.fromEntries(exitList.map((e) => [e.id, e]));
export const EXIT_PRESET_IDS = exitList.map((e) => e.id);

// ---------- emphasis of important words (e = eased progress since the word is spoken, 0..1) ----------
export interface EmphasisPreset {
  id: string;
  label: string;
  /** style of the word's span */
  apply: (e: number, c: { accent: string; size: number; k: number; chars: number }) => CSSProperties;
  deco?: "underline" | "stroke" | "mask";
}
const em = (id: string, label: string, apply: EmphasisPreset["apply"], deco?: EmphasisPreset["deco"]): EmphasisPreset => ({ id, label, apply, deco });
const emList: EmphasisPreset[] = [
  // the word grows by 0.16 k x its width: the same room is made in the line (about 0.6 em per character, half on each side), so a neighbour is moved away instead of being covered
  em("scale", "Scale up", (e, c) => ({ display: "inline-block", transform: `scale(${(1 + 0.16 * c.k * e).toFixed(4)})`, color: c.accent, marginInline: `${(0.3 * c.chars * 0.16 * c.k * e).toFixed(3)}em` })),
  em("color", "Colour shift", (e, c) => ({ color: e > 0 ? c.accent : undefined, opacity: 1 })),
  em("underline", "Underline", () => ({}), "underline"),
  em("glow", "Glow", (e, c) => ({ color: c.accent, textShadow: `0 0 ${(26 * e * c.k).toFixed(1)}px ${c.accent}, 0 4px 18px rgba(0,0,0,0.5)` })),
  em("mask", "Colour fill", (e, c) => ({ color: "#fff", backgroundImage: `linear-gradient(90deg, ${c.accent}, ${c.accent})`, backgroundRepeat: "no-repeat", backgroundSize: `${(e * 100).toFixed(1)}% 100%`, padding: "0 0.18em", borderRadius: "0.18em" } as CSSProperties), "mask"),
  em("tracking", "Tracking", (e, c) => ({ letterSpacing: `${(0.07 * e * c.k).toFixed(4)}em`, color: c.accent })),
  em("pulse", "Pulse", (e, c) => ({ display: "inline-block", color: c.accent, transform: `scale(${(1 + 0.14 * c.k * Math.sin(Math.PI * e)).toFixed(4)})` })),
  em("stroke", "Highlighter stroke", (e) => ({ color: e > 0.6 ? "#111" : "#fff" }), "stroke"),
];
export const EMPHASIS_PRESETS: Record<string, EmphasisPreset> = Object.fromEntries(emList.map((e) => [e.id, e]));
export const EMPHASIS_IDS = emList.map((e) => e.id);

export const easeFor = (p: TextPreset, x: number): number => EASE[p.ease](clamp01(x));
