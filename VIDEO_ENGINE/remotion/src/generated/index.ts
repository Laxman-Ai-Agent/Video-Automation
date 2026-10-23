// The registry of the generated scenes. This file is fixed: it finds the scene_<id>.tsx files next to it by itself (webpack require.context, which Remotion bundles with),
// so nothing writes it. Motion Animation and render staging (VIDEO_ENGINE/stages/motion_animation.py, stages/render.py stage_motion) only copy scene_*.tsx here; those are
// stage outputs, not tracked (.gitignore). On a fresh checkout there is none and the registry is empty.
import React from "react";
import type { ComponentType } from "react";
import type { LayerT } from "../schema";

// require.context is webpack's; @types/webpack-env is not installed, so the part used here is typed here.
declare const require: {
  context(directory: string, recursive: boolean, filter: RegExp): { keys(): string[]; (key: string): { default: ComponentType<any> } };
};

const scenes = require.context("./", false, /^\.\/scene_.+\.tsx$/);

export const customSceneRegistry: Record<string, ComponentType<any>> = {};
for (const key of scenes.keys()) {
  const name = key.replace(/^\.\/scene_/, "").replace(/\.tsx$/, "");
  const Comp = scenes(key).default;
  customSceneRegistry[name] = Comp;
  customSceneRegistry[`scene_${name}`] = Comp;
}

export function getCustomScene(name: string | number): ComponentType<any> | null {
  return customSceneRegistry[String(name)] || customSceneRegistry[`scene_${name}`] || null;
}

export const CustomSceneLayer: React.FC<{ layer: LayerT }> = ({ layer }) => {
  const sceneId = (layer as any).scene_id ?? (layer as any).id;
  const Comp = getCustomScene(sceneId);
  if (!Comp) {
    return null;
  }
  return React.createElement(Comp, { layer });
};

export default customSceneRegistry;
