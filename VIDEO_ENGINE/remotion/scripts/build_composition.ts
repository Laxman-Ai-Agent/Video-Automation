// npx tsx scripts/build_composition.ts <projectDir>
// scene_plan.json (+ transcript for subtitle words) -> composition.json. Claude only picks patterns/params.
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { PATTERNS, buildScene, type PP } from "../src/patterns";
import { paceFor, richenScene } from "../src/motion/integrate";
import type { Choice } from "../src/motion/select";
import { breakLines, estWidth, fitSize, textRoom } from "../src/motion/core";
import { layoutPhrase } from "../src/motion/phrase";
import { kitByName, kitLook } from "../src/styleKit";
import { planDiagram, type DEl, type DRel, type DiagramOut } from "../src/motion/diagram";
import { iconsOf, tagLayers, type RegEntry } from "../src/library/registry";
import { DEFAULT_PALETTE, SAFE, layoutFor, roles } from "../src/theme";
import { TRANSITIONS, pickTransition } from "../src/transitions";

const dir = process.argv[2];
if (!dir) throw new Error("usage: build_composition.ts <projectDir> [--aspect 9:16]");
// --aspect 9:16 writes composition_9x16.json (1080x1920); the default writes composition.json (1920x1080) exactly as before
const ai = process.argv.indexOf("--aspect");
const aspect = ai > 0 ? process.argv[ai + 1] : "16:9";
if (aspect !== "16:9" && aspect !== "9:16") throw new Error(`unknown aspect "${aspect}" (16:9 or 9:16)`);
const [W, H] = aspect === "9:16" ? [1080, 1920] : [1920, 1080];
const plan = JSON.parse(readFileSync(join(dir, "scene_plan.json"), "utf-8"));
const tPath = ["transcript_fixed.json", "transcript_corrected.json", "transcript.json"].map((f) => join(dir, f)).find(existsSync);
const tr = tPath ? JSON.parse(readFileSync(tPath, "utf-8")) : null;
const audio = ["audio.mp3", "audio.wav", "audio.m4a"].find((f) => existsSync(join(dir, f))) ?? "audio.wav";
const duration: number = tr?.duration ?? plan.scenes[plan.scenes.length - 1].end;
const palette: string[] = plan.style?.palette ?? DEFAULT_PALETTE;   // roles: [base, accent, secondary]
const { base, secondary } = roles(palette);
// the Resource Library (docs/resources.md): VERIFIED registry resources may draw an icon element or a layer; the layers that use one record `resource_id` + the pinned hash. No registry = nothing changes.
// the same registry backend/resource_library.py reads: resource-library at the repo root
const regUrl = [new URL("../../../resource-library/catalog/registry.json", import.meta.url)].find((u) => existsSync(u));
const registry: RegEntry[] = regUrl ? JSON.parse(readFileSync(regUrl, "utf-8")).resources ?? [] : [];

