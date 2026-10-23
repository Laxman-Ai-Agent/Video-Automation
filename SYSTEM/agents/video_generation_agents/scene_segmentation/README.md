# Scene Segmentation Agent

- **Agent ID:** `scene_segmentation`
- **Stage ID:** `segmentation`
- **Version:** `2.0.0`
- **Primary Class:** `SceneSegmentationAgent` (alias `SceneSegmentationAdapter`)

## Purpose
Partitions narration transcript into semantic scenes obeying strict duration and word-boundary rules, augmented by an LLM-powered narrative intelligence layer for cross-lingual topic modeling, Telugu-English vocabulary standardization, and adaptive pacing telemetry.

## Capabilities
- `semantic-chunking`
- `boundary-snapping`
- `duration-enforcement`
- `topic-modeling`
- `adaptive-pacing`
- `vocabulary-standardization`

## Bound Tools
- `llm_client`
- `llm_gateway`
- `regex_validator`

## Architecture Notes
This agent operates as a dedicated autonomous component inheriting from `SYSTEM.agents.shared.BaseAgent`.
It possesses isolated private memory (`self.memory`), execution history logging, and connects directly to the central skill catalog and tool registry.
The deterministic core in `VIDEO_ENGINE/stages/scene_segmentation.py` groups the words of `transcript_corrected.json` into scenes; its timing and coverage invariants are checked by `DeterministicInvariantGuard`. Semantic intelligence is orchestrated via `SYSTEM.agents.video_generation_agents.scene_segmentation.semantic_analyzer.SemanticAnalyzer` and guarded by `DeterministicInvariantGuard`.
