import { Easing, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import type { CSSProperties } from "react";
import type { EnterT } from "./schema";
import { useAbsFrame } from "./sceneContext";

export const ease = Easing.bezier(0.22, 1, 0.36, 1);

/** Style for an enter animation starting at enter.at (absolute seconds). */
export function useEnterStyle(enter?: EnterT, exit?: EnterT): CSSProperties {
  const abs = useAbsFrame();
  const { fps } = useVideoConfig();
  let opacity = 1;
  let transform = "";
  let clipPath: string | undefined;
  if (enter) {
    const t0 = enter.at * fps;
    const p = interpolate(abs, [t0, t0 + enter.dur * fps], [0, 1], {
      extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease,
    });
    if (enter.anim === "pop") {
      const s = spring({ frame: abs - t0, fps, config: { damping: 12, stiffness: 140 } });
      transform = `scale(${abs < t0 ? 0 : s})`;
      opacity = abs < t0 ? 0 : Math.min(1, p * 3);
    } else {
      opacity = p;
      if (enter.anim === "slide-left") transform = `translateX(${(1 - p) * 160}px)`;
      if (enter.anim === "slide-up") transform = `translateY(${(1 - p) * 80}px)`;
      if (enter.anim === "wipe") { clipPath = `inset(0 ${(1 - p) * 100}% 0 0)`; opacity = abs < t0 ? 0 : 1; }
    }
  }
  if (exit) {
    const t1 = exit.at * fps;
    opacity *= interpolate(abs, [t1, t1 + exit.dur * fps], [1, 0], {
      extrapolateLeft: "clamp", extrapolateRight: "clamp",
    });
  }
  return { opacity, transform: transform || undefined, clipPath };
}

export { useCurrentFrame };
