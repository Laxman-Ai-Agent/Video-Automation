"""Unit tests for ContractValidator."""
from __future__ import annotations

import pytest
from SYSTEM.agents.architecture_validator.contracts import FindingSeverity
from SYSTEM.agents.architecture_validator.validators.contract_validator import (
    ContractValidator,
)


def test_contracts_validate_cleanly():
    validator = ContractValidator()
    findings = validator.validate()
    blocking = [f for f in findings if f.severity == FindingSeverity.BLOCKING_ERROR]
    assert len(blocking) == 0, f"Unexpected contract failures: {[f.message for f in blocking]}"
