/** Lists the presets of the motion library as JSON (run: npx tsx scripts/motion_list.ts). Used by tests/test_motion_library.py and by people who want to search the presets. */
import { existsSync, readFileSync } from "node:fs";
import { icons } from "lucide-react";
import { iconsOf } from "../src/library/registry";
import { PRIMITIVES, REGION_BOX } from "../src/motion/diagram";
import { GFX_PRESETS } from "../src/motion/graphics";
import { MASKS } from "../src/motion/masks";
import { EMPHASIS_PRESETS, EXIT_PRESETS, TEXT_PRESETS } from "../src/motion/textPresets";

// the same registry backend/resource_library.py reads: resource-library at the repo root
const regUrl = [new URL("../../../resource-library/catalog/registry.json", import.meta.url)].find((u) => existsSync(u));
const registry = regUrl ? JSON.parse(readFileSync(regUrl, "utf-8")).resources ?? [] : [];

console.log(JSON.stringify({
  text: Object.values(TEXT_PRESETS).map((p) => ({ id: p.id, label: p.label, category: p.category, unit: p.unit, indic: p.indic, desc: p.desc })),
  graphics: Object.values(GFX_PRESETS).map((p) => ({ id: p.id, label: p.label, category: p.category, loop: p.loop, desc: p.desc })),
  masks: MASKS,
  exits: Object.values(EXIT_PRESETS).map((e) => ({ id: e.id, label: e.label })),
  emphasis: Object.values(EMPHASIS_PRESETS).map((e) => ({ id: e.id, label: e.label })),
  // the other drawing primitives of the renderer that the diagram builder uses: a disc of the `shape` layer and lucide icons of the `icon` layer (only icons lucide really has)
  region_boxes: REGION_BOX,
  // + the VERIFIED icons of the Resource Library (docs/resources.md): `resource:<resource_id>`; a resource that is not verified is not listed, so the planner cannot choose it
  primitives: [...iconsOf(registry).map((i) => ({ id: `resource:${i.id}`, label: `Resource icon ${i.id}`, layer: "icon" })), ...PRIMITIVES.shape.map((k) => ({ id: `shape:${k}`, label: `Shape ${k}`, layer: "shape" })), ...PRIMITIVES.icon.filter((n) => (icons as Record<string, unknown>)[n.replace(/(^|-)(\w)/g, (_, __, c: string) => c.toUpperCase())]).map((n) => ({ id: `icon:${n}`, label: `Icon ${n}`, layer: "icon" }))],
}));
