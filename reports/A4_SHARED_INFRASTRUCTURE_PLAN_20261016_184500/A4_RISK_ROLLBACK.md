# A4 Risk Analysis, Rollback Strategy, and Guardrails

**Date:** October 16, 2026  
**Repository:** `E:\audio-to-video`  
**Phase:** A4 — Shared Infrastructure Integration Planning  
**Status:** COMPLETE  

---

## 1. Risk Evaluation & Mitigation Matrix

| # | Risk Description | Severity | Likelihood | Impact on System | Proactive Mitigation Strategy |
| :- | :--- | :--- | :--- | :--- | :--- |
| **R1** | **Legacy Endpoints Silently Changing Semantics** | High | Low | UI or test expecting immediate synchronous return breaks if route triggers whole-pipeline run. | Maintain wrapper signatures; only dispatch to `PipelineOrchestrator(from_stage=...)` where semantics match. Wrap in feature toggle `A2V_ORCHESTRATOR_WRAPPER`. |
| **R2** | **Dual-Engine Race Conditions (jobs.py vs orchestrator.py)** | Critical | Low | Two background threads simultaneously write artifacts to same project directory, causing file corruption. | Unified project mutex in `store.get_project_lock(pid)`. Both engines check `jobs.is_running(pid)` and `orchestrator.is_running(pid)`. |
| **R3** | **Conflicting State / Checkpoint Writes** | High | Low | State drift between `info.json`, `.build_state.json`, and `.pipeline_state.json`. | Designate `.pipeline_state.json` as sole canonical stage truth. Relegate `info.json` to high-level mirror and `.build_state.json` to fallback. |
| **R4** | **Loss of Cooperative Cancellation** | High | Low | Worker thread keeps running in background after client cancels. | Unified cancellation wrapper sets `job.cancel` flag, marks `RunRecord.status="cancelled"`, and invokes `procs.kill(pid)` on child processes. |
| **R5** | **Route / OpenAPI Schema Regressions** | High | Low | Frontend client fails to compile or throws runtime fetch errors. | Run `npm --prefix frontend test -- tests/contract.test.ts` and `npm run typecheck` on every batch. |
| **R6** | **LLM Usage / Cost Leakage** | Medium | Med | Direct callers to `llm_client` escape cost tracking. | Route `analysis_autofix.py` and `promptgen.py` through `llm_gateway.execute()`. |
| **R7** | **Sensitive Credential Leakage in Logs** | High | Low | API keys or PIN hashes printed to logs or SSE streams. | Central redaction regex in `llm_gateway.py` and `communication.py` automatically scrubs known patterns (`sk-...`, `Bearer ...`). |
| **R8** | **Accidental ASR / Remotion Render Execution** | High | Low | Long, expensive runs triggered during testing. | Enforce synthetic fixtures and mocked runners in all test definitions. Explicit prohibition on live render commands. |

---

## 2. Hard Stop Conditions

Execution must halt immediately and request human operator review if any of the following occur:
1. **Frozen File Alteration:** Any proposed change touches or modifies `backend/transcribe.py`, `backend/transcript_review.py`, or `backend/scene_segmentation.py`.
2. **Hash Discrepancy:** SHA-256 check fails on any frozen baseline.
3. **Data Migration Requirement:** Any change that would corrupt or invalidate existing on-disk user projects in `projects/`.
4. **Unbounded Test Failures:** More than 2 unexpected test failures in a batch verification step.
5. **Security Bypass:** Any code path allowing side effects (e.g., render, export, baseline promotion) without valid Laxman PIN verification.

---

## 3. Detailed Batch Rollback Procedures

### Batch 1 Rollback (Route Wrappers):
- Trigger: Frontend error on `/motion/run` or `/advance`.
- Action: Set environment variable `A2V_ORCHESTRATOR_WRAPPER=0`.
- Effect: Route handlers immediately revert to invoking `jobs.start()` without needing a code deployment.
- Recovery Time: < 30 seconds.

### Batch 2 Rollback (Concurrency & Locks):
- Trigger: Deadlock or lock acquisition timeout.
- Action: Revert `store.get_project_lock(pid)` modifications in `jobs.py` and `orchestrator.py` to their independent thread locks.
- Verification: Verify with `pytest tests/test_orchestrator_and_monitoring.py -k test_concurrent`.

### Batch 3 Rollback (LLM Gateway Convergence):
- Trigger: JSON parsing error or timeout in `analysis_autofix.py` or `promptgen.py`.
- Action: Revert specific function calls back to `llm_client.generate_text()`.
- Verification: Run `pytest tests/test_llm_gateway.py`.

### Batch 4 Rollback (Observability & Correlation):
- Trigger: SSE connection drops or corrupted `communications.jsonl` lines.
- Action: Revert `pipeline_view.py` and response payload augmentations.
- Verification: Run frontend vitest suite.
