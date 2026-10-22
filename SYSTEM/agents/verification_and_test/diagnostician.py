"""Failure Diagnostician for Verification & Test Agent.

Groups test failures by affected component and root cause category, distinguishing
implementation defects from test-environment, dependency, or service issues.
Guarantees strictly read-only analysis without attempting code modification.
"""
from __future__ import annotations

import re
from typing import Any

from SYSTEM.agents.verification_and_test.contracts import (
    CheckResult,
    FailureCategory,
    FailureDiagnosis,
)


class Diagnostician:
    """Analyzes test and check failures to attribute root causes and suggest minimal diagnostics."""

    def diagnose_failures(self, checks: list[CheckResult]) -> list[FailureDiagnosis]:
        """Processes failing checks and produces structured diagnostic attributions."""
        diagnoses: list[FailureDiagnosis] = []

        for check in checks:
            if check.is_successful:
                continue

            category = self._classify_failure(check)
            summary = check.failure_diagnosis or f"Check '{check.check_id}' failed with exit code {check.exit_code}."
            hints = self._extract_root_cause_hints(check)
            diagnostics = self._suggest_diagnostics(check)

            diagnoses.append(
                FailureDiagnosis(
                    check_id=check.check_id,
                    component=check.component,
                    category=category,
                    summary=summary,
                    root_cause_hints=hints,
                    suggested_diagnostics=diagnostics,
                )
            )

        return diagnoses

    def _classify_failure(self, check: CheckResult) -> FailureCategory:
        if check.failure_category != FailureCategory.NONE:
            return check.failure_category

        combined_text = (check.stdout + "\n" + check.stderr).lower()

        if "hash mismatch" in combined_text or "tamper" in combined_text:
            return FailureCategory.INTEGRITY_TAMPER
        elif "modulenotfounderror" in combined_text or "no module named" in combined_text:
            return FailureCategory.MISSING_DEPENDENCY
        elif "connectionerror" in combined_text or "service unavailable" in combined_text:
            return FailureCategory.SERVICE_UNAVAILABLE
        elif "timed out" in combined_text or "timeoutexpired" in combined_text:
            return FailureCategory.TIMEOUT
        elif "permissionerror" in combined_text or "access denied" in combined_text:
            return FailureCategory.TEST_ENVIRONMENT
        elif "assertionerror" in combined_text or "def test_" in combined_text or check.failed_count > 0:
            return FailureCategory.IMPLEMENTATION_DEFECT

        return FailureCategory.TEST_ENVIRONMENT

    def _extract_root_cause_hints(self, check: CheckResult) -> list[str]:
        hints: list[str] = []
        combined_text = check.stdout + "\n" + check.stderr

        # Extract specific failing pytest test cases
        failing_tests = re.findall(r"FAILED\s+([^\s:]+::[^\s]+)", combined_text)
        if failing_tests:
            for t in failing_tests[:5]:  # Top 5 failing test nodes
                hints.append(f"Failing test: {t}")

        # Extract specific assertion error messages
        assertion_matches = re.findall(r"((?:AssertionError|ValueError|KeyError|TypeError):\s*.+)", combined_text)
        if assertion_matches:
            for m in assertion_matches[:3]:
                hints.append(f"Error detail: {m.strip()[:150]}")

        # Extract missing modules if any
        missing_mods = re.findall(r"No module named\s+'([^']+)'", combined_text)
        if missing_mods:
            hints.append(f"Missing import: {missing_mods[0]}")

        if not hints:
            if check.stderr:
                hints.append(f"Stderr: {check.stderr.strip()[:150]}")
            elif check.stdout:
                hints.append(f"Stdout summary: {check.stdout.strip()[-150:]}")

        return hints

    def _suggest_diagnostics(self, check: CheckResult) -> list[str]:
        diagnostics: list[str] = []
        target = check.check_id.replace("pytest_", "").replace("_", "/")
        diagnostics.append(f"Run targeted isolated test: pytest {target} -vv -x --tb=short")
        if check.component == "frozen_files":
            diagnostics.append("Verify git status of VIDEO_ENGINE/stages/ to inspect accidental modifications.")
        elif check.failure_category == FailureCategory.MISSING_DEPENDENCY:
            diagnostics.append("Inspect virtual environment and requirements.txt for missing package.")
        return diagnostics
