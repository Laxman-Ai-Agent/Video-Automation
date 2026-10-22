---
skill_id: motion.infographic_layouts
name: Infographic Layouts (timeline, comparison, progress, table, lower third, callout)
domain: motion
version: 1.0.0
summary: Reusable explainer layouts built from SVG/DOM and frame-driven springs.
status: approved
source: local
license: Apache-2.0
license_evidence: Authored internally for Dark World Video Generation Agent. Libraries named here are installed from npm under their own licenses (none).
risk_level: low
capabilities:
  - timeline
  - comparison
  - progress
  - table
  - lower-third
  - callout
  - before-after
dependencies:
  - remotion
  - @remotion/paths
  - d3-scale
compatible_agents:
  - motion_planning
  - motion_animation
compatible_project_modes:
  - motion_only
---

# Infographic Layouts

Compose these on the dark gradient with glass cards (motion.design_kit). One idea per scene, max 3 to 4 items, the key number is the biggest element.
- **Timeline**: a horizontal line drawn with `evolvePath` (`@remotion/paths`), nodes (circles + icon) appearing with `spring` stagger 8 frames, year above, caption below; the current node glows.
- **Comparison (A vs B)**: two equal glass columns with a "VS" badge between; metric bars animate width from 0 with `spring`; the winner gets the accent gradient, the other stays neutral.
- **Progress**: ring = `strokeDasharray` / `strokeDashoffset` computed from `value * spring`; bar = width %; the number counts up with `Math.round(value * progress)`.
- **Table / data grid**: CSS grid, header row in accent, rows reveal one by one (opacity + translateY 12px, stagger 4 frames), numbers right-aligned, zebra rows at 4% white.
- **Lower third**: accent bar slides in from the left (translateX -100% to 0, 10 frames), name 40px / title 26px, glass strip behind, bottom-left inside the safe area.
- **Callout / annotation**: a dot on the target, a leader line drawn with `evolvePath`, a glass label box at the end of the line.
- **Before / after**: two layers, the "after" revealed by `clipPath: inset(0 ${100 - p}% 0 0)` with a thin bright divider at the edge; labels "Before"/"After" in chips.
- **Split screen / title card**: 50/50 glass panels with a 2px gap; title card = centred big gradient title, small kicker above, accent underline drawn by width.
- Scales: `d3-scale` (`scaleLinear().domain([0, max]).range([0, width])`) for bar lengths and positions.
