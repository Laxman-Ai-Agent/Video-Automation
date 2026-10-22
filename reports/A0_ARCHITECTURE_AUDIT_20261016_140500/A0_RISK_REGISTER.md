# A0 Risk Register — Architectural, Operational & Concurrency Risks

**Audit ID:** A0-RISK-01  
**Timestamp:** 2026-10-16T14:15:00+05:30  
**Repository Root:** `E:\audio-to-video`  

---

## 1. Risk Matrix

| Risk ID | Description | Evidence | Probability | Impact | Severity | Mitigation | Owner | Recommended Phase | Status |
|---|---|---|---|---|---|---|---|---|---|
| **A0-R-001** | **Shared Staging Race Condition:** Remotion compiles generated TSX from `remotion/src/generated/`. While an in-process mutex exists, concurrent multi-process workers would overwrite files. | `backend/motion_animation.py:39` (`_remotion_staging_lock`) | Medium | High | **High** | Maintain single-worker execution on port 8000; design isolated temporary Remotion project roots for future scaling. | Architecture Lead | A1 / A3 | Open |
| **A0-R-002** | **Self-Declared Approver Spoofing:** Human approval records use unauthenticated text strings without cryptographic signature or token verification. | `backend/timeline_approval.py:12` ("recorded as self_declared") | Low | High | **Medium** | Implement Laxman Approval central authorization with session token or API key authentication. | Security / Governance | A2 | Open |
| **A0-R-003** | **Dual Pipeline Runner Drift:** Coexistence of legacy step-graph runner (`jobs.py` / `pipeline.py`) and canonical orchestrator (`orchestrator.py`) leads to confusing routes and maintenance overhead. | `backend/routes/pipeline.py` vs `backend/routes/orchestrator.py` | High | Medium | **Medium** | Plan phased migration of frontend stage triggers to canonical orchestrator routes. | Orchestrator Team | A1 / A4 | Open |
| **A0-R-004** | **Host Chromium Dependency:** Remotion requires a working headless Chrome/Chromium installation. If host Chrome path changes or is missing in Docker, render fails closed. | `backend/orchestrator.py:find_browser_executable()` | Low (on host) / High (in container) | High | **High** | Ensure Dockerfile installs `google-chrome-stable` or `chromium`; document in operator runbooks. | DevOps / Operator | Current (Documented) | Mitigated |
| **A0-R-005** | **Untrusted External Code Execution via Skills:** Discovering or installing external skills from GitHub/npm without sandboxing could expose system to prompt injection or shell exploit. | `backend/skill_registry.py` | Low (remote deferred) | Critical | **High** | Keep remote discovery in quarantine (`skills/staging/`); require static security scan and explicit human approval before promotion. | Security Lead | A5 / A6 | Controlled |
| **A0-R-006** | **Deep Relative Import Breakage on Refactor:** Extensive use of `from ... import` in `backend/agents/adapters/stage_adapters.py` makes broad physical folder moves risky. | `backend/agents/adapters/stage_adapters.py:1013` | High | High | **High** | Favor logical classification and module aliasing over mass physical relocation into new root directories. | Architecture Lead | A1 | Open |
| **A0-R-007** | **Memory/Token Cost Runaway:** High LLM token consumption across multi-stage generation and bounded repair loops. | `backend/llm_usage.py`, `config/llm_usage.json` | Medium | Medium | **Medium** | Enforce bounded repair loops (max 3 attempts); monitor cumulative INR costs via `llm_usage.py` dashboard. | LLM Gateway Team | Current (Monitored) | Mitigated |
| **A0-R-008** | **Accidental Modification of Frozen Stages:** Editing `transcribe.py`, `transcript_review.py`, or `scene_segmentation.py` breaks Telugu preservation baselines. | Frozen baseline SHA-256 checks in all test suites | Low | Critical | **High** | Keep frozen policy active; enforce automated pre-test hash verification in CI/CD and tests. | System Architect | Continuous | Enforced |

---

## 2. Summary & Residual Risk Assessment

The primary operational and architectural risks are:
1. **Shared staging directory in Remotion:** Mitigated for local development by `_remotion_staging_lock`, but requires isolation before horizontal scaling.
2. **Dual execution paths:** Coexistence of legacy `jobs.py` and canonical `orchestrator.py` requires careful convergence in A1/A4 so that the user interface seamlessly controls the robust DAG orchestrator.
3. **External skill security:** Fully controlled by maintaining the quarantine-first and human-approval-only policy for any future Skill Finder integrations.
