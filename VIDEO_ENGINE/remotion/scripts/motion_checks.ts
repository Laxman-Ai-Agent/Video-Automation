/** Checks of the motion library (run: npx tsx scripts/motion_checks.ts). Prints one JSON line {ok, count, failed[], ...}; exit code 1 when a check fails.
 *  Pure functions only (no browser): timing, text visibility, Telugu, determinism, preset configuration. Real-renderer checks are in tests/test_motion_library.py. */
import { markOf, planDiagram, type DEl } from "../src/motion/diagram";
import { pickIcon, pickIconAlias, type IconRes } from "../src/library/registry";
import { breakLines, estWidth, graphemes, rnd } from "../src/motion/core";
import { type TextParams, textFrame } from "../src/motion/textFrame";
import { EMPHASIS_IDS, EXIT_PRESET_IDS, TEXT_PRESETS, TEXT_PRESET_IDS } from "../src/motion/textPresets";

const checks: Record<string, boolean> = {};
const check = (name: string, ok: boolean) => { checks[name] = !!ok; };

// Resource Library icon choice: a NAME in the description wins; only a curated alias is a fallback; a tag alone never selects
const ICONS: IconRes[] = [{ id: "icon.tabler.eyeglass", sha256: "a", tags: ["glasses", "space"], aliases: ["glasses", "spectacles"] }, { id: "icon.tabler.map-pin", sha256: "b", tags: ["space"], aliases: [] }];
check("icon_name_in_description_wins", pickIcon("a map pin on the route", ICONS)?.id === "icon.tabler.map-pin");
check("icon_alias_only_as_fallback", pickIcon("smart glasses icon", ICONS) === null && pickIconAlias("smart glasses icon", ICONS)?.id === "icon.tabler.eyeglass");
check("icon_tag_alone_never_selects", pickIcon("a space station", ICONS) === null && pickIconAlias("a space station", ICONS) === null);
// diagram markers: a point and a horizon glow are drawn, a line / route / world / dome is not a marker
const E = (desc: string): DEl => ({ id: "x", type: "graphic", role: "", required: true, desc, region: "left" });
check("marker_point", markOf(E("Small bright node marking the present starting point")) === "point");
check("marker_glow", markOf(E("Soft violet horizon glow where the path continues onward")) === "glow");
check("marker_not_a_link", markOf(E("Glowing cyan line running left to right, fading open at its far end")) === null);
check("marker_not_a_world", markOf(E("A flat teal disc representing Earth")) === null && markOf({ ...E("A dome"), type: "icon" }) === null);
// the scene of the live project (a path from a starting point to a horizon): all three required elements are drawn in both formats, none is skipped, nothing leaves the safe area
for (const [name, W, H, tall] of [["land", 1920, 1080, false], ["tall", 1080, 1920, true]] as const) {
  const els: DEl[] = [{ id: "journey_path", type: "graphic", role: "", required: true, desc: "Glowing cyan line running left to right, fading open at its far end", region: "path_across_frame" },
    { id: "origin_point", type: "graphic", role: "", required: true, desc: "Small bright node marking the present starting point", region: "left" },
    { id: "future_horizon", type: "graphic", role: "", required: true, desc: "Soft violet horizon glow where the path continues onward", region: "right" }];
  const out = planDiagram({ els, rels: [{ source: "journey_path", target: "origin_point", relation: "connects_to" }, { source: "journey_path", target: "future_horizon", relation: "connects_to" }], start: 9, end: 13, tall, W, H, speed: 1.4,
    texts: [[0.09, 0.33, 0.6, 0.63]], items: [{ id: "g", preset: "dashed-flow", kind: "gfx", box: [0.2, 0.4, 0.6, 0.1] }], fixed: new Set(), obstacles: [], colors: { earth: "#3b82f6", mars: "#ef4444", moon: "#9ca3af", line: "#22d3ee" } });
  const ids = out.placed.map((p) => p.element_id).sort().join(",");
  check(`diagram_markers_${name}`, ids === "future_horizon,journey_path,origin_point" && out.skipped.length === 0 && out.placed.every((p) => p.box[0] >= 0.05 - 1e-9 && p.box[0] + p.box[2] <= 0.95 + 1e-9 && p.box[1] + p.box[3] <= (tall ? 0.84 : 0.95) + 1e-9));
}
const FPS = 30;
const EN = "The Moon slowly drifts away from Earth every single year";
const TE = "భూమి చుట్టూ తిరిగే చంద్రుడు ప్రతి సంవత్సరం దూరమవుతున్నాడు";
const base = (text: string, preset: string, o: Partial<TextParams> = {}): TextParams => ({ text, preset, at: 2, size: 96, maxWidth: 1536, accent: "#f5b942", fps: FPS, mark: text.split(" ")[1], ...o });

const num = (s: string, re: RegExp) => [...s.matchAll(re)].map((m) => Number(m[1]));
/** A style that shows the text completely: opaque, unclipped, unmasked, unblurred, no offset, scale 1, no rotation. */
function settled(s: Record<string, unknown>): boolean {
  if (s.opacity !== undefined && Math.abs(Number(s.opacity) - 1) > 1e-6) return false;
  if (s.clipPath && s.clipPath !== "none") return false;
  if (s.WebkitMaskImage || s.maskImage) return false;
  if (s.filter && s.filter !== "none") return false;
  const tr = String(s.transform ?? "");
  if (tr) {
    const [tx, ty] = [...tr.matchAll(/translate\((-?[\d.]+)px, (-?[\d.]+)px\)/g)].flatMap((m) => [Number(m[1]), Number(m[2])]);
    if (tx !== undefined && (Math.abs(tx) > 0.01 || Math.abs(ty) > 0.01)) return false;
    if (num(tr, /scale\((-?[\d.]+)\)/g).some((v) => Math.abs(v - 1) > 1e-3)) return false;
    if (num(tr, /rotate[XY]?\((-?[\d.]+)deg\)/g).some((v) => Math.abs(v) > 1e-2)) return false;
  }
  return true;
}
const allStyles = (f: ReturnType<typeof textFrame>) => [f.block, ...f.lines.flatMap((l) => [l.style, ...l.words.flatMap((w) => [w.style, ...(w.chars ?? []).map((c) => c.style)])])] as Record<string, unknown>[];
const wordsOut = (f: ReturnType<typeof textFrame>) => f.lines.flatMap((l) => l.words.map((w) => (w.chars ? w.chars.map((c) => c.text).join("") : w.text)));

// ---------- preset configuration ----------
check("text_presets_at_least_40", TEXT_PRESET_IDS.length >= 40);
check("exits_at_least_8", EXIT_PRESET_IDS.length >= 8);
check("emphasis_at_least_8", EMPHASIS_IDS.length >= 8);
check("preset_ids_unique", new Set(TEXT_PRESET_IDS).size === TEXT_PRESET_IDS.length);
check("every_text_preset_is_documented", Object.values(TEXT_PRESETS).every((p) => p.id && p.label && p.desc.length > 10 && p.category && p.dur > 0 && p.stagger >= 0));
check("every_fallback_exists_and_is_indic_safe", Object.values(TEXT_PRESETS).every((p) => p.indic || (TEXT_PRESETS[p.fallback] && TEXT_PRESETS[p.fallback].indic)));
check("categories_cover_the_brief", ["entrance", "reveal", "typography", "kinetic", "depth"].every((c) => Object.values(TEXT_PRESETS).some((p) => p.category === c)));
check("units_cover_block_line_word_char", ["block", "line", "word", "char"].every((u) => Object.values(TEXT_PRESETS).some((p) => p.unit === u)));

