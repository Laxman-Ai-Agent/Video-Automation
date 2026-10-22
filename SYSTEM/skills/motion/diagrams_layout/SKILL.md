---
skill_id: motion.diagrams_layout
name: Diagrams, Networks & Maps (precomputed layout)
domain: motion
version: 1.0.0
summary: Flowcharts, networks, trees and maps with layout computed up front and drawn as SVG.
status: approved
source: local
license: Apache-2.0
license_evidence: Authored internally for Dark World Video Generation Agent. Libraries named here are installed from npm under their own licenses (MIT (@dagrejs/dagre), ISC (d3-*), ISC (topojson-client)).
risk_level: low
capabilities:
  - flowchart
  - network
  - treemap
  - map
dependencies:
  - remotion
  - @dagrejs/dagre
  - d3-force
  - d3-hierarchy
  - d3-geo
  - topojson-client
  - world-atlas
compatible_agents:
  - motion_planning
  - motion_animation
compatible_project_modes:
  - motion_only
---

# Diagrams, Networks & Maps

- Flowcharts: `@dagrejs/dagre` computes node x/y (`dagre.layout(g)`), draw boxes/arrows as SVG; reveal nodes in order with frame-driven opacity/translate; arrows with `evolvePath`.
- Networks: `d3-force` simulation `.stop()` then `.tick(300)` synchronously, then draw the final positions (optionally interpolate from a start layout by frame). No live simulation.
- Trees/treemaps: `d3-hierarchy` (`hierarchy`, `treemap`, `tree`).
- Maps: `d3-geo` (`geoNaturalEarth1` or `geoOrthographic` for a globe) + `topojson-client` `feature(world, world.objects.countries)` + `world-atlas/countries-110m.json`, projected to SVG paths; style with gradient fill, thin light borders, glow on the highlighted country; reveal by frame-driven opacity/stroke. No map tiles, no WebGL.
