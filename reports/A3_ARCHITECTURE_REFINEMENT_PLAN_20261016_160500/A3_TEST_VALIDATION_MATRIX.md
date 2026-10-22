# A3 — Test Validation Matrix (For Future Execution)

**Document ID:** A3-TVM-01  
**Date:** 2026-10-16 16:05:00 UTC  
**Repository:** `E:\audio-to-video`  
**Git Branch / HEAD:** `agents-building` / `f6989b17372e3cdb42b4c92ab1783b3122a401ae`  
**Execution Notice:** **A3 is a planning-only task. Zero tests have been executed during this planning run.** This matrix maps the required test suites to proposed future implementation changes.

---

## 1. Change-to-Test Mapping Matrix

| Future Implementation Area | Proposed Changes | Applicable Test Suite | Specific Test Assertions / Invariants |
|---|---|---|---|
| **Batch 1: Agent Category in Contracts & Registry** | Add `AgentCategory` enum to `contracts.py`; classify 14 agents in `registry.py` | `pytest tests/test_agent_routes.py tests/test_agent_runtime_and_communication.py -v` | 1. All 14 existing agent IDs are present and unchanged.<br>2. `main_orchestrator` has `category == "orchestrator"`.<br>3. 12 active stages have `category == "video_engine_agent"`.<br>4. `motion_template_selection` has `category == "video_engine_agent"` and `status == "deprecated"`.<br>5. `GET /agents` returns valid JSON with `category` serialized. |
| **Batch 2: Frontend Types & Client Synchronization** | Add `category` to `agentTypes.ts`; update drawer filter | `npm --prefix frontend run typecheck`<br>`npm --prefix frontend test -- tests/client.test.ts` | 1. TypeScript compiles with zero errors.<br>2. API client properly types `listAgents()` response.<br>3. AgentCommunicationDrawer continues filtering messages by agent ID without regression. |
| **Batch 3: UI Agent Separation Display** | Render separate UI groups for Orchestrator, Video Engine, and System Subagents | `npm --prefix frontend run typecheck`<br>`npm --prefix frontend test -- tests/agents_page.test.tsx` (new test) | 1. Main Orchestrator renders as controller card.<br>2. 12 Video Engine Agents render in sequential stage order with frozen badges.<br>3. System Subagents section renders planned items with `PLANNED` badge.<br>4. Empty, loading, and error states render cleanly.<br>5. Existing navigation (`Laxman Approval`, `Dashboard`) is unaffected. |
| **Batch 4: Cleanup Step 1 (Untracked Files)** | Remove `.claude/worktrees/` (32 MB) and `out/` (30 MB) after verified backup | `pytest tests/test_timeline_render_qc_delivery.py -v`<br>`npm --prefix frontend run typecheck` | 1. Verified deletion does not impact Remotion rendering pipeline.<br>2. Project renders to `projects/<pid>/out.mp4` unaffected.<br>3. Zero missing module import errors. |
| **Batch 5: Cleanup Step 2 (Decouple Status Files)** | Refactor `tests/test_status.py` and retire `STATUS.json` / `STATUS.md` | `pytest tests/test_status.py -v`<br>`pytest tests/test_orchestrator_and_monitoring.py -v` | 1. `test_status.py` passes by asserting on authoritative code registries instead of root JSON files.<br>2. Root directory is clean of obsolete static checklists. |

---

## 2. Regression Safety & Test Scoping

When implementation is approved, testing must follow strict safety rules:
1. **Zero ASR Execution**: Never trigger live Whisper transcription or download model weights during automated testing. Test using prepared synthetic fixtures (`projects/test-01-c2a8/` or `conftest.py` fixtures).
2. **Zero Real Pipeline or Render Runs**: Do not trigger long-running Remotion renders unless explicitly requested. Use existing mock/synthetic pipeline test configurations.
3. **Scoped Failure Diagnosis**: If a test fails, do not loop or blindly retry. Capture the exact command and traceback, diagnose the root cause, and apply targeted fixes.
4. **Frozen Module Hashes**: Re-verify bit-level SHA-256 hashes of `transcribe.py`, `transcript_review.py`, and `scene_segmentation.py` before and after any batch.

---

## 3. Planning Confirmation

**No tests were run during Phase A3 planning.** This ensures complete non-interference with ongoing background processes (such as Uvicorn) and strictly obeys the user instruction: *"Do not run tests, execute ASR, run the real pipeline, or render videos during this planning phase."*
