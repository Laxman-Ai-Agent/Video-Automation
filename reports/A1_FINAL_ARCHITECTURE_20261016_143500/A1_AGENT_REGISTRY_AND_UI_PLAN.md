# A1 Agent Registry & UI Classification Plan

**Audit ID:** A1-REG-PLAN-01  
**Timestamp:** 2026-10-16T14:40:00+05:30  
**Repository Root:** `E:\audio-to-video`  

---

## 1. Tripartite Agent Taxonomy

To eliminate confusion between pipeline workers, system-level capabilities, and pipeline coordinators, the system establishes three explicit, non-overlapping categories:

1. **`orchestrator`**: Coordinates pipeline execution flow, concurrency serialization, stage eligibility, and error recovery. The orchestrator is a coordinator, **never** a video pipeline stage.
2. **`video_engine_agent`**: Autonomous agents responsible for discrete stages in the active Motion-Only video transformation pipeline (from Audio Input through Final Delivery).
3. **`system_subagent`**: Reusable project-wide background capabilities (initially Capability & Skill Finder and Skill Factory) invoked on-demand by the user or orchestrator. They are **never** placed into the sequential 12-stage video pipeline.

---

## 2. Enhanced Registry Schema Specification

To support this taxonomy without breaking any existing contracts or consumers, we propose an additive enhancement to `AgentMetadata` in `backend/agents/contracts.py`:

```python
from enum import Enum
from dataclasses import dataclass, field
from typing import Any

class AgentCategory(str, Enum):
    ORCHESTRATOR = "orchestrator"
    VIDEO_ENGINE_AGENT = "video_engine_agent"
    SYSTEM_SUBAGENT = "system_subagent"

class AgentStatus(str, Enum):
    IMPLEMENTED = "implemented"
    ADAPTER_ONLY = "adapter_only"
    PLANNED = "planned"
    BLOCKED = "blocked"
    DEPRECATED = "deprecated"

@dataclass
class AgentMetadata:
    agent_id: str                                  # Stable, unchanging identifier (e.g. "audio_input")
    name: str                                      # Human-readable title
    category: AgentCategory = AgentCategory.VIDEO_ENGINE_AGENT  # ADDITIVE FIELD (defaults to video_engine_agent)
    version: str = "1.0.0"
    status: AgentStatus = AgentStatus.IMPLEMENTED
    purpose: str = ""
    capabilities: list[str] = field(default_factory=list)
    inputs_schema: str | None = None
    outputs_schema: str | None = None
    stage_id: str | None = None                    # None for system_subagents & orchestrator
    allowed_tools: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    owner: str = "agent-system"
    is_frozen: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
```

---

## 3. Authoritative Agent Inventory & Mapping

