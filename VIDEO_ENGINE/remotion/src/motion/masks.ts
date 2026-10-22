import type { CSSProperties } from "react";
import { type Dir, clamp01, rnd } from "./core";

export type MaskKind =
  | "iris-circle" | "iris-diamond" | "bars-h" | "bars-v" | "diagonal-stripes" | "directional" | "split-open-h" | "split-open-v"
  | "layered-strips" | "spotlight" | "corner-wipe" | "slit-scan";

export interface MaskInfo { id: MaskKind; label: string; category: "shape-wipe" | "directional" | "split" | "layered" | "spotlight"; desc: string }
export const MASKS: MaskInfo[] = [
  { id: "iris-circle", label: "Circle iris", category: "shape-wipe", desc: "a circle opens from the centre" },
  { id: "iris-diamond", label: "Diamond iris", category: "shape-wipe", desc: "a diamond opens from the centre" },
  { id: "bars-h", label: "Horizontal blinds", category: "shape-wipe", desc: "eight horizontal bars open" },
  { id: "bars-v", label: "Vertical blinds", category: "shape-wipe", desc: "eight vertical bars open" },
  { id: "diagonal-stripes", label: "Diagonal stripes", category: "shape-wipe", desc: "diagonal stripes widen until the picture is complete" },
  { id: "corner-wipe", label: "Corner wipe", category: "shape-wipe", desc: "a diagonal wipe from the top-left corner" },
  { id: "directional", label: "Directional reveal", category: "directional", desc: "a hard edge moves across in the given direction" },
  { id: "slit-scan", label: "Slit reveal", category: "directional", desc: "a thin slit widens in the given direction" },
  { id: "split-open-h", label: "Split screen (horizontal)", category: "split", desc: "the picture opens from a centre line toward left and right" },
  { id: "split-open-v", label: "Split screen (vertical)", category: "split", desc: "the picture opens from a centre line upward and downward" },
  { id: "layered-strips", label: "Layered strips", category: "layered", desc: "three strips reveal one after the other (layered mask)" },
  { id: "spotlight", label: "Spotlight", category: "spotlight", desc: "a soft circular spotlight grows over the picture" },
];
export const MASK_IDS = MASKS.map((m) => m.id);

const set = (m: string): CSSProperties => ({ WebkitMaskImage: m, maskImage: m } as CSSProperties);
const stripes = (angle: string, size: number, open: number) => set(`repeating-linear-gradient(${angle}, #000 0px, #000 ${(open * size).toFixed(2)}px, transparent ${(open * size).toFixed(2)}px, transparent ${size.toFixed(2)}px)`);

/** CSS that shows the part of an element a mask transition has revealed at progress p (0 = nothing, 1 = everything: no mask at all). */
export function maskStyle(kind: MaskKind, p0: number, o: { dir?: Dir; seed?: string | number; w: number; h: number }): CSSProperties {
  const p = clamp01(p0);
  if (p >= 1) return {};
  const dir = o.dir ?? "left";
  const e = ((1 - p) * 100).toFixed(2);
  switch (kind) {
    case "iris-circle": return { clipPath: `circle(${(p * 78).toFixed(2)}% at 50% 50%)` };
    case "iris-diamond": { const d = p * 76; return { clipPath: `polygon(50% ${(50 - d).toFixed(2)}%, ${(50 + d).toFixed(2)}% 50%, 50% ${(50 + d).toFixed(2)}%, ${(50 - d).toFixed(2)}% 50%)` }; }
    case "bars-h": return stripes("to bottom", o.h / 8, p);
    case "bars-v": return stripes("to right", o.w / 8, p);
    case "diagonal-stripes": return stripes("135deg", Math.max(o.w, o.h) / 7, p);
    case "corner-wipe": return { clipPath: `polygon(0 0, ${(p * 210).toFixed(2)}% 0, 0 ${(p * 210).toFixed(2)}%)` };
    case "directional": return { clipPath: { left: `inset(0 ${e}% 0 0)`, right: `inset(0 0 0 ${e}%)`, up: `inset(0 0 ${e}% 0)`, down: `inset(${e}% 0 0 0)` }[dir] };
    case "slit-scan": { const a = ((1 - p) * 50).toFixed(2); return { clipPath: dir === "up" || dir === "down" ? `inset(${a}% 0 ${a}% 0)` : `inset(0 ${a}% 0 ${a}%)` }; }
    case "split-open-h": return { clipPath: `inset(0 ${((1 - p) * 50).toFixed(2)}% 0 ${((1 - p) * 50).toFixed(2)}%)` };
    case "split-open-v": return { clipPath: `inset(${((1 - p) * 50).toFixed(2)}% 0 ${((1 - p) * 50).toFixed(2)}% 0)` };
    case "layered-strips": {
      const ps = [0, 1, 2].map((i) => clamp01(p * 1.7 - i * 0.35));
      const image = ps.map((q) => `linear-gradient(to right, #000 ${(q * 100).toFixed(2)}%, transparent ${(q * 100).toFixed(2)}%)`).join(", ");
      return { WebkitMaskImage: image, maskImage: image, WebkitMaskSize: "100% 33.4%", maskSize: "100% 33.4%", WebkitMaskRepeat: "no-repeat", maskRepeat: "no-repeat", WebkitMaskPosition: "0 0, 0 50%, 0 100%", maskPosition: "0 0, 0 50%, 0 100%" } as CSSProperties;
    }
    case "spotlight": { const x = 30 + rnd(o.seed ?? 0, 1) * 40, y = 35 + rnd(o.seed ?? 0, 2) * 30; return set(`radial-gradient(circle at ${x.toFixed(1)}% ${y.toFixed(1)}%, #000 ${(p * 70).toFixed(2)}%, transparent ${(p * 70 + 18).toFixed(2)}%)`); }
  }
}
