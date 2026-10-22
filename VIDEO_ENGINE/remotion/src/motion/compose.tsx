import { type CSSProperties, useMemo } from "react";
import { useVideoConfig } from "remotion";
import { resolve } from "../registry";
import { useAbsFrame, useScene } from "../sceneContext";
import type { LayerT } from "../schema";
import { layoutFor, usePalette } from "../theme";
import { EASE, clamp01, prog } from "./core";
import { drawGfx } from "./graphics";
import { type MItem, type Resolved, resolveItems } from "./layout";
import { type MaskKind, maskStyle } from "./masks";
import { MotionTextView } from "./text";
import { type TextParams, textFrame } from "./textFrame";

/** Audio-synchronised emphasis for any item: a small scale pulse at each time of `times` (seconds on the audio timeline). Exactly 1 outside the windows. */
export function pulseAt(frame: number, times: number[] | undefined, fps: number, amount = 0.06): number {
  let s = 1;
  for (const t of times ?? []) {
    const d = frame - t * fps, len = 0.5 * fps;
    if (d >= 0 && d <= len) s = Math.max(s, 1 + amount * Math.sin((Math.PI * d) / len));
  }
  return s;
}

function Item({ r, abs, fps, w, h }: { r: Resolved; abs: number; fps: number; w: number; h: number }) {
  const it = r.item;
  const pal = usePalette();
  const lay = layoutFor(w, h);
  if (r.hidden || abs < r.start * fps - 0.001 || abs > r.end * fps) return null;
  const f = (abs - r.start * fps) * (it.speed ?? 1);       // `speed` plays a graphic faster; the item's start, end and exit stay on the audio timeline
  const exitDur = it.exitDur ?? 0.5;
  const q = EASE.inOutSine(prog(abs, (r.end - exitDur) * fps, exitDur * fps));
  const [x, y, bw, bh] = r.box;
  const pulse = pulseAt(abs, it.pulseAt, fps);
  const wrap: CSSProperties = { position: "absolute", left: x, top: y, width: bw, height: bh, transform: pulse !== 1 ? `scale(${pulse})` : undefined, zIndex: it.z ?? 0 };
  const accent = it.accentColor ?? pal.accent;
  if (it.kind === "text") {
    const size = it.size ?? (it.style === "caption" || it.style === "label" ? lay.type.body : lay.type.display);
    const a: TextParams = { text: it.text ?? "", preset: it.preset, exit: it.exit, emphasis: it.emphasis, at: r.start, dur: it.enterDur, until: r.end - exitDur, exitDur, size, weight: it.weight ?? (it.style === "headline" || !it.style ? 800 : 600), maxWidth: bw, dir: it.dir, k: it.k, seed: it.seed ?? it.id ?? r.index, mark: it.mark, emphasisAt: it.emphasisAt, accent, color: it.color, fps, maxLines: 3, fontId: it.fontId as string | undefined, fontSha: it.fontSha as string | undefined };
    const tf = textFrame(a, abs);
    return <div style={{ ...wrap, height: undefined, minHeight: bh, textAlign: it.align ?? "left" }}><MotionTextView f={tf} a={a} /></div>;
  }
  if (it.kind === "reveal") {
    const p = EASE[it.ease ?? "inOutCubic"](clamp01(prog(f, 0, (it.enterDur ?? 1.0) * fps)));
    const C = it.content ? resolve(String((it.content as { type?: string }).type)) : null;
    return <div style={{ ...wrap, overflow: "hidden", opacity: 1 - q, ...maskStyle((it.mask ?? it.preset) as MaskKind, p, { dir: it.dir, seed: it.seed ?? it.id ?? r.index, w: bw, h: bh }) }}>{C && it.content && <C layer={it.content as unknown as LayerT} />}</div>;
  }
  return (
    <div style={{ ...wrap, opacity: 1 - q }}>
      <svg width={bw} height={bh} viewBox={`0 0 ${bw} ${bh}`} style={{ overflow: "visible", display: "block", fontFamily: "inherit" }}>
        {drawGfx(it.preset, { f, fps, w: bw, h: bh, color: it.color ?? "#ffffff", accent, secondary: pal.secondary, seed: it.seed ?? it.id ?? r.index, k: it.k ?? 1, dir: it.dir ?? "right", label: it.label, value: it.value, data: it.data }, it.enterDur)}
      </svg>
    </div>
  );
}

/** Layer `motion_scene`: several independent animated layers (text, graphics, masked images) of one scene with their own start, end, phases and z-order,
 *  placed inside the safe area of either aspect ratio, readable items kept apart. */
export const MotionScene: React.FC<{ layer: LayerT }> = ({ layer }) => {
  const l = layer as LayerT & { items?: MItem[] };
  const abs = useAbsFrame();
  const { fps, width, height } = useVideoConfig();
  const { startFrame, durFrames } = useScene();
  const items = l.items;
  const res = useMemo(() => resolveItems(items ?? [], width, height, startFrame / fps, (startFrame + durFrames) / fps).items, [items, width, height, startFrame, durFrames, fps]);
  return <>{[...res].sort((a, b) => (a.item.z ?? 0) - (b.item.z ?? 0) || a.index - b.index).map((r) => <Item key={r.index} r={r} abs={abs} fps={fps} w={width} h={height} />)}</>;
};

/** Layer `motion_gfx`: one graphic preset (fields: preset, at, dur, box [x,y,w,h] fractions, label, value, data, color, dir, k, seed). */
export const MotionGfxLayer: React.FC<{ layer: LayerT }> = ({ layer }) => {
  const l = layer as LayerT & Partial<MItem> & { at?: number; dur?: number };
  const start = l.at ?? l.enter?.at ?? 0;
  const item: MItem = { ...(l as Partial<MItem>), kind: "gfx", preset: l.preset ?? "line-draw", start, end: l.dur !== undefined ? start + l.dur : undefined, box: l.box ?? [0.3, 0.4, 0.4, 0.2] };
  return <MotionScene layer={{ type: "motion_scene", z: l.z, items: [item] } as unknown as LayerT} />;
};