| Stable Agent ID | Display Name | Category | Stage ID | Current Status | Adapter Class / Implementation Path | UI Section |
|---|---|---|---|---|---|---|
| `main_orchestrator` | Main Orchestrator Agent | `orchestrator` | `pipeline` | `implemented` | `backend/agents/adapters/stage_adapters.py:MainOrchestratorAdapter` | System Orchestration Card / Header |
| `audio_input` | Audio Input Agent | `video_engine_agent` | `audio` | `implemented` | `backend/agents/adapters/stage_adapters.py:AudioInputAdapter` | Video Engine: Stage 1 |
| `audio_analyzer` | Audio Analyzer Agent | `video_engine_agent` | `analyzer` | `implemented` [FROZEN] | `backend/agents/adapters/stage_adapters.py:AudioAnalyzerAdapter` | Video Engine: Stage 2 (Frozen) |
| `scene_segmentation` | Scene Segmentation Agent | `video_engine_agent` | `segmentation` | `implemented` [FROZEN] | `backend/agents/adapters/stage_adapters.py:SceneSegmentationAdapter` | Video Engine: Stage 3 (Frozen) |
| `visual_planning` | Visual Planning Agent | `video_engine_agent` | `planning` | `implemented` | `backend/agents/adapters/stage_adapters.py:VisualPlanningAdapter` | Video Engine: Stage 4 |
| `motion_planning` | Motion Planning Agent | `video_engine_agent` | `motion_plan` | `implemented` | `backend/agents/adapters/stage_adapters.py:MotionPlanningAdapter` | Video Engine: Stage 5 |
| `motion_template_selection` | Motion Template Selection Agent | `video_engine_agent` | `motion_template` | `deprecated` | `backend/agents/adapters/stage_adapters.py:MotionTemplateSelectionAdapter` | Video Engine: Deprecated |
| `motion_animation` | Motion Animation Agent | `video_engine_agent` | `motion_gen` | `implemented` | `backend/agents/adapters/stage_adapters.py:MotionAnimationAdapter` | Video Engine: Stage 6 |
| `motion_timeline_validation` | Motion & Timeline Validation Agent | `video_engine_agent` | `motion_validation` | `implemented` | `backend/agents/adapters/stage_adapters.py:MotionValidationAdapter` | Video Engine: Stage 7 |
| `timeline_build` | Timeline Build Agent | `video_engine_agent` | `timeline` | `implemented` | `backend/agents/adapters/stage_adapters.py:TimelineBuildAdapter` | Video Engine: Stage 8 |
| `timeline_approval` | Timeline Approval Agent | `video_engine_agent` | `approval` | `implemented` (Human Gate) | `backend/agents/adapters/stage_adapters.py:TimelineApprovalAdapter` | Video Engine: Stage 9 (Human Gate) |
| `render_video` | Render Video Agent | `video_engine_agent` | `render` | `implemented` | `backend/agents/adapters/stage_adapters.py:RenderVideoAdapter` | Video Engine: Stage 10 |
| `final_qc` | Final QC Agent | `video_engine_agent` | `qc` | `implemented` (Dual Gate) | `backend/agents/adapters/stage_adapters.py:FinalQcAdapter` | Video Engine: Stage 11 (Dual Gate) |
| `final_video_delivery` | Final Video Delivery Agent | `video_engine_agent` | `final` | `implemented` | `backend/agents/adapters/stage_adapters.py:FinalVideoDeliveryAdapter` | Video Engine: Stage 12 |
| `skill_finder` | Capability & Skill Finder Agent | `system_subagent` | `None` | `planned` (Phase A5) | `backend/agents/system/skill_finder.py` (Planned) | System Subagents: Capabilities Tab |
| `skill_factory` | Skill Factory Agent | `system_subagent` | `None` | `planned` (Phase A6) | `backend/agents/system/skill_factory.py` (Planned) | System Subagents: Capabilities Tab |

---

## 4. UI Presentation & Navigation Plan

### 4.1 Navigation Hierarchy
Within `frontend/src/App.tsx`, we propose adding an **Agents & Capabilities** entry point:
- Route: `/agents`
- Component: `frontend/src/pages/AgentsDirectoryPage.tsx`
- Layout: Reuses the existing Dark World header (`LayoutDashboard`, `Plus`, `FolderOpen`, `Library`, plus a new `Bot` icon for Agents).

### 4.2 Tabbed / Sectional Interface
The `/agents` page will render two visibly distinct tabs:
1. **Tab 1: Video Engine Pipeline Agents**
   - Displays all 12 active stage adapters in pipeline execution order.
   - Shows active stage ID, current status (`implemented`, `frozen`, `deprecated`), associated skills, and allowed tools.
   - Includes a link to each stage's dedicated pipeline step page (`/p/:id/step/:stage`).
2. **Tab 2: Reusable System Subagents**
   - Displays project-wide capability subagents (`skill_finder`, `skill_factory`).
   - Visibly labels them as `PLANNED` until implemented in Phases A5 and A6.
   - When implemented, provides an on-demand interface to trigger capability scans or author skill packages without running the video pipeline.
3. **Top Status Card: System Orchestrator**
   - Displays the `main_orchestrator` status, runtime capabilities (Node, Chrome, FFmpeg), and project execution locks in a distinct banner above the tabs.

---

## 5. Backward Compatibility & Test Safety

- **Default Parameter Value:** Setting `category: AgentCategory = AgentCategory.VIDEO_ENGINE_AGENT` ensures that existing code calling `AgentMetadata(...)` without `category` continues to compile and execute without modification.
- **REST API Filter:** `GET /agents?category=video_engine_agent` allows filtered queries while returning all agents when no category parameter is passed, maintaining 100% backward compatibility for existing client callers.
- **Contract Tests:** `frontend/tests/contract.test.ts` and `tests/test_agent_routes.py` will continue to pass without modifications.
