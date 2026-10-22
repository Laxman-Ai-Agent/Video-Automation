# Main Architecture Agent (System Coordinator)

- **Agent ID:** `main_architecture_agent`
- **Category:** `ORCHESTRATOR`
- **Primary Class:** `MainArchitectureAgent`

## System Purpose
The Main Architecture Agent is the system-level coordinator for the multi-agent architecture.
It parses high-level user requirements, decomposes them into structured subtasks with clear dependency ordering, discovers capabilities across agents, skills, and tools, and delegates execution to registered agents: its own six subagents and, when a domain project is connected, that project's agents.

## Main Architecture Agent vs Main Orchestrator
These are two different agents with two different jobs. They are not interchangeable.

| | Main Architecture Agent | Main Orchestrator |
|---|---|---|
| Id | `main_architecture_agent` | `main_orchestrator` |
| Belongs to | the Agent Building System (generic) | the video project (`SYSTEM/agents/video_generation_agents/main_orchestrator`) |
| Job | coordinates any goal: decomposes it, discovers capabilities, routes tasks to registered agents, enforces policy | executes the **video pipeline**: stage order, auto-advance, safe stop, error recovery |
| Present when | always | only while the video project is connected (it registers the agent through `SYSTEM/core/integrations.py`) |
| Execution engine | none: it never executes a domain pipeline itself | `VIDEO_ENGINE.pipeline.orchestrator.PipelineOrchestrator` |

The Main Architecture Agent reaches the Main Orchestrator only through `AgentRegistry`, like any other agent; it never imports the video project.

## Core Responsibilities
1. **Goal Analysis & Decomposition:** Decomposes complex system objectives into ordered `SubTask` records.
2. **Capability & Resource Discovery:** Dynamically queries `AgentRegistry`, `SkillRegistry`, and `ToolRegistry`.
3. **Delegation & Task Supervision:** Dispatches requests to target subagents and collects structured execution results.
4. **Policy & Permission Enforcement:** Enforces execution safety and Laxman approval gates.
5. **Durable Coordination History:** Logs all architectural decisions into `SYSTEM/history/decisions.jsonl`.

## Architectural Boundary
The Main Architecture Agent does **NOT** execute a domain project's pipeline, and does not duplicate or compete with the project's own execution engine.
In the video project, `VIDEO_ENGINE.pipeline.orchestrator.PipelineOrchestrator` remains the sole canonical execution engine governing video stage ordering, cancellation, checkpoints, retries, and render runs, and the `main_orchestrator` agent drives it. When a goal needs that pipeline and the video project is connected, the Main Architecture Agent delegates it to `main_orchestrator` through `AgentRegistry`. With no domain project connected there is no such agent and nothing to delegate to.
