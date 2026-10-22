# Main Architecture Agent (System Coordinator)

- **Agent ID:** `main_architecture_agent`
- **Category:** `ORCHESTRATOR`
- **Primary Class:** `MainArchitectureAgent`

## System Purpose
The Main Architecture Agent is the system-level coordinator for the multi-agent architecture.
It parses high-level user requirements, decomposes them into structured subtasks with clear dependency ordering, discovers capabilities across agents, skills, and tools, and delegates execution to specialized system or video-generation subagents.

## Core Responsibilities
1. **Goal Analysis & Decomposition:** Decomposes complex system objectives into ordered `SubTask` records.
2. **Capability & Resource Discovery:** Dynamically queries `AgentRegistry`, `SkillRegistry`, and `ToolRegistry`.
3. **Delegation & Task Supervision:** Dispatches requests to target subagents and collects structured execution results.
4. **Policy & Permission Enforcement:** Enforces execution safety and Laxman approval gates.
5. **Durable Coordination History:** Logs all architectural decisions into `SYSTEM/history/decisions.jsonl`.

## Architectural Boundary
The Main Architecture Agent does **NOT** duplicate or compete with `VIDEO_ENGINE.pipeline.orchestrator.PipelineOrchestrator`.
`PipelineOrchestrator` remains the sole canonical execution engine governing video stage ordering, cancellation, checkpoints, retries, and render runs. When video generation is needed, the Main Architecture Agent delegates the pipeline execution to `PipelineOrchestrator` via `main_orchestrator`.
