import { createContext, useContext } from "react";

/** The composition's audio file name (in public/) and the spoken words with their times in seconds (same shape as schema.ts `words`). Provided by Main so a generated scene can drive
 *  an audio visualizer (@remotion/media-utils `useAudioData(staticFile(audio))`) or sync an emphasis to the moment a word is spoken. Empty when the project has no transcript. */
export type SpokenWord = { w: string; start: number; end: number };
export type SceneDataValue = { audio: string | null; words: SpokenWord[] };

export const SceneData = createContext<SceneDataValue>({ audio: null, words: [] });
export const useSceneData = () => useContext(SceneData);
