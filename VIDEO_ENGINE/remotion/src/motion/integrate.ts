import type { LayerT, SceneT } from "../schema";
import type { KitLook } from "../styleKit";
import { hash } from "./core";
import { makeRuns } from "./phrase";
import { type Choice, type SceneFacts, choose, chooseDecor, chooseText } from "./select";
import type { MItem } from "./layout";
import { TEXT_PRESETS } from "./textPresets";

const PHRASE_PRESETS = ["word-reveal", "word-slide", "word-pop", "word-blur"];      // word-unit presets of the library: a phrase is revealed word by word

/** Text layers the classic patterns create. lower-third stays classic (its accent bar is part of its design); the other styles get a motion preset. */
const TEXT_TYPES = new Set(["text", "hero_text", "hero-text", "title", "headline", "caption", "motion", "motion_graphics", "motion-graphics"]);
const ROLE: Record<string, SceneFacts["role"]> = { "big-highlight": "headline", caption: "caption", label: "label" };
const IMAGE_TYPES = new Set(["image", "stock-video"]);
const MIN_DUR = 0.25;                // seconds: no entrance or exit is shorter than this, so nothing flashes

type L = LayerT & { kind?: string; style?: string; text?: string; at?: number; dur?: number; mark?: string; enter?: { at: number }; pos?: [number, number] };

export interface RichOpts {
  tall: boolean;
  mood?: string;
  importance?: number;                 // 0..1
  prev?: Choice;                       // the previous scene's choice: not repeated
  seed?: string | number;
  /** Use Images = OFF: the picture layers are removed and the scene is carried by text, shapes, lines and graphics (a headline is made from `fallbackText` when the scene has none). */
  motionOnly?: boolean;
  fallbackText?: string;
  /** the motion hints of the Visual Plan for this scene: they choose the placed graphic (select.ts intentPool) */
  intents?: string[];
  /** the Visual Plan regions of the scene's texts and labels: a placed graphic is kept clear of them (select.ts placeClear) */
  textRegions?: string[];
  /** where the renderer draws a text layer, [x0, y0, x1, y1] fractions (build_composition drawnBox): the placed graphics are chosen clear of these boxes too */
  drawn?: (layer: unknown) => number[];
  /** pace factor: 1 = the preset durations as designed, 1.4 = every entrance, stagger and exit 40 % shorter (never below MIN_DUR seconds). Absent = unchanged output. */
  speed?: number;
  /** the scene's look from the project's style kit (src/styleKit.ts): its colours go onto the text and the graphics, and the headline becomes a phrase when the text allows it. Absent = unchanged output. */
  kit?: KitLook;
}

/** The pace factor from A2V_MOTION_SPEED, clamped to a range in which text stays readable. Default: 1.4 in motion-only mode, 1.3 with the motion library otherwise. */
export const paceFor = (raw: string | undefined, motionOnly: boolean): number => {
  const n = Number(raw);
  return raw !== undefined && raw !== "" && Number.isFinite(n) ? Math.min(2, Math.max(0.5, n)) : motionOnly ? 1.4 : 1.3;
};

const r2 = (x: number): number => Math.round(x * 100) / 100;

/** Decoration items of a scene as one `motion_scene` layer; `speed` shortens their start offsets and plays the graphics faster. */
const DARKENS = new Set(["vignette-focus"]);      // graphics that darken the frame: on a light kit look they only dirty the colour field
function addDecor(scene: SceneT, decor0: Choice["decor"], seed: string | number, speed: number, kit?: KitLook): SceneT {
  const decor = kit && !kit.dark ? decor0.filter((d) => !DARKENS.has(d.preset)) : decor0;
  if (!decor.length) return scene;
  const items: MItem[] = decor.map((d, i) => ({
    id: `${scene.id}:${d.preset}`, kind: "gfx", preset: d.preset, start: scene.start + r2(d.start / speed), box: d.box, boxTall: d.boxTall, bleed: d.bleed, k: d.k, dir: d.dir,
    seed: `${seed}:${scene.id}:${d.preset}`, z: d.bleed ? 2 : 8 + i, exitDur: r2(Math.max(MIN_DUR, 0.5 / speed)), ...(speed !== 1 ? { speed } : {}),
    ...(kit ? { color: kit.fg, accentColor: kit.accent } : {}),
  }));
  return { ...scene, layers: [...scene.layers, { type: "motion_scene", z: 8, items } as unknown as LayerT] };
}

/**
 * The "rich" version of a scene built by patterns/index.ts: its text layers become `motion_text` layers with a preset chosen from the scene's content, and
 * one `motion_scene` layer adds fitting decorations (HUD, frames, lines, light, route / pin for maps). Images, charts, maps and counters are untouched.
 * `motionOnly` (Use Images = OFF) first removes the picture layers and makes the decorations carry the scene; `speed` shortens entrances, stagger and exits.
 * Deterministic: the choice depends only on the scene id, the seed, the text and the previous scene's choice.
 */
