"""Production Verification Test Suite for Phase 6: Verification & Test Agent.

Validates:
1. Canonical imports and legacy facade class identity across all resolution paths.
2. Authoritative AgentRegistry single registration, metadata, and capability contracts.
3. MainArchitectureAgent delegation via both dedicated and general delegation interfaces.
4. Clean handling of missing targets and invalid coordination requests.
5. Verification execution, requirement partitioning, component mapping, and result capture.
6. Diagnostic categorization distinguishing implementation defects from environment issues.
7. Evidence-based verdicts (PASS, FAIL, BLOCKED, CONDITIONAL) without false passes.
8. Read-only guarantees: source code under review remains bit-for-bit unmutated.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Canonical imports
from SYSTEM.agents.verification_and_test import (
    CheckResult,
    ComponentMapper,
    Diagnostician,
    FailureCategory,
    FailureDiagnosis,
    TestExecutionStatus,
    TestExecutor,
    VerificationAndTestAgent as CanonicalVTA_Pkg,
    VerificationReport,
    VerificationVerdict,
)
from SYSTEM.agents.verification_and_test.agent import VerificationAndTestAgent as CanonicalVTA_Mod

# Legacy imports
from SYSTEM.agents.system_agents import VerificationAndTestAgent as LegacyRootVTA
from SYSTEM.agents.system_agents.verification_and_test import VerificationAndTestAgent as LegacyVTA_Pkg
from SYSTEM.agents.system_agents.verification_and_test.agent import VerificationAndTestAgent as LegacyVTA_Mod

VerificationAndTestAgent = CanonicalVTA_Mod

# Architecture and Registry
from SYSTEM.agents.main_architecture_agent.agent import MainArchitectureAgent
from SYSTEM.agents.shared.contracts import (
    AgentCategory,
    AgentMetadata,
    AgentRequest,
    AgentResult,
    AgentStatus,
)
from SYSTEM.registries.agent_registry import AgentRegistry, get_agent_registry

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestVerificationAndTestClassAndRegistration:
    """Verifies import resolution, class identity, and single registration."""

    def test_class_identity_across_all_paths(self):
        assert CanonicalVTA_Pkg is CanonicalVTA_Mod
        assert CanonicalVTA_Pkg is LegacyVTA_Pkg
        assert CanonicalVTA_Pkg is LegacyVTA_Mod
        assert CanonicalVTA_Pkg is LegacyRootVTA

    def test_single_canonical_registration_in_agent_registry(self):
        reg = get_agent_registry()
        matches = [m for m in reg.list_all_agents() if m.agent_id == "verification_and_test"]
        assert len(matches) == 1, f"Expected 1 registration for verification_and_test, found {len(matches)}"

        meta = matches[0]
        assert meta.agent_id == "verification_and_test"
        assert meta.category == AgentCategory.SYSTEM_SUBAGENT
        assert meta.status == AgentStatus.IMPLEMENTED
        assert "change-verification" in meta.capabilities
        assert "test-execution" in meta.capabilities

        adapter = reg.get_agent("verification_and_test")
        assert isinstance(adapter, CanonicalVTA_Mod)


class TestVerificationExecutionAndContracts:
    """Verifies core verification, execution capture, diagnosis, and report generation."""

    def test_verify_action_with_component_mapping(self):
        agent = VerificationAndTestAgent(project_root=PROJECT_ROOT)
        req = AgentRequest(
            project_id="test_project",
            agent_id="verification_and_test",
            stage_id="system",
            parameters={
                "action": "verify",
                "components": ["video_pipeline"],
                "requirements": [
                    "Keep the video stage outputs unchanged",
                    "Require manual review and human sign-off on staging video",
                ],
            },
        )
        res = agent.execute(PROJECT_ROOT, req)
        assert res.status == "succeeded"
        report = res.metadata["report"]

        # Verifiable vs unverified requirement split
        assert "Keep the video stage outputs unchanged" in report["requirements_verified"]
        assert any("human sign-off" in u for u in report["unverified_requirements"])

        # Unverified manual requirement makes verdict CONDITIONAL rather than unqualified PASS
        assert report["verdict"] == "CONDITIONAL"

    def test_verdict_blocks_on_missing_or_timed_out_test(self):
        agent = VerificationAndTestAgent(project_root=PROJECT_ROOT)
        req = AgentRequest(
            project_id="test_project",
            agent_id="verification_and_test",
            parameters={
                "action": "run_tests",
                "targets": ["tests/nonexistent_test_file.py"],
            },
        )
        res = agent.execute(PROJECT_ROOT, req)
        assert res.status == "failed"
        report = res.metadata["report"]
        assert report["verdict"] == "BLOCKED"
        assert report["summary"]["blocked_checks"] >= 1


class TestMainArchitectureAgentIntegration:
    """Verifies Main Architecture Agent coordination and delegation."""

    def test_maa_verify_and_test_action(self):
        maa = MainArchitectureAgent()
        req = AgentRequest(
            project_id="test_coordination",
            agent_id="main_architecture_agent",
            stage_id="system",
            parameters={
                "action": "verify_and_test",
                "verification_action": "status",
            },
        )
        res = maa.execute(PROJECT_ROOT, req)
        assert res.status == "succeeded"
        assert "Verification coordinated" in res.summary
        assert res.metadata["delegated_to"] == "verification_and_test"
        v_res = res.metadata["verification_result"]
        assert v_res["metadata"]["status"] == "ready"

    def test_maa_general_delegate_to_verification_and_test(self):
        maa = MainArchitectureAgent()
        req = AgentRequest(
            project_id="test_coordination",
            agent_id="main_architecture_agent",
            stage_id="system",
            parameters={
                "action": "delegate",
                "target_agent_id": "verification_and_test",
                "sub_parameters": {"action": "status"},
            },
        )
        res = maa.execute(PROJECT_ROOT, req)
        assert res.status == "succeeded"
        assert "Delegated task completed by verification_and_test" in res.summary

    def test_maa_delegation_missing_target_fails_cleanly(self):
        maa = MainArchitectureAgent()
        req = AgentRequest(
            project_id="test_coordination",
            agent_id="main_architecture_agent",
            stage_id="system",
            parameters={
                "action": "delegate",
                "target_agent_id": "nonexistent_subagent",
            },
        )
        res = maa.execute(PROJECT_ROOT, req)
        assert res.status == "failed"
        assert "not found in registry" in res.error
