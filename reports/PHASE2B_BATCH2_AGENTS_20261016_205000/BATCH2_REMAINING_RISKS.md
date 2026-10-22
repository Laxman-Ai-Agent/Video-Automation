# Phase 2B — Batch 2 Remaining Risks and Next Batch Prerequisites Report

- **Date/Time**: 2026-10-16 20:50:00 UTC+5:30
- **Repository Root**: `E:\audio-to-video`
- **Branch / HEAD**: `agents-building` / `f6989b17372e3cdb42b4c92ab1783b3122a401ae`
- **Scope**: Remaining Risks, Subsystem Dependencies & Batch 3 Readiness

---

## 1. Subsystem Dependencies & Compatibility Status

With Batch 2 complete, all agent implementations (`BaseAgent`, contracts, communication, stage adapters, and registry) reside canonically under `SYSTEM/agents/` and `SYSTEM/registries/`.

The following cross-subsystem dependencies remain active and are scheduled for subsequent migration batches:

1. **Pipeline Execution Engine (`backend/orchestrator.py` & `backend/jobs.py`)**:
   - Currently residing in `backend/`.
   - Stage adapters in `SYSTEM/agents/video_generation_agents/stage_adapters.py` interact with pipeline stages and orchestrator contracts.
   - **Resolution Plan**: Scheduled for **Batch 3** (`VIDEO_ENGINE/pipeline/` and `VIDEO_ENGINE/stages/`).
2. **Video Engine Stage Implementations**:
   - Stage execution scripts (`concept_stage.py`, `component_stage.py`, `layout_stage.py`, `codegen_stage.py`, `timeline_stage.py`, `render_stage.py`, `qc_stage.py`, `export_stage.py`, etc.) currently reside in `backend/`.
   - **Resolution Plan**: Scheduled for **Batch 3** (`VIDEO_ENGINE/stages/`).
3. **Frozen ASR & Segmentation Stage Files**:
   - `backend/transcribe.py`, `backend/transcript_review.py`, and `backend/scene_segmentation.py` are strictly protected files.
   - **Resolution Plan**: In Batch 3, these files must be handled strictly according to the frozen file gate rules — verifying SHA-256 before any action, preserving them intact, and ensuring zero regressions.
4. **Remotion Engine & Compositions (`remotion/`)**:
   - Currently residing at the root `remotion/`.
   - **Resolution Plan**: Scheduled for **Batch 4** (`VIDEO_ENGINE/remotion/` and `VIDEO_ENGINE/rendering/`).
5. **UI Backend Routes & Frontend (`backend/routes/*`, `backend/main.py`, `frontend/`)**:
   - `backend/routes/agents.py` is already repointed to canonical `SYSTEM` modules. The remaining pipeline, media, and visual routes will migrate with the UI subsystem.
   - **Resolution Plan**: Scheduled for **Batch 5** (`UI/backend/` and `UI/frontend/`).
6. **Temporary Backward Compatibility Shims in `backend/agents/`**:
   - Thin `sys.modules` aliases currently maintain seamless compatibility for legacy tests and unmigrated modules.
   - **Resolution Plan**: Scheduled for safe retirement in **Batch 7** once all repository imports have been converged to `SYSTEM.*`.

---

## 2. Deferred Removals & Cleanups

1. **Dead Image Mode Code**:
   - The 5 identified legacy image files (`backend/image_gate.py`, `backend/bg_remove.py`, `backend/fill_slots.py`, `backend/prompts_writer.py`, `backend/motion_template_selection.py`) were intentionally preserved intact during Batch 2.
   - **Scheduled**: **Batch 6** (Post-stage migration dead code elimination).
2. **Legacy JobRunner Thread Pool**:
   - `backend/jobs.py` contains legacy thread pool execution logic that has been superseded by `PipelineOrchestrator`. Full convergence and removal is scheduled for **Batch 3**.

---

## 3. Updated Risk Register

| Risk ID | Description | Severity | Pre-Batch 2 Status | Post-Batch 2 Status | Mitigation Strategy |
|---|---|---|---|---|---|
| **RSK-001** | Frozen Files Modification | `BLOCKER` | CONTROLLED | **CONTROLLED** | Hashes verified 100% identical. 0 edits to transcribe/review/segmentation. |
| **RSK-002** | Agent Registry State Split | `HIGH` | OPEN | **RESOLVED** | Authoritative singleton lives at `SYSTEM/registries/agent_registry.py`. `sys.modules` aliasing guarantees zero duplicate registries. |
| **RSK-003** | Route Handler Import Failure | `HIGH` | CONTROLLED | **CONTROLLED** | `backend/routes/agents.py` repointed directly to canonical paths; 3/3 route tests passed; 65 routes mounted. |
| **RSK-004** | Stage Adapter Contract Desync | `MEDIUM` | OPEN | **RESOLVED** | All 14 stage adapters verified against `SYSTEM/core/artifact_contracts.py` and `SYSTEM/agents/shared/contracts.py`. 57/57 tests pass. |
| **RSK-005** | Pipeline Execution Disruption | `HIGH` | PENDING | **PENDING (Batch 3)** | Orchestrator and stages remain in `backend/` until Batch 3. Will be migrated with backward compatibility aliases. |
| **RSK-006** | Remotion Bundle Path Shift | `HIGH` | PENDING | **PENDING (Batch 4)** | Remotion folder untouched in Batch 2. Full path reconciliation scheduled for Batch 4. |
| **RSK-007** | Premature Code Deletion | `MEDIUM` | CONTROLLED | **CONTROLLED** | Zero image mode files or legacy modules deleted. |

---

## 4. Prerequisites for Batch 3 (VIDEO_ENGINE Pipeline & Stages Migration)

Before initiating Batch 3:

1. **User Approval**: Explicit user review and authorization of Batch 2 results.
2. **Frozen File Pre-Check**: Pre-migration SHA-256 hash recalculation and verification against `PHASE2_FROZEN_FILE_HASHES.md`.
3. **Execution Safety**: Strict adherence to no-run policies (no Whisper ASR, no Remotion renders, no live pipeline triggers).
4. **Target Structure Preparation**: Ensure `VIDEO_ENGINE/pipeline/` and `VIDEO_ENGINE/stages/` directories are properly initialized with `__init__.py`.
