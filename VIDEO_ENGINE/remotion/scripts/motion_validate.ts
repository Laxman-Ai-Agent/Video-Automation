// npx tsx scripts/motion_validate.ts <composition.json>
// Motion Generation, stage "Code Validation": does the composition satisfy the renderer's own contract? (the zod schema of src/schema.ts, and a registered component for every layer type)
// Prints one JSON line: { zod: true | [issues], layer_types: { type: count }, unknown: [types the renderer would skip], wallclock: [files with a clock or Math.random in the animation code] }.
import { readFileSync, readdirSync } from "node:fs";
import { icons } from "lucide-react";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { registry, resolve } from "../src/registry";
import { CompositionSchema } from "../src/schema";

const file = process.argv[2];
if (!file) throw new Error("usage: motion_validate.ts <composition.json>");
const comp = JSON.parse(readFileSync(file, "utf-8"));
const r = CompositionSchema.safeParse(comp);
const types: Record<string, number> = {};
for (const s of comp.scenes ?? []) for (const l of s.layers ?? []) types[String(l.type)] = (types[String(l.type)] ?? 0) + 1;
const unknown = Object.keys(types).filter((t) => !resolve(t));
// an icon layer whose lucide name does not exist draws nothing (IconPop returns null): name it
const pascal = (s: string) => s.replace(/(^|-)([a-z0-9])/g, (_, __, c: string) => c.toUpperCase());
const badIcons = [...new Set((comp.scenes ?? []).flatMap((s: any) => (s.layers ?? []).filter((l: any) => l.type === "icon" && !l.resource_id && !(icons as Record<string, unknown>)[pascal(String(l.lucide))]).map((l: any) => String(l.lucide))))];

// the frame-driven rule: nothing that is drawn may depend on the wall clock or on an unseeded random number
const root = join(dirname(fileURLToPath(import.meta.url)), "..", "src");
const files: string[] = [];
const walk = (d: string) => { for (const e of readdirSync(d, { withFileTypes: true })) { const p = join(d, e.name); if (e.isDirectory()) walk(p); else if (/\.(ts|tsx)$/.test(e.name)) files.push(p); } };
walk(root);
const clock = /\b(Date\.now|performance\.now|Math\.random|setTimeout|setInterval|requestAnimationFrame)\s*\(/;
const wallclock = files.filter((f) => !/index\.ts$|Root\.tsx$|Main\.tsx$/.test(f) && clock.test(readFileSync(f, "utf-8").replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, ""))).map((f) => f.slice(root.length + 1));

console.log(JSON.stringify({ zod: r.success ? true : r.error.issues.slice(0, 5).map((i) => `${i.path.join(".")}: ${i.message}`), layer_types: types, unknown, bad_icons: badIcons, registered: Object.keys(registry).length, wallclock }));
