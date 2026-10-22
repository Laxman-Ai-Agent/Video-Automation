import type { ReactNode } from "react";
import { useCurrentFrame } from "remotion";
import { cameraAt } from "../camera";
import { useScene } from "../sceneContext";
import type { SceneT } from "../schema";

export const Camera: React.FC<{ cam: SceneT["camera"]; children: ReactNode }> = ({ cam, children }) => {
  const frame = useCurrentFrame();
  const { durFrames, startFrame } = useScene();
  const s = cameraAt(cam, frame, durFrames, `cam${startFrame}`);   // the seed (scene start) makes the optional drift repeatable
  return (
    <div style={{
      position: "absolute", inset: 0,
      transformOrigin: `${s.originX}% ${s.originY}%`,
      // rotate only when the optional drift is on: a steady camera keeps exactly the transform it always had
      transform: `translate(${s.tx}%, ${s.ty}%)${s.rot ? ` rotate(${s.rot}deg)` : ""} scale(${s.scale})`,
    }}>
      {children}
    </div>
  );
};
