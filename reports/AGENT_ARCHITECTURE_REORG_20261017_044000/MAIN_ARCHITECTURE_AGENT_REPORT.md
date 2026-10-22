# Main Architecture Agent & System Subagents Report

**Date:** 2026-10-17  
**Repository:** `E:\audio-to-video`  
**Components:** `MainArchitectureAgent`, `CapabilityFinderAgent`, `SkillFactoryAgent`

---

## 1. Architecture & Role of Main Architecture Agent

The `MainArchitectureAgent` serves as the system-level coordinator for high-level requirement analysis, goal decomposition, agent delegation, and governance.

- **Class:** `SYSTEM.agents.main_architecture_agent.agent.MainArchitectureAgent`
- **Category:** `AgentCategory.ORCHESTRATOR`
- **Capabilities:** `["goal_planning", "task_decomposition", "agent_delegation", "system_governance"]`
- **Allowed Tools:** `agent_registry`, `tool_registry`, `skill_registry`, `memory_service`, `history_service`

### Strict Separation of Concerns: Architecture Coordinator vs. Video Engine Pipeline

> [!IMPORTANT]
> `MainArchitectureAgent` does **NOT** replace, duplicate, or compete with `VIDEO_ENGINE.pipeline.orchestrator.PipelineOrchestrator`.

1. **`MainArchitectureAgent` (System Level):**
   - Operates above individual execution pipelines.
   - Decomposes high-level natural language user goals into structured subtasks.
   - Discovers appropriate agents, skills, and tools across the entire system.
   - Delegates subtasks to specialized agents (e.g., delegating video rendering tasks to `main_orchestrator`).
   - Records architectural decisions and governance audits in `HistoryService`.

2. **`PipelineOrchestrator` / `main_orchestrator` (Video Engine Level):**
   - The canonical deterministic engine for video pipeline execution.
   - Sequences media stages (`audio` $\rightarrow$ `analyzer` $\rightarrow$ `segmentation` $\rightarrow$ `planning` $\rightarrow$ `motion_plan` $\rightarrow$ `motion_gen` $\rightarrow$ `motion_validation` $\rightarrow$ `timeline` $\rightarrow$ `approval` $\rightarrow$ `render` $\rightarrow$ `qc` $\rightarrow$ `final`).
   - Enforces the 12 technical motion rules, human approval gates, Remotion rendering, and file delivery.

---

## 2. Core Actions of Main Architecture Agent

### 1. `action="discover"`
Queries the central registries and returns an inventory of all active agents, approved skills, and available tools.
```python
result = main_arch_agent.execute(project_dir, AgentRequest(
    project_id="system",
    agent_id="main_architecture_agent",
    stage_id="system",
    parameters={"action": "discover"}
))
# Output: Discovered 17 agents, 6 approved skills, and 9 tools.
```

### 2. `action="plan"`
Decomposes an abstract goal (e.g., `"Render video from narration audio"`) into structured `SubTask` records with dependencies and agent assignments.
- For video generation goals: schedules `capability_finder` followed by `main_orchestrator`.
- For skill creation goals: schedules `capability_finder` followed by `skill_factory`.
- Records each decomposition decision in `HistoryService` (`DecisionRecord`).

### 3. `action="delegate"`
Hands off execution of a specific subtask to a registered target agent, wraps the request with execution history tracking, and records the delegation rationale.

### 4. `action="status"`
Queries recent executions, decisions, and system health status via `HistoryService`.

---

## 3. System Subagents Breakdown

### 1. Capability Finder Agent (`capability_finder`)
- **Module:** `SYSTEM/agents/system_agents/capability_finder/`
- **Class:** `CapabilityFinderAgent`
- **Category:** `AgentCategory.SYSTEM_SUBAGENT`
- **Role:** Discovers matching agents and skills based on search queries and evaluates environmental prerequisites (FFmpeg availability, FFprobe availability, Faster-Whisper model checkpoints).

### 2. Skill Factory Agent (`skill_factory`)
- **Module:** `SYSTEM/agents/system_agents/skill_factory/`
- **Class:** `SkillFactoryAgent`
- **Category:** `AgentCategory.SYSTEM_SUBAGENT`
- **Role:** Synthesizes new candidate skills, audits content against prompt injection patterns and dangerous shell commands, stages validated candidates into `SYSTEM/skills/staging/`, and registers approved skills in `SkillRegistry`.

---

## 4. Verification Evidence

- `test_main_architecture_agent_metadata`: **PASSED**
- `test_discovery_action`: **PASSED** (17 agents, 6 skills, 9 tools)
- `test_plan_action_video_goal`: **PASSED** (2 structured subtasks)
- `test_plan_action_skill_goal`: **PASSED** (2 structured subtasks)
- `test_capability_finder_discovery`: **PASSED**
- `test_skill_factory_audit_safe`: **PASSED**
- `test_skill_factory_audit_blocks_prompt_injection`: **PASSED**
- `test_skill_factory_audit_blocks_dangerous_execution`: **PASSED**
