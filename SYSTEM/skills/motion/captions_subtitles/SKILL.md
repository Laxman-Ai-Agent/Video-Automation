---
skill_id: motion.captions_subtitles
name: Captions & Word-Synced Emphasis
domain: motion
version: 1.0.0
summary: Word-by-word English captions with @remotion/captions and emphasis synced to the spoken words.
status: approved
source: local
license: Apache-2.0
license_evidence: Authored internally for Dark World Video Generation Agent. Libraries named here are installed from npm under their own licenses (MIT (@remotion/captions)).
risk_level: low
capabilities:
  - captions
  - word-sync
dependencies:
  - remotion
  - @remotion/captions
compatible_agents:
  - motion_planning
  - motion_animation
compatible_project_modes:
  - motion_only
---

# Captions & Word-Synced Emphasis

- The project-level Telugu subtitles are a separate optional layer (`meta.subtitles`, Noto Sans Telugu); on-screen text inside a scene is ENGLISH (CLAUDE.md).
- English caption phrases: build `Caption` objects `{ text, startMs, endMs, timestampMs: null, confidence: null }` (a leading space in `text` for every word after the first) from the phrase timing you are given, then
  `const { pages } = createTikTokStyleCaptions({ captions, combineTokensWithinMilliseconds: 800 });` (`import { createTikTokStyleCaptions } from "@remotion/captions"`).
- Each page: `{ text, startMs, durationMs, tokens: [{ text, fromMs, toMs }] }`. Current time `const t = (frame / fps) * 1000`; the active page is the one with `t >= startMs && t < startMs + durationMs`; the active token has `t >= fromMs && t < toMs` (accent colour / scale 1.08, the others white).
- Spoken-word timing: `import { useSceneData } from "../sceneData"` gives `words: { w, start, end }[]` in SECONDS on the global timeline. Convert the frame with `import { useAbsFrame } from "../sceneContext"` (global frame) and compare `abs / fps` with `start`/`end` to pulse an emphasis exactly when a word is spoken. The words are Telugu: use them for TIMING only, never print them.
- Style: bottom third inside the safe area, 56 to 72px, weight 800, text-shadow, glass pill behind (see motion.design_kit). Words enter with `spring` scale 0.85 to 1 over 6 frames.
