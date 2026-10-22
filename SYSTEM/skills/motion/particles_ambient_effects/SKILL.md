---
skill_id: motion.particles_ambient_effects
name: Particles & Ambient Effects (seeded, CPU-friendly)
domain: motion
version: 1.0.0
summary: Deterministic floating particles, glows and noise-driven motion using remotion random() and @remotion/noise.
status: approved
source: local
license: Apache-2.0
license_evidence: Authored internally for Dark World Video Generation Agent. Libraries named here are installed from npm under their own licenses (Remotion License (@remotion/noise)).
risk_level: low
capabilities:
  - particles
  - ambient-motion
  - procedural
dependencies:
  - remotion
  - @remotion/noise
compatible_agents:
  - motion_planning
  - motion_animation
compatible_project_modes:
  - motion_only
---

# Particles & Ambient Effects

- Determinism: positions come from `random("p" + i)` (`import { random } from "remotion"`) and the frame, never `Math.random()` or timers (the renderer rejects wall-clock animation).
- Drift: `x = baseX + noise2D("x" + i, frame / 90, i) * 60`, `y = baseY - ((frame * speed + offset) % height)`; `import { noise2D } from "@remotion/noise"` returns -1..1.
- Budget for this CPU: at most ~60 SVG circles, radius 1 to 4px, opacity 0.15 to 0.6; NO blur filters on individual particles, no canvas. One soft glow = a few large radial gradients behind them.
- Looks: floating dust (slow upward drift), sparkles (opacity = `Math.abs(Math.sin(frame / 12 + i))`), data streams (thin vertical lines falling at different speeds), glowing orbs (radial-gradient circles, 200 to 500px, opacity 0.2).
- Keep particles behind the content and below 40% opacity so text stays readable.
