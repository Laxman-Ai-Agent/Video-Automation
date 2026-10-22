# Animation Domain Skills

## Overview
Skills in the `animation` domain provide specialized TSX component structures, preset motion effects (e.g. wipe, glitch, scale-in, blur-fade), and canvas styling primitives for Remotion compositions.

## Associated Agents
- `motion_animation` (`MotionAnimationAgent`): Remotion code synthesizer.

## Technical Constraints
- All animation components must compile cleanly with `tsc --noEmit`.
- Animation components must be self-contained or import only from allowlisted Remotion packages (`remotion`, `@remotion/shapes`).
- No external unverified npm dependencies.

## Contribution Guidelines
1. Validate AST safety and type soundness.
2. Stage in `SYSTEM/skills/staging/` and test preview still rendering.
3. Promote approved skills into `SYSTEM/skills/animation/<skill_name>/SKILL.md`.
