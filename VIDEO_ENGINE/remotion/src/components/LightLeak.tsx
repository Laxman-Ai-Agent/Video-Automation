import { interpolate, useVideoConfig } from "remotion";
import { useAbsFrame } from "../sceneContext";
import type { LayerT } from "../schema";

// CSS-only light leak: a warm gradient sweeping across the frame, screen-blended.
export const LeakBlob: React.FC<{ p: number; color?: string }> = ({ p, color = "255,150,60" }) => (
  <div style={{ position: "absolute", inset: 0, mixBlendMode: "screen", pointerEvents: "none",
    opacity: Math.sin(Math.max(0, Math.min(1, p)) * Math.PI) * 0.85,
    background: `radial-gradient(ellipse 60% 90% at ${interpolate(p, [0, 1], [-10, 110])}% 40%, rgba(${color},0.95), rgba(${color},0) 70%)` }} />
);

export const LightLeak: React.FC<{ layer: LayerT }> = ({ layer }) => {
  const l = layer as LayerT & { at: number; dur?: number; color?: string };
  const abs = useAbsFrame();
  const { fps } = useVideoConfig();
  const p = (abs - l.at * fps) / ((l.dur ?? 1.2) * fps);
  return p < 0 || p > 1 ? null : <LeakBlob p={p} color={l.color} />;
};
