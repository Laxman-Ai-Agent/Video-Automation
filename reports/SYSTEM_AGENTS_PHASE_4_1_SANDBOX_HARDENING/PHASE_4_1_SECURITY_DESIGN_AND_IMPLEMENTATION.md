# Phase 4.1 Security Design and Implementation Report
## Skill Factory Sandbox Security Hardening & Fail-Closed Boundary

**Repository:** `E:\audio-to-video`  
**Branch:** `agents-building`  
**Phase:** 4.1 of 10  
**Phase Name:** Skill Factory Sandbox Security Hardening  
**Date:** 2026-10-17  
**Verdict:** `CONDITIONAL — FAIL-CLOSED PROTECTION VERIFIED, ISOLATED EXECUTION NOT YET AVAILABLE`

---

## 1. Executive Summary

Phase 4.1 addresses the foundational execution boundary of the **Skill Factory** (`SYSTEM/agents/skill_factory/`). In Phase 4, candidate skills were executed in temporary directories with basic denylist scrubbing and subprocess timeouts. While effective for well-behaved code, denylists and standard subprocesses do not prevent host credential discovery, child process escape, log flooding denial-of-service, or uncontained host filesystem traversal by arbitrary untrusted code.

Phase 4.1 replaces reactive denylisting with a **rigorous multi-layered security architecture**:
1. **Preflight Capability Detection**: Probes Docker CLI/daemon and Windows Job Object kernel support before attempting execution.
2. **Mandatory Fail-Closed Policy**: If untrusted executable code requires container isolation and Docker is unavailable, the runner strictly fails closed (`status="blocked_isolation"`), preserving source and diagnostics while forbidding unrestricted execution.
3. **Strict Environment Variable Allowlist**: Replaces naive denylists with a strict allowlist (`SYSTEMROOT`, `COMSPEC`, `PATH`, `PATHEXT`, `TEMP`, `TMP`, `PYTHONPATH`, etc.). All parent secrets, API keys, bearer tokens, and credentials are completely omitted.
4. **Windows Job Object Governance & Tree Termination**: On Windows, child processes are attached to a `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` Job Object. When timeouts occur, the entire process tree—including background grandchild workers—is terminated by the Windows kernel.
5. **Workspace Confinement & Path Escape Guards**: Temporary workspaces strictly isolate inputs, code, and temporary files. Symlinks pointing outside the workspace and directory traversal paths trigger `SandboxSecurityError`.
6. **Output Byte Capping**: Standard output and error streams are bounded to 64 KB (`policy.max_output_bytes`) to prevent memory exhaustion and log flooding.
7. **Cryptographic Content-Hash Evidence Binding**: Test results record `tested_content_sha256`. The publisher strictly verifies that candidate content has not been tampered with or modified between behavioral testing and atomic publication.
8. **Lifecycle State Machine Integration**: Adds `BLOCKED_ISOLATION` as a distinct lifecycle state that strictly prevents promotion.

---

## 2. Threat Model & Sandbox Boundaries

| Threat Vector | Prior State (Phase 4) | Hardened State (Phase 4.1) |
| :--- | :--- | :--- |
| **Parent Secret Leakage** | Naive denylist (`clean_env.pop(k)`). Any new or unlisted env var leaked to child. | **Strict Allowlist** (`DEFAULT_ENV_ALLOWLIST`). Child environment built from scratch; only system-critical keys permitted. |
| **Uncontained Execution Fallback** | Fallback to host subprocess if container was missing. | **Mandatory Fail-Closed**. If required isolation backend is missing, returns `status="blocked_isolation"` and blocks promotion. |
| **Orphan Background Descendants** | Child could spawn `Popen` grandchildren surviving timeout. | **Windows Job Object**. Kernel kills entire process tree on timeout (`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` + `TerminateJobObject`). |
| **Memory Denial of Service** | Unbounded stdout/stderr capture leading to OOM. | **Output Capping** (`max_output_bytes=65536`). Output truncated with audit notice. |
| **Post-Test Code Tampering** | Content tested was not cryptographically bound to publication content. | **SHA-256 Evidence Binding**. `tested_content_sha256` verified in `promote_skill`; mismatch aborts publication. |
| **Workspace Escape via Symlinks** | Symlinks inside temp folder could resolve outside sandbox. | **Symlink & Confinement Guards**. `verify_no_symlink_escapes` and `verify_sandbox_path_confinement` check all paths. |
| **Pipeline Tampering** | Checked only during AST validation. | **Baseline Hash Verification**. SHA-256 of all 3 frozen pipeline files verified before and after test execution. |

---

## 3. Architecture & Module Breakdown

### 3.1 Preflight Capability Detector (`sandbox_preflight.py`)
- **Location**: `SYSTEM/agents/skill_factory/sandbox_preflight.py`
- **Functions**:
  - `check_docker_runtime()`: Probes `docker --version` and `docker info` to verify CLI presence and daemon responsiveness.
  - `check_windows_job_objects()`: Probes Windows `kernel32.dll` for `CreateJobObjectW` and `SetInformationJobObject`.
  - `probe_sandbox_capabilities(force_refresh=False) -> SandboxCapabilities`: Caches and returns platform capabilities, active backends, and recommended isolation strategy.
- **Current Host Capabilities**:
  - Platform: `win32` (Windows 64-bit)
  - Docker Available: `False` (Docker CLI not installed on host)
  - Windows Job Objects Available: `True`
  - Available Backends: `['windows_job_object']`
  - Recommended Backend: `windows_job_object`

### 3.2 Security Policy & Confinement Rules (`sandbox_policy.py`)
- **Location**: `SYSTEM/agents/skill_factory/sandbox_policy.py`
- **Constants & Dataclasses**:
  - `DEFAULT_ENV_ALLOWLIST`: Frozenset containing only system-essential keys:
    `{"SYSTEMROOT", "COMSPEC", "PATH", "PATHEXT", "TEMP", "TMP", "PYTHONPATH", "PYTHONDONTWRITEBYTECODE", "PYTHONIOENCODING", "PYTHONUNBUFFERED", "PYTHONUTF8", "LANG", "LC_ALL"}`
  - `SandboxPolicy`: Configures `isolation_backend`, `require_container`, `timeout_seconds`, `max_output_bytes`, `memory_limit_mb`, and `fail_closed_on_missing_backend`.
  - `sanitize_environment(workspace, allowlist)`: Constructs clean dictionary from scratch and routes `TEMP`/`TMP` into `workspace / "tmp"`.
  - `verify_sandbox_path_confinement(target, root)`: Resolves canonical paths and prevents `..` traversal.
  - `verify_no_symlink_escapes(directory, root)`: Traverses tree to block symlink targets resolving outside the workspace.
  - `compute_baseline_hashes()` & `verify_baseline_hashes_unchanged()`: Verifies that frozen pipeline files remain identical bit-for-bit.

### 3.3 Hardened Isolated Test Runner (`test_runner.py`)
- **Location**: `SYSTEM/agents/skill_factory/test_runner.py`
- **Enhancements**:
  - `WindowsJobObject`: Ctypes wrapper for `JOBOBJECT_EXTENDED_LIMIT_INFORMATION` setting `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`.
  - `BehavioralTestResult`: Added `tested_content_sha256` for cryptographic audit.
  - `_resolve_isolation_backend()`: Dispatches to container, job object, or fail-closed `blocked_isolation`.
  - Safe Policy Clones: Avoids in-place mutation of runner default policy via `dataclasses.replace`.
  - Output Limiting: Truncates stdout/stderr exceeding `max_output_bytes`.

### 3.4 Cryptographic Content-Hash Binding in Publisher (`publisher.py`)
- **Location**: `SYSTEM/agents/skill_factory/publisher.py`
- **Enhancements**:
  - `promote_skill` checks `test_result.status != "blocked_isolation"`.
  - `promote_skill` verifies `test_result.passed is True`.
  - `promote_skill` asserts `test_result.tested_content_sha256 == hashlib.sha256(content.encode()).hexdigest()`.
  - Re-checks historical test evidence in `lifecycle.history`.

### 3.5 Lifecycle State Machine (`lifecycle.py`)
- **Location**: `SYSTEM/agents/skill_factory/lifecycle.py`
- **Enhancements**:
  - Added `BLOCKED_ISOLATION` to `LifecycleState`.
  - Added legal transition `TESTING -> BLOCKED_ISOLATION`.
  - `BLOCKED_ISOLATION` mapped to registry status `rejected`.
  - `is_promotable` remains strictly `False` for `BLOCKED_ISOLATION`.

---

## 4. Verification Evidence

The implementation was verified through an adversarial test suite (`test_sandbox_hardening.py`) verifying all 16 security constraints:

1. **Preflight Detection**: Accurately detects win32 Job Objects and Docker absence without crashing.
2. **Container Required Fail-Closed**: `require_container=True` returns `status="blocked_isolation"`.
3. **Invalid Backend Fail-Closed**: `isolation_backend="nonexistent"` returns `status="blocked_isolation"`.
4. **Blocked Promotion Rejection**: `promote_skill` rejects candidates with `status="blocked_isolation"`.
5. **Lifecycle State Invariance**: `BLOCKED_ISOLATION` state blocks promotion transitions.
6. **Secret Leakage Elimination**: Test code verified `TEST_SECRET_API_KEY` is None in child process.
7. **Allowlist Key Purity**: Child process environment confirmed to contain only allowlisted keys.
8. **Job Object Tree Termination**: Grandchild sleep process terminated upon 1.0s timeout.
9. **Output Byte Capping**: 200 KB output safely truncated to 4 KB with audit notice.
10. **Path Confinement Guards**: `../outside.txt` traversal raises `SandboxSecurityError`.
11. **Symlink Escape Guards**: Detected symlinks pointing outside workspace.
12. **Content Hash Binding**: Modified post-test code rejected by `promote_skill`.
13. **Failed Evidence Rejection**: Failed test runs prevent skill promotion.
14. **Declarative Skill Bypass**: Markdown skills safely validated without container overhead.
15. **Frozen File Invariance**: All 3 frozen pipeline files retain exact baseline hashes.
16. **Agent Level Handling**: `SkillFactoryAgent` returns `status="blocked"` for container requests.
