"""Authoritative Autonomous Execution Agent.

Implements the bounded task execution and recovery component for the LAXMAN-AUTONOMOUS MASTER SYSTEM.

BOUNDARIES:
- Works as a bounded task execution and recovery engine.
- Does NOT compete with or replace MainArchitectureAgent (which coordinates goals, requirements, and strategies).
- Does NOT replace or bypass VIDEO_ENGINE.pipeline.orchestrator (which owns video generation stages).
- Does NOT silently modify acceptance criteria or bypass SecurityPolicyAgent.
- Employs VerificationAndTestAgent and bit-for-bit SHA-256 checks before declaring completion.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from SYSTEM.agents.shared.base_agent import BaseAgent
from SYSTEM.agents.shared.contracts import (
    AgentCategory,
    AgentMetadata,
    AgentRequest,
    AgentResult,
    AgentStatus,
)

from .checkpoint_manager import CheckpointManager
from .contracts import (
    StepExecutionRecord,
    TaskCheckpoint,
    TaskLifecycleState,
    TaskRequirementSpec,
)
from .recovery_manager import RecoveryManager
from .task_runner import TaskRunner

logger = logging.getLogger("autonomous_execution")


class AutonomousExecutionAgent(BaseAgent):
    """System subagent for bounded autonomous task execution, durable checkpointing, and recovery."""

    def __init__(self, metadata: AgentMetadata | None = None) -> None:
        if metadata is None:
            metadata = AgentMetadata(
                agent_id="autonomous_execution",
                name="Autonomous Execution Agent",
                version="1.0.0",
                category=AgentCategory.SYSTEM_SUBAGENT,
                status=AgentStatus.IMPLEMENTED,
                purpose=(
                    "Supervises autonomous task execution, bounded failure recovery, durable checkpointing, "
                    "and independent completion verification without competing with the Main Architecture Agent "
                    "or Video Pipeline Orchestrator."
                ),
                capabilities=[
                    "task-execution",
                    "bounded-recovery",
                    "checkpoint-persistence",
                    "task-resume",
                    "loop-prevention",
                    "verification-dispatch",
                ],
                allowed_tools=[
                    "agent_registry",
                    "security_policy",
                    "verification_and_test",
                    "checkpoint_manager",
                    "recovery_manager",
                ],
                owner="system",
            )
        super().__init__(metadata)
        self.checkpoint_manager = CheckpointManager()
        self.recovery_manager = RecoveryManager()
        self.runner = TaskRunner(
            checkpoint_manager=self.checkpoint_manager,
            recovery_manager=self.recovery_manager,
        )

    def validate(self, project_dir: Path, request: AgentRequest) -> list[str]:
        """Validates action parameters and required fields."""
        action = request.parameters.get("action", "execute_task")
        allowed_actions = {"execute_task", "resume_task", "get_checkpoint", "recover_step", "status"}
        if action not in allowed_actions:
            return [f"Unknown action '{action}'. Allowed: {', '.join(sorted(allowed_actions))}"]

        errors: list[str] = []
        if action == "execute_task":
            if not request.parameters.get("task_spec") and not request.parameters.get("goal"):
                errors.append("execute_task requires either 'task_spec' or 'goal' parameter.")
        elif action in ("resume_task", "get_checkpoint"):
            if not request.parameters.get("task_id"):
                errors.append(f"{action} requires 'task_id' parameter.")
        return errors

    def execute(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        """Executes task management, recovery, or checkpoint queries."""
        action = request.parameters.get("action", "execute_task")

        if action == "execute_task":
            return self._handle_execute_task(project_dir, request)
        elif action == "resume_task":
            return self._handle_resume_task(project_dir, request)
        elif action == "get_checkpoint":
            return self._handle_get_checkpoint(project_dir, request)
        elif action == "recover_step":
            return self._handle_recover_step(project_dir, request)
        else:
            return self._handle_status(project_dir, request)

    def _handle_execute_task(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        """Parses specification and steps, then executes the autonomous task plan."""
        spec_data = request.parameters.get("task_spec")
        if isinstance(spec_data, dict):
            spec = TaskRequirementSpec.from_dict(spec_data)
        elif isinstance(spec_data, TaskRequirementSpec):
            spec = spec_data
        else:
            # Construct spec from goal and parameters
            task_id = request.correlation_id or request.parameters.get("task_id", f"task_{request.stage_id or 'auto'}")
            spec = TaskRequirementSpec(
                task_id=task_id,
                purpose=request.parameters.get("goal", "Execute autonomous task"),
                requested_outcome=request.parameters.get("requested_outcome", "Complete specified subtasks successfully"),
                acceptance_criteria=request.parameters.get("acceptance_criteria", ["All steps complete successfully"]),
                required_agents=request.parameters.get("required_agents", []),
                required_changes=request.parameters.get("required_changes", []),
                excluded_changes=request.parameters.get("excluded_changes", []),
                scope_boundaries=request.parameters.get("scope_boundaries", []),
                dependencies=request.parameters.get("dependencies", []),
            )

        # Parse steps
        raw_steps = request.parameters.get("steps", [])
        steps: list[StepExecutionRecord] = []
        for s in raw_steps:
            if isinstance(s, dict):
                steps.append(StepExecutionRecord.from_dict(s))
            elif isinstance(s, StepExecutionRecord):
                steps.append(s)

        report = self.runner.execute_task(spec, steps, project_dir=project_dir, resume=False)
        return AgentResult(
            agent_id=self.agent_id,
            status="succeeded" if report.success else "failed",
            summary=f"Autonomous task '{spec.task_id}' finished in state '{report.final_state}' (Success: {report.success}).",
            error=report.error,
            metadata=report.to_dict(),
        )

    def _handle_resume_task(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        """Resumes an interrupted task from its latest valid checkpoint."""
        task_id = request.parameters["task_id"]
        try:
            spec = self.checkpoint_manager.load_spec(task_id, custom_dir=project_dir)
            checkpoint = self.checkpoint_manager.load_checkpoint(task_id, custom_dir=project_dir)
        except Exception as e:
            return AgentResult(
                agent_id=self.agent_id,
                status="failed",
                error=f"Cannot resume task '{task_id}': {e}",
            )

        # Re-execute using saved checkpoint and steps
        steps = list(checkpoint.steps.values())
        report = self.runner.execute_task(spec, steps, project_dir=project_dir, resume=True)
        return AgentResult(
            agent_id=self.agent_id,
            status="succeeded" if report.success else "failed",
            summary=f"Resumed autonomous task '{task_id}' finished in state '{report.final_state}' (Success: {report.success}).",
            error=report.error,
            metadata=report.to_dict(),
        )

    def _handle_get_checkpoint(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        """Retrieves checkpoint details for a given task ID."""
        task_id = request.parameters["task_id"]
        try:
            ckpt = self.checkpoint_manager.load_checkpoint(task_id, custom_dir=project_dir)
            return AgentResult(
                agent_id=self.agent_id,
                status="succeeded",
                summary=f"Retrieved checkpoint v{ckpt.version} for task '{task_id}' (State: {ckpt.state}).",
                metadata={"checkpoint": ckpt.to_dict()},
            )
        except Exception as e:
            return AgentResult(
                agent_id=self.agent_id,
                status="failed",
                error=f"Failed to load checkpoint for task '{task_id}': {e}",
            )

    def _handle_recover_step(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        """Evaluates retry eligibility or performs a targeted step recovery."""
        error_msg = request.parameters.get("error", "Unknown error")
        step_id = request.parameters.get("step_id", "step_0")
        cat = self.recovery_manager.classify_failure(error_msg, context=request.parameters)
        step = StepExecutionRecord(
            step_id=step_id,
            attempts=int(request.parameters.get("attempts", 0)),
            max_attempts=int(request.parameters.get("max_attempts", 3)),
            is_irreversible=bool(request.parameters.get("is_irreversible", False)),
        )
        dummy_ckpt = TaskCheckpoint(
            checkpoint_id="eval",
            task_id="eval_task",
            spec_hash="eval_hash",
            task_retry_count=int(request.parameters.get("task_retry_count", 0)),
            max_task_retries=int(request.parameters.get("max_task_retries", 6)),
        )
        eligible, reason = self.recovery_manager.is_retry_eligible(step, cat, dummy_ckpt, error_msg=error_msg)
        return AgentResult(
            agent_id=self.agent_id,
            status="succeeded",
            summary=f"Recovery evaluation: eligible={eligible}, category={cat.value}. {reason}",
            metadata={
                "eligible": eligible,
                "category": cat.value,
                "reason": reason,
                "backoff_seconds": self.recovery_manager.calculate_backoff(step.attempts + 1),
            },
        )

    def _handle_status(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        """Returns health and status of autonomous execution agent."""
        return AgentResult(
            agent_id=self.agent_id,
            status="succeeded",
            summary="Autonomous Execution Agent is active and ready.",
            metadata={
                "version": self.metadata.version,
                "capabilities": self.metadata.capabilities,
                "allowed_tools": self.metadata.allowed_tools,
            },
        )
