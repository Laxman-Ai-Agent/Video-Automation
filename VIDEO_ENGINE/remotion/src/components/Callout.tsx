import { evolvePath } from "@remotion/paths";
import { interpolate, useVideoConfig } from "remotion";
import { ease } from "../anim";
import { useAbsFrame } from "../sceneContext";
import type { LayerT } from "../schema";
import { usePalette } from "../theme";

// Draw-on annotation: arrow | circle | underline | box around/at `target` [x,y] px.
export const Callout: React.FC<{ layer: LayerT }> = ({ layer }) => {
  const l = layer as LayerT & { kind: string; target: [number, number]; size?: [number, number]; color?: string; at?: number; dur?: number };
  const abs = useAbsFrame();
  const { fps, width, height } = useVideoConfig();
  const { accent } = usePalette();
  const t0 = (l.at ?? l.enter?.at ?? 0) * fps;
  const p = interpolate(abs, [t0, t0 + (l.dur ?? 0.7) * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  const [x, y] = l.target;
  const [w, h] = l.size ?? [300, 120];
  const color = l.color ?? accent;
  const paths: Record<string, string> = {
    circle: `M ${x} ${y - h / 2} A ${w / 2} ${h / 2} 0 1 1 ${x - 0.01} ${y - h / 2}`,
    underline: `M ${x - w / 2} ${y + h / 2} Q ${x} ${y + h / 2 + 12} ${x + w / 2} ${y + h / 2 - 4}`,
    box: `M ${x - w / 2} ${y - h / 2} H ${x + w / 2} V ${y + h / 2} H ${x - w / 2} Z`,
    arrow: `M ${x - 260} ${y - 200} Q ${x - 200} ${y - 40} ${x - 14} ${y - 14}`,
  };
  const d = paths[l.kind] ?? paths.circle;
  const ev = evolvePath(p, d);
  const head = l.kind === "arrow" && p > 0.85
    ? <path d={`M ${x - 52} ${y - 18} L ${x - 8} ${y - 8} L ${x - 24} ${y - 52}`} fill="none" stroke={color} strokeWidth={10} strokeLinecap="round" strokeLinejoin="round" /> : null;
  return (
    <svg viewBox={`0 0 ${width} ${height}`} style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      <path d={d} fill="none" stroke={color} strokeWidth={10} strokeLinecap="round" {...ev} />
      {head}
    </svg>
  );
};
