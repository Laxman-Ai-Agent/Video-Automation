---
skill_id: visual.word_semantic_animation
name: Word-Level Semantic Visual Animation
domain: visual_planning
version: 1.0.0
summary: Coordinates multiple word-level semantic animation events within each scene,
  synchronizing meaningful words and action verbs to visual transformations using
  word-level alignment.
status: draft
source: local
license: Apache-2.0
license_evidence: 'Authored via Skill Factory: skill_factory'
risk_level: low
capabilities:
- word-level-semantic-animation
- temporal-event-coordination
- narration-visual-synchronization
- multi-event-scene-pacing
tags:
- word_animation
- semantic_timing
- word_alignment
- kinetic_synchronization
- multi_event
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
  word_timestamps:
    type: list
    description: List of words with start and end seconds
  elements:
    type: list
    description: Planned scene visual elements
output_contracts:
  word_animation_events:
    type: list
    description: Structured list of word-synchronized visual animation cues
---

# Word-Level Semantic Visual Animation

## Purpose
Maps key meaningful words, action verbs, and expressive adjectives from the spoken narration into synchronized, visually relevant animation cues. Coordinates multiple dynamic animation events within each scene without creating unnecessary scene cuts.

## Core Directives

1. **Word-Level Transcript Alignment**:
   - Ingest word-level timestamp data (`word@start-end` seconds) from Whisper transcript segments.
   - Ground every animation event to the precise second range where the key word/phrase is spoken.

2. **Semantic Word-to-Motion Vocabulary**:
   - **Emergence / Birth ("పుడుతోంది", "born", "ignites")**: Trigger `ignite_birth` event (scale from 0 to 1.1 with glowing filaments).
   - **Speed / Acceleration ("వేగం", "speed", "beyond imagination")**: Trigger `velocity_pulse` or `streak_acceleration` on the primary node.
   - **Power / Magnitude ("super AI", "బలమైన", "powerful")**: Trigger `power_burst` with radial shockwave and scale expansion.
   - **Global Network ("భూమి", "వ్యవస్థను", "systems")**: Trigger `network_connect` linking peripheral nodes to central globe.
   - **Rapid Creation ("క్షణాల్లో", "సృష్టించే", "in moments")**: Trigger `staggered_cascade` revealing entities with high-velocity spring pop.
   - **Hazard / Tension ("ప్రమాదం", "danger", "warning")**: Trigger `danger_alert_pulse` with amber/red luminance surge.
   - **Past Dissolving ("ముగింపు", "ending", "fading")**: Trigger `dissolve_fade` gently fading the past era elements.
   - **New Dawn ("ప్రారంభం", "beginning", "dawn")**: Trigger `dawn_reveal` expanding radiant illumination over the horizon.

3. **Multi-Event Scene Orchestration**:
   - A single 4-6s scene must feature 2 to 4 distinct, harmonized visual animation events that evolve the composition in real-time.
   - Events must NOT require scene cuts; elements transition, transform, or emphasize in place.
