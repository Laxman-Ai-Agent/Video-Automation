import type { TransitionPresentation, TransitionPresentationComponentProps } from "@remotion/transitions";
import { AbsoluteFill, interpolate, random, useVideoConfig } from "remotion";
import { LeakBlob } from "../components/LightLeak";

type P = Record<string, never>;
type Props = TransitionPresentationComponentProps<P>;

const make = (C: React.FC<Props>): TransitionPresentation<P> => ({ component: C, props: {} });
const lerp = (p: number, a: number, b: number) => interpolate(p, [0, 1], [a, b]);

// Entering scene sits on top; exiting scene underneath. Both get presentationProgress 0..1.
export const zoomThrough = make(({ children, presentationDirection: d, presentationProgress: p }) => {
  const enter = d === "entering";
  return <AbsoluteFill style={{
    opacity: enter ? Math.min(1, p * 2) : 1 - Math.max(0, p * 2 - 1),
    transform: `scale(${enter ? lerp(p, 0.7, 1) : lerp(p, 1, 2.4)})`,
  }}>{children}</AbsoluteFill>;
});

export const lightLeak = make(({ children, presentationDirection: d, presentationProgress: p }) => (
  <AbsoluteFill style={{ opacity: d === "entering" ? p : 1 }}>
    {children}
    {d === "entering" && <LeakBlob p={p} />}
  </AbsoluteFill>
));

export const blur = make(({ children, presentationDirection: d, presentationProgress: p }) => {
  const enter = d === "entering";
  return <AbsoluteFill style={{
    opacity: enter ? p : 1 - p * 0.6,
    filter: `blur(${(enter ? 1 - p : p) * 24}px)`,
  }}>{children}</AbsoluteFill>;
});

export const maskShape = make(({ children, presentationDirection: d, presentationProgress: p }) => (
  <AbsoluteFill style={d === "entering" ? { clipPath: `circle(${p * 80}% at 50% 50%)` } : undefined}>{children}</AbsoluteFill>
));

export const matchMove = make(({ children, presentationDirection: d, presentationProgress: p }) => {
  const enter = d === "entering";
  return <AbsoluteFill style={{
    opacity: enter ? Math.min(1, p * 1.6) : 1 - p,
    transform: `translateX(${enter ? lerp(p, 18, 0) : lerp(p, 0, -18)}%) scale(${enter ? lerp(p, 1.12, 1) : lerp(p, 1, 1.12)})`,
  }}>{children}</AbsoluteFill>;
});

export const particle = make(({ children, presentationDirection: d, presentationProgress: p }) => {
  const { width, height } = useVideoConfig();
  return (
  <AbsoluteFill style={{ opacity: d === "entering" ? p : 1 }}>
    {children}
    {d === "entering" && (
      <svg viewBox={`0 0 ${width} ${height}`} style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
        {Array.from({ length: 50 }, (_, i) => (
          <circle key={i} cx={random(`px${i}`) * width + (p - 0.5) * 300 * random(`v${i}`)} cy={random(`py${i}`) * height}
            r={3 + random(`pr${i}`) * 8} fill="#fff" opacity={Math.sin(p * Math.PI) * 0.8} />
        ))}
      </svg>
    )}
  </AbsoluteFill>
  );
});
