import { Loop, OffthreadVideo, staticFile, useVideoConfig } from "remotion";
import { useEnterStyle } from "../anim";
import type { LayerT } from "../schema";

export const StockVideo: React.FC<{ layer: LayerT }> = ({ layer }) => {
  const l = layer as LayerT & { file?: string; opacity?: number; clipDur?: number; clipStart?: number };
  const { fps } = useVideoConfig();
  const st = useEnterStyle(l.enter, l.exit);
  if (!l.file) return null;
  const startFrame = Math.round((l.clipStart ?? 0) * fps);
  return (
    <div style={{ position: "absolute", inset: 0, ...st, opacity: (st.opacity as number) * (l.opacity ?? 1) }}>
      <Loop durationInFrames={Math.round((l.clipDur ?? 10) * fps)}>
        <OffthreadVideo src={staticFile(l.file)} startFrom={startFrame} muted style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      </Loop>
    </div>
  );
};
