import { createContext, useContext } from "react";
import { useVideoConfig } from "remotion";
import theme from "./theme.json";

// One theme per video. The values live in theme.json so the Python checks (tests/test_m9.py, backend/palette.py) read the same numbers.
export const SAFE: number = theme.safeMargin;                  // share of width/height kept clear of text
export const TYPE = theme.type;                                // the type scale: every font size comes from here
export const SCRIM: number = theme.scrim;                      // dark overlay under text that sits on images
export const DEFAULT_PALETTE: string[] = theme.palette;
/** A dark panel behind an icon or a number that sits on a photo (layer field `backing`), so an accent colour never disappears into the picture. */
export const BACKING = theme.backing;
export const backingColor = (): string => {
  const h = BACKING.color.replace("#", "");
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
  return `rgba(${r},${g},${b},${BACKING.opacity})`;
};
/** Named image boxes as [x, y, width, height] fractions of the frame; backend/focus.py reads the same table. */
export const BOXES = theme.boxes as unknown as Record<string, [number, number, number, number]>;
export const GRADES = theme.grades as unknown as Record<string, [string, string]>;   // [top, bottom] overlay colors

const P = theme.portrait;
const TYPE_PORTRAIT = Object.fromEntries(Object.entries(TYPE).map(([k, v]) => [k, Math.round(v * P.typeScale)])) as typeof TYPE;

/**
 * Frame-dependent values. 16:9 (1920x1080) returns exactly the constants above; a taller frame (9:16, 1080x1920) gets
 * its own box table and a smaller type scale, because the frame is 44% narrower. Components call this instead of
 * importing TYPE / BOXES directly.
 */
export function layoutFor(width: number, height: number) {
  const portrait = height > width;
  return {
    w: width, h: height, portrait,
    type: portrait ? TYPE_PORTRAIT : TYPE,
    boxes: (portrait ? P.boxes : theme.boxes) as unknown as Record<string, [number, number, number, number]>,
    captionBottom: portrait ? P.captionBottom : "8%", lowerThirdBottom: portrait ? P.lowerThirdBottom : "12%", labelTop: portrait ? P.labelTop : "8%",
  };
}
export const useLayout = () => { const { width, height } = useVideoConfig(); return layoutFor(width, height); };

/** WCAG relative luminance of a hex color (0 = black, 1 = white). */
export function luminance(hex: string): number {
  const lin = (v: number) => ((v /= 255) <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
  const [r, g, b] = rgb(hex).map(lin);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/**
 * Palette roles, derived from the colors and NOT from their order (plans list them as [dark, teal, amber]
 * while docs show [dark, amber, teal]): base = the darkest color (backgrounds), accent = the brightest of the
 * rest (highlights, icons, lines), secondary = the remaining one (gradient end, 2nd chart series).
 */
export function roles(p: string[]) {
  const [base, ...rest] = [...p].sort((a, b) => luminance(a) - luminance(b));
  const [secondary, accent] = rest.length ? [rest[0], rest[rest.length - 1]] : [base, base];
  return { base, accent, secondary: rest.length > 1 ? secondary : accent };
}
export type Palette = ReturnType<typeof roles>;

export const PaletteCtx = createContext<Palette>(roles(DEFAULT_PALETTE));
export const usePalette = () => useContext(PaletteCtx);

// a function declaration, not a const: it is hoisted, and PaletteCtx below calls roles() while this module is still loading
function rgb(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  const f = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
  return [0, 2, 4].map((i) => parseInt(f.slice(i, i + 2), 16)) as [number, number, number];
}

/** Linear mix of two hex colors (t = 0 gives a, t = 1 gives b). */
export function mix(a: string, b: string, t: number): string {
  const [x, y] = [rgb(a), rgb(b)];
  return "#" + x.map((v, i) => Math.round(v + (y[i] - v) * t).toString(16).padStart(2, "0")).join("");
}
