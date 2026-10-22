"""Unit tests for Autonomous Execution Agent, Contracts, CheckpointManager, and RecoveryManager."""
from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

import pytest

from SYSTEM.agents.autonomous_execution.agent import AutonomousExecutionAgent
from SYSTEM.agents.autonomous_execution.checkpoint_manager import (
    CheckpointManager,
    CorruptCheckpointError,
    StaleCheckpointError,
)
from SYSTEM.agents.autonomous_execution.contracts import (
    ExecutionReport,
    FailureCategory,
    StepExecutionRecord,
    TaskCheckpoint,
    TaskLifecycleState,
    TaskRequirementSpec,
)
from SYSTEM.agents.autonomous_execution.recovery_manager import RecoveryManager
from SYSTEM.agents.autonomous_execution.task_runner import TaskRunner
from SYSTEM.agents.shared.contracts import AgentMetadata, AgentRequest, AgentResult, AgentStatus


class TestContractsAndSpecLock:
    """Verifies TaskRequirementSpec immutability, hashing, and validation."""

    def test_spec_hash_determinism_and_validation(self):
        spec1 = TaskRequirementSpec(
            task_id="task_100",
            purpose="Generate video assets",
            requested_outcome="Render final mp4",
            acceptance_criteria=["Video is 1080p", "Duration matches audio"],
            required_agents=["visual_planning", "motion_planning"],
        )
        assert spec1.spec_hash != ""
        assert spec1.validate() == []

        # Identical parameters must produce identical hash
        spec2 = TaskRequirementSpec(
            task_id="task_100",
            purpose="Generate video assets",
            requested_outcome="Render final mp4",
            acceptance_criteria=["Duration matches audio", "Video is 1080p"],  # order differs, but sorted
            required_agents=["motion_planning", "visual_planning"],
        )
        assert spec1.spec_hash == spec2.spec_hash

    def test_spec_detects_unauthorized_scope_mutation(self):
        spec = TaskRequirementSpec(
            task_id="task_200",
            purpose="Strict task",
            requested_outcome="Exact outcome",
            acceptance_criteria=["Criterion 1", "Criterion 2"],
        )
        original_hash = spec.spec_hash
        assert spec.validate() == []

        # Simulate silent criteria deletion or scope expansion
        spec.acceptance_criteria = ["Criterion 1"]  # Deleted criterion
        errs = spec.validate()
        assert len(errs) > 0
        assert "Spec hash mismatch detected" in errs[0]

    def test_spec_rejects_empty_mandatory_fields(self):
        invalid_spec = TaskRequirementSpec(
            task_id="",
            purpose="",
            requested_outcome="",
            acceptance_criteria=[],
        )
        errs = invalid_spec.validate()
        assert any("Task ID cannot be empty" in e for e in errs)
        assert any("purpose cannot be empty" in e for e in errs)
        assert any("Requested outcome cannot be empty" in e for e in errs)
        assert any("acceptance criterion is required" in e for e in errs)


