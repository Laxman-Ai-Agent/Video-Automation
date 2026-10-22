// Draws the Visual Plan elements that the placed graphic cannot stand for (a planet, a spacecraft, a crew, a link between two worlds) from primitives the renderer already has:
// the `shape` layer (a disc), the `icon` layer (a lucide icon) and the link graphics of the library (dashed-flow, route-line, timeline-dots, node-network).
// Pure and deterministic: the same elements, texts and graphics give the same layers. Every layer carries the id of the Visual Plan element (`elementId`) it draws.
// What it does not draw (no primitive) is returned in `skipped` with the reason, never hidden. Times are seconds, boxes are fractions of the frame [x, y, w, h].

import { tallestRadius } from "../components/domeGeometry";
import { type IconRes, pickIcon, pickIconAlias } from "../library/registry";

export type Box = [number, number, number, number];
export type Rect = [number, number, number, number];                   // x0, y0, x1, y1 (fractions)
export interface DEl { id: string; type: string; role: string; required: boolean; desc: string; region: string; appearance?: Record<string, unknown> }
export interface DRel { source: string; target: string; relation: string }
export interface DItem { id?: string; preset: string; kind?: string; box: number[]; boxTall?: number[]; bleed?: boolean; start?: number; data?: number[]; [k: string]: unknown }
export interface Placed { element_id: string; kind: "disc" | "dome" | "icon" | "link" | "marker"; layer: "shape" | "icon" | "motion_scene"; id: string; box: Box; at: number; status: "resolved" | "approximate"; note: string }
export interface Skipped { element_id: string; reason: string }
export interface DiagramIn {
  els: DEl[]; rels: DRel[]; start: number; end: number; tall: boolean; W: number; H: number; speed: number;
  texts: Rect[];                      // where the renderer draws the scene's texts
  items: DItem[];                     // the scene's motion_scene items (the carriers); `box` / `boxTall` may be changed in place
  fixed: Set<string>;                 // presets whose box was decided by "Solve warnings" (kept as they are)
  obstacles: Rect[];                  // other layers on the frame (icons of the pattern)
  colors: { earth: string; mars: string; moon: string; line: string };
  resources?: IconRes[];              // the VERIFIED icons of the Resource Library: an icon element no lucide rule knows is drawn by the registry icon whose name its description says
}
export interface IconInfo { lucide: string; status: "resolved" | "approximate"; note: string; resource?: { id: string; sha256: string } }
export interface DiagramOut { layers: Record<string, unknown>[]; newItems: DItem[]; placed: Placed[]; skipped: Skipped[]; moved: { preset: string; box: Box }[]; replaced: { from: string; to: string; why: string }[] }

/** The primitives this module uses (checked against lucide and the renderer by motion_checks.ts). */
export const PRIMITIVES = { shape: ["circle", "dome"], icon: ["rocket", "users", "book-open"] };
const LINKS = new Set(["route-line", "dashed-flow", "timeline-dots", "node-network"]);
const BODY: [RegExp, "earth" | "mars" | "moon"][] = [[/\bEarth\b/, "earth"], [/\bMars\b/, "mars"], [/\bMoon\b/, "moon"]];
const X_OF: Record<string, number> = { left: 0.14, center: 0.5, right: 0.86, over_primary_visual: 0.5, around_primary_visual: 0.5, path_across_frame: 0.5 };
// where the Visual Plan places its regions (a mirror of backend/visual_planning.REGION_BOX, compared by tests/test_motion_planning.py): a graphic must also keep clear of the area planned for a text
export const REGION_BOX: Record<string, Rect | null> = { center: [0.35, 0.28, 0.65, 0.72], left: [0.05, 0.22, 0.35, 0.78], right: [0.65, 0.22, 0.95, 0.78], top: [0.1, 0.05, 0.9, 0.28], bottom: [0.05, 0.68, 0.95, 0.95],
  upper_left: [0.05, 0.22, 0.35, 0.45], upper_right: [0.65, 0.22, 0.95, 0.45], lower_left: [0.05, 0.55, 0.35, 0.78], lower_right: [0.65, 0.55, 0.95, 0.78], upper_safe_area: [0.1, 0.05, 0.9, 0.2],
  lower_safe_area: [0.1, 0.8, 0.9, 0.95], path_across_frame: [0.1, 0.42, 0.9, 0.58], full_frame: [0, 0, 1, 1], around_primary_visual: null, over_primary_visual: null };
