import theme from "../theme.json";
import { DIRS, type Box, type Dir, graphemes, hash, isIndic, wordsOf } from "./core";
import { REGION_BOX, type Rect } from "./diagram";
import { GFX_PRESETS } from "./graphics";
import { EMPHASIS_IDS, EXIT_PRESETS, TEXT_PRESETS } from "./textPresets";

/** Everything the selection may look at. All of it comes from the scene plan / transcript: no clock, no Math.random. */
export interface SceneFacts {
  id: number;
  seed: string | number;
  role: "headline" | "caption" | "label" | "quote";
  text: string;
  importance: number;          // 0..1: how much this scene matters (a keyword was spoken, a number, the first/last scene ...)
  mood: string;
  pattern: string;
  duration: number;            // seconds
  tall: boolean;               // 9:16
  prev?: Choice;               // what the previous scene used: never repeated
  motionOnly?: boolean;        // Use Images = OFF: there is no picture, so the decorations carry the scene (more of them, an atmosphere layer always)
  intents?: string[];          // the motion hints of the Visual Plan for this scene (show_flow_direction, travel_along_path ...): they decide which placed graphic is used
  textRegions?: string[];      // the Visual Plan regions of the scene's texts and labels (lower_safe_area ...): a placed graphic is kept clear of them
  textBoxes?: Rect[];          // where the renderer really draws the scene's texts [x0, y0, x1, y1] (build_composition drawnBox): kept clear as well
}
export interface DecorItem { preset: string; box: Box; boxTall?: Box; bleed?: boolean; start: number; k?: number; dir?: Dir; label?: string; value?: number; why?: string }
export interface Choice {
  text: { preset: string; exit: string; emphasis: string; dir: Dir; k: number; reason: string };
  decor: DecorItem[];
}

// ---------- text pools ----------
const CALM = ["cinematic-fade", "blur-reveal", "scale-reveal", "mask-reveal", "wipe", "directional-reveal", "tracking-compress", "line-reveal", "layered-depth", "gradient-sweep", "underline-draw", "clip-reveal", "outline-to-solid", "slide-up", "tracking-expand", "word-reveal"];
const BOLD = ["zoom-in", "elastic", "bounce", "rotate-in", "split-reveal", "kinetic", "split-reassemble", "flip-x", "char-scale", "word-pop", "zoom-out", "flip-y", "char-drop", "char-rotate"];
const POOLS: Record<SceneFacts["role"], { calm: string[]; bold: string[] }> = {
  headline: { calm: CALM, bold: BOLD },
  caption: { calm: ["word-reveal", "line-fade", "cinematic-fade", "blur-reveal", "word-blur", "slide-up", "typewriter", "line-reveal"], bold: ["word-pop", "word-slide", "char-reveal", "slide-left", "slide-right", "scale-reveal"] },
  label: { calm: ["slide-left", "mask-reveal", "wipe", "scale-reveal", "line-slide", "cinematic-fade"], bold: ["slide-right", "elastic", "word-pop", "directional-reveal", "slide-left"] },
  quote: { calm: ["line-fade", "line-reveal", "word-reveal", "cinematic-fade", "tracking-compress", "line-cascade", "blur-reveal"], bold: ["typewriter", "line-cascade", "word-slide", "mask-reveal"] },
};
const EXIT_FOR: [RegExp, string][] = [[/^slide|^line-slide|^word-slide/, "slide-out"], [/blur/, "blur-out"], [/^scale|^zoom-out|^elastic|^rotate/, "scale-out"], [/^zoom-in/, "grow-out"], [/wipe|mask|clip|reveal/, "wipe-out"], [/tracking/, "tracking-out"], [/bounce|drop/, "drop-out"]];

/** Is this preset a sensible choice for this text? (Telugu never gets per-letter motion; very long text never gets a big dramatic entrance.) */
export function suitable(id: string, text: string): boolean {
  const p = TEXT_PRESETS[id];
  if (!p) return false;
  const chars = graphemes(text).length, words = wordsOf(text).length, indic = isIndic(text);
  if (indic && !p.indic) return false;
  if (p.unit === "char" && (chars > 36 || words > 6)) return false;
  if (id === "typewriter" && chars > 60) return false;
  if ((id === "kinetic" || id === "split-reassemble") && chars > 24) return false;
  if (["flip-x", "flip-y", "rotate-in", "bounce", "elastic", "zoom-in", "zoom-out"].includes(id) && words > 8) return false;
  if (p.unit === "line" && words < 3) return false;
  if (id === "split-reveal" && words > 6) return false;
  return true;
}