// ---------- timing, visibility, order of words (English and Telugu), every preset ----------
let timingOk = true, visibleOk = true, orderOk = true, hiddenBefore = true, deterministic = true, noNaN = true;
for (const id of TEXT_PRESET_IDS) {
  for (const text of [EN, TE]) {
    const a = base(text, id, { emphasisAt: [3.2] });
    const f0 = textFrame(a, a.at * FPS - 1);
    hiddenBefore &&= f0.hidden;                                   // nothing is drawn before the start frame
    const fEnd = textFrame(a, f0.enterEnd + 2);
    visibleOk &&= !fEnd.hidden && allStyles(fEnd).every(settled);   // after the entrance every unit is fully visible
    orderOk &&= wordsOut(fEnd).join(" ") === text.split(" ").join(" ");   // every word, in the script order
    timingOk &&= fEnd.enterEnd >= a.at * FPS && fEnd.enterEnd - a.at * FPS < 6 * FPS;      // an entrance never takes more than 6 s
    for (let fr = 0; fr < 200; fr += 7) {
      const x = textFrame(a, fr), y = textFrame(a, fr);
      deterministic &&= JSON.stringify(x) === JSON.stringify(y);
      noNaN &&= !JSON.stringify(x).includes("NaN") && !JSON.stringify(x).includes("Infinity");
    }
    const fwd = [10, 40, 90].map((fr) => JSON.stringify(textFrame(a, fr))), rev = [90, 40, 10].map((fr) => JSON.stringify(textFrame(a, fr))).reverse();
    deterministic &&= fwd.join() === rev.join();                 // the order in which frames are evaluated does not matter
  }
}
check("nothing_drawn_before_the_start_frame", hiddenBefore);
check("entrance_timing_is_bounded", timingOk);
check("every_preset_ends_fully_visible_en_and_te", visibleOk);
check("every_word_present_in_order_en_and_te", orderOk);
check("text_frames_are_deterministic", deterministic);
check("no_nan_or_infinity_in_any_style", noNaN);

// ---------- Telugu is never cut inside a cluster ----------
const tf = textFrame(base(TE, "char-reveal"), 120);
check("telugu_char_preset_falls_back_to_words", tf.preset.unit !== "char" && tf.preset.indic);
const clusters = graphemes(TE.split(" ")[0]);
check("telugu_clusters_stay_whole", clusters.join("") === TE.split(" ")[0] && clusters.length < [...TE.split(" ")[0]].length);
check("latin_char_preset_splits_by_character", textFrame(base(EN, "char-reveal"), 120).lines[0].words[0].chars?.length === EN.split(" ")[0].length);

// ---------- exit ----------
const ea = base(EN, "cinematic-fade", { until: 6, exitDur: 0.5, exit: "blur-out" });
check("visible_before_the_exit", !textFrame(ea, 6 * FPS - 1).hidden);
check("hidden_after_the_exit", textFrame(ea, 6.6 * FPS).hidden);
check("exit_is_gradual", Number(textFrame(ea, 6.25 * FPS).block.opacity) > 0 && Number(textFrame(ea, 6.25 * FPS).block.opacity) < 1);
check("every_exit_preset_ends_hidden", EXIT_PRESET_IDS.every((x) => textFrame(base(EN, "cinematic-fade", { until: 6, exitDur: 0.5, exit: x }), 6.7 * FPS).hidden));

// ---------- keyword emphasis follows the spoken time ----------
const ka = base(EN, "word-reveal", { mark: "Moon", emphasisAt: [4], emphasis: "glow" });
const wordMoon = (fr: number) => textFrame(ka, fr).lines.flatMap((l) => l.words).find((w) => w.text === "Moon")!;
check("emphasis_waits_for_the_spoken_time", wordMoon(4 * FPS - 1).e === 0 && wordMoon(4 * FPS + 30).e > 0.99);
check("only_the_marked_word_is_emphasised", textFrame(ka, 200).lines.flatMap((l) => l.words).filter((w) => w.marked).length === 1);
check("every_emphasis_preset_renders", EMPHASIS_IDS.every((e) => textFrame(base(EN, "blur-reveal", { mark: "Moon", emphasisAt: [3], emphasis: e }), 150).lines.flatMap((l) => l.words).some((w) => w.marked)));

// ---------- variation without randomness ----------
const kin = (seed: string) => JSON.stringify(textFrame(base(EN, "kinetic", { seed }), 70));
check("same_seed_same_result", kin("a") === kin("a"));
check("different_seed_different_motion", kin("a") !== kin("b"));
check("rnd_is_stable", rnd("x", 3) === rnd("x", 3) && rnd("x", 3) !== rnd("x", 4));
check("direction_changes_the_motion", JSON.stringify(textFrame(base(EN, "mask-reveal", { dir: "left" }), 70).block) !== JSON.stringify(textFrame(base(EN, "mask-reveal", { dir: "up" }), 70).block));
check("intensity_changes_the_motion", JSON.stringify(textFrame(base(EN, "blur-reveal", { k: 0.5 }), 70).block) !== JSON.stringify(textFrame(base(EN, "blur-reveal", { k: 1.5 }), 70).block));
check("duration_changes_the_timing", textFrame(base(EN, "blur-reveal", { dur: 0.4 }), 70).enterEnd < textFrame(base(EN, "blur-reveal", { dur: 1.6 }), 70).enterEnd);

// ---------- layout: every line fits its box, in 16:9 and 9:16 widths ----------
for (const [name, w] of [["16_9", 1536], ["9_16", 864]] as const)
  for (const [lang, text] of [["en", EN], ["te", TE]] as const) {
    const f = textFrame(base(text, "line-reveal", { maxWidth: w, size: name === "9_16" ? 80 : 120 }), 200);
    check(`lines_fit_the_safe_width_${lang}_${name}`, breakLines(text, f.size, 800, w).every((l) => estWidth(l.join(" "), f.size, 800) <= w * 1.001 || l.length === 1));
  }

// ---------- graphics: 40+ presets, every one draws sane SVG at every sampled frame, deterministic ----------
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { GFX_CATEGORIES, GFX_PRESETS, GFX_PRESET_IDS, drawGfx } from "../src/motion/graphics";
import { MASKS, MASK_IDS, maskStyle } from "../src/motion/masks";
import { type MItem, allInside, hasReadableOverlap, resolveItems, safeRect } from "../src/motion/layout";
import { choose, chooseDecor, placeClear, suitable, SLOT, textRect } from "../src/motion/select";
import { richenScene } from "../src/motion/integrate";
import { prog, hash } from "../src/motion/core";

const gctx = (id: string, f: number, o: Record<string, unknown> = {}) => ({ f, fps: FPS, w: 600, h: 300, color: "#ffffff", accent: "#f5b942", secondary: "#2a9d8f", seed: id, k: 1, dir: "right" as const, label: "Mars", value: 72, data: [3, 5, 2, 8], ...o });
const svg = (id: string, f: number, o: Record<string, unknown> = {}) => renderToStaticMarkup(createElement("svg", null, drawGfx(id, gctx(id, f, o))));
check("graphic_presets_at_least_40", GFX_PRESET_IDS.length >= 40);
check("graphic_ids_unique", new Set(GFX_PRESET_IDS).size === GFX_PRESET_IDS.length);
check("graphic_categories_all_used", GFX_CATEGORIES.every((c) => Object.values(GFX_PRESETS).some((p) => p.category === c)));
check("every_graphic_is_documented", Object.values(GFX_PRESETS).every((p) => p.label && p.desc.length > 10 && p.dur > 0));
check("brief_graphics_present", ["line-draw", "circle-expand", "rect-frame-draw", "polygon-spin", "dots-grid", "grid-lines", "stroke-path-reveal", "shape-morph", "animated-border", "corner-accents",
  "node-network", "arrow-draw", "pointer-callout", "hud-brackets", "targeting-ring", "scan-line", "radar-sweep", "light-sweep", "particles-float", "line-network", "map-pin-drop", "route-line",
  "stat-counter", "bars-grow", "circular-progress", "timeline-dots", "donut-segments", "line-chart-draw", "vignette-focus", "divider-grow"].every((id) => !!GFX_PRESETS[id]));