const MARGIN = 0.05, PORTRAIT_UI = 0.16;                                  // theme / config.SAFE_AREA
const r3 = (n: number) => Math.round(n * 1000) / 1000;
const hit = (a: Rect, b: Rect) => a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3];
const rect = (b: number[]): Rect => [b[0], b[1], b[0] + b[2], b[1] + b[3]];

/** A graphic that is only a MARKER on the route: a small bright point (node, dot, point, marker) or a glow at the horizon. Never a link (those say line / link / route) and never a world (a disc). */
export function markOf(e: DEl): "point" | "glow" | null {
  if (e.type !== "graphic" || bodyOf(e) || /\b(line|link|route)\b/i.test(e.desc) || isDome(e)) return null;
  if (/\bhorizon\b/i.test(e.desc) && /\bglow\b/i.test(e.desc)) return "glow";
  if (/\b(node|point|dot|marker)\b/i.test(e.desc)) return "point";
  return null;
}
const MARK_R = { point: 0.5, glow: 1.5 };                                   // radius of a marker as a share of the disc radius
const markColor = (e: DEl, line: string): string => (/\bviolet|purple\b/i.test(e.desc) ? "#8b5cf6" : /\b(white|bright)\b/i.test(e.desc) && markOf(e) === "point" ? "#ffffff" : line);

export function bodyOf(e: DEl): "earth" | "mars" | "moon" | null {
  if (e.type !== "graphic" || !/\bdisc\b/i.test(e.desc)) return null;
  for (const [re, name] of BODY) if (re.test(e.desc)) return name;
  return null;
}
export function iconOf(e: DEl, res?: IconRes[]): IconInfo | null {
  if (e.type === "icon" && /spacecraft|rocket|ship/i.test(e.desc)) return { lucide: "rocket", status: "resolved", note: "a rocket icon placed on the route; it does not travel along it" };
  if (e.type === "icon" && /\bbook\b/i.test(e.desc)) return { lucide: "book-open", status: "resolved", note: "an open-book icon" };
  if (e.type === "graphic" && /\bsilhouettes?\b/i.test(e.desc)) return { lucide: "users", status: "approximate", note: "a generic people icon: the astronaut silhouettes are not drawn" };
  const r = e.type === "icon" && res?.length ? pickIcon(e.desc, res) : null;      // after every lucide rule: the Resource Library only fills what was not drawn before
  if (r) { const rel = /^(around|over)_primary_visual$/.test(e.region);                                // "around the globe": the icon is drawn, but in a free strip, not around another visual
    return { lucide: "", status: rel ? "approximate" : "resolved", note: `the registry icon ${r.id} (Resource Library), placed like the book icon${rel ? "; it is not placed around the primary visual" : ""}`, resource: { id: r.id, sha256: r.sha256 } }; }
  const al = !r && e.type === "icon" && res?.length ? pickIconAlias(e.desc, res) : null;      // only a curated alias of a verified icon; drawn as an APPROXIMATION, said so
  if (al) return { lucide: "", status: "approximate", note: `drawn by the registry icon ${al.id} (curated alias): the description says more than this plain icon shows`, resource: { id: al.id, sha256: al.sha256 } };
  return null;
}
const DETAIL: Record<string, string> = { earth: "plain flat disc; land shapes / habitation lights not drawn", mars: "plain flat disc; glow / habitation lights not drawn", moon: "plain flat disc; craters not drawn" };

