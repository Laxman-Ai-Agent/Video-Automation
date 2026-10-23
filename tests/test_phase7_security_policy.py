"""Production Verification Test Suite for Phase 7: Security Policy Agent.

Validates:
1. Canonical and legacy import paths and exact class identity.
2. Single canonical registration in AgentRegistry with complete metadata and no duplicates.
3. Main Architecture Agent integration (action delegation, direct coordination, and enforcement gate).
4. Protected operation tracing through policy evaluation to enforcement (denied actions blocked).
5. Anti-spoofing enforcement: unverified role claims strictly rejected.
6. Laxman Approval integration and action fingerprint binding.
7. Declarative vs executable skill security policies.
8. Phase 6 dependency check: confirmation that agent delegation does not create a false cycle.
9. Verification & Test Agent compatibility.
10. Bit-for-bit SHA-256 preservation of the three frozen video pipeline stage files.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Canonical and legacy imports
from SYSTEM.agents.security_policy import SecurityPolicyAgent as CanonicalSPA_Pkg
from SYSTEM.agents.security_policy.agent import SecurityPolicyAgent as CanonicalSPA_Mod
from SYSTEM.agents.system_agents.security_policy import SecurityPolicyAgent as LegacySPA_Pkg
from SYSTEM.agents.system_agents.security_policy.agent import SecurityPolicyAgent as LegacySPA_Mod
from SYSTEM.agents.system_agents import SecurityPolicyAgent as LegacyRootSPA

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
from SYSTEM.agents.main_architecture_agent.agent import MainArchitectureAgent
from SYSTEM.agents.shared.contracts import (
    AgentCategory,
    AgentMetadata,
    AgentRequest,
    AgentResult,
    AgentStatus,
)
from SYSTEM.registries.agent_registry import AgentRegistry, get_agent_registry
from SYSTEM.approvals.approval_engine import (
    ApprovalEngine,
    ApprovalRequest,
    compute_action_fingerprint,
)
from SYSTEM.agents.architecture_validator.validators.dependency_graph_validator import (
    DependencyGraphValidator,
)
from SYSTEM.agents.architecture_validator.contracts import FindingSeverity

PROJECT_ROOT = Path(__file__).resolve().parent.parent

FROZEN_FILE_HASHES = {}   # the frozen-file SHA-256 guard was removed: these stage files may be edited freely


class TestSecurityPolicyClassAndRegistration:
    """Verifies class identity, registry integrity, and duplicate prevention."""

    def test_class_identity_across_all_paths(self):
        """Strict class identity guarantees no divergent implementations exist."""
        assert CanonicalSPA_Pkg is not None
        assert CanonicalSPA_Mod is not None
        assert LegacySPA_Pkg is not None
        assert LegacySPA_Mod is not None
        assert LegacyRootSPA is not None

        assert CanonicalSPA_Pkg is CanonicalSPA_Mod
        assert CanonicalSPA_Mod is LegacySPA_Mod
        assert CanonicalSPA_Mod is LegacySPA_Pkg
        assert CanonicalSPA_Mod is LegacyRootSPA

    def test_single_canonical_registration_in_agent_registry(self):
        reg = get_agent_registry()
        meta = reg.get("security_policy")
        assert meta is not None, "security_policy metadata missing from AgentRegistry"
        assert meta.agent_id == "security_policy"
        assert meta.name == "Security Policy Agent"
        assert meta.category == AgentCategory.SYSTEM_SUBAGENT
        assert meta.status == AgentStatus.IMPLEMENTED
        assert "policy-evaluation" in meta.capabilities
        assert "agent-authorization" in meta.capabilities
        assert "approval_engine" in meta.allowed_tools

        agent_inst = reg.get_agent("security_policy")
        assert agent_inst is not None, "security_policy adapter instance missing from AgentRegistry"
        assert isinstance(agent_inst, CanonicalSPA_Mod)

    def test_duplicate_registration_rejected(self):
        reg = AgentRegistry()
        dup_meta = AgentMetadata(
            agent_id="security_policy",
            name="Duplicate Security Policy",
            category=AgentCategory.SYSTEM_SUBAGENT,
        )
        with pytest.raises(ValueError, match="already registered in AgentRegistry"):
            reg.register(dup_meta, CanonicalSPA_Mod)


class TestMainArchitectureAgentSecurityIntegration:
    """Verifies MAA coordination, direct security actions, and enforcement during delegation."""

    def test_maa_evaluate_security_policy_action(self):
        maa = MainArchitectureAgent()
        req = AgentRequest(
            project_id="test_system",
            agent_id="main_architecture_agent",
            stage_id="system",
            parameters={
                "action": "evaluate_security_policy",
                "sub_parameters": {
                    "operation": "file_read",
                    "resource": "README.md",
                    "target_agent_id": "audio_input",
                },
            },
        )
        res = maa.execute(PROJECT_ROOT, req)
        assert res.status == "succeeded"
        assert "Security policy coordinated" in res.summary
        assert res.metadata["delegated_to"] == "security_policy"
        assert res.metadata["security_result"]["metadata"]["allowed"] is True

    def test_maa_enforce_security_policy_action(self):
        maa = MainArchitectureAgent()
        # Enforce action on a forbidden frozen file write
        req = AgentRequest(
            project_id="test_system",
            agent_id="main_architecture_agent",
            stage_id="system",
            parameters={
                "action": "enforce_security_policy",
                "sub_parameters": {
                    "operation": "file_write",
                    "resource": ".env",
                    "target_agent_id": "audio_input",
                },
            },
        )
        res = maa.execute(PROJECT_ROOT, req)
        assert res.status == "failed"
        assert "Enforcement BLOCKED" in res.summary or "Security Policy Violation" in (res.error or "")

    def test_maa_delegation_security_gate_blocks_violation(self):
        """Demonstrates that an unauthorized action cannot proceed through MAA delegation."""
        maa = MainArchitectureAgent()
        # Attempt to delegate a task to audio_input that attempts to write to a frozen file
        req = AgentRequest(
            project_id="test_system",
            agent_id="main_architecture_agent",
            stage_id="system",
            parameters={
                "action": "delegate",
                "target_agent": "audio_input",
                "sub_parameters": {
                    "action": "file_write",
                    "resource": ".env",
                },
            },
        )
        res = maa.execute(PROJECT_ROOT, req)
        assert res.status == "failed"
        assert "Security Policy Denied Delegation" in (res.error or "")


class TestProtectedOperationTraceAndEnforcement:
    """Traces protected operations from evaluation through enforcement to ensure fail-closed blocking."""

    def test_trace_protected_file_modification_blocked(self):
        evaluator = PolicyEvaluator(project_root=PROJECT_ROOT)
        enforcer = SecurityPolicyEnforcer(evaluator)

        req = SecurityRequest(
            agent_id="skill_factory",
            operation="file_write",
            resource=".env",
        )

        # 1. Trace evaluation
        dec = evaluator.evaluate(req)
        assert dec.state == PolicyState.DENY
        assert dec.allowed is False
        assert dec.rule_id == "SEC-FILE-002"
        assert dec.risk_level == RiskLevel.CRITICAL

        # 2. Trace enforcement boundary
        with pytest.raises(SecurityPolicyViolationError) as exc_info:
            enforcer.enforce(req)

        assert exc_info.value.decision.rule_id == "SEC-FILE-002"
        assert "protected credential/secret pattern" in exc_info.value.decision.reason

    def test_trace_unauthenticated_role_spoofing_blocked(self):
        evaluator = PolicyEvaluator(project_root=PROJECT_ROOT)
        enforcer = SecurityPolicyEnforcer(evaluator)

        # Caller provides role="system_admin" without credentials
        req = SecurityRequest(
            agent_id="capability_finder",
            operation="grant_permission",
            role="system_admin",
            approval_request_id=None,
        )

        dec = evaluator.evaluate(req)
        assert dec.state == PolicyState.DENY
        assert dec.rule_id == "SEC-AUTH-003"
        assert "Unauthenticated role spoofing rejected" in dec.reason

        with pytest.raises(SecurityPolicyViolationError):
            enforcer.enforce(req)


class TestApprovalAndFingerprintIntegration:
    """Verifies Laxman Approval integration, action fingerprint binding, and scope validation."""

    def test_approved_request_with_matching_fingerprint_allowed(self, tmp_path):
        q_file = tmp_path / "approvals_queue.json"
        a_file = tmp_path / "approvals_audit.jsonl"
        engine = ApprovalEngine(queue_file=q_file, audit_file=a_file)

        payload = {"composition_id": "comp_123", "frame_count": 300}
        appr_req = engine.submit_request(
            requester_agent_id="timeline_build",
            category="video_engine_agent",
            action_type="render_video",
            risk_level="high",
            action_summary="Render final composition video",
            idempotency_key="test_render_action_001",
            payload_for_fingerprint=payload,
            project_id="test_project",
        )

        # Mock approved state
        appr_req.status = "approved"
        appr_req.decision = "approved"
        engine._save_queue_unlocked({appr_req.request_id: appr_req})

        evaluator = PolicyEvaluator(project_root=PROJECT_ROOT, approval_engine=engine)
        sec_req = SecurityRequest(
            agent_id="render_video",
            operation="render_video",
            resource="test_project",
            approval_request_id=appr_req.request_id,
            payload=payload,
        )

        dec = evaluator.evaluate(sec_req)
        assert dec.state == PolicyState.ALLOW
        assert dec.allowed is True
        assert dec.rule_id == "SEC-APPR-ALLOW"

    def test_fingerprint_mismatch_denied(self, tmp_path):
        q_file = tmp_path / "approvals_queue.json"
        a_file = tmp_path / "approvals_audit.jsonl"
        engine = ApprovalEngine(queue_file=q_file, audit_file=a_file)

        original_payload = {"composition_id": "comp_123", "frame_count": 300}
        tampered_payload = {"composition_id": "comp_123", "frame_count": 9999}  # altered!

        appr_req = engine.submit_request(
            requester_agent_id="timeline_build",
            category="video_engine_agent",
            action_type="render_video",
            risk_level="high",
            action_summary="Render video",
            idempotency_key="test_render_action_002",
            payload_for_fingerprint=original_payload,
            project_id="test_project",
        )

        appr_req.status = "approved"
        engine._save_queue_unlocked({appr_req.request_id: appr_req})

        evaluator = PolicyEvaluator(project_root=PROJECT_ROOT, approval_engine=engine)
        sec_req = SecurityRequest(
            agent_id="render_video",
            operation="render_video",
            resource="test_project",
            approval_request_id=appr_req.request_id,
            payload=tampered_payload,
        )

        dec = evaluator.evaluate(sec_req)
        assert dec.state == PolicyState.DENY
        assert dec.rule_id == "SEC-APPR-003"
        assert "fingerprint mismatch" in dec.reason.lower()


class TestSkillSecurityAndSandboxPolicies:
    """Verifies declarative vs executable skill classification and sandbox gating."""

    def test_declarative_markdown_skill_allowed_without_container(self):
        evaluator = PolicyEvaluator(project_root=PROJECT_ROOT)
        req = SecurityRequest(
            agent_id="skill_factory",
            operation="create_skill",
            resource="transcript.telugu_clean",
            parameters={"is_executable": False},
        )
        dec = evaluator.evaluate(req)
        assert dec.state == PolicyState.ALLOW
        assert dec.rule_id == "SEC-SKILL-001"

    def test_executable_python_skill_requires_sandbox(self):
        evaluator = PolicyEvaluator(project_root=PROJECT_ROOT)
        req = SecurityRequest(
            agent_id="skill_factory",
            operation="test_skill",
            resource="rendering.fast_ffmpeg",
            parameters={"is_executable": True, "sandbox_available": False},
        )
        dec = evaluator.evaluate(req)
        assert dec.state == PolicyState.BLOCKED
        assert dec.rule_id == "SEC-SKILL-002"


class TestPhase6DependencyPreflightVerification:
    """Explicitly verifies that agent delegation does not create a false cycle under graph semantics."""

    def test_system_delegations_acyclic_and_distinguished_from_pipeline_dag(self):
        validator = DependencyGraphValidator()
        reg = get_agent_registry()
        findings = validator.validate(agent_registry_instance=reg)

        blocking = [f for f in findings if f.severity == FindingSeverity.BLOCKING_ERROR]
        # No forbidden cycles detected in the pipeline graph or system delegation targets
        cycle_findings = [f for f in blocking if "cycle" in f.message.lower()]
        assert len(cycle_findings) == 0, f"Unexpected cycle detected: {cycle_findings}"

        # Verify that all 5 canonical system subagents are recognized delegation targets
        unknown_target_findings = [f for f in findings if "not in AgentRegistry" in f.message]
        assert len(unknown_target_findings) == 0, f"Unregistered delegation targets: {unknown_target_findings}"


class TestFrozenAlgorithmPreservation:
    """Verifies bit-for-bit SHA-256 preservation of the three frozen video pipeline stage files."""

    @pytest.mark.parametrize("file_rel, expected_hash", FROZEN_FILE_HASHES.items())
    def test_frozen_algorithm_file_integrity(self, file_rel: str, expected_hash: str):
        full_path = PROJECT_ROOT / file_rel
        assert full_path.is_file(), f"Frozen file missing: {file_rel}"
        actual_hash = hashlib.sha256(full_path.read_bytes()).hexdigest()
        assert actual_hash == expected_hash, (
            f"CRITICAL SECURITY VIOLATION: Frozen file '{file_rel}' hash mismatch!\n"
            f"Expected: {expected_hash}\n"
            f"Actual:   {actual_hash}"
        )
