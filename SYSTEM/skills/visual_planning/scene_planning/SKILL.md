---
skill_id: visual.scene_planning
name: Visual Scene Planning and Concept Breakdown
domain: visual_planning
version: 1.0.0
summary: Transforms segmented narration into structured semantic visual concepts, element hierarchies, and mode-aware layouts.
status: approved
source: local
license: Apache-2.0
license_evidence: Authored internally for Dark World Video Generation Agent.
risk_level: low
capabilities:
  - scene-concept-generation
  - element-hierarchy-planning
  - mode-aware-layout
  - visual-objective-mapping
tags:
  - visual_planning
  - concept
  - hierarchy
  - elements
  - layout
dependencies: []
compatible_agents:
  - visual_concept
  - motion_architect
compatible_project_modes:
  - motion_only
input_contracts:
  scene_id:
    type: string
    description: Unique identifier for the scene
  narration_text:
    type: string
    description: Telugu or English transcribed speech for this scene
  duration_seconds:
    type: float
    description: Duration of the scene in seconds
  aspect_ratio:
    type: string
    options:
      - "9:16"
      - "16:9"
    default: "9:16"
  theme_palette:
    type: dict
    description: Color scheme including primary, accent, surface, and background colors
output_contracts:
  visual_concept:
    type: string
    description: Core metaphor, graphic representation, or kinetic scene visual
  scene_objective:
    type: string
    description: What the audience should understand or feel from this scene
  elements:
    type: list
    description: List of visual elements with type, role, z_index, and layout bounds
  hierarchy:
    type: dict
    description: Visual dominance tree specifying primary, secondary, and tertiary elements
  layout_mode:
    type: string
    description: Canvas layout style (centered_headline, split_metric, diagrammatic, etc.)
---

# Visual Scene Planning and Concept Breakdown

## Purpose
Transforms spoken Telugu narrative scenes into high-impact, semantic motion concepts.
Establishes the visual hierarchy, kinetic typography roles, diagrams, and element layers
for autonomous code generation while strictly respecting Motion-Only constraints.

## Core Rules

1. **Semantic Concept Mapping**:
   - Every scene must extract 1 core visual metaphor directly related to the narration.
   - Do not request generic "backgrounds"; specify concrete kinetic graphic elements.

2. **Motion-Only Mode Adherence**:
   - External photographic image generation and stock video clip requests are strictly prohibited.
   - All visual elements must be achievable via Remotion vector shapes, SVG diagrams, typography, charts, or particles.

3. **Element Breakdown & Z-Index Layering**:
   - Layer 0 (Background): Subtle radial gradient, grid, or ambient particle field.
   - Layer 1 (Secondary Graphics): Supporting charts, diagrams, bounding frames, or accent rules.
   - Layer 2 (Primary Focus): Dominant kinetic typography, focal diagram, or numerical counter.
   - Layer 3 (Overlay / Captions): Safe-zone synchronized Telugu subtitles or badges.

4. **Aspect-Ratio Sensitivity**:
   - `9:16` Vertical: Maintain single vertical stack; focal elements occupy center 60% of screen.
   - `16:9` Landscape: Utilize horizontal balance; split screen (left: graphic/chart, right: kinetic text).

## Safe Zones and Layout Bounds

- **9:16 Canvas (1080 × 1920)**:
  - Top margin: 230px (preserves mobile header / status bar safety).
  - Bottom margin: 345px (preserves mobile engagement icons / description area).
  - Left / Right margins: 86px.

- **16:9 Canvas (1920 × 1080)**:
  - Top / Bottom margins: 90px (title safe zone).
  - Left / Right margins: 120px (action safe zone).