// A2V_MOTION=1 (or --motion rich): use the motion library (src/motion). Off by default: the composition is exactly what it was before.
// --no-images (Use Images = OFF): no picture layers, the scenes are carried by text animation and motion graphics; it always uses the motion library.
const motionOnly = process.argv.includes("--no-images") || process.env.A2V_USE_IMAGES === "0";
const rich = motionOnly || process.env.A2V_MOTION === "1" || process.argv.includes("--motion");
// pace: shorter entrances / stagger / exits and shorter scene transitions (A2V_MOTION_SPEED, default 1.3 with the library and 1.4 without pictures; 1 = as designed). 30 fps stays.
const speed = rich ? paceFor(process.env.A2V_MOTION_SPEED, motionOnly) : 1;
// A2V_STYLE_KIT=<id> (`1` = editorial): the scenes change look (background, text and graphic colours) from a kit of one visual family and the headline becomes a phrase (src/styleKit.ts, src/motion/phrase.ts).
// Off by default: without it the composition is exactly what it was. It needs the motion library.
const kit = rich ? kitByName(process.env.A2V_STYLE_KIT) : undefined;
const kitSeed = plan.style?.seed ?? `${plan.scenes.length}:${plan.scenes[0]?.concept ?? plan.scenes[0]?.meaning ?? ""}`;
let prevLookId: string | undefined;
// --visual-plan (the Python side passes it only for a Visual Plan that is current): the on-screen text and the motion hints of visual_planning.json decide the text and the
// placed graphic of every scene, instead of the legacy scene plan's text and the topic alone. Without the flag nothing changes.
const vpPath = join(dir, "visual_planning.json");
const vpScenes = new Map<number, { texts: string[]; intents: string[]; els: DEl[]; rels: DRel[] }>();
if (process.argv.includes("--visual-plan") && existsSync(vpPath)) {
  for (const s of JSON.parse(readFileSync(vpPath, "utf-8")).scenes ?? []) {
    const texts: string[] = (s.elements ?? []).filter((e: any) => (e.type === "text" || e.type === "label") && typeof e.content === "string" && e.content.trim())
      .sort((a: any, b: any) => (a.placement?.priority ?? 9) - (b.placement?.priority ?? 9)).map((e: any) => e.content.trim());
    vpScenes.set(s.plan_scene_id, { texts, intents: (s.motion_hints ?? []).map((h: any) => String(h.intent ?? "")).filter(Boolean),
      els: (s.elements ?? []).map((e: any): DEl => ({ id: String(e.element_id), type: String(e.type), role: String(e.role ?? ""), required: !!e.required, desc: String(e.visual_description ?? ""), region: String(e.placement?.region ?? ""), appearance: e.appearance && typeof e.appearance === "object" ? e.appearance : undefined })),
      rels: (s.element_relationships ?? []).map((r: any): DRel => ({ source: String(r.source), target: String(r.target), relation: String(r.relation) })) });
  }
}
// --fixes (motion_fixes.json, written by "Solve warnings"): a graphic moved off the planned text, a text shown earlier so it can be read. Only these two things change, in both
// the plan and the composition, so Motion Generation still builds exactly what was planned.
type Fix = { box?: Record<string, number[]>; boxTall?: Record<string, number[]>; textAt?: Record<string, number>; emphasisAt?: Record<string, number> };
const fixes = new Map<number, Fix>();
const fxPath = join(dir, "motion_fixes.json");
if (process.argv.includes("--fixes") && existsSync(fxPath)) for (const [id, f] of Object.entries(JSON.parse(readFileSync(fxPath, "utf-8")).scenes ?? {})) fixes.set(Number(id), f as Fix);
// Where the renderer draws a text, as fractions of the frame [x0, y0, x1, y1]: the same placement rules, type scale and line breaking as `MotionTextLayer` (motion/text.tsx).
// The width is the library's own estimate (estWidth, an upper bound), not a measurement.
const lay = layoutFor(W, H);
const pct = (s: string, of: number) => (s.endsWith("%") ? (parseFloat(s) / 100) * of : parseFloat(s));
function drawnBox(t: any): number[] {
  const head = t.style === "headline" || t.style === "quote";
  const boxW = textRoom(W * (1 - 2 * SAFE) * (head || lay.portrait ? 1 : 0.7), W, SAFE, Array.isArray(t.pos) ? t.pos : undefined, t.center);      // the same width as MotionTextLayer (motion/text.tsx)
  const weight = t.style === "headline" ? 800 : 600;
  let w: number, h: number;
  if (Array.isArray(t.runs)) {                                   // a phrase: the words have their own sizes, so the box is measured with the same layout the renderer uses
    const L = layoutPhrase(t.runs, head ? lay.type.display : lay.type.body, weight, boxW, 3);
    w = Math.min(boxW, L.width); h = L.height;
  } else {
    const size = fitSize(t.text ?? "", head ? lay.type.display : lay.type.body, weight, boxW, 3);
    const lines = breakLines(t.text ?? "", size, weight, boxW);
    w = Math.min(boxW, Math.max(0, ...lines.map((l) => estWidth(l.join(" "), size, weight)))); h = lines.length * size * 1.12;
  }
  const centered = t.style === "headline" || t.style === "caption";
  const at: [number, number] | undefined = Array.isArray(t.pos) ? t.pos : undefined;      // a positioned text (the quote_type pattern): its top-left corner is `pos` (MotionTextLayer: left / top), `center` puts pos at its middle
  const x0 = at ? (t.center ? at[0] - w / 2 : at[0]) : centered ? (W - w) / 2 : t.style === "quote" ? SAFE * W : 0.06 * W;
  const y0 = at ? at[1] : t.style === "headline" ? 0.38 * H : t.style === "quote" ? 0.3 * H : t.style === "caption" ? H - pct(lay.captionBottom, H) - h : t.style === "label" ? pct(lay.labelTop, H) : H - pct(lay.lowerThirdBottom, H) - h;
  return [x0, y0, x0 + w, y0 + h].map((v, i) => Math.round((v / (i % 2 ? H : W)) * 1000) / 1000);
}

