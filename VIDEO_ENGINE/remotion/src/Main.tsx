import { AbsoluteFill, Audio, staticFile } from "remotion";
import { FilmLook } from "./components/FilmLook";
import { Grade } from "./components/Grade";
import { Subtitles } from "./components/Subtitles";
import { SceneData } from "./sceneData";
import { SceneRoot } from "./SceneRoot";
import type { Comp } from "./schema";
import { DEFAULT_PALETTE, PaletteCtx, mix, roles } from "./theme";
import "./fonts";

export const Main: React.FC<Comp> = ({ meta, scenes, words }) => {
  const palette = roles(meta.palette ?? DEFAULT_PALETTE);
  return (
    <PaletteCtx.Provider value={palette}>
      <SceneData.Provider value={{ audio: meta.audio ?? null, words: words ?? [] }}>
        <AbsoluteFill style={{ background: `linear-gradient(135deg,${palette.base},${mix(palette.base, "#ffffff", 0.12)})` }}>
          <Audio src={staticFile(meta.audio)} />
          <SceneRoot scenes={scenes} fps={meta.fps} />
          <Grade grade={meta.grade} />
          <FilmLook />
          {meta.subtitles && words && <Subtitles words={words} />}
        </AbsoluteFill>
      </SceneData.Provider>
    </PaletteCtx.Provider>
  );
};
