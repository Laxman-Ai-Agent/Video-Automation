import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { FONT } from "../fonts";
import type { Comp } from "../schema";
import { SAFE, useLayout, usePalette } from "../theme";

export type Caption = NonNullable<Comp["captions"]>[number];

// A caption shows a little before its first word and after its last one. render_cache.CAPTION_PAD covers this window: keep the two together.
const LEAD_S = 0.05;
const TAIL_S = 0.25;
const POP_FRAMES = 4;

/**
 * Draws the caption lines the backend built (stages/captions.py: grouping, hook and key terms are decided there, once).
 * The word being spoken is in the accent colour and pops in; a key term (a number, or a word the picture stresses too) is bold and underlined; the HOOK
 * (the first caption, inside the first seconds) is larger, in the same place (the middle of the frame is where the scenes draw their hero; a real frame showed a
 * centred hook hiding it). Every caption is on a dark plate so it reads on any scene without the generated scenes having to leave room for it, and its lines are balanced
 * (a one-word second line looked like a mistake).
 */
export const Subtitles: React.FC<{ captions: Caption[] }> = ({ captions }) => {
  const { fps } = useVideoConfig();
  const lay = useLayout();
  const frame = useCurrentFrame();
  const t = frame / fps;
  const { secondary: highlight } = usePalette();            // not `accent`: that role is the BRIGHTEST palette colour (cream in the test project), which does not stand out from the white words
  const cap = captions.find((c) => t >= c.start - LEAD_S && t <= c.end + TAIL_S);
  if (!cap) return null;

  // 1. 50% smaller font size than the original (compact, cinematic & readable)
  const currentSize = cap.hook ? Math.round(lay.type.display * 0.55) : lay.type.body;
  const size = Math.round(currentSize * 0.5);

  // 2. Cumulative / progressive word-by-word reveal as spoken
  const visibleWords = cap.words.filter((w) => t >= w.start);
  if (visibleWords.length === 0) return null;

  return (
    <div
      style={{
        position: "absolute",
        left: "5%",
        right: "5%",
        bottom: lay.portrait ? lay.captionBottom : `${SAFE * 100}%`,
        textAlign: "center",
        fontFamily: FONT,
        fontSize: size,
        lineHeight: 1.3,
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        pointerEvents: "none",
      }}
    >
      <span
        style={{
          display: "inline-block",
          padding: "0.22em 0.7em",
          borderRadius: "0.4em",
          background: "rgba(0, 0, 0, 0.65)",
          backdropFilter: "blur(4px)",
          textShadow: "0 2px 8px rgba(0, 0, 0, 0.9)",
          whiteSpace: "nowrap",
          maxWidth: "92%",
          overflow: "hidden",
          textOverflow: "ellipsis",
        }}
      >
        {visibleWords.map((w, i) => {
          const active = t >= w.start && t <= w.end + 0.05;
          const since = frame - Math.round(w.start * fps);
          const pop = active ? interpolate(since, [0, POP_FRAMES], [1.14, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) : 1;
          return (
            <span key={i}>
              <span
                style={{
                  display: "inline-block",
                  transform: `scale(${pop})`,
                  fontWeight: w.key ? 800 : 600,
                  color: active ? highlight : "#fff",
                  textDecoration: w.key ? "underline" : "none",
                  textDecorationColor: highlight,
                  textUnderlineOffset: "0.12em",
                }}
              >
                {w.w}
              </span>
              {" "}
            </span>
          );
        })}
      </span>
    </div>
  );
};
