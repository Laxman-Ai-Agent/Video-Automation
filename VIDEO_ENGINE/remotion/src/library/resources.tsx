// The renderer's side of the Resource Library (docs/resources.md): resolves a registry id to LOCAL data only, never the network.
// `render_bundle.json` is derived from resource-library/catalog/registry.json by backend/resource_library.py (outside src/, so a registry change does not change the renderer's own digest);
// a layer names a resource by id (`resource_id` on icon / background / chart / gfx layers, `fontId` on text) and records the pinned hash it was built with.
// Data, not code: an icon is a list of allow-listed SVG nodes, a font is a list of files under public/resource-fonts. Frame-driven and deterministic: no clock, no randomness.
import { createElement, type ReactNode } from "react";
import { cancelRender, continueRender, delayRender, staticFile } from "remotion";
import bundleJson from "../../../../resource-library/bundle/render_bundle.json";

export interface SvgNode { tag: string; attrs: Record<string, string>; children: SvgNode[] }
interface IconRes { kind: "icon"; sha256: string; viewBox: string; children: SvgNode[] }
interface FontRes { kind: "font"; sha256: string; family: string; files: { weight: number; style: string; url: string; sha256: string }[] }
type Res = IconRes | FontRes | { kind: "local"; sha256: string };
const RES = (bundleJson as { resources: Record<string, Res> }).resources;

// the same allow-lists as backend/resource_library.parse_svg (defence in depth: the bundle is already sanitised)
const TAGS = new Set(["g", "path", "circle", "ellipse", "rect", "line", "polyline", "polygon"]);
const ATTRS = new Set(["d", "cx", "cy", "r", "rx", "ry", "x", "y", "x1", "y1", "x2", "y2", "points", "transform", "fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin",
  "stroke-opacity", "fill-opacity", "opacity", "fill-rule", "clip-rule", "stroke-miterlimit", "width", "height"]);
const camel = (k: string) => k.replace(/-([a-z])/g, (_, c: string) => c.toUpperCase());

export function resourceSha(id: string): string | null { return RES[id]?.sha256 ?? null; }

/** The drawing of a registered icon, or null when the id is unknown. A layer built with another version of the files (its recorded hash differs) is an error, not a silent redraw. */
export function resourceIcon(id: string, builtWith?: string): IconRes | null {
  const r = RES[id];
  if (!r || r.kind !== "icon") return null;
  if (builtWith && builtWith !== r.sha256) throw new Error(`resource ${id}: the layer was built with another version of the icon (hash differs); rebuild the composition`);
  return r;
}

function drawNode(n: SvgNode, key: number): ReactNode {
  if (!TAGS.has(n.tag)) return null;
  const props: Record<string, string | number> = { key };
  for (const [k, v] of Object.entries(n.attrs)) if (ATTRS.has(k)) props[camel(k)] = v;
  return createElement(n.tag, props, ...n.children.map(drawNode));
}

/** An outline icon (24-unit viewBox, stroke only), drawn the way the lucide icons of IconPop are: `size` px, the layer's colour, a 1.75 stroke. */
export function SvgIcon({ res, size, color }: { res: IconRes; size: number; color: string }) {
  return <svg width={size} height={size} viewBox={res.viewBox} fill="none" stroke={color} strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">{res.children.map(drawNode)}</svg>;
}

const loaded = new Set<string>();
/** The CSS font stack of a registered font: its own family first, the project's default stack after it (a glyph the font lacks, e.g. native Telugu digits, falls through).
 *  The files are loaded from public/resource-fonts (staged copies, hash-checked by Stage 10) and the frame waits for them; a missing file fails the render. */
export function resourceFontStack(id: string, fallback: string, builtWith?: string): string {
  const r = RES[id];
  if (!r || r.kind !== "font") return fallback;
  if (builtWith && builtWith !== r.sha256) throw new Error(`resource ${id}: the layer was built with another version of the font (hash differs); rebuild the composition`);
  const family = `res-${id.replace(/[^a-z0-9]+/g, "-")}`;
  if (!loaded.has(id)) {
    loaded.add(id);
    const handle = delayRender(`resource font ${id}`, { timeoutInMilliseconds: 60000 });
    Promise.all(r.files.map((f) => new FontFace(family, `url(${staticFile(f.url)})`, { weight: String(f.weight), style: f.style }).load().then((ff) => { document.fonts.add(ff); })))
      .then(() => continueRender(handle)).catch((e) => cancelRender(e));
  }
  return `"${family}", ${fallback}`;
}
