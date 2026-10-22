"""Unit tests for ArchitectureValidatorAgent."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from SYSTEM.agents.architecture_validator.agent import ArchitectureValidatorAgent
from SYSTEM.agents.architecture_validator.contracts import FindingSeverity
from SYSTEM.agents.shared.contracts import (
    AgentCategory,
    AgentMetadata,
    AgentRequest,
    AgentResult,
    AgentStatus,
)


def test_agent_initialization_and_metadata():
    agent = ArchitectureValidatorAgent()
    assert agent.agent_id == "architecture_validator"
    assert agent.metadata.category == AgentCategory.SYSTEM_SUBAGENT
    assert agent.metadata.status == AgentStatus.IMPLEMENTED
    assert "full-architecture-audit" in agent.metadata.capabilities
    assert "agent_registry" in agent.metadata.allowed_tools


def test_agent_validate_action():
    agent = ArchitectureValidatorAgent()
    # Supported action
    req_valid = AgentRequest(
        agent_id="architecture_validator",
        parameters={"action": "full_architecture_audit"},
    )
    errors = agent.validate(None, req_valid)
    assert errors == []

    # Unsupported action
    req_invalid = AgentRequest(
        agent_id="architecture_validator",
        parameters={"action": "unsupported_action_xyz"},
    )
    errors = agent.validate(None, req_invalid)
    assert len(errors) == 1
    assert "Unknown architecture validation action" in errors[0]


def test_agent_execute_full_audit():
    agent = ArchitectureValidatorAgent()
    req = AgentRequest(
        agent_id="architecture_validator",
        parameters={"action": "full_architecture_audit"},
    )
    res = agent.execute(None, req)
    assert isinstance(res, AgentResult)
    assert res.agent_id == "architecture_validator"
    assert "audit_result" in res.metadata
    audit_data = res.metadata["audit_result"]
    assert audit_data["action"] == "full_architecture_audit"
    assert "findings" in audit_data
    assert "metrics" in audit_data
    assert audit_data["metrics"]["total_findings"] >= 0


def test_agent_execute_targeted_audit():
    agent = ArchitectureValidatorAgent()
    req = AgentRequest(
        agent_id="architecture_validator",
        parameters={"action": "targeted_audit", "target": "pipeline"},
    )
    res = agent.execute(None, req)
    assert res.status in ("succeeded", "failed")
    assert "audit_result" in res.metadata


def test_audit_is_read_only_and_preserves_catalogs(tmp_path):
    """Verifies that running an audit does not mutate skills/catalog.json or project files."""
    from SYSTEM.registries.skill_registry import CATALOG_FILE

    before_content = CATALOG_FILE.read_bytes() if CATALOG_FILE.exists() else b""

    agent = ArchitectureValidatorAgent()
    req = AgentRequest(
        agent_id="architecture_validator",
        parameters={"action": "full_architecture_audit"},
    )
    agent.execute(None, req)

    after_content = CATALOG_FILE.read_bytes() if CATALOG_FILE.exists() else b""
    assert before_content == after_content, "Audit run mutated catalog.json!"
