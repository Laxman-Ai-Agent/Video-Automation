import type { CSSProperties } from "react";
import { Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { useEnterStyle } from "../anim";
import { useScene } from "../sceneContext";
import type { LayerT } from "../schema";
import { useLayout } from "../theme";

// Named boxes live in theme.json (16:9 table + portrait table) so the backend can work out where a photo's focus point lands on screen.
const boxCss = (boxes: Record<string, [number, number, number, number]>, name: string | undefined): CSSProperties => {
  const [x, y, w, h] = boxes[name ?? "full"] ?? boxes.full;
  return { left: `${x * 100}%`, top: `${y * 100}%`, width: `${w * 100}%`, height: `${h * 100}%` };
};

export const ImageLayer: React.FC<{ layer: LayerT }> = ({ layer }) => {
  // crop = the photo's focus point [x, y] (0..1): when the box is much narrower than the photo (9:16), the visible part is centered on it.
  // zoom (>1, saved in the crop editor) enlarges the photo around that same point, so the point stays where it is on screen.
  const l = layer as LayerT & { file?: string | null; pos?: string | number[]; anim?: string; parallax?: number; crop?: [number, number]; zoom?: number };
  const frame = useCurrentFrame();
  const { durFrames } = useScene();
  const enter = useEnterStyle(l.enter, l.exit);
  const { boxes } = useLayout();
  if (!l.file) return null; // empty slot: nothing to draw until M5 fills it
  const box: CSSProperties = Array.isArray(l.pos)
    ? { left: l.pos[0], top: l.pos[1], width: l.pos[2], height: l.pos[3] }
    : boxCss(boxes, l.pos);
  const kbOn = l.anim === "ken-burns";
  const cutout = l.anim === "float";
  const kb = kbOn ? interpolate(frame, [0, durFrames], [1, 1.06], { extrapolateRight: "clamp" }) : 1;
  const dx = kbOn ? interpolate(frame, [0, durFrames], [0, -1.2], { extrapolateRight: "clamp" }) : 0;
  return (
    <div style={{ position: "absolute", overflow: "hidden", ...box, ...enter,
      ...(l.pos && l.pos !== "full" && !cutout ? { boxShadow: "0 24px 60px rgba(0,0,0,0.55)", borderRadius: 12 } : {}),
      ...(l.parallax ? { marginLeft: interpolate(frame, [0, durFrames], [l.parallax * 120, -l.parallax * 120]) } : {}) }}>
      <Img src={staticFile(l.file)} style={{
        width: "100%", height: "100%", objectFit: cutout ? "contain" : "cover",
        ...(l.crop && !cutout ? { objectPosition: `${l.crop[0] * 100}% ${l.crop[1] * 100}%` } : {}),
        ...(l.crop && l.zoom && l.zoom > 1 && !cutout ? { transformOrigin: `${l.crop[0] * 100}% ${l.crop[1] * 100}%` } : {}),
        transform: `translateX(${dx}%) translateY(${l.anim === "float" ? Math.sin(frame / 25) * 14 : 0}px) scale(${kb * (!cutout && l.zoom && l.zoom > 1 ? l.zoom : 1)})`,
      }} />
    </div>
  );
};