let gfxSane = true, gfxDet = true, gfxStarts = true, gfxEnds = true;
for (const id of GFX_PRESET_IDS) {
  const frames = [0, 5, 15, 30, 60, 120, 300];
  for (const f of frames) {
    const a = svg(id, f), b = svg(id, f);
    gfxDet &&= a === b;
    gfxSane &&= !a.includes("NaN") && !a.includes("Infinity") && !a.includes("undefined") && a.length > 20;
  }
  gfxStarts &&= svg(id, 0).length <= svg(id, 120).length + 400 || GFX_PRESETS[id].loop;     // a non-loop graphic starts nearly empty and grows
  const fwd = [10, 50, 200].map((f) => svg(id, f)).join("|"), rev = [200, 50, 10].map((f) => svg(id, f)).reverse().join("|");
  gfxDet &&= fwd === rev;
}
check("every_graphic_draws_valid_svg_at_every_frame", gfxSane);
check("graphics_are_deterministic_in_any_order", gfxDet);
check("graphics_start_small_and_grow", gfxStarts);
check("graphics_change_over_time", GFX_PRESET_IDS.filter((id) => svg(id, 3) !== svg(id, 40)).length >= GFX_PRESET_IDS.length - 3);
check("seed_changes_seeded_graphics", ["node-network", "particles-float", "radar-sweep", "polygon-spin", "dust", "floating-dots"].every((id) => new Set(["a", "b", "c", "d", "e", "f"].map((s) => svg(id, 60, { seed: s }))).size > 1));
check("data_graphics_use_the_data", svg("bars-grow", 80, { data: [1, 9] }) !== svg("bars-grow", 80, { data: [9, 1] }) && svg("circular-progress", 80, { value: 20 }) !== svg("circular-progress", 80, { value: 90 }));
check("label_and_value_are_shown", svg("pointer-callout", 80, { label: "Olympus Mons" }).includes("Olympus Mons") && svg("stat-counter", 120, { value: 4200 }).includes("4,200"));
check("loops_keep_moving_after_the_entrance", ["ring-pulse", "scan-line", "radar-sweep", "particles-float", "line-network", "dashed-flow"].every((id) => svg(id, 150) !== svg(id, 175)));
check("unknown_graphic_falls_back", svg("no-such-preset", 40).length > 20);

// ---------- masks and transitions ----------
check("masks_at_least_12", MASK_IDS.length >= 12 && new Set(MASK_IDS).size === MASK_IDS.length);
check("mask_categories_cover_the_brief", ["shape-wipe", "directional", "split", "layered", "spotlight"].every((c) => MASKS.some((m) => m.category === c)));
check("masks_show_nothing_complete_at_the_ends", MASK_IDS.every((k) => Object.keys(maskStyle(k, 1, { w: 800, h: 450 })).length === 0 && Object.keys(maskStyle(k, 0.5, { w: 800, h: 450 })).length > 0));
check("masks_are_monotonic_and_deterministic", MASK_IDS.every((k) => JSON.stringify(maskStyle(k, 0.4, { w: 800, h: 450, seed: 3 })) === JSON.stringify(maskStyle(k, 0.4, { w: 800, h: 450, seed: 3 })) && JSON.stringify(maskStyle(k, 0.2, { w: 800, h: 450 })) !== JSON.stringify(maskStyle(k, 0.7, { w: 800, h: 450 }))));
check("mask_at_zero_hides_everything", MASK_IDS.every((k) => { const s = JSON.stringify(maskStyle(k, 0, { w: 800, h: 450 })); return s.length > 4 && !s.includes("NaN"); }));

// ---------- composition: bounds, safe area, overlap prevention, both aspect ratios ----------
const items: MItem[] = [
  { id: "title", kind: "text", preset: "blur-reveal", text: "The Moon is drifting away from Earth", style: "headline", start: 1, end: 8, box: [0.08, 0.3, 0.84, 0.3] },
  { id: "sub", kind: "text", preset: "word-reveal", text: "about four centimetres every single year", style: "caption", start: 2, end: 8, box: [0.08, 0.32, 0.84, 0.1] },        // starts on top of the title
  { id: "tag", kind: "gfx", preset: "callout-label", label: "Apollo laser reflectors", start: 3, end: 8, box: [0.05, 0.33, 0.4, 0.08] },                // also on top
  { id: "off", kind: "text", preset: "cinematic-fade", text: "Edge text", style: "label", start: 1, end: 8, box: [0.97, 0.98, 0.5, 0.1] },             // outside the frame
  { id: "fx", kind: "gfx", preset: "particles-float", start: 1, end: 8, box: [0, 0, 1, 1], bleed: true },
  { id: "late", kind: "text", preset: "typewriter", text: "Later line", style: "caption", start: 9, end: 12, box: [0.08, 0.32, 0.84, 0.1] },          // not at the same time: may keep its place
];
for (const [name, W, H] of [["16_9", 1920, 1080], ["9_16", 1080, 1920]] as const) {
  const r = resolveItems(items, W, H, 0, 12);
  const [sx, sy, sw, sh] = safeRect(W, H);
  const vis = r.items.filter((x) => !x.hidden && !x.item.bleed);
  check(`composition_inside_frame_${name}`, allInside(r.items, W, H));
  check(`composition_inside_safe_area_${name}`, vis.every((x) => x.box[0] >= sx - 0.5 && x.box[1] >= sy - 0.5 && x.box[0] + x.box[2] <= sx + sw + 0.5 && x.box[1] + x.box[3] <= sy + sh + 0.5));
  check(`no_readable_overlap_${name}`, !hasReadableOverlap(r.items));
  check(`every_text_is_kept_${name}`, r.items.filter((x) => x.item.kind === "text").every((x) => !x.hidden));
  check(`bleed_layer_covers_the_frame_${name}`, (() => { const b = r.items.find((x) => x.item.id === "fx")!; return b.box[0] === 0 && b.box[2] === W; })());
  check(`later_item_keeps_its_place_${name}`, JSON.stringify(r.items.find((x) => x.item.id === "late")!.box) === JSON.stringify(resolveItems([items[5]], W, H, 0, 12).items[0].box));
  check(`resolve_is_deterministic_${name}`, JSON.stringify(r) === JSON.stringify(resolveItems(items, W, H, 0, 12)));
}
check("phone_bottom_strip_is_kept_free_in_9_16", resolveItems([{ kind: "text", preset: "cinematic-fade", text: "Low text", style: "caption", start: 0, box: [0.1, 0.95, 0.8, 0.05] }], 1080, 1920, 0, 5).items[0].box[1] + resolveItems([{ kind: "text", preset: "cinematic-fade", text: "Low text", style: "caption", start: 0, box: [0.1, 0.95, 0.8, 0.05] }], 1080, 1920, 0, 5).items[0].box[3] <= 1920 * 0.84 + 0.5);
check("group_stagger_orders_the_starts", (() => { const g = resolveItems([0, 1, 2].map((i) => ({ kind: "gfx", preset: "dots-grid", start: 1, group: "g", delay: 0.2, box: [0.1, 0.1 + i * 0.1, 0.2, 0.05] } as MItem)), 1920, 1080, 0, 9).items; return g[0].start < g[1].start && g[1].start < g[2].start; })());
check("item_phases_entry_hold_exit", prog(30 * 3, 30 * 3, 15) === 0 && prog(30 * 3 + 15, 30 * 3, 15) === 1);

