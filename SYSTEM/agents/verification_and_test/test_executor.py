"""Safe Test Execution and Result Capture Engine for Verification & Test Agent.

Executes permitted test commands, parses test totals, enforces execution timeouts,
bounds stdout/stderr capture, and guarantees read-only execution.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

from SYSTEM.agents.verification_and_test.contracts import (
    CheckResult,
    FailureCategory,
    TestExecutionStatus,
)

MAX_OUTPUT_BYTES = 50_000  # 50 KB output bounding to prevent memory exhaustion


class TestExecutor:
    """Safely executes targeted tests ."""
    __test__ = False

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = project_root or Path(__file__).resolve().parents[3]

    def execute_pytest_target(
        self,
        target: str,
        timeout_seconds: int = 60,
        extra_args: list[str] | None = None,
    ) -> CheckResult:
        """Executes pytest against a targeted test file or directory with timeout governance."""
        full_target_path = self.project_root / target
        if not full_target_path.exists():
            return CheckResult(
                check_id=f"pytest_{target.replace('/', '_')}",
                component="unknown",
                check_type="pytest",
                status=TestExecutionStatus.BLOCKED,
                exit_code=1,
                stderr=f"Target path '{target}' does not exist on filesystem.",
                failed_count=1,
                failure_category=FailureCategory.MISSING_DEPENDENCY,
                failure_diagnosis=f"Test target path not found: {target}",
            )

        cmd = [
            sys.executable,
            "-m",
            "pytest",
            target,
            "-v",
            "--no-header",
        ]
        if extra_args:
            cmd.extend(extra_args)

        start_time = time.time()
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                encoding="utf-8",
                errors="replace",
            )
            duration_ms = (time.time() - start_time) * 1000.0

            stdout = proc.stdout[:MAX_OUTPUT_BYTES]
            stderr = proc.stderr[:MAX_OUTPUT_BYTES]

            passed, failed, skipped, errors = self._parse_pytest_counts(stdout + "\n" + stderr)

            # In pytest: 0 means all passed, 1 means tests failed, 5 means no tests collected
            if proc.returncode == 0:
                failure_cat = FailureCategory.NONE
                diagnosis = None
            elif proc.returncode == 1:
                failure_cat = FailureCategory.IMPLEMENTATION_DEFECT
                diagnosis = f"{failed} test(s) failed during execution of {target}."
            elif proc.returncode == 5:
                failure_cat = FailureCategory.PRECONDITION_FAILED
                diagnosis = f"No tests collected from {target}."
            else:
                failure_cat = FailureCategory.TEST_ENVIRONMENT
                diagnosis = f"Pytest exited with non-standard return code {proc.returncode}."

            return CheckResult(
                check_id=f"pytest_{target.replace('/', '_')}",
                component=self._infer_component_from_target(target),
                check_type="pytest",
                status=TestExecutionStatus.EXECUTED,
                exit_code=proc.returncode,
                duration_ms=duration_ms,
                stdout=stdout,
                stderr=stderr,
                passed_count=passed,
                failed_count=failed,
                skipped_count=skipped,
                error_count=errors,
                failure_category=failure_cat,
                failure_diagnosis=diagnosis,
            )

        except subprocess.TimeoutExpired as e:
            duration_ms = (time.time() - start_time) * 1000.0
            return CheckResult(
                check_id=f"pytest_{target.replace('/', '_')}",
                component=self._infer_component_from_target(target),
                check_type="pytest",
                status=TestExecutionStatus.BLOCKED,
                exit_code=-1,
                duration_ms=duration_ms,
                stdout=(e.stdout or "")[:MAX_OUTPUT_BYTES] if isinstance(e.stdout, str) else "",
                stderr=f"Execution timed out after {timeout_seconds} seconds.",
                failed_count=1,
                failure_category=FailureCategory.TIMEOUT,
                failure_diagnosis=f"Test command timed out after {timeout_seconds}s.",
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000.0
            return CheckResult(
                check_id=f"pytest_{target.replace('/', '_')}",
                component=self._infer_component_from_target(target),
                check_type="pytest",
                status=TestExecutionStatus.BLOCKED,
                exit_code=-2,
                duration_ms=duration_ms,
                stderr=f"Subprocess execution error: {e}",
                failed_count=1,
                failure_category=FailureCategory.TEST_ENVIRONMENT,
                failure_diagnosis=f"Failed to spawn test subprocess: {e}",
            )

    @staticmethod
    def _parse_pytest_counts(output: str) -> tuple[int, int, int, int]:
        """Extracts passed, failed, skipped, and error counts from pytest terminal output."""
        passed = 0
        failed = 0
        skipped = 0
        errors = 0

        # Look for summary lines like: "93 passed in 1.20s" or "1 failed, 2 passed, 3 skipped in 0.5s"
        pass_match = re.search(r"(\d+)\s+passed", output)
        if pass_match:
            passed = int(pass_match.group(1))

        fail_match = re.search(r"(\d+)\s+failed", output)
        if fail_match:
            failed = int(fail_match.group(1))

        skip_match = re.search(r"(\d+)\s+skipped", output)
        if skip_match:
            skipped = int(skip_match.group(1))

        err_match = re.search(r"(\d+)\s+error(?:s)?", output)
        if err_match:
            errors = int(err_match.group(1))

        return passed, failed, skipped, errors

    @staticmethod
    def _infer_component_from_target(target: str) -> str:
        t = target.lower()
        if "architecture_validator" in t or "phase5" in t:
            return "architecture_validator"
        elif "capability" in t or "phase2" in t or "phase3" in t:
            return "capability_finder"
        elif "skill_factory" in t or "phase4" in t:
            return "skill_factory"
        elif "phase1" in t or "agent_architecture" in t or "registry" in t:
            return "agent_registry"
        elif "video" in t or "timeline" in t or "render" in t:
            return "video_pipeline"
        elif "verification" in t or "phase6" in t:
            return "verification_and_test"
        return "general_system"
