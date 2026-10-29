import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

export interface KineticWord {
  text: string;
  frame: number;      // frame (of the enclosing Sequence) where this word appears: its own spoken start_frame
}

export interface KineticWordsProps {
  words: KineticWord[];
  fontSize: number;
  color: string;
  fontFamily?: string;
  fontWeight?: number;
  gap?: number;       // px between words
  align?: "flex-start" | "center" | "flex-end";
}

/** Words that spring in one by one, each at its own frame. Every word stays visible to the end once it has appeared. */
export const KineticWords: React.FC<KineticWordsProps> = ({ words, fontSize, color, fontFamily, fontWeight = 800, gap = Math.round(fontSize * 0.3), align = "center" }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <div style={{ display: "flex", flexWrap: "wrap", justifyContent: align, columnGap: gap, rowGap: Math.round(gap / 2) }}>
      {words.map((w, i) => {
        const p = spring({ frame: frame - w.frame, fps, config: { damping: 14, stiffness: 140 } });
        return (
          <span
            key={`${i}-${w.text}`}
            style={{
              fontSize,
              color,
              fontFamily,
              fontWeight,
              lineHeight: 1.15,
              opacity: interpolate(p, [0, 1], [0, 1], { extrapolateRight: "clamp" }),
              transform: `translateY(${interpolate(p, [0, 1], [fontSize * 0.5, 0])}px) scale(${interpolate(p, [0, 1], [0.92, 1])})`,
              display: "inline-block",
            }}
          >
            {w.text}
          </span>
        );
      })}
    </div>
  );
};
