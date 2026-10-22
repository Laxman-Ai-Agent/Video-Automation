import { Easing } from "remotion";
import theme from "./theme.json";

const A = theme.accent;
const up = Easing.out(Easing.cubic);
const down = Easing.inOut(Easing.sin);

/**
 * Scale (1 .. theme.accent.pulseScale) of a small emphasis pulse for an element: a quick rise, a slower settle, around each
 * time in `times` (seconds on the audio timeline: keyword times snapped to spoken words, or the moment a highlight/counter
 * finishes). Pulses never stack: the largest one wins. Outside the pulse windows the element is untouched (exactly 1).
 */
export function pulseScale(frame: number, times: number[], fps: number): number {
  let s = 1;
  for (const t of times) {
    const f = frame - t * fps;
    if (f < 0 || f > A.upFrames + A.downFrames) continue;
    const k = f < A.upFrames ? up(f / A.upFrames) : 1 - down((f - A.upFrames) / A.downFrames);
    s = Math.max(s, 1 + (A.pulseScale - 1) * k);
  }
  return s;
}
