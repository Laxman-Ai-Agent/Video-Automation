---
skill_id: motion.charts_nivo_echarts
name: Charts & Gauges (Nivo / ECharts SVG)
domain: motion
version: 1.0.0
summary: Premium charts and gauges rendered as SVG, driven by the frame.
status: approved
source: local
license: Apache-2.0
license_evidence: Authored internally for Dark World Video Generation Agent. Libraries named here are installed from npm under their own licenses (MIT (@nivo/*), Apache-2.0 (echarts)).
risk_level: low
capabilities:
  - bar-chart
  - line-chart
  - pie-chart
  - gauge
  - sankey
  - treemap
  - heatmap
dependencies:
  - remotion
  - @nivo/core
  - @nivo/bar
  - @nivo/line
  - @nivo/pie
  - echarts
compatible_agents:
  - motion_planning
  - motion_animation
compatible_project_modes:
  - motion_only
---

# Charts & Gauges

## Nivo (React SVG)
`import { Bar } from "@nivo/bar"` (also line, pie, radar, funnel, waffle, sankey, treemap, heatmap, chord). Always the fixed-size component (never `Responsive*`): `width`/`height` in px. Always `animate={false}`. Make the data a function of the frame: `value * spring({ frame: frame - 6, fps })`.
Style: `theme={{ text: { fill: "#cbd5e1", fontSize: 22 }, grid: { line: { stroke: "rgba(255,255,255,0.08)" } } }}`, rounded bars (`borderRadius`), gradient fills with `defs=[{ id, type: "linearGradient", colors: [{offset:0,color},{offset:100,color}] }]` and `fill=[{ match: "*", id }]`. Hide clutter: `enableLabel={false}`, `tickSize: 0`.

## ECharts gauge / extra chart types (SVG, server-side rendering)
`import * as echarts from "echarts/core"; import { GaugeChart } from "echarts/charts"; import { SVGRenderer } from "echarts/renderers"; echarts.use([GaugeChart, SVGRenderer]);` Import only from `echarts/core|charts|components|renderers` (never bare `echarts`).
`const c = echarts.init(null, null, { renderer: "svg", ssr: true, width, height }); c.setOption({ animation: false, ... }); const svg = c.renderToSVGString(); c.dispose();` then `<div dangerouslySetInnerHTML={{ __html: svg }} />`. Compute the option from the frame each render.

## Place charts inside a glass card (motion.design_kit). One chart per scene; label the key number big.
