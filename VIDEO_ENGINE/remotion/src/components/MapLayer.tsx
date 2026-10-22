import { evolvePath } from "@remotion/paths";
import { geoMercator, geoPath } from "d3-geo";
import { useMemo } from "react";
import { feature } from "topojson-client";
import { interpolate, useVideoConfig } from "remotion";
import { ease, useEnterStyle } from "../anim";
import { FONT } from "../fonts";
import { useAbsFrame } from "../sceneContext";
import type { LayerT } from "../schema";
import { useLayout, usePalette } from "../theme";
import world from "../../public/geo/countries-110m.json";
import indiaStates from "../../public/geo/india-states.json";

const W = 1000, H = 760;
// world-atlas has countries only; indiaStates has Indian regional & Telugu state boundaries.
const countries = (feature(world as never, (world as never as { objects: { countries: never } }).objects.countries) as unknown as
  { features: { properties: { name: string } }[] }).features;
const states = (indiaStates as unknown as { features: { properties: { name: string } }[] }).features;

export const MapLayer: React.FC<{ layer: LayerT }> = ({ layer }) => {
  const l = layer as LayerT & { region?: string; highlight?: string[]; route?: [number, number][]; at?: number; pos?: string; labels?: string[] };
  const abs = useAbsFrame();
  const { fps } = useVideoConfig();
  const st = useEnterStyle(l.enter ?? { at: l.at ?? 0, anim: "slide-left", dur: 0.6 }, l.exit);
  const { accent } = usePalette();
  const { type: TYPE, portrait } = useLayout();
  const t0 = (l.at ?? l.enter?.at ?? 0) * fps;
  const g = useMemo(() => {
    const regLower = (l.region ?? "").toLowerCase();
    const isStateQuery = Boolean(l.region && states.some((s) => s.properties.name.toLowerCase() === regLower));
    const isIndiaQuery = Boolean(l.region && ["india", "bharat", "andhra", "telangana", "ap", "ts"].includes(regLower));

    const activeCollection = (isStateQuery || isIndiaQuery) ? states : countries;
    const focus = l.region && l.region !== "world"
      ? activeCollection.find((c) => c.properties.name.toLowerCase() === regLower)
      : null;

    const proj = geoMercator();
    if (focus) {
      proj.fitExtent([[60, 60], [W - 60, H - 60]], focus as never);
    } else if (isIndiaQuery || isStateQuery) {
      proj.fitSize([W, H], { type: "FeatureCollection", features: states } as never);
    } else {
      proj.fitSize([W, H], { type: "FeatureCollection", features: countries } as never);
    }

    const path = geoPath(proj);
    const hl = new Set((l.highlight ?? []).map((s) => s.toLowerCase()));
    if (focus) {
      hl.add(focus.properties.name.toLowerCase());
    }

    const pts = (l.route ?? []).map((r) => proj(r) as [number, number]);
    return {
      proj,
      d: activeCollection.map((c) => ({
        n: c.properties.name,
        d: path(c as never) ?? "",
        hl: hl.has(c.properties.name.toLowerCase())
      })),
      pts,
      routeD: pts.length > 1 ? `M ${pts.map((q) => q.join(" ")).join(" L ")}` : ""
    };
  }, [l.region, l.highlight, l.route]);
  const p = interpolate(abs, [t0 + 10, t0 + 2.5 * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  const box = portrait ? (l.pos === "right-third" ? { left: 120, width: 840, height: 640, top: 1180 } : { left: 40, width: 1000, height: 760, top: 560 })
    : l.pos === "right-third" ? { right: 40, width: 760, height: 580 } : { left: 460, width: 1000, height: 760 };
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ position: "absolute", top: 160, ...box, ...st,
      WebkitMaskImage: "radial-gradient(ellipse 62% 62% at 50% 50%, #000 55%, transparent 100%)",
      maskImage: "radial-gradient(ellipse 62% 62% at 50% 50%, #000 55%, transparent 100%)" }}>
      {g.d.map((c) => <path key={c.n} d={c.d} fill={c.hl ? accent : "rgba(255,255,255,0.14)"} stroke="rgba(255,255,255,0.3)" strokeWidth={0.6} />)}
      {g.routeD && <path d={g.routeD} fill="none" stroke="#fff" strokeWidth={6} strokeLinecap="round" {...evolvePath(p, g.routeD)} />}
      {g.pts.map((q, i) => {
        const on = p >= (g.pts.length === 1 ? 0 : i / (g.pts.length - 1));
        const pop = on ? 1 : 0;
        return <g key={i} transform={`translate(${q[0]},${q[1]}) scale(${pop})`}>
          <circle r={22} fill="rgba(231,111,81,0.35)" /><circle r={14} fill="#E76F51" stroke="#fff" strokeWidth={4} />
          {l.labels?.[i] && <text x={28} y={10} fill="#fff" fontSize={TYPE.map} fontFamily={FONT} fontWeight={600} stroke="rgba(0,0,0,0.75)" strokeWidth={7} paintOrder="stroke" strokeLinejoin="round">{l.labels[i]}</text>}
        </g>;
      })}
    </svg>
  );
};
