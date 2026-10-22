import { Easing } from "remotion";
import { noise2D } from "@remotion/noise";
import theme from "./theme.json";

// The scene camera as pure functions of (camera settings, frame): easy to test, no hidden state.
export type CamMove = "push-in" | "pull-out" | "pan-left" | "pan-right" | "zoom-to-focus" | "static";
export interface Cam { move: CamMove; from: number; to: number; focus: [number, number]; drift?: number }
export interface CamState { scale: number; tx: number; ty: number; rot: number; originX: number; originY: number }

const C = theme.camera;
const bezier = (b: number[]) => Easing.bezier(b[0], b[1], b[2], b[3]);
// One curve per kind of move (theme.json). A zoom or pan is slow and even: ease in AND out, never a burst at the start.
export const CURVES = { push: bezier(C.easing.push), pan: bezier(C.easing.pan), focus: bezier(C.easing.focus) };

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

/**
 * Camera transform `frame` frames into a scene that lasts `durFrames`. tx/ty are % of the frame, rot is degrees,
 * the origin is where the zoom aims (frame coordinates, %). `drift` (0..1, default off) adds a seeded handheld sway
 * of at most theme.camera.drift (0.3 % shift, 0.15 deg) plus a little extra scale so the edges never show.
 */
export function cameraAt(cam: Cam, frame: number, durFrames: number, seed: string): CamState {
  const t = Math.min(Math.max(frame / Math.max(durFrames, 1), 0), 1);
  let scale = 1;
  let tx = 0;
  switch (cam.move) {
    case "push-in": scale = lerp(cam.from, cam.to, CURVES.push(t)); break;
    case "pull-out": scale = lerp(cam.to, cam.from, CURVES.push(t)); break;
    case "zoom-to-focus": scale = lerp(cam.from, Math.max(cam.to, C.focusScale), CURVES.focus(t)); break;
    case "pan-left": scale = 1.12; tx = lerp(3, -3, CURVES.pan(t)); break;
    case "pan-right": scale = 1.12; tx = lerp(-3, 3, CURVES.pan(t)); break;
  }
  let ty = 0;
  let rot = 0;
  const d = Math.min(Math.max(cam.drift ?? 0, 0), 1);
  if (d > 0) {
    const n = frame / C.drift.period;
    tx += noise2D(seed + "x", n, 0) * C.drift.maxShiftPct * d;
    ty = noise2D(seed + "y", n, 1) * C.drift.maxShiftPct * d;
    rot = noise2D(seed + "r", n, 2) * C.drift.maxRotateDeg * d;
    scale *= 1 + C.drift.headroom * d;
  }
  return { scale, tx, ty, rot, originX: cam.focus[0] * 100, originY: cam.focus[1] * 100 };
}
