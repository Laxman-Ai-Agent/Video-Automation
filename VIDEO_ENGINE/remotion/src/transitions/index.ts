import { clockWipe } from "@remotion/transitions/clock-wipe";
import { fade } from "@remotion/transitions/fade";
import { flip } from "@remotion/transitions/flip";
import { slide } from "@remotion/transitions/slide";
import { wipe } from "@remotion/transitions/wipe";
import type { TransitionPresentation } from "@remotion/transitions";
import * as c from "./custom";
import byMood from "./by_mood.json";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Pres = TransitionPresentation<any>;

export const TRANSITIONS = [
  "fade", "slide", "wipe", "flip", "clock-wipe",
  "zoom-through", "light-leak", "blur", "mask-shape", "match-move", "particle",
] as const;

export function getPresentation(type: string, width = 1920, height = 1080): Pres {
  switch (type) {
    case "slide": return slide();
    case "wipe": return wipe();
    case "flip": return flip();
    case "clock-wipe": return clockWipe({ width, height });
    case "zoom-through": return c.zoomThrough;
    case "light-leak": return c.lightLeak;
    case "blur": return c.blur;
    case "mask-shape": return c.maskShape;
    case "match-move": return c.matchMove;
    case "particle": return c.particle;
    case "fade": return fade();
    default:
      console.warn(`[transition] unknown "${type}", using fade`);
      return fade();
  }
}

// Shared with backend/transition_audit.py, which checks plans against the same table.
const BY_MOOD: Record<string, string[]> = byMood;

/** Choose a transition for the mood; never returns `prev`. `index` rotates choices deterministically. */
export function pickTransition(prev: string | undefined, mood: string, index = 0): string {
  const key = Object.keys(BY_MOOD).find((k) => mood.toLowerCase().includes(k)) ?? "calm";
  const opts = BY_MOOD[key].filter((t) => t !== prev);
  const pool = opts.length ? opts : TRANSITIONS.filter((t) => t !== prev);
  return pool[index % pool.length];
}
