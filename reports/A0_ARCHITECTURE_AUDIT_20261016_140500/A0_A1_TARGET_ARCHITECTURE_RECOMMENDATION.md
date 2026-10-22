# A0 Target Architecture Recommendation for A1

**Audit ID:** A0-REC-01  
**Timestamp:** 2026-10-16T14:15:00+05:30  
**Repository Root:** `E:\audio-to-video`  

---

## 1. Guiding Principles & Design Constraints

1. **Safety & Zero Disruption First:** The active project currently passes **121 / 121 tests** across all 11 test suites and renders real MP4 videos headlessly. Physical file moves must be minimized. Never perform mass folder renaming merely to match an abstract diagram.
2. **Logical Taxonomy over Physical Relocation:** Categorize components cleanly in registries, contracts, and API responses rather than moving dozens of deeply-imported files.
3. **Strict Separation of Agent Roles:**
   - **Video Engine Agents:** Pipeline-specific workers executing sequential video transformation.
   - **System Subagents:** Reusable cross-project background capabilities (Skill Finder, Skill Factory).
   - **Main Orchestrator:** Overall task and run coordinator, not a pipeline stage.
4. **Unified Laxman Approval:** Centralize all human approval gates under a unified permission queue and dedicated UI screen without bypassing stage-level deterministic invariants.
5. **Preserve Reusable Canonical Assets:** Retain `resource-library/` as the single canonical registry for fonts, icons, and render components.

---

## 2. Recommended Root Structure for A1

We recommend **keeping the existing stable top-level directories** intact and structuring their internal namespaces logically:

```
E:\audio-to-video\
├── backend/                           # Core Python application
│   ├── agents/                        # Agent framework and definitions
│   │   ├── base_agent.py              # BaseAgent contract
│   │   ├── registry.py                # Central AgentRegistry (enhanced with category enum)
│   │   ├── communication.py           # Inter-agent messaging
│   │   ├── adapters/                  # Video Engine Stage Adapters (12 active + 1 deprecated)
│   │   └── system/                    # [NEW in A5-A6] System Subagents (SkillFinder, SkillFactory)
│   ├── orchestrator.py                # Main Orchestrator (PipelineOrchestrator)
│   ├── approvals/                     # [NEW in A2] Laxman Approval Engine & Request Queue
│   ├── pipeline_state.py              # Canonical state & checkpoint service
│   ├── artifact_contracts.py          # Artifact schema validation & path confinement
│   ├── llm_gateway.py                 # Central model gateway
│   ├── llm_review.py                  # Fail-closed stage review gates
│   ├── skill_registry.py              # Central Skill catalog manager
│   ├── shared_memory.py               # Shared technical memory service
│   ├── evaluation.py                  # Benchmarking & self-learning
│   ├── routes/                        # FastAPI REST API routers (BFF / API layer)
│   └── [stage modules]                # Video engine stages (audio, segmentation, visual, motion, render, qc)
├── frontend/                          # Vite + React 19 UI
│   ├── src/
│   │   ├── api/                       # Typed backend client (client.ts, agentTypes, skillTypes)
│   │   ├── components/                # Reusable UI components & drawers
│   │   ├── pages/                     # Application screens
│   │   │   ├── LaxmanApprovalPage.tsx # [NEW in A2] Central Operator Approval Inbox
│   │   │   ├── AgentsDirectoryPage.tsx# [NEW in A1] Dual-section Directory (Video Engine vs System)
│   │   │   └── ...                    # Existing stage pages
│   │   └── pipeline/                  # Flowchart & auto-advance hooks
├── remotion/                          # Remotion video engine (independent Node.js project)
├── skills/                            # Canonical Markdown skill packages & catalog
├── resource-library/                  # Canonical font/icon/asset library
├── config/                            # Persistent system configuration (eval, llm, memory)
├── projects/                          # Per-project isolated workspaces
└── tests/                             # Pytest test suites (Phases 1-10, A1+)
```

---

## 3. Analysis: Is a `UI/backend` (BFF) Separation Justified?

- **Question:** Should we create a new `UI/backend` directory?
- **Finding:** **No, a separate physical `UI/backend` directory is not recommended.**
- **Rationale:** 
  1. The existing `backend/routes/` directory already serves strictly as the UI-facing API / Backend-for-Frontend (BFF) layer.
  2. The frontend client in `frontend/src/api/client.ts` already calls these routes cleanly over HTTP.
  3. Splitting `backend/` into `UI/backend` and `CORE/backend` would require rewriting imports in 93 Python files, altering all test fixtures, and disrupting Uvicorn startup scripts with zero runtime benefit.
  4. Keeping `backend/routes/` as the defined API boundary maintains complete compatibility.

