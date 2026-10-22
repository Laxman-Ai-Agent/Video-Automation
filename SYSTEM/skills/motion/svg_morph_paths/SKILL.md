---
skill_id: motion.svg_morph_paths
name: SVG Morphing & Path Drawing
domain: motion
version: 1.0.0
summary: Shape morphing and draw-on paths, deterministic and frame-driven.
status: approved
source: local
license: Apache-2.0
license_evidence: Authored internally for Dark World Video Generation Agent. Libraries named here are installed from npm under their own licenses (MIT (flubber), Remotion License (@remotion/paths)).
risk_level: low
capabilities:
  - morphing
  - path-draw
dependencies:
  - remotion
  - flubber
  - @remotion/paths
compatible_agents:
  - motion_planning
  - motion_animation
compatible_project_modes:
  - motion_only
---

# SVG Morphing & Path Drawing

- Morph: `import { interpolate as morph } from "flubber"; const d = morph(fromPath, toPath, { maxSegmentLength: 8 })(t);` with `t = interpolate(frame, [start, end], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })`. Build the morph function with `useMemo` (it is the expensive part).
- Draw-on line: `import { evolvePath, getLength } from "@remotion/paths"; const { strokeDasharray, strokeDashoffset } = evolvePath(progress, path);`.
- Style: gradient stroke (`<linearGradient>`), `strokeLinejoin="round"`, 6px stroke, fill at 30 to 40% opacity, a soft glow via `drop-shadow`.
- Everything derives from the frame: no timers, no `requestAnimationFrame`.
