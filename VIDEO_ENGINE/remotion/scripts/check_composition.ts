import { readFileSync } from "node:fs";
import { CompositionSchema } from "../src/schema";
const r = CompositionSchema.safeParse(JSON.parse(readFileSync("../projects/demo/composition.json", "utf-8")));
console.log(r.success ? "zod OK" : r.error.issues.slice(0, 3));
