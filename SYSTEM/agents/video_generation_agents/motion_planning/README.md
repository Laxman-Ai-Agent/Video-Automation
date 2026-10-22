# Motion Planning Agent

- **Agent ID:** `motion_planning`
- **Stage ID:** `motion_plan`
- **Version:** `2.0.0`
- **Primary Class:** `MotionPlanningAgent` (alias `MotionPlanningAdapter`)

## Purpose
Transforms visual plans and scene segmentation into cinematic, audio-aware, temporally synchronized, collision-safe motion plans (`motion_plan.json` and `motion_planning.json`).

## Capabilities
- `kinetic-typography-math`
- `spring-curve-solver`
- `transition-scheduling`
- `cinematic-camera-choreography`
- `audio-reactive-intelligence`
- `collision-resolution`

## Bound Tools
- `llm_client`
- `llm_gateway`
- `spring_solver`

## Architecture Notes
This agent operates as a dedicated autonomous component inheriting from `SYSTEM.agents.shared.BaseAgent`.
It possesses isolated private memory (`self.memory`), execution history logging, and connects directly to the central skill catalog and tool registry.
Creative and semantic decisions (strategy selection, narrative role, camera move, spring physics profile, audio-reactive accents) are reasoned via `MotionIntelligenceEngine` and LLM Gateway (`fast_structured` profile), while exact geometry, frame arithmetic, Telugu-safe presets, safe areas, and collisions are strictly validated by the deterministic core in `VIDEO_ENGINE/stages/motion_planning.py`.
