import type { LayerT, SceneT } from "../schema";
import { DEFAULT_PALETTE, roles } from "../theme";

export type PP = {
  palette?: string[];      // scene_plan.style.palette: [base, accent, secondary]
  pulses?: number[];       // times (s) of the scene's later keywords: the headline pulses when they are spoken
  start: number; end: number; files: string[];
  text?: string; text2?: string; mark?: string; icon?: string;
  number?: number; unit?: string;
  data?: { label: string; value: number }[]; kind?: "bar" | "line" | "pie";
  region?: string; highlight?: string[]; route?: [number, number][]; labels?: string[];
  colors?: [string, string]; video?: string;
  mood?: string;           // the scene's mood words from the plan: picks the background look
  textAt?: number; sceneId?: number;
  width?: number; height?: number;   // frame size; taller than wide = 9:16 layout (default 1920x1080)
};
type Cam = SceneT["camera"];
type Fn = (p: PP) => LayerT[];

const L = (o: Record<string, unknown>) => o as unknown as LayerT;
const pal = (p: PP) => roles(p.palette ?? DEFAULT_PALETTE);
/** Background look from the mood words (first match wins); an unknown or missing mood keeps the plain gradient (no field written). */
export const lookFor = (mood?: string): string | undefined =>
  /dramatic|tense|ominous|dark|serious|urgent/i.test(mood ?? "") ? "spotlight"
    : /hopeful|energetic|majestic|inspir|joy|wonder|triumph/i.test(mood ?? "") ? "mesh"
      : /calm|sad|reflective|gentle|quiet|peace/i.test(mood ?? "") ? "aurora" : undefined;
const bg = (p: PP) => { const look = lookFor(p.mood); return L({ type: "background", colors: p.colors ?? [pal(p).base, pal(p).secondary], z: 0, ...(look ? { look, seed: `bg${p.sceneId ?? 0}` } : {}) }); };
const img = (p: PP, i: number, o: Record<string, unknown> = {}) =>
  L({ type: "image", slot: `s${String(p.sceneId ?? 0).padStart(2, "0")}_${i}`, file: p.files[i] ?? null, z: 1 + i, ...o });
const txt = (p: PP, style: string, t: number, o: Record<string, unknown> = {}) =>
  L({ type: "text", style, text: p.text ?? "", mark: p.mark, at: p.textAt ?? p.start + t, z: 10, ...(p.pulses?.length ? { pulses: p.pulses } : {}), ...o });
const at = (p: PP, t: number) => p.start + t;
const focusIdx = (p: PP) => { const v = (p.data ?? []).map((d) => d.value); return v.indexOf(Math.max(...v)); };
const dur = (p: PP) => p.end - p.start;
const tall = (p: PP) => (p.height ?? 1080) > (p.width ?? 1920);   // 9:16: pixel positions below are laid out for 1080x1920

