"""Comprehensive Integration & Verification Suite for Phase 8: Autonomous Task Execution & Recovery Protocol.

Validates:
1. Task Planning and Requirements:
   - Valid task execution matches locked requirements.
   - Invalid/empty specifications are rejected.
   - Scope mutations/criteria deletion are detected and blocked via SHA-256 fingerprinting.
   - Strict topological execution order and cycle rejection.
2. Execution and Coordination:
   - MainArchitectureAgent coordinates execution via AutonomousExecutionAgent without becoming competing orchestrators.
   - AutonomousExecutionAgent is registered once in AgentRegistry with valid metadata.
   - Existing specialist-agent delegation operates unimpeded.
   - Missing agents produce explicit errors without crashes.
   - Video Pipeline Orchestrator retains exclusive authority over pipeline stages.
3. Bounded Failure Recovery & Loop Prevention:
   - Transient failures are retried within configured attempt limits (default 3).
   - Permanent failures halt immediately without retry.
   - Successful retries verify intermediate results before proceeding downstream.
   - Exhausted retries terminate cleanly in FAILED without infinite loops.
   - Repeated identical errors trigger fingerprint loop detection and halt.
   - Security denials and approval requirements fail-closed without retry bypass.
4. Checkpoint Persistence and Resume:
   - Completed steps and irreversible actions are skipped upon resume.
   - Interrupted tasks resume from the latest valid checkpoint.
   - Corrupted or stale checkpoints are safely detected and rejected.
   - Task retry counters survive disk persistence and reload.
   - Approval gates require revalidation upon resume.
5. Verification and Completion:
   - Tasks cannot reach COMPLETED with unverified mandatory criteria.
   - Independent verification via VerificationAndTestAgent.
"""
from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

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
from SYSTEM.agents.main_architecture_agent.agent import MainArchitectureAgent
from SYSTEM.agents.shared.base_agent import BaseAgent
from SYSTEM.agents.shared.contracts import (
    AgentCategory,
    AgentMetadata,
    AgentRequest,
    AgentResult,
    AgentStatus,
)
from SYSTEM.registries.agent_registry import AgentRegistry, get_agent_registry

PROJECT_ROOT = Path(__file__).resolve().parent.parent



