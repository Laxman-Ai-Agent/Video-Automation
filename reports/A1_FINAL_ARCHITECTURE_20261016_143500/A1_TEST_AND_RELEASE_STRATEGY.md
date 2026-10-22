# A1 Test & Release Strategy — Verification Gates & Safe Rollout

**Audit ID:** A1-TST-01  
**Timestamp:** 2026-10-16T14:40:00+05:30  
**Repository Root:** `E:\audio-to-video`  

---

## 1. Verified Baseline Test Status

Prior to initiating Phase A1, the complete cross-phase regression test suite was executed across all 11 test suites (Phases 1 through 10):

- **Total Tests Executed:** 121
- **Passed:** 121
- **Failed:** 0
- **Duration:** 58.53 seconds
- **Frontend Typecheck (`npm run typecheck`):** 0 errors
- **Frozen File Baseline Check (SHA-256):** 3 / 3 matched 100%

This establishes an authoritative, reproducible baseline.

---

## 2. Test Execution Policy: Focused Checks vs. Regression Gates

To avoid wasteful, repetitive test runs while guaranteeing safety:

1. **Focused Component Checks (During Phase Work):**
   - When modifying a specific module or adding an agent adapter, run **only** the directly affected test suite (e.g. `pytest tests/test_skills_and_shared_memory.py -k <target>`).
2. **Phase Completion Regression Gate (Before Sign-off):**
   - At the completion of each implementation phase (A2 through A7), run the comprehensive cross-phase suite (all 121 tests + new phase tests) **once** to verify zero regressions.
3. **No ASR / Production Render in Automated Testing:**
   - Always run with mock ASR prohibition monkeypatches to prevent triggering local Whisper inference.
   - Use isolated synthetic project fixtures (`test_p10_e2e_synthetic`) with path confinement; **never touch `projects/` user directories during test runs**.

---

## 3. Targeted Test Matrix for Future Implementation Phases

| Phase | Targeted Area | Primary Verification Command | Specific Invariants to Assert |
|---|---|---|---|
| **Phase A2: Laxman Approval** | `backend/approvals/` & `/approvals` UI | `pytest tests/test_laxman_approval.py -v` | 1. Invalid/missing PIN fails closed (`403 Forbidden`).<br>2. Fingerprint tampering marks status `stale`.<br>3. Constant-time comparison matches salted hash.<br>4. Rejection cannot be bypassed. |
| **Phase A3: Execution Convergence** | `backend/orchestrator.py` & route wrappers | `pytest tests/test_orchestrator_and_monitoring.py tests/test_pipeline_gate.py -v` | 1. Legacy `/step/{name}/run` endpoints execute target stage via Orchestrator.<br>2. Checkpoints created atomically.<br>3. 0 regressions on existing step tests. |
| **Phase A4: Frontend Integration** | `frontend/src/` | `npm --prefix frontend run typecheck && npm --prefix frontend test` | 1. `client.ts` methods connect to orchestrator.<br>2. Pipeline page reflects real orchestrator stage states.<br>3. Flowchart SVG renders correctly. |
| **Phase A5: Skill Finder Agent** | `backend/agents/system/skill_finder.py` | `pytest tests/test_skill_finder_agent.py -v` | 1. Queries internal `SkillRegistry` first.<br>2. Staged external candidates are quarantined.<br>3. Static security audit rejects dangerous AST tokens. |
| **Phase A6: Skill Factory Agent** | `backend/agents/system/skill_factory.py` | `pytest tests/test_skill_factory_agent.py -v` | 1. Authors valid `SKILL.md` schema.<br>2. Remotion test render executes without errors.<br>3. Submits promotion request to Laxman Approval. |
| **Phase A7: Cleanup & Release** | Entire repository | Full regression suite (121+ tests) + `npm run typecheck` | 1. Deletion of `dashboard/` and `.claude/worktrees/` causes 0 test failures.<br>2. Final production readiness verified. |

---

## 4. Frozen File Continuous Integrity Gate

Every test run and CI build must execute the automated hash check verifying the 3 frozen files:

```python
FROZEN_BASELINE_HASHES = {
    "backend/transcribe.py": "07a200319d41c2bd1550dfd5704f3bbcc5fac8331a0aeb09dcca4bf46d61376e",
    "backend/transcript_review.py": "7290ea210d922514c011c799caf73aad61398f0229cc6799dd2f10072b38d049",
    "backend/scene_segmentation.py": "2d9ea882b8c53a6cfcd43b048481f72140a1a6792b8f05578e16fd56a9b37042",
}
```
If any SHA-256 differs, the test runner halts immediately before executing any tests.