// ---------- selection: variety without randomness, fallbacks ----------
const scenes = Array.from({ length: 60 }, (_, i) => ({ id: i + 1, text: ["Mars once had oceans", "Four billion years ago", "The red planet", "Data from orbit shows ice beneath the dust", "What happens next?"][i % 5], role: (["headline", "caption", "label", "quote"] as const)[i % 4], importance: [0.5, 0.9, 0.3, 0.7][i % 4], mood: ["calm", "dramatic", "science", "map route"][i % 4], pattern: ["hero_text", "hero_only", "stat_counter", "map_route"][i % 4] }));
let prevC: ReturnType<typeof choose> | undefined; const used = new Set<string>(); const seqA: string[] = []; let consecutive = false, unsuited = false;
for (const s of scenes) {
  const c = choose({ ...s, seed: "demo", duration: 6, tall: false, prev: prevC });
  if (prevC && c.text.preset === prevC.text.preset) consecutive = true;
  if (!suitable(c.text.preset, s.text)) unsuited = true;
  used.add(c.text.preset); seqA.push(c.text.preset + "/" + c.decor.map((d) => d.preset).join("+")); prevC = c;
}
check("no_text_preset_repeats_in_consecutive_scenes", !consecutive);
check("selection_uses_a_broad_range_of_presets", used.size >= 15);
check("selection_never_picks_an_unsuitable_preset", !unsuited);
check("selection_is_deterministic", (() => { let p: ReturnType<typeof choose> | undefined; return scenes.every((s, i) => { const c = choose({ ...s, seed: "demo", duration: 6, tall: false, prev: p }); p = c; return seqA[i] === c.text.preset + "/" + c.decor.map((d) => d.preset).join("+"); }); })());
check("different_seed_different_selection", scenes.slice(0, 12).some((s) => choose({ ...s, seed: "x", duration: 6, tall: false }).text.preset !== choose({ ...s, seed: "y", duration: 6, tall: false }).text.preset));
check("telugu_never_gets_per_letter_motion", scenes.every((s) => { const c = choose({ ...s, text: TE, seed: "te", duration: 6, tall: false }); return TEXT_PRESETS[c.text.preset].indic; }));
check("long_text_gets_a_calm_fallback", ["flip-x", "bounce", "kinetic", "typewriter", "char-reveal"].every((id) => !suitable(id, "This is a very long sentence that should never be animated with a dramatic per letter or flipping effect because it needs to stay readable for everyone")));
check("emphasis_matches_importance", scenes.every((s) => ["mask", "scale", "glow", "stroke"].includes(choose({ ...s, seed: "e", duration: 6, tall: false, importance: 0.95 }).text.emphasis) && ["underline", "color", "pulse", "tracking"].includes(choose({ ...s, seed: "e", duration: 6, tall: false, importance: 0.1 }).text.emphasis)));
check("decor_slots_exist_for_every_pool_preset", Object.keys(SLOT).every((id) => !!GFX_PRESETS[id]));
check("short_scenes_get_no_decor", choose({ ...scenes[0], seed: "d", duration: 1.5, tall: false }).decor.length === 0 && choose({ ...scenes[0], pattern: "grid_four", seed: "d", duration: 8, tall: false }).decor.length === 0);
check("decor_boxes_stay_clear_of_the_caption_strip", Object.values(SLOT).every((s) => s.bleed || (s.box[1] + s.box[3] <= 0.88 && (s.boxTall ?? s.box)[1] + (s.boxTall ?? s.box)[3] <= 0.8)));

// ---------- integration: classic scenes become rich scenes, nothing else changes ----------
const classic = { id: 4, start: 20, end: 28, pattern: "hero_text", camera: { move: "push-in", from: 1, to: 1.1, focus: [0.6, 0.4] }, layers: [
  { type: "background", z: 0, colors: ["#111", "#222"] }, { type: "image", z: 1, slot: "s04_0", file: "04.png", anim: "ken-burns" },
  { type: "text", style: "big-highlight", text: "Mars once had oceans", mark: "oceans", at: 21, z: 10 }, { type: "text", style: "lower-third", text: "Source: NASA", at: 22, z: 10 }] } as never;
for (const tall of [false, true]) {
  const r = richenScene(classic, { tall, mood: "science", importance: 0.8, seed: "demo" });
  const L = r.scene.layers as unknown as { type: string; text?: string; preset?: string; at?: number; mark?: string; emphasisAt?: number[]; items?: unknown[] }[];
  check(`rich_scene_converts_the_headline_${tall ? "9_16" : "16_9"}`, L.some((l) => l.type === "motion_text" && l.text === "Mars once had oceans" && !!l.preset && l.at === 21 && l.mark === "oceans" && l.emphasisAt?.[0] === 21.25));
  check(`rich_scene_keeps_other_layers_${tall ? "9_16" : "16_9"}`, L.filter((l) => l.type === "background" || l.type === "image").length === 2 && L.some((l) => l.type === "text" && l.text === "Source: NASA"));
  check(`rich_scene_adds_decoration_${tall ? "9_16" : "16_9"}`, L.some((l) => l.type === "motion_scene" && (l.items?.length ?? 0) >= 1));
  check(`rich_scene_is_deterministic_${tall ? "9_16" : "16_9"}`, JSON.stringify(r) === JSON.stringify(richenScene(classic, { tall, mood: "science", importance: 0.8, seed: "demo" })));
}
check("scene_without_text_is_untouched", richenScene({ ...(classic as object), layers: [{ type: "image", z: 1 }] } as never, { tall: false }).scene.layers.length === 1);
check("previous_choice_is_not_repeated", (() => { const a = richenScene(classic, { tall: false, seed: "s", importance: 0.8 }); const b = richenScene(classic, { tall: false, seed: "s", importance: 0.8, prev: a.choice }); return a.choice!.text.preset !== b.choice!.text.preset; })());
// pinned values: the seeded hash must give the same numbers on every machine and run (a change here would change every video built with a seed)
check("hash_is_pinned_across_runs_and_machines", hash("scene-1") === 4004251844 && Math.abs(rnd("x", 3) - 0.7787105592433363) < 1e-12);

// ---------- Use Images = OFF (motion-only) and the pace ----------
import { paceFor } from "../src/motion/integrate";
const mo = (tall: boolean, speed: number, extra: object = {}) => richenScene(classic, { tall, mood: "science", importance: 0.8, seed: "demo", motionOnly: true, speed, fallbackText: "Mars once had oceans", ...extra });
const names = (r: { scene: { layers: unknown[] } }) => (r.scene.layers as { type: string }[]).map((l) => l.type);
for (const tall of [false, true]) {
  const tag = tall ? "9_16" : "16_9";
  const r = mo(tall, 1.4);
  const L = r.scene.layers as unknown as { type: string; items?: { kind: string; bleed?: boolean; start: number; speed?: number; box: number[]; boxTall?: number[]; preset: string }[]; dur?: number; stagger?: number; preset?: string; exitDur?: number }[];
  check(`motion_only_has_no_picture_${tag}`, !names(r).includes("image") && !names(r).includes("stock-video"));
  check(`motion_only_keeps_background_and_text_${tag}`, names(r).includes("background") && names(r).includes("motion_text"));
  const items = L.find((l) => l.type === "motion_scene")?.items ?? [];
  check(`motion_only_has_an_atmosphere_and_a_placed_graphic_${tag}`, items.some((i) => i.bleed) && items.some((i) => !i.bleed) && items.length >= 2);
  check(`motion_only_graphics_play_faster_${tag}`, items.every((i) => i.speed === 1.4));
  check(`motion_only_is_deterministic_${tag}`, JSON.stringify(r) === JSON.stringify(mo(tall, 1.4)));
  const [W, H] = tall ? [1080, 1920] : [1920, 1080];
  const res = resolveItems(items as unknown as MItem[], W, H, 20, 28);
  check(`motion_only_graphics_do_not_overlap_and_stay_inside_${tag}`, !hasReadableOverlap(res.items) && allInside(res.items, W, H));
  const t = L.find((l) => l.type === "motion_text")!;
  check(`speed_shortens_the_entrance_${tag}`, (t.dur ?? 9) < TEXT_PRESETS[t.preset!].dur && (t.dur ?? 0) >= 0.25 && (t.exitDur ?? 9) < 0.5 && (t.exitDur ?? 0) >= 0.25);
  check(`speed_shortens_the_stagger_${tag}`, (t.stagger ?? 99) <= TEXT_PRESETS[t.preset!].stagger);
}
check("speed_1_keeps_the_preset_durations", (() => { const t = (richenScene(classic, { tall: false, seed: "demo", importance: 0.8, speed: 1 }).scene.layers as unknown as { type: string; dur?: number; stagger?: number }[]).find((l) => l.type === "motion_text")!; return t.dur === undefined && t.stagger === undefined; })());
check("scene_without_text_gets_a_headline_from_the_fallback_text", (() => { const r = richenScene({ ...(classic as object), layers: [{ type: "background", z: 0 }, { type: "image", z: 1 }] } as never, { tall: false, seed: "f", motionOnly: true, speed: 1.4, fallbackText: "The danger of unchecked machines is real and very big" }); const t = (r.scene.layers as unknown as { type: string; text?: string }[]).find((l) => l.type === "motion_text"); return !!t && t.text === "The danger of unchecked machines is"; })());
check("picture_only_scene_still_gets_graphics_in_motion_only", (() => { const r = richenScene({ ...(classic as object), layers: [{ type: "background", z: 0 }, { type: "image", z: 1 }] } as never, { tall: false, seed: "p", motionOnly: true, speed: 1.4 }); const n = names(r); return !n.includes("image") && n.includes("motion_scene"); })());
check("pace_default_and_clamp", paceFor(undefined, true) === 1.4 && paceFor(undefined, false) === 1.3 && paceFor("1", true) === 1 && paceFor("9", true) === 2 && paceFor("0.1", false) === 0.5 && paceFor("abc", false) === 1.3);
check("motion_only_decor_never_repeats_the_previous_scene", (() => { const a = mo(false, 1.4); const b = richenScene({ ...(classic as object), id: 5 } as never, { tall: false, mood: "science", importance: 0.8, seed: "demo", motionOnly: true, speed: 1.4, prev: a.choice }); const pa = new Set(a.choice!.decor.map((d) => d.preset)); return b.choice!.decor.every((d) => !pa.has(d.preset)); })());

