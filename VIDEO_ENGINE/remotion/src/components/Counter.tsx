import { interpolate, useVideoConfig } from "remotion";
import { pulseScale } from "../accent";
import { ease } from "../anim";
import { FONT } from "../fonts";
import { useAbsFrame } from "../sceneContext";
import type { LayerT } from "../schema";
import { fitFontSize } from "../textfit";
import { BACKING, SAFE, backingColor, useLayout, usePalette } from "../theme";

export const Counter: React.FC<{ layer: LayerT }> = ({ layer }) => {
  const l = layer as LayerT & { from?: number; to: number; unit?: string; at?: number; dur?: number; decimals?: number; pos?: [number, number]; pulse?: boolean; backing?: boolean };
  const abs = useAbsFrame();
  const { fps, width, height } = useVideoConfig();
  const TYPE = useLayout().type;
  const t0 = (l.at ?? 0) * fps;
  const v = interpolate(abs, [t0, t0 + (l.dur ?? 2) * fps], [l.from ?? 0, l.to], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  const fade = interpolate(abs, [t0 - 6, t0 + 6], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const dec = l.decimals ?? 0;
  const [x, y] = l.pos ?? [width / 2, height / 2];
  const { accent } = usePalette();
  const pulse = l.pulse === false ? 1 : pulseScale(abs, [(l.at ?? 0) + (l.dur ?? 2)], fps);   // a small pulse when the number lands
  // the final number is the widest it gets: size the whole counter once so it never leaves the safe margin
  const last = l.to.toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec });
  const size = fitFontSize(last + (l.unit ? "  " + l.unit : ""), TYPE.hero, 800, width * (1 - 2 * SAFE));
  return (
    <div style={{ position: "absolute", left: x, top: y, transform: `translate(-50%,-50%)${pulse !== 1 ? ` scale(${pulse})` : ""}`, opacity: fade,
      fontFamily: FONT, fontWeight: 800, color: "#fff", fontSize: size, textShadow: "0 8px 40px rgba(0,0,0,0.6)",
      fontVariantNumeric: "tabular-nums", whiteSpace: "nowrap",
      // backing: a dark rounded panel for a number that sits on a photo (theme.json "backing"); without it the counter is drawn exactly as before
      ...(l.backing ? { padding: `${size * BACKING.pad * 0.4}px ${size * BACKING.pad}px`, borderRadius: size * 0.3, background: backingColor() } : {}) }}>
      {v.toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec })}
      {l.unit && <span style={{ fontSize: size * TYPE.unit / TYPE.hero, marginLeft: 20, color: accent }}>{l.unit}</span>}
    </div>
  );
};