export function planDiagram(o: DiagramIn): DiagramOut {
  const out: DiagramOut = { layers: [], newItems: [], placed: [], skipped: [], moved: [], replaced: [] };
  const bodies = o.els.map((e) => ({ e, body: bodyOf(e) })).filter((x): x is { e: DEl; body: "earth" | "mars" | "moon" } => !!x.body);
  const marks = o.els.map((e) => ({ e, mark: markOf(e) })).filter((x): x is { e: DEl; mark: "point" | "glow" } => !!x.mark);
  const icons = o.els.map((e) => ({ e, ic: iconOf(e, o.resources) })).filter((x): x is { e: DEl; ic: IconInfo } => !!x.ic);
  const links = o.els.filter((e) => e.type === "graphic" && !bodyOf(e) && !iconOf(e, o.resources) && /\b(line|link|route)\b/i.test(e.desc) && o.rels.some((r) => r.source === e.id && r.relation === "connects_to"));
  const domes = o.els.filter(isDome);
  if (!bodies.length && !icons.length && !marks.length) {
    if (domes.length) placeDomes(o, domes, out, [...plannedTexts(o), ...o.texts.map(padded), ...o.obstacles, ...o.items.filter((i) => !i.bleed && i.box[2] * i.box[3] < 0.5).map((i) => rect((o.tall ? i.boxTall ?? i.box : i.box)))], 0);
    return out;
  }

  const { W, H, tall } = o;
  const lim = tall ? 1 - PORTRAIT_UI : 1 - MARGIN;
  const stripH = tall ? 0.14 : 0.2;
  const r = Math.min(0.3 * stripH * H, 0.042 * W);                          // disc radius in px
  const rw = r / W, rh = r / H;
  const planned = plannedTexts(o);
  const placeable = o.items.filter((i) => !i.bleed && i.box[2] * i.box[3] < 0.5);
  const hasCrew = icons.some((x) => x.ic.lucide === "users");
  if (bodies.length >= 3 && !hasCrew) {                                   // three or more worlds along one route: the dots of a timeline are its stops
    const pick = placeable.find((i) => (LINKS.has(i.preset) || i.preset === "grid-lines") && i.preset !== "timeline-dots" && !o.fixed.has(i.preset));
    if (pick) { out.replaced.push({ from: pick.preset, to: "timeline-dots", why: `${bodies.length} stops along one route` }); pick.preset = "timeline-dots"; pick.id = String(pick.id ?? "").replace(/:[^:]*$/, ":timeline-dots"); }
  }
  const carrier = placeable.find((i) => LINKS.has(i.preset) && (i.preset !== "node-network" || (bodies.length >= 2 && !hasCrew)));
  const ring = placeable.find((i) => i.preset === "node-network" && hasCrew);
  const field = (i: DItem): number[] => (tall ? i.boxTall ?? i.box : i.box);
  const setBox = (i: DItem, b: Box) => { if (tall) i.boxTall = b; else i.box = b; out.moved.push({ preset: i.preset, box: b }); };
  const avoid: Rect[] = [...planned, ...o.texts.map((t): Rect => [t[0] - 0.03, t[1] - 0.03, t[2] + 0.03, t[3] + 0.03]), ...o.obstacles,
    ...placeable.filter((i) => i !== carrier && i !== ring).map((i) => rect(field(i)))];
  const fixedCarrier = !!carrier && o.fixed.has(carrier.preset);
  const noStrip = (ids: string[]) => { for (const id of ids) out.skipped.push({ element_id: id, reason: "no free strip next to the text, the frame and the other layers is high enough" }); return out; };
  const allIds = [...bodies.map((b) => b.e.id), ...icons.map((i) => i.e.id), ...marks.map((m) => m.e.id)];

  // ---- where the nodes sit: on the route's ends (a route-line), on the dots of a timeline, or in a free strip next to the text ----
  const nodes = [...bodies.map((b) => ({ id: b.e.id, x: X_OF[b.e.region] ?? 0.5, body: b.body as "earth" | "mars" | "moon" | null })),
    ...marks.map((m) => ({ id: m.e.id, x: X_OF[m.e.region] ?? 0.5, body: null as null })),
    ...icons.filter((x) => x.ic.lucide === "book-open" || x.ic.resource).map((x) => ({ id: x.e.id, x: X_OF[x.e.region] ?? 0.5, body: null as null }))];
  nodes.sort((a, b) => a.x - b.x);
  let yc: number;
  let pos: { id: string; x: number; y: number; body: "earth" | "mars" | "moon" | null }[] = [];
  if (carrier && carrier.preset === "route-line" && nodes.length >= 2) {
    if (!fixedCarrier) {                                                 // a route across the free strip; its ends carry the two worlds
      const y = freeStripY(avoid, lim, stripH, carrier, field);
      if (y === null) return noStrip(allIds);
      setBox(carrier, [0.1, r3(y), 0.8, stripH]);
    }
    const bb = field(carrier);
    const A = { x: bb[0] + 0.08 * bb[2], y: bb[1] + 0.8 * bb[3] }, B = { x: bb[0] + 0.92 * bb[2], y: bb[1] + 0.22 * bb[3] };
    pos = [{ ...nodes[0], x: A.x, y: A.y }, { ...nodes[nodes.length - 1], x: B.x, y: B.y }];
    yc = (A.y + B.y) / 2;
  } else {
    const y = freeStripY(avoid, lim, stripH, carrier ?? ring, field, o.els.find((e) => e.id === nodes[0]?.id)?.region);
    if (y === null) return noStrip(allIds);
    yc = y + stripH / 2;
    if (carrier && carrier.preset === "timeline-dots") {
      const n = Math.max(nodes.length, 2), bx = 0.1, bw = 0.8;
      setBox(carrier, [bx, r3(yc - 0.06), bw, 0.12]);
      carrier.data = nodes.map(() => 1);
      pos = nodes.map((nd, i) => ({ ...nd, x: bx + ((i + 0.5) / n) * bw, y: yc }));
    } else {
      const edge = tall ? 0.22 : 0.19;
      const xs = nodes.length > 1 ? nodes.map((_, i) => edge + (i / (nodes.length - 1)) * (1 - 2 * edge)) : nodes.map((nd) => nd.x);
      pos = nodes.map((nd, i) => ({ ...nd, x: xs[i], y: yc }));
      if (carrier && pos.length >= 2) {                                    // the link graphic runs between the two worlds
        const radW = (id: string) => rw * (MARK_R[marks.find((m) => m.e.id === id)?.mark as "point" | "glow"] ?? 1);                 // a marker is smaller or bigger than a world
        const x0 = pos[0].x + radW(pos[0].id) * 1.25, x1 = pos[pos.length - 1].x - radW(pos[pos.length - 1].id) * 1.25;
        setBox(carrier, carrier.preset === "dashed-flow" ? [r3(x0), r3(yc - 0.01), r3(x1 - x0), tall ? 0.025 : 0.035] : [r3(x0), r3(yc - 0.1), r3(x1 - x0), 0.2]);
      }
    }
  }

  // ---- layers ----
  const sz = 0.1 * Math.min(W, H) * (tall ? 1.3 : 1);
  let k = 0;
  const t0 = o.start + 0.3 / o.speed, step = 0.35 / o.speed;
  for (const p of pos) {
    const nd = bodies.find((b) => b.e.id === p.id);
    const at = r3(t0 + step * k++);
    const mk = marks.find((m) => m.e.id === p.id);
    if (mk) {                                                                  // a point or a glow on the route: a plain filled circle (the shape layer), drawn like a world
      const rr = r * MARK_R[mk.mark], cx = p.x * W, cy = p.y * H, col = markColor(mk.e, o.colors.line);
      out.layers.push({ type: "shape", kind: "circle", elementId: mk.e.id, from: [Math.round(cx - rr), Math.round(cy - rr)], to: [Math.round(cx), Math.round(cy - rr)], color: col, fill: col, width: mk.mark === "glow" ? 3 : 5, at, dur: r3(0.7 / o.speed), z: mk.mark === "glow" ? 11 : 12 });
      out.placed.push({ element_id: mk.e.id, kind: "marker", layer: "shape", id: "shape:circle", box: [r3(p.x - rw * MARK_R[mk.mark]), r3(p.y - rh * MARK_R[mk.mark]), r3(2 * rw * MARK_R[mk.mark]), r3(2 * rh * MARK_R[mk.mark])], at, status: mk.mark === "glow" ? "approximate" : "resolved", note: mk.mark === "glow" ? "a plain filled disc where the glow is: the soft glowing edge is not drawn" : "a small filled point on the route" });
    } else if (nd) {
      const col = o.colors[nd.body], cx = p.x * W, cy = p.y * H;       // the `shape` layer draws its circle with the centre at from + (r, r) (an arc through two almost equal points): `from` is set so that the centre is (cx, cy)
      out.layers.push({ type: "shape", kind: "circle", elementId: nd.e.id, from: [Math.round(cx - r), Math.round(cy - r)], to: [Math.round(cx), Math.round(cy - r)], color: col, fill: col, width: 5, at, dur: r3(0.7 / o.speed), z: 12 });
      out.placed.push({ element_id: nd.e.id, kind: "disc", layer: "shape", id: "shape:circle", box: [r3(p.x - rw), r3(p.y - rh), r3(2 * rw), r3(2 * rh)], at, status: "resolved", note: DETAIL[nd.body] });
    } else {
      const ic = icons.find((x) => x.e.id === p.id)!;
      out.layers.push(iconLayer(ic.e.id, ic.ic.lucide, p.x, p.y, sz, at, o, ic.ic.resource));
      out.placed.push(iconPlaced(ic.e.id, ic.ic, p.x, p.y, sz, W, H, at));
    }
  }
  // the spacecraft rides the route: a point of its curve (cubic, the control points of the route-line graphic) or the middle of the link
  for (const x of icons.filter((i) => i.ic.lucide === "rocket")) {
    let px = 0.5, py = yc - 0.07;
    if (carrier?.preset === "route-line") { const bb = field(carrier), t = 0.5, c = (a: number, b: number, c2: number, d: number) => (1 - t) ** 3 * a + 3 * (1 - t) ** 2 * t * b + 3 * (1 - t) * t * t * c2 + t ** 3 * d; px = bb[0] + c(0.08, 0.3, 0.55, 0.92) * bb[2]; py = bb[1] + c(0.8, 0.1, 0.95, 0.22) * bb[3]; }
    else if (pos.length >= 2) { px = (pos[0].x + pos[pos.length - 1].x) / 2; py = yc - rh * 1.4; }
    const at = r3(t0 + step * k++ + 0.6);
    out.layers.push(iconLayer(x.e.id, "rocket", px, py, sz, at, o));
    out.placed.push(iconPlaced(x.e.id, x.ic, px, py, sz, W, H, at));
  }
  // the crew with the ring of three supports around it
  for (const x of icons.filter((i) => i.ic.lucide === "users")) {
    const cx = X_OF[x.e.region] ?? 0.78;
    const at = r3(t0 + step * k++);
    out.layers.push(iconLayer(x.e.id, "users", cx, yc, sz, at, o));
    out.placed.push(iconPlaced(x.e.id, x.ic, cx, yc, sz, W, H, at));
    if (ring) { const rwid = tall ? 0.34 : 0.2, rhei = tall ? 0.13 : 0.22, rx = Math.min(Math.max(cx - rwid / 2, MARGIN), 1 - MARGIN - rwid), ry = Math.min(Math.max(yc - rhei / 2, MARGIN), lim - rhei); setBox(ring, [r3(rx), r3(ry), rwid, rhei]); }
  }
  // links: the signal link is the carrier's own line; the help line is a faint dashed line from the first world toward the crew
  for (const l of links) {
    const a = pos.find((p) => p.body), crew = out.placed.find((p) => p.id === "icon:users");
    if (!crew && carrier) {
      out.placed.push({ element_id: l.id, kind: "link", layer: "motion_scene", id: carrier.preset, box: field(carrier).slice(0, 4) as Box, at: carrier.start ?? o.start, status: "resolved", note: carrier.preset === "dashed-flow" ? "dashes march along the line (dotted is drawn as dashed)" : `drawn by ${carrier.preset} between the worlds` });
    } else if (a && crew) {
      const ringBox = ring ? field(ring) : null, x1 = (ringBox ? ringBox[0] : crew.box[0]) - 0.02, x0 = a.x + rw * 1.25;
      if (x1 - x0 > 0.1) {
        const item: DItem = { id: `${l.id}:dashed-flow`, kind: "gfx", preset: "dashed-flow", start: r3(o.start + 1.6 / o.speed), box: [r3(x0), r3(yc - 0.0175), r3(x1 - x0), 0.035], boxTall: [r3(x0), r3(yc - 0.0125), r3(x1 - x0), 0.025], k: 0.8, dir: "right", z: 9, exitDur: 0.36, speed: o.speed };
        out.newItems.push(item);
        out.placed.push({ element_id: l.id, kind: "link", layer: "motion_scene", id: "dashed-flow", box: (tall ? item.boxTall : item.box) as Box, at: item.start as number, status: "approximate", note: "a dashed line from the world toward the crew; its fade before arrival is not drawn" });
      } else out.skipped.push({ element_id: l.id, reason: "no room between the world and the crew for the line" });
    }
  }
  // the habitat domes stand where the worlds, icons, links and texts are not (after them, so they never push them)
  if (domes.length) placeDomes(o, domes, out, [...avoid, ...out.placed.filter((p) => p.layer !== "motion_scene").map((p) => rect(p.box)), ...[carrier, ring].filter((i): i is DItem => !!i).map((i) => rect(field(i)))], k);
  // everything drawn here must be clear of the texts and the other layers and inside the safe area, otherwise it is not drawn at all
  const free = (b: Rect) => !avoid.some((a) => hit(a, b)) && b[0] >= MARGIN - 1e-9 && b[2] <= 1 - MARGIN + 1e-9 && b[1] >= MARGIN - 1e-9 && b[3] <= lim + 1e-9;
  const bad = out.placed.filter((p) => p.layer !== "motion_scene" && !free(rect(p.box)));
  if (bad.length) {
    const ids = new Set(bad.map((b) => b.element_id));
    out.layers = out.layers.filter((l) => !ids.has(String(l.elementId)));
    out.placed = out.placed.filter((p) => !ids.has(p.element_id));
    for (const b of bad) out.skipped.push({ element_id: b.element_id, reason: "its place would touch a text, another layer or the margin" });
  }
  return out;
}

