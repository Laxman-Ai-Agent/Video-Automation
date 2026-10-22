import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { AbsoluteFill, Easing, useCurrentFrame, useVideoConfig } from "remotion";
import { Camera } from "./components/Camera";
import { CAMERA_TYPES, resolve } from "./registry";
import { SceneCtx } from "./sceneContext";
import type { LayerT, SceneT } from "./schema";
import { getPresentation } from "./transitions";

/** An image layer with a file (empty slots render nothing) or a stock video. */
const showsPhoto = (l: LayerT) => (l.type === "image" && !!(l as LayerT & { file?: string }).file) || l.type === "stock-video";

/** A layer switched off in the timeline (enabled: false) stays in the composition but is not drawn. */
const isOn = (l: LayerT) => (l as LayerT & { enabled?: boolean }).enabled !== false;

const SceneBody: React.FC<{ scene: SceneT }> = ({ scene }) => {
  useCurrentFrame();
  const layers = scene.layers.filter(isOn).sort((a, b) => a.z - b.z);
  const draw = (l: LayerT, i: number) => {
    const C = resolve(l.type);
    return C ? <C key={i} layer={l} /> : null;
  };
  return (
    <AbsoluteFill>
      <Camera cam={scene.camera}>{layers.filter((l) => CAMERA_TYPES.has(l.type)).map(draw)}</Camera>
      {layers.filter((l) => !CAMERA_TYPES.has(l.type)).map(draw)}
    </AbsoluteFill>
  );
};

/**
 * Each scene is extended by its outgoing transition; the overlap is subtracted by
 * TransitionSeries, so scene N still starts exactly at scene.start (audio sync).
 */
export const SceneRoot: React.FC<{ scenes: SceneT[]; fps: number }> = ({ scenes, fps }) => {
  const { width, height } = useVideoConfig();
  const items: React.ReactNode[] = [];
  scenes.forEach((s, i) => {
    const start = Math.round(s.start * fps);
    const base = Math.round(s.end * fps) - start;
    const hasNext = i < scenes.length - 1;
    const t = hasNext ? s.transition_out : undefined;
    const outFr = t ? Math.min(Math.round(t.dur * fps), base - 1) : 0;
    items.push(
      <TransitionSeries.Sequence key={`s${s.id}`} durationInFrames={base + outFr}>
        <SceneCtx.Provider value={{ startFrame: start, durFrames: base, hasImage: s.layers.filter(isOn).some(showsPhoto) }}>
          <SceneBody scene={s} />
        </SceneCtx.Provider>
      </TransitionSeries.Sequence>,
    );
    if (t && outFr > 0) {
      items.push(
        <TransitionSeries.Transition key={`t${s.id}`} presentation={getPresentation(t.type, width, height)}
          timing={linearTiming({ durationInFrames: outFr, easing: Easing.inOut(Easing.cubic) })} />,
      );
    }
  });
  return <TransitionSeries>{items}</TransitionSeries>;
};
