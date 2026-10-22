---
skill_id: visual.scene_variety_pacing
name: Scene Variety and Pacing Rhythm Governance
domain: visual_planning
version: 1.0.0
summary: Enforces visual variety across adjacent scenes, prevents visual fatigue,
  alternates representation patterns and shot layouts, and manages narrative pacing.
status: draft
source: local
license: Apache-2.0
license_evidence: 'Authored via Skill Factory: skill_factory'
risk_level: low
capabilities:
- scene-variety-enforcement
- visual-fatigue-prevention
- shot-size-alternation
- pacing-rhythm-control
tags:
- scene_variety
- pacing
- fatigue_prevention
- shot_alternation
dependencies: []
compatible_agents:
- visual_planning
- visual_concept
- motion_architect
compatible_project_modes:
- motion_only
target_agent_id: visual_planning
input_contracts:
  scene_sequence:
    type: list
    description: Sequential list of planned scenes
output_contracts:
  variety_verdict:
    type: string
    description: Pass or detected repetition warnings
  density_curve:
    type: list
    description: Density score per scene across duration
---

# Scene Variety and Pacing Rhythm Governance

## Purpose
Prevents repetitive scene designs and visual monotony by enforcing systematic variety across scene representations, layout regions, visual densities, and emotional tension.

## Core Directives

1. **Consecutive Scene Representation Prohibition**:
   - Consecutive scenes must not use identical representation patterns unless narratively justified.
   - Alternate across `abstract_graphic`, `comparison`, `process_diagram`, `object_in_context`, `typography`, and `data_visualization`.

2. **Spatial Layout Alternation**:
   - Vary the focal region between adjacent scenes (e.g. Center Hero -> Split Left/Right -> Central Ring Network -> Triad Row -> Lower Skyline -> Dual Horizon).
   - Ensure viewer focal attention shifts dynamically across the canvas.

3. **Pacing Rhythm and Density Breathing Room**:
   - Alternate high-density multi-element scenes with clean, minimalist single-concept moments.
   - Follow tension peaks (such as warning/danger) with expansive, visionary resolutions.
