import { Fragment, useMemo } from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import { FONT } from "../fonts";
import { SAFE, useLayout, usePalette } from "../theme";

export type Word = { w: string; start: number; end: number };

// Group words into short lines (max 7 words, split on pauses over 0.6s).
const chunk = (words: Word[]) => {
  const out: Word[][] = [];
  let cur: Word[] = [];
  words.forEach((w, i) => {
    if (cur.length && (cur.length >= 7 || w.start - words[i - 1].end > 0.6)) { out.push(cur); cur = []; }
    cur.push(w);
  });
  if (cur.length) out.push(cur);
  return out;
};

export const Subtitles: React.FC<{ words: Word[] }> = ({ words }) => {
  const { fps } = useVideoConfig();
  const lay = useLayout();
  const TYPE = lay.type;
  const t = useCurrentFrame() / fps;
  const { accent } = usePalette();
  const lines = useMemo(() => chunk(words), [words]);
  const line = lines.find((ln) => t >= ln[0].start - 0.05 && t <= ln[ln.length - 1].end + 0.25);
  if (!line) return null;
  return (
    <div style={{ position: "absolute", left: "8%", right: "8%", bottom: lay.portrait ? lay.captionBottom : `${SAFE * 100}%`, textAlign: "center",
      fontFamily: FONT, fontWeight: 600, fontSize: TYPE.body, lineHeight: 1.3, textShadow: "0 3px 14px rgba(0,0,0,0.9)" }}>
      {line.map((w, i) => (
        <Fragment key={i}>
          <span style={{ marginRight: 14, color: t >= w.start && t <= w.end + 0.05 ? accent : "#fff" }}>{w.w}</span>
          {/* a tall frame needs a break opportunity between words, otherwise a long line cannot wrap and runs out of the frame (measured in the real renderer) */}
          {lay.portrait ? " " : null}
        </Fragment>
      ))}
    </div>
  );
};
