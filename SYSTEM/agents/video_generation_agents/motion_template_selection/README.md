# Motion Template Selection Agent (Internal Helper)

- **Agent ID:** `motion_template_selection`
- **Stage ID:** `motion_template`
- **Primary Class:** `MotionTemplateSelectionAgent` (alias `MotionTemplateSelectionAdapter`)

## Purpose
Evaluates reusable motion graphic templates and presets for scene suitability.

## Capabilities
- `template-search`
- `preset-evaluation`
- `metadata-scoring`

## Bound Tools
- `template_registry`
- `preset_library`

## Architecture Notes
This agent operates as a dedicated autonomous component inheriting from `SYSTEM.agents.shared.BaseAgent`.
It possesses isolated private memory (`self.memory`), execution history logging, and connects directly to the central skill catalog and tool registry.