export function richenScene(scene0: SceneT, o: RichOpts): { scene: SceneT; choice?: Choice; decor?: Choice["decor"] } {
  const seed = o.seed ?? "a2v";
  const speed = o.speed && o.speed !== 1 ? o.speed : 1;
  let scene = scene0;
  if (o.motionOnly) {
    const kept = scene.layers.filter((l) => !IMAGE_TYPES.has(l.type) && !(scene.pattern === "split_two" && l.type === "shape" && (l as L).kind === "line"));      // the divider of split_two only separates its two pictures: without them it divides nothing (it crossed the caption)
    const hasText = kept.some((l) => TEXT_TYPES.has(l.type) && ((l as L).text ?? "").trim());
    const words = (o.fallbackText ?? "").trim().split(/\s+/).filter(Boolean).slice(0, 6).join(" ");
    const headline = !hasText && words ? [{ type: "text", style: "big-highlight", text: words, at: r2(scene.start + 0.2 / speed), z: 11 } as unknown as LayerT] : [];
    scene = { ...scene, layers: [...kept, ...headline] };
  }
  const dur = scene.end - scene.start;
  const texts = scene.layers.filter((l) => TEXT_TYPES.has(l.type) && ROLE[(l as L).style ?? "caption"] && ((l as L).text ?? "").trim());
  const base = (id: number, role: SceneFacts["role"], text: string, importance: number): SceneFacts =>
    ({ id, seed, role, text, importance, mood: o.mood ?? "", pattern: scene.pattern ?? "", duration: dur, tall: o.tall, prev: o.prev, motionOnly: o.motionOnly, intents: o.intents, textRegions: o.textRegions });
  if (!texts.length) {
    if (!o.motionOnly) return { scene, choice: undefined };
    const decor = chooseDecor(base(scene.id * 10, "headline", "", o.importance ?? 0.5));
    return { scene: addDecor(scene, decor, seed, speed, o.kit), choice: o.prev ? { text: o.prev.text, decor } : undefined, decor };
  }
  const facts = (l: L, k: number): SceneFacts => base(scene.id * 10 + k, ROLE[l.style ?? "caption"], l.text ?? "", o.importance ?? (l.mark ? 0.8 : 0.5));
  const main = texts[0] as L;
  const choice = choose(facts(main, 0));
  const layers = scene.layers.map((l0): LayerT => {
    const l = l0 as L;
    const k = texts.indexOf(l0);
    if (k < 0) return l0;
    const c = k === 0 ? choice.text : chooseText({ ...facts(l, k), prev: { text: choice.text, decor: [] } });
    const at = l.at ?? l.enter?.at ?? scene.start;
    const p = TEXT_PRESETS[c.preset];
    const pace = speed !== 1 && p ? { dur: r2(Math.max(MIN_DUR, p.dur / speed)), stagger: r2(p.stagger / speed), exitDur: r2(Math.max(MIN_DUR, 0.5 / speed)) } : {};
    const out = { ...l, type: "motion_text", style: ROLE[l.style ?? "caption"], preset: c.preset, exitPreset: c.exit, emphasis: c.emphasis, dir: c.dir, k: c.k, seed: `${seed}:${scene.id}:${k}`,
      at, until: l.dur !== undefined ? at + l.dur : undefined, ...(l.mark ? { emphasisAt: [at + r2(0.25 / speed)] } : {}), ...pace } as Record<string, unknown>;
    if (o.kit) {
      Object.assign(out, { color: o.kit.fg, accent: o.kit.accent, ...(o.kit.dark ? {} : { flat: true }) });
      // the headline of the scene becomes a phrase (per-word font, size, colour, marker) when its text is a short English sentence; the other texts keep the plain layer
      const ph = k === 0 && out.style === "headline" && !l.pos ? makeRuns(l.text ?? "", { mark: l.mark, seed: `${seed}:${scene.id}`, colors: { fg: o.kit.fg, accent: o.kit.accent, dim: o.kit.dim, bg: o.kit.bg[0] } }) : null;
      if (ph) {
        const ps = ph.recipe === "marker" ? "word-reveal" : TEXT_PRESETS[c.preset]?.unit === "word" ? c.preset : PHRASE_PRESETS[hash(`${seed}:${scene.id}:ph`) % PHRASE_PRESETS.length];
        const q = TEXT_PRESETS[ps];
        Object.assign(out, { runs: ph.runs, recipe: ph.recipe, preset: ps, ...(ph.emphasis ? { emphasis: ph.emphasis } : {}),
          ...(speed !== 1 && q ? { dur: r2(Math.max(MIN_DUR, q.dur / speed)), stagger: r2(q.stagger / speed) } : {}) });
      }
    }
    return out as unknown as LayerT;
  });
  const textBoxes = o.drawn ? layers.filter((l) => l.type === "motion_text").map((l) => o.drawn!(l) as [number, number, number, number]) : [];
  const decor = textBoxes.length ? chooseDecor({ ...facts(main, 0), textBoxes }) : choice.decor;       // chosen once the texts are laid out: never on a text where it is drawn
  const final = { text: choice.text, decor };
  return { scene: addDecor({ ...scene, layers }, decor, seed, speed, o.kit), choice: final, decor };
}