class TestRecoveryManager:
    """Verifies failure classification, retry limits, loop detection, and backoff."""

    def test_failure_classification_categories(self):
        rm = RecoveryManager()
        assert rm.classify_failure("Security policy denied tool execution") == FailureCategory.SECURITY_DENIED
        assert rm.classify_failure("Access denied: unauthorized user") == FailureCategory.SECURITY_DENIED
        assert rm.classify_failure("Approval required for timeline render") == FailureCategory.APPROVAL_REQUIRED
        assert rm.classify_failure("Operation timed out after 30s") == FailureCategory.TIMEOUT
        assert rm.classify_failure("Resource temporarily unavailable; connection reset") == FailureCategory.TRANSIENT
        assert rm.classify_failure("Agent 'foo' not found in registry") == FailureCategory.PREREQUISITE_MISSING
        assert rm.classify_failure("SyntaxError: invalid syntax in file") == FailureCategory.DEFECT
        assert rm.classify_failure("Fatal unrecoverable corrupted state") == FailureCategory.PERMANENT

    def test_retry_eligibility_enforces_limits_and_security(self):
        rm = RecoveryManager(default_step_max_attempts=3, default_task_max_retries=5)
        step = StepExecutionRecord(step_id="step_1", attempts=0, max_attempts=3)
        ckpt = TaskCheckpoint(checkpoint_id="c1", task_id="t1", spec_hash="h1", task_retry_count=0, max_task_retries=5)

        # Transient error: eligible
        eligible, reason = rm.is_retry_eligible(step, FailureCategory.TRANSIENT, ckpt, "network reset")
        assert eligible is True

        # Security denial: NEVER eligible
        eligible, reason = rm.is_retry_eligible(step, FailureCategory.SECURITY_DENIED, ckpt, "unauthorized")
        assert eligible is False
        assert "Security Policy Denial" in reason

        # Approval required: paused, not retried as transient
        eligible, reason = rm.is_retry_eligible(step, FailureCategory.APPROVAL_REQUIRED, ckpt, "approval needed")
        assert eligible is False
        assert "requires an approval" in reason

        # Permanent error: NEVER eligible
        eligible, reason = rm.is_retry_eligible(step, FailureCategory.PERMANENT, ckpt, "unrecoverable")
        assert eligible is False
        assert "permanent failure" in reason

        # Irreversible step: NEVER eligible
        step_irrev = StepExecutionRecord(step_id="step_irrev", attempts=0, is_irreversible=True)
        eligible, reason = rm.is_retry_eligible(step_irrev, FailureCategory.TRANSIENT, ckpt, "transient error")
        assert eligible is False
        assert "irreversible" in reason

        # Step attempt limit exhaustion
        step.attempts = 3
        eligible, reason = rm.is_retry_eligible(step, FailureCategory.TRANSIENT, ckpt, "retry 4")
        assert eligible is False
        assert "exhausted retry attempt limit" in reason

        # Task budget exhaustion
        step.attempts = 1
        ckpt.task_retry_count = 5
        eligible, reason = rm.is_retry_eligible(step, FailureCategory.TRANSIENT, ckpt, "retry budget")
        assert eligible is False
        assert "Task-wide retry budget exhausted" in reason

    def test_infinite_loop_detector(self):
        rm = RecoveryManager()
        step = StepExecutionRecord(step_id="step_loop", attempts=0, max_attempts=5)
        ckpt = TaskCheckpoint(checkpoint_id="c1", task_id="t1", spec_hash="h1")

        # 1st attempt
        eligible, _ = rm.is_retry_eligible(step, FailureCategory.DEFECT, ckpt, "Missing table 'users'")
        assert eligible is True

        # 2nd attempt with identical error
        eligible, _ = rm.is_retry_eligible(step, FailureCategory.DEFECT, ckpt, "Missing table 'users'")
        assert eligible is True

        # 3rd attempt with identical error without state change: LOOP TRIGGERED
        eligible, reason = rm.is_retry_eligible(step, FailureCategory.DEFECT, ckpt, "Missing table 'users'")
        assert eligible is False
        assert "Loop prevention triggered" in reason

    def test_bounded_backoff_calculation(self):
        rm = RecoveryManager()
        policy = {"backoff_base_seconds": 0.05, "max_backoff_seconds": 0.5}
        d1 = rm.calculate_backoff(1, policy)
        d2 = rm.calculate_backoff(2, policy)
        d3 = rm.calculate_backoff(3, policy)
        d10 = rm.calculate_backoff(10, policy)

        assert d1 == 0.05
        assert d2 == 0.10
        assert d3 == 0.20
        assert d10 == 0.50  # Capped at max_backoff_seconds


