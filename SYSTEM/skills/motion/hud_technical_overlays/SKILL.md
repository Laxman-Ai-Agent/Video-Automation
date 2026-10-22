---
skill_id: motion.hud_technical_overlays
name: HUD & Technical Overlays
domain: motion
version: 1.0.0
summary: Sci-fi / technical interface elements in SVG: brackets, scan lines, grids, ring gauges, readouts.
status: approved
source: local
license: Apache-2.0
license_evidence: Authored internally for Dark World Video Generation Agent. Libraries named here are installed from npm under their own licenses (none).
risk_level: low
capabilities:
  - hud
  - scan-line
  - technical-overlay
dependencies:
  - remotion
  - @remotion/noise
  - @remotion/paths
compatible_agents:
  - motion_planning
  - motion_animation
compatible_project_modes:
  - motion_only
---

# HUD & Technical Overlays

- Corner brackets: 4 SVG `path`s (L-shapes, stroke 3px, accent colour, 70% opacity) at the safe-area corners; they draw in with `evolvePath` over 12 frames.
- Scan line: a 2px gradient line whose `translateY` = `(frame * 6) % height`; a faint 40px band behind it; opacity 0.5.
- Grid / blueprint: SVG pattern of thin lines every 60px at 5 to 8% white; major lines every 5th at 12%.
- Ring gauge: circle with `strokeDasharray` ticks (`2 14`) rotating slowly (`rotate(frame * 0.4)`), plus an arc for the value.
- Readouts: `fontFamily: fontStack("mono")` (`import { fontStack } from "../fonts"`), 20 to 26px, letter-spacing 2px, values changing with the frame (`Math.round(base + noise2D("v", frame / 40, 0) * 5)`), a blinking cursor = `Math.floor(frame / 15) % 2`.
- Target indicator: a circle + crosshair that moves between two points with `spring`; a label box follows with a short leader line.
- All 2D SVG; no WebGL, no perspective transforms; keep the HUD at 30 to 60% opacity so it never competes with the message.