const isDome = (e: DEl): boolean => e.type === "graphic" && /\bdomes?\b/i.test(e.desc);
const padded = (t: Rect): Rect => [t[0] - 0.03, t[1] - 0.03, t[2] + 0.03, t[3] + 0.03];
const hex = (v: unknown, d: string): string => (typeof v === "string" && /^#[0-9a-f]{6}$/i.test(v) ? v : d);

/** The areas the Visual Plan planned for its texts (the portrait rules of region_box). */
function plannedTexts(o: DiagramIn): Rect[] {
  const lim = o.tall ? 1 - PORTRAIT_UI : 1 - MARGIN;
  return o.els.filter((e) => e.type === "text" || e.type === "label").flatMap((e): Rect[] => {
    const g = REGION_BOX[e.region];
    if (!g || e.region === "full_frame") return [];
    if (!o.tall) return [g];
    if (e.region === "lower_safe_area") return [[g[0], 1 - 0.18 - (g[3] - g[1]), g[2], 1 - 0.18]];
    if (e.region === "upper_safe_area") return [[g[0], 0.1, g[2], 0.1 + (g[3] - g[1])]];
    return [[g[0], Math.min(g[1], lim), g[2], Math.min(g[3], lim)]];
  });
}

/**
 * Habitat domes: ONE `shape` layer of kind `dome` per element (a cluster of three when the description says cluster / domes, one dome otherwise), standing as low in the safe area as the free space
 * allows and as near the column of its region as possible. Colours are the element's own (`appearance.color`, `appearance.window_color`), else the line and teal colour of the scene.
 * When no place is free of the texts and the other layers, nothing is drawn and the reason is returned.
 */
function placeDomes(o: DiagramIn, domes: DEl[], out: DiagramOut, avoid: Rect[], slot: number): void {
  const { W, H, tall } = o;
  const lim = tall ? 1 - PORTRAIT_UI : 1 - MARGIN;
  const t0 = o.start + 0.3 / o.speed, step = 0.35 / o.speed;
  const taken = [...avoid];
  domes.forEach((e, i) => {
    const n = /\bcluster\b|\bdomes\b/i.test(e.desc) ? 3 : 1;
    const cw = tall ? 0.5 : 0.28, hgt = tallestRadius(cw * W, n) / H, pref = X_OF[e.region] ?? 0.5;
    let best: { x0: number; yb: number } | null = null, bestCost = Infinity;
    for (let x0 = MARGIN; x0 + cw <= 1 - MARGIN + 1e-9; x0 += 0.01) {
      for (let yb = lim; yb - hgt >= MARGIN - 1e-9; yb -= 0.01) {
        const b: Rect = [x0, yb - hgt, x0 + cw, yb];
        if (taken.some((a) => hit(a, b))) continue;
        const cost = Math.abs(x0 + cw / 2 - pref) * 4 + (lim - yb);
        if (cost < bestCost) { bestCost = cost; best = { x0, yb }; }
      }
    }
    if (!best) { out.skipped.push({ element_id: e.id, reason: "no free place for the domes: the texts, the other layers and the margins leave no strip high enough" }); return; }
    const x1 = Math.round(best.x0 * W), x2 = Math.round((best.x0 + cw) * W), y = Math.round(best.yb * H), at = r3(t0 + step * (slot + i));
    const col = hex(e.appearance?.color, o.colors.line), win = hex(e.appearance?.window_color, o.colors.earth);
    out.layers.push({ type: "shape", kind: "dome", elementId: e.id, from: [x1, y], to: [x2, y], count: n, color: col, fill: col, window: win, width: 4, at, dur: r3(0.9 / o.speed), z: 12 });
    const box: Box = [r3(x1 / W), r3(y / H - tallestRadius(x2 - x1, n) / H), r3((x2 - x1) / W), r3(tallestRadius(x2 - x1, n) / H)];
    out.placed.push({ element_id: e.id, kind: "dome", layer: "shape", id: "shape:dome", box, at, status: "resolved", note: `${n === 1 ? "a dome" : `a cluster of ${n} domes`} with lit window arches; shading and surface detail are not drawn` });
    taken.push(rect(box));
  });
}

function iconLayer(id: string, lucide: string, x: number, y: number, size: number, at: number, o: DiagramIn, resource?: { id: string; sha256: string }): Record<string, unknown> {
  return { type: "icon", ...(resource ? { resource_id: resource.id, resource_sha256: resource.sha256 } : { lucide }), elementId: id, pos: [Math.round(x * o.W), Math.round(y * o.H)], size: Math.round(size), color: o.colors.line, enter: { at, anim: "pop", dur: r3(0.5 / o.speed) }, z: 12 };
}
function iconPlaced(id: string, ic: IconInfo, x: number, y: number, size: number, W: number, H: number, at: number): Placed {
  return { element_id: id, kind: "icon", layer: "icon", id: ic.resource ? `resource:${ic.resource.id}` : `icon:${ic.lucide}`, box: [r3(x - size / 2 / W), r3(y - size / 2 / H), r3(size / W), r3(size / H)], at, status: ic.status, note: ic.note };
}

/** The top of the first free strip of the height `h` nearest to where the carrier sits now (above or below the texts); null when there is none. */
function freeStripY(avoid: Rect[], lim: number, h: number, carrier: DItem | undefined, field: (i: DItem) => number[], region = ""): number | null {
  const pref = carrier ? field(carrier)[1] + field(carrier)[3] / 2 : /^upper/.test(region) ? 0.15 : /^lower/.test(region) ? 0.85 : 0.5;
  const ok: number[] = [];
  for (let y = MARGIN; y + h <= lim + 1e-9; y += 0.01) if (!avoid.some((a) => hit(a, [0.08, y, 0.92, y + h]))) ok.push(r3(y));
  return ok.length ? ok.sort((a, b) => Math.abs(a + h / 2 - pref) - Math.abs(b + h / 2 - pref))[0] : null;
}
