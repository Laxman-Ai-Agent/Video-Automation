# Agent Source-to-Target Mapping Report

**Date:** 2026-10-17  
**Repository:** `E:\audio-to-video`  
**Scope:** Complete component mapping from baseline monolithic structure to dedicated modular architecture.

---

## 1. Video Generation Agents Mapping (14/14)

All 14 logical video generation agents have been extracted from `SYSTEM/agents/video_generation_agents/stage_adapters.py` into dedicated modules.

| Agent ID | Target Module Directory | Dedicated Agent Class | Facade Alias (`stage_adapters.py`) | Stage ID | Status |
|:---|:---|:---|:---|:---|:---|
| `main_orchestrator` | `video_generation_agents/main_orchestrator/` | `MainOrchestratorAgent` | `MainOrchestratorAdapter` | `pipeline` | IMPLEMENTED |
| `audio_input` | `video_generation_agents/audio_input/` | `AudioInputAgent` | `AudioInputAdapter` | `audio` | IMPLEMENTED |
| `audio_analyzer` | `video_generation_agents/audio_analyzer/` | `AudioAnalyzerAgent` | `AudioAnalyzerAdapter` | `analyzer` | IMPLEMENTED |
| `scene_segmentation` | `video_generation_agents/scene_segmentation/` | `SceneSegmentationAgent` | `SceneSegmentationAdapter` | `segmentation` | IMPLEMENTED |
| `visual_planning` | `video_generation_agents/visual_planning/` | `VisualPlanningAgent` | `VisualPlanningAdapter` | `planning` | IMPLEMENTED |
| `motion_planning` | `video_generation_agents/motion_planning/` | `MotionPlanningAgent` | `MotionPlanningAdapter` | `motion_plan` | IMPLEMENTED |
| `motion_template_selection`| `video_generation_agents/motion_template_selection/`| `MotionTemplateSelectionAgent`| `MotionTemplateSelectionAdapter`| `motion_template`| DEPRECATED |
| `motion_animation` | `video_generation_agents/motion_animation/` | `MotionAnimationAgent` | `MotionAnimationAdapter` | `motion_gen` | IMPLEMENTED |
| `motion_timeline_validation`| `video_generation_agents/motion_timeline_validation/`| `MotionValidationAgent` | `MotionValidationAdapter` | `motion_validation`| IMPLEMENTED |
| `timeline_build` | `video_generation_agents/timeline_build/` | `TimelineBuildAgent` | `TimelineBuildAdapter` | `timeline` | IMPLEMENTED |
| `timeline_approval` | `video_generation_agents/timeline_approval/` | `TimelineApprovalAgent` | `TimelineApprovalAdapter` | `approval` | IMPLEMENTED |
| `render_video` | `video_generation_agents/render_video/` | `RenderVideoAgent` | `RenderVideoAdapter` | `render` | IMPLEMENTED |
| `final_qc` | `video_generation_agents/final_qc/` | `FinalQcAgent` | `FinalQcAdapter` | `qc` | IMPLEMENTED |
| `final_video_delivery`| `video_generation_agents/final_video_delivery/`| `FinalVideoDeliveryAgent` | `FinalVideoDeliveryAdapter` | `final` | IMPLEMENTED |

---

## 2. System Orchestrator and System Subagents Mapping

| Agent ID | Target Module Directory | Agent Class | Category | Primary Purpose |
|:---|:---|:---|:---|:---|
| `main_architecture_agent` | `SYSTEM/agents/main_architecture_agent/` | `MainArchitectureAgent` | `ORCHESTRATOR` | System-level coordination, goal planning, task decomposition, agent delegation. |
| `capability_finder` | `SYSTEM/agents/system_agents/capability_finder/` | `CapabilityFinderAgent` | `SYSTEM_SUBAGENT` | Discovers agents, skills, and tools matching queries; inspects system prerequisites. |
| `skill_factory` | `SYSTEM/agents/system_agents/skill_factory/` | `SkillFactoryAgent` | `SYSTEM_SUBAGENT` | Generates candidate skills, executes static security/leakage audits, stages approved items. |

---

## 3. Shared Infrastructure & Registry Mapping

| Subsystem | Source Component | Target Architecture Location | Primary Role |
|:---|:---|:---|:---|
| **Memory Scoping** | New Component | `SYSTEM/memory/memory_scoping.py` | `ScopedMemoryManager` enforcing strict boundary isolation across `agent`, `project`, `global` scopes. |
| **Memory Service** | Facade | `SYSTEM/memory/memory_service.py` | Unified access interface for scoped agent storage. |
| **Agent Memory Adapter** | New Component | `SYSTEM/agents/shared/memory_adapter.py` | Binds `self.memory` to `self.agent_id` for transparent agent-isolated storage. |
| **History Service** | New Component | `SYSTEM/history/history_service.py` | Durable recording and querying of executions, decisions, and security audits. |
| **Execution History** | New Schema | `SYSTEM/history/execution_history.py` | `ExecutionRecord` schema tracking runtime duration, status, inputs, and outputs. |
| **Decision History** | New Schema | `SYSTEM/history/decision_history.py` | `DecisionRecord` schema capturing rationale, chosen option, alternatives, and parameters. |
| **Audit History** | New Schema | `SYSTEM/history/audit_history.py` | `AuditRecord` schema recording immutable security and compliance check events. |
| **Tool Registry** | New Component | `SYSTEM/registries/tool_registry.py` | Central `ToolRegistry` managing 9 system tools, permissions, and discovery. |
| **Agent Registry** | Updated | `SYSTEM/registries/agent_registry.py` | Authoritative singleton registry managing all 17 agents with zero-breakage backward compatibility. |
| **Skills Domains** | New Layout | `SYSTEM/skills/<domain>/` | 10 domain directories with `README.md` descriptors. |

---

## 4. Invariant Preservation Guarantee

Every dedicated agent directory contains:
- `agent.py`: Agent logic subclassing `BaseAgent`.
- `__init__.py`: Clean export of agent class.
- `README.md`: Technical documentation, contracts, capabilities, and dependencies.
- `config/agent_config.json`: Runtime configuration parameters.
- `memory/memory_policy.json`: Scoping and retention policy.
- `tests/test_agent.py`: Standalone package unit test.
- `prompts/`: Template directory for system prompt variants.
- `history/`: Dedicated directory for agent-specific execution history.
- `tools/`: Dedicated directory for agent tool specifications.
