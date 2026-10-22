# Motion Domain Skills

## Overview
Skills in the `motion` domain drive kinetic typography choreography, spring curve physics, entry/exit timing, layout collision resolution, and Remotion TSX code generation.

## Associated Agents
- `motion_planning` (`MotionPlanningAgent`): Kinetic rhythm, bounding box placement, typography hierarchy.
- `motion_animation` (`MotionAnimationAgent`): Standalone TSX component synthesis and Remotion composition staging.

## Active Skills
- `motion.kinetic_typography` (`kinetic_typography/SKILL.md`): Guidelines for kinetic word-by-word animation, weight shifts, and stagger delays.
- `motion.remotion_spring_curves` (`remotion_spring_curves/SKILL.md`): Remotion spring configurations (`damping`, `mass`, `stiffness`) for snappy typography transitions.

## Contribution Guidelines
1. Ensure all Remotion spring curves are parameterized and bounded to prevent infinite oscillations.
2. Motion skills must adhere strictly to the Motion-Only architecture (no legacy image-mode fallbacks).
3. Promote approved skills into `SYSTEM/skills/motion/<skill_name>/SKILL.md`.
