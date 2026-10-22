---
skill_id: visual.cinematic_composition
name: Cinematic Composition and Depth Layering
domain: visual_planning
version: 1.0.0
summary: Enforces 3-plane depth layering (foreground, midground, background), rule-of-thirds
  focal point placement, safe area margin compliance, and eye-flow direction.
status: draft
source: local
license: Apache-2.0
license_evidence: 'Authored via Skill Factory: skill_factory'
risk_level: low
capabilities:
- cinematic-composition
- depth-layering
- visual-hierarchy
- safe-area-governance
- focal-point-direction
tags:
- cinematic
- composition
- depth_layering
- visual_hierarchy
- safe_zones
dependencies: []
compatible_agents:
- visual_planning
- visual_concept
- motion_architect
compatible_project_modes:
- motion_only
target_agent_id: visual_planning
input_contracts:
  scene_id:
    type: string
    description: Scene identifier
  aspect_ratio:
    type: string
    options:
    - '16:9'
    - '9:16'
  elements:
    type: list
    description: Planned elements
output_contracts:
  depth_layers:
    type: dict
    description: Assigned foreground, midground, background elements
  focal_region:
    type: string
    description: Primary focal point region
  safe_area_checked:
    type: bool
    description: Verification of safe area bounds
---

# Cinematic Composition and Depth Layering

## Purpose
Establishes cinematic visual hierarchy and multi-plane depth layering for autonomous Motion-Only video generation. Eliminates flat, empty backgrounds by structuring scenes into Foreground, Midground, and Background planes.

## Core Directives

1. **Three-Plane Spatial Depth Structure**:
   - **Layer 0 (Background / Environment)**: Ambient atmosphere, radial depth gradient, subtle particle grid, or darkening skyline. Never pure black emptiness.
   - **Layer 1 (Midground / Supporting)**: Contextual relational graphics, branching networks, system nodes, comparison anchors, or secondary diagrams.
   - **Layer 2 (Foreground / Hero Focus)**: Dominant hero element (igniting intelligence core, super AI node, globe, key triad icon) and concise kinetic text.

2. **Rule-of-Thirds & Asymmetric Balance**:
   - Avoid placing all elements dead center across consecutive scenes.
   - Use dynamic visual tension: split comparison (left 35% vs right 65%), diagonal energy flow (lower-left origin to upper-right destination), or upper-safe headline over lower-safe thematic entity.

3. **Safe Area Margin Governance**:
   - 16:9 Landscape (1920x1080): 5% minimum margin (96px left/right, 54px top/bottom).
   - 9:16 Portrait (1080x1920): 16% bottom safety margin for mobile UI engagement icons; 12% top margin for status headers.

4. **Visual Flow & Eye Guidance**:
   - Leading lines, radiant filaments, and network connections must direct viewer gaze toward the primary focal element.