let prevChoice: Choice | undefined;
let prev: string | undefined;
const diagrams: Record<number, { placed: DiagramOut["placed"]; skipped: DiagramOut["skipped"]; moved: DiagramOut["moved"]; replaced: DiagramOut["replaced"] }> = {};      // the elements drawn by src/motion/diagram.ts (written into motion_plan.json)
const how: Record<number, { texts: string; decor: Record<string, string>; intents: string[]; mood: string; importance: number }> = {};      // how each scene's choices were made (written into motion_plan.json)
const scenes = plan.scenes.map((sc: any, i: number) => {
  if (!PATTERNS[sc.pattern]) throw new Error(`scene ${sc.id}: unknown pattern "${sc.pattern}"`);
  const last = i === plan.scenes.length - 1;
  let tt: string | undefined = last ? undefined : sc.transition;
  if (!last && (!tt || !(TRANSITIONS as readonly string[]).includes(tt) || tt === prev)) tt = pickTransition(prev, sc.mood ?? "", i);
  if (!last) prev = tt;
  const vp = vpScenes.get(sc.id);
  const look = kit ? kitLook(kit, i, kitSeed, prevLookId) : undefined;       // never the look of the scene before
  if (look) prevLookId = look.id;
  const kw0 = sc.keywords?.[0]?.at;
  // later keywords of the scene (times snapped to spoken words): the headline pulses when each one is said
  const pulses: number[] = (sc.keywords ?? []).slice(1).map((k: any) => k.at).filter((t: number) => t >= sc.start && t < sc.end);
  const params: PP = {
    // background gradient = base -> secondary (the accent is for highlights, never for backgrounds)
    start: sc.start, end: sc.end, files: [], palette, colors: look ? [look.bg[0], look.bg[1]] : [base, secondary], pulses, mood: look ? undefined : sc.mood,      // a kit look is a flat colour field: the mood's light field (aurora, spotlight ...) would dirty it
    ...(aspect === "9:16" ? { width: W, height: H } : {}),
    ...(sc.params ?? {}),
    ...(vp ? { text: vp.texts[0], text2: vp.texts[1], mark: sc.params?.mark && vp.texts[0]?.toLowerCase().includes(String(sc.params.mark).toLowerCase()) ? sc.params.mark : undefined } : {}),   // the Visual Plan's words, never the narration sentence
    textAt: kw0 !== undefined && kw0 >= sc.start && kw0 < sc.end ? kw0 : undefined,
  };
  const built = buildScene(sc.id, sc.pattern, params, tt ? { type: tt, dur: speed !== 1 ? Math.max(0.25, Math.round(((sc.transition_dur ?? 0.6) / speed) * 100) / 100) : sc.transition_dur ?? 0.6 } : undefined);
  if (!rich) { tagLayers(built.layers as any[], registry); return built; }
  // the motion library: text layers get a preset chosen from the content, decorations are added; never the previous scene's choice again
  const importance = Math.min(1, (kw0 !== undefined ? 0.8 : 0.5) + (i === 0 || i === plan.scenes.length - 1 ? 0.1 : 0));
  const r = richenScene(built, { tall: aspect === "9:16", mood: sc.mood, importance, prev: prevChoice, motionOnly, speed, intents: vp?.intents, textRegions: vp?.els.filter((e) => e.type === "text" || e.type === "label").map((e) => e.region), drawn: drawnBox, fallbackText: vp ? vp.texts[0] ?? "" : sc.params?.text ?? sc.keywords?.[0]?.text ?? sc.meaning, seed: kitSeed, kit: look });   // from the plan, never from the folder path: the same plan always gives the same choices
  how[sc.id] = { texts: vp ? "visual_plan" : "scene_plan", decor: Object.fromEntries((r.decor ?? []).map((d) => [d.preset, d.why ?? "topic"])), intents: vp?.intents ?? [], mood: sc.mood ?? "", importance };
  if (r.choice) prevChoice = r.choice;
  const fx = fixes.get(sc.id);
  if (fx) {
    let ti = 0;
    for (const l of r.scene.layers as any[]) {
      if (l.type === "motion_text") {
        const k = String(ti++);
        if (fx.textAt?.[k] !== undefined) l.at = fx.textAt[k];
        if (fx.emphasisAt?.[k] !== undefined) l.emphasisAt = [fx.emphasisAt[k]];      // the second the marked word is spoken (a decision recorded by motion_planning.align_emphasis)
      }
      if (l.type === "motion_scene") for (const it of l.items ?? []) { if (fx.box?.[it.preset]) it.box = fx.box[it.preset]; if (fx.boxTall?.[it.preset]) it.boxTall = fx.boxTall[it.preset]; }
    }
  }
  if (vp && motionOnly && vp.els.length) {                    // the Visual Plan elements the placed graphic cannot draw: discs, icons, links (src/motion/diagram.ts), after the decisions of "Solve warnings"
    const layers = r.scene.layers as any[];
    const msLayer = layers.find((l) => l.type === "motion_scene");
    const items: any[] = msLayer?.items ?? [];
    const colors = { earth: "#2a9d9f", mars: "#d9582b", moon: "#b9b2a3", line: palette[3] ?? "#f2e6d0" };      // the colours the Visual Plan names: teal Earth, orange-red Mars, cream-grey Moon
    const d = planDiagram({
      els: vp.els, rels: vp.rels, start: sc.start, end: sc.end, tall: aspect === "9:16", W, H, speed,
      texts: layers.filter((l) => l.type === "motion_text").map((l) => { const b = drawnBox(l); return [b[0], b[1], b[2], b[3]] as [number, number, number, number]; }),
      items, fixed: new Set([...Object.keys(fixes.get(sc.id)?.[aspect === "9:16" ? "boxTall" : "box"] ?? {})]),
      obstacles: layers.filter((l) => l.type === "icon" && !l.elementId && l.pos).map((l) => { const s = (l.size ?? 160) / 2; return [(l.pos[0] - s) / W, (l.pos[1] - s) / H, (l.pos[0] + s) / W, (l.pos[1] + s) / H] as [number, number, number, number]; }),
      colors, resources: iconsOf(registry),
    });
    layers.push(...d.layers);
    if (d.newItems.length) { if (msLayer) items.push(...d.newItems); else layers.push({ type: "motion_scene", z: 8, items: d.newItems }); }
    if (d.placed.length || d.skipped.length) diagrams[sc.id] = { placed: d.placed, skipped: d.skipped, moved: d.moved, replaced: d.replaced };
  }
  tagLayers(r.scene.layers as any[], registry);
  return r.scene;
});

