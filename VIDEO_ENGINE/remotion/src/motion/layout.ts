import { SAFE, layoutFor } from "../theme";
import { type Box, type Dir, breakLines, inside, overlaps } from "./core";
import type { EaseName } from "./core";
import { GFX_PRESETS } from "./graphics";
import type { MaskKind } from "./masks";

/** One animated element of a motion scene. Boxes are fractions of the frame [x, y, w, h] so one description works for 16:9 and 9:16 (boxTall overrides it in a tall frame). */
export interface MItem {
  id?: string;
  kind: "text" | "gfx" | "reveal";
  preset: string;                 // text preset / graphic preset / mask kind
  fontId?: string; fontSha?: string;     // text items: a registered font (Resource Library) and the hash the item was built with
  start: number;                  // seconds on the audio timeline
  end?: number;                   // default: the end of the scene
  enterDur?: number; exitDur?: number; exit?: string; ease?: EaseName;
  delay?: number; group?: string; // items of one group enter one after the other (stagger = delay x position in the group)
  z?: number;
  box: Box; boxTall?: Box;
  bleed?: boolean;                // a full-frame atmosphere layer (particles, light): may touch the frame edge, never counts as an obstacle
  // text
  text?: string; style?: "headline" | "caption" | "label" | "quote"; mark?: string; emphasisAt?: number[]; emphasis?: string; size?: number; weight?: number; align?: "left" | "center" | "right";
  // graphic
  label?: string; value?: number; data?: number[]; color?: string; accentColor?: string;
  // reveal: a layer (an image or a stock video) shown through a mask transition
  content?: Record<string, unknown>; mask?: MaskKind;
  dir?: Dir; k?: number; seed?: string | number;
  pulseAt?: number[];             // audio-synchronised emphasis: the item pulses at these times
  speed?: number;                 // graphic items: playback speed of the preset (1 = as designed, 1.4 = 40 % faster)
}

export interface Resolved { item: MItem; index: number; box: Box; start: number; end: number; hidden: boolean; warnings: string[] }

export const PORTRAIT_BOTTOM = 0.16; // phone apps cover the bottom 16% of a 9:16 frame

/** The area text may use: the safe margin on every side, and in a tall frame also the bottom strip. */
export function safeRect(w: number, h: number): Box {
  const portrait = h > w;
  const x0 = SAFE * w, y0 = SAFE * h, y1 = h * (1 - (portrait ? PORTRAIT_BOTTOM : SAFE));
  return [x0, y0, w - 2 * x0, y1 - y0];
}

/** Does this item hold readable content (text or a label)? Those must not overlap each other while they are on screen at the same time. */
export const isBlocking = (it: MItem): boolean => it.kind === "text" || (it.kind === "gfx" && !!it.label) || (it.kind === "gfx" && ["data-callout-card", "stat-counter", "hud-readout"].includes(it.preset));

function textHeight(it: MItem, boxW: number, w: number, h: number): number {
  const lay = layoutFor(w, h);
  const size = it.size ?? (it.style === "caption" || it.style === "label" ? lay.type.body : lay.type.display);
  return breakLines(it.text ?? "", size, it.weight ?? 800, boxW).length * size * 1.15 + size * 0.2;
}

/** Pixel boxes inside the safe area; overlapping readable items that are visible at the same time are moved apart (down first, then up). Nothing is dropped: an
 *  unresolvable overlap is reported in `warnings` (a text is never hidden: every script word is displayed), only a decorative label graphic may be suppressed. */
export function resolveItems(items: MItem[], w: number, h: number, sceneStart: number, sceneEnd: number): { items: Resolved[]; warnings: string[] } {
  const portrait = h > w;
  const [sx, sy, sw, sh] = safeRect(w, h);
  const out: Resolved[] = items.map((item, index) => {
    const f = portrait && item.boxTall ? item.boxTall : item.box;
    const warnings: string[] = [];
    let [x, y, bw, bh] = [f[0] * w, f[1] * h, f[2] * w, f[3] * h];
    if (item.kind === "text") bh = textHeight(item, Math.min(bw, sw), w, h);
    if (!item.bleed) {
      bw = Math.min(bw, sw); bh = Math.min(bh, sh);
      const nx = Math.min(Math.max(x, sx), sx + sw - bw), ny = Math.min(Math.max(y, sy), sy + sh - bh);
      if (Math.abs(nx - x) > 0.5 || Math.abs(ny - y) > 0.5) warnings.push("moved into the safe area");
      x = nx; y = ny;
    } else { x = Math.max(0, Math.min(x, w - bw)); y = Math.max(0, Math.min(y, h - bh)); }
    const start = Math.max(sceneStart, item.start) + (item.delay ?? 0);
    return { item, index, box: [x, y, bw, bh] as Box, start, end: Math.min(sceneEnd, item.end ?? sceneEnd), hidden: false, warnings };
  });
  // group stagger: the n-th item of a group starts n x delay later (the delay of the item itself is its step)
  const seen: Record<string, number> = {};
  for (const r of out) if (r.item.group) { const n = seen[r.item.group] ?? 0; seen[r.item.group] = n + 1; r.start += n * (r.item.delay ?? 0.18); }

  const placed: Resolved[] = [];
  const order = out.filter((r) => isBlocking(r.item) && !r.item.bleed).sort((a, b) => a.start - b.start || (a.item.z ?? 0) - (b.item.z ?? 0) || a.index - b.index);
  const gap = h * 0.012;
  for (const r of order) {
    // the earlier readable items that are on screen at the same time as this one
    const rivals = placed.filter((o) => !o.hidden && r.start < o.end && o.start < r.end);
    const clash = (y: number) => rivals.find((o) => overlaps([r.box[0], y, r.box[2], r.box[3]], o.box));
    if (clash(r.box[1])) {
      // candidate positions: just below or just above every rival, nearest to the wanted place first; the first one that clashes with nobody wins
      const cands = [sy, ...rivals.flatMap((o) => [o.box[1] + o.box[3] + gap, o.box[1] - r.box[3] - gap])]
        .filter((y) => y >= sy - 0.5 && y + r.box[3] <= sy + sh + 0.5).sort((a, b) => Math.abs(a - r.box[1]) - Math.abs(b - r.box[1]));
      const y = cands.find((c) => !clash(c));
      if (y !== undefined) r.box = [r.box[0], y, r.box[2], r.box[3]];
      else {
        r.warnings.push(`overlaps ${clash(r.box[1])?.item.id ?? "another item"} and cannot be moved`);
        if (r.item.kind === "gfx") r.hidden = true;           // a decorative label may go, a text never does
      }
    }
    placed.push(r);
  }
  const warnings = out.flatMap((r) => r.warnings.map((m) => `${r.item.id ?? r.index}: ${m}`));
  return { items: out, warnings };
}

/** True when every visible item lies inside the frame. */
export const allInside = (rs: Resolved[], w: number, h: number): boolean => rs.every((r) => r.hidden || inside(r.box, w, h, 0));
/** True when two readable items that are visible at the same time overlap. */
export const hasReadableOverlap = (rs: Resolved[]): boolean => {
  const bl = rs.filter((r) => !r.hidden && isBlocking(r.item) && !r.item.bleed);
  return bl.some((a, i) => bl.slice(i + 1).some((b) => a.start < b.end && b.start < a.end && overlaps(a.box, b.box)));
};
export const gfxExists = (id: string) => !!GFX_PRESETS[id];
