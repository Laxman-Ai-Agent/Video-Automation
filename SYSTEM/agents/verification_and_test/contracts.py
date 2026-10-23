"""Contracts, Data Classes, and Enums for the Verification & Test Agent.

Canonically located at: SYSTEM/agents/verification_and_test/contracts.py
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Literal


class VerificationVerdict(str, Enum):
    """Evidence-based overall verdict for a verification request."""
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    CONDITIONAL = "CONDITIONAL"


class TestExecutionStatus(str, Enum):
    """Execution status distinguishing executed vs inferred vs skipped checks."""
    __test__ = False
    EXECUTED = "EXECUTED"
    PREVIOUSLY_EXECUTED = "PREVIOUSLY_EXECUTED"
    INFERRED = "INFERRED"
    NOT_RUN = "NOT_RUN"
    SKIPPED = "SKIPPED"
    BLOCKED = "BLOCKED"


class FailureCategory(str, Enum):
    """Diagnostic categorization for detected verification failures."""
    NONE = "NONE"
    IMPLEMENTATION_DEFECT = "IMPLEMENTATION_DEFECT"
    TEST_ENVIRONMENT = "TEST_ENVIRONMENT"
    MISSING_DEPENDENCY = "MISSING_DEPENDENCY"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    PRECONDITION_FAILED = "PRECONDITION_FAILED"
    INTEGRITY_TAMPER = "INTEGRITY_TAMPER"


@dataclass
class CheckResult:
    """Individual verification check or test execution result."""
    check_id: str
    component: str
    check_type: Literal["pytest", "hash_verification", "contract_check", "static_analysis", "custom"]
    status: TestExecutionStatus
    exit_code: int = 0
    duration_ms: float = 0.0
    stdout: str = ""
    stderr: str = ""
    passed_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    failure_category: FailureCategory = FailureCategory.NONE
    failure_diagnosis: str | None = None
    evidence_source: str = "fresh_execution"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_successful(self) -> bool:
        """Determines if the check completed with a genuine passing result."""
        return (
            self.status in (TestExecutionStatus.EXECUTED, TestExecutionStatus.PREVIOUSLY_EXECUTED)
            and self.exit_code == 0
            and self.failed_count == 0
            and self.error_count == 0
            and self.failure_category == FailureCategory.NONE
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value if isinstance(self.status, Enum) else self.status
        data["failure_category"] = (
            self.failure_category.value if isinstance(self.failure_category, Enum) else self.failure_category
        )
        data["is_successful"] = self.is_successful
        return data


@dataclass
class FailureDiagnosis:
    """Structured failure diagnosis with root cause attribution and minimal follow-up."""
    check_id: str
    component: str
    category: FailureCategory
    summary: str
    root_cause_hints: list[str] = field(default_factory=list)
    suggested_diagnostics: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["category"] = self.category.value if isinstance(self.category, Enum) else self.category
        return data


@dataclass
class VerificationReport:
    """Comprehensive structured verification report complying with system reporting contracts."""
    request_id: str
    project_id: str
    correlation_id: str
    revision: str
    components_covered: list[str]
    requirements_verified: list[str]
    unverified_requirements: list[str]
    checks: list[CheckResult] = field(default_factory=list)
    failure_diagnoses: list[FailureDiagnosis] = field(default_factory=list)
    verdict: VerificationVerdict = VerificationVerdict.PASS
    verdict_explanation: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def summary_counts(self) -> dict[str, int]:
        total = len(self.checks)
        executed = sum(1 for c in self.checks if c.status == TestExecutionStatus.EXECUTED)
        previously_executed = sum(1 for c in self.checks if c.status == TestExecutionStatus.PREVIOUSLY_EXECUTED)
        skipped = sum(1 for c in self.checks if c.status == TestExecutionStatus.SKIPPED)
        blocked = sum(1 for c in self.checks if c.status == TestExecutionStatus.BLOCKED)
        not_run = sum(1 for c in self.checks if c.status == TestExecutionStatus.NOT_RUN)
        passed_tests = sum(c.passed_count for c in self.checks)
        failed_tests = sum(c.failed_count for c in self.checks)
        error_tests = sum(c.error_count for c in self.checks)

        return {
            "total_checks": total,
            "executed_checks": executed,
            "previously_executed_checks": previously_executed,
            "skipped_checks": skipped,
            "blocked_checks": blocked,
            "not_run_checks": not_run,
            "test_passes": passed_tests,
            "test_failures": failed_tests,
            "test_errors": error_tests,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "project_id": self.project_id,
            "correlation_id": self.correlation_id,
            "revision": self.revision,
            "components_covered": self.components_covered,
            "requirements_verified": self.requirements_verified,
            "unverified_requirements": self.unverified_requirements,
            "summary": self.summary_counts,
            "verdict": self.verdict.value if isinstance(self.verdict, Enum) else self.verdict,
            "verdict_explanation": self.verdict_explanation,
            "checks": [c.to_dict() for c in self.checks],
            "failure_diagnoses": [d.to_dict() for d in self.failure_diagnoses],
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }
