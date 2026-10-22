# A4 Shared Systems Inventory

**Date:** October 16, 2026  
**Repository:** `E:\audio-to-video`  
**Phase:** A4 — Shared Infrastructure Integration Planning  
**Status:** COMPLETE  

---

## 1. Inventory Overview

This inventory audits every shared subsystem across `backend/`, `frontend/`, `config/`, and `projects/`, identifying its authoritative canonical owner, actual source paths, active callers, backing storage contracts, overlap with older mechanisms, and recommended convergence action.

---

## 2. Comprehensive Shared Systems Inventory Table

| Responsibility | Canonical Owner | Actual Paths | Callers | Data Store / Contracts | Status / Evidence | Overlap / Duplication | Recommended Action | Risk |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Pipeline Orchestration & Stage Dispatch** | `PipelineOrchestrator` | `backend/orchestrator.py` | `backend/routes/orchestrator.py`, `tests/test_orchestrator_*.py`, `test_e2e_production_readiness.py` | `projects/{pid}/.pipeline_state.json`, `.checkpoints/`, `RunRecord` | `verified` | Overlaps with `backend/jobs.py` + `backend/pipeline.py:execute()`. | Maintain as canonical orchestrator. Convert legacy endpoints into wrappers dispatching here. | Low |
| **2. Legacy Job Runner & Step Chains** | `JobRunner` (Adapter Role) | `backend/jobs.py`, `backend/pipeline.py` | `backend/routes/pipeline.py`, `backend/routes/review.py`, `backend/routes/run.py`, legacy tests | In-memory `_jobs`, `projects/{pid}/.build_state.json`, `projects/{pid}/info.json` | `verified` | Dual execution engine running parallel threadpool. | Retain as thin backward-compatibility adapter; delegate stage execution to orchestrator. | Med |
| **3. Agent Metadata Registry & Serialization** | `AgentRegistry` | `backend/agents/registry.py`, `backend/agents/contracts.py` | `backend/routes/agents.py`, `backend/orchestrator.py`, `frontend/src/pages/AgentsPage.tsx` | In-memory authoritative registry of 14 agents; JSON schema via `to_dict()`. | `verified` | No duplication; single authoritative source. | Retain as canonical registry. Ensure frontend tolerates both categorized and raw responses. | Low |
| **4. Durable Agent Communication & Handoffs** | `communication` module | `backend/agents/communication.py` | `backend/orchestrator.py`, `backend/jobs.py`, `backend/routes/agents.py` | `projects/{pid}/agent-communications/communications.jsonl`, in-memory SSE queue | `verified` | No duplication; authentic lifecycle and handoff stream. | Retain as canonical communication and audit stream. | Low |
| **5. Stage State, Checkpoints & Resume** | `PipelineStateStore` | `backend/pipeline_state.py`, `backend/artifact_contracts.py` | `backend/orchestrator.py`, `backend/routes/orchestrator.py`, `tests/test_pipeline_state_*.py` | `projects/{pid}/.pipeline_state.json`, `projects/{pid}/.checkpoints/{stage}_cp.json` | `verified` | Overlaps with legacy `info.json` ("status") and `.build_state.json`. | Keep `pipeline_state.py` as canonical stage state. Sync high-level status to `info.json`. | Low |
| **6. Task Queue & Concurrency Serialization** | `orchestrator._PROJECT_LOCKS` & `jobs.RENDER_LOCK` | `backend/orchestrator.py`, `backend/jobs.py` | `backend/routes/orchestrator.py`, `backend/routes/pipeline.py` | In-memory `threading.Lock` per project; atomic disk state updates. | `verified` | Three independent project lock dictionaries exist across modules. | Unify project lock access in a single shared helper to prevent dual-engine race conditions. | Med |
| **7. LLM Gateway, Routing & Review Gates** | `LlmGateway` & `LlmReview` | `backend/llm_gateway.py`, `backend/llm_review.py` | `backend/motion_animation.py`, `backend/orchestrator.py`, `tests/test_llm_gateway.py` | `config/llm_settings.json`, `projects/{pid}/reviews/{stage}_review.json` | `partially_verified` | `analysis_autofix.py` and `promptgen.py` invoke raw `llm_client.generate_text()` directly. | Migrate direct callers to `llm_gateway.execute()`. Keep review gate non-negotiable. | Low |
| **8. Approval Engine & PIN Authorization** | `LaxmanApprovalEngine` | `backend/approvals/approval_engine.py`, `backend/approvals/pin_service.py` | `backend/routes/approvals.py`, `backend/approvals/adapters/`, `frontend/src/pages/LaxmanApprovalPage.tsx` | `config/approvals_queue.json`, `config/approvals_audit.jsonl`, `config/laxman_pin.json` | `verified` | Distinct from LLM review; protects side-effect boundaries. | Retain as canonical human authorization authority. Enforce guards at render and delivery. | Low |
| **9. Central Skill Catalog & Shared Memory** | `SkillRegistry` & `SharedMemory` | `backend/skill_registry.py`, `backend/shared_memory.py` | `backend/routes/skills.py`, `backend/routes/memory.py`, `backend/motion_animation.py` | `skills/catalog.json`, `skills/staging/`, `config/shared_memory.json` | `verified` | No competing skill catalog. Clear isolation from project-specific code. | Retain as canonical catalog and verified memory. Do not implement external fetchers in A4. | Low |
| **10. Observability, Logs & Telemetry** | `LlmUsageMonitor` & `communication` | `backend/llm_usage.py`, `backend/agents/communication.py` | `backend/routes/llm.py`, `backend/llm_gateway.py`, `frontend/src/pages/LlmUsagePage.tsx` | `config/llm_usage.json`, `~/.claude/metrics/costs.jsonl`, `projects/{pid}/logs/` | `verified` | Logs split between raw `log.txt`, `communications.jsonl`, and `llm_usage.json`. | Establish unified correlation schema (`run_id`, `correlation_id`, `request_id`). | Low |
| **11. Frontend API Client & Route Contracts** | `api` client & TypeScript types | `frontend/src/api/client.ts`, `frontend/src/api/agentTypes.ts` | All frontend pages (`PipelinePage`, `AgentsPage`, `LaxmanApprovalPage`, etc.) | TypeScript interfaces, Vitest contract snapshots in `frontend/tests/contract.test.ts` | `verified` | Frontend still invokes legacy action endpoints (`api.advancePipeline`, `api.runMotion`). | Keep API client method signatures stable; map backend endpoints to orchestrator. | Med |
| **12. Remotion / FFmpeg Render Boundary** | `render` module & Remotion Root | `backend/render.py`, `remotion/` | `backend/orchestrator.py`, `backend/pipeline.py`, `backend/routes/pipeline.py` | `projects/{pid}/composition.json`, `projects/{pid}/out_{aspect}.mp4` | `verified` | Render invoked via CLI command through `procs.py`. RENDER_LOCK prevents concurrent renders. | Retain `backend/render.py` as stage service; orchestrated via `PipelineOrchestrator`. | Low |

---

## 3. Key Observations & Structural Analysis

1. **Clean Separation of Domain vs Shared Infrastructure**:
   - Shared infrastructure modules (`llm_gateway.py`, `skill_registry.py`, `shared_memory.py`, `approvals/`, `llm_usage.py`) are strictly decoupled from project-specific state and reside at the top of the dependency graph.
2. **Stable Physical Package Roots**:
   - All shared components reside naturally within `backend/`, `frontend/`, `config/`, and `skills/`. There is zero operational justification for a disruptive file move to hypothetical `SYSTEM/` or `SHARED/` trees.
3. **Primary Convergence Bottleneck**:
   - The single most critical architectural seam is the coexistence of `jobs.py` and `orchestrator.py`. Resolving this by making legacy endpoints thin wrappers around `PipelineOrchestrator` unlocks end-to-end consistency across state, checkpoints, retries, and telemetry.
