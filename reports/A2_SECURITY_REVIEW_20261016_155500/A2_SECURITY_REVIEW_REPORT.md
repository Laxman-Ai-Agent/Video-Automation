# Phase A2 Final Security Review Report — Minimal Fixes Only

**Review Date**: 2026-10-16 15:55:00 UTC  
**Target Repository**: `E:\audio-to-video`  
**Git Branch**: `agents-building` (HEAD: `f6989b17372e3cdb42b4c92ab1783b3122a401ae`)  
**Scope**: Focused security review and minimal hardening of Phase A2 Laxman Approval implementation.

---

## Executive Summary

A comprehensive, focused security audit of the Laxman Approval subsystem was conducted in accordance with Phase A2 security requirements. Two specific security enhancements were identified and applied:

1. **Elimination of Plaintext PIN in CLI Arguments**:
   - `scripts/set_laxman_pin.py` previously supported optional `--pin` and `--confirm` command-line flags. Accepting sensitive secrets as CLI arguments exposes plaintext PINs in the operating system's process table (e.g., `Get-Process`, `ps`, `/proc`), terminal command history, and shell logging.
   - **Remediation**: The CLI argument flags were removed. `scripts/set_laxman_pin.py` now exclusively uses masked terminal input (`getpass.getpass()`) with an automated fallback for secure piped standard input, eliminating process-argument and history leakage.

2. **Universal PIN Authorization for All Protected State Changes**:
   - `backend/approvals/approval_engine.py:decide()` previously enforced PIN verification exclusively for `approved` decisions, while allowing unauthenticated callers to issue `rejected` or `changes_requested` decisions with only a reason string. This opened a denial-of-service / state disruption vector where unauthenticated actors could reject or disrupt in-flight approvals.
   - **Remediation**: Moved `pin_service.verify_pin(pin)` to execute unconditionally at the beginning of `ApprovalEngine.decide()`. Every human operator decision (`approved`, `rejected`, `changes_requested`) now strictly requires a valid 6-8 digit Laxman PIN. The frontend modal (`LaxmanApprovalPage.tsx`) was updated to render the masked PIN field for all decision types.

All 18 backend unit/integration tests and 8 frontend component tests passed cleanly, and frozen file invariants were 100% verified.

---

## 1. PIN Setup & Storage Security Audit

### 1.1 CLI Argument & Process Table Hardening (`scripts/set_laxman_pin.py`)
- **Vulnerability Checked**: CLI flags `--pin` and `--confirm` exposed plaintext credentials to process monitoring tools (`Get-CimInstance Win32_Process`, Task Manager, shell logs).
- **Hardening Applied**:
  - Removed `argparse` CLI options for `--pin` and `--confirm`.
  - Implemented secure input reader `_read_masked()`:
    - Interactive TTY: prompts via `getpass.getpass()` without terminal echo.
    - Piped / non-interactive stdin: reads directly from standard input stream without CLI argv exposure.
  - Zero plaintext secrets appear in `sys.argv`.

### 1.2 Cryptographic Key Derivation & Constant-Time Verification (`backend/approvals/pin_service.py`)
- **Algorithm**: Salted PBKDF2 with SHA-256 (`hashlib.pbkdf2_hmac("sha256", ...)`).
- **Iteration Count**: 100,000 iterations.
- **Salt Generation**: 32 cryptographically secure pseudo-random bytes (`os.urandom(32)`).
- **Comparison**: Constant-time verification using `hmac.compare_digest(stored_hash, candidate_hash)` preventing timing attack side-channels.
- **File System Permissions & Git Exclusion**:
  - Hash file location: `config/.laxman_pin_hash`.
  - Exclusion: Explicitly ignored on line 29 of `.gitignore` (`config/.laxman_pin_hash`). Confirmed untracked and ignored via `git status -s --ignored`.
  - Atomic persistence: Writes to `.tmp` file and atomically replaces destination.
- **Fail-Closed Behavior**:
  - If the hash file is missing: raises `PinNotConfiguredError`.
  - If corrupted or invalid JSON: raises `PinSecurityError` (fail-closed, never permits open access).
- **Rate Limiting & Lockout**:
  - In-memory rolling rate limiter (`RateLimiter`): maximum 5 failed attempts per 15-minute window (`max_attempts=5, window_seconds=900`).
  - Upon 5th consecutive failure: status transitions to `locked=True`, raising `PinLockoutError` for all subsequent attempts until the lockout expires.

