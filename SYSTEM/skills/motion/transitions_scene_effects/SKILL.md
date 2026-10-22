---
skill_id: motion.transitions_scene_effects
name: In-Scene Transitions (DOM-only) and Scene Hand-off
domain: motion
version: 1.0.0
summary: Sub-scene transitions with @remotion/transitions fade/slide/wipe/flip/iris/clock-wipe; no WebGL transitions or light leaks.
status: approved
source: local
license: Apache-2.0
license_evidence: Authored internally for Dark World Video Generation Agent. Libraries named here are installed from npm under their own licenses (Remotion License (@remotion/transitions)).
risk_level: low
capabilities:
  - transitions
  - scene-handoff
dependencies:
  - remotion
  - @remotion/transitions
compatible_agents:
  - motion_planning
  - motion_animation
compatible_project_modes:
  - motion_only
---

# In-Scene Transitions

- Transitions BETWEEN scenes are decided by the pipeline (`transition_out` in the motion plan); a scene only needs a clean entrance (first 10 frames) and exit (last 8 to 12 frames: opacity + 20px move).
- Inside one scene, beats can be chained with `TransitionSeries`:
  `import { TransitionSeries, linearTiming } from "@remotion/transitions"; import { fade } from "@remotion/transitions/fade";`
  `<TransitionSeries><TransitionSeries.Sequence durationInFrames={60}>...</TransitionSeries.Sequence><TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: 15 })} /><TransitionSeries.Sequence durationInFrames={60}>...</TransitionSeries.Sequence></TransitionSeries>`
- Allowed presentations (plain DOM, fast on this CPU): `fade` (`@remotion/transitions/fade`), `slide` (`/slide`), `wipe` (`/wipe`), `flip` (`/flip`), `iris` (`/iris`), `clockWipe` (`/clock-wipe`). A transition overlaps its neighbours: total = sum of sequences minus the transitions.
- FORBIDDEN (WebGL / canvas, unsupported here and rejected by the audit): `@remotion/light-leaks`, `blurSlide`, `crossZoom`, `dreamyZoom`, `filmBurn`, `linearBlur`, and the presentations blur-slide, book-flip, cross-zoom, crosswarp, dissolve, dreamy-zoom, film-burn, linear-blur, ripple, swap, zoom-blur, zoom-in-out.
- A "light leak" look: a large radial gradient (amber to transparent) whose position and opacity are driven by the frame, blend-mode `screen`.
