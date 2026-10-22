---
skill_id: visual.narrative_semantic_mapping
name: Narrative-to-Visual Semantic Metaphor Mapping
domain: visual_planning
version: 1.0.0
summary: Translates spoken narrative concepts into concrete visual entities, eliminating
  generic placeholder graphics and grounding abstract ideas in tangible visual structures.
status: draft
source: local
license: Apache-2.0
license_evidence: 'Authored via Skill Factory: skill_factory'
risk_level: low
capabilities:
- narrative-semantic-mapping
- metaphor-selection
- concrete-visual-grounding
- entity-relationship-structuring
tags:
- narrative_mapping
- visual_metaphor
- concrete_grounding
- semantic_entities
dependencies: []
compatible_agents:
- visual_planning
- visual_concept
- motion_architect
compatible_project_modes:
- motion_only
target_agent_id: visual_planning
input_contracts:
  narration_text:
    type: string
    description: Spoken transcript
  core_meaning:
    type: string
    description: Underlying narrative meaning
output_contracts:
  visual_metaphor:
    type: string
    description: Selected visual metaphor
  entity_breakdown:
    type: list
    description: Concrete visual entities
---

# Narrative-to-Visual Semantic Metaphor Mapping

## Purpose
Ensures spoken narration translates into concrete, contextually relevant visual entities rather than generic abstract shapes or empty floating icons.

## Core Directives

1. **Concrete Metaphor Grounding**:
   - Transform abstract narrative statements into specific visual constructs:
     - *Intelligence birth* -> Glowing neural core igniting radiating filaments.
     - *Super AI vs Human* -> Asymmetric scale comparison: small dim node eclipsed by massive pulsing nexus.
     - *Earth systems transformation* -> High-tech planetary globe encircled by an interconnected, lighting system grid.
     - *Multi-domain breakthroughs (medicine, energy, science)* -> Structured triad icon cluster populating in quick succession.
     - *Civilization risk* -> Atmospheric city skyline silhouette transitioning into high-contrast hazard warning.
     - *Epochal transition* -> Dual-state horizon divide: decaying monochromatic past fading into luminous cyan dawn.

2. **Subject-Action-Object Semantic Mapping**:
   - Identify the narrative subject (who/what acts), the action verb (what dynamic change occurs), and the object (what is affected).
   - Ensure the visual composition visually embodies this relationship using directional relational edges (`connects_to`, `flows_from`, `compares_with`, `explains`).

3. **Motion-Only Feasibility**:
   - No external photos or raster footage required. All metaphors must be expressible via vector geometry, Lucide icons, SVG paths, data charts, and typography.
