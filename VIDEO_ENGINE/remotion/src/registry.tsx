import type { ComponentType } from "react";
import { Background } from "./components/Background";
import { HighlightText } from "./components/HighlightText";
import { ImageLayer } from "./components/ImageLayer";
import { Callout } from "./components/Callout";
import { Chart } from "./components/Chart";
import { Counter } from "./components/Counter";
import { Effect } from "./components/Effect";
import { IconPop } from "./components/IconPop";
import { LightLeak } from "./components/LightLeak";
import { MapLayer } from "./components/MapLayer";
import { ShapeAnim } from "./components/ShapeAnim";
import { StockVideo } from "./components/StockVideo";
import { MotionGfxLayer, MotionScene } from "./motion/compose";
import { MotionTextLayer } from "./motion/text";
import { CustomSceneLayer } from "./generated";
import type { LayerT } from "./schema";

type LayerC = ComponentType<{ layer: LayerT }>;

export const registry: Record<string, LayerC> = {
  background: Background,
  image: ImageLayer,
  text: HighlightText,
  hero_text: HighlightText,
  "hero-text": HighlightText,
  title: HighlightText,
  headline: HighlightText,
  caption: HighlightText,
  motion: HighlightText,
  motion_graphics: HighlightText,
  "motion-graphics": HighlightText,
  icon: IconPop,
  callout: Callout,
  shape: ShapeAnim,
  counter: Counter,
  "number counter": Counter,
  "number-counter": Counter,
  stat_counter: Counter,
  chart: Chart,
  "bar chart": Chart,
  "line chart": Chart,
  "pie chart": Chart,
  chart_focus: Chart,
  map: MapLayer,
  effect: Effect,
  "stock-video": StockVideo,
  "light-leak": LightLeak,
  // the motion library (src/motion): text presets, graphic presets and multi-layer scenes, all frame-driven
  motion_text: MotionTextLayer,
  motion_gfx: MotionGfxLayer,
  motion_scene: MotionScene,
  custom_scene: CustomSceneLayer,
  custom_motion: CustomSceneLayer,
};

/** Layers affected by the scene camera; everything else is a screen-space overlay. */
export const CAMERA_TYPES = new Set(["background", "image", "stock-video"]);

const warned = new Set<string>();
export function resolve(type: string): LayerC | null {
  const norm = (type || "").toLowerCase().trim();
  const c = registry[norm] ?? registry[type];
  if (c) return c;
  if (norm.includes("counter")) return Counter;
  if (norm.includes("chart")) return Chart;
  if (norm.includes("callout") || norm.includes("arrow")) return Callout;
  if (norm.includes("text") || norm.includes("title") || norm.includes("headline") || norm.includes("caption") || norm.includes("motion")) return HighlightText;
  if (norm.includes("icon")) return IconPop;
  if (norm.includes("effect") || norm.includes("glow") || norm.includes("sparkle")) return Effect;
  if (!warned.has(type)) {
    warned.add(type);
    console.warn(`[registry] unknown layer type "${type}" skipped`);
  }
  return null;
}
