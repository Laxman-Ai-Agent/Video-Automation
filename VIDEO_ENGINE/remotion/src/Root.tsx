import { Composition } from "remotion";
import { fontsReady } from "./fonts";
import { Main } from "./Main";
import { CompositionSchema, type Comp } from "./schema";
import sample from "../public/composition.json";

export const Root: React.FC = () => (
  <Composition
    id="Main"
    component={Main}
    width={1920}
    height={1080}
    fps={30}
    durationInFrames={900}
    defaultProps={CompositionSchema.parse(sample)}
    calculateMetadata={async ({ props }) => {
      const r = CompositionSchema.safeParse(props);
      if (!r.success) {
        const msg = r.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`).join("\n");
        throw new Error(`Invalid composition.json:\n${msg}`);
      }
      await fontsReady;
      const c: Comp = r.data;
      return {
        props: c,
        fps: c.meta.fps,
        width: c.meta.width,
        height: c.meta.height,
        durationInFrames: Math.round(c.meta.duration * c.meta.fps),
      };
    }}
  />
);
