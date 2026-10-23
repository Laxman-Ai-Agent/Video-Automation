"""Unit tests for SecurityBoundaryValidator."""
from __future__ import annotations

from SYSTEM.agents.architecture_validator.contracts import FindingSeverity
from SYSTEM.agents.architecture_validator.validators.security_boundary_validator import (
    SecurityBoundaryValidator,
)


def test_security_boundary_has_no_blocking_findings():
    findings = SecurityBoundaryValidator().validate()
    blocking = [f for f in findings if f.severity == FindingSeverity.BLOCKING_ERROR]
    assert not blocking, [f.message for f in blocking]