// --plan-only: write what the motion library chose for every scene (motion_plan.json, "Motion Planning") and stop; the normal run builds the composition from the same plan ("Motion Generation").
const summarize = (s: any) => ({
  id: s.id, start: s.start, end: s.end, pattern: s.pattern, pictures: s.layers.filter((l: any) => l.type === "image").length,
  // the first fields of every entry are the ones version 1 had (the pipeline compares the presets); the rest is the absolute timing and the reason of each choice
  texts: s.layers.filter((l: any) => l.type === "motion_text").map((l: any) => ({ text: l.text, style: l.style, preset: l.preset, exit: l.exitPreset, emphasis: l.emphasis, enter_s: l.dur ?? null,
    at: l.at ?? null, until: l.until ?? null, exit_s: l.exitDur ?? null, emphasis_at: l.emphasisAt ?? [], source: how[s.id]?.texts ?? "scene_plan", drawn_box: drawnBox(l) })),
  graphics: s.layers.filter((l: any) => l.type === "motion_scene").flatMap((l: any) => (l.items ?? []).map((i: any) => ({ preset: i.preset, atmosphere: !!i.bleed, speed: i.speed ?? 1,
    anchored: !!diagrams[s.id]?.moved.some((m) => m.preset === i.preset), start: i.start ?? null, end: i.end ?? null, exit_s: i.exitDur ?? null, box: (aspect === "9:16" ? i.boxTall : undefined) ?? i.box ?? null, why: how[s.id]?.decor[i.preset] ?? "topic" }))),
  transition: s.transition_out ? { type: s.transition_out.type, dur: s.transition_out.dur } : null,
  // the other things the scene shows, so a Visual Plan element can be found in the plan: icons, the classic (lower-third) texts and the data layers (counter, chart, map ...)
  icons: s.layers.filter((l: any) => l.type === "icon" && !l.elementId).map((l: any) => ({ name: l.lucide ?? l.name ?? null, at: l.enter?.at ?? l.at ?? null })),
  classic_texts: s.layers.filter((l: any) => l.type !== "motion_text" && typeof l.text === "string" && l.text.trim()).map((l: any) => ({ text: l.text, style: l.style ?? null, at: l.at ?? null })),
  other_layers: s.layers.map((l: any) => l.type).filter((t: string) => !["motion_text", "motion_scene", "image", "icon", "text", "hero_text", "hero-text", "title", "headline", "caption"].includes(t)),
  why: how[s.id] ?? null,
  diagram: diagrams[s.id] ?? null,
  resources: [...new Set([...s.layers, ...s.layers.flatMap((l: any) => l.items ?? [])].map((l: any) => l.resource_id).filter(Boolean))],      // the registry resources the scene uses (docs/resources.md)
});
if (process.argv.includes("--plan-only")) {
  if (!rich) throw new Error("--plan-only needs the motion library (--motion or --no-images)");
  const planName = aspect === "9:16" ? "motion_plan_9x16.json" : "motion_plan.json";
  writeFileSync(join(dir, planName), JSON.stringify({ version: 1, aspect, mode: motionOnly ? "motion-only" : "with-pictures", speed, fps: 30, ...(vpScenes.size ? { visual_plan_used: true } : {}), scenes: scenes.map(summarize) }, null, 1));
  console.log(`${planName}: ${scenes.length} scenes planned (${motionOnly ? "motion-only" : "with pictures"}, pace x${speed})`);
  process.exit(0);
}
const words = tr ? tr.segments.flatMap((s: any) => s.words) : undefined;
const meta = { fps: 30, width: W, height: H, audio, duration, subtitles: false, palette, ...(plan.style?.grade ? { grade: plan.style.grade } : {}), ...(rich ? { motion: "rich", motionSpeed: speed } : {}), ...(motionOnly ? { motionOnly: true } : {}), ...(kit ? { kit: kit.id } : {}) };
const comp = { meta, scenes, ...(words ? { words } : {}) };
const outName = aspect === "9:16" ? "composition_9x16.json" : "composition.json";
writeFileSync(join(dir, outName), JSON.stringify(comp, null, 1));
console.log(`${outName}: ${scenes.length} scenes, ${scenes.filter((s: any) => s.layers.some((l: any) => l.type === "image")).length} with images${motionOnly ? " (motion-only: no pictures)" : ""}`);