// ---- the picture divider of split_two (regression: the full-height line crossed the caption of a scene that had no pictures) ----
import { PATTERNS, buildScene } from "../src/patterns";
for (const tall of [false, true]) {
  const tag = tall ? "9_16" : "16_9";
  const built = buildScene(5, "split_two", { start: 26.08, end: 35.05, files: [], palette: ["#111", "#eee", "#a52"], colors: ["#111", "#a52"], pulses: [], text: "Knowledge · Training · Trust", textAt: 31.88, ...(tall ? { width: 1080, height: 1920 } : {}) } as never);
  const shapes = (s: { layers: unknown[] }) => (s.layers as { type: string; role?: string; kind?: string }[]).filter((l) => l.type === "shape");
  check(`split_two_has_a_picture_divider_with_pictures_${tag}`, shapes(built).some((l) => l.kind === "line"));
  const mo = richenScene(built, { tall, motionOnly: true, mood: "science", importance: 0.6, seed: "demo", speed: 1.4 }).scene;
  check(`split_two_motion_only_has_no_divider_${tag}`, !shapes(mo).length);
  check(`split_two_motion_only_keeps_the_caption_${tag}`, (mo.layers as { type: string; text?: string }[]).some((l) => l.type === "motion_text" && l.text === "Knowledge · Training · Trust"));
  const im = richenScene(built, { tall, mood: "science", importance: 0.6, seed: "demo" }).scene;
  check(`split_two_with_pictures_keeps_the_divider_${tag}`, shapes(im).some((l) => l.kind === "line"));
  // no other pattern loses a layer in motion-only except its pictures
  check(`other_patterns_keep_their_shape_layers_in_motion_only_${tag}`, Object.keys(PATTERNS).filter((id) => id !== "split_two").every((id) => { try { const b = buildScene(1, id, { start: 0, end: 8, files: [], palette: ["#111", "#eee", "#a52"], colors: ["#111", "#a52"], pulses: [], text: "x", textAt: 1, data: [{ label: "a", value: 1 }], number: 5, ...(tall ? { width: 1080, height: 1920 } : {}) } as never); return shapes(richenScene(b, { tall, motionOnly: true, mood: "science", importance: 0.6, seed: "demo", speed: 1.4 }).scene).length === shapes(b).length; } catch { return true; } }));
}

