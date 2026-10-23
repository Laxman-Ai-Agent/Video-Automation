// The registry of the generated scenes. This file is fixed: it finds the scene_<id>.tsx files next to it by itself (webpack require.context, which Remotion bundles with),
// so nothing writes it. Motion Animation and render staging (VIDEO_ENGINE/stages/motion_animation.py, stages/render.py stage_motion) only copy scene_*.tsx here; those are
// stage outputs, not tracked (.gitignore). On a fresh checkout there is none and the registry is empty.
// The scenes are looked up on first use, not when the module loads: the scripts that import this file under plain Node (motion_validate.ts ...) never draw a scene, and require.context
// exists only inside the webpack bundle.
import React from "react";
import type { ComponentType } from "react";
import type { LayerT } from "../schema";

// require.context is webpack's; @types/webpack-env is not installed, so the part used here is typed here.
declare const require: {
  context(directory: string, recursive: boolean, filter: RegExp): { keys(): string[]; (key: string): { default: ComponentType<any> } };
};

let registry: Record<string, ComponentType<any>> | null = null;

function scenes(): Record<string, ComponentType<any>> {
  if (registry === null) {
    const context = require.context("./", false, /^\.\/scene_.+\.tsx$/);
    registry = {};
    for (const key of context.keys()) {
      const name = key.replace(/^\.\/scene_/, "").replace(/\.tsx$/, "");
      const Comp = context(key).default;
      registry[name] = Comp;
      registry[`scene_${name}`] = Comp;
    }
  }
  return registry;
}

export function getCustomScene(name: string | number): ComponentType<any> | null {
  const all = scenes();
  return all[String(name)] || all[`scene_${name}`] || null;
}

export const CustomSceneLayer: React.FC<{ layer: LayerT }> = ({ layer }) => {
  const sceneId = (layer as any).scene_id ?? (layer as any).id;
  const Comp = getCustomScene(sceneId);
  if (!Comp) {
    return null;
  }
  return React.createElement(Comp, { layer });
};
