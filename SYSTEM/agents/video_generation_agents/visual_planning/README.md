# Visual Planning Agent

- **Agent ID:** `visual_planning`
- **Stage ID:** `planning`
- **Primary Class:** `VisualPlanningAgent` (alias `VisualPlanningAdapter`)

## Purpose
Generates semantic visual concepts, metaphors, visual hierarchies, and scene-by-scene plans.

## Capabilities
- `visual-metaphors`
- `kinetic-typography-design`
- `color-continuity`

## Bound Tools
- `llm_client`
- `llm_gateway`
- `store`

## Architecture Notes
This agent operates as a dedicated autonomous component inheriting from `SYSTEM.agents.shared.BaseAgent`.
It possesses isolated private memory (`self.memory`), execution history logging, and connects directly to the central skill catalog and tool registry.
