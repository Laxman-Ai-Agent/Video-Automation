"""Unit tests for canonical Security Policy Agent, contracts, evaluator, and enforcer."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from SYSTEM.agents.security_policy.agent import SecurityPolicyAgent
from SYSTEM.agents.security_policy.contracts import (
    PolicyDecision,
    PolicyState,
    RiskLevel,
    SecurityRequest,
)
from SYSTEM.agents.security_policy.enforcer import (
    SecurityPolicyEnforcer,
    SecurityPolicyViolationError,
)
from SYSTEM.agents.security_policy.evaluator import PolicyEvaluator
from SYSTEM.agents.shared.contracts import AgentMetadata, AgentRequest, AgentResult

PROJECT_ROOT = Path(__file__).resolve().parents[4]


class TestSecurityPolicyAgentBasics:
    """Verifies SecurityPolicyAgent metadata, lifecycle, and default contract conformance."""

    def test_agent_initialization_and_metadata(self):
        agent = SecurityPolicyAgent()
        assert agent.agent_id == "security_policy"
        assert agent.metadata.name == "Security Policy Agent"
        assert "policy-evaluation" in agent.metadata.capabilities
        assert "agent-authorization" in agent.metadata.capabilities
        assert "frozen-file-protection" in agent.metadata.capabilities
        assert "approval_engine" in agent.metadata.allowed_tools

    def test_status_action(self):
        agent = SecurityPolicyAgent()
        req = AgentRequest(
            project_id="test_proj",
            agent_id="security_policy",
            stage_id="security",
            parameters={"action": "status"},
        )
        res = agent.execute(PROJECT_ROOT, req)
        assert res.status == "succeeded"
        assert res.metadata["status"] == "operational"
        assert len(res.metadata["rules"]) >= 6

    def test_invalid_action_rejected_in_validate(self):
        agent = SecurityPolicyAgent()
        req = AgentRequest(
            project_id="test_proj",
            agent_id="security_policy",
            stage_id="security",
            parameters={"action": "unsupported_action_xyz"},
        )
        errs = agent.validate(PROJECT_ROOT, req)
        assert len(errs) == 1
        assert "Unknown security action 'unsupported_action_xyz'" in errs[0]


class TestAgentPermissionsAndAntiSpoofing:
    """Verifies agent identity registration and anti-spoofing defense."""

    def test_unregistered_agent_denied(self):
        evaluator = PolicyEvaluator(project_root=PROJECT_ROOT)
        req = SecurityRequest(
            agent_id="malicious_unregistered_agent_999",
            operation="read_file",
            resource="README.md",
        )
        dec = evaluator.evaluate(req)
        assert dec.state == PolicyState.DENY
        assert dec.rule_id == "SEC-AGT-002"
        assert "not registered" in dec.reason

    def test_registered_agent_allowed_for_safe_action(self):
        evaluator = PolicyEvaluator(project_root=PROJECT_ROOT)
        req = SecurityRequest(
            agent_id="capability_finder",
            operation="file_read",
            resource="README.md",
        )
        dec = evaluator.evaluate(req)
        assert dec.state == PolicyState.ALLOW
        assert dec.allowed is True

    def test_empty_agent_id_denied(self):
        evaluator = PolicyEvaluator(project_root=PROJECT_ROOT)
        req = SecurityRequest(
            agent_id="",
            operation="read_file",
        )
        dec = evaluator.evaluate(req)
        assert dec.state == PolicyState.DENY
        assert dec.rule_id == "SEC-AGT-001"

    def test_unauthenticated_role_spoofing_rejected(self):
        evaluator = PolicyEvaluator(project_root=PROJECT_ROOT)
        # Caller claims elevated 'system_admin' role without an Approval
        req = SecurityRequest(
            agent_id="capability_finder",
            operation="update_config",
            role="system_admin",
            approval_request_id=None,
        )
        dec = evaluator.evaluate(req)
        assert dec.state == PolicyState.DENY
        assert dec.rule_id == "SEC-AUTH-003"
        assert dec.risk_level == RiskLevel.CRITICAL
        assert "Unauthenticated role spoofing rejected" in dec.reason

    def test_unrecognized_role_rejected(self):
        evaluator = PolicyEvaluator(project_root=PROJECT_ROOT)
        req = SecurityRequest(
            agent_id="capability_finder",
            operation="update_config",
            role="super_supreme_overlord",
        )
        dec = evaluator.evaluate(req)
        assert dec.state == PolicyState.DENY
        assert dec.rule_id == "SEC-AUTH-002"
        assert "not a recognized trusted role" in dec.reason

    def test_security_policy_agent_cannot_self_approve(self):
        evaluator = PolicyEvaluator(project_root=PROJECT_ROOT)
        req = SecurityRequest(
            agent_id="security_policy",
            operation="promote_skill",
            resource="skill_abc",
        )
        dec = evaluator.evaluate(req)
        assert dec.state == PolicyState.DENY
        assert dec.rule_id == "SEC-AUTH-001"
        assert "cannot self-approve" in dec.reason


class TestFileBoundariesAndFrozenFiles:
    """Verifies file access controls and frozen algorithm protection."""

    @pytest.mark.parametrize(
        "frozen_file",
        [
            "VIDEO_ENGINE/stages/transcribe.py",
            "VIDEO_ENGINE/stages/transcript_review.py",
            "VIDEO_ENGINE/stages/scene_segmentation.py",
            "video_engine/stages/transcribe.py",
        ],
    )
    def test_modification_of_frozen_files_strictly_denied(self, frozen_file: str):
        evaluator = PolicyEvaluator(project_root=PROJECT_ROOT)
        req = SecurityRequest(
            agent_id="skill_factory",
            operation="file_write",
            resource=frozen_file,
        )
        dec = evaluator.evaluate(req)
        assert dec.state == PolicyState.DENY
        assert dec.rule_id == "SEC-FILE-001"
        assert dec.risk_level == RiskLevel.CRITICAL
        assert "Modification of frozen video algorithm stage file" in dec.reason

    def test_access_to_protected_secret_denied_without_auth(self):
        evaluator = PolicyEvaluator(project_root=PROJECT_ROOT)
        req = SecurityRequest(
            agent_id="capability_finder",
            operation="file_read",
            resource="config/.env",
        )
        dec = evaluator.evaluate(req)
        assert dec.state == PolicyState.DENY
        assert dec.rule_id == "SEC-FILE-002"
        assert dec.risk_level == RiskLevel.CRITICAL
        assert "Access to protected credential/secret" in dec.reason

    def test_path_traversal_outside_project_denied(self):
        evaluator = PolicyEvaluator(project_root=PROJECT_ROOT)
        req = SecurityRequest(
            agent_id="capability_finder",
            operation="file_read",
            resource="../../windows/system32/cmd.exe",
        )
        dec = evaluator.evaluate(req)
        assert dec.state == PolicyState.DENY
        assert dec.rule_id == "SEC-FILE-003"
        assert "Path traversal outside project root" in dec.reason


class TestToolPermissions:
    """Verifies tool access controls and agent allowlists."""

    def test_tool_not_in_registry_blocked(self):
        evaluator = PolicyEvaluator(project_root=PROJECT_ROOT)
        req = SecurityRequest(
            agent_id="capability_finder",
            operation="invoke_tool",
            resource="unknown_thirdparty_miner",
            parameters={"tool_id": "unknown_thirdparty_miner"},
        )
        dec = evaluator.evaluate(req)
        assert dec.state == PolicyState.BLOCKED
        assert dec.rule_id == "SEC-TOOL-001"

    def test_tool_not_in_agent_allowlist_denied(self):
        evaluator = PolicyEvaluator(project_root=PROJECT_ROOT)
        # capability_finder allowed tools: agent_registry, skill_registry, tool_registry
        # trying to invoke llm_gateway
        req = SecurityRequest(
            agent_id="capability_finder",
            operation="invoke_tool",
            resource="llm_gateway",
            parameters={"tool_id": "llm_gateway"},
        )
        dec = evaluator.evaluate(req)
        assert dec.state == PolicyState.DENY
        assert dec.rule_id == "SEC-TOOL-002"
        assert "not authorized to invoke tool" in dec.reason


class TestSkillSecurityAndApprovals:
    """Verifies declarative vs executable skills and approval gating."""

    def test_declarative_skill_allowed_without_container(self):
        evaluator = PolicyEvaluator(project_root=PROJECT_ROOT)
        req = SecurityRequest(
            agent_id="skill_factory",
            operation="create_skill",
            resource="motion.fade_in",
            parameters={"is_executable": False, "manifest_type": "declarative"},
        )
        dec = evaluator.evaluate(req)
        assert dec.state == PolicyState.ALLOW
        assert dec.rule_id == "SEC-SKILL-001"
        assert dec.risk_level == RiskLevel.LOW

    def test_executable_skill_testing_blocked_without_sandbox(self):
        evaluator = PolicyEvaluator(project_root=PROJECT_ROOT)
        req = SecurityRequest(
            agent_id="skill_factory",
            operation="test_skill",
            resource="motion.complex_py",
            parameters={"is_executable": True, "sandbox_available": False},
        )
        dec = evaluator.evaluate(req)
        assert dec.state == PolicyState.BLOCKED
        assert dec.rule_id == "SEC-SKILL-002"
        assert "requires active sandbox isolation" in dec.reason

    def test_skill_promotion_requires_approval(self):
        evaluator = PolicyEvaluator(project_root=PROJECT_ROOT)
        req = SecurityRequest(
            agent_id="skill_factory",
            operation="promote_skill",
            resource="motion.bounce_effect",
        )
        dec = evaluator.evaluate(req)
        assert dec.state == PolicyState.APPROVAL_REQUIRED
        assert dec.rule_id == "SEC-SKILL-003"
        assert dec.approval_required is True

    def test_nonexistent_approval_request_denied(self):
        evaluator = PolicyEvaluator(project_root=PROJECT_ROOT)
        req = SecurityRequest(
            agent_id="capability_finder",
            operation="render_video",
            approval_request_id="appr_non_existent_12345",
        )
        dec = evaluator.evaluate(req)
        assert dec.state == PolicyState.DENY
        assert dec.rule_id == "SEC-APPR-001"
        assert "not found" in dec.reason


class TestEnforcementBoundary:
    """Verifies that SecurityPolicyEnforcer blocks denied operations."""

    def test_enforce_raises_on_policy_denial(self):
        enforcer = SecurityPolicyEnforcer()
        req = SecurityRequest(
            agent_id="skill_factory",
            operation="file_write",
            resource="VIDEO_ENGINE/stages/transcribe.py",
        )
        with pytest.raises(SecurityPolicyViolationError) as exc_info:
            enforcer.enforce(req)

        assert exc_info.value.decision.rule_id == "SEC-FILE-001"
        assert exc_info.value.decision.state == PolicyState.DENY

    def test_guard_decorator_prevents_execution_on_denial(self):
        enforcer = SecurityPolicyEnforcer()
        executed = False

        @enforcer.guard(
            agent_id="capability_finder",
            operation="file_write",
            resource="VIDEO_ENGINE/stages/transcribe.py",
        )
        def sensitive_mutator():
            nonlocal executed
            executed = True
            return "mutated"

        with pytest.raises(SecurityPolicyViolationError):
            sensitive_mutator()

        # The protected operation was NOT executed
        assert executed is False
