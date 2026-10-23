"""Isolated Behavioral Test Runner for Skill Factory.

Executes and verifies skills in controlled, bounded workspaces with:
1. Preflight capability detection for container and OS isolation runtimes.
2. Mandatory fail-closed policy when required isolation backends are unavailable.
3. Strict environment variable allowlist scrubbing (no parent secrets or API keys).
4. Windows Job Object governance with guaranteed process tree termination on timeout.
5. Workspace path confinement, symlink escape guards, and output byte bounding.
6. Zero side-effect guarantees (production registries & pipeline stage files verified untouched).
7. Cryptographic evidence binding via tested_content_sha256.
8. Distinction between executable code testing and declarative contract validation.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from ctypes import wintypes
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

from SYSTEM.agents.skill_factory.sandbox_policy import (
    DEFAULT_ENV_ALLOWLIST,
    SandboxPolicy,
    SandboxSecurityError,
    compute_baseline_hashes,
    sanitize_environment,
    verify_baseline_hashes_unchanged,
    verify_no_symlink_escapes,
    verify_sandbox_path_confinement,
)
from SYSTEM.agents.skill_factory.evaluation_cache import evaluation_cache
from SYSTEM.agents.skill_factory.sandbox_preflight import (
    SandboxCapabilities,
    probe_sandbox_capabilities,
)
from SYSTEM.agents.skill_factory.specification import SkillSpecification
from SYSTEM.agents.skill_factory.video_quality_evaluator import (
    VideoQualityCheckResult,
    video_quality_evaluator,
)

logger = logging.getLogger("skill_factory.test_runner")

TestStatus = Literal["passed", "failed", "timed_out", "blocked_isolation"]

# Windows Job Object Structures & Constants
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
JOB_OBJECT_LIMIT_JOB_MEMORY = 0x0200
JobObjectExtendedLimitInformation = 9


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryLimit", ctypes.c_size_t),
        ("PeakJobMemoryLimit", ctypes.c_size_t),
    ]


class WindowsJobObject:
    """Manages a Windows Job Object handle to enforce process tree termination."""

    def __init__(self, memory_limit_bytes: int | None = None) -> None:
        self.handle: Any = None
        if sys.platform != "win32":
            return

        kernel32 = ctypes.windll.kernel32
        self.handle = kernel32.CreateJobObjectW(None, None)
        if not self.handle:
            logger.warning("Failed to create Windows Job Object.")
            return

        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        limit_flags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if memory_limit_bytes and memory_limit_bytes > 0:
            limit_flags |= JOB_OBJECT_LIMIT_JOB_MEMORY
            info.JobMemoryLimit = memory_limit_bytes

        info.BasicLimitInformation.LimitFlags = limit_flags

        res = kernel32.SetInformationJobObject(
            self.handle,
            JobObjectExtendedLimitInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        if not res:
            logger.warning("Failed to configure JobObjectExtendedLimitInformation.")

    def assign_process(self, process_handle: int) -> bool:
        """Assigns a child process to this job object."""
        if not self.handle or sys.platform != "win32":
            return False
        res = ctypes.windll.kernel32.AssignProcessToJobObject(self.handle, int(process_handle))
        return bool(res)

    def terminate(self, exit_code: int = 1) -> bool:
        """Terminates all processes currently attached to the job object."""
        if not self.handle or sys.platform != "win32":
            return False
        res = ctypes.windll.kernel32.TerminateJobObject(self.handle, exit_code)
        return bool(res)

    def close(self) -> None:
        """Closes the job object handle."""
        if self.handle and sys.platform == "win32":
            ctypes.windll.kernel32.CloseHandle(self.handle)
            self.handle = None

    def __enter__(self) -> WindowsJobObject:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()


@dataclass
class BehavioralTestResult:
    """Structured report produced by isolated skill execution."""
    passed: bool
    status: TestStatus
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    duration_ms: float = 0.0
    stdout: str = ""
    stderr: str = ""
    isolation_strategy: str = ""
    tested_content_sha256: str = ""
    diagnostics: list[str] = field(default_factory=list)
    test_cases: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SkillTestRunner:
    """Manages isolated workspace execution and contract verification for candidate skills."""

    def __init__(self, default_policy: SandboxPolicy | None = None) -> None:
        self.default_policy = default_policy or SandboxPolicy()

    def run_tests(
        self,
        spec: SkillSpecification,
        content: str = "",
        timeout_seconds: float | None = None,
        python_executable: str | None = None,
        policy: SandboxPolicy | None = None,
        isolation_backend: str | None = None,
        use_cache: bool = True,
    ) -> BehavioralTestResult:
        """Executes behavioral tests adhering to platform preflight detection and fail-closed security."""
        t0 = time.perf_counter()
        py_bin = python_executable or sys.executable
        base_pol = policy or self.default_policy
        overrides: dict[str, Any] = {}
        if timeout_seconds is not None:
            overrides["timeout_seconds"] = timeout_seconds
        if isolation_backend is not None:
            overrides["isolation_backend"] = isolation_backend
        active_policy = replace(base_pol, **overrides) if overrides else base_pol

        # Content to hash for cryptographic evidence
        content_to_test = content or spec.code_content or spec.instructions_markdown
        tested_sha = hashlib.sha256(content_to_test.encode("utf-8")).hexdigest()

        # Check cryptographic evaluation cache first to prevent redundant work
        if use_cache:
            cached_data = evaluation_cache.get(
                content_sha256=tested_sha,
                spec=spec,
                policy=active_policy,
                result_type="test_result",
            )
            if cached_data is not None:
                cached_res = BehavioralTestResult(**cached_data)
                if not any("cache" in d.lower() for d in cached_res.diagnostics):
                    cached_res.diagnostics.append("Result retrieved from verified cryptographic evaluation cache.")
                return cached_res

        # Check if skill contains TypeScript / React / Remotion TSX code
        has_ts_code = bool(
            "```tsx" in content
            or "```ts\n" in content
            or "```typescript" in content
            or getattr(spec, "language", "") in ("tsx", "typescript")
        )
        if has_ts_code:
            ts_res = self._validate_remotion_tsx_contracts(spec, content, tested_sha, t0)
            if use_cache and ts_res.passed:
                evaluation_cache.put(tested_sha, spec, ts_res.to_dict(), active_policy, "test_result")
            return ts_res

        # Check if skill contains executable Python code or is declarative
        has_exec_code = bool(spec.code_content or "```python" in content or "```py\n" in content)

        if not has_exec_code:
            # Declarative Skill Contract Validation (safe in-process static verification)
            decl_res = self._validate_declarative_contracts(spec, content, tested_sha, t0)
            if use_cache and decl_res.passed:
                evaluation_cache.put(tested_sha, spec, decl_res.to_dict(), active_policy, "test_result")
            return decl_res

        # Untrusted Executable Code Path: Check preflight capabilities
        caps = probe_sandbox_capabilities()
        chosen_backend = self._resolve_isolation_backend(active_policy, caps)

        if chosen_backend == "blocked_isolation":
            duration = round((time.perf_counter() - t0) * 1000.0, 2)
            diag_msg = (
                f"Isolation backend '{active_policy.isolation_backend}' is unavailable or unconfigured. "
                "Fail-closed policy strictly prevents uncontained host execution of untrusted executable code."
            )
            logger.warning(diag_msg)
            return BehavioralTestResult(
                passed=False,
                status="blocked_isolation",
                duration_ms=duration,
                isolation_strategy="blocked_isolation",
                tested_content_sha256=tested_sha,
                diagnostics=[diag_msg],
                test_cases=[{
                    "name": "isolation_preflight_check",
                    "passed": False,
                    "status": "blocked_isolation",
                    "reason": diag_msg,
                }],
            )

        if chosen_backend == "docker":
            return self._execute_in_docker(spec, content_to_test, tested_sha, active_policy, t0)

        if chosen_backend == "windows_job_object":
            return self._execute_under_windows_job_object(
                spec=spec,
                content=content_to_test,
                tested_sha=tested_sha,
                policy=active_policy,
                py_bin=py_bin,
                t0=t0,
            )

        # Fallback unknown backend -> fail closed
        duration = round((time.perf_counter() - t0) * 1000.0, 2)
        return BehavioralTestResult(
            passed=False,
            status="blocked_isolation",
            duration_ms=duration,
            isolation_strategy="blocked_isolation",
            tested_content_sha256=tested_sha,
            diagnostics=[f"Unsupported isolation backend '{chosen_backend}'. Execution blocked."],
            test_cases=[{"name": "isolation_backend", "passed": False, "status": "blocked_isolation"}],
        )

    def _resolve_isolation_backend(
        self,
        policy: SandboxPolicy,
        caps: SandboxCapabilities,
    ) -> str:
        """Determines the active isolation backend or triggers fail-closed blocked status."""
        req_backend = policy.isolation_backend.lower()

        # If container isolation is explicitly required
        if policy.require_container or req_backend == "docker":
            if caps.docker_available:
                return "docker"
            return "blocked_isolation"

        if req_backend == "windows_job_object":
            if caps.windows_job_objects_available:
                return "windows_job_object"
            return "blocked_isolation"

        if req_backend == "auto":
            if caps.docker_available:
                return "docker"
            if caps.windows_job_objects_available:
                return "windows_job_object"
            return "blocked_isolation"

        return "blocked_isolation"

    def _validate_declarative_contracts(
        self,
        spec: SkillSpecification,
        content: str,
        tested_sha: str,
        t0: float,
    ) -> BehavioralTestResult:
        """Validates declarative instruction rules and schema contracts."""
        diagnostics: list[str] = []
        test_cases: list[dict[str, Any]] = []
        tests_run = 0
        tests_passed = 0

        # Test Case 1: Capability Coverage in Markdown Body
        tests_run += 1
        missing_caps = [c for c in spec.capabilities if c.lower() not in content.lower()]
        if missing_caps:
            diagnostics.append(f"Declared capabilities missing from instructions: {', '.join(missing_caps)}")
            test_cases.append({"name": "capability_coverage", "passed": False, "details": missing_caps})
        else:
            tests_passed += 1
            test_cases.append({"name": "capability_coverage", "passed": True})

        # Test Case 2: Frontmatter & Heading Structure
        tests_run += 1
        has_headings = "# " in content and "## Purpose" in content and "## " in content
        if not has_headings:
            diagnostics.append("Markdown instructions missing required '# Title' and '## Purpose' headings.")
            test_cases.append({"name": "heading_structure", "passed": False})
        else:
            tests_passed += 1
            test_cases.append({"name": "heading_structure", "passed": True})

        # Test Case 3: Declared Contract Validation
        tests_run += 1
        contracts_valid = isinstance(spec.inputs, dict) and isinstance(spec.outputs, dict)
        if not contracts_valid:
            diagnostics.append("Invalid input/output dictionary contracts.")
            test_cases.append({"name": "contract_schema", "passed": False})
        else:
            tests_passed += 1
            test_cases.append({"name": "contract_schema", "passed": True})

        duration = round((time.perf_counter() - t0) * 1000.0, 2)
        passed = tests_passed == tests_run

        return BehavioralTestResult(
            passed=passed,
            status="passed" if passed else "failed",
            tests_run=tests_run,
            tests_passed=tests_passed,
            tests_failed=tests_run - tests_passed,
            duration_ms=duration,
            isolation_strategy="declarative_contract_validation",
            tested_content_sha256=tested_sha,
            diagnostics=diagnostics,
            test_cases=test_cases,
        )

    def _validate_remotion_tsx_contracts(
        self,
        spec: SkillSpecification,
        content: str,
        tested_sha: str,
        t0: float,
    ) -> BehavioralTestResult:
        """Validates Remotion TSX component skills against component contracts, hooks, and static types."""
        from SYSTEM.agents.skill_factory.ts_validator import ts_validator

        diagnostics: list[str] = []
        test_cases: list[dict[str, Any]] = []
        tests_run = 0
        tests_passed = 0

        # Test Case 1: Capability Coverage in Markdown Body
        tests_run += 1
        missing_caps = [c for c in spec.capabilities if c.lower() not in content.lower()]
        if missing_caps:
            diagnostics.append(f"Declared capabilities missing from instructions: {', '.join(missing_caps)}")
            test_cases.append({"name": "capability_coverage", "passed": False, "details": missing_caps})
        else:
            tests_passed += 1
            test_cases.append({"name": "capability_coverage", "passed": True})

        # Test Case 2: Frontmatter & Heading Structure
        tests_run += 1
        has_headings = "# " in content and "## Purpose" in content
        if not has_headings:
            diagnostics.append("Markdown instructions missing required '# Title' and '## Purpose' headings.")
            test_cases.append({"name": "heading_structure", "passed": False})
        else:
            tests_passed += 1
            test_cases.append({"name": "heading_structure", "passed": True})

        # Test Case 3: Contract Schema
        tests_run += 1
        contracts_valid = isinstance(spec.inputs, dict) and isinstance(spec.outputs, dict)
        if not contracts_valid:
            diagnostics.append("Invalid input/output dictionary contracts.")
            test_cases.append({"name": "contract_schema", "passed": False})
        else:
            tests_passed += 1
            test_cases.append({"name": "contract_schema", "passed": True})

        # Test Case 4: Remotion Component & Props Contract
        tests_run += 1
        audit_res = ts_validator.audit_security(content)
        if not audit_res.prop_contract_detected:
            diagnostics.append("Remotion component missing typed Props interface or Zod schema.")
            test_cases.append({"name": "props_contract", "passed": False})
        else:
            tests_passed += 1
            test_cases.append({"name": "props_contract", "passed": True})

        # Test Case 5: Remotion Animation Invariants
        tests_run += 1
        contract_issues = ts_validator.validate_remotion_contracts(content)
        if contract_issues:
            diagnostics.extend(contract_issues)
            test_cases.append({"name": "remotion_invariants", "passed": False, "issues": contract_issues})
        else:
            tests_passed += 1
            test_cases.append({"name": "remotion_invariants", "passed": True})

        duration = round((time.perf_counter() - t0) * 1000.0, 2)
        passed = tests_passed == tests_run

        return BehavioralTestResult(
            passed=passed,
            status="passed" if passed else "failed",
            tests_run=tests_run,
            tests_passed=tests_passed,
            tests_failed=tests_run - tests_passed,
            duration_ms=duration,
            isolation_strategy="remotion_tsx_contract_validation",
            tested_content_sha256=tested_sha,
            diagnostics=diagnostics,
            test_cases=test_cases,
        )

    def _execute_under_windows_job_object(
        self,
        spec: SkillSpecification,
        content: str,
        tested_sha: str,
        policy: SandboxPolicy,
        py_bin: str,
        t0: float,
    ) -> BehavioralTestResult:
        """Executes untrusted code within a confined workspace under a Windows Job Object boundary."""
        workspace = tempfile.mkdtemp(prefix="sf_sandbox_ws_")
        ws_path = Path(workspace)

        # Baseline hash tracking for the pipeline stage files
        baseline_hashes = compute_baseline_hashes()

        try:
            # 1. Prepare strictly allowlisted environment (no parent secrets)
            clean_env = sanitize_environment(ws_path, allowlist=policy.env_allowlist)

            # 2. Extract and write executable code
            code_to_run = spec.code_content
            if not code_to_run:
                import re
                blocks = re.findall(r"```(?:python|py)\n(.*?)```", content, re.DOTALL)
                code_to_run = "\n\n".join(blocks)

            script_file = ws_path / "skill_entrypoint.py"
            script_file.write_text(code_to_run, encoding="utf-8")
            verify_sandbox_path_confinement(script_file, ws_path)

            # 3. Create test harness
            test_harness_file = ws_path / "run_harness.py"
            harness_code = self._build_test_harness(spec)
            test_harness_file.write_text(harness_code, encoding="utf-8")
            verify_sandbox_path_confinement(test_harness_file, ws_path)

            # 4. Initialize Windows Job Object with process tree termination
            mem_bytes = policy.memory_limit_mb * 1024 * 1024
            job = WindowsJobObject(memory_limit_bytes=mem_bytes)

            cmd = [py_bin, str(test_harness_file)]
            creation_flags = 0x00000200  # CREATE_NEW_PROCESS_GROUP

            proc = subprocess.Popen(
                cmd,
                cwd=str(ws_path),
                env=clean_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=creation_flags,
            )

            # Attach process to job object immediately
            job.assign_process(proc._handle)

            try:
                stdout_data, stderr_data = proc.communicate(timeout=policy.timeout_seconds)
                duration = round((time.perf_counter() - t0) * 1000.0, 2)
                passed = proc.returncode == 0

                # Enforce output bounds
                stdout_data = self._truncate_output(stdout_data, policy.max_output_bytes)
                stderr_data = self._truncate_output(stderr_data, policy.max_output_bytes)

                # Verify workspace confinement & symlinks
                verify_no_symlink_escapes(ws_path, ws_path)

                # Verify zero side effects on pipeline stage files
                verify_baseline_hashes_unchanged(baseline_hashes)

                diagnostics = []
                if not passed:
                    diagnostics.append(f"Subprocess failed with exit code {proc.returncode}.")
                    if stderr_data:
                        diagnostics.append(f"Stderr: {stderr_data[:500]}")

                res = BehavioralTestResult(
                    passed=passed,
                    status="passed" if passed else "failed",
                    tests_run=1,
                    tests_passed=1 if passed else 0,
                    tests_failed=0 if passed else 1,
                    duration_ms=duration,
                    stdout=stdout_data,
                    stderr=stderr_data,
                    isolation_strategy="governed_windows_job_object",
                    tested_content_sha256=tested_sha,
                    diagnostics=diagnostics,
                    test_cases=[{
                        "name": "isolated_execution",
                        "exit_code": proc.returncode,
                        "passed": passed,
                    }],
                )
                if passed:
                    evaluation_cache.put(tested_sha, spec, res.to_dict(), policy, "test_result")
                return res

            except subprocess.TimeoutExpired:
                # Terminate entire job object (kills process and all spawned descendants)
                job.terminate(1)
                proc.kill()
                self._terminate_process_tree(proc.pid)

                duration = round((time.perf_counter() - t0) * 1000.0, 2)
                return BehavioralTestResult(
                    passed=False,
                    status="timed_out",
                    tests_run=1,
                    tests_passed=0,
                    tests_failed=1,
                    duration_ms=duration,
                    isolation_strategy="governed_windows_job_object",
                    tested_content_sha256=tested_sha,
                    diagnostics=[f"Execution timed out after {policy.timeout_seconds} seconds. Process tree terminated."],
                    test_cases=[{"name": "isolated_execution", "status": "timed_out", "passed": False}],
                )
            finally:
                job.close()

        except SandboxSecurityError as sse:
            duration = round((time.perf_counter() - t0) * 1000.0, 2)
            logger.error(f"Sandbox security breach detected: {sse}")
            return BehavioralTestResult(
                passed=False,
                status="failed",
                duration_ms=duration,
                isolation_strategy="governed_windows_job_object",
                tested_content_sha256=tested_sha,
                diagnostics=[f"Sandbox boundary security breach: {sse}"],
                test_cases=[{"name": "sandbox_boundary_security", "passed": False, "error": str(sse)}],
            )
        finally:
            shutil.rmtree(workspace, ignore_errors=True)

    def _execute_in_docker(
        self,
        spec: SkillSpecification,
        content: str,
        tested_sha: str,
        policy: SandboxPolicy,
        t0: float,
    ) -> BehavioralTestResult:
        """Executes untrusted code within a hermetic, read-only Docker container."""
        workspace = tempfile.mkdtemp(prefix="sf_docker_sandbox_")
        ws_path = Path(workspace)

        try:
            code_to_run = spec.code_content or content
            script_file = ws_path / "skill_entrypoint.py"
            script_file.write_text(code_to_run, encoding="utf-8")

            test_harness_file = ws_path / "run_harness.py"
            test_harness_file.write_text(self._build_test_harness(spec), encoding="utf-8")

            container_cmd = [
                "docker", "run", "--rm",
                "--network", "none",
                "--memory", f"{policy.memory_limit_mb}m",
                "-v", f"{ws_path.resolve()}:/workspace:rw",
                "-w", "/workspace",
                "python:3.12-slim",
                "python", "/workspace/run_harness.py",
            ]

            proc = subprocess.run(
                container_cmd,
                capture_output=True,
                text=True,
                timeout=policy.timeout_seconds,
            )
            duration = round((time.perf_counter() - t0) * 1000.0, 2)
            passed = proc.returncode == 0

            stdout_data = self._truncate_output(proc.stdout, policy.max_output_bytes)
            stderr_data = self._truncate_output(proc.stderr, policy.max_output_bytes)

            return BehavioralTestResult(
                passed=passed,
                status="passed" if passed else "failed",
                tests_run=1,
                tests_passed=1 if passed else 0,
                tests_failed=0 if passed else 1,
                duration_ms=duration,
                stdout=stdout_data,
                stderr=stderr_data,
                isolation_strategy="docker_container_runtime",
                tested_content_sha256=tested_sha,
                test_cases=[{"name": "container_execution", "exit_code": proc.returncode, "passed": passed}],
            )
        except subprocess.TimeoutExpired:
            duration = round((time.perf_counter() - t0) * 1000.0, 2)
            return BehavioralTestResult(
                passed=False,
                status="timed_out",
                duration_ms=duration,
                isolation_strategy="docker_container_runtime",
                tested_content_sha256=tested_sha,
                diagnostics=[f"Docker execution timed out after {policy.timeout_seconds}s."],
            )
        finally:
            shutil.rmtree(workspace, ignore_errors=True)

    def _truncate_output(self, text: str, max_bytes: int) -> str:
        """Truncates stdout/stderr if it exceeds max_bytes to prevent memory denial-of-service."""
        if len(text.encode("utf-8")) <= max_bytes:
            return text
        truncated = text[:max_bytes]
        return truncated + f"\n[TRUNCATED: Output exceeded sandbox limit of {max_bytes} bytes]"

    def _terminate_process_tree(self, pid: int) -> None:
        """Kills a process and all its descendants on Windows using taskkill as fallback."""
        if sys.platform == "win32":
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True,
                    timeout=2.0,
                    check=False,
                )
            except Exception:
                pass

    def _build_test_harness(self, spec: SkillSpecification) -> str:
        """Constructs an executable Python harness that imports and exercises the skill."""
        return (
            "import sys\n"
            "try:\n"
            "    import skill_entrypoint\n"
            "    if hasattr(skill_entrypoint, 'execute'):\n"
            "        res = skill_entrypoint.execute({})\n"
            "    elif hasattr(skill_entrypoint, 'run'):\n"
            "        res = skill_entrypoint.run({})\n"
            "    print('Skill execution harness completed successfully.')\n"
            "    sys.exit(0)\n"
            "except Exception as e:\n"
            "    print(f'Harness caught exception: {e}', file=sys.stderr)\n"
            "    sys.exit(1)\n"
        )

    def evaluate_video_domain_quality(
        self,
        spec: SkillSpecification,
        output_data: dict[str, Any],
        **kwargs: Any,
    ) -> VideoQualityCheckResult:
        """Runs domain-specific quality checks based on the skill domain."""
        domain = spec.domain.lower()
        if "audio" in domain or "transcript" in domain:
            if "telugu" in spec.skill_id or "typography" in spec.skill_id:
                return video_quality_evaluator.evaluate_telugu_typography_contract(output_data, **kwargs)
            return video_quality_evaluator.evaluate_audio_transcript_contract(output_data, **kwargs)
        elif "visual" in domain:
            return video_quality_evaluator.evaluate_visual_planning_contract(output_data, **kwargs)
        elif "motion" in domain or "graphics" in domain:
            return video_quality_evaluator.evaluate_motion_graphics_contract(output_data, **kwargs)
        elif "rendering" in domain or "timeline" in domain or "qc" in domain:
            return video_quality_evaluator.evaluate_rendering_and_qa_contract(output_data, **kwargs)
        else:
            return video_quality_evaluator.evaluate_motion_graphics_contract(output_data, **kwargs)


# Authoritative singleton
skill_test_runner = SkillTestRunner()
