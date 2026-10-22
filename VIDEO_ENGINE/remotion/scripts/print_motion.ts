// Prints what the renderer's camera and pulse functions return, so tests/test_m9.py can check them numerically.
// THEME_INPUT = {"cams": [{"cam": {...}, "dur": 150, "seed": "s", "frames": [0, 1, ...]}],
//                "curveSamples": [0, 0.5, 1], "pulses": [{"times": [1.0], "fps": 30, "frames": [...]}]}
import { pulseScale } from "../src/accent";
import { CURVES, cameraAt, type Cam } from "../src/camera";

type CamCase = { cam: Cam; dur: number; seed: string; frames: number[] };
type PulseCase = { times: number[]; fps: number; frames: number[] };
const input = JSON.parse(process.env.THEME_INPUT ?? "{}") as { cams?: CamCase[]; curveSamples?: number[]; pulses?: PulseCase[] };
console.log(JSON.stringify({
  cams: (input.cams ?? []).map((c) => c.frames.map((f) => cameraAt(c.cam, f, c.dur, c.seed))),
  curves: Object.fromEntries(Object.entries(CURVES).map(([name, fn]) => [name, (input.curveSamples ?? []).map((t) => fn(t))])),
  pulses: (input.pulses ?? []).map((p) => p.frames.map((f) => pulseScale(f, p.times, p.fps))),
}));
