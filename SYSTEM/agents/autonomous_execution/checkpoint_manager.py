"""Durable checkpoint persistence, atomic storage, and safe resume calculation.

Implements:
1. Atomic write using temporary files and atomic rename to avoid corruption during crashes.
2. Checkpoint schema and integrity validation against locked TaskRequirementSpec.
3. Resumption calculation: identifying completed steps to skip and earliest eligible step to resume.
4. Protection against accidental repetition of completed irreversible actions.
5. Approval revalidation on resume.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from .contracts import (
    StepExecutionRecord,
    TaskCheckpoint,
    TaskLifecycleState,
    TaskRequirementSpec,
)

logger = logging.getLogger("autonomous_execution.checkpoint_manager")


class CheckpointError(Exception):
    """Base exception for checkpoint operations."""


class CorruptCheckpointError(CheckpointError):
    """Raised when a checkpoint file is truncated, invalid JSON, or missing mandatory fields."""


class StaleCheckpointError(CheckpointError):
    """Raised when a checkpoint fails spec hash integrity validation against locked requirements."""


class CheckpointManager:
    """Manages atomic persistence, validation, and safe resume calculation for task checkpoints."""

    def __init__(self, base_tasks_dir: Path | None = None) -> None:
        self.base_tasks_dir = base_tasks_dir or (Path(__file__).resolve().parents[3] / "config" / "tasks")

    def _get_task_dir(self, task_id: str, custom_dir: Path | None = None) -> Path:
        target = (custom_dir / "tasks" / task_id) if custom_dir else (self.base_tasks_dir / task_id)
        target.mkdir(parents=True, exist_ok=True)
        return target

    def get_checkpoint_path(self, task_id: str, custom_dir: Path | None = None) -> Path:
        return self._get_task_dir(task_id, custom_dir) / "checkpoint.json"

    def get_spec_path(self, task_id: str, custom_dir: Path | None = None) -> Path:
        return self._get_task_dir(task_id, custom_dir) / "locked_spec.json"

    def save_spec(self, spec: TaskRequirementSpec, custom_dir: Path | None = None) -> Path:
        """Persists the locked TaskRequirementSpec snapshot."""
        task_dir = self._get_task_dir(spec.task_id, custom_dir)
        spec_file = task_dir / "locked_spec.json"
        tmp_file = task_dir / "locked_spec.json.tmp"

        payload = json.dumps(spec.to_dict(), indent=2, ensure_ascii=False)
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp_file, spec_file)
        return spec_file

    def load_spec(self, task_id: str, custom_dir: Path | None = None) -> TaskRequirementSpec:
        """Loads and validates a locked requirement spec."""
        spec_file = self.get_spec_path(task_id, custom_dir)
        if not spec_file.exists():
            raise FileNotFoundError(f"Locked spec for task '{task_id}' not found at {spec_file}")

        try:
            raw = spec_file.read_text(encoding="utf-8")
            data = json.loads(raw)
            spec = TaskRequirementSpec.from_dict(data)
            errors = spec.validate()
            if errors:
                raise StaleCheckpointError(f"Spec integrity validation failed: {'; '.join(errors)}")
            return spec
        except json.JSONDecodeError as e:
            raise CorruptCheckpointError(f"Locked spec file at {spec_file} is corrupted: {e}")

    def save_checkpoint(self, checkpoint: TaskCheckpoint, custom_dir: Path | None = None) -> Path:
        """Atomically saves a checkpoint snapshot to disk."""
        task_dir = self._get_task_dir(checkpoint.task_id, custom_dir)
        ckpt_file = task_dir / "checkpoint.json"
        tmp_file = task_dir / f"checkpoint.json.{os.getpid()}.tmp"

        checkpoint.version += 1
        data = checkpoint.to_dict()
        payload = json.dumps(data, indent=2, ensure_ascii=False)

        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp_file, ckpt_file)
        logger.debug("Saved atomic checkpoint v%d for task %s", checkpoint.version, checkpoint.task_id)
        return ckpt_file

    def load_checkpoint(self, task_id: str, custom_dir: Path | None = None) -> TaskCheckpoint:
        """Loads and parses a task checkpoint from disk, handling malformed or corrupted files."""
        ckpt_file = self.get_checkpoint_path(task_id, custom_dir)
        if not ckpt_file.exists():
            raise FileNotFoundError(f"Checkpoint for task '{task_id}' not found at {ckpt_file}")

        try:
            raw = ckpt_file.read_text(encoding="utf-8")
            if not raw.strip():
                raise CorruptCheckpointError(f"Checkpoint file at {ckpt_file} is empty (0 bytes).")
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise CorruptCheckpointError(f"Checkpoint file at {ckpt_file} did not contain a valid JSON object.")
            if "task_id" not in data or "spec_hash" not in data:
                raise CorruptCheckpointError(f"Checkpoint at {ckpt_file} missing mandatory keys (task_id or spec_hash).")
            return TaskCheckpoint.from_dict(data)
        except json.JSONDecodeError as e:
            raise CorruptCheckpointError(f"Checkpoint JSON parse error at {ckpt_file}: {e}")

    def validate_checkpoint_integrity(
        self,
        checkpoint: TaskCheckpoint,
        locked_spec: TaskRequirementSpec,
    ) -> list[str]:
        """Verifies checkpoint validity and guarantees it matches the locked spec."""
        errors: list[str] = []
        if checkpoint.task_id != locked_spec.task_id:
            errors.append(f"Task ID mismatch: checkpoint has '{checkpoint.task_id}', spec has '{locked_spec.task_id}'.")
        if checkpoint.spec_hash != locked_spec.spec_hash:
            errors.append(
                f"Locked spec hash mismatch (checkpoint: {checkpoint.spec_hash[:8]}, spec: {locked_spec.spec_hash[:8]}). "
                "The task requirements have been modified externally; checkpoint is stale."
            )
        return errors

    def determine_resume_plan(
        self,
        checkpoint: TaskCheckpoint,
        ordered_step_ids: list[str],
    ) -> tuple[list[str], list[str], str | None]:
        """Calculates resume schedule from checkpoint.

        Returns:
            (completed_steps_to_skip, remaining_steps_to_run, next_eligible_step_id)
        """
        completed = set(checkpoint.completed_steps)
        # Also include any steps marked 'succeeded' in step records
        for sid, rec in checkpoint.steps.items():
            if rec.status == "succeeded":
                completed.add(sid)

        to_skip: list[str] = []
        to_run: list[str] = []

        for sid in ordered_step_ids:
            rec = checkpoint.steps.get(sid)
            if sid in completed:
                # Do not repeat completed actions
                to_skip.append(sid)
            elif rec and rec.is_irreversible and rec.status == "succeeded":
                # Irreversible actions already succeeded must NEVER be rerun
                to_skip.append(sid)
            else:
                to_run.append(sid)

        next_eligible = to_run[0] if to_run else None
        return to_skip, to_run, next_eligible

    def revalidate_approvals(self, checkpoint: TaskCheckpoint) -> list[str]:
        """Revalidates approval conditions on task resume.

        Returns list of step IDs whose approvals are still required before execution.
        """
        pending_approvals: list[str] = []
        for sid, rec in checkpoint.steps.items():
            if rec.action in ("approve", "timeline_approval") or "approval" in rec.title.lower():
                if sid not in checkpoint.approvals_granted:
                    pending_approvals.append(sid)
        return pending_approvals
