---
skill_id: motion.kinetic_typography
name: Kinetic Typography Specialist
domain: motion
version: 1.0.0
summary: Principles and constraints for Telugu narration kinetic typography layout, timing, and readability.
status: approved
source: local
license: Apache-2.0
license_evidence: Authored internally for Dark World Video Generation Agent.
risk_level: low
capabilities:
  - typography-layout
  - rhythm-matching
  - readability-optimization
dependencies:
  - remotion
compatible_agents:
  - motion_planning
  - motion_animation
compatible_project_modes:
  - motion_only
---

# Kinetic Typography Specialist Skill

## Purpose
Governs the visual pacing, font hierarchy, line wrapping, and motion mechanics of on-screen English text synchronized to Telugu spoken narration.

## Core Rules
1. **Language Orthography**:
   - Spoken audio is Telugu; on-screen kinetic text is English.
   - Text must clearly translate or emphasize key conceptual keywords from the Telugu audio.
2. **Readability & Pacing**:
   - Maximum 4 to 6 words displayed simultaneously on screen.
   - Word display duration must be at least 15 frames (0.5 seconds at 30 fps) to guarantee visual comprehension.
   - Stagger sequential words using 3 to 5 frame offsets to create natural reading flow.
3. **Visual Hierarchy**:
   - Hero/Keyword: Extra-bold font weight (800/900), accent color, scale factor 1.15-1.30.
   - Supporting phrase: Regular or medium font weight (400/500), muted color.
4. **Layout & Safe Zones**:
   - 9:16 Portrait: Text bounding box must stay within x: [100, 980], y: [250, 1650].
   - 16:9 Landscape: Text bounding box must stay within x: [160, 1760], y: [120, 960].
   - Never overlap text across screen borders or platform overlay areas.
