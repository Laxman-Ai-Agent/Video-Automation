import type { CSSProperties } from "react";
import { interpolate, spring, useVideoConfig } from "remotion";
import { pulseScale } from "../accent";
import { FONT } from "../fonts";
import { useAbsFrame, useScene } from "../sceneContext";
import type { LayerT } from "../schema";
import { fitFontSize } from "../textfit";
import { SAFE, SCRIM, useLayout, usePalette, mix, luminance } from "../theme";

const pct = (v: number) => `${v * 100}%`;
const scrim = `rgba(0,0,0,${SCRIM})`;

// Sizes come from the type scale, boxes stay inside the safe margin, panels use the shared scrim.
// A tall frame (9:16) keeps captions above the bottom 16-20% that phone apps cover (theme.json portrait).
const styles = ({ type: TYPE, captionBottom, lowerThirdBottom, labelTop, portrait }: ReturnType<typeof useLayout>): Record<string, CSSProperties> => ({
  "big-highlight": { fontSize: TYPE.display, fontWeight: 800, left: 0, right: 0, top: "38%", textAlign: "center", padding: `0 ${pct(SAFE)}` },
  caption: { fontSize: TYPE.body, fontWeight: 600, left: 0, right: 0, bottom: captionBottom, textAlign: "center", width: "fit-content",
    maxWidth: pct(1 - 2 * SAFE), margin: "0 auto", background: scrim, padding: "10px 32px", borderRadius: 16 },
  label: { fontSize: TYPE.body, fontWeight: 600, left: pct(0.06), top: labelTop, maxWidth: pct(portrait ? 0.88 : 0.6), background: scrim, padding: "8px 24px", borderRadius: 14 },
  "lower-third": { fontSize: TYPE.body, fontWeight: 600, left: pct(0.06), bottom: lowerThirdBottom, maxWidth: pct(portrait ? 0.88 : 0.7), background: scrim, padding: "14px 32px" },
});

export const HighlightText: React.FC<{ layer: LayerT }> = ({ layer }) => {
  const l = layer as LayerT & { text: string; style?: string; at?: number; dur?: number; mark?: string; markColor?: string; pos?: [number, number]; center?: boolean;
    pulses?: number[]; pulse?: boolean };
  const abs = useAbsFrame();
  const { fps, width } = useVideoConfig();
  const lay = useLayout();
  const TYPE = lay.type;
  const { hasImage } = useScene();
  const { accent } = usePalette();
  const rawStyle = l.style ?? "caption";
  const styleMap = styles(lay);
  const style = styleMap[rawStyle] ? rawStyle : (rawStyle.includes("highlight") || rawStyle.includes("hero") || rawStyle.includes("title") ? "big-highlight" : "caption");
  const t0 = (l.at ?? l.enter?.at ?? 0) * fps;
  const s = spring({ frame: abs - t0, fps, config: { damping: 16, stiffness: 110 } });
  const opacity = interpolate(abs, [t0, t0 + 10], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const sweep = interpolate(abs, [t0 + 8, t0 + 26], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const exitAt = l.exit ? l.exit.at : (l.dur ? (l.at ?? 0) + l.dur : undefined);
  const exitDur = l.exit?.dur ?? 0.5;
  const out = exitAt !== undefined ? interpolate(abs, [exitAt * fps, (exitAt + exitDur) * fps], [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) : 1;
  const markColor = l.markColor ?? accent;
  const isBright = luminance(markColor) > 0.45;
  const targetColor = isBright ? "#111111" : "#ffffff";
  const markTextColor = mix("#ffffff", targetColor, Math.max(0, Math.min(1, sweep)));
  // a small pulse when the highlight finishes sweeping and at every later keyword of the scene (spoken-word times); pulse:false turns it off
  const pulse = l.pulse === false ? 1 : pulseScale(abs, [...(l.mark ? [(t0 + 26) / fps] : []), ...(l.pulses ?? [])], fps);
  // long headlines shrink (down to 70%) to stay on one line inside the safe margin; beyond that they wrap
  const fitted = style === "big-highlight" && !l.pos ? { fontSize: fitFontSize(l.text ?? "", TYPE.display, 800, width * (1 - 2 * SAFE)) } : {};
  // text over a photo gets a dark band behind it (rules.md: no text over busy areas without a scrim)
  const band: CSSProperties = style === "big-highlight" && hasImage
    ? { padding: `12px ${pct(SAFE)}`, background: `linear-gradient(90deg, rgba(0,0,0,0), ${scrim} 18%, ${scrim} 82%, rgba(0,0,0,0))` } : {};

  const markWords = (l.mark ?? "").trim().toLowerCase().split(/\s+/).filter(Boolean);
  const isWordMarked = (w: string) => {
    if (!l.mark) return false;
    const clean = w.toLowerCase().replace(/[^\w\u0C00-\u0C7F]/g, "");
    if (!clean) return false;
    return markWords.some((mw) => {
      const cleanMw = mw.replace(/[^\w\u0C00-\u0C7F]/g, "");
      return cleanMw && (clean.includes(cleanMw) || cleanMw.includes(clean));
    });
  };

  const textContent = l.text ?? "";

  return (
    <div style={{
      position: "absolute", fontFamily: FONT, color: "#fff", lineHeight: 1.1,
      textShadow: "0 6px 30px rgba(0,0,0,0.6)", letterSpacing: -0.5, wordSpacing: "0.3em",
      ...styleMap[style],
      ...(style === "lower-third" ? { borderLeft: `8px solid ${accent}` } : {}),
      ...band,
      ...fitted,
      ...(l.pos ? { left: l.pos[0], top: l.pos[1], right: "auto", bottom: "auto", textAlign: "left", transformOrigin: "center" } : {}),
      // a tall frame has no room to the right of a pinned text: it wraps inside the safe width (16:9 keeps its old behavior)
      ...(l.pos && lay.portrait ? { maxWidth: l.center ? 2 * Math.min(l.pos[0], width - l.pos[0]) - 2 * width * SAFE : width * (1 - SAFE) - l.pos[0] } : {}),
      opacity: opacity * out,
      transform: `${l.center ? "translateX(-50%) " : ""}translateY(${(1 - s) * 70}px)${pulse !== 1 ? ` scale(${pulse})` : ""}`,
    }}>{l.mark ? textContent.split(" ").map((w, i) => isWordMarked(w)
      ? <span key={i} style={{
          display: "inline-block",
          padding: "2px 10px",
          marginRight: 12,
          borderRadius: 8,
          color: markTextColor,
          textShadow: sweep > 0.6 && isBright ? "none" : "0 6px 30px rgba(0,0,0,0.6)",
          background: `linear-gradient(${markColor}, ${markColor}) no-repeat left / ${sweep * 100}% 100%`,
        }}>{w}</span>
      : <span key={i} style={{ marginRight: 12 }}>{w}</span>) : textContent}</div>
  );
};
