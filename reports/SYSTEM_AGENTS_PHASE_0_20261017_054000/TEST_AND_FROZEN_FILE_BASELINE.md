# Test & Frozen File Baseline Report

**Date:** 2026-10-17  
**Repository Root:** `E:\audio-to-video`  
**Report Directory:** `reports/SYSTEM_AGENTS_PHASE_0_20261017_054000/`  

---

## 1. Git & Environment Baseline

### Git Repository State
- **Branch:** `agents-building`
- **HEAD Commit:** `f6989b17372e3cdb42b4c92ab1783b3122a401ae`
- **Working Tree:**
  - Application source code is clean and unmodified.
  - Retained historical reports and improvement design documents are untracked.
  - Confirmed deleted legacy media assets and image test samples are staged as deleted in git status.

### Runtime Environment
- **Python Version:** Python 3.12.10 (`.venv\Scripts\python.exe`)
- **Pytest Version:** 9.1.1
- **Node.js Version:** v24.19.0
- **Remotion Version:** Remotion 4.x (located at `VIDEO_ENGINE/remotion/`)
- **FFmpeg / FFprobe:** System binaries discovered and validated via `shutil.which()`.

---

## 2. Frozen Algorithm File Verification

The three canonical core algorithm files are strictly protected invariants. They must remain 100% byte-for-byte identical across all phases:

```text
VIDEO_ENGINE/stages/transcribe.py
VIDEO_ENGINE/stages/transcript_review.py
VIDEO_ENGINE/stages/scene_segmentation.py
```

### SHA-256 Hash Audit Results

| File Path | Canonical Required SHA-256 Hash | Current Working Tree SHA-256 | Verification Status | Byte Diff |
|:---|:---|:---|:---:|:---:|
| `VIDEO_ENGINE/stages/transcribe.py` | `07a200319d41c2bd1550dfd5704f3bbcc5fac8331a0aeb09dcca4bf46d61376e` | `07a200319d41c2bd1550dfd5704f3bbcc5fac8331a0aeb09dcca4bf46d61376e` | **MATCH (100%)** | 0 bytes |
| `VIDEO_ENGINE/stages/transcript_review.py` | `7290ea210d922514c011c799caf73aad61398f0229cc6799dd2f10072b38d049` | `7290ea210d922514c011c799caf73aad61398f0229cc6799dd2f10072b38d049` | **MATCH (100%)** | 0 bytes |
| `VIDEO_ENGINE/stages/scene_segmentation.py` | `2d9ea882b8c53a6cfcd43b048481f72140a1a6792b8f05578e16fd56a9b37042` | `2d9ea882b8c53a6cfcd43b048481f72140a1a6792b8f05578e16fd56a9b37042` | **MATCH (100%)** | 0 bytes |

**Finding:** All 3 frozen algorithm files exist at their canonical paths and match their required SHA-256 hashes byte-for-byte.

---

## 3. Reusable Test Evidence Inventory

Per Phase 0 safety instructions, the full test suite was **not** rerun during Phase 0. The following table records verified reusable test evidence captured prior to Phase 0:

| Test File / Suite | Tests Run | Result | Evidence Timestamp | Scope & Purpose |
|:---|:---:|:---:|:---:|:---|
| `SYSTEM/agents/main_architecture_agent/tests/test_self_learning.py` | 15 | **PASSED** | 2026-10-17 05:29 | Experience collection, reflection, proposals, strategy rollback |
| `SYSTEM/agents/main_architecture_agent/tests/test_agent.py` | 2 | **PASSED** | 2026-10-17 05:29 | Master Agent discovery and plan decomposition |
| `tests/test_agent_architecture_reorg.py` | 74 | **PASSED** | 2026-10-17 05:30 | 14 video agents, adapters, metadata, category enums |
| `tests/test_agent_runtime_and_communication.py` | 8 | **PASSED** | 2026-10-17 05:30 | Inter-agent communication bus, project lock, redaction |
| `tests/test_skills_and_shared_memory.py` | 19 | **PASSED** | 2026-10-17 05:30 | Central skills catalog, staging, memory scoping |
| `tests/test_evaluation_and_self_learning.py` | 11 | **PASSED** | 2026-10-17 05:30 | Phase 9 two-tier evaluation, baselines, candidates |
| `tests/test_laxman_approval.py` | 18 | **PASSED** | 2026-10-17 05:30 | Cryptographic PIN hashing, salt, approval queue |
| `tests/test_agent_routes.py` | 3 | **PASSED** | 2026-10-17 05:30 | Backend presentation routes for agent inspection |
| `tests/test_audio_visual_agents_integration.py` | 12 | **PASSED** | 2026-10-17 05:34 | Audio input, audio analyzer, scene segmentation |
| `tests/test_motion_codegen_and_concurrency.py` | 9 | **PASSED** | 2026-10-17 05:34 | Motion planning, TSX component codegen, concurrency |
| `tests/test_timeline_render_qc_delivery.py` | 12 | **PASSED** | 2026-10-17 05:34 | Timeline compile, approval, render, QC probe |
| `tests/test_orchestrator_and_monitoring.py` | 13 | **PASSED** | 2026-10-17 05:34 | PipelineOrchestrator state recovery, events, cancellation |
| `tests/test_llm_gateway.py` | 12 | **PASSED** | 2026-10-17 05:34 | Multi-provider routing, retry fallback, cache |
| `tests/test_llm_usage.py` | 10 | **PASSED** | 2026-10-17 05:34 | Token usage, cost estimation, quota limits |
| `tests/test_pipeline_state_and_checkpoint.py` | 11 | **PASSED** | 2026-10-17 05:34 | Atomic state transitions, resume from disk |
| `tests/test_e2e_production_readiness.py` (Tier A & B) | 10 | **PASSED** | 2026-10-17 05:33 | Pre-flight validation, pipeline mock runs |
| **Total Reusable Passed Tests** | **239** | **PASSED** | — | **Zero Regressions on Canonical Architecture** |

---

## 4. Failing Test Baselines (Legacy Image Mode)

When executing broad `pytest tests/`, 8 test files fail at module collection time. These are historical remnants of the Image Mode pipeline that were intentionally retired during Batch 6 (Motion-Only migration):

1. `tests/test_improve_p8.py` — imports `fill_slots` from `backend` (deleted in Batch 6).
2. `tests/test_m9_portrait.py` — imports `pipeline` from `SYSTEM.core` (legacy path; moved to `VIDEO_ENGINE.pipeline`).
3. `tests/test_m9_prerender.py` — imports `pipeline` from `SYSTEM.core`.
4. `tests/test_m9_promptgen.py` — imports `test_m9_review` which imports `fill_slots`.
5. `tests/test_m9_review.py` — imports `fill_slots`, `jobs`, `promptgen`, `review`.
6. `tests/test_m9_visual.py` — imports `test_m9_review`.
7. `tests/test_pipeline_gate.py` — imports `image_gate` from `backend` (deleted in Batch 6).
8. `tests/test_stock.py` — imports `image_gate` from `backend` (deleted in Batch 6).

**Recommendation:** Do not modify these legacy test files in Phase 0. In a subsequent cleanup phase, safely archive or adapt them to motion-only equivalents.

---

## 5. Unverified Test Scope

The following test area remains explicitly **Unverified** in Phase 0:
- **Tier C Live Remotion Video Render Tests (`test_tier_c_isolated_synthetic_live_render_and_media_probe`):** Intentionally skipped during Phase 0 to strictly abide by the read-only, non-render directive. Headless Chromium live render capability remains verified from Phase 10 / Batch 7 historical reports, but was not executed in this audit.
