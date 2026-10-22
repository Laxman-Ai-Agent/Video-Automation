# Main Orchestrator Agent

- **Agent ID:** `main_orchestrator`
- **Stage ID:** `pipeline`
- **Primary Class:** `MainOrchestratorAgent` (alias `MainOrchestratorAdapter`)

## Purpose
Coordinates pipeline execution flow, auto-advancement rules, and error recovery.

## Capabilities
- `orchestration`
- `auto-advance`
- `safe-stop-guard`

## Bound Tools
- `job_queue`
- `step_graph`
- `pipeline_view`
- `memory_service`

## Architecture Notes
This agent operates as a dedicated autonomous component inheriting from `SYSTEM.agents.shared.BaseAgent`.
It possesses isolated private memory (`self.memory`), execution history logging, and connects directly to the central skill catalog and tool registry.
