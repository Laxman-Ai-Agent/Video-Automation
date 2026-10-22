import { evolvePath } from "@remotion/paths";
import { noise2D } from "@remotion/noise";
import { interpolate, random, useVideoConfig } from "remotion";
import { ease } from "../anim";
import { useAbsFrame } from "../sceneContext";
import type { LayerT } from "../schema";
import { usePalette } from "../theme";
import { checkmarkTimeline } from "./checkmarkTimeline";

const star = (r: number) => `M0 ${-r} Q0 0 ${r} 0 Q0 0 0 ${r} Q0 0 ${-r} 0 Q0 0 0 ${-r} Z`;
const MAX_PARTICLES = 60;

export const Effect: React.FC<{ layer: LayerT }> = ({ layer }) => {
  const l = layer as LayerT & { name: string; at: number; pos?: [number, number]; dur?: number; color?: string; count?: number };
  const abs = useAbsFrame();
  const { fps, width, height } = useVideoConfig();
  const dur = (l.dur ?? (l.name === "particles" ? 6 : 1.2)) * fps;
  const f = abs - l.at * fps;
  if (f < 0 || f > dur) return null;
  const p = f / dur;
  const [x, y] = l.pos ?? [width / 2, height / 2];
  const { accent, secondary } = usePalette();
  const c = l.color ?? accent;
  let body: React.ReactNode = null;
  if (l.name === "sparkle") {
    const s = interpolate(p, [0, 0.4, 1], [0, 1, 0], { easing: ease });
    body = <g transform={`translate(${x},${y}) rotate(${p * 90}) scale(${s})`}><path d={star(70)} fill={c} /><path d={star(36)} fill="#fff" /></g>;
  } else if (l.name === "burst") {
    body = <g transform={`translate(${x},${y})`}>{Array.from({ length: 14 }, (_, i) => {
      const a = (i / 14) * Math.PI * 2, r0 = 40 + p * 160, r1 = r0 + 60 * (1 - p);
      return <line key={i} x1={Math.cos(a) * r0} y1={Math.sin(a) * r0} x2={Math.cos(a) * r1} y2={Math.sin(a) * r1}
        stroke={c} strokeWidth={14} strokeLinecap="round" opacity={1 - p} />;
    })}<circle r={30 + p * 150} fill="none" stroke="#fff" strokeWidth={6 * (1 - p)} opacity={1 - p} />
      <circle r={40 * (1 - p)} fill="#fff" opacity={0.9} /></g>;
  } else if (l.name === "glow") {
    const o = Math.sin(p * Math.PI);
    body = <><defs><radialGradient id={`g${l.at}`}><stop offset="0" stopColor={c} stopOpacity={0.8} /><stop offset="1" stopColor={c} stopOpacity={0} /></radialGradient></defs>
      <circle cx={x} cy={y} r={420} fill={`url(#g${l.at})`} opacity={o} /></>;
  } else if (l.name === "checkmark") {
    const d = "M-50 0 L-15 38 L55 -40";
    const k = checkmarkTimeline(f / fps, dur / fps); // one paused GSAP timeline sought to this frame (see gsapTimeline.ts): deterministic
    const e = evolvePath(k.draw, d);
    body = <g transform={`translate(${x},${y})`} opacity={k.fade}>
      <circle r={90 * k.pop} fill={secondary} opacity={0.9} /><path d={d} fill="none" stroke="#fff" strokeWidth={16} strokeLinecap="round" strokeLinejoin="round" {...e} /></g>;
  } else if (l.name === "particles") {
    const n = Math.min(l.count ?? 40, MAX_PARTICLES);
    body = <>{Array.from({ length: n }, (_, i) => {
      const px = random(`x${i}`) * width, py = random(`y${i}`) * height, r = 3 + random(`r${i}`) * 8;
      const dx = noise2D("a" + i, f / 90, 0) * 60, dy = noise2D("b" + i, f / 90, 1) * 60 - f * 0.25;
      const cx = px + dx, cy = (py + dy + height * 4) % height, o = (0.35 + 0.5 * random(`o${i}`)) * Math.min(1, p * 8) * Math.min(1, (1 - p) * 8);
      return <g key={i}><circle cx={cx} cy={cy} r={r * 3} fill="#fff" opacity={o * 0.18} /><circle cx={cx} cy={cy} r={r} fill="#fff" opacity={o} /></g>;
    })}</>;
  }
  return <svg viewBox={`0 0 ${width} ${height}`} style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>{body}</svg>;
};
