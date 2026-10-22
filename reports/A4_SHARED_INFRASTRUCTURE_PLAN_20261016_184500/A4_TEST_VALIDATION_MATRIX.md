# A4 Test and Validation Matrix

**Date:** October 16, 2026  
**Repository:** `E:\audio-to-video`  
**Phase:** A4 — Shared Infrastructure Integration Planning  
**Status:** PLANNING ONLY — NO TESTS EXECUTED DURING THIS PHASE  

---

## 1. Overview and Test Boundaries

In accordance with Phase A4 planning guardrails:
- **Zero test suites are executed during this planning phase.**
- Every proposed implementation batch is mapped to existing, deterministic test definitions.
- Strict test execution rules apply during implementation:
  - Synthetic and mocked fixtures only.
  - Zero ASR / transcription execution.
  - Zero Remotion headless video rendering or FFmpeg encoding.
  - Targeted, bounded test commands only.

---

## 2. Test Mapping Matrix per Implementation Batch

| Batch | Subsystem / Capability | Existing Test File | Specific Test Targets / Assertions | Precondition | Command (Recommendation) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Batch 1** | Route Dispatch & Orchestrator Wrappers | `tests/test_orchestrator_and_monitoring.py` | `test_start_run_idempotency`, `test_stage_dependency_graph`, `test_cancel_run` | Clean checkout | `pytest tests/test_orchestrator_and_monitoring.py` |
| **Batch 1** | Legacy Route Public Contract | `tests/test_motion_only_mode.py` | `test_motion_branch_endpoints`, `test_pipeline_advance_motion_only` | Batch 1 applied | `pytest tests/test_motion_only_mode.py` |
| **Batch 1** | Frontend API Contract Snapshot | `frontend/tests/contract.test.ts` | Validates OpenAPI route mapping table against ROUTES | Batch 1 applied | `npm --prefix frontend test -- tests/contract.test.ts` |
| **Batch 2** | Project Concurrency & Mutual Exclusion | `tests/test_orchestrator_and_monitoring.py` | `test_concurrent_run_rejection` (Verifies HTTP 409 `job_running`) | Batch 1 verified | `pytest tests/test_orchestrator_and_monitoring.py -k test_concurrent` |
| **Batch 2** | Process Restart & Orphaned Recovery | `tests/test_pipeline_state_and_checkpoint.py` | `test_orphan_recovery_after_restart`, `test_checkpoint_integrity` | Batch 2 applied | `pytest tests/test_pipeline_state_and_checkpoint.py` |
| **Batch 3** | LLM Gateway Routing & Repair | `tests/test_llm_gateway.py` | `test_profile_routing`, `test_json_repair_retry`, `test_bounded_backoff` | Batch 2 verified | `pytest tests/test_llm_gateway.py` |
| **Batch 3** | Telemetry & Usage Cost Attribution | `tests/test_llm_usage.py` | `test_record_usage_event`, `test_cost_calculation_usd_inr` | Batch 3 applied | `pytest tests/test_llm_usage.py` |
| **Batch 3** | Mandatory Review Gate Enforcement | `tests/test_motion_codegen_and_concurrency.py` | `test_mandatory_review_gate_blocks_on_failure` | Batch 3 applied | `pytest tests/test_motion_codegen_and_concurrency.py -k test_review` |
| **Batch 4** | Agent Registry & Category Model | `tests/test_agent_runtime_and_communication.py` | `test_registry_14_agents_valid`, `test_agent_categories` | Batch 3 verified | `pytest tests/test_agent_runtime_and_communication.py` |
| **Batch 4** | Durable Communication Audit Stream | `tests/test_agent_routes.py` | `test_get_agent_communications`, `test_stream_events` | Batch 4 applied | `pytest tests/test_agent_routes.py` |
| **Batch 4** | Laxman PIN Authorization Guard | `tests/test_laxman_approval.py` | `test_pin_verification_success_and_lockout`, `test_single_use_token_consumed` | Core invariant | `pytest tests/test_laxman_approval.py` |
| **Batch 4** | Frontend UI Typecheck & Unit Tests | `frontend/tests/agents_page.test.tsx`, `laxman_approval_page.test.tsx` | All 6 agent page tests + 8 approval page tests pass cleanly | Batch 4 applied | `npm --prefix frontend run typecheck && npm --prefix frontend test -- tests/agents_page.test.tsx` |
| **Batch 4** | End-to-End Production Readiness | `tests/test_e2e_production_readiness.py` | Full 12-stage synthetic pipeline coordination without ASR/render | Full implementation | `pytest tests/test_e2e_production_readiness.py` |

---

## 3. Bit-Level Frozen Code Validation

Before and after each batch, the bit-level SHA-256 integrity of the three frozen files must be checked:
```powershell
python -c "
import hashlib
hashes = {
  'backend/transcribe.py': '07a200319d41c2bd1550dfd5704f3bbcc5fac8331a0aeb09dcca4bf46d61376e',
  'backend/transcript_review.py': '7290ea210d922514c011c799caf73aad61398f0229cc6799dd2f10072b38d049',
  'backend/scene_segmentation.py': '2d9ea882b8c53a6cfcd43b048481f72140a1a6792b8f05578e16fd56a9b37042',
}
for p, expected in hashes.items():
  with open(p, 'rb') as f:
    actual = hashlib.sha256(f.read()).hexdigest()
    assert actual == expected, f'Hash mismatch on {p}!'
print('Frozen hashes verified 100% identical.')
"
```