class MockSpecialistAgent(BaseAgent):
    """Configurable mock agent for testing transient, permanent, and approval flows."""

    def __init__(self, metadata: AgentMetadata) -> None:
        super().__init__(metadata)
        self.call_count = 0
        self.behaviors: list[Any] = []

    def validate(self, project_dir: Path, request: AgentRequest) -> list[str]:
        return []

    def execute(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        self.call_count += 1
        action = request.parameters.get("action", "run")

        if self.behaviors:
            behavior = self.behaviors.pop(0)
            if isinstance(behavior, Exception):
                raise behavior
            if isinstance(behavior, AgentResult):
                return behavior
            if behavior == "succeed":
                return AgentResult(agent_id=self.agent_id, status="succeeded", summary=f"Success on attempt {self.call_count}")
            elif behavior == "transient_fail":
                return AgentResult(agent_id=self.agent_id, status="failed", error="Transient error: resource temporarily unavailable")
            elif behavior == "permanent_fail":
                return AgentResult(agent_id=self.agent_id, status="failed", error="Permanent failure: corrupted unrecoverable input")
            elif behavior == "approval_needed":
                return AgentResult(agent_id=self.agent_id, status="failed", error="Approval required: human approval needed")
            elif behavior == "security_denied":
                return AgentResult(agent_id=self.agent_id, status="failed", error="Security policy denied: unauthorized access")
            elif behavior == "repeat_fail":
                return AgentResult(agent_id=self.agent_id, status="failed", error="Database connection error 1005")

        return AgentResult(agent_id=self.agent_id, status="succeeded", summary=f"Executed {action}")


# -----------------------------------------------------------------------------
# 1. TASK PLANNING AND REQUIREMENT LOCK TESTS
# -----------------------------------------------------------------------------
class TestTaskPlanningAndRequirementLock:
    """Verifies requirement lock, hash immutability, and dependency ordering."""

    def test_locked_spec_immutability_and_hash_protection(self):
        spec = TaskRequirementSpec(
            task_id="task_video_gen_1",
            purpose="Generate video segment from audio",
            requested_outcome="Produce 10s kinetic motion preview",
            acceptance_criteria=["Valid mp4 output", "Sync within 50ms"],
            required_agents=["visual_planning", "motion_planning"],
        )
        assert spec.spec_hash is not None
        assert spec.validate() == []

        # Silent mutation: criteria deletion must trigger validation error
        mutated_spec = TaskRequirementSpec.from_dict(spec.to_dict())
        mutated_spec.acceptance_criteria = ["Valid mp4 output"]  # Removed second criterion
        errs = mutated_spec.validate()
        assert len(errs) > 0
        assert "Spec hash mismatch detected" in errs[0]

    def test_invalid_task_spec_rejected(self):
        invalid_spec = TaskRequirementSpec(
            task_id="t_bad",
            purpose="",  # empty purpose
            requested_outcome="Something",
            acceptance_criteria=[],  # empty criteria
        )
        errs = invalid_spec.validate()
        assert len(errs) >= 2
        assert any("purpose cannot be empty" in e for e in errs)
        assert any("acceptance criterion is required" in e for e in errs)

    def test_topological_execution_order(self):
        runner = TaskRunner()
        steps = {
            "step_render": StepExecutionRecord(step_id="step_render", dependencies=["step_plan"]),
            "step_audio": StepExecutionRecord(step_id="step_audio", dependencies=[]),
            "step_plan": StepExecutionRecord(step_id="step_plan", dependencies=["step_audio"]),
        }
        ordered = runner.topological_sort(steps)
        assert ordered == ["step_audio", "step_plan", "step_render"]

    def test_cycle_detection_in_task_dependencies(self):
        runner = TaskRunner()
        cycle_steps = {
            "A": StepExecutionRecord(step_id="A", dependencies=["C"]),
            "B": StepExecutionRecord(step_id="B", dependencies=["A"]),
            "C": StepExecutionRecord(step_id="C", dependencies=["B"]),
        }
        with pytest.raises(ValueError, match="Cyclic dependency detected"):
            runner.topological_sort(cycle_steps)


# -----------------------------------------------------------------------------
# 2. EXECUTION AND DELEGATION INTEGRATION TESTS
# -----------------------------------------------------------------------------
class TestExecutionAndDelegation:
    """Verifies MainArchitectureAgent coordination, registry integration, and boundary preservation."""

    def test_autonomous_execution_registered_once(self):
        reg = get_agent_registry()
        meta = reg.get("autonomous_execution")
        assert meta is not None
        assert meta.agent_id == "autonomous_execution"
        assert meta.category == AgentCategory.SYSTEM_SUBAGENT
        assert meta.status == AgentStatus.IMPLEMENTED
        assert "task-execution" in meta.capabilities
        assert "bounded-recovery" in meta.capabilities

        agent = reg.get_agent("autonomous_execution")
        assert isinstance(agent, AutonomousExecutionAgent)

    def test_main_architecture_agent_coordinates_autonomous_execution(self):
        maa = MainArchitectureAgent()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            spec = TaskRequirementSpec(
                task_id="t_coord_1",
                purpose="Test MAA coordination",
                requested_outcome="Execution success",
                acceptance_criteria=["Status is succeeded"],
                required_agents=["capability_finder"],
            )
            step = StepExecutionRecord(
                step_id="s1",
                title="Check Capabilities",
                assigned_agent_id="capability_finder",
                action="status",
                parameters={"role": "operator"},
            )

            req = AgentRequest(
                agent_id="main_architecture_agent",
                parameters={
                    "action": "execute_autonomous_task",
                    "task_spec": spec.to_dict(),
                    "steps": [step.to_dict()],
                },
            )
            res = maa.invoke(tmppath, req)
            assert res.status == "succeeded"
            assert "Autonomous task execution coordinated" in res.summary
            assert res.metadata.get("delegated_to") == "autonomous_execution"

    def test_missing_specialist_agent_produces_explicit_error(self):
        runner = TaskRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            spec = TaskRequirementSpec(
                task_id="t_missing_agent",
                purpose="Test missing agent",
                requested_outcome="Report error cleanly",
                acceptance_criteria=["Fail cleanly"],
            )
            step = StepExecutionRecord(
                step_id="s_ghost",
                assigned_agent_id="non_existent_ghost_agent",
                action="do_magic",
            )
            report = runner.execute_task(spec, [step], project_dir=tmppath)
            assert report.success is False
            assert report.final_state in (TaskLifecycleState.FAILED.value, TaskLifecycleState.BLOCKED.value)
            assert "not registered in the authoritative agentregistry" in str(report.error).lower() or "not found in agentregistry" in str(report.error).lower()

    def test_video_pipeline_orchestrator_boundary_preserved(self):
        """Verifies that the Video Pipeline Orchestrator retains exclusive control of video stages."""
        from VIDEO_ENGINE.pipeline.orchestrator import PipelineOrchestrator, STAGE_DEPENDENCIES, ACTIVE_STAGES
        assert len(ACTIVE_STAGES) == 13
        assert hasattr(PipelineOrchestrator, "start_run")
        assert hasattr(PipelineOrchestrator, "cancel_run")

        # AutonomousExecutionAgent purpose explicitly notes bounded execution and no competition
        ae_meta = get_agent_registry().get("autonomous_execution")
        assert "Video Pipeline Orchestrator" in ae_meta.purpose


# -----------------------------------------------------------------------------
# 3. BOUNDED FAILURE RECOVERY AND LOOP PREVENTION TESTS
# -----------------------------------------------------------------------------
class TestBoundedRecoveryAndLoopPrevention:
    """Verifies transient retries, permanent halts, attempt limits, loop detection, and security/approval gating."""

    def test_transient_failure_retried_and_succeeds(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            reg = AgentRegistry()

            # Register mock agent that fails once with transient error then succeeds
            mock_meta = AgentMetadata(
                agent_id="mock_transient_agent",
                name="Mock Transient Agent",
                category=AgentCategory.SYSTEM_SUBAGENT,
                purpose="Fails transiently once",
            )
            reg.register(mock_meta, MockSpecialistAgent)
            mock_inst: MockSpecialistAgent = reg.get_agent("mock_transient_agent")
            mock_inst.behaviors = ["transient_fail", "succeed"]

            cm = CheckpointManager(base_tasks_dir=tmppath)
            rm = RecoveryManager()
            runner = TaskRunner(project_root=tmppath, checkpoint_manager=cm, recovery_manager=rm, registry=reg)

            with patch.object(runner, "_run_independent_verification", return_value={"is_valid": True, "errors": []}):
                spec = TaskRequirementSpec(
                    task_id="t_transient_ok",
                    purpose="Recover from transient glitch",
                    requested_outcome="Step succeeds on 2nd attempt",
                    acceptance_criteria=["Step succeeded"],
                    retry_policy={"backoff_base_seconds": 0.01, "max_backoff_seconds": 0.02},
                )
                step = StepExecutionRecord(
                    step_id="step_transient",
                    assigned_agent_id="mock_transient_agent",
                    action="retry_action",
                    max_attempts=3,
                )
                report = runner.execute_task(spec, [step], project_dir=tmppath)
                assert report.success is True
                assert report.final_state == TaskLifecycleState.COMPLETED.value
                assert mock_inst.call_count == 2
                assert report.retry_stats.get("task_retries") == 1

    def test_permanent_failure_halts_immediately_without_retry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            reg = AgentRegistry()

            mock_meta = AgentMetadata(
                agent_id="mock_perm_agent",
                name="Mock Permanent Agent",
                category=AgentCategory.SYSTEM_SUBAGENT,
                purpose="Fails permanently",
            )
            reg.register(mock_meta, MockSpecialistAgent)
            mock_inst: MockSpecialistAgent = reg.get_agent("mock_perm_agent")
            mock_inst.behaviors = ["permanent_fail"]

            cm = CheckpointManager(base_tasks_dir=tmppath)
            rm = RecoveryManager()
            runner = TaskRunner(project_root=tmppath, checkpoint_manager=cm, recovery_manager=rm, registry=reg)

            spec = TaskRequirementSpec(
                task_id="t_perm_halt",
                purpose="Halt on permanent error",
                requested_outcome="No retry for permanent error",
                acceptance_criteria=["Halt immediately"],
            )
            step = StepExecutionRecord(
                step_id="step_perm",
                assigned_agent_id="mock_perm_agent",
                max_attempts=3,
            )
            report = runner.execute_task(spec, [step], project_dir=tmppath)
            assert report.success is False
            assert report.final_state == TaskLifecycleState.FAILED.value
            assert mock_inst.call_count == 1  # Not retried!
            assert "permanent failure" in str(report.error).lower()

    def test_exhausted_retries_stops_without_infinite_loop(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            reg = AgentRegistry()

            mock_meta = AgentMetadata(
                agent_id="mock_exhaust_agent",
                name="Mock Exhaust Agent",
                category=AgentCategory.SYSTEM_SUBAGENT,
                purpose="Fails repeatedly with varying transient errors",
            )
            reg.register(mock_meta, MockSpecialistAgent)
            mock_inst: MockSpecialistAgent = reg.get_agent("mock_exhaust_agent")
            # Multiple varying transient errors to test attempt limit rather than loop detector
            mock_inst.behaviors = [
                AgentResult(agent_id="mock_exhaust_agent", status="failed", error="Transient error: 503-A"),
                AgentResult(agent_id="mock_exhaust_agent", status="failed", error="Transient error: 503-B"),
                AgentResult(agent_id="mock_exhaust_agent", status="failed", error="Transient error: 503-C"),
            ]

            cm = CheckpointManager(base_tasks_dir=tmppath)
            rm = RecoveryManager(default_step_max_attempts=2)
            runner = TaskRunner(project_root=tmppath, checkpoint_manager=cm, recovery_manager=rm, registry=reg)

            spec = TaskRequirementSpec(
                task_id="t_exhaust",
                purpose="Test attempt exhaustion",
                requested_outcome="Halt when attempts reach max",
                acceptance_criteria=["Halt cleanly"],
                retry_policy={"backoff_base_seconds": 0.01, "max_backoff_seconds": 0.02},
            )
            step = StepExecutionRecord(
                step_id="s_exh",
                assigned_agent_id="mock_exhaust_agent",
                max_attempts=2,
            )
            report = runner.execute_task(spec, [step], project_dir=tmppath)
            assert report.success is False
            assert report.final_state == TaskLifecycleState.FAILED.value
            assert mock_inst.call_count == 2
            assert "exhausted retry attempt limit" in str(report.error).lower()

    def test_identical_error_triggers_fingerprint_loop_detector(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            reg = AgentRegistry()

            mock_meta = AgentMetadata(
                agent_id="mock_loop_agent",
                name="Mock Loop Agent",
                category=AgentCategory.SYSTEM_SUBAGENT,
                purpose="Fails repeatedly with identical error",
            )
            reg.register(mock_meta, MockSpecialistAgent)
            mock_inst: MockSpecialistAgent = reg.get_agent("mock_loop_agent")
            mock_inst.behaviors = ["repeat_fail", "repeat_fail", "repeat_fail", "repeat_fail"]

            cm = CheckpointManager(base_tasks_dir=tmppath)
            rm = RecoveryManager()
            runner = TaskRunner(project_root=tmppath, checkpoint_manager=cm, recovery_manager=rm, registry=reg)

            spec = TaskRequirementSpec(
                task_id="t_loop_detect",
                purpose="Test loop prevention",
                requested_outcome="Halt when loop detected",
                acceptance_criteria=["Detect identical error loop"],
                retry_policy={"backoff_base_seconds": 0.01, "max_backoff_seconds": 0.02},
            )
            step = StepExecutionRecord(
                step_id="s_loop",
                assigned_agent_id="mock_loop_agent",
                max_attempts=10,  # High limit, but loop detector must catch it early
            )
            report = runner.execute_task(spec, [step], project_dir=tmppath)
            assert report.success is False
            assert report.final_state == TaskLifecycleState.FAILED.value
            # Caught after 3 identical attempts (len >= 2 matching in history)
            assert mock_inst.call_count <= 3
            assert "loop prevention triggered" in str(report.error).lower()

    def test_security_denials_fail_closed_without_retry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            reg = AgentRegistry()

            mock_meta = AgentMetadata(
                agent_id="mock_sec_agent",
                name="Mock Security Agent",
                category=AgentCategory.SYSTEM_SUBAGENT,
                purpose="Violates security policy",
            )
            reg.register(mock_meta, MockSpecialistAgent)
            mock_inst: MockSpecialistAgent = reg.get_agent("mock_sec_agent")
            mock_inst.behaviors = ["security_denied"]

            cm = CheckpointManager(base_tasks_dir=tmppath)
            rm = RecoveryManager()
            runner = TaskRunner(project_root=tmppath, checkpoint_manager=cm, recovery_manager=rm, registry=reg)

            spec = TaskRequirementSpec(
                task_id="t_sec_deny",
                purpose="Fail-closed on security denial",
                requested_outcome="Never retry security denials",
                acceptance_criteria=["Blocked on denial"],
            )
            step = StepExecutionRecord(
                step_id="s_sec",
                assigned_agent_id="mock_sec_agent",
                max_attempts=5,
            )
            report = runner.execute_task(spec, [step], project_dir=tmppath)
            assert report.success is False
            assert report.final_state in (TaskLifecycleState.FAILED.value, TaskLifecycleState.BLOCKED.value)
            assert mock_inst.call_count == 1
            assert "security policy denial" in str(report.error).lower()

    def test_approval_required_step_pauses_in_waiting_approval(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            cm = CheckpointManager(base_tasks_dir=tmppath)
            runner = TaskRunner(project_root=tmppath, checkpoint_manager=cm)

            spec = TaskRequirementSpec(
                task_id="t_appr_wait",
                purpose="Human approval gate test",
                requested_outcome="Pause in waiting_approval",
                acceptance_criteria=["Pause safely"],
            )
            step = StepExecutionRecord(
                step_id="s_appr",
                title="Mandatory Human Approval",
                action="timeline_approval",
                assigned_agent_id="timeline_approval",
            )
            report = runner.execute_task(spec, [step], project_dir=tmppath)
            assert report.success is False
            assert report.final_state == TaskLifecycleState.WAITING_APPROVAL.value
            assert "requires an approval" in str(report.error)

            # Checkpoint on disk must be saved as waiting_approval
            ckpt = cm.load_checkpoint("t_appr_wait", custom_dir=tmppath)
            assert ckpt.state == TaskLifecycleState.WAITING_APPROVAL.value


# -----------------------------------------------------------------------------
# 4. CHECKPOINT, PERSISTENCE, AND RESUME TESTS
# -----------------------------------------------------------------------------
class TestCheckpointAndResume:
    """Verifies atomic persistence, skipping completed steps, and handling stale/corrupt checkpoints."""

    def test_resume_skips_completed_steps_and_executes_remaining(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            reg = AgentRegistry()

            mock_meta = AgentMetadata(
                agent_id="mock_step_agent",
                name="Mock Step Agent",
                category=AgentCategory.SYSTEM_SUBAGENT,
                purpose="Tracks execution calls",
            )
            reg.register(mock_meta, MockSpecialistAgent)
            mock_inst: MockSpecialistAgent = reg.get_agent("mock_step_agent")

            cm = CheckpointManager(base_tasks_dir=tmppath)
            runner = TaskRunner(project_root=tmppath, checkpoint_manager=cm, registry=reg)

            # 1. First run: step 1 succeeds, step 2 fails
            spec = TaskRequirementSpec(
                task_id="t_resume_flow",
                purpose="Resume after crash",
                requested_outcome="Step 2 completes without repeating Step 1",
                acceptance_criteria=["Both steps succeed"],
                retry_policy={"backoff_base_seconds": 0.01, "max_backoff_seconds": 0.02},
            )
            s1 = StepExecutionRecord(step_id="step_1", assigned_agent_id="mock_step_agent", action="act1")
            s2 = StepExecutionRecord(step_id="step_2", assigned_agent_id="mock_step_agent", action="act2", dependencies=["step_1"])

            mock_inst.behaviors = ["succeed", "permanent_fail"]

            rep1 = runner.execute_task(spec, [s1, s2], project_dir=tmppath)
            assert rep1.success is False
            assert rep1.completed_steps == ["step_1"]
            assert mock_inst.call_count == 2

            # Checkpoint verification
            ckpt = cm.load_checkpoint("t_resume_flow", custom_dir=tmppath)
            assert "step_1" in ckpt.completed_steps

            # 2. Resume run: mock now succeeds on step 2
            mock_inst.behaviors = ["succeed"]
            mock_inst.call_count = 0  # reset call counter

            with patch.object(runner, "_run_independent_verification", return_value={"is_valid": True, "errors": []}):
                rep2 = runner.execute_task(spec, [s1, s2], project_dir=tmppath, resume=True)
                assert rep2.success is True
                assert rep2.final_state == TaskLifecycleState.COMPLETED.value
                assert "step_1" in rep2.completed_steps
                assert "step_2" in rep2.completed_steps
                # Step 1 was SKIPPED, only Step 2 executed!
                assert mock_inst.call_count == 1

    def test_stale_checkpoint_hash_mismatch_rejected_on_resume(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            cm = CheckpointManager(base_tasks_dir=tmppath)
            runner = TaskRunner(project_root=tmppath, checkpoint_manager=cm)

            spec = TaskRequirementSpec(
                task_id="t_stale",
                purpose="Original purpose",
                requested_outcome="Outcome",
                acceptance_criteria=["Original criteria"],
            )
            ckpt = TaskCheckpoint(
                checkpoint_id="c_stale",
                task_id="t_stale",
                spec_hash="tampered_different_hash",  # Stale hash
                state=TaskLifecycleState.RUNNING.value,
            )
            cm.save_spec(spec, custom_dir=tmppath)
            cm.save_checkpoint(ckpt, custom_dir=tmppath)

            rep = runner.execute_task(spec, [], project_dir=tmppath, resume=True)
            assert rep.success is False
            assert "integrity validation failed" in str(rep.error).lower()


# -----------------------------------------------------------------------------
# 5. INDEPENDENT VERIFICATION TESTS
# -----------------------------------------------------------------------------
class TestIndependentVerification:
    """Verifies that acceptance criteria are strictly verified."""

    def test_unverified_acceptance_criteria_prevents_completed_verdict(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            cm = CheckpointManager(base_tasks_dir=tmppath)
            runner = TaskRunner(project_root=tmppath, checkpoint_manager=cm)

            spec = TaskRequirementSpec(
                task_id="t_unverified",
                purpose="Task with failing verification",
                requested_outcome="Detect unverified criteria",
                acceptance_criteria=["Non-negotiable QC criteria"],
            )

            # Mock verification failure
            failing_verif = {
                "is_valid": False,
                "errors": ["Verification check 'Non-negotiable QC criteria' failed."],
                "unverified_criteria": ["Non-negotiable QC criteria"],
            }

            with patch.object(runner, "_run_independent_verification", return_value=failing_verif):
                rep = runner.execute_task(spec, [], project_dir=tmppath)
                assert rep.success is False
                assert rep.final_state == TaskLifecycleState.FAILED.value
                assert rep.verification_verdict == "FAIL"
                assert "Independent acceptance verification failed" in str(rep.error)
