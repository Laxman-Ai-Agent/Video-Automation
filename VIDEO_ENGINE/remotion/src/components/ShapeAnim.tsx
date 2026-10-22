import { evolvePath } from "@remotion/paths";
import { interpolate, useVideoConfig } from "remotion";
import { ease } from "../anim";
import { useAbsFrame } from "../sceneContext";
import type { LayerT } from "../schema";
import { domeBodies, domeLayout, domeWindows } from "./domeGeometry";

// line (from->to), rect (from=top-left, to=bottom-right), circle (from=center, to=edge point), dome (from, to = the ends of the base line, see domeGeometry.ts).
export const ShapeAnim: React.FC<{ layer: LayerT }> = ({ layer }) => {
  const l = layer as LayerT & { kind: string; from: [number, number]; to: [number, number]; color?: string; width?: number; at?: number; dur?: number; fill?: string };
  const abs = useAbsFrame();
  const { fps, width, height } = useVideoConfig();
  const t0 = (l.at ?? l.enter?.at ?? 0) * fps;
  const p = interpolate(abs, [t0, t0 + (l.dur ?? 0.8) * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  const [x1, y1] = l.from, [x2, y2] = l.to;
  if (l.kind === "dome") {                    // dome: from / to = the two ends of the base line; `count` (1-5) domes fill that width; the outline is drawn, then the body and the lit windows (`window`) appear
    const L = l as typeof l & { count?: number; window?: string };
    const base = (y1 + y2) / 2, domes = domeLayout(x1, x2, L.count);
    const d = domeBodies(domes, base);
    const lit = interpolate(abs, [t0 + (l.dur ?? 0.8) * fps, t0 + (l.dur ?? 0.8) * fps + 0.4 * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
    return (
      <svg viewBox={`0 0 ${width} ${height}`} style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
        <path d={d} stroke={l.color ?? "#fff"} strokeWidth={l.width ?? 6} strokeLinecap="round" strokeLinejoin="round" fill={l.fill && p >= 1 ? l.fill : "none"} {...evolvePath(p, d)} />
        {L.window ? <path d={domeWindows(domes, base)} fill={L.window} opacity={lit} /> : null}
      </svg>
    );
  }
  const d = l.kind === "rect" ? `M ${x1} ${y1} H ${x2} V ${y2} H ${x1} Z`
    : l.kind === "circle" ? (() => { const r = Math.hypot(x2 - x1, y2 - y1);
        return `M ${x1 + r} ${y1} A ${r} ${r} 0 1 1 ${x1 + r - 0.01} ${y1}`; })()
    : `M ${x1} ${y1} L ${x2} ${y2}`;
  return (
    <svg viewBox={`0 0 ${width} ${height}`} style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      <path d={d} stroke={l.color ?? "#fff"} strokeWidth={l.width ?? 6} strokeLinecap="round"
        fill={l.fill && p >= 1 ? l.fill : "none"} {...evolvePath(p, d)} />
    </svg>
  );
};
