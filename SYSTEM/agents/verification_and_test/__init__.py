"""Verification & Test Agent Package.

Canonical exports for verification, test execution, component mapping, and failure diagnosis.
"""
from __future__ import annotations

from .agent import VerificationAndTestAgent
from .component_mapper import ComponentMapper
from .contracts import (
    CheckResult,
    FailureCategory,
    FailureDiagnosis,
    TestExecutionStatus,
    VerificationReport,
    VerificationVerdict,
)
from .diagnostician import Diagnostician
from .test_executor import TestExecutor

__all__ = [
    "CheckResult",
    "ComponentMapper",
    "Diagnostician",
    "FailureCategory",
    "FailureDiagnosis",
    "TestExecutionStatus",
    "TestExecutor",
    "VerificationAndTestAgent",
    "VerificationReport",
    "VerificationVerdict",
]
