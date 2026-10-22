---
skill_id: motion.math_code_visuals
name: Math Formulas & Code Visuals
domain: motion
version: 1.0.0
summary: KaTeX formulas and prism-react-renderer code blocks with typewriter reveals.
status: approved
source: local
license: Apache-2.0
license_evidence: Authored internally for Dark World Video Generation Agent. Libraries named here are installed from npm under their own licenses (MIT (katex, prism-react-renderer)).
risk_level: low
capabilities:
  - math
  - code-visualization
  - terminal
dependencies:
  - remotion
  - katex
  - prism-react-renderer
compatible_agents:
  - motion_planning
  - motion_animation
compatible_project_modes:
  - motion_only
---

# Math Formulas & Code Visuals

## Formulas (KaTeX)
`import katex from "katex"; const html = katex.renderToString("E = mc^2", { displayMode: true, throwOnError: false });` then `<div dangerouslySetInnerHTML={{ __html: html }} style={{ fontSize: 84, color: "#fff" }} />`. The KaTeX stylesheet and fonts are loaded globally by fonts.ts; do not import CSS in a scene.
Colour parts with the KaTeX `color` command (backslash + `color{#22d3ee}{x}`); reveal a derivation line by line (opacity + translateY, stagger 12 frames) by rendering one expression per line.

## Code (prism-react-renderer)
```
import { Highlight, themes } from "prism-react-renderer";
<Highlight theme={themes.vsDark} code={visibleCode} language="tsx">
  {({ tokens, getLineProps, getTokenProps }) => (<pre style={{ fontFamily: fontStack("mono"), fontSize: 30, margin: 0 }}>
    {tokens.map((line, i) => (<div key={i} {...getLineProps({ line })}>{line.map((token, k) => (<span key={k} {...getTokenProps({ token })} />))}</div>))}</pre>)}
</Highlight>
```
Typewriter: `visibleCode = code.slice(0, Math.floor(frame * 1.5))`. Put it in a glass "terminal" card with three coloured dots; max ~12 lines, 28 to 34px.
