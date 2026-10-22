# Validation Domain Skills

## Overview
Skills in the `validation` domain enforce technical constraints, safe area bounding margins, font legibility rules, contrast ratios, and resource library file integrity across all video assets.

## Associated Agents
- `motion_timeline_validation` (`MotionValidationAgent`): Evaluates compositions against 12 technical validation rules and generates preview frames.
- `final_qc` (`FinalQcAgent`): Automated black frame / freeze detection and human playback audit.

## Active Skills
- `validation.layout_safe_zones` (`layout_safe_zones/SKILL.md`): Enforces 10% outer title-safe boundary and 20% platform action-safe boundary (preventing overlap with social media UI overlays).

## Contribution Guidelines
1. Validation skills must define unambiguous, computable boundary checks.
2. Must never bypass errors or suppress critical rendering defects.
3. Promote approved skills into `SYSTEM/skills/validation/<skill_name>/SKILL.md`.
