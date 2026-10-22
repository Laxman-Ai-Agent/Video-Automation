---
skill_id: motion.backgrounds_reveals_camera
name: Animated Backgrounds, Reveals & Camera Moves
domain: motion
version: 1.0.0
summary: Moving gradients, mask/clip reveals and 2D camera moves (push-in, pan, parallax).
status: approved
source: local
license: Apache-2.0
license_evidence: Authored internally for Dark World Video Generation Agent. Libraries named here are installed from npm under their own licenses (Remotion License (@remotion/noise)).
risk_level: low
capabilities:
  - animated-background
  - reveal
  - camera-motion
dependencies:
  - remotion
  - @remotion/noise
compatible_agents:
  - motion_planning
  - motion_animation
compatible_project_modes:
  - motion_only
---

# Animated Backgrounds, Reveals & Camera Moves

- Moving gradient: `background: linear-gradient(${120 + frame * 0.3}deg, c1, c2)` plus 2 to 3 large radial-gradient blobs (500 to 900px) whose positions follow `noise2D("b" + i, frame / 200, 0) * 120`; opacity 0.25 to 0.5. No blur filters over the full frame.
- Mask / clip reveal: `clipPath: inset(0 ${100 - p}% 0 0 round 24px)` (left to right), `circle(${r}% at 50% 50%)` (iris-like), or a diagonal `polygon(...)`; p from `interpolate(frame, [s, s + 15], [0, 100], { extrapolateRight: "clamp" })` with an ease-out.
- Camera push-in: wrap the content in a div with `transform: scale(${1 + 0.06 * progress}) translate(${dx}px, ${dy}px)` over the scene duration (slow, 3 to 8%); never scale text near the edges beyond the safe area.
- Parallax (2.5D without 3D): 2 to 3 layers moved by different fractions of one value (`x * 0.3`, `x * 0.6`, `x * 1`); 2D translate only, no `perspective`.
- Glitch (use sparingly, 6 to 10 frames): offset a duplicate of the headline by 4 to 8px in cyan and magenta with `mix-blend-mode: screen`, driven by `random("g" + frame)`.
