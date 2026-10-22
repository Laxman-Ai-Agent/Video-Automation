import { interpolate, random, useCurrentFrame, useVideoConfig } from "remotion";
import { useScene } from "../sceneContext";
import type { LayerT } from "../schema";
import { mix, usePalette } from "../theme";

/** Background looks (layer field `look`). `gradient` is the original two-colour sweep and the default, so every older composition renders exactly as before.
 *  The others are slow, deterministic light fields (CSS radial gradients only, no filter and no canvas: cheap on a CPU render).
 *  gradient: calm sweep | aurora: soft drifting colour clouds | mesh: four corner glows | spotlight: one moving beam of light on a dark field. */
export const BACKGROUND_LOOKS = ["gradient", "aurora", "mesh", "spotlight"] as const;
export type BackgroundLook = (typeof BACKGROUND_LOOKS)[number];

const a = (hex: string, alpha: number) => `${hex}${Math.round(Math.max(0, Math.min(1, alpha)) * 255).toString(16).padStart(2, "0")}`;
const wave = (t: number, period: number, phase: number) => Math.sin((t / period + phase) * Math.PI * 2);
const blob = (x: number, y: number, rx: number, ry: number, color: string) => `radial-gradient(ellipse ${rx}% ${ry}% at ${x.toFixed(2)}% ${y.toFixed(2)}%, ${color}, transparent 70%)`;

export const Background: React.FC<{ layer: LayerT }> = ({ layer }) => {
  const l = layer as LayerT & { colors?: string[]; look?: string; seed?: string | number; k?: number };
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { durFrames } = useScene();
  const { base, secondary } = usePalette();
  const [c1, c2] = l.colors ?? [base, secondary];
  const look = (BACKGROUND_LOOKS as readonly string[]).includes(l.look ?? "") ? (l.look as BackgroundLook) : "gradient";
  const angle = interpolate(frame, [0, durFrames], [120, 160], { extrapolateRight: "clamp" });
  if (look === "gradient") return <div style={{ position: "absolute", inset: 0, background: `linear-gradient(${angle}deg, ${c1}, ${c2})` }} />;

  const t = frame / fps;
  const k = l.k ?? 1;                                   // intensity of the light (0.5 subtle .. 1.5 strong)
  const ph = (i: number) => random(`${l.seed ?? "bg"}:${i}`);   // the same seed always gives the same drift
  const end = mix(c1, c2, look === "spotlight" ? 0.45 : look === "aurora" ? 0.75 : 1);   // how far the base sweep travels toward the secondary colour: the scene keeps its palette
  const glow = mix(c2, "#ffffff", 0.3);                 // lights come from the secondary colour: the accent stays for text and highlights, never the background
  const haze = mix(c1, c2, 0.5);
  let layers: string[];
  if (look === "aurora") {
    layers = [
      blob(30 + 14 * wave(t, 17, ph(0)), 35 + 12 * wave(t, 23, ph(1)), 70, 55, a(glow, 0.38 * k)),
      blob(72 + 12 * wave(t, 19, ph(2)), 62 + 14 * wave(t, 29, ph(3)), 65, 60, a(mix(c2, "#ffffff", 0.12), 0.55 * k)),
      blob(50 + 18 * wave(t, 31, ph(4)), 85 + 6 * wave(t, 13, ph(5)), 80, 40, a(mix(glow, "#ffffff", 0.35), 0.12 * k)),
    ];
  } else if (look === "mesh") {
    layers = [
      blob(8 + 6 * wave(t, 21, ph(0)), 12 + 6 * wave(t, 25, ph(1)), 60, 70, a(glow, 0.3 * k)),
      blob(92 + 5 * wave(t, 27, ph(2)), 10 + 7 * wave(t, 18, ph(3)), 55, 65, a(c2, 0.55 * k)),
      blob(88 + 6 * wave(t, 24, ph(4)), 92 + 5 * wave(t, 22, ph(5)), 60, 70, a(haze, 0.45 * k)),
      blob(10 + 7 * wave(t, 20, ph(6)), 90 + 5 * wave(t, 26, ph(7)), 55, 65, a(mix(glow, "#ffffff", 0.2), 0.18 * k)),
    ];
  } else {                                                // spotlight: one soft beam sweeps slowly, the field around it stays dark
    const x = 50 + 28 * wave(t, 26, ph(0));
    layers = [
      blob(x, 28, 42, 62, a(mix(glow, "#ffffff", 0.4), 0.3 * k)),
      blob(x, 95, 55, 30, a(glow, 0.16 * k)),
      "radial-gradient(ellipse 120% 100% at 50% 50%, transparent 55%, rgba(0,0,0,0.45) 100%)",
    ];
  }
  return <div style={{ position: "absolute", inset: 0, background: `${layers.join(", ")}, linear-gradient(${angle}deg, ${c1}, ${end})` }} />;
};