const pick = <T,>(list: T[], seed: string | number): T => list[hash(seed) % list.length];

/** Choose the text preset for a scene: bold for important short text, calm for the rest; never the previous scene's preset; always a suitable one. */
export function chooseText(f: SceneFacts): Choice["text"] {
  const pool = POOLS[f.role];
  const bold = f.importance >= 0.65;
  const first = bold ? pool.bold : pool.calm;
  const rest = bold ? pool.calm : pool.bold;
  const prev = f.prev?.text.preset;
  const tryList = (list: string[], tag: string) => {
    const ok = list.filter((id) => id !== prev && suitable(id, f.text));
    return ok.length ? { id: pick(ok, `${f.seed}:${f.id}:${tag}`), tag } : null;
  };
  const got = tryList(first, bold ? "bold" : "calm") ?? tryList(rest, "alt") ?? { id: "cinematic-fade", tag: "fallback" };
  const preset = got.id;
  const exit = EXIT_FOR.find(([re]) => re.test(preset))?.[1] ?? "fade-out";
  const emphList = (f.importance >= 0.7 ? ["mask", "scale", "glow", "stroke"] : ["underline", "color", "pulse", "tracking"]).filter((e) => EMPHASIS_IDS.includes(e) && !(e === "tracking" && isIndic(f.text)));
  const emphasis = pick(emphList, `${f.seed}:${f.id}:emph`);
  const dirFixed = preset.match(/^slide-(left|right|up|down)$/)?.[1] as Dir | undefined;
  return { preset, exit: EXIT_PRESETS[exit] ? exit : "fade-out", emphasis, dir: dirFixed ?? pick(DIRS, `${f.seed}:${f.id}:dir`), k: Math.round((0.7 + 0.6 * f.importance) * 100) / 100, reason: got.tag };
}

