# Scene Segmentation Domain Skills

## Overview
Skills in the `scene_segmentation` domain partition narration transcripts into coherent semantic scenes adhering to strict duration limits, natural sentence pauses, and word boundary alignment.

## Associated Agents
- `scene_segmentation` (`SceneSegmentationAgent`): Splits narration into semantic scenes.

## Constraints & Requirements
- Target scene duration: 3 to 7 seconds per scene.
- Every cut must align precisely with word boundary timestamps.
- Zero gap between adjacent scenes; total scenes duration must equal audio duration.
- Preserve all algorithm invariants in `VIDEO_ENGINE/stages/scene_segmentation.py`.

## Contribution Guidelines
1. Validate semantic splitting algorithms against the corrected transcript (`transcript_corrected.json`).
2. Stage proposed segmentation heuristics in `SYSTEM/skills/staging/`.
3. Promote approved skills into `SYSTEM/skills/scene_segmentation/<skill_name>/SKILL.md`.
