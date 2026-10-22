---
skill_id: motion.lottie_overlays
name: Lottie Animated Illustrations
domain: motion
version: 1.0.0
summary: Pre-made vector animations, frame-driven by Remotion.
status: approved
source: local
license: Apache-2.0
license_evidence: Authored internally for Dark World Video Generation Agent. Libraries named here are installed from npm under their own licenses (MIT (lottie-web), Remotion License (@remotion/lottie); each animation file has its own license).
risk_level: low
capabilities:
  - lottie
dependencies:
  - remotion
  - @remotion/lottie
  - lottie-web
compatible_agents:
  - motion_planning
  - motion_animation
compatible_project_modes:
  - motion_only
---

# Lottie Animated Illustrations

- `import { Lottie } from "@remotion/lottie"; import animationData from "../lottie/success_check.json";` then `<Lottie animationData={animationData} style={{ width, height }} />`. Remotion drives the playhead from the current frame; never `fetch` the JSON, always import it statically.
- Only SVG-renderer friendly files under ~300 KB; avoid files with heavy masks/expressions (slow, may not render).
- Check each file's licence (LottieFiles licences vary) and record it next to the file before use.
- Place on a glass card or directly on the gradient; keep one Lottie per scene.

## Available animations (src/lottie/manifest.json lists every file with its source and licence)
- `success_check.json`: ring draws on, then a check mark (success / verified; holds its final state).
- `loading_ring.json`: rotating arc over a faint track (loading / processing; loop).
- `pulse_rings.json`: rings expanding from a dot (signal / live / alert; loop).
- `arrow_bounce.json`: arrow bouncing forward (next / continue; loop).
Use ONLY files listed in the manifest: the audit rejects any other `../lottie/*.json` import.

## Adding an external animation (e.g. LottieFiles)
Download it yourself from its page, check THAT page's licence (Lottie Simple License allows commercial use but not redistribution of the file, and creators may add terms), keep it under 300 KB and self-contained (no image assets), save it to `VIDEO_ENGINE/remotion/src/lottie/`, and add an entry to `manifest.json` with id, file, description, author, licence and the page URL. Do not publish the repository publicly with such files in it.
