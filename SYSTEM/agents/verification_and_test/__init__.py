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
    FrozenFileCheck,
    TestExecutionStatus,
    VerificationReport,
    VerificationVerdict,
)
from .diagnostician import Diagnostician
from .test_executor import FROZEN_ALGORITHM_FILES, TestExecutor

__all__ = [
    "CheckResult",
    "ComponentMapper",
    "Diagnostician",
    "FailureCategory",
    "FailureDiagnosis",
    "FrozenFileCheck",
    "TestExecutionStatus",
    "TestExecutor",
    "VerificationAndTestAgent",
    "VerificationReport",
    "VerificationVerdict",
    "FROZEN_ALGORITHM_FILES",
]
