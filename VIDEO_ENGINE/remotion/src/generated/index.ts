// The base registry of generated scenes: empty. Motion Animation (VIDEO_ENGINE/stages/motion_animation.py) and render staging (stages/render.py stage_motion)
// overwrite this file with the project's own registry and write scene_*.tsx next to it (those are stage outputs, not tracked: .gitignore).
import React from "react";
import type { ComponentType } from "react";
import type { LayerT } from "../schema";

export const customSceneRegistry: Record<string, ComponentType<any>> = {};

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