// ---- the diagram builder: the Visual Plan elements the placed graphic cannot draw (discs, icons, links) ----
import { icons as LUCIDE } from "lucide-react";
import { PRIMITIVES, planDiagram, REGION_BOX, type DEl, type DRel, type DItem } from "../src/motion/diagram";
import { DOME_GAP, DOME_RATIOS, domeBodies, domeCount, domeLayout, domeWindows, tallestRadius } from "../src/components/domeGeometry";
{
  const el = (id: string, type: string, desc: string, region: string, role = "supporting"): DEl => ({ id, type, role, required: true, desc, region });
  const earth = el("earth", "graphic", "A flat teal disc representing Earth", "left"), mars = el("mars", "graphic", "A flat orange-red disc representing Mars", "right"), moon = el("moon", "graphic", "A cream-grey disc representing the Moon", "center");
  const rocket = el("rocket", "icon", "A single small spacecraft icon travelling along the route", "over_primary_visual"), crew = el("crew", "graphic", "One group of astronaut silhouettes in cream", "right", "primary");
  const dome = el("domes", "graphic", "A small cluster of simple habitat domes with lit windows", "center", "primary"), link = el("link", "graphic", "A thin dotted signal line between Mars and Earth", "path_across_frame", "primary");
  const rels: DRel[] = [{ source: "link", target: "earth", relation: "connects_to" }, { source: "link", target: "mars", relation: "connects_to" }, { source: "help", target: "earth", relation: "connects_to" }, { source: "help", target: "crew", relation: "connects_to" }];
  const colors = { earth: "#2a9d9f", mars: "#d9582b", moon: "#b9b2a3", line: "#f2e6d0" };
  const run = (tall: boolean, els: DEl[], items: DItem[], texts: [number, number, number, number][], fixed: string[] = []) => planDiagram({ els, rels, start: 10, end: 18, tall, W: tall ? 1080 : 1920, H: tall ? 1920 : 1080, speed: 1.4, texts, items: JSON.parse(JSON.stringify(items)), fixed: new Set(fixed), obstacles: [], colors });
  const headline: [number, number, number, number] = [0.09, 0.38, 0.91, 0.53];
  const rect = (b: number[]): [number, number, number, number] => [b[0], b[1], b[0] + b[2], b[1] + b[3]];
  const hit = (a: number[], b: number[]) => a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3];
  const dashed: DItem = { id: "3:dashed-flow", preset: "dashed-flow", kind: "gfx", box: [0.1, 0.16, 0.8, 0.02], boxTall: [0.1, 0.14, 0.8, 0.015], start: 10.5 };
  for (const tall of [false, true]) {
    const tag = tall ? "9_16" : "16_9", lim = tall ? 0.84 : 0.95;
    const a = run(tall, [earth, mars, link], [dashed], [headline]);
    check(`diagram_draws_both_worlds_and_the_link_${tag}`, a.placed.length === 3 && a.skipped.length === 0 && a.layers.length === 2 && a.layers.every((l) => ["shape", "icon"].includes(String(l.type)) && !!l.elementId));
    check(`diagram_is_clear_of_the_text_and_inside_the_safe_area_${tag}`, a.placed.every((p) => !hit(rect(p.box), [headline[0], headline[1], headline[2], headline[3]]) && p.box[0] >= 0.05 && p.box[1] >= 0.05 && p.box[0] + p.box[2] <= 0.95 && p.box[1] + p.box[3] <= lim));
    check(`diagram_is_deterministic_${tag}`, JSON.stringify(a) === JSON.stringify(run(tall, [earth, mars, link], [dashed], [headline])));
    check(`diagram_link_runs_between_the_two_worlds_${tag}`, (() => { const [x, , w] = (tall ? a.moved[0].box : a.moved[0].box); const e = a.placed.find((p) => p.element_id === "earth")!, m = a.placed.find((p) => p.element_id === "mars")!; return x >= e.box[0] + e.box[2] - 1e-9 && x + w <= m.box[0] + 1e-9; })());
    const three = run(tall, [earth, moon, mars], [{ id: "7:grid-lines", preset: "grid-lines", kind: "gfx", box: [0.62, 0.06, 0.32, 0.3], boxTall: [0.5, 0.05, 0.44, 0.16], start: 10.5 }], [[0.05, 0.38, 0.95, 0.68]]);
    check(`diagram_three_stops_replace_the_grid_by_a_timeline_and_say_so_${tag}`, three.replaced.length === 1 && three.replaced[0].from === "grid-lines" && three.replaced[0].to === "timeline-dots" && three.placed.length === 3 && three.moved[0].preset === "timeline-dots");
    check(`diagram_stops_sit_on_the_dots_of_the_timeline_${tag}`, (() => { const b = three.moved[0].box; return three.placed.every((p, i) => Math.abs(p.box[0] + p.box[2] / 2 - (b[0] + ((i + 0.5) / 3) * b[2])) < 0.002); })());
    const domes = run(tall, [dome, earth], [dashed], [headline]);
    const dl = domes.layers.find((l) => l.elementId === "domes"), dp = domes.placed.find((p) => p.element_id === "domes");
    check(`diagram_domes_are_one_dome_layer_with_the_elements_id_and_colours_${tag}`, !!dl && dl.type === "shape" && dl.kind === "dome" && dl.count === 3 && domes.layers.filter((l) => l.elementId === "domes").length === 1 && domes.skipped.length === 0
      && !!dp && dp.kind === "dome" && dp.id === "shape:dome" && dp.status === "resolved" && /lit window arches/.test(dp.note) && /^#/.test(String(dl.window)) && /^#/.test(String(dl.fill)));
    check(`diagram_domes_stand_clear_of_the_text_inside_the_safe_area_and_below_it_${tag}`, !!dp && !hit(rect(dp.box), headline) && dp.box[0] >= 0.05 && dp.box[0] + dp.box[2] <= 0.95 && dp.box[1] + dp.box[3] <= lim + 1e-9 && dp.box[1] > headline[3]);
    check(`diagram_domes_box_is_where_the_layer_draws_them_${tag}`, !!dl && !!dp && (() => { const [a, b] = [dl.from as number[], dl.to as number[]], W = tall ? 1080 : 1920, H = tall ? 1920 : 1080; const top = tallestRadius(b[0] - a[0], 3); return Math.abs(dp.box[0] - a[0] / W) < 0.002 && Math.abs(dp.box[2] - (b[0] - a[0]) / W) < 0.002 && Math.abs(dp.box[3] - top / H) < 0.002 && Math.abs(dp.box[1] + dp.box[3] - a[1] / H) < 0.002; })());
    check(`diagram_domes_are_deterministic_and_use_the_elements_own_colours_${tag}`, JSON.stringify(domes) === JSON.stringify(run(tall, [dome, earth], [dashed], [headline])) && (() => { const c = run(tall, [{ ...dome, appearance: { color: "#112233", window_color: "#445566" } }], [], [headline]).layers[0]; return c.fill === "#112233" && c.window === "#445566"; })()
      && run(tall, [{ ...dome, appearance: { color: "red" } }], [], [headline]).layers[0].fill === "#f2e6d0");
    check(`diagram_a_single_dome_is_drawn_for_the_singular_and_no_place_says_why_${tag}`, run(tall, [{ ...dome, desc: "One small habitat dome" }], [], [headline]).layers[0].count === 1
      && (() => { const full = run(tall, [dome], [{ id: "9:x", preset: "grid-lines", kind: "gfx", box: [0.05, 0.05, 0.9, 0.32], boxTall: [0.05, 0.05, 0.9, 0.32] }, { id: "9:y", preset: "grid-lines", kind: "gfx", box: [0.05, 0.53, 0.9, 0.42], boxTall: [0.05, 0.53, 0.9, 0.32] }], [headline]); return full.layers.length === 0 && full.skipped.some((s) => s.element_id === "domes" && /no free place/.test(s.reason)); })());
    const crewScene = run(tall, [earth, crew, { ...link, id: "help", desc: "A faint dashed cream line from Earth toward the crew" }], [{ id: "5:node-network", preset: "node-network", kind: "gfx", box: [0.62, 0.06, 0.32, 0.3], boxTall: [0.5, 0.05, 0.44, 0.16], start: 10.5 }, { id: "5:bracket-frame", preset: "bracket-frame", kind: "gfx", box: [0.06, 0.3, 0.88, 0.3], boxTall: [0.06, 0.28, 0.88, 0.26] }], [[0.27, 0.862, 0.73, 0.92]]);
    check(`diagram_crew_is_a_stand_in_and_its_ring_stays_inside_the_safe_area_${tag}`, (() => { const c = crewScene.placed.find((p) => p.element_id === "crew")!; const r = crewScene.moved.find((m) => m.preset === "node-network")!.box; return c.status === "approximate" && /generic people icon/.test(c.note) && r[0] >= 0.05 && r[1] >= 0.05 && r[0] + r[2] <= 0.95 && r[1] + r[3] <= lim; })());
    check(`diagram_help_line_is_a_new_dashed_graphic_marked_approximate_${tag}`, crewScene.newItems.length === 1 && crewScene.newItems[0].preset === "dashed-flow" && crewScene.placed.some((p) => p.element_id === "help" && p.status === "approximate"));
    const full = run(tall, [earth, mars], [dashed], [[0, 0, 1, 1]]);
    check(`diagram_without_a_free_strip_draws_nothing_and_says_why_${tag}`, full.layers.length === 0 && full.placed.length === 0 && full.skipped.length === 2 && full.skipped.every((s) => /no free strip/.test(s.reason)));
  }
  const route: DItem = { id: "2:route-line", preset: "route-line", kind: "gfx", box: [0.125, 0.662, 0.3, 0.2], start: 10.5 };
  const rt = run(false, [earth, mars, rocket], [route], [headline], ["route-line"]);
  check("diagram_keeps_a_route_box_decided_by_solve_warnings_and_puts_the_worlds_on_its_ends", JSON.stringify(rt.moved) === "[]" && (() => { const e = rt.placed.find((p) => p.element_id === "earth")!, m = rt.placed.find((p) => p.element_id === "mars")!; return Math.abs(e.box[0] + e.box[2] / 2 - (0.125 + 0.08 * 0.3)) < 0.002 && Math.abs(m.box[0] + m.box[2] / 2 - (0.125 + 0.92 * 0.3)) < 0.002; })());
  check("diagram_rocket_rides_the_route_between_the_worlds", (() => { const r = rt.placed.find((p) => p.element_id === "rocket")!, e = rt.placed.find((p) => p.element_id === "earth")!, m = rt.placed.find((p) => p.element_id === "mars")!; return r.id === "icon:rocket" && r.box[0] > e.box[0] && r.box[0] < m.box[0]; })());
  // ---- the `dome` kind of the shape layer: geometry (pure) ----
  for (const n of [1, 2, 3, 4, 5]) {
    const ds = domeLayout(100, 1100, n);
    check(`dome_cluster_of_${n}_fills_exactly_its_width_with_the_tallest_in_the_middle_and_no_overlap`, ds.length === n && Math.abs(Math.min(...ds.map((d) => d.cx - d.r)) - 100) < 1e-6 && Math.abs(Math.max(...ds.map((d) => d.cx + d.r)) - 1100) < 1e-6
      && Math.abs(Math.max(...ds.map((d) => d.r)) - tallestRadius(1000, n)) < 1e-6 && ds.every((d, i) => i === 0 || d.cx - d.r > ds[i - 1].cx + ds[i - 1].r) && (n < 3 || ds.indexOf(ds.reduce((a, b) => (b.r > a.r ? b : a))) === Math.floor((n - 1) / 2) || n >= 4));
  }
  check("dome_count_is_clamped_to_1_to_5_and_geometry_is_deterministic", domeCount(0) === 1 && domeCount(9) === 5 && domeCount("3") === 3 && domeCount(undefined) === 1 && JSON.stringify(domeLayout(10, 500, 3)) === JSON.stringify(domeLayout(500, 10, 3)));
  check("dome_paths_are_half_discs_on_the_base_line_and_windows_sit_inside_their_dome", (() => { const ds = domeLayout(0, 600, 3), b = domeBodies(ds, 400), w = domeWindows(ds, 400); return (b.match(/M /g) ?? []).length === 3 && (w.match(/M /g) ?? []).length === 3 && !/NaN|Infinity/.test(b + w) && ds.every((d) => 0.42 * d.r < d.r * 0.98); })());
  check("dome_ratios_are_those_the_python_side_mirrors", JSON.stringify(DOME_RATIOS) === "[1,0.7,0.5,0.4,0.3]" && DOME_GAP === 0.1);
  check("diagram_primitives_exist_in_lucide_and_the_shape_layer", PRIMITIVES.shape.includes("circle") && PRIMITIVES.shape.includes("dome") &&PRIMITIVES.icon.every((n) => (LUCIDE as Record<string, unknown>)[n.replace(/(^|-)(\w)/g, (_, __, c: string) => c.toUpperCase())]));
  check("placed_graphics_keep_clear_of_the_planned_texts_or_are_not_used", (() => {
    const share = (b: number[], t: number[]) => { const ov = Math.max(0, Math.min(b[0] + b[2], t[2]) - Math.max(b[0], t[0])) * Math.max(0, Math.min(b[1] + b[3], t[3]) - Math.max(b[1], t[1])); return ov / Math.min(b[2] * b[3], (t[2] - t[0]) * (t[3] - t[1])); };
    return [false, true].every((tall) => ["upper_safe_area", "lower_safe_area"].every(() => {
      const texts = ["upper_safe_area", "lower_safe_area"];
      const f = { id: 5, seed: "a2v", role: "headline" as const, text: "Business systems", importance: 0.9, mood: "", pattern: "quote_type", duration: 6, tall, motionOnly: true, intents: ["show_connected_structure"], textRegions: texts };
      const rects = texts.map((r) => textRect(r, tall)!);
      const items = chooseDecor(f).filter((d) => !d.bleed);
      const moved = placeClear("node-network", f);           // its own slot lies on the upper label: it is moved, same size, inside the frame
      return items.length > 0 && items.every((d) => { const b = (tall ? d.boxTall : undefined) ?? d.box; return b[2] * b[3] >= 0.5 || rects.every((t) => share(b, t) <= 0.25); })
        && !!moved && moved[2] === ((tall ? SLOT["node-network"].boxTall : undefined) ?? SLOT["node-network"].box)[2] && rects.every((t) => share(moved, t) <= 0.25)
        && placeClear("node-network", { ...f, textRegions: [] }) === ((tall ? SLOT["node-network"].boxTall : undefined) ?? SLOT["node-network"].box);   // no planned text: its own slot, unchanged
    }));
  })());
  check("placed_graphics_keep_clear_of_where_the_texts_are_drawn", (() => {
    const drawn: [number, number, number, number] = [0.05, 0.04, 0.95, 0.24];               // a text drawn over the graphic's own 9:16 slot, where no region was planned
    const f = { id: 5, seed: "a2v", role: "headline" as const, text: "Beyond simple automation", importance: 0.9, mood: "", pattern: "quote_type", duration: 6, tall: true, motionOnly: true, intents: ["show_connected_structure"], textRegions: [], textBoxes: [drawn] };
    const b = placeClear("node-network", f);
    const ov = b ? Math.max(0, Math.min(b[0] + b[2], drawn[2]) - Math.max(b[0], drawn[0])) * Math.max(0, Math.min(b[1] + b[3], drawn[3]) - Math.max(b[1], drawn[1])) : 0;
    return b !== SLOT["node-network"].boxTall && (b === null || ov / Math.min(b[2] * b[3], (drawn[2] - drawn[0]) * (drawn[3] - drawn[1])) <= 0.25);
  })());
  check("a_placed_graphic_shrinks_to_three_quarters_when_no_full_size_spot_is_clear", (() => {
    const drawn: [number, number, number, number][] = [[0.13, 0.333, 0.853, 0.547], [0.13, 0.625, 0.865, 0.681]];     // 9:16 scene: a headline and a label as the renderer draws them, the label planned at the top
    const b = placeClear("node-network", { id: 5, seed: "a2v", role: "headline" as const, text: "Beyond simple automation", importance: 0.9, mood: "", pattern: "quote_type", duration: 6, tall: true, motionOnly: true, intents: ["show_connected_structure"], textRegions: ["upper_safe_area"], textBoxes: drawn });
    return !!b && Math.abs(b[2] - 0.33) < 1e-6 && b[1] + b[3] <= 0.8 + 1e-6;
  })());
  check("diagram_region_table_has_the_regions_of_the_visual_plan", ["upper_safe_area", "lower_safe_area", "center", "left", "right", "top", "bottom", "path_across_frame", "full_frame"].every((k) => k in REGION_BOX));
}

