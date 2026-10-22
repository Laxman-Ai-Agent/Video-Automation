// Fonts are SELF-HOSTED (@fontsource, OFL-1.1): the files come from node_modules, never from the internet at render time. The google-fonts loader used before fetched them from
// fonts.gstatic.com for every render page, and a single failed fetch ("Failed to fetch") failed the whole render or preview still.
//
// The CSS is imported DYNAMICALLY and only in a browser: Node scripts (tsx: composition schema validation, build_composition) import this module through the component tree, and Node
// cannot load .css files (ERR_UNKNOWN_FILE_EXTENSION). Without `document` nothing is imported.
const inBrowser = typeof document !== "undefined";
const cssLoaded: Promise<unknown> = inBrowser
  ? Promise.all([
      import("@fontsource/poppins/latin-600.css"),
      import("@fontsource/poppins/latin-800.css"),
      import("@fontsource/noto-sans-telugu/telugu-600.css"),
      import("@fontsource/noto-sans-telugu/telugu-800.css"),
      import("@fontsource/noto-sans-telugu/latin-600.css"),
      import("@fontsource/noto-sans-telugu/latin-800.css"),
      import("@fontsource/jetbrains-mono/latin-500.css"),
      import("@fontsource/jetbrains-mono/latin-700.css"),
      import("@fontsource/instrument-serif/latin-400.css"),
      import("@fontsource/instrument-serif/latin-400-italic.css"),
      import("katex/dist/katex.min.css"),                       // formula styling + its own math fonts (katex.renderToString in a generated scene)
    ])
  : Promise.resolve();

export const FONT = `"Poppins", "Noto Sans Telugu", sans-serif`;

const TELUGU_SAMPLE = "అఆఇ";
/** Resolves when the default stack (Poppins 600/800 + Noto Sans Telugu 600/800, Telugu glyphs included) is decoded: Root.tsx waits for it inside delayRender. */
export const fontsReady: Promise<unknown> = inBrowser
  ? cssLoaded.then(() =>
      Promise.all([
        document.fonts.load('600 40px "Poppins"'),
        document.fonts.load('800 40px "Poppins"'),
        document.fonts.load('600 40px "Noto Sans Telugu"', TELUGU_SAMPLE),
        document.fonts.load('800 40px "Noto Sans Telugu"', TELUGU_SAMPLE),
      ]),
    )
  : Promise.resolve();

/** The style kit's font families (src/styleKit.ts): `sans` is the project's default stack, `serif` an italic-capable display serif and `mono` a technical mono for labels.
 *  Used for ENGLISH on-screen text only (the display fonts have no Telugu glyphs; the stack ends with the default one, so a missing glyph falls through to Noto Sans Telugu).
 *  The @font-face rules above are static, but the browser reads a font file only when a layer actually uses its family. */
export type FontKind = "sans" | "serif" | "mono";
export function fontStack(kind: FontKind | undefined): string {
  if (!kind || kind === "sans") return FONT;
  if (kind === "serif") return `"Instrument Serif", Georgia, ${FONT}`;
  return `"JetBrains Mono", ui-monospace, ${FONT}`;
}
