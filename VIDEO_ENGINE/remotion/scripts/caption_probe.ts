// npx tsx scripts/caption_probe.ts <cases.json> <outDir>
// Renders small stills with the REAL renderer (Chrome, real fonts) so tests can measure where captions land.
// cases.json: {"scale": 0.3333, "cases": [{"name": "portrait_7_words", "frame": 30, "props": <composition>}]}  ->  <outDir>/<name>.png
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import { createServer } from "node:net";
import { join, resolve } from "node:path";
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";

const [casesFile, outDir] = process.argv.slice(2);
if (!casesFile || !outDir) throw new Error("usage: caption_probe.ts <cases.json> <outDir>");
const { scale = 0.3333, cases, publicDir } = JSON.parse(readFileSync(casesFile, "utf-8"));   // publicDir (optional): a folder with the files the cases use
mkdirSync(outDir, { recursive: true });

// the renderer's own bundle server must not land on a port another application already answers on (it then refuses it as "a foreign page")
const freePort = () => new Promise<number>((res) => { const s = createServer(); s.listen(0, "127.0.0.1", () => { const p = (s.address() as { port: number }).port; s.close(() => res(p)); }); });
const serveUrl = await bundle({ entryPoint: resolve("src/index.ts"), ...(publicDir ? { publicDir } : {}) });   // bundled once for all cases
for (const c of cases) {
  if (existsSync(join(outDir, `${c.name}.png`))) continue;       // a rerun into the same folder continues where the last run stopped
  // every render loads the web fonts again: one failed download (Google Fonts) is retried, so a long run is not lost to a single hiccup
  for (let attempt = 1; ; attempt++) {
    try {
      const port = await freePort();
      const composition = await selectComposition({ serveUrl, id: "Main", inputProps: c.props, port });
      await renderStill({ composition, serveUrl, inputProps: c.props, frame: c.frame, scale, port, output: join(outDir, `${c.name}.png`) });
      break;
    } catch (e) {
      if (attempt >= 5) throw e;
      await new Promise((r) => setTimeout(r, 3000 * attempt));
    }
  }
  console.log(`rendered ${c.name}`);
}
