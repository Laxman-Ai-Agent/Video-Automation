# A1 Folder Ownership Map — Physical Paths vs. Logical Boundaries

**Audit ID:** A1-OWN-01  
**Timestamp:** 2026-10-16T14:40:00+05:30  
**Repository Root:** `E:\audio-to-video`  

---

## 1. Domain & Capability Ownership Matrix

| Capability / Domain | Current Canonical Path(s) | Entry Point / Callers | Current Evidence | Proposed Logical Owner | Decision | Proposed Physical Move? | Reason / Migration Risk |
|---|---|---|---|---|---|---|---|
| **API and Route Layer** | `backend/routes/*.py` | `backend/main.py:app.include_router` | 14 router modules registered in `main.py` | `backend/routes/` (API / BFF layer) | `KEEP` | **NO** | Already cleanly serves as UI-facing API layer; moving to `UI/backend` would break 93 import paths and all test fixtures. |
| **JobRunner Legacy Path** | `backend/jobs.py`, `backend/pipeline.py` | `backend/routes/pipeline.py:POST /step/{name}/run` | Background thread pool handling step chains | `backend/jobs.py` -> `backend/orchestrator.py` | `MERGE` / `DEPRECATE` | **NO** | Keep in place; gradually delegate execution to `PipelineOrchestrator` in Phase A3. Deleting now would break existing stage pages. |
| **PipelineOrchestrator** | `backend/orchestrator.py` | `backend/routes/orchestrator.py:POST /run` | Canonical 12-stage DAG runner with Phase 3 checkpoints | `backend/orchestrator.py` | `EXTEND` | **NO** | Canonical engine; extend to handle individual stage stepping so it fully replaces `JobRunner`. |
| **Agent Registry and Adapters** | `backend/agents/registry.py`, `backend/agents/adapters/stage_adapters.py` | `AgentRegistry.get_agent()` | 14 registered adapters implementing `BaseAgent` | `backend/agents/` | `EXTEND` | **NO** | Add `category` enum (`video_engine_agent`, `system_subagent`, `orchestrator`) in metadata without moving files. |
| **Main Orchestrator** | `backend/agents/adapters/stage_adapters.py:MainOrchestratorAdapter` | `AgentRegistry.get_agent("main_orchestrator")` | Registered as an agent adapter in `registry.py` | `backend/orchestrator.py` | `REFACTOR` | **NO** | Reclassify category from `video_engine_agent` to `orchestrator` in registry metadata. |
| **Video Engine Agents** | `backend/agents/adapters/stage_adapters.py` (12 active + 1 deprecated) | Invoked by `PipelineOrchestrator` | 12 stage adapters mapping to active Motion-Only DAG | `backend/agents/adapters/` | `KEEP` | **NO** | Working cleanly; deep relative imports (`from ... import`) make physical relocation dangerous. |
| **System Subagents** | Planned: `skill_finder`, `skill_factory` | None currently in code | Documented in Phase 4 plans and A0 audit | `backend/agents/system/` | `MISSING` | **NEW PATH in A5-A6** | Place new system subagents in `backend/agents/system/` when implemented; do not touch video stage adapters. |
| **Skill Registry & Catalog** | `backend/skill_registry.py`, `skills/catalog.json` | `get_skill_registry()` | Atomic JSON catalog with thread-lock & security audit | `backend/skill_registry.py` | `KEEP` | **NO** | Authoritative single source of truth for skills; keep canonical roots intact. |
| **Skill Staging & Quarantine** | `skills/staging/` | `SkillRegistry.stage_external_candidate()` | Unreviewed candidate skills staged under quarantine | `skills/staging/` | `KEEP` | **NO** | Essential security quarantine area; keep intact. |
| **LLM Gateway & Review** | `backend/llm_gateway.py`, `backend/llm_review.py` | `call_llm_gateway()`, `evaluate_stage_review()` | Multi-provider client with retry, cost tracking, review rubrics | `backend/llm_gateway.py` | `KEEP` | **NO** | Canonical model gateway and fail-closed quality gate; keep intact. |
| **Shared State & Checkpoints** | `backend/pipeline_state.py`, `backend/artifact_contracts.py` | `PipelineStateService` | Atomic checkpoint persistence & path traversal guards | `backend/pipeline_state.py` | `KEEP` | **NO** | Canonical state and contract enforcement; keep intact. |
| **Human Approvals** | `backend/timeline_approval.py`, `backend/final_qc.py` | `timeline_gate.require_approved()`, `final_qc.gate()` | Fragmented stage files for timeline & QC review | `backend/approvals/` | `EXTEND` / `MERGE` | **NEW SUBMODULE in A2** | Introduce unified `backend/approvals/approval_engine.py` with PIN verification; wrap existing stage checks. |
| **UI Agent Display** | `frontend/src/components/AgentCommunicationDrawer.tsx` | Embedded in `frontend/src/pipeline/PipelinePage.tsx` | Real-time agent messaging drawer with filters | `frontend/src/components/` | `EXTEND` | **NO** | Extend to support separate views for Video Engine Agents vs System Subagents in Phase A1/A4. |
| **UI Pipeline Pages** | `frontend/src/pipeline/PipelinePage.tsx`, `frontend/src/pages/*.tsx` | React Router in `frontend/src/App.tsx` | 12 stage detail pages, flowchart canvas | `frontend/src/pages/` | `KEEP` / `EXTEND` | **NO** | Working React 19 pages; keep in place and connect to orchestrator in A4. |
| **Remotion / Render Adapter** | `backend/render.py`, `backend/render_video.py` | `render_video.run()` | Remotion headless Chrome CLI subprocess launcher | `backend/render.py` | `KEEP` | **NO** | Working headless renderer using host Chrome; keep in place. |
| **FFmpeg / Render Tools** | `backend/media_probe.py`, `backend/audio_utils.py` | Subprocess invocations of `ffmpeg` / `ffprobe` | ffprobe media stream analysis & WAV downsampling | `backend/media_probe.py` | `KEEP` | **NO** | Lightweight utility wrappers; keep in place. |
| **Resource Library** | `resource-library/`, `backend/resource_library.py` | `resource_library.registry()` | Static SVG icons, Telugu fonts, license texts, render bundle | `resource-library/` | `KEEP` | **NO** | Canonical resource catalog; do not move or duplicate. |
| **Project Artifacts / Storage** | `projects/<pid>/` | `backend/store.py` | Per-project isolated runtime directories | `projects/` | `KEEP` | **NO** | Strict project isolation verified across all phases; keep in place. |
| **Logging & Observability** | `projects/<pid>/communications.jsonl`, `config/llm_usage.json` | `communication.publish_message()`, `llm_usage.record()` | Durable JSONL agent messages & token usage tracker | `backend/agents/communication.py` | `KEEP` | **NO** | Working truthful observability; keep in place. |
| **Tests & Fixtures** | `tests/*.py` | Pytest CLI (`pytest tests/`) | 68 test files covering all 10 phases (121 passing tests) | `tests/` | `KEEP` | **NO** | Deep test dependencies assume `from backend import ...`; moving would break tests. |
| **Legacy Dashboard** | `dashboard/` | None (removed 2026-10-13) | 175 MB of orphaned node_modules and old `public/status.json` | None (Orphaned) | `REMOVE-CANDIDATE` | **NO (in A1)** | Candidate for later approved deletion in Phase A7. Zero code depends on it. |

---

## 2. Decision on Proposed Physical Folder Moves

### Question: Should we move files into `SYSTEM/`, `UI/`, or `VIDEO_ENGINE/` root directories?
- **Decision:** **NO PHYSICAL MOVE.**
- **Rationale:**
  1. **Zero Runtime Gain:** Moving files changes only filesystem paths; it does not improve memory, performance, or separation of concerns.
  2. **Severe Import Breakage:** `backend/` modules use extensive relative imports (`from ... import`, `from . import`). Moving files would break hundreds of import statements across 93 backend files and 68 test files.
  3. **Build & Tooling Friction:** Vite (`frontend/`), Remotion (`remotion/`), and Pytest (`tests/`) are pre-configured to look at current package roots. Moving files introduces configuration drift.
  4. **Alternative Selected:** Implement **logical categorization** (via `category` in `AgentMetadata` and dedicated subpackages like `backend/approvals/` and `backend/agents/system/`) within the stable existing directory structure.