// ---------- decoration pools ----------
const SCI = /ai|space|data|science|tech|future|robot|planet|mars|moon|earth|orbit|cyber|signal|radar|quantum/i;
const MAPS = /map|route|region|country|border|war|geo|trade|city|migration/i;
const DRAMA = /dramatic|tense|dark|war|crisis|epic|danger/i;
const POOL_CALM = ["corner-accents", "divider-grow", "underline-sweep", "light-sweep", "dust", "bracket-frame", "frame-in", "double-line", "dots-grid", "floating-dots"];
const POOL_SCI = ["hud-brackets", "scan-line", "radar-sweep", "targeting-ring", "line-network", "data-ticks", "crosshair", "node-network", "grid-lines", "ring-pulse"];
const POOL_MAP = ["route-line", "map-pin-drop", "location-callout", "dots-grid", "dashed-flow", "concentric-rings"];
const POOL_DRAMA = ["vignette-focus", "light-sweep", "glow-orb", "particles-float", "double-line", "corner-accents"];
/** Where each decoration sits (fractions of the frame; boxTall for 9:16). Kept away from the headline band and the caption strip. */
export const SLOT: Record<string, { box: Box; boxTall?: Box; bleed?: boolean }> = {
  "corner-accents": { box: [0.04, 0.06, 0.92, 0.8], boxTall: [0.05, 0.05, 0.9, 0.74] }, "frame-in": { box: [0.04, 0.06, 0.92, 0.8], boxTall: [0.05, 0.05, 0.9, 0.74] },
  "bracket-frame": { box: [0.06, 0.3, 0.88, 0.3], boxTall: [0.06, 0.28, 0.88, 0.26] }, "hud-brackets": { box: [0.05, 0.07, 0.9, 0.78], boxTall: [0.05, 0.06, 0.9, 0.72] },
  "divider-grow": { box: [0.35, 0.16, 0.3, 0.03], boxTall: [0.3, 0.14, 0.4, 0.02] }, "underline-sweep": { box: [0.3, 0.6, 0.4, 0.03], boxTall: [0.15, 0.58, 0.7, 0.02] }, "double-line": { box: [0.3, 0.16, 0.4, 0.04], boxTall: [0.2, 0.14, 0.6, 0.03] },
  "data-ticks": { box: [0.1, 0.8, 0.8, 0.06], boxTall: [0.1, 0.72, 0.8, 0.03] }, "dashed-flow": { box: [0.1, 0.16, 0.8, 0.02], boxTall: [0.1, 0.14, 0.8, 0.015] },
  "radar-sweep": { box: [0.74, 0.08, 0.2, 0.36], boxTall: [0.62, 0.06, 0.32, 0.17] }, "targeting-ring": { box: [0.74, 0.08, 0.2, 0.36], boxTall: [0.64, 0.06, 0.3, 0.16] },
  "crosshair": { box: [0.76, 0.1, 0.16, 0.28], boxTall: [0.68, 0.06, 0.26, 0.14] }, "ring-pulse": { box: [0.76, 0.1, 0.16, 0.28], boxTall: [0.66, 0.06, 0.28, 0.15] },
  "node-network": { box: [0.62, 0.06, 0.32, 0.3], boxTall: [0.5, 0.05, 0.44, 0.16] }, "grid-lines": { box: [0.62, 0.06, 0.32, 0.3], boxTall: [0.5, 0.05, 0.44, 0.16] },
  "dots-grid": { box: [0.66, 0.08, 0.28, 0.2], boxTall: [0.54, 0.05, 0.4, 0.1] }, "concentric-rings": { box: [0.76, 0.1, 0.16, 0.28], boxTall: [0.66, 0.06, 0.28, 0.15] },
  "route-line": { box: [0.1, 0.12, 0.3, 0.2], boxTall: [0.08, 0.06, 0.5, 0.12] }, "map-pin-drop": { box: [0.8, 0.08, 0.1, 0.28], boxTall: [0.78, 0.05, 0.14, 0.14] },
  "location-callout": { box: [0.06, 0.1, 0.34, 0.16], boxTall: [0.06, 0.05, 0.6, 0.09] }, "floating-dots": { box: [0, 0, 1, 1], bleed: true },
  "scan-line": { box: [0, 0, 1, 1], bleed: true }, "line-network": { box: [0, 0, 1, 1], bleed: true }, dust: { box: [0, 0, 1, 1], bleed: true },
  "light-sweep": { box: [0, 0, 1, 1], bleed: true }, "vignette-focus": { box: [0, 0, 1, 1], bleed: true }, "glow-orb": { box: [0.3, 0.2, 0.4, 0.6], bleed: true },
  "particles-float": { box: [0, 0, 1, 1], bleed: true },
};

// ---------- placed graphics keep clear of the planned texts ----------
const pct = (s: string) => parseFloat(s) / 100;
/** Where a Visual Plan text region is on this aspect's frame: the 9:16 caption and label bands follow theme.json, as backend/visual_planning.region_box does. The other
 *  regions keep their 16:9 box, which is at most larger than the backend's 9:16 box (that one only cuts the phone-UI strip): clear here is clear there. */
export function textRect(region: string, tall: boolean): Rect | null {
  const b = REGION_BOX[region];
  if (!b || region === "full_frame" || !tall) return b ?? null;
  const P = theme.portrait;
  if (region === "lower_safe_area") { const y1 = 1 - pct(P.captionBottom); return [b[0], y1 - (b[3] - b[1]), b[2], y1]; }
  if (region === "upper_safe_area") { const y0 = pct(P.labelTop); return [b[0], y0, b[2], y0 + (b[3] - b[1])]; }
  return b;
}
const MAX_SHARE = 0.25;                                     // the Layout Validator's limit (backend/motion_planning.py rule graphic_clear_of_text)
const covers = (b: Box, t: Rect): boolean => {
  const ov = Math.max(0, Math.min(b[0] + b[2], t[2]) - Math.max(b[0], t[0])) * Math.max(0, Math.min(b[1] + b[3], t[3]) - Math.max(b[1], t[1]));
  const small = Math.min(b[2] * b[3], (t[2] - t[0]) * (t[3] - t[1]));
  return small > 0 && ov / small > MAX_SHARE;
};
/** A placed graphic's box in this scene: its own slot when no planned text lies under it, else the nearest clear spot of the same size inside the safe frame (then of 3/4 size), else null (then
 *  another graphic is chosen). A full-frame graphic (bleed) or one that covers half the frame or more (a frame) keeps its slot, as the Layout Validator does. */
