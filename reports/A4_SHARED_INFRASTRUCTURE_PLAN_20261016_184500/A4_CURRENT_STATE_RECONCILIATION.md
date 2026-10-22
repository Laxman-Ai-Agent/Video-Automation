# A4 Current-State Reconciliation Report

**Date:** October 16, 2026  
**Repository:** `E:\audio-to-video`  
**Git Branch:** `agents-building`  
**Git HEAD:** `f6989b17372e3cdb42b4c92ab1783b3122a401ae`  
**Mode:** Read-Only Verification  

---

## 1. Executive Reconciliation Summary

This report performs a line-by-line verification of claims made in previous milestone reports (Phase 1–10, A0 Architecture Audit, A1 Final Architecture, A2 Laxman Approval, A2 Security Review, A3 Planning, and A3 Implementation) against the live source code in `E:\audio-to-video`.

Every item is classified as:
- **`verified`**: Directly supported by implementation and verified in current files.
- **`partially_verified`**: Implementation exists, but end-to-end integration or runtime wiring is incomplete or optional.
- **`unverified`**: Claimed in earlier reports, but source evidence does not confirm active presence.
- **`missing`**: No implementation found in inspected locations.
- **`blocked`**: Cannot be safely verified without external execution or unavailable systems.

---

## 2. Verification of Prior Report Claims

| Subsystem / Claim | Earlier Report Source | Current Code Path | Status | Verification Evidence / Findings |
| :--- | :--- | :--- | :--- | :--- |
| **Canonical Pipeline Orchestrator** | Phase 8 Report | `backend/orchestrator.py` | `verified` | `PipelineOrchestrator` coordinates 12 stages, checks `jobs.is_running()`, manages cooperative cancellation, publishes genuine handoff events via `communication.py`. |
| **Legacy Route Forwarding to Orchestrator** | A3 Planning Report | `backend/routes/pipeline.py` | `missing` | **Contradiction Resolved:** Routes `/projects/{pid}/pipeline/advance` (line 137), `/projects/{pid}/motion/run` (line 92), `/projects/{pid}/render` (line 758) still invoke `jobs.start(...)`. They do NOT forward to `PipelineOrchestrator`. |
| **Authoritative Agent Registry** | Phase 1 Report, A3 Report | `backend/agents/registry.py` | `verified` | All 14 stable agent IDs are registered. `main_orchestrator` has `category=AgentCategory.ORCHESTRATOR`; all other 13 agents default to `VIDEO_ENGINE_AGENT`. |
| **Dedicated Agents UI Page** | A3 Implementation Report | `frontend/src/pages/AgentsPage.tsx` | `verified` | Standalone page registered at route `/agents` in `App.tsx` with `Bot` icon. Distinguishes Orchestrator, Video Engine Agents (12 stages), and System Subagents. |
| **Planned System Subagents** | A3 Implementation Report | `frontend/src/pages/AgentsPage.tsx` | `verified` | `capability_finder` and `skill_factory` are rendered with prominent `PLANNED` badges for Phases A5 & A6. Not registered as fake backend agents. |
| **Laxman Approval Engine** | A2 Report, A2 Sec Review | `backend/approvals/` | `verified` | PIN service uses salted PBKDF2 with constant-time comparison and fail-closed rate-limiting. Interactive CLI in `scripts/set_laxman_pin.py`. Central queue in `config/approvals_queue.json`, audit in `config/approvals_audit.jsonl`. |
| **Laxman Approval UI** | A2 Report | `frontend/src/pages/LaxmanApprovalPage.tsx` | `verified` | Standalone UI page registered at `/approvals` in `App.tsx`. Modal PIN dialog with error handling and rate-limit lockout support. |
| **Central LLM Gateway** | Phase 2 Report | `backend/llm_gateway.py` | `partially_verified` | Implementation is complete with profile routing, bounded retry, JSON repair, and usage tracking. However, `analysis_autofix.py` and `promptgen.py` still invoke raw `llm_client.generate_text()`. |
| **Mandatory LLM Review Gates** | Phase 2 Report | `backend/llm_review.py` | `verified` | All 12 stages have defined review descriptors. Review results are structured, persisted, and enforce non-negotiable completion rules before stage completion. |
| **Stage-State & Checkpoint Manager** | Phase 3 Report | `backend/pipeline_state.py` | `verified` | Manages 8 lifecycle states (`pending`, `running`, `completed`, `blocked`, `failed`, `needs_review`, `cancelled`, `skipped`). Persists to `.pipeline_state.json` and `.checkpoints/`. |
| **Artifact Contracts & Fingerprints** | Phase 3 Report | `backend/artifact_contracts.py` | `verified` | Defines input/output schema validators and SHA-256 fingerprint calculators for all 12 stages. |
| **Central Skill Catalog & Staging** | Phase 4 Report | `backend/skill_registry.py` | `verified` | Manages skill lifecycle (`discovered` -> `quarantined` -> `draft` -> `review_required` -> `approved` -> `deprecated`). Persists to `skills/catalog.json` and uses `skills/staging/`. |
| **Central Shared Memory Service** | Phase 4 Report | `backend/shared_memory.py` | `verified` | Separates project execution state, verified knowledge, and proposed candidates. Secret redaction and supersession tracking. Persists to `config/shared_memory.json`. |
| **Resource Library & Font/Icon Audits** | Phase 6 Report | `backend/resource_library.py` | `verified` | Tracks assets, bundles, licenses, and previews. Audits conducted via `resource_audit.py` and `resource_verify.py`. |
| **LLM Usage & Cost Monitor** | Phase 2 Report | `backend/llm_usage.py` | `verified` | Tracks token usage from development sessions (`~/.claude/metrics/costs.jsonl`) and runtime LLM calls. Computes API-equivalent costs in USD/INR. Persists to `config/llm_usage.json`. |
| **Frozen Code Preservation** | Phase 1–10, A0–A3 | `backend/transcribe.py`, `transcript_review.py`, `scene_segmentation.py` | `verified` | Bit-level SHA-256 hashes match frozen baselines exactly. Zero unauthorized edits. |
| **Cleaned Untracked Directories** | A3 Implementation Report | `.claude/worktrees/`, `out/` | `verified` | Both directories were backed up to `E:\a2v_tmp\backups/`, verified with `zipfile.testzip()`, and removed. `Test-Path` returns `False`. |