// ----- background looks: chosen from the mood; no mood (or an unknown one) writes nothing, so older compositions are unchanged -----
{
  const { lookFor, PATTERNS } = await import("../src/patterns");
  const { BACKGROUND_LOOKS } = await import("../src/components/Background");
  const bgOf = (mood?: string) => PATTERNS.hero_only({ start: 0, end: 4, files: [], sceneId: 3, mood }).find((l) => l.type === "background") as unknown as Record<string, unknown>;
  check("background_look_follows_the_mood", lookFor("dramatic, tense") === "spotlight" && lookFor("calm, sad") === "aurora" && lookFor("hopeful, majestic") === "mesh");
  check("background_look_unknown_mood_keeps_the_gradient", lookFor(undefined) === undefined && lookFor("playful") === undefined && !("look" in bgOf("playful")) && !("look" in bgOf(undefined)));
  check("background_look_is_written_with_a_seed", bgOf("calm").look === "aurora" && bgOf("calm").seed === "bg3");
  check("background_looks_are_all_known_to_the_component", ["dramatic", "calm", "hopeful"].every((m) => (BACKGROUND_LOOKS as readonly string[]).includes(lookFor(m) as string)));
}

// ----- style kit (P0) and phrase composer (P1): src/styleKit.ts, src/motion/phrase.ts -----
{
  const { KITS, contrast, kitByName, kitLook } = await import("../src/styleKit");
  const { layoutPhrase, makeRuns, phraseText, pickHero } = await import("../src/motion/phrase");
  const kit = KITS.editorial;
  const looks = Array.from({ length: 12 }, (_, i) => kitLook(kit, i, "seed", i ? kitLook(kit, i - 1, "seed").id : undefined));
  // the kit
  check("kit_off_by_default_and_unknown_is_an_error", kitByName(undefined) === undefined && kitByName("") === undefined && kitByName("0") === undefined && kitByName("1")?.id === "editorial" && (() => { try { kitByName("nope"); return false; } catch { return true; } })());
  check("kit_text_is_readable_on_every_background", kit.looks.every((l) => contrast(l.fg, l.bg[0]) >= 4.5 && contrast(l.fg, l.bg[1]) >= 4.5));
  check("kit_accent_is_visible_on_every_background", kit.looks.every((l) => contrast(l.accent, l.bg[0]) >= 2.5 && contrast(l.accent, l.bg[1]) >= 2.5));
  check("kit_scene_never_gets_the_look_of_the_scene_before", looks.every((l, i) => i === 0 || l.id !== looks[i - 1].id));
  check("kit_looks_are_deterministic_and_vary", JSON.stringify(looks) === JSON.stringify(Array.from({ length: 12 }, (_, i) => kitLook(kit, i, "seed", i ? kitLook(kit, i - 1, "seed").id : undefined))) && new Set(looks.map((l) => l.id)).size >= 3);
  check("kit_marks_dark_and_light_looks", kit.looks.every((l) => { const k1 = { ...kit, looks: [l] }; return kitLook(k1, 0, "x").dark === (l.id === "ink" || l.id === "graphite" || l.id === "cobalt"); }));
  // the composer
  const colors = { fg: "#ffffff", accent: "#ffd23f", dim: "#aab", bg: "#2b44ff" };
  const TXT = ["so you can see how capable", "You create", "Smarter than us", "Every system reacts in moments", "The danger of unchecked machines is real"];
  const recipes = new Set<string>();
  for (const t of TXT) for (let s = 0; s < 12; s++) { const p = makeRuns(t, { seed: s, colors }); if (p) recipes.add(p.recipe); }
  check("phrase_every_recipe_is_reachable", ["lead-hero", "sans-serif", "marker"].every((r) => recipes.has(r)));
  check("phrase_keeps_every_word_in_order", TXT.every((t) => { for (let s = 0; s < 12; s++) { const p = makeRuns(t, { seed: s, colors }); if (!p || phraseText(p.runs) !== t) return false; } return true; }));
  check("phrase_is_deterministic", JSON.stringify(makeRuns(TXT[0], { seed: 4, colors })) === JSON.stringify(makeRuns(TXT[0], { seed: 4, colors })));
  check("phrase_refuses_what_it_cannot_style", makeRuns("Smarter", { seed: 1, colors }) === null && makeRuns("భూమి చుట్టూ తిరిగే చంద్రుడు", { seed: 1, colors }) === null && makeRuns("one two three four five six seven eight nine ten eleven", { seed: 1, colors }) === null && makeRuns("Café au lait here", { seed: 1, colors }) === null);
  check("phrase_hero_is_the_keyword_else_the_longest_real_word", pickHero(["so", "you", "can", "see", "how", "capable"]) === 5 && pickHero(["Smarter", "than", "us"]) === 0 && pickHero(["a", "big", "danger", "ahead"], "big") === 1);
  const L = (w: number, t = TXT[0], s = 0) => layoutPhrase(makeRuns(t, { seed: s, colors })!.runs, 144, 800, w, 3);
  check("phrase_layout_fits_the_box_in_both_formats", [1728, 972].every((w) => TXT.every((t) => [0, 1, 2, 3].every((s) => { const l = L(w, t, s); return l.lines.length <= 3 && l.width <= w + 1e-6 && l.size >= 144 * 0.55 - 1e-6 && l.lines.flat().map((x) => x.text).join(" ") === t; }))));
  check("phrase_layout_height_follows_the_biggest_word_of_each_line", (() => { const p = makeRuns(TXT[0], { seed: 0, colors })!; const l = layoutPhrase(p.runs, 100, 800, 4000, 3); return p.recipe !== "lead-hero" || Math.abs(l.height - 100 * 1.6 * 1.12) < 1e-6; })());
  // the frame: every word drawn, with its run, revealed word by word
  const ph = makeRuns("so you can see how capable", { seed: 0, colors })!;
  const pa = (o: Partial<TextParams> = {}): TextParams => ({ text: "so you can see how capable", preset: "word-slide", at: 2, size: 120, maxWidth: 1600, accent: "#ffd23f", fps: FPS, runs: ph.runs, ...o });
  const f0 = textFrame(pa(), 2 * FPS + 200);
  check("phrase_frame_draws_every_word_with_its_run", wordsOut(f0).join(" ") === "so you can see how capable" && f0.lines.flatMap((l) => l.words).every((w) => !!w.run));
  check("phrase_frame_is_settled_after_the_entrance", allStyles(f0).every(settled));
  check("phrase_frame_reveals_word_by_word", (() => { const early = textFrame(pa(), 2 * FPS + 4), ws = early.lines.flatMap((l) => l.words); return !early.hidden && ws.some((w) => Number(w.style.opacity ?? 1) < 1) && ws.some((w) => Number(w.style.opacity ?? 1) >= 1 || w.style.opacity === undefined); })());
  check("phrase_with_a_non_word_preset_is_revealed_word_by_word_not_by_letter", textFrame(pa({ preset: "char-reveal" }), 2 * FPS + 10).preset.unit === "word" && textFrame(pa({ preset: "kinetic" }), 2 * FPS + 10).lines.every((l) => l.words.every((w) => !w.chars)));
  check("text_without_runs_has_no_run_fields", textFrame({ ...pa(), runs: undefined }, 2 * FPS + 200).lines.every((l) => l.words.every((w) => !("run" in w))));
  const DT = "The danger of unchecked machines is real";
  const marker = (() => { for (let s = 0; s < 30; s++) { const p = makeRuns(DT, { seed: s, colors, mark: "danger" }); if (p?.recipe === "marker") return p; } return null; })();
  check("phrase_marker_word_is_the_keyword_with_a_readable_text_colour", !!marker && marker.runs.filter((r) => r.hl).length === 1 && marker.runs.find((r) => r.hl)!.text === "danger" && contrast(marker.runs.find((r) => r.hl)!.hlColor!, colors.accent) >= 4.5);
  check("phrase_marker_switches_the_text_colour_when_drawn", (() => { if (!marker) return false; const t = (fr: number) => textFrame(pa({ text: DT, runs: marker.runs, emphasis: "stroke" }), fr).lines.flatMap((l) => l.words).find((w) => w.run?.hl)!; return t(2 * FPS + 400).emph.color === marker.runs.find((r) => r.hl)!.hlColor && t(2 * FPS).e === 0; })());
  // integration: a kit changes colours and the headline only; without it nothing changes
  const hero = buildScene(3, "hero_text", { start: 0, end: 5, files: [], palette: ["#0b1d26", "#f2a541", "#2a9d8f"], text: "so you can see how capable", mark: "capable", mood: "science" });
  const plain = JSON.stringify(richenScene(hero, { tall: false, seed: "k", importance: 0.8 }));
  const lk = kitLook(kit, 0, "k");
  const withKit = richenScene(hero, { tall: false, seed: "k", importance: 0.8, kit: lk });
  const txt = (withKit.scene.layers as unknown as Record<string, unknown>[]).find((l) => l.type === "motion_text")!;
  check("kit_off_leaves_the_scene_exactly_as_before", plain === JSON.stringify(richenScene(hero, { tall: false, seed: "k", importance: 0.8, kit: undefined })) && !plain.includes('"runs"') && !plain.includes('"accent"'));
  check("kit_on_colours_the_text_and_turns_the_headline_into_a_phrase", txt.color === lk.fg && txt.accent === lk.accent && Array.isArray(txt.runs) && phraseText(txt.runs as never) === "so you can see how capable" && TEXT_PRESETS[String(txt.preset)].unit === "word");
  check("kit_on_colours_the_graphics", (() => { const ms = (withKit.scene.layers as unknown as { type: string; items?: { color?: string; accentColor?: string }[] }[]).find((l) => l.type === "motion_scene"); return !ms || ms.items!.every((i) => i.color === lk.fg && i.accentColor === lk.accent); })());
  check("kit_on_is_deterministic", JSON.stringify(withKit) === JSON.stringify(richenScene(hero, { tall: false, seed: "k", importance: 0.8, kit: lk })));
  check("kit_light_background_drops_the_shadow", (() => { const light = kit.looks.find((l) => l.id === "paper")!; const r = richenScene(hero, { tall: false, seed: "k", importance: 0.8, kit: kitLook({ ...kit, looks: [light] }, 0, "k") }); const t = (r.scene.layers as unknown as Record<string, unknown>[]).find((l) => l.type === "motion_text")!; return t.flat === true; })());
  check("kit_light_look_has_no_vignette_graphic", (() => { const light = { ...kit, looks: kit.looks.filter((l) => l.id === "paper") }; for (let s = 0; s < 40; s++) { const r = richenScene(hero, { tall: false, seed: `v${s}`, importance: 0.8, mood: "dramatic", kit: kitLook(light, 0, `v${s}`) }); const ms = (r.scene.layers as unknown as { type: string; items?: { preset: string }[] }[]).find((l) => l.type === "motion_scene"); if (ms?.items?.some((i) => i.preset === "vignette-focus")) return false; } return true; })());
}

// ===== SECTIONS-APPEND-HERE =====

const failed = Object.entries(checks).filter(([, v]) => !v).map(([k]) => k);
console.log(JSON.stringify({ ok: failed.length === 0, count: Object.keys(checks).length, failed, text_presets: TEXT_PRESET_IDS.length, exits: EXIT_PRESET_IDS.length, emphasis: EMPHASIS_IDS.length }));
process.exit(failed.length ? 1 : 0);