export function placeClear(id: string, f: SceneFacts): Box | null {
  const s = SLOT[id];
  const own = (f.tall ? s.boxTall : undefined) ?? s.box;
  if (s.bleed || own[2] * own[3] >= 0.5) return own;
  const texts = [...(f.textRegions ?? []).map((r) => textRect(r, f.tall)).filter((r): r is Rect => !!r), ...(f.textBoxes ?? [])];
  const clear = (b: Box) => !texts.some((t) => covers(b, t));
  if (clear(own)) return own;
  const m = 0.05, bottom = f.tall ? 1 - pct(theme.portrait.lowerThirdBottom) : 1 - m;            // 9:16: above the phone-UI and caption strip
  const r3 = (v: number) => Math.round(v * 1000) / 1000;
  const steps = (lo: number, hi: number, at: number) => (hi < lo ? [] : [...new Set([...Array.from({ length: Math.floor((hi - lo) / 0.05) + 1 }, (_, i) => r3(lo + i * 0.05)), r3(hi)])])
    .sort((a, b) => Math.abs(a - at) - Math.abs(b - at));                                      // every 5 % plus the far edge (a gap that ends between two steps is still found)
  for (const k of [1, 0.75]) {                                                                  // the same size first; a 3/4 size when the frame has no clear spot that large
    const [x0, y0] = own, w = r3(own[2] * k), h = r3(own[3] * k);
    for (const y of steps(m, r3(bottom - h), y0)) for (const x of steps(m, r3(1 - m - w), x0)) if (clear([x, y, w, h])) return [x, y, w, h];
  }
  return null;
}
const placed = (id: string, b: Box, tall: boolean) => ({ preset: id, ...SLOT[id], ...(tall ? { boxTall: b } : { box: b }) });

/** Which placed graphics say what a Visual Plan motion hint means (only presets that have a placement and exist in the library). */
const INTENT_POOLS: [RegExp, string[]][] = [
  [/flow|travel|route|path|journey|signal|direction/i, ["route-line", "dashed-flow"]],
  [/connect|link|relat|network|sequence|structure/i, ["node-network", "grid-lines"]],
  [/emphas|highlight|focus|attention|key|spotlight/i, ["targeting-ring", "crosshair", "ring-pulse"]],
  [/locat|place|pin|where|map/i, ["map-pin-drop", "location-callout"]],
  [/measure|data|progress|growth|count|scale|compare/i, ["data-ticks", "concentric-rings"]],
];
/** The placed graphics the scene's motion hints ask for, in the order of the hints; empty when the hints say nothing the library can draw. */
export function intentPool(intents: string[] | undefined): { preset: string; why: string; rank: number }[] {
  const out: { preset: string; why: string; rank: number }[] = [];
  (intents ?? []).forEach((intent, rank) => { for (const [re, list] of INTENT_POOLS) if (re.test(intent)) for (const id of list) if (SLOT[id] && !SLOT[id].bleed && GFX_PRESETS[id] && !out.some((o) => o.preset === id)) out.push({ preset: id, why: `hint:${intent}`, rank }); });
  return out;
}
/** Of the usable graphics, the ones the FIRST hint that has any asks for (the first hint is the scene's main motion intent); all of them when none is hinted. */
const bestHinted = (ids: string[], hinted: { preset: string; rank: number }[]): string[] => {
  const ranks = ids.map((id) => hinted.find((h) => h.preset === id)?.rank).filter((r): r is number => r !== undefined);
  if (!ranks.length) return ids;
  const best = Math.min(...ranks);
  return ids.filter((id) => hinted.find((h) => h.preset === id)?.rank === best);
};
const NO_DECOR = new Set(["grid_four", "collage_five", "triple_stack", "split_two", "timeline", "chart_focus"]);

