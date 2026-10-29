import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";

export interface CameraPose {
  scale: number;
  x: number;          // % of the canvas width the content is shifted by
  y: number;          // % of the canvas height
}

export interface CameraRigProps {
  from: CameraPose;
  to: CameraPose;
  start?: number;     // frame (of the enclosing Sequence) where the move begins
  duration: number;   // frames the move takes
  children?: React.ReactNode;
}

/** A push / pan of its children between two poses. Driven by the current frame only (no timers, no library animation). */
export const CameraRig: React.FC<CameraRigProps> = ({ from, to, start = 0, duration, children }) => {
  const frame = useCurrentFrame();
  const t = interpolate(frame, [start, start + Math.max(1, duration)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.inOut(Easing.cubic),
  });
  const at = (a: number, b: number) => a + (b - a) * t;
  return (
    <AbsoluteFill
      style={{
        transform: `translate(${at(from.x, to.x)}%, ${at(from.y, to.y)}%) scale(${at(from.scale, to.scale)})`,
        transformOrigin: "50% 50%",
      }}
    >
      {children}
    </AbsoluteFill>
  );
};
