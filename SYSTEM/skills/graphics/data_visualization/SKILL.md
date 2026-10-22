---
skill_id: graphics.data_visualization
name: Dynamic Motion Data Visualization
domain: graphics
version: 1.0.0
summary: Synthesizes parameterized, accessible motion graphics (bar charts, line graphs, donut charts, metric counters) with Remotion spring pacing.
status: approved
source: local
license: Apache-2.0
license_evidence: Authored internally for Dark World Video Generation Agent.
risk_level: low
capabilities:
  - data-visualization
  - bar-chart
  - line-chart
  - donut-chart
  - metric-counter
  - spring-pacing
tags:
  - graphics
  - charts
  - data
  - remotion
  - motion
dependencies: []
compatible_agents:
  - motion_generation
  - motion_architect
compatible_project_modes:
  - motion_only
input_contracts:
  chart_type:
    type: string
    options:
      - bar_chart
      - line_chart
      - donut_chart
      - metric_counter
    default: bar_chart
  data_points:
    type: list
    description: List of items with 'label' (string) and 'value' (number)
  theme:
    type: string
    default: dark_cyan
  aspect_ratio:
    type: string
    options:
      - "9:16"
      - "16:9"
    default: "9:16"
  animation_duration_frames:
    type: integer
    default: 45
output_contracts:
  svg_paths:
    type: list
    description: Evaluated SVG vector path definitions for the chart elements
  interpolations:
    type: dict
    description: Remotion spring and interpolate configurations for entrance and progression
  clamped_bounds:
    type: dict
    description: Screen bounding box ensuring zero clipping across canvas safe zones
  legend:
    type: list
    description: Formatted label and color mappings
---

# Dynamic Motion Data Visualization

## Purpose
Provides a parameterized, multi-variant data visualization engine for documentary videos.
Renders responsive bar charts, progression line graphs, proportional donut charts, and
incrementing numerical metric counters at 30 fps with smooth Remotion spring curves.

## Supported Variants

1. **`bar_chart`**:
   - Compares 2 to 5 distinct categories.
   - Bars animate upwards (or horizontally in 9:16) using `spring()` with `damping: 14, stiffness: 90`.
   - Data values dynamically tick upward alongside bar progress.

2. **`line_chart`**:
   - Illustrates temporal progression or growth metrics across 3 to 8 points.
   - Line stroke animates using SVG `strokeDashoffset` from length to 0.
   - Anchor points pop in sequentially with slight stagger (3 frames per point).

3. **`donut_chart`**:
   - Displays percentage distribution across 2 to 4 segments.
   - SVG `strokeDasharray` rotation around center point with smooth easing.
   - Central callout highlights the primary metric percentage.

4. **`metric_counter`**:
   - High-impact single or dual metric callout (e.g., "$12.4 Billion", "85% Growth").
   - Large typography with tabular numbers (`fontVariantNumeric: 'tabular-nums'`).
   - Smooth interpolation from 0 to target value with spring settling.

## Remotion Implementation Primitives

- Code must exclusively utilize Remotion primitives:
  - `useCurrentFrame()`
  - `useVideoConfig()`
  - `spring({ frame, fps, config: { damping: 12, mass: 0.8, stiffness: 100 } })`
  - `interpolate(frame, [start, end], [0, 1], { extrapolateRight: 'clamp' })`
- Do not import external charting libraries (e.g., recharts, chart.js); all graphics must be pure vector SVG/TSX.

## Layout & Accessibility Constraints

- Maximum 5 categories on 9:16 screens to avoid visual crowding.
- Contrast ratio between text and background must exceed 4.5:1.
- All numbers must be rounded to at most 1 decimal place unless exact currency is required.