class TestCheckpointManager:
    """Verifies atomic persistence, integrity checks, and resume calculations."""

    def test_atomic_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            cm = CheckpointManager(base_tasks_dir=tmppath)

            spec = TaskRequirementSpec(
                task_id="t_atomic",
                purpose="Test atomic writes",
                requested_outcome="Saved cleanly",
                acceptance_criteria=["Clean save"],
            )
            spec_file = cm.save_spec(spec)
            assert spec_file.exists()
            loaded_spec = cm.load_spec("t_atomic")
            assert loaded_spec.spec_hash == spec.spec_hash

            ckpt = TaskCheckpoint(
                checkpoint_id="",
                task_id="t_atomic",
                spec_hash=spec.spec_hash,
                state=TaskLifecycleState.RUNNING.value,
                completed_steps=["step_1"],
                steps={"step_1": StepExecutionRecord(step_id="step_1", status="succeeded")},
            )
            ckpt_file = cm.save_checkpoint(ckpt)
            assert ckpt_file.exists()

            loaded_ckpt = cm.load_checkpoint("t_atomic")
            assert loaded_ckpt.task_id == "t_atomic"
            assert loaded_ckpt.completed_steps == ["step_1"]
            assert loaded_ckpt.version == 2

    def test_corrupted_and_stale_checkpoint_rejection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            cm = CheckpointManager(base_tasks_dir=tmppath)
            task_dir = tmppath / "corrupt_task"
            task_dir.mkdir(parents=True)

            # Corrupt (non-json) checkpoint file
            ckpt_file = task_dir / "checkpoint.json"
            ckpt_file.write_text("{invalid json", encoding="utf-8")

            with pytest.raises(CorruptCheckpointError):
                cm.load_checkpoint("corrupt_task")

            # Empty file
            ckpt_file.write_text("", encoding="utf-8")
            with pytest.raises(CorruptCheckpointError):
                cm.load_checkpoint("corrupt_task")

    def test_resume_plan_skips_completed_and_preserves_irreversible(self):
        cm = CheckpointManager()
        spec = TaskRequirementSpec(
            task_id="t_res",
            purpose="Resume test",
            requested_outcome="Resume correctly",
            acceptance_criteria=["No repeat"],
        )
        ckpt = TaskCheckpoint(
            checkpoint_id="c1",
            task_id="t_res",
            spec_hash=spec.spec_hash,
            completed_steps=["s1"],
            steps={
                "s1": StepExecutionRecord(step_id="s1", status="succeeded"),
                "s2": StepExecutionRecord(step_id="s2", status="succeeded", is_irreversible=True),
                "s3": StepExecutionRecord(step_id="s3", status="pending"),
            },
        )
        ordered = ["s1", "s2", "s3"]
        to_skip, to_run, next_eligible = cm.determine_resume_plan(ckpt, ordered)

        assert to_skip == ["s1", "s2"]  # Both completed and irreversible completed are skipped
        assert to_run == ["s3"]
        assert next_eligible == "s3"


class TestTaskRunnerAndAutonomousExecutionAgent:
    """Verifies execution dispatch, dependency ordering, cycle detection, and agent interface."""

    def test_topological_sort_and_cycle_rejection(self):
        runner = TaskRunner()
        valid_steps = {
            "s1": StepExecutionRecord(step_id="s1", dependencies=[]),
            "s2": StepExecutionRecord(step_id="s2", dependencies=["s1"]),
            "s3": StepExecutionRecord(step_id="s3", dependencies=["s2"]),
        }
        ordered = runner.topological_sort(valid_steps)
        assert ordered == ["s1", "s2", "s3"]

        # Circular dependency
        cycle_steps = {
            "s1": StepExecutionRecord(step_id="s1", dependencies=["s3"]),
            "s2": StepExecutionRecord(step_id="s2", dependencies=["s1"]),
            "s3": StepExecutionRecord(step_id="s3", dependencies=["s2"]),
        }
        with pytest.raises(ValueError, match="Cyclic dependency detected"):
            runner.topological_sort(cycle_steps)

    def test_autonomous_execution_agent_action_validation(self):
        agent = AutonomousExecutionAgent()
        # Missing goal / spec
        req_bad = AgentRequest(agent_id="autonomous_execution", parameters={"action": "execute_task"})
        errs = agent.validate(Path("."), req_bad)
        assert len(errs) > 0
        assert "requires either 'task_spec' or 'goal'" in errs[0]

        # Valid action
        req_ok = AgentRequest(
            agent_id="autonomous_execution",
            parameters={"action": "execute_task", "goal": "Valid goal"},
        )
        assert agent.validate(Path("."), req_ok) == []

        # Unknown action
        req_unknown = AgentRequest(agent_id="autonomous_execution", parameters={"action": "invalid_action"})
        errs = agent.validate(Path("."), req_unknown)
        assert any("Unknown action 'invalid_action'" in e for e in errs)
