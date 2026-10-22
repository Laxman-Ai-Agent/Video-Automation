import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve("../reports/STYLE_KIT/gallery");
const comp16_9 = JSON.parse(readFileSync(`${root}/composition_gallery.json`, "utf-8"));
const comp9_16 = JSON.parse(readFileSync(`${root}/composition_gallery_9x16.json`, "utf-8"));

const cases = [
  { name: "16x9_s1", frame: 60, props: comp16_9 },
  { name: "16x9_s1_reveal", frame: 45, props: comp16_9 },
  { name: "16x9_s2", frame: 180, props: comp16_9 },
  { name: "16x9_s3", frame: 300, props: comp16_9 },
  { name: "16x9_s3_reveal", frame: 285, props: comp16_9 },
  { name: "16x9_s4", frame: 420, props: comp16_9 },
  { name: "16x9_s5", frame: 540, props: comp16_9 },
  { name: "16x9_s6", frame: 660, props: comp16_9 },

  { name: "9x16_s1", frame: 60, props: comp9_16 },
  { name: "9x16_s2", frame: 180, props: comp9_16 },
  { name: "9x16_s3", frame: 300, props: comp9_16 },
  { name: "9x16_s4", frame: 420, props: comp9_16 },
  { name: "9x16_s5", frame: 540, props: comp9_16 },
  { name: "9x16_s6", frame: 660, props: comp9_16 },
];

writeFileSync(`${root}/cases_gallery.json`, JSON.stringify({ scale: 0.5, cases }, null, 2));
console.log("Wrote cases_gallery.json with", cases.length, "cases");
