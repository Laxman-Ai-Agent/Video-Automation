---
skill_id: motion.maps_regions
name: Regional Maps (US states, countries, nation outlines)
domain: motion
version: 1.0.0
summary: TopoJSON maps with d3-geo: us-atlas states and world-atlas countries, highlight and reveal by frame.
status: approved
source: local
license: Apache-2.0
license_evidence: Authored internally for Dark World Video Generation Agent. Libraries named here are installed from npm under their own licenses (ISC (us-atlas, topojson-client, d3-geo)).
risk_level: low
capabilities:
  - us-map
  - regional-map
  - choropleth
dependencies:
  - remotion
  - d3-geo
  - topojson-client
  - us-atlas
  - world-atlas
compatible_agents:
  - motion_planning
  - motion_animation
compatible_project_modes:
  - motion_only
---

# Regional Maps

- US: `import us from "us-atlas/states-10m.json"; import { feature } from "topojson-client"; const states = feature(us as any, (us as any).objects.states); const projection = geoAlbersUsa().fitSize([width, height], states); const pathOf = geoPath(projection);` (`import { geoAlbersUsa, geoPath } from "d3-geo"`). State ids are 2-digit FIPS strings ("06" California, "48" Texas, "36" New York); `properties.name` has the name. Other files: `nation-10m.json`, `counties-10m.json` (large: avoid unless needed).
- World: `world-atlas/countries-110m.json` (country ids are numeric ISO codes as strings, e.g. "356" India, "840" United States, "156" China) with `geoNaturalEarth1` (see motion.diagrams_layout).
- Style: dim glass fill (rgba(255,255,255,0.06)), thin light borders (0.5px, 18% white), highlighted regions with the accent gradient + `drop-shadow(0 0 12px accent)`; reveal highlights one by one by frame (opacity 0 to 1, 8-frame stagger); a small label chip near the region centroid (`pathOf.centroid(feature)`).
- Choropleth: `scaleLinear` from `d3-scale` mapping a value to two accent colours; draw a legend bar.
- No map tiles, no WebGL.
