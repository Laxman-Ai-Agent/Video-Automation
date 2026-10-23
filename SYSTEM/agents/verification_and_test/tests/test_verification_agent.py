"""Unit and contract tests for VerificationAndTestAgent.

Canonically located at: SYSTEM/agents/verification_and_test/tests/test_agent.py
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from SYSTEM.agents.shared.contracts import (
    AgentCategory,
    AgentMetadata,
    AgentRequest,
    AgentResult,
    AgentStatus,
)
from SYSTEM.agents.verification_and_test.agent import VerificationAndTestAgent
from SYSTEM.agents.verification_and_test.component_mapper import ComponentMapper
from SYSTEM.agents.verification_and_test.contracts import (
    CheckResult,
    FailureCategory,
    FailureDiagnosis,
    TestExecutionStatus,
    VerificationReport,
    VerificationVerdict,
)
from SYSTEM.agents.verification_and_test.diagnostician import Diagnostician
from SYSTEM.agents.verification_and_test.test_executor import TestExecutor
from SYSTEM.registries.agent_registry import AgentRegistry, get_agent_registry


def test_agent_initialization_and_metadata():
    agent = VerificationAndTestAgent()
    assert agent.agent_id == "verification_and_test"
    assert agent.metadata.name == "Verification & Test Agent"
    assert agent.metadata.category == AgentCategory.SYSTEM_SUBAGENT
    assert agent.metadata.status == AgentStatus.IMPLEMENTED
    assert "change-verification" in agent.metadata.capabilities
    assert "test-execution" in agent.metadata.capabilities
    assert "failure-diagnosis" in agent.metadata.capabilities
    assert "pytest_runner" in agent.metadata.allowed_tools
    assert "hash_verifier" in agent.metadata.allowed_tools


def test_agent_config_file_present_and_valid():
    config_path = (
        Path(__file__).resolve().parents[1] / "config" / "agent_config.json"
    )
    assert config_path.exists(), f"agent_config.json missing at {config_path}"
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["agent_id"] == "verification_and_test"
    assert "pytest_runner" in data["allowed_tools"]
    assert "hash_verifier" in data["allowed_tools"]


def test_validate_action_handling():
    agent = VerificationAndTestAgent()
    proj_dir = Path(".")

    # Valid actions
    assert agent.validate(proj_dir, AgentRequest("verification_and_test", parameters={"action": "verify"})) == []
    assert agent.validate(proj_dir, AgentRequest("verification_and_test", parameters={"action": "status"})) == []
    assert agent.validate(proj_dir, AgentRequest("verification_and_test", parameters={"action": "verify_regression"})) == []

    # Invalid action
    invalid_res = agent.validate(proj_dir, AgentRequest("verification_and_test", parameters={"action": "unsupported_action"}))
    assert len(invalid_res) == 1
    assert "Unknown verification action" in invalid_res[0]

    # run_tests without targets/components/changed_files
    missing_targets = agent.validate(proj_dir, AgentRequest("verification_and_test", parameters={"action": "run_tests"}))
    assert len(missing_targets) == 1
    assert "requires at least one of" in missing_targets[0]


def test_status_action_execution():
    agent = VerificationAndTestAgent()
    req = AgentRequest("verification_and_test", parameters={"action": "status"})
    res = agent.execute(Path("."), req)
    assert res.status == "succeeded"
    assert "active and operational" in res.summary
    assert res.metadata["agent_id"] == "verification_and_test"
    assert "verify" in res.metadata["supported_actions"]


def test_component_mapper_resolution():
    mapper = ComponentMapper()
    # File mapping
    comps = mapper.map_changed_files_to_components([
        "SYSTEM/registries/agent_registry.py",
        "SYSTEM/agents/architecture_validator/agent.py",
        "VIDEO_ENGINE/stages/transcribe.py",
    ])
    assert "agent_registry" in comps
    assert "architecture_validator" in comps
    assert "video_pipeline" in comps

    # Target resolution
    targets = mapper.resolve_test_targets(["agent_registry", "architecture_validator"])
    assert "tests/test_phase1_system_agents_restructuring.py" in targets
    assert "tests/test_agent_architecture_reorg.py" in targets
    assert "tests/test_phase5_architecture_validator.py" in targets


def test_component_mapper_requirement_partitioning():
    mapper = ComponentMapper()
    verifiable, unverified = mapper.analyze_requirements([
        "All unit tests must pass",
        "Keep the video stage outputs unchanged",
        "Require manual review and human sign-off on staging video",
        "Connect to live internet external cloud cluster",
    ])
    assert len(verifiable) == 2
    assert "All unit tests must pass" in verifiable
    assert len(unverified) == 2
    assert any("human sign-off" in u for u in unverified)
    assert any("live internet" in u for u in unverified)


def test_diagnostician_categorization():
    diag = Diagnostician()

    # 1. Implementation Defect
    defect_check = CheckResult(
        check_id="pytest_tests_test_sample.py",
        component="test",
        check_type="pytest",
        status=TestExecutionStatus.EXECUTED,
        exit_code=1,
        stdout="FAILED tests/test_sample.py::test_fail - AssertionError: 4 != 5",
        failed_count=1,
    )
    diagnoses = diag.diagnose_failures([defect_check])
    assert len(diagnoses) == 1
    assert diagnoses[0].category == FailureCategory.IMPLEMENTATION_DEFECT
    assert any("AssertionError" in h for h in diagnoses[0].root_cause_hints)

    # 2. Missing Dependency
    missing_dep_check = CheckResult(
        check_id="pytest_tests_test_missing.py",
        component="test",
        check_type="pytest",
        status=TestExecutionStatus.EXECUTED,
        exit_code=1,
        stderr="ModuleNotFoundError: No module named 'nonexistent_package'",
        failed_count=1,
    )
    diagnoses2 = diag.diagnose_failures([missing_dep_check])
    assert diagnoses2[0].category == FailureCategory.MISSING_DEPENDENCY
    assert any("nonexistent_package" in h for h in diagnoses2[0].root_cause_hints)

    # 3. Timeout
    timeout_check = CheckResult(
        check_id="pytest_tests_test_timeout.py",
        component="test",
        check_type="pytest",
        status=TestExecutionStatus.BLOCKED,
        exit_code=-1,
        stderr="Execution timed out after 60 seconds.",
        failed_count=1,
        failure_category=FailureCategory.TIMEOUT,
    )
    diagnoses3 = diag.diagnose_failures([timeout_check])
    assert diagnoses3[0].category == FailureCategory.TIMEOUT


def test_diagnose_failure_action():
    agent = VerificationAndTestAgent()
    req = AgentRequest(
        "verification_and_test",
        parameters={
            "action": "diagnose_failure",
            "component": "agent_registry",
            "stdout": "FAILED tests/test_agent.py::test_reg - ValueError: Agent ID already registered",
        },
    )
    res = agent.execute(Path("."), req)
    assert res.status == "succeeded"
    assert "Diagnosis completed" in res.summary
    assert res.metadata["primary_diagnosis"]["category"] == "IMPLEMENTATION_DEFECT"


def test_evidence_based_verdicts_cannot_mark_unexecuted_as_passed():
    agent = VerificationAndTestAgent()

    # Empty checks -> BLOCKED
    assert agent._determine_verdict([], []) == VerificationVerdict.BLOCKED

    # Check with failure -> FAIL
    fail_chk = CheckResult("c1", "comp", "pytest", TestExecutionStatus.EXECUTED, exit_code=1, failed_count=1)
    assert agent._determine_verdict([fail_chk], []) == VerificationVerdict.FAIL

    # Check that was blocked -> BLOCKED
    blocked_chk = CheckResult("c2", "comp", "pytest", TestExecutionStatus.BLOCKED, exit_code=1, failed_count=1)
    assert agent._determine_verdict([blocked_chk], []) == VerificationVerdict.BLOCKED

    # Check with skipped test and passing test -> PASS (skipped does not fail, but is not counted as pass)
    pass_chk = CheckResult("c3", "comp", "pytest", TestExecutionStatus.EXECUTED, exit_code=0, passed_count=5, skipped_count=1)
    assert agent._determine_verdict([pass_chk], []) == VerificationVerdict.PASS

    # Passing checks with unverified requirements -> CONDITIONAL
    assert agent._determine_verdict([pass_chk], ["Requires human sign-off"]) == VerificationVerdict.CONDITIONAL


def test_read_only_guarantee(tmp_path: Path):
    """Verifies that verification operations leave source files bit-for-bit unmutated."""
    agent = VerificationAndTestAgent()
    test_file = tmp_path / "sample_source.py"
    test_file.write_text("x = 42\n", encoding="utf-8")
    before_bytes = test_file.read_bytes()

    req = AgentRequest(
        "verification_and_test",
        parameters={
            "action": "verify",
            "components": ["video_pipeline"],
            "changed_files": [str(test_file)],
            "requirements": ["Source file check"],
        },
    )
    agent.execute(tmp_path, req)

    after_bytes = test_file.read_bytes()
    assert before_bytes == after_bytes, "Source file was modified during verification!"
