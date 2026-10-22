import { hash } from "./motion/core";
import { luminance, mix } from "./theme";

/**
 * A style kit: a few background looks of ONE visual family, so a video changes colour from scene to scene (as the editorial motion reels do) and still looks like one piece.
 * It is chosen per project (A2V_STYLE_KIT=<id>, `1` = editorial); without it nothing changes. Everything here is data plus pure functions of (kit, scene index, seed):
 * the same plan always gives the same looks, and a scene never gets the look of the scene before it.
 * The fonts of a kit (serif italic for emphasis, mono for labels) are for ENGLISH on-screen text only; see fonts.ts.
 */
export interface KitLook {
  id: string;
  bg: [string, string];      // background gradient, start and end
  fg: string;                // text and lines
  accent: string;            // highlights: the hero word, a marker, an icon
  dim: string;               // fg faded toward the background: small lead-in words, secondary lines
  dark: boolean;             // a dark background (the soft text shadow stays; on a light one it is removed)
}
export interface StyleKit { id: string; label: string; looks: Omit<KitLook, "dim" | "dark">[] }

export const KITS: Record<string, StyleKit> = {
  editorial: {
    id: "editorial", label: "Editorial: ink, cobalt, sun, paper, graphite",
    looks: [
      { id: "ink", bg: ["#0B0B10", "#16161F"], fg: "#F4F1EA", accent: "#FF5A36" },
      { id: "cobalt", bg: ["#2B44FF", "#1E32D8"], fg: "#FFFFFF", accent: "#FFD23F" },
      { id: "sun", bg: ["#F8C630", "#F1B814"], fg: "#15110A", accent: "#D93A24" },
      { id: "paper", bg: ["#EFEBE3", "#E4DED1"], fg: "#15110A", accent: "#2B44FF" },
      { id: "graphite", bg: ["#1B1E27", "#262B38"], fg: "#ECE9E1", accent: "#3DDBB3" },
    ],
  },
};

/** The kit named by A2V_STYLE_KIT ("" or "0" = none, "1" = editorial); an unknown name is an error, never a silent fallback. */
export function kitByName(name: string | undefined): StyleKit | undefined {
  const n = (name ?? "").trim();
  if (!n || n === "0") return undefined;
  const k = KITS[n === "1" ? "editorial" : n];
  if (!k) throw new Error(`unknown style kit "${n}" (known: ${Object.keys(KITS).join(", ")})`);
  return k;
}

const complete = (l: StyleKit["looks"][number]): KitLook => ({ ...l, bg: [l.bg[0], l.bg[1]], dim: mix(l.fg, l.bg[0], 0.5), dark: luminance(l.bg[0]) < 0.3 });

/** WCAG contrast ratio of two hex colours (1..21). */
export const contrast = (a: string, b: string): number => { const [x, y] = [luminance(a), luminance(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };

/** The look of scene `index`: a seeded pick that is never the look of the previous scene (`prevId`). */
export function kitLook(kit: StyleKit, index: number, seed: string | number, prevId?: string): KitLook {
  const pool = kit.looks.filter((l) => l.id !== prevId);
  return complete(pool[hash(`${seed}:${kit.id}:${index}`) % pool.length]);
}