export const PATTERNS: Record<string, Fn> = {
  hero_only: (p) => [bg(p), img(p, 0, { anim: "ken-burns" })],
  hero_text: (p) => [bg(p), img(p, 0, { anim: "ken-burns" }), txt(p, "big-highlight", Math.min(1.5, dur(p) / 3))],
  hero_icon: (p) => [bg(p), img(p, 0, { anim: "ken-burns" }),
    L({ type: "icon", lucide: p.icon ?? "star", pos: tall(p) ? [900, 260] : [1560, 250], z: 10, enter: { at: at(p, 1.2), anim: "pop", dur: 0.5 } }),
    L({ type: "effect", name: "sparkle", at: at(p, 1.3), pos: tall(p) ? [900, 260] : [1560, 250], z: 11 })],
  hero_map_icon: (p) => [bg(p), img(p, 0, { anim: "ken-burns" }),
    L({ type: "map", region: p.region ?? "world", highlight: p.highlight, route: p.route, labels: p.labels, pos: "right-third", at: at(p, 1.5), z: 9 }),
    L({ type: "icon", lucide: p.icon ?? "map-pin", pos: tall(p) ? [200, 260] : [220, 220], z: 10, enter: { at: at(p, 2.2), anim: "pop", dur: 0.5 } })],
  split_two: (p) => [bg(p), img(p, 0, { pos: "left-half", anim: "ken-burns" }), img(p, 1, { pos: "right-half", anim: "ken-burns" }),
    L({ type: "shape", kind: "line", ...(tall(p) ? { from: [0, 960], to: [1080, 960] } : { from: [960, 0], to: [960, 1080] }), color: "#fff", width: 6, at: at(p, 0.4), z: 10 }),
    ...(p.text ? [txt(p, "caption", 1)] : [])],
  triple_stack: (p) => [bg(p), img(p, 0, { anim: "ken-burns" }),
    img(p, 1, { pos: "top-left", parallax: 0.3, enter: { at: at(p, 1), anim: "slide-up", dur: 0.6 } }),
    img(p, 2, { pos: "bottom-right", parallax: 0.6, enter: { at: at(p, 1.8), anim: "slide-left", dur: 0.6 } }),
    ...(p.text ? [txt(p, "caption", 2.5)] : [])],
  grid_four: (p) => [bg(p), ...[0, 1, 2, 3].map((i) =>
    img(p, i, { pos: `grid-${i}`, anim: "ken-burns", enter: { at: at(p, 0.3 + i * 0.5), anim: "pop", dur: 0.5 } })),
    ...(p.text ? [txt(p, "caption", 2.4)] : [])],
  collage_five: (p) => [bg(p), img(p, 0, { pos: "center", parallax: 0.1 }),
    img(p, 1, { pos: "top-left", parallax: 0.3, enter: { at: at(p, 0.6), anim: "slide-up", dur: 0.5 } }),
    img(p, 2, { pos: "bottom-right", parallax: 0.5, enter: { at: at(p, 1.1), anim: "slide-left", dur: 0.5 } }),
    img(p, 3, { pos: "top-right", parallax: 0.4, enter: { at: at(p, 1.6), anim: "fade", dur: 0.5 } }),
    img(p, 4, { pos: "bottom-left", parallax: 0.2, enter: { at: at(p, 2.1), anim: "fade", dur: 0.5 } })],
  stat_counter: (p) => [bg(p),
    L({ type: "effect", name: "glow", at: at(p, 0.3), dur: dur(p) - 0.5, pos: tall(p) ? [540, 700] : [960, 500], z: 1 }),
    L({ type: "counter", to: p.number ?? 0, unit: p.unit, at: p.textAt ?? at(p, 0.6), dur: 2, pos: tall(p) ? (p.data ? [540, 400] : [540, 860]) : p.data ? [560, 420] : [960, 480], z: 5 }),
    ...(p.data ? [L({ type: "chart", kind: p.kind ?? "bar", data: p.data, at: at(p, 2), box: tall(p) ? [40, 620, 1000, 760] : [900, 200, 900, 650], z: 6 })] : []),
    ...(p.text ? [txt(p, "caption", 1.2)] : [])],
  chart_focus: (p) => [bg(p),
    L({ type: "chart", kind: p.kind ?? "bar", data: p.data ?? [], at: at(p, 0.8), focus: focusIdx(p), focusAt: at(p, 2.6), z: 5 }),
    ...(p.text ? [txt(p, "label", 0.4)] : [])],
  map_route: (p) => [bg(p),
    L({ type: "map", region: p.region ?? "world", highlight: p.highlight, route: p.route, labels: p.labels, at: at(p, 0.3), z: 5 }),
    ...(p.text ? [txt(p, "lower-third", 1)] : [])],
  timeline: (p) => {
    const n = Math.max(2, p.labels?.length ?? 3);
    if (tall(p)) {   // 9:16: the line runs down the middle, labels and photos alternate left and right of it
      const ys = Array.from({ length: n }, (_, i) => 380 + (i * 1160) / (n - 1));
      return [bg(p),
        L({ type: "shape", kind: "line", from: [540, 300], to: [540, 1620], color: "#fff", width: 8, at: at(p, 0.3), dur: 1.2, z: 3 }),
        ...ys.flatMap((y, i) => [
          L({ type: "shape", kind: "circle", from: [540, y], to: [560, y], color: pal(p).accent, fill: pal(p).accent, width: 6, at: at(p, 1 + i * 0.6), dur: 0.4, z: 4 }),
          L({ type: "text", style: "label", text: p.labels?.[i] ?? "", pos: [i % 2 ? 810 : 270, y - 130], center: true, at: at(p, 1.2 + i * 0.6), z: 6 }),
          ...(p.files[i] ? [img(p, i, { pos: [i % 2 ? 90 : 590, y - 70, 400, 225], parallax: 0.1, enter: { at: at(p, 1.3 + i * 0.6), anim: "pop", dur: 0.4 } })] : []),
        ])];
    }
    const xs = Array.from({ length: n }, (_, i) => 300 + (i * 1320) / (n - 1));
    return [bg(p),
      L({ type: "shape", kind: "line", from: [160, 540], to: [1760, 540], color: "#fff", width: 8, at: at(p, 0.3), dur: 1.2, z: 3 }),
      ...xs.flatMap((x, i) => [
        L({ type: "shape", kind: "circle", from: [x, 540], to: [x + 20, 540], color: pal(p).accent, fill: pal(p).accent, width: 6, at: at(p, 1 + i * 0.6), dur: 0.4, z: 4 }),
        L({ type: "text", style: "label", text: p.labels?.[i] ?? "", pos: [x, i % 2 ? 610 : 440], center: true, at: at(p, 1.2 + i * 0.6), z: 6 }),
        ...(p.files[i] ? [img(p, i, { pos: [x - 150, i % 2 ? 130 : 690, 300, 170], parallax: 0.1, enter: { at: at(p, 1.3 + i * 0.6), anim: "pop", dur: 0.4 } })] : []),
      ])];
  },
  quote_type: (p) => [bg(p),
    L({ type: "shape", kind: "line", ...(tall(p) ? { from: [90, 640], to: [90, 960] } : { from: [120, 330], to: [120, 560] }), color: pal(p).accent, width: 12, at: at(p, 0.2), dur: 0.6, z: 3 }),
    txt(p, "big-highlight", 0.5, { pos: tall(p) ? [140, 640] : [170, 360] }),
    ...(p.text2 ? [txt({ ...p, text: p.text2, mark: undefined }, "label", 2, { pos: tall(p) ? [140, 1200] : [160, 800] })] : [])],
  object_float: (p) => [bg(p),
    L({ type: "effect", name: "glow", at: at(p, 0.2), dur: dur(p) - 0.3, pos: tall(p) ? [540, 960] : [960, 540], z: 1 }),
    img(p, 0, { pos: "small-center", anim: "float", enter: { at: at(p, 0.4), anim: "pop", dur: 0.6 } }),
    ...(p.text ? [txt(p, "caption", 1.2)] : [])],
  stock_overlay: (p) => [bg(p),
    L({ type: "stock-video", file: p.video ?? null, opacity: 0.55, z: 1 }),
    ...(p.icon ? [L({ type: "icon", lucide: p.icon, pos: tall(p) ? [540, 520] : [960, 300], z: 8, enter: { at: at(p, 0.8), anim: "pop", dur: 0.5 } })] : []),
    ...(p.text ? [txt(p, "big-highlight", 1.2)] : [])],
  before_after: (p) => [bg(p), img(p, 0, { pos: "full" }),
    img(p, 1, { pos: "full", z: 3, enter: { at: at(p, 1.5), anim: "wipe", dur: 1.4 } }),
    ...(p.text ? [txt(p, "label", 0.3)] : [])],
};

export const PATTERN_CAMERA: Record<string, Cam> = {
  hero_only: { move: "push-in", from: 1, to: 1.12, focus: [0.5, 0.45] },
  hero_text: { move: "push-in", from: 1, to: 1.1, focus: [0.6, 0.4] },
  hero_icon: { move: "pan-right", from: 1, to: 1.1, focus: [0.5, 0.5] },
  hero_map_icon: { move: "pull-out", from: 1, to: 1.12, focus: [0.5, 0.5] },
  before_after: { move: "static", from: 1, to: 1, focus: [0.5, 0.5] },
};
const STATIC: Cam = { move: "static", from: 1, to: 1, focus: [0.5, 0.5] };

export const PATTERN_NAMES = Object.keys(PATTERNS);

export function buildScene(id: number, name: string, p: PP, transition?: { type: string; dur: number }): SceneT {
  const fn = PATTERNS[name];
  if (!fn) throw new Error(`unknown pattern "${name}"`);
  return { id, start: p.start, end: p.end, pattern: name, camera: PATTERN_CAMERA[name] ?? STATIC, layers: fn({ ...p, sceneId: id }), transition_out: transition };
}
