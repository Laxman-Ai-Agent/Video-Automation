import { arc, line, pie } from "d3-shape";
import { scaleBand, scaleLinear } from "d3-scale";
import { useMemo } from "react";
import { interpolate, useVideoConfig } from "remotion";
import { ease } from "../anim";
import { FONT } from "../fonts";
import { useAbsFrame } from "../sceneContext";
import type { LayerT } from "../schema";
import { useLayout, usePalette } from "../theme";

type D = { label: string; value: number };
const EXTRA = ["#E76F51", "#8AB17D", "#6C8EAD", "#C77DFF"];   // further series colors; the first two are the palette's accent and secondary
const W = 1100, H = 560;

export const Chart: React.FC<{ layer: LayerT }> = ({ layer }) => {
  const l = layer as LayerT & { kind: "bar" | "line" | "pie" | "donut" | "horizontal_bar"; data: D[]; at?: number; dur?: number; title?: string;
    box?: [number, number, number, number]; focus?: number; focusAt?: number };
  const abs = useAbsFrame();
  const { fps } = useVideoConfig();
  const { accent, secondary } = usePalette();
  const { type: TYPE, portrait } = useLayout();
  const COLORS = [accent, secondary, ...EXTRA];
  const t0 = (l.at ?? 0) * fps;
  const [bx, by, bw, bh] = l.box ?? (portrait ? [40, 560, 1000, 640] : [260, 150, 1400, 780]);
  const p = interpolate(abs, [t0, t0 + (l.dur ?? 1.2) * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  const max = Math.max(...l.data.map((d) => d.value));
  const total = l.data.reduce((sum, d) => sum + d.value, 0);
  const g = useMemo(() => ({
    x: scaleBand().domain(l.data.map((d) => d.label)).range([0, W]).padding(0.3),
    y: scaleLinear().domain([0, max * 1.1]).range([H, 0]),
    hx: scaleLinear().domain([0, max * 1.15]).range([0, W - 260]),
    hy: scaleBand().domain(l.data.map((d) => d.label)).range([0, H]).padding(0.25),
    arcs: pie<D>().value((d) => d.value).sort(null)(l.data),
  }), [l.data, max]);
  const txt = { fontFamily: FONT, fill: "#fff", fontSize: TYPE.chart, fontWeight: 600 } as const;
  const fp = interpolate(abs, [(l.focusAt ?? 0) * fps, (l.focusAt ?? 0) * fps + 18], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  return (
    <svg viewBox={`-80 -100 ${W + 160} ${H + 220}`} style={{ position: "absolute", left: bx, top: by, width: bw, height: bh, opacity: Math.min(1, p * 4) }}>
      <defs>{COLORS.map((c, i) => (
        <linearGradient key={i} id={`bar${i}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={c} /><stop offset="1" stopColor={c} stopOpacity={0.65} /></linearGradient>
      ))}</defs>
      {l.kind !== "pie" && l.kind !== "donut" && <>
        {[0.25, 0.5, 0.75, 1].map((f) => <line key={f} x1={0} x2={W} y1={H - f * H} y2={H - f * H} stroke="rgba(255,255,255,0.14)" strokeWidth={2} />)}
        <line x1={0} x2={W} y1={H} y2={H} stroke="rgba(255,255,255,0.7)" strokeWidth={4} />
      </>}
      {l.kind === "bar" && l.data.map((d, i) => {
        const h = (H - g.y(d.value)) * p;
        const cx = (g.x(d.label) ?? 0) + g.x.bandwidth() / 2;
        return <g key={d.label}>
          <rect x={g.x(d.label)} y={H - h} width={g.x.bandwidth()} height={h} rx={10} fill={`url(#bar${i % 6})`} />
          <text x={cx} y={H + 64} textAnchor="middle" {...txt}>{d.label}</text>
          <text x={cx} y={H - h - 18} textAnchor="middle" {...txt} fontWeight={800}>{Math.round(d.value * p).toLocaleString("en-US")}</text>
          {l.focus === i && <ellipse cx={cx} cy={H - h - 28} rx={g.x.bandwidth() / 2 + 20} ry={78}
            fill="none" stroke="#fff" strokeWidth={8} strokeLinecap="round" strokeDasharray={`${fp * 2400} 2400`} opacity={fp > 0 ? 1 : 0}  />}
        </g>;
      })}
      {l.kind === "horizontal_bar" && l.data.map((d, i) => {
        const yPos = g.hy(d.label) ?? 0;
        const barH = g.hy.bandwidth();
        const barW = Math.max(4, g.hx(d.value) * p);
        return <g key={d.label}>
          <text x={-20} y={yPos + barH / 2 + 8} textAnchor="end" {...txt}>{d.label}</text>
          <rect x={0} y={yPos} width={barW} height={barH} rx={8} fill={COLORS[i % 6]} />
          <text x={barW + 18} y={yPos + barH / 2 + 8} textAnchor="start" {...txt} fontWeight={800}>{Math.round(d.value * p).toLocaleString("en-US")}</text>
        </g>;
      })}
      {l.kind === "line" && (() => {
        const pts = l.data.map((d) => [(g.x(d.label) ?? 0) + g.x.bandwidth() / 2, g.y(d.value)] as [number, number]);
        const d = line()(pts) ?? "";
        return <g>
          <path d={d} fill="none" stroke={accent} strokeWidth={10} strokeLinecap="round" strokeLinejoin="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - p} />
          {pts.map((pt, i) => <g key={i} opacity={p > i / pts.length ? 1 : 0}>
            <circle cx={pt[0]} cy={pt[1]} r={16} fill="#fff" stroke={accent} strokeWidth={6} />
            <text x={pt[0]} y={pt[1] - 30} textAnchor="middle" {...txt} fontWeight={800} stroke="rgba(6,24,32,0.9)" strokeWidth={10} strokeLinejoin="round" paintOrder="stroke">{l.data[i].value.toLocaleString("en-US")}</text>
            <text x={pt[0]} y={H + 64} textAnchor="middle" {...txt}>{l.data[i].label}</text></g>)}
        </g>;
      })()}
      {(l.kind === "pie" || l.kind === "donut") && <g transform={`translate(${W / 2},${H / 2})`}>
        {g.arcs.map((a, i) => {
          const innerR = l.kind === "donut" ? 160 : 60;
          const outerR = 270;
          const end = a.startAngle + (a.endAngle - a.startAngle) * p;
          const path = arc<unknown>().innerRadius(innerR).outerRadius(outerR).cornerRadius(8).padAngle(0.02)({ startAngle: a.startAngle, endAngle: end } as never) ?? "";
          const [cx, cy] = arc<unknown>().innerRadius(outerR + 50).outerRadius(outerR + 50).centroid({ startAngle: a.startAngle, endAngle: a.endAngle } as never);
          return <g key={i}><path d={path} fill={COLORS[i % 6]} />
            <text x={cx} y={cy} textAnchor="middle" opacity={p} {...txt}>{l.data[i].label}</text></g>;
        })}
        {l.kind === "donut" && <g opacity={p}>
          <text x={0} y={-8} textAnchor="middle" fill="#fff" fontSize={TYPE.chart * 1.3} fontFamily={FONT} fontWeight={800}>{Math.round(total * p).toLocaleString("en-US")}</text>
          <text x={0} y={32} textAnchor="middle" fill="rgba(255,255,255,0.7)" fontSize={TYPE.chart * 0.75} fontFamily={FONT} fontWeight={500}>Total</text>
        </g>}
      </g>}
    </svg>
  );
};
