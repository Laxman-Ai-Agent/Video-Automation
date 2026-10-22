import { z } from "zod";

const enter = z.object({
  at: z.number(),
  anim: z.enum(["fade", "slide-left", "slide-up", "pop", "wipe", "draw"]).default("fade"),
  dur: z.number().default(0.5),
});

// Layers are validated loosely here; each component reads its own fields.
// Unknown `type` values are skipped with a warning by the registry.
export const Layer = z.looseObject({
  type: z.string(),
  z: z.number().default(0),
  enter: enter.optional(),
  exit: enter.optional(),
});

const Camera = z.object({
  move: z.enum(["push-in", "pull-out", "pan-left", "pan-right", "zoom-to-focus", "static"]),
  from: z.number().default(1),
  to: z.number().default(1.1),
  focus: z.tuple([z.number(), z.number()]).default([0.5, 0.5]),
  drift: z.number().min(0).max(1).optional(),   // handheld sway strength; omitted = a perfectly steady camera
});

const Scene = z.object({
  id: z.number(),
  start: z.number(),
  end: z.number(),
  pattern: z.string().optional(),
  camera: Camera.default({ move: "static", from: 1, to: 1, focus: [0.5, 0.5] }),
  layers: z.array(Layer),
  transition_out: z.object({ type: z.string(), dur: z.number() }).optional(),
});

export const CompositionSchema = z.object({
  meta: z.object({
    fps: z.number().default(30),
    width: z.number().default(1920),
    height: z.number().default(1080),
    audio: z.string(),
    duration: z.number(),
    subtitles: z.boolean().default(false),
    // set by backend fill from scene_plan.style; roles: [base, accent, secondary] (see theme.ts)
    palette: z.array(z.string()).min(2).optional(),
    grade: z.enum(["warm", "cool", "teal-orange"]).optional(),
    motion: z.enum(["rich"]).optional(),   // set when the scenes were built with the motion library (A2V_MOTION=1)
    motionOnly: z.boolean().optional(),    // Use Images = OFF: the scenes have no pictures, only motion graphics and text (build_composition.ts --no-images)
    motionSpeed: z.number().optional(),    // pace factor the motion library was built with (1 = the preset durations, 1.4 = 40 % shorter)
    kit: z.string().optional(),            // the style kit the scenes were built with (A2V_STYLE_KIT, src/styleKit.ts); absent = no kit
  }),
  scenes: z.array(Scene).min(1),
  words: z.array(z.object({ w: z.string(), start: z.number(), end: z.number() })).optional(),
});

export type Comp = z.infer<typeof CompositionSchema>;
export type SceneT = z.infer<typeof Scene>;
export type LayerT = z.infer<typeof Layer>;
export type EnterT = z.infer<typeof enter>;
