import { writeFileSync } from "node:fs";
import { PATTERN_NAMES, buildScene, type PP } from "../src/patterns";
import { TRANSITIONS } from "../src/transitions";

const D = 4;
const files = (n: number) => Array.from({ length: n }, (_, i) => `img_0${(i % 3) + 1}.png`);
const data = [{ label: "A", value: 12 }, { label: "B", value: 30 }, { label: "C", value: 21 }];
const cols: [string, string][] = [["#0B1D26", "#2A9D8F"], ["#14285A", "#E76F51"], ["#3C1432", "#F2A541"]];

const scenes = PATTERN_NAMES.map((name, i) => {
  const p: PP = {
    start: i * D, end: (i + 1) * D, files: files(5), text: name.replace("_", " "), mark: "text",
    icon: "droplet", number: 1400, unit: "km", data, region: "india", highlight: ["India"],
    route: [[77.2, 28.6], [72.8, 19.0], [80.2, 13.0]], labels: ["Delhi", "Mumbai", "Chennai"],
    colors: cols[i % 3], text2: "Gallery sample",
  };
  const last = i === PATTERN_NAMES.length - 1;
  return buildScene(i + 1, name, p, last ? undefined : { type: TRANSITIONS[i % TRANSITIONS.length], dur: 0.7 });
});

const used = new Set(scenes.map((s) => s.transition_out?.type).filter(Boolean));
scenes.forEach((s, i) => { if (i && s.transition_out?.type === scenes[i - 1].transition_out?.type) throw new Error("adjacent transitions equal"); });
if (used.size < TRANSITIONS.length) throw new Error("not every transition used");

const comp = { meta: { fps: 30, width: 1920, height: 1080, audio: "audio_test.wav", duration: scenes.length * D, subtitles: false }, scenes };
const json = JSON.stringify(comp);
writeFileSync("public/gallery.json", json);
writeFileSync("../tests/fixtures/gallery.json", json);
console.log(`gallery: ${scenes.length} scenes, ${used.size} transitions`);