---

## 2. Approval API Authorization Audit

### 2.1 Backend Decision Enforcement (`backend/approvals/approval_engine.py`)
- **Inspection**:
  - Reviewed `ApprovalEngine.decide()`.
  - Previously, `if decision == "approved":` encapsulated the PIN check.
  - Hardened implementation:
    ```python
    # Strict PIN verification required for any human decision altering protected state
    try:
        verified, err_msg = pin_service.verify_pin(pin)
        if not verified:
            self._append_audit_event_unlocked(
                "approval_pin_failed",
                {"request_id": request_id, "action_type": req.action_type, "decision": decision, "error": err_msg},
            )
            raise ApprovalAuthError(f"Authorization refused: {err_msg}")
    except (PinLockoutError, PinNotConfiguredError) as e:
        self._append_audit_event_unlocked(
            "approval_auth_blocked",
            {"request_id": request_id, "decision": decision, "reason": type(e).__name__},
        )
        raise ApprovalAuthError(str(e))
    ```
- **Rationale Enforced**:
  - `rejected` requires a non-empty human rationale string (HTTP 422 if empty).
  - `changes_requested` requires structured change feedback (HTTP 422 if empty).
  - Both require valid PIN authentication (HTTP 403 `ApprovalAuthError` if missing or incorrect).

### 2.2 FastAPI Route Security (`backend/routes/approvals.py`)
- `POST /approvals/{request_id}/decide`:
  - Validates `ApprovalDecisionPayload` containing `decision`, `pin`, and optional `reason`.
  - Catches `ApprovalAuthError` and maps to HTTP 403 Forbidden with sanitized detail `"Authorization refused: Incorrect PIN"`.
  - Never leaks hashes, salts, or internal exception stack traces.

### 2.3 Frontend Operator UI (`frontend/src/pages/LaxmanApprovalPage.tsx`)
- In `LaxmanApprovalPage`:
  - `handleSubmitDecision()` enforces 6-8 numeric digit client validation for `approve`, `reject`, and `changes`.
  - Decision modals for Reject and Request Changes now render the masked password input field.
  - Clears `pinInput` in state immediately upon modal close or completion.

---

## 3. Cryptographic Fingerprint Binding & Replay Prevention

### 3.1 Action Fingerprint Generation
- `compute_action_fingerprint()` hashes `action_type`, `project_id`, and canonical JSON payload using SHA-256:
  $$\text{Fingerprint} = \text{SHA256}(\text{action\_type} \parallel \text{project\_id} \parallel \text{json.dumps(payload, sort\_keys=True)})$$
- Any modification to scene counts, composition SHAs, or upstream assets changes the fingerprint.

### 3.2 Single-Use Consumption (`backend/approvals/guard.py` & `ApprovalEngine.consume_approval()`)
- Before executing any protected side-effect (e.g. video rendering, candidate promotion):
  - `require_approved_action(request_id, expected_fingerprint)` is invoked.
  - Verifies status is strictly `"approved"`.
  - Verifies approved fingerprint matches current upstream state.
  - Transitions status to `"consumed"` and records `consumed_at`.
  - Replay attempts immediately fail with `ApprovalGuardError(code="approval_not_approved")`.

### 3.3 Dynamic Invalidation on Upstream Change
- If `consume_approval()` detects a fingerprint mismatch:
  - Automatically transitions request status to `"stale"`.
  - Logs `approval_consumption_rejected_stale` to the audit log.
  - Raises `ApprovalGuardError(code="approval_stale")`, blocking execution.

---

## 4. Audit Trail & Secret Redaction Audit

### 4.1 Redaction Implementation (`backend/approvals/approval_engine.py:_append_audit_event_unlocked`)
- Every audit record passes through secret sanitization:
  ```python
  sanitized = {}
  for k, v in details.items():
      if "pin" in k.lower() or "secret" in k.lower() or "salt" in k.lower():
          sanitized[k] = "***REDACTED***"
      else:
          sanitized[k] = v
  ```
- Verified via `test_audit_trail_logging_and_redaction`:
  - The plaintext PIN `"123456"` was confirmed absent from the append-only audit file `config/approvals_audit.jsonl`.
  - In `approval_pin_failed` events, failure reasons are logged without recording the supplied candidate PIN.

---

## 5. Verification Test Results