---

## 4. Agent Taxonomy & Classification Proposal for A1

### 4.1 Enhanced `AgentMetadata` Schema
Add a required `category` field in `backend/agents/contracts.py`:
```python
class AgentCategory(str, Enum):
    VIDEO_ENGINE_AGENT = "video_engine_agent"
    SYSTEM_SUBAGENT = "system_subagent"
    ORCHESTRATOR = "orchestrator"

@dataclass
class AgentMetadata:
    agent_id: str
    name: str
    category: AgentCategory = AgentCategory.VIDEO_ENGINE_AGENT  # NEW FIELD
    version: str = "1.0.0"
    status: AgentStatus = AgentStatus.IMPLEMENTED
    purpose: str = ""
    capabilities: list[str] = field(default_factory=list)
    stage_id: str | None = None
    ...
```

### 4.2 Categorization Mapping

| Category | Agents Included | Invocation Mechanism | UI Presentation |
|---|---|---|---|
| **`orchestrator`** | `main_orchestrator` | Invoked on project run / stage transition | Top-level system status banner; controls pipeline execution |
| **`video_engine_agent`** | 12 active stage adapters + 1 deprecated | Sequential execution along the 12-stage Motion-Only DAG | Pipeline flowchart (`/p/:id`); stage progress cards |
| **`system_subagent`** | `skill_finder`, `skill_factory` (planned) | On-demand background invocation via Orchestrator or user capability request | Dedicated "System Capabilities & Agents" UI tab; **never** in the video flowchart |

---

## 5. Laxman Approval Architectural Design for A2

1. **Core Module:** `backend/approvals/approval_engine.py` (singleton service).
2. **Standardized Request Object (`ApprovalRequest`):**
   - `request_id`: UUIDv4
   - `project_id`: Target project or `"system"`
   - `requesting_agent`: Sender agent ID
   - `action_type`: `"timeline_render"`, `"final_delivery"`, `"skill_promotion"`, `"memory_promotion"`, `"code_execution"`
   - `risk_level`: `"low"`, `"medium"`, `"high"`, `"critical"`
   - `action_summary`: Human-readable description
   - `affected_files`: List of file paths
   - `action_fingerprint`: SHA-256 of candidate payload / timeline
   - `preview_data`: URLs/paths to stills, video previews, or code diffs
   - `status`: `"pending"`, `"approved"`, `"rejected"`, `"changes_requested"`, `"stale"`, `"cancelled"`
   - `reviewer`: Operator identifier
   - `decision_reason`: Mandatory text on rejection or accepted risks
   - `timestamp`: ISO-8601 UTC timestamp
3. **Central Enforcement:**
   - Pre-action guard: Any stage or agent executing a protected side-effect calls `ApprovalEngine.require_approved(request_id)`.
   - Staleness check: If input fingerprint changes, status becomes `"stale"`.
4. **UI Screen:** `frontend/src/pages/LaxmanApprovalPage.tsx` mounted at `/approvals`.

---

## 6. Phased Implementation Roadmap (A1 through A7)

```mermaid
graph LR
    A0["A0: Current Audit (Read-Only)"] --> A1["A1: Taxonomy & Architecture Boundary"]
    A1 --> A2["A2: Laxman Approval Engine & UI"]
    A2 --> A3["A3: Execution Engine Convergence"]
    A3 --> A4["A4: Frontend Orchestrator Integration"]
    A4 --> A5["A5: Capability & Skill Finder Agent"]
    A5 --> A6["A6: Skill Factory Agent"]
    A6 --> A7["A7: Production Hardening & E2E Verification"]
```

- **A1: Architecture & Ownership Finalization** (No breaking changes; classify agents in registry; establish system subagent interfaces).
- **A2: Central Laxman Approval Engine** (Build request queue, authorization guard, and unified operator inbox UI).
- **A3: Execution Convergence** (Migrate pipeline stage triggers to canonical Orchestrator while keeping legacy backward compatibility).
- **A4: Frontend Orchestrator Integration** (Wire frontend flowchart directly to orchestrator monitoring endpoints).
- **A5: Capability & Skill Finder Agent** (Implement internal-first lookup, discovery connectors, license/security auditing).
- **A6: Skill Factory Agent** (Implement skill package synthesis, structural validation, Remotion test render verification).
- **A7: End-to-End Hardening** (Full cross-system test suite, operator runbook update, production readiness sign-off).
