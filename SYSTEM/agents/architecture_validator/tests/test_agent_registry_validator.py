"""Unit tests for AgentRegistryValidator."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from SYSTEM.agents.architecture_validator.contracts import FindingSeverity
from SYSTEM.agents.architecture_validator.validators.agent_registry_validator import (
    AgentRegistryValidator,
)
from SYSTEM.agents.shared.base_agent import BaseAgent
from SYSTEM.agents.shared.contracts import (
    AgentCategory,
    AgentMetadata,
    AgentRequest,
    AgentResult,
    AgentStatus,
)


class DummyValidAgent(BaseAgent):
    def validate(self, project_dir, request):
        return []

    def execute(self, project_dir, request):
        return AgentResult(agent_id=self.agent_id, status="succeeded", summary="ok")


class InvalidNoValidateAgent(BaseAgent):
    def execute(self, project_dir, request):
        return AgentResult(agent_id=self.agent_id, status="succeeded", summary="ok")


class NotABaseAgent:
    pass


def test_valid_registry_passes():
    validator = AgentRegistryValidator()
    # Mock clean registry
    mock_reg = MagicMock()
    meta = AgentMetadata(
        agent_id="test_agent",
        name="Test Agent",
        version="1.0.0",
        category=AgentCategory.SYSTEM_SUBAGENT,
        status=AgentStatus.IMPLEMENTED,
        purpose="Testing",
        capabilities=["testing"],
        owner="test",
    )
    adapter = DummyValidAgent(meta)
    mock_reg._metadata = {"test_agent": meta}
    mock_reg._adapters = {"test_agent": adapter}

    findings = validator.validate(mock_reg)
    blocking = [f for f in findings if f.severity == FindingSeverity.BLOCKING_ERROR]
    assert len(blocking) == 0


def test_detects_empty_registry():
    validator = AgentRegistryValidator()
    mock_reg = MagicMock()
    mock_reg._metadata = {}
    mock_reg._adapters = {}

    findings = validator.validate(mock_reg)
    blocking = [f for f in findings if f.severity == FindingSeverity.BLOCKING_ERROR]
    assert any("contains no registered agents" in f.message for f in blocking)


def test_detects_missing_adapter_for_metadata():
    validator = AgentRegistryValidator()
    mock_reg = MagicMock()
    meta = AgentMetadata(
        agent_id="orphan_meta",
        name="Orphan Meta",
        version="1.0.0",
        category=AgentCategory.SYSTEM_SUBAGENT,
        status=AgentStatus.IMPLEMENTED,
        purpose="Testing",
        capabilities=["testing"],
    )
    mock_reg._metadata = {"orphan_meta": meta}
    mock_reg._adapters = {}

    findings = validator.validate(mock_reg)
    blocking = [f for f in findings if f.severity == FindingSeverity.BLOCKING_ERROR]
    assert any("missing instantiated adapter" in f.message for f in blocking)


def test_detects_missing_metadata_for_adapter():
    validator = AgentRegistryValidator()
    mock_reg = MagicMock()
    adapter = DummyValidAgent(AgentMetadata(agent_id="orphan_adapter", name="A"))
    mock_reg._metadata = {}
    mock_reg._adapters = {"orphan_adapter": adapter}

    findings = validator.validate(mock_reg)
    blocking = [f for f in findings if f.severity == FindingSeverity.BLOCKING_ERROR]
    assert any("missing AgentMetadata" in f.message for f in blocking)


def test_detects_non_base_agent_adapter():
    validator = AgentRegistryValidator()
    mock_reg = MagicMock()
    meta = AgentMetadata(agent_id="bad_agent", name="Bad", version="1.0.0")
    mock_reg._metadata = {"bad_agent": meta}
    mock_reg._adapters = {"bad_agent": NotABaseAgent()}

    findings = validator.validate(mock_reg)
    blocking = [f for f in findings if f.severity == FindingSeverity.BLOCKING_ERROR]
    assert any("does not inherit from BaseAgent" in f.message for f in blocking)
