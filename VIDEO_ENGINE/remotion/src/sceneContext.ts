import { createContext, useContext } from "react";
import { useCurrentFrame } from "remotion";

/** hasImage: the scene shows a photo or video, so text on it needs a dark scrim. */
export const SceneCtx = createContext({ startFrame: 0, durFrames: 1, hasImage: false });

/** Frame on the global (audio) timeline, even inside a <Sequence>. */
export const useAbsFrame = () => useCurrentFrame() + useContext(SceneCtx).startFrame;
export const useScene = () => useContext(SceneCtx);
