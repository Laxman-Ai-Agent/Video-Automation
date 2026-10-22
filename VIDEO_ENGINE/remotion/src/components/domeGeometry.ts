// The geometry of the `dome` kind of the `shape` layer: a row of 1 to 5 half-discs (domes) standing on one base line, the tallest in the middle, each with a lit window arch.
// Pure and deterministic. `from` and `to` of the layer are the two ends of the base line: the whole cluster fills that width, so the tallest dome is DOME_RATIOS[0] x R0 high.
// backend/motion_generation.rect_of_layer repeats the radius formula (it needs the height of a drawn dome to check the layout): tests/test_motion_validation.py compares the two.

/** Radius of each dome relative to the tallest one, in the order they are drawn when they are sorted by size. */
export const DOME_RATIOS = [1, 0.7, 0.5, 0.4, 0.3];
/** The gap between two neighbouring domes, as a share of the tallest radius. */
export const DOME_GAP = 0.1;
/** Left to right, the index into DOME_RATIOS of each dome: the tallest stands in the middle. */
const ORDER: number[][] = [[0], [0, 1], [1, 0, 2], [1, 0, 2, 3], [3, 1, 0, 2, 4]];

export interface Dome { cx: number; r: number }

export const domeCount = (count: unknown): number => Math.max(1, Math.min(DOME_RATIOS.length, Math.round(Number(count) || 1)));

/** The radius of the tallest dome of a cluster of `count` domes that fills the width `w`. */
export const tallestRadius = (w: number, count: number): number => {
  const n = domeCount(count);
  return w / (2 * DOME_RATIOS.slice(0, n).reduce((a, b) => a + b, 0) + DOME_GAP * (n - 1));
};

/** The domes of the cluster between the base ends x1 and x2 (centres and radii in the same unit as x1 and x2). */
export function domeLayout(x1: number, x2: number, count: unknown): Dome[] {
  const n = domeCount(count), left = Math.min(x1, x2), R0 = tallestRadius(Math.abs(x2 - x1), n);
  let x = left;
  return ORDER[n - 1].map((idx) => {
    const r = R0 * DOME_RATIOS[idx], d = { cx: x + r, r };
    x += 2 * r + DOME_GAP * R0;
    return d;
  });
}

/** SVG path of the dome bodies: one half-disc per dome, closed along the base line (y). */
export const domeBodies = (domes: Dome[], y: number): string => domes.map(({ cx, r }) => `M ${cx - r} ${y} A ${r} ${r} 0 0 1 ${cx + r} ${y} Z`).join(" ");

/** SVG path of the lit windows: an arch of 0.16 r half-width and 0.42 r height at the foot of every dome. */
export const domeWindows = (domes: Dome[], y: number): string => domes.map(({ cx, r }) => { const w = 0.16 * r, h = 0.42 * r; return `M ${cx - w} ${y} V ${y - h + w} A ${w} ${w} 0 0 1 ${cx + w} ${y - h + w} V ${y} Z`; }).join(" ");