/** Choose at most two decorations that fit the scene: HUD for science, route/pins for maps, light and depth for drama, quiet frames and lines otherwise. */
export function chooseDecor(f: SceneFacts): DecorItem[] {
  if (f.motionOnly) return chooseMotionOnlyDecor(f);
  if (f.duration < 2.4 || NO_DECOR.has(f.pattern)) return [];
  const probe = `${f.mood} ${f.pattern} ${f.text}`;
  const hinted = intentPool(f.intents);
  const pool = hinted.length ? [...hinted.map((h) => h.preset), ...POOL_CALM] : MAPS.test(`${f.pattern} ${f.mood}`) ? POOL_MAP : DRAMA.test(f.mood) ? POOL_DRAMA : SCI.test(probe) ? POOL_SCI : POOL_CALM;
  const prev = new Set(f.prev?.decor.map((d) => d.preset) ?? []);
  const known = pool.filter((id) => SLOT[id] && GFX_PRESETS[id] && placeClear(id, f));
  const fresh = known.filter((id) => !prev.has(id));
  const list = fresh.length ? fresh : known;
  const n = f.importance >= 0.55 && f.duration >= 4 ? 2 : 1;
  const out: DecorItem[] = [];
  for (let i = 0; i < n; i++) {
    const rest = list.filter((id) => !out.some((d) => d.preset === id));
    if (!rest.length) break;
    // the second decoration is of the other kind: a placed graphic with an atmosphere layer, never two of the same placement
    const diff = i === 0 ? rest : rest.filter((id) => !!SLOT[id].bleed !== !!SLOT[out[0].preset].bleed);
    const hintFirst = i === 0 ? bestHinted(rest.filter((id) => hinted.some((h) => h.preset === id)), hinted) : [];     // the first decoration is the one the first hint asks for
    const id = pick(hintFirst.length ? hintFirst : diff.length ? diff : rest, `${f.seed}:${f.id}:decor${i}`);
    out.push({ ...placed(id, placeClear(id, f)!, f.tall), why: hinted.find((h) => h.preset === id)?.why ?? "topic", start: 0.15 + 0.45 * i, k: Math.round((0.8 + 0.4 * f.importance) * 100) / 100, dir: pick(DIRS, `${f.seed}:${f.id}:dd${i}`) });
  }
  return out;
}

// ---------- Use Images = OFF ----------
const ATMOSPHERE = ["particles-float", "floating-dots", "line-network", "light-sweep", "glow-orb", "dust", "scan-line", "vignette-focus"];
const ACCENT_LINES = ["corner-accents", "divider-grow", "underline-sweep", "double-line", "bracket-frame", "frame-in"];

/**
 * Without pictures the scene is carried by its graphics: always one full-frame atmosphere layer (it moves from the first frame), one placed graphic that
 * fits the topic (HUD / route / ring) and, in a scene of 2.5 s or more, one frame or line that draws itself. Never the previous scene's graphics again.
 */
function chooseMotionOnlyDecor(f: SceneFacts): DecorItem[] {
  if (f.duration < 0.8) return [];
  const probe = `${f.mood} ${f.pattern} ${f.text}`;
  const topic = MAPS.test(`${f.pattern} ${f.mood}`) ? POOL_MAP : DRAMA.test(f.mood) ? POOL_DRAMA : SCI.test(probe) ? POOL_SCI : POOL_CALM;
  const prev = new Set(f.prev?.decor.map((d) => d.preset) ?? []);
  const usable = (list: string[], bleed: boolean) => {
    const ok = list.filter((id) => SLOT[id] && GFX_PRESETS[id] && !!SLOT[id].bleed === bleed && placeClear(id, f));
    const fresh = ok.filter((id) => !prev.has(id));
    return fresh.length ? fresh : ok;
  };
  const hinted = intentPool(f.intents);
  const kinds: [string[], boolean][] = [[[...ATMOSPHERE, ...topic], true], [hinted.length ? hinted.map((h) => h.preset) : topic, false], ...(f.duration >= 2.5 ? [[ACCENT_LINES, false] as [string[], boolean]] : [])];
  const out: DecorItem[] = [];
  kinds.forEach(([list, bleed], i) => {
    const free = usable(list, bleed).filter((id) => !out.some((d) => d.preset === id));
    const left = !bleed && i === 1 ? bestHinted(free, hinted) : free;          // the placed graphic is the one the scene's first motion hint asks for
    if (!left.length) return;
    const id = pick(left, `${f.seed}:${f.id}:mo${i}`);
    out.push({ ...placed(id, placeClear(id, f)!, f.tall), why: bleed ? "atmosphere" : i === 1 ? (hinted.find((h) => h.preset === id)?.why ?? "topic") : "accent", start: 0.05 + 0.3 * i, k: Math.round((0.9 + 0.4 * f.importance) * 100) / 100, dir: pick(DIRS, `${f.seed}:${f.id}:mod${i}`) });
  });
  return out;
}

export const choose = (f: SceneFacts): Choice => ({ text: chooseText(f), decor: chooseDecor(f) });
