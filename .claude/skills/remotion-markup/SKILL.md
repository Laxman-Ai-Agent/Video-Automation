---
name: remotion-markup
description: Official Remotion best practices for compositions, timing (interpolate, spring, Sequence), layout, text measuring, fonts, audio, transitions and Lottie. Use when writing or editing Remotion scene/composition code in this project.
---

The canonical copy of this skill lives in the central skill library: read `SYSTEM/skills/remotion/markup/SKILL.md` (registry id `remotion.markup`) and the reference files next to it, then follow it.

Its "Project overrides" block wins over the rest: no 3D/WebGL/canvas, self-hosted fonts, only the libraries in `APPROVED_IMPORTS` (`VIDEO_ENGINE/stages/motion_animation.py`), type-check with `npx tsc --noEmit` in `VIDEO_ENGINE/remotion`.
