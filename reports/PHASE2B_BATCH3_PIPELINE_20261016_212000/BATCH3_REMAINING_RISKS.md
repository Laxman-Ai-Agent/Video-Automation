# Phase 2B — Batch 3 Remaining Risks and Next Batch Prerequisites Report

- **Date/Time**: 2026-10-16 21:20:00 UTC+5:30
- **Repository Root**: `E:\audio-to-video`
- **Branch / HEAD**: `agents-building` / `f6989b17372e3cdb42b4c92ab1783b3122a401ae`
- **Scope**: Remaining Risks, Subsystem Dependencies & Batch 4 Readiness

---

## 1. Remaining Dependencies Across Subsystems

With Batch 3 complete, both `SYSTEM/` (shared infrastructure and agents) and `VIDEO_ENGINE/` (pipeline execution and stages) are canonically structured and operational.

The following cross-subsystem dependencies remain active and will be resolved in subsequent batches:

1. **Remotion Engine & Compositions (`remotion/`)**:
   - Currently residing at root `remotion/`.
   - Stage adapters and renderer scripts (`VIDEO_ENGINE/stages/render.py`, `render_video.py`) reference `remotion/` via `config.PROJECT_ROOT / "remotion"`.
   - **Resolution Plan**: Scheduled for **Batch 4** (`VIDEO_ENGINE/remotion/` and `VIDEO_ENGINE/rendering/`).
2. **FFmpeg & Media Probing (`backend/media_probe.py`)**:
   - Currently residing at `backend/media_probe.py` with temporary bridge in `VIDEO_ENGINE/stages/media_probe.py`.
   - **Resolution Plan**: Scheduled for **Batch 4** (`VIDEO_ENGINE/ffmpeg/media_probe.py`).
3. **UI Backend Routes & Frontend (`backend/routes/*`, `backend/main.py`, `frontend/`)**:
   - FastAPI app and HTTP endpoints still reside in `backend/`.
   - **Resolution Plan**: Scheduled for **Batch 5** (`UI/backend/` and `UI/frontend/`).
4. **Dead Image Mode Candidates**:
   - The 5 identified legacy image files (`backend/image_gate.py`, `backend/bg_remove.py`, `backend/fill_slots.py`, `backend/prompts_writer.py`, `backend/motion_template_selection.py`) are bridged in `VIDEO_ENGINE/stages/` and remain intact.
   - **Resolution Plan**: Scheduled for clean removal in **Batch 6**.
5. **Temporary Backward Compatibility Bridges in `backend/`**:
   - Bridges exist in `backend/` to ensure unmigrated callers and external tools resolve smoothly.
   - **Resolution Plan**: Scheduled for safe retirement in **Batch 7** after root configuration and test imports converge.

---

## 2. Updated Risk Register Post-Batch 3

| Risk ID | Description | Severity | Pre-Batch 3 Status | Post-Batch 3 Status | Mitigation & Verification |
|---|---|---|---|---|---|
| **RSK-001** | Frozen Files Integrity Violation | `BLOCKER` | CONTROLLED | **PRESERVED & RELOCATED** | All 3 frozen files moved byte-for-byte to `VIDEO_ENGINE/stages/`. Hashes 100% match approved baseline. |
| **RSK-002** | Dual Execution Loop / Split State | `HIGH` | OPEN | **RESOLVED** | `jobs.py` converged to `jobs_adapter.py`; `PipelineOrchestrator` is sole canonical engine. |
| **RSK-003** | Stage Adapter Contract Breakage | `MEDIUM` | OPEN | **RESOLVED** | All 14 stage adapters repointed directly to `VIDEO_ENGINE.pipeline` and `VIDEO_ENGINE.stages`. 138/138 tests pass. |
| **RSK-004** | Remotion Bundle Path Shift | `HIGH` | PENDING | **PENDING (Batch 4)** | Remotion folder untouched in Batch 3. Path reconciliation scheduled for Batch 4. |
| **RSK-005** | Unauthorized Render / ASR Trigger | `HIGH` | CONTROLLED | **CONTROLLED** | Strict mock fixtures enforced in tests (`mock_no_asr`). Zero real ASR or video renders executed. |
| **RSK-006** | Premature Code Deletion | `MEDIUM` | CONTROLLED | **CONTROLLED** | Zero image mode files or legacy modules deleted. |

---

## 3. Prerequisites for Batch 4 (VIDEO_ENGINE Remotion & FFmpeg Migration)

Before proceeding to Batch 4:

1. **User Approval**: Explicit user review and authorization of Batch 3 results.
2. **Remotion Subsystem Verification**: Inspect Remotion package structure (`package.json`, `tsconfig.json`, `remotion.config.ts`, `src/`) before relocation.
3. **Asset Path Confinement**: Verify that paths to `projects/` and `resource-library/` remain accessible from the new `VIDEO_ENGINE/remotion/` location.
4. **Execution Safety**: Continue strict enforcement of no-render and no-install policies.