---

## 3. Deep-Dive: The Route-to-Orchestrator Convergence Contradiction

### 3.1 What Earlier Planning Stated (A3 Option 2A)
A3 planning documents specified:
> "Option 2A: Keep legacy execution routes as compatibility wrappers while gradually converging execution through `PipelineOrchestrator`."

### 3.2 What Current Source Code Actually Implements
We inspected `backend/routes/pipeline.py` and `backend/routes/orchestrator.py`:

```python
# backend/routes/pipeline.py:50-58
def _motion_timeline(pdir, pid: str):
    label = "timeline-9x16" if pipeline_view.aspect_of(pdir) == "9:16" else "timeline"
    return jobs.start(pid, label, chain_for(pdir, label), Ctx())

def _motion_job(pdir, pid: str):
    label = "motion-9x16" if pipeline_view.aspect_of(pdir) == "9:16" else "motion"
    return jobs.start(pid, label, chain_for(pdir, label), Ctx())

# backend/routes/pipeline.py:78-93
@router.post("/motion/run", response_model=JobStarted, status_code=202)
def run_motion(pid: str):
    ...
    return _started(_motion_job(pdir, pid))

# backend/routes/pipeline.py:118-138
@router.post("/pipeline/advance")
def advance(pid: str, part: str = "all"):
    ...
    _motion_timeline(pdir, pid)
    return {"advanced": True, "reason": "Motion-Only mode: the timeline is being built from the plan"}
```

Meanwhile, in `backend/routes/orchestrator.py`:
```python
# backend/routes/orchestrator.py:28-44
@router.post("/run", status_code=202)
def start_orchestrator_run(pid: str, body: RunRequestBody | None = None) -> dict[str, Any]:
    orch = orchestrator.PipelineOrchestrator(pid, body.aspect)
    run = orch.start_run(...)
    return run.to_dict()
```

### 3.3 Call Path Analysis
1. **Frontend Callers**:
   - `frontend/src/pipeline/PipelineChart.tsx` and `useAutoAdvance.ts` call `api.advancePipeline(pid)` -> `POST /projects/{pid}/pipeline/advance`.
   - `frontend/src/pages/MotionPlanningPage.tsx` calls `api.runMotion(pid)` -> `POST /projects/{pid}/motion/run`.
   - `frontend/src/pages/RenderVideoPage.tsx` calls `api.renderVideo(pid)` -> `POST /projects/{pid}/render`.
   - **Conclusion:** The live UI currently executes via `jobs.py` (`ThreadPoolExecutor`), not `PipelineOrchestrator`.
2. **Test Callers**:
   - `tests/test_motion_only_mode.py` and `tests/test_improve_p7.py` test `pipeline.execute()` and `jobs.start()`.
   - `tests/test_orchestrator_and_monitoring.py` and `tests/test_e2e_production_readiness.py` test `PipelineOrchestrator` directly and via `POST /projects/{pid}/orchestrator/run`.
   - **Conclusion:** Both engines are actively exercised in separate test suites.

### 3.4 Reconciled Finding
Legacy routes do **NOT** forward to `PipelineOrchestrator`. Forwarding was deferred during A3 to prevent breaking frontend behavior and legacy tests before a comprehensive contract mapping.
In A4, we establish the explicit adapter strategy to bridge this gap safely in A4 implementation.

---

## 4. Current Git State and Uncommitted Work
- Working Directory: `E:\audio-to-video`
- Current Branch: `agents-building`
- Current Commit: `f6989b17372e3cdb42b4c92ab1783b3122a401ae`
- Uncommitted modified files: 58 files (pipeline improvements, review gates, frontend UI, remotion code)
- Untracked files: New Phase 1–10 and A0–A3 modules, reports, tests.
- Untracked obsolete directories (`.claude/worktrees/`, `out/`): Confirmed completely removed and archived.
