// npx tsx scripts/style_gallery.ts <outDir>
// The gallery of the style kit and the phrase composer: six scenes (every look of the kit, every phrase recipe) built through the SAME code the pipeline uses
// (patterns -> richenScene with a kit look), written as composition_gallery.json (1920x1080) and composition_gallery_9x16.json (1080x1920) in <outDir>.
// It renders nothing and touches no project: render the stills from these files (see reports/STYLE_KIT/README.md). The text is sample text, not a project's script.
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { richenScene } from "../src/motion/integrate";
import { makeRuns, type Recipe } from "../src/motion/phrase";
import { buildScene } from "../src/patterns";
import { DEFAULT_PALETTE } from "../src/theme";
import { KITS, kitLook } from "../src/styleKit";

const out = process.argv[2];
if (!out) throw new Error("usage: style_gallery.ts <outDir>");
mkdirSync(out, { recursive: true });
const kit = KITS.editorial;
const SECONDS = 4;
// [look, recipe wanted, text, keyword]
const PLAN: [string, Recipe, string, string | undefined][] = [
  ["cobalt", "lead-hero", "so you can see how capable", "capable"],
  ["ink", "sans-serif", "You create the future", undefined],
  ["paper", "marker", "Match the model to the task", "task"],
  ["sun", "lead-hero", "Smarter than us", "Smarter"],
  ["graphite", "sans-serif", "Every system reacts in moments", undefined],
  ["cobalt", "marker", "The danger of unchecked machines", "danger"],
];

for (const [aspect, W, H] of [["16:9", 1920, 1080], ["9:16", 1080, 1920]] as const) {
  const scenes = PLAN.map(([lookId, recipe, text, mark], i) => {
    const look = kitLook({ ...kit, looks: kit.looks.filter((l) => l.id === lookId) }, i, "gallery");
    // the recipe is a seeded pick: find the seed that gives the wanted one (richenScene builds the phrase from `${seed}:${scene id}`)
    let seed = "g0";
    for (let s = 0; s < 400; s++) if (makeRuns(text, { mark, seed: `g${s}:${i + 1}`, colors: { fg: look.fg, accent: look.accent, dim: look.dim, bg: look.bg[0] } })?.recipe === recipe) { seed = `g${s}`; break; }
    const built = buildScene(i + 1, "hero_text", { start: i * SECONDS, end: (i + 1) * SECONDS, files: [], palette: DEFAULT_PALETTE, colors: [look.bg[0], look.bg[1]], text, mark, ...(aspect === "9:16" ? { width: W, height: H } : {}) });
    return richenScene(built, { tall: aspect === "9:16", importance: 0.8, seed, kit: look, speed: 1.4, mood: "calm", motionOnly: true }).scene;
  });
  const meta = { fps: 30, width: W, height: H, audio: "audio.mp3", duration: SECONDS * PLAN.length, subtitles: false, palette: DEFAULT_PALETTE, motion: "rich", motionOnly: true, motionSpeed: 1.4, kit: kit.id };
  writeFileSync(join(out, aspect === "9:16" ? "composition_gallery_9x16.json" : "composition_gallery.json"), JSON.stringify({ meta, scenes }, null, 1));
  console.log(`${aspect}: ${scenes.length} scenes -> ${aspect === "9:16" ? "composition_gallery_9x16.json" : "composition_gallery.json"}`);
}
