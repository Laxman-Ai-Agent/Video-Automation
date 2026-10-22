# A1 Risk & Rollback Register — Implementation & Operational Safeguards

**Audit ID:** A1-RSK-01  
**Timestamp:** 2026-10-16T14:40:00+05:30  
**Repository Root:** `E:\audio-to-video`  

---

## 1. Risk & Rollback Matrix for Planned Phases

| Risk ID | Risk Description | Likelihood | Impact | Severity | Mitigation Strategy | Rollback Procedure | Owner | Required Approval Gate |
|---|---|---|---|---|---|---|---|---|
| **A1-R-01** | **PIN Bypass via Direct API Call:** Caller invokes underlying render or delivery functions directly, bypassing Laxman Approval PIN verification. | Low | Critical | **High** | Embed PIN verification token check inside `require_approved()` immediately before side-effects; fail closed if authorization token missing. | Revert side-effect wrapper functions; restore original file states via Git. | Security Architect | Laxman Human Approval |
| **A1-R-02** | **Orchestrator Stage-Stepping Regression:** Migrating legacy `/step/{name}/run` to `PipelineOrchestrator` causes timing or schema mismatch with existing frontend pages. | Medium | High | **Medium** | Introduce reversible feature toggle `USE_CANONICAL_ORCHESTRATOR=false`; keep legacy `JobRunner` code intact as fallback during Phase A3/A4. | Set `USE_CANONICAL_ORCHESTRATOR=false` in environment; immediately restores legacy code path without redeployment. | Orchestrator Team | Tech Lead Review |
| **A1-R-03** | **Unintentional Deletion of Required Files during Cleanup:** Deleting `STATUS.json` or other candidates breaks existing test suites (e.g. `test_status.py`). | Medium | High | **High** | Strict candidate policy: zero deletions in A1; require pre-deletion test run and local zip backup in Phase A7. | Restore deleted file from local zip backup or `git checkout HEAD -- <path>`. | DevOps / QA Lead | Laxman Human Approval |
| **A1-R-04** | **Shared Staging Race in Remotion:** Concurrent multi-project renders overwrite files in `remotion/src/generated/`. | Low (single-instance) | High | **Medium** | Enforce `_remotion_staging_lock` process mutex; queue conflicting render requests. | Abort conflicting run; clean `remotion/src/generated/` from project backup. | Rendering Lead | Automated Orchestrator Mutex |
| **A1-R-05** | **Prompt Injection or Dangerous Shell in Discovered Skill:** Candidate skill staged by Skill Finder contains shell commands or token leakage. | Low | Critical | **High** | Mandatory static security audit in `audit_skill_content()`; quarantine in `skills/staging/`; require Laxman PIN approval before promotion. | Transition skill to `status="rejected"`; delete from staging directory. | Security Lead | Laxman Human Approval |
| **A1-R-06** | **Deep Relative Import Breakage on Refactor:** Reorganizing submodules inside `backend/agents/` breaks relative traversal. | High (if moved) | High | **High** | Adopt zero-move policy for existing files; add only additive files under `backend/agents/system/` and `backend/approvals/`. | Revert relative import edits via Git. | Architecture Lead | Tech Lead Review |
| **A1-R-07** | **Frozen File Inadvertent Modification:** Accidental edit to `transcribe.py`, `transcript_review.py`, or `scene_segmentation.py`. | Low | Critical | **High** | Automated pre-commit and pre-test SHA-256 baseline hash assertions. | Restore exact baseline bytes from Git `f6989b17372e3cdb42b4c92ab1783b3122a401ae`. | System Architect | Strict Baseline Lock |

---

## 2. Emergency Recovery & Disaster Rollback Protocol

If any future implementation phase introduces blocking regressions:
1. **Source Code Rollback:** All code changes must be atomic per phase. Revert to stable HEAD (`f6989b17372e3cdb42b4c92ab1783b3122a401ae`) or previous phase completion commit.
2. **Configuration Rollback:** Configuration files (`config/shared_memory.json`, `config/eval_*.json`, `skills/catalog.json`) maintain atomic `.bak` snapshots before write operations.
3. **Execution Flag Fallback:** All architectural transitions (such as execution engine convergence) must provide an environment toggle (`USE_CANONICAL_ORCHESTRATOR=false`) providing instantaneous zero-downtime rollback.
