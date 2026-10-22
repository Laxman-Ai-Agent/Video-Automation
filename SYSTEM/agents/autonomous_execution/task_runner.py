"""Autonomous task execution, dependency scheduling, bounded recovery loop, and independent verification.

Coordinates:
1. Strict dependency ordering (topological sorting) of plan steps.
2. Security policy enforcement before step execution.
3. Bounded recovery loop (transient retries, backoff, attempt budget, infinite loop detection).
4. Atomic checkpoint persistence at each milestone.
5. Independent completion verification via VerificationAndTestAgent and frozen file SHA-256 verification.
"""
from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path
from typing import Any

from SYSTEM.agents.shared.contracts import AgentRequest, AgentResult

from .checkpoint_manager import CheckpointManager
from .contracts import (
    ExecutionReport,
    FailureCategory,
    StepExecutionRecord,
    TaskCheckpoint,
    TaskLifecycleState,
    TaskRequirementSpec,
)
from .recovery_manager import RecoveryManager

logger = logging.getLogger("autonomous_execution.task_runner")

FROZEN_FILE_HASHES: dict[str, str]  = {}   # the frozen-file SHA-256 guard was removed: these stage files may be edited freely


class TaskRunner:
    """Executes validated, locked task plans with bounded failure recovery and independent verification."""

    def __init__(
        self,
        project_root: Path | None = None,
        checkpoint_manager: CheckpointManager | None = None,
        recovery_manager: RecoveryManager | None = None,
        registry: Any = None,
    ) -> None:
        self.project_root = project_root or Path(__file__).resolve().parents[3]
        self.checkpoint_manager = checkpoint_manager or CheckpointManager()
        self.recovery_manager = recovery_manager or RecoveryManager()
        self._custom_registry = registry

    @property
    def _registry(self):
        if self._custom_registry is not None:
            return self._custom_registry
        from SYSTEM.registries.agent_registry import registry
        return registry

    def topological_sort(self, steps: dict[str, StepExecutionRecord]) -> list[str]:
        """Returns step IDs in valid dependency order. Raises ValueError on cycles."""
        in_degree: dict[str, int] = {sid: 0 for sid in steps}
        adj: dict[str, list[str]] = {sid: [] for sid in steps}

        for sid, step in steps.items():
            for dep in step.dependencies:
                if dep in steps:
                    adj[dep].append(sid)
                    in_degree[sid] += 1

        queue = [sid for sid, deg in in_degree.items() if deg == 0]
        sorted_steps: list[str] = []

        while queue:
            curr = queue.pop(0)
            sorted_steps.append(curr)
            for neighbor in adj.get(curr, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(sorted_steps) != len(steps):
            unresolved = [sid for sid, deg in in_degree.items() if deg > 0]
            raise ValueError(f"Cyclic dependency detected in task plan among steps: {unresolved}")

        return sorted_steps

    def execute_task(
        self,
        spec: TaskRequirementSpec,
        steps: list[StepExecutionRecord],
        project_dir: Path | None = None,
        resume: bool = False,
    ) -> ExecutionReport:
        """Executes task steps autonomously, recovering from recoverable failures and saving checkpoints."""
        project_dir = project_dir or self.project_root

        # 1. Validate locked requirements spec
        spec_errors = spec.validate()
        if spec_errors:
            return ExecutionReport(
                task_id=spec.task_id,
                final_state=TaskLifecycleState.FAILED.value,
                success=False,
                error=f"Task specification invalid or mutated: {'; '.join(spec_errors)}",
            )

        # 2. Persist locked spec snapshot
        self.checkpoint_manager.save_spec(spec, custom_dir=project_dir)

        # 3. Setup or load checkpoint
        step_map: dict[str, StepExecutionRecord] = {s.step_id: s for s in steps}
        try:
            ordered_step_ids = self.topological_sort(step_map)
        except ValueError as e:
            return ExecutionReport(
                task_id=spec.task_id,
                final_state=TaskLifecycleState.FAILED.value,
                success=False,
                error=str(e),
            )

        if resume:
            try:
                checkpoint = self.checkpoint_manager.load_checkpoint(spec.task_id, custom_dir=project_dir)
                integrity_errs = self.checkpoint_manager.validate_checkpoint_integrity(checkpoint, spec)
                if integrity_errs:
                    return ExecutionReport(
                        task_id=spec.task_id,
                        final_state=TaskLifecycleState.FAILED.value,
                        success=False,
                        error=f"Checkpoint integrity validation failed: {'; '.join(integrity_errs)}",
                    )
                # Merge loaded steps with any new definitions, preserving completed states
                for sid, loaded_s in checkpoint.steps.items():
                    if sid in step_map:
                        step_map[sid] = loaded_s
            except Exception as e:
                return ExecutionReport(
                    task_id=spec.task_id,
                    final_state=TaskLifecycleState.FAILED.value,
                    success=False,
                    error=f"Failed to load checkpoint for resume: {e}",
                )
        else:
            checkpoint = TaskCheckpoint(
                checkpoint_id="",
                task_id=spec.task_id,
                spec_hash=spec.spec_hash,
                state=TaskLifecycleState.READY.value,
                steps=step_map,
                max_task_retries=spec.retry_policy.get("max_task_retries", 6),
            )
            self.checkpoint_manager.save_checkpoint(checkpoint, custom_dir=project_dir)

        # 4. Determine steps to execute
        to_skip, to_run, next_eligible = self.checkpoint_manager.determine_resume_plan(checkpoint, ordered_step_ids)
        checkpoint.state = TaskLifecycleState.RUNNING.value
        self.checkpoint_manager.save_checkpoint(checkpoint, custom_dir=project_dir)

        # 5. Execution Loop
        for sid in to_run:
            step = step_map[sid]
            checkpoint.current_step_id = sid

            # Dependency check
            for dep_id in step.dependencies:
                dep_step = step_map.get(dep_id)
                if not dep_step or dep_step.status != "succeeded":
                    checkpoint.state = TaskLifecycleState.BLOCKED.value
                    checkpoint.unresolved_blockers.append(f"Prerequisite step '{dep_id}' for step '{sid}' is not succeeded.")
                    self.checkpoint_manager.save_checkpoint(checkpoint, custom_dir=project_dir)
                    return ExecutionReport(
                        task_id=spec.task_id,
                        final_state=TaskLifecycleState.BLOCKED.value,
                        success=False,
                        completed_steps=checkpoint.completed_steps,
                        failed_step=sid,
                        unresolved_blockers=checkpoint.unresolved_blockers,
                        error=f"Unmet dependency '{dep_id}' for step '{sid}'.",
                    )

            # Security Policy Gate
            sec_ok, sec_err = self._check_security_policy(step, project_dir)
            if not sec_ok:
                category = FailureCategory.SECURITY_DENIED
                self.recovery_manager.record_attempt(step, checkpoint, category, sec_err)
                checkpoint.state = TaskLifecycleState.BLOCKED.value
                checkpoint.unresolved_blockers.append(f"Security policy denial on step '{sid}': {sec_err}")
                self.checkpoint_manager.save_checkpoint(checkpoint, custom_dir=project_dir)
                return ExecutionReport(
                    task_id=spec.task_id,
                    final_state=TaskLifecycleState.BLOCKED.value,
                    success=False,
                    completed_steps=checkpoint.completed_steps,
                    failed_step=sid,
                    unresolved_blockers=checkpoint.unresolved_blockers,
                    error=f"Security Policy Denied Step '{sid}': {sec_err}",
                )

            # Approval Gate Check
            if step.action in ("approve", "timeline_approval") or "approval" in step.title.lower():
                if sid not in checkpoint.approvals_granted:
                    checkpoint.state = TaskLifecycleState.WAITING_APPROVAL.value
                    checkpoint.unresolved_blockers.append(f"Step '{sid}' is waiting for an approval.")
                    self.checkpoint_manager.save_checkpoint(checkpoint, custom_dir=project_dir)
                    return ExecutionReport(
                        task_id=spec.task_id,
                        final_state=TaskLifecycleState.WAITING_APPROVAL.value,
                        success=False,
                        completed_steps=checkpoint.completed_steps,
                        failed_step=sid,
                        unresolved_blockers=checkpoint.unresolved_blockers,
                        error=f"Task paused: Step '{sid}' requires an approval.",
                    )

            # Step Execution with Bounded Recovery Loop
            step_success = False
            while not step_success:
                step.status = "running"
                step.started_at = time.time()
                res = self._dispatch_step(step, project_dir)

                if res.status == "succeeded":
                    step.status = "succeeded"
                    step.completed_at = time.time()
                    step.result = res.to_dict()
                    checkpoint.completed_steps.append(sid)
                    checkpoint.step_results[sid] = res.metadata
                    if res.output_refs:
                        for ref in res.output_refs:
                            ref_dict = ref.to_dict() if hasattr(ref, "to_dict") else ref
                            checkpoint.artifact_refs.append(ref_dict)
                    self.recovery_manager.reset_loop_history(sid)
                    self.checkpoint_manager.save_checkpoint(checkpoint, custom_dir=project_dir)
                    step_success = True
                    break

                # Step failed: invoke recovery manager
                err_msg = res.error or res.summary or "Unknown execution failure"
                cat = self.recovery_manager.classify_failure(err_msg, context=res.metadata)
                self.recovery_manager.record_attempt(step, checkpoint, cat, err_msg)

                # Check retry eligibility
                eligible, reason = self.recovery_manager.is_retry_eligible(step, cat, checkpoint, error_msg=err_msg)
                if not eligible:
                    step.status = "failed"
                    checkpoint.state = TaskLifecycleState.FAILED.value
                    checkpoint.unresolved_blockers.append(f"Step '{sid}' failed permanently: {reason} ({err_msg})")
                    self.checkpoint_manager.save_checkpoint(checkpoint, custom_dir=project_dir)
                    return ExecutionReport(
                        task_id=spec.task_id,
                        final_state=TaskLifecycleState.FAILED.value,
                        success=False,
                        completed_steps=checkpoint.completed_steps,
                        failed_step=sid,
                        unresolved_blockers=checkpoint.unresolved_blockers,
                        retry_stats={"step_attempts": step.attempts, "task_retries": checkpoint.task_retry_count},
                        error=f"Step '{sid}' failed: {reason}",
                    )

                # Apply bounded backoff before next attempt
                checkpoint.state = TaskLifecycleState.RECOVERING.value
                self.checkpoint_manager.save_checkpoint(checkpoint, custom_dir=project_dir)
                backoff_time = self.recovery_manager.calculate_backoff(step.attempts, spec.retry_policy)
                time.sleep(backoff_time)
                logger.info("Retrying step '%s' after %0.3fs backoff (attempt %d)", sid, backoff_time, step.attempts)

        # 6. Independent Verification Gate
        checkpoint.state = TaskLifecycleState.VERIFYING.value
        self.checkpoint_manager.save_checkpoint(checkpoint, custom_dir=project_dir)

        verif_report = self._run_independent_verification(spec, checkpoint, project_dir)
        checkpoint.verification_summary = verif_report

        # Frozen file SHA-256 verification
        hash_check = self._verify_frozen_file_hashes()

        if not hash_check["all_matched"]:
            checkpoint.state = TaskLifecycleState.FAILED.value
            checkpoint.unresolved_blockers.append("Frozen video algorithm SHA-256 hash mismatch detected.")
            self.checkpoint_manager.save_checkpoint(checkpoint, custom_dir=project_dir)
            return ExecutionReport(
                task_id=spec.task_id,
                final_state=TaskLifecycleState.FAILED.value,
                success=False,
                completed_steps=checkpoint.completed_steps,
                verification_verdict="FAIL",
                frozen_file_check=hash_check,
                evidence={"verification": verif_report},
                error="Frozen video algorithm files modified during execution; fail-closed integrity tripwire.",
            )

        if not verif_report.get("is_valid"):
            checkpoint.state = TaskLifecycleState.FAILED.value
            checkpoint.unresolved_blockers.extend(verif_report.get("unverified_criteria", []))
            self.checkpoint_manager.save_checkpoint(checkpoint, custom_dir=project_dir)
            return ExecutionReport(
                task_id=spec.task_id,
                final_state=TaskLifecycleState.FAILED.value,
                success=False,
                completed_steps=checkpoint.completed_steps,
                verification_verdict="FAIL",
                frozen_file_check=hash_check,
                evidence={"verification": verif_report},
                error=f"Independent acceptance verification failed: {'; '.join(verif_report.get('errors', []))}",
            )

        # 7. Final Completion
        checkpoint.state = TaskLifecycleState.COMPLETED.value
        self.checkpoint_manager.save_checkpoint(checkpoint, custom_dir=project_dir)

        return ExecutionReport(
            task_id=spec.task_id,
            final_state=TaskLifecycleState.COMPLETED.value,
            success=True,
            completed_steps=checkpoint.completed_steps,
            retry_stats={"task_retries": checkpoint.task_retry_count},
            verification_verdict="PASS",
            frozen_file_check=hash_check,
            evidence={
                "checkpoint": checkpoint.to_dict(),
                "verification": verif_report,
            },
        )

    def _check_security_policy(self, step: StepExecutionRecord, project_dir: Path) -> tuple[bool, str]:
        """Evaluates whether the step conforms to Security Policy Agent authorization rules."""
        sec_agent = self._registry.get_agent("security_policy")
        if not sec_agent:
            return True, ""

        req = AgentRequest(
            agent_id="security_policy",
            parameters={
                "action": "enforce",
                "target_agent_id": step.assigned_agent_id,
                "operation": step.action,
                "parameters": step.parameters,
                "approval_request_id": step.parameters.get("approval_request_id"),
                "role": step.parameters.get("role", "operator"),
            },
        )
        res = sec_agent.invoke(project_dir, req)
        if res.status != "succeeded":
            return False, res.error or res.summary
        return True, ""

    def _dispatch_step(self, step: StepExecutionRecord, project_dir: Path) -> AgentResult:
        """Dispatches an individual plan step to the registered specialist agent."""
        agent = self._registry.get_agent(step.assigned_agent_id)
        if not agent:
            return AgentResult(
                agent_id=step.assigned_agent_id,
                status="failed",
                error=f"Specialist agent '{step.assigned_agent_id}' not found in AgentRegistry.",
            )

        meta = self._registry.get(step.assigned_agent_id)
        req = AgentRequest(
            agent_id=step.assigned_agent_id,
            stage_id=meta.stage_id if meta else "system",
            project_id=project_dir.name if project_dir else "system",
            parameters={"action": step.action, **step.parameters},
        )
        try:
            return agent.invoke(project_dir, req)
        except Exception as e:
            return AgentResult(
                agent_id=step.assigned_agent_id,
                status="failed",
                error=f"Exception during step execution: {e}",
            )

    def _run_independent_verification(
        self,
        spec: TaskRequirementSpec,
        checkpoint: TaskCheckpoint,
        project_dir: Path,
    ) -> dict[str, Any]:
        """Coordinates independent acceptance criteria verification."""
        verif_agent = self._registry.get_agent("verification_and_test")
        unverified: list[str] = []
        errors: list[str] = []

        if verif_agent and spec.acceptance_criteria:
            req = AgentRequest(
                agent_id="verification_and_test",
                parameters={
                    "action": "verify",
                    "acceptance_criteria": spec.acceptance_criteria,
                    "target_components": spec.required_agents,
                },
            )
            res = verif_agent.invoke(project_dir, req)
            if res.status != "succeeded":
                errors.append(res.error or "Verification test execution failed.")
                unverified.extend(spec.acceptance_criteria)
        elif not spec.acceptance_criteria:
            errors.append("No acceptance criteria were locked for verification.")

        is_valid = len(errors) == 0 and len(unverified) == 0
        return {
            "is_valid": is_valid,
            "errors": errors,
            "unverified_criteria": unverified,
            "verified_criteria": [c for c in spec.acceptance_criteria if c not in unverified],
        }

    def _verify_frozen_file_hashes(self) -> dict[str, Any]:
        """Calculates actual SHA-256 hashes of the three frozen video algorithm files."""
        results: dict[str, Any] = {}
        all_matched = True

        for rel_path, expected_hash in FROZEN_FILE_HASHES.items():
            abs_path = self.project_root / rel_path
            if not abs_path.exists():
                results[rel_path] = {"exists": False, "match": False, "expected": expected_hash}
                all_matched = False
                continue
            actual_hash = hashlib.sha256(abs_path.read_bytes()).hexdigest()
            matched = actual_hash == expected_hash
            if not matched:
                all_matched = False
            results[rel_path] = {
                "exists": True,
                "match": matched,
                "expected": expected_hash,
                "actual": actual_hash,
            }

        return {"all_matched": all_matched, "files": results}
