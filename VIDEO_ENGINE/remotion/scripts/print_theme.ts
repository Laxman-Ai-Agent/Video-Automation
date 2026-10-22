// npx tsx scripts/print_theme.ts '{"palettes": [["#0B1D26","#2A9D8F","#F2A541"]], "fits": [["text", 144, 800, 1728]]}'
// Prints what the renderer's theme functions return, so tests/test_m9.py can compare them with the Python side.
// Importing theme.ts also proves the module loads (it builds a context from roles() at load time).
import { fitFontSize } from "../src/textfit";
import { SAFE, SCRIM, TYPE, roles } from "../src/theme";

const input = JSON.parse(process.env.THEME_INPUT ?? process.argv[2] ?? "{}") as { palettes?: string[][]; fits?: [string, number, number, number][] };
console.log(JSON.stringify({
  safe: SAFE, scrim: SCRIM, type: TYPE,
  roles: (input.palettes ?? []).map((p) => roles(p)),
  fits: (input.fits ?? []).map(([text, size, weight, maxWidth]) => fitFontSize(text, size, weight, maxWidth)),
}));
