# A3 — UI & Registry Plan

**Document ID:** A3-UIR-01  
**Date:** 2026-10-16 16:05:00 UTC  
**Repository:** `E:\audio-to-video`  
**Git Branch / HEAD:** `agents-building` / `f6989b17372e3cdb42b4c92ab1783b3122a401ae`  

---

## 1. Registry Architecture & Backend Schema Changes

### 1.1 Category Enum Definition (`backend/agents/contracts.py`)
To enable centralized classification without mutating existing agent IDs, introduce an explicit `AgentCategory` enum in `backend/agents/contracts.py`:

```python
class AgentCategory(str, Enum):
    ORCHESTRATOR = "orchestrator"
    VIDEO_ENGINE_AGENT = "video_engine_agent"
    SYSTEM_SUBAGENT = "system_subagent"
```

### 1.2 Extension of `AgentMetadata`
Add `category` to the `AgentMetadata` dataclass with a safe, backward-compatible default:

```python
@dataclass
class AgentMetadata:
    agent_id: str
    name: str
    version: str = "1.0.0"
    category: AgentCategory = AgentCategory.VIDEO_ENGINE_AGENT  # NEW FIELD
    status: AgentStatus = AgentStatus.IMPLEMENTED
    purpose: str = ""
    capabilities: list[str] = field(default_factory=list)
    inputs_schema: str | None = None
    outputs_schema: str | None = None
    stage_id: str | None = None
    allowed_tools: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    owner: str = "agent-system"
    is_frozen: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value if isinstance(self.status, AgentStatus) else str(self.status)
        d["category"] = self.category.value if isinstance(self.category, AgentCategory) else str(self.category)
        return d
```

### 1.3 Registry Categorization (`backend/agents/registry.py`)
In `backend/agents/registry.py`, initialize metadata entries with their confirmed categories:
- `main_orchestrator`: `category=AgentCategory.ORCHESTRATOR`
- The 12 active video agents (`audio_input` through `final_video_delivery`): `category=AgentCategory.VIDEO_ENGINE_AGENT`
- `motion_template_selection`: `category=AgentCategory.VIDEO_ENGINE_AGENT, status=AgentStatus.DEPRECATED`
- Planned system subagents: documented/staged for registration when implemented in A5/A6.

### 1.4 API Contract & Route Compatibility
- `GET /agents`: returns a list of dictionaries with the new `"category"` key. Existing fields (`agent_id`, `name`, `capabilities`, `status`, etc.) remain completely unchanged.
- `GET /agents/{agent_id}`: includes `"category"`.
- Backward-compatibility: Any client that ignores the new key continues functioning without modification.

---

## 2. Frontend Contract & Type Definitions

### 2.1 TypeScript Interface Extension (`frontend/src/api/agentTypes.ts`)
Update frontend types to match the backend contract:

```typescript
export type AgentCategory = "orchestrator" | "video_engine_agent" | "system_subagent"

export interface AgentMetadata {
  agent_id: string
  name: string
  version: string
  category: AgentCategory
  status: "implemented" | "adapter_only" | "planned" | "blocked" | "deprecated"
  purpose: string
  capabilities: string[]
  inputs_schema?: string | null
  outputs_schema?: string | null
  stage_id?: string | null
  allowed_tools: string[]
  skills: string[]
  owner: string
  is_frozen?: boolean
}
```

---

## 3. UI Display Groups & Navigation Design

### 3.1 Separation of Concerns
The UI must clearly distinguish between three functional roles:
1. **Main Orchestrator**: The top-level coordinator managing concurrency, stage scheduling, and fault recovery. Displayed as a system-level controller card, not as an ordinary pipeline stage.
2. **Video Engine Agents**: The sequential 12-stage video production pipeline (`audio`, `analyzer`, ..., `final`). Displayed as the core production engine.
3. **System Subagents**: Cross-cutting, on-demand background services (`Capability & Skill Finder`, `Skill Factory`). Displayed in a separate section, highlighting their asynchronous, cross-project utility.

### 3.2 Visual Presentation & Layout Specification
When the dedicated agent view is rendered (either at `/agents` or within a dedicated tab on `/dashboard`):

```
+-----------------------------------------------------------------------------------+
|  [Logo] Audio to Video Studio     [Dashboard]  [All Projects]  [Laxman Approval]  |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  MAIN ORCHESTRATOR                                                                |
|  +-----------------------------------------------------------------------------+  |
|  |  Main Orchestrator Agent (v1.0.0)                         [STATUS: ACTIVE]  |  |
|  |  Coordinates pipeline execution flow, checkpoint recovery, and monitoring.  |  |
|  |  Capabilities: [orchestration] [auto-advance] [concurrency-guard]           |  |
|  +-----------------------------------------------------------------------------+  |
|                                                                                   |
|  VIDEO ENGINE AGENTS (12 Active Stages)                                           |
|  +------------------+  +------------------+  +------------------+                 |
|  | 01. Audio Input  |  | 02. Analyzer     |  | 03. Segmentation |   ...           |
|  | Ingests narration|  | Whisper ASR      |  | Semantic scenes  |                 |
|  | [IMPLEMENTED]    |  | [FROZEN]         |  | [FROZEN]         |                 |
|  +------------------+  +------------------+  +------------------+                 |
|                                                                                   |
|  SYSTEM SUBAGENTS (Cross-Project Services)                                        |
|  +---------------------------------------+  +----------------------------------+  |
|  | Capability & Skill Finder Agent       |  | Skill Factory Agent              |  |
|  | Autonomous discovery of motion skills |  | Authors and tests skill packages |  |
|  | [STATUS: PLANNED - Phase A5]          |  | [STATUS: PLANNED - Phase A6]     |  |
|  +---------------------------------------+  +----------------------------------+  |
|                                                                                   |
+-----------------------------------------------------------------------------------+
```

### 3.3 Card Fields & State Handling
For each agent card/row:
- **Card Fields**:
  - Agent Name & Version
  - Category Badge (`ORCHESTRATOR` / `VIDEO ENGINE` / `SYSTEM SUBAGENT`)
  - Status Indicator (`ACTIVE` / `FROZEN` / `DEPRECATED` / `PLANNED`)
  - Stage ID (for Video Engine Agents)
  - Purpose summary
  - Capabilities chips
  - Active skills tags
- **Empty & Error States**:
  - Loading: Skeleton cards with pulse animation matching dark theme (`bg-ink-800/40`).
  - Error: Inline banner with retry button (`Failed to load agent registry`).
  - Filter: If filtering by category yields zero items, show clean informational card: `No agents found in this category`.

### 3.4 Preservation of Navigation Boundaries
- The **Laxman Approval** button (`/approvals`) in `App.tsx` remains completely independent.
- The **Agent Communication Drawer** continues to function using the unified registry query, with optional filtering by `category`.