### 5.1 Backend Approval Tests
```powershell
.\.venv\Scripts\python.exe -m pytest -v tests/test_laxman_approval.py
```
**Results**: **18 passed, 0 failed in 21.94s**
- `test_pin_format_validation`: PASSED
- `test_pin_setup_mismatch_and_format_errors`: PASSED
- `test_pin_setup_creates_salted_hash`: PASSED
- `test_pin_verification_success_and_failure`: PASSED
- `test_unconfigured_pin_fails_closed`: PASSED
- `test_corrupt_pin_store_fails_closed`: PASSED
- `test_rate_limiting_and_lockout`: PASSED
- `test_submit_and_retrieve_request`: PASSED
- `test_idempotent_submission`: PASSED
- `test_approve_with_valid_pin`: PASSED
- `test_approve_with_invalid_pin_raises_auth_error`: PASSED
- `test_reject_and_request_changes`: PASSED (verified PIN required for reject/changes)
- `test_consume_approval_and_replay_protection`: PASSED
- `test_fingerprint_mismatch_marks_stale_and_blocks`: PASSED
- `test_audit_trail_logging_and_redaction`: PASSED
- `test_api_status_endpoint`: PASSED
- `test_api_request_lifecycle`: PASSED (tested approve and reject via API with PIN)
- `test_eval_adapter_submission`: PASSED

### 5.2 Frontend Typecheck
```powershell
npm --prefix frontend run typecheck
```
**Results**: **0 errors (Exit code 0)**

### 5.3 Frontend Unit Tests
```powershell
npm --prefix frontend test -- tests/laxman_approval_page.test.tsx
```
**Results**: **8 passed, 0 failed in 4.69s**
- `renders page title and configured status with pending queue`: PASSED
- `displays prominent warning when PIN is not configured`: PASSED
- `displays security lockout banner when rate-limited`: PASSED
- `opens PIN modal and validates 6-8 digit input on approve`: PASSED
- `requires PIN and reason when rejecting a request`: PASSED
- `requires PIN and instructions when requesting changes`: PASSED
- `displays stale indicator for invalidated requests`: PASSED
- `switches to audit trail tab and displays recorded events`: PASSED

### 5.4 Regression Test Suites
```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_timeline_render_qc_delivery.py
```
**Results**: **12 passed in 2.52s**

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_agent_routes.py tests/test_agent_runtime_and_communication.py tests/test_skills_and_shared_memory.py tests/test_evaluation_and_self_learning.py
```
**Results**: **41 passed in 8.01s**

---

## 6. Frozen Files & Repository Safety Audit

### 6.1 Frozen File Bit-Level Hashes
Verified using `Get-FileHash -Algorithm SHA256`:
| File | Expected SHA-256 | Actual SHA-256 | Status |
|---|---|---|---|
| `backend/transcribe.py` | `07a200319d41c2bd1550dfd5704f3bbcc5fac8331a0aeb09dcca4bf46d61376e` | `07A200319D41C2BD1550DFD5704F3BBCC5FAC8331A0AEB09DCCA4BF46D61376E` | **MATCH (UNTOUCHED)** |
| `backend/transcript_review.py` | `7290ea210d922514c011c799caf73aad61398f0229cc6799dd2f10072b38d049` | `7290EA210D922514C011C799CAF73AAD61398F0229CC6799DD2F10072B38D049` | **MATCH (UNTOUCHED)** |
| `backend/scene_segmentation.py` | `2d9ea882b8c53a6cfcd43b048481f72140a1a6792b8f05578e16fd56a9b37042` | `2D9EA882B8C53A6CFCD43B048481F72140A1A6792B8F05578E16FD56A9B37042` | **MATCH (UNTOUCHED)** |

### 6.2 Git Cleanliness & Operational Boundaries
- **No Git commits performed**.
- **No Git resets, checkouts, or cleans performed**.
- **No ASR models executed**.
- **No real video rendering or media generation triggered**.

---

## 7. Status & Sign-Off

The security review and minimal fixes are complete. The Laxman Approval subsystem is fully secured with:
1. Masked PIN setup without command-line parameter leakage.
2. Mandatory PIN verification across all human decision paths (`approved`, `rejected`, `changes_requested`).
3. Single-use consumption and automatic stale invalidation.
4. Comprehensive append-only audit trail with secret redaction.

**Execution halted. Awaiting explicit user approval before proceeding to Phase A3.**
