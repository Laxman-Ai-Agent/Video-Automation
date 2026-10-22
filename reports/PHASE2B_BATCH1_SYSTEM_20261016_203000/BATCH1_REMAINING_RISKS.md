# Phase 2B — Batch 1 Remaining Risks and Next Batch Prerequisites Report

- **Date/Time**: 2026-10-16 20:30:00 UTC+5:30
- **Repository Root**: `E:\audio-to-video`
- **Branch / HEAD**: `agents-building` / `f6989b17372e3cdb42b4c92ab1783b3122a401ae`
- **Scope**: Remaining Risks, Compatibility Status & Batch 2 Readiness

---

## 1. Remaining Dependencies & Compatibility Status

With Batch 1 complete, the core shared services (`llm_gateway`, `pipeline_state`, `errors`, `artifact_contracts`, `approval_engine`, `guard`, `pin_service`, `shared_memory`, `store`, `skill_registry`, `llm_review`, `llm_usage`, `evaluation`) are canonicalized under `SYSTEM/`.

The following cross-subsystem dependencies remain active and will be resolved in subsequent batches:

1. **Agent Implementations (`backend/agents/`)**:
   - Currently residing in `backend/agents/`.
   - `llm_gateway.py` and `pipeline_state.py` dynamically resolve `communication` and `contracts` from either `SYSTEM.agents.shared` or `backend.agents`.
   - **Resolution Plan**: Scheduled for **Batch 2** (`SYSTEM/agents/shared/`, `SYSTEM/agents/video_generation_agents/`, `SYSTEM/agents/system_agents/`).
2. **Video Pipeline & Stages (`backend/orchestrator.py` & stage files)**:
   - Currently residing in `backend/`.
   - `SYSTEM/core/pipeline_state.py` references `jobs` via fallback import.
   - **Resolution Plan**: Scheduled for **Batch 3** (`VIDEO_ENGINE/pipeline/` and `VIDEO_ENGINE/stages/`).
3. **UI Routes & Frontend (`backend/routes/*`, `backend/main.py`, `frontend/`)**:
   - FastAPI routers in `backend/routes/` are still mounted by `backend/main.py`.
   - Key route files (`approvals.py`, `evaluation.py`, `memory.py`, `skills.py`, `llm.py`) have already been repointed to `SYSTEM.*`. Remaining pipeline/visual/results routes still reference `backend.*`.
   - **Resolution Plan**: Scheduled for **Batch 5** (`UI/backend/` and `UI/frontend/`).
4. **Temporary Compatibility Shims in `backend/`**:
   - `backend/` retains exact `sys.modules` aliases to canonical `SYSTEM` modules.
   - **Resolution Plan**: These shims will be safely deleted in **Batch 7** once all callers and tests across the repository are repointed directly to `SYSTEM.*`.

---

## 2. Deferred Removals & Cleanups

1. **Motion-Only Image Mode Deletions**:
   - The 5 identified dead image mode files (`backend/image_gate.py`, `backend/bg_remove.py`, `backend/fill_slots.py`, `backend/prompts_writer.py`, `backend/motion_template_selection.py`) were intentionally preserved in Batch 1.
   - **Scheduled**: **Batch 6** (Clean removal after stage migration).
2. **Legacy JobRunner Thread Pool Cleanup**:
   - `backend/jobs.py` currently delegates to `PipelineOrchestrator`. Full retirement and removal of legacy thread pool code is deferred to **Batch 3**.

---

## 3. Risk Register Status After Batch 1

| Risk ID | Severity | Status | Post-Batch 1 Assessment |
|---|---|---|---|
| **RSK-001** (Frozen Files Integrity) | `BLOCKER` | **CONTROLLED** | Hashes verified 100% intact after Batch 1. Files remain untouched in `backend/`. |
| **RSK-002** (Dual State / Status Sync) | `HIGH` | **IMPROVED** | `pipeline_state.py` and `store.py` now both live canonically under `SYSTEM/` sharing single state contracts. |
| **RSK-003** (UI Contract Breakage) | `HIGH` | **CONTROLLED** | FastAPI app and all 15 routers verified loading with code 0. Compatibility aliases prevent broken imports. |
| **RSK-004** (Remotion Asset Paths) | `HIGH` | **DEFERRED** | Deferred to Batch 4; `remotion/` has not been moved yet. |
| **RSK-005** (Laxman PIN Hash Security) | `MEDIUM` | **SECURED** | `pin_service.py` migrated to `SYSTEM/approvals/`. PBKDF2 constant-time verification fully tested (18/18 tests passed). |
| **RSK-006** (Dead Code Removal) | `MEDIUM` | **DEFERRED** | Deferred to Batch 6; zero image code deleted prematurely. |
| **RSK-007** (Unauthorized Execution) | `HIGH` | **CONTROLLED** | Strict execution limits maintained; zero renders, ASR, or pipeline runs executed. |

---

## 4. Prerequisites for Batch 2 (SYSTEM Agents Migration)

Before proceeding to Batch 2:
- [x] Batch 1 reports written and verified.
- [x] All 81 focused tests passing.
- [x] Zero frozen file changes verified.
- [ ] **Operator review and explicit approval to proceed to Batch 2.**

**Ready for Batch 2: Migration of SYSTEM Agents (`backend/agents/*` -> `SYSTEM/agents/*` and `SYSTEM/registries/agent_registry.py`).**
