import { icons } from "lucide-react";
import { useVideoConfig } from "remotion";
import { useEnterStyle } from "../anim";
import { SvgIcon, resourceIcon } from "../library/resources";
import type { LayerT } from "../schema";
import { BACKING, backingColor, usePalette } from "../theme";

const pascal = (s: string) => s.replace(/(^|-)(\w)/g, (_, __, c: string) => c.toUpperCase());

export const IconPop: React.FC<{ layer: LayerT }> = ({ layer }) => {
  // resource_id: a registered icon of the Resource Library (a local SVG, pinned by hash) instead of a lucide name; without it the layer is drawn exactly as before
  const l = layer as LayerT & { lucide?: string; resource_id?: string; resource_sha256?: string; pos?: [number, number]; size?: number; color?: string; draw?: boolean; backing?: boolean };
  const res = l.resource_id ? resourceIcon(l.resource_id, l.resource_sha256) : null;
  const Icon = l.lucide ? icons[pascal(l.lucide) as keyof typeof icons] : undefined;
  const st = useEnterStyle(l.enter ?? { at: 0, anim: "pop", dur: 0.5 }, l.exit);
  const { accent } = usePalette();
  const { width, height } = useVideoConfig();
  if (!res && !Icon) { console.warn(`[icon] unknown icon "${l.resource_id ?? l.lucide}"`); return null; }
  const [x, y] = l.pos ?? [width / 2, height / 2];
  const size = l.size ?? 160;
  // backing: a dark round panel behind the icon (theme.json "backing"), for an icon that sits on a photo; without it the layer is drawn exactly as before
  const pad = l.backing ? size * BACKING.pad : 0;
  const panel = l.backing ? { width: size + 2 * pad, height: size + 2 * pad, display: "flex", alignItems: "center", justifyContent: "center", borderRadius: "50%", background: backingColor() } as const : {};
  return (
    <div style={{ position: "absolute", left: x - size / 2 - pad, top: y - size / 2 - pad, ...panel, ...st,
      filter: "drop-shadow(0 8px 24px rgba(0,0,0,0.5))" }}>
      {res ? <SvgIcon res={res} size={size} color={l.color ?? accent} /> : Icon ? <Icon size={size} color={l.color ?? accent} strokeWidth={1.75} /> : null}
    </div>
  );
};
