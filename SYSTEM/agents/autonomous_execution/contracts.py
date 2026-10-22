"""Contracts, data models, and lifecycle states for Autonomous Execution & Recovery.

Defines:
- TaskLifecycleState: Authoritative lifecycle states.
- FailureCategory: Taxonomy of execution failure modes.
- StepExecutionRecord: Discrete step execution state and attempt history.
- TaskRequirementSpec: Immutable locked requirements and acceptance criteria.
- TaskCheckpoint: Durable state snapshot for crash recovery and resume.
- ExecutionReport: Final evidence-based verdict and outcome summary.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal


class TaskLifecycleState(str, Enum):
    """Authoritative lifecycle states for autonomous tasks."""
    PENDING = "pending"
    PLANNING = "planning"
    READY = "ready"
    RUNNING = "running"
    RECOVERING = "recovering"
    WAITING_APPROVAL = "waiting_approval"
    BLOCKED = "blocked"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"


class FailureCategory(str, Enum):
    """Categorization of step execution failures for governed recovery."""
    TRANSIENT = "transient"
    DEFECT = "defect"
    PREREQUISITE_MISSING = "prerequisite_missing"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    TIMEOUT = "timeout"
    APPROVAL_REQUIRED = "approval_required"
    SECURITY_DENIED = "security_denied"
    PERMANENT = "permanent"


@dataclass
class StepExecutionRecord:
    """Detailed record of a single plan step execution and recovery attempts."""
    step_id: str
    title: str = ""
    assigned_agent_id: str = ""
    action: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    status: str = "pending"  # pending, running, succeeded, failed, blocked, skipped, waiting_approval
    attempts: int = 0
    max_attempts: int = 3
    is_irreversible: bool = False
    result: dict[str, Any] | None = None
    error: str | None = None
    failure_category: str | None = None
    failure_history: list[dict[str, Any]] = field(default_factory=list)
    started_at: float | None = None
    completed_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StepExecutionRecord:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class TaskRequirementSpec:
    """Immutable locked requirement specification and acceptance criteria.

    Calculates an authoritative SHA-256 fingerprint (spec_hash) to detect and prevent
    scope creep, criteria deletion, or unauthorized requirement mutation during execution.
    """
    task_id: str
    purpose: str
    requested_outcome: str
    required_changes: list[str] = field(default_factory=list)
    excluded_changes: list[str] = field(default_factory=list)
    scope_boundaries: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    required_agents: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    required_approvals: list[str] = field(default_factory=list)
    verification_requirements: list[str] = field(default_factory=list)
    retry_policy: dict[str, Any] = field(
        default_factory=lambda: {
            "max_step_retries": 3,
            "max_task_retries": 6,
            "backoff_base_seconds": 0.05,
            "max_backoff_seconds": 1.0,
        }
    )
    spec_hash: str = ""
    created_at: str = ""
    locked: bool = True

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.spec_hash:
            self.spec_hash = self.compute_hash()

    def compute_hash(self) -> str:
        """Computes a deterministic SHA-256 hash across immutable requirement fields."""
        payload = {
            "task_id": self.task_id,
            "purpose": self.purpose.strip(),
            "requested_outcome": self.requested_outcome.strip(),
            "required_changes": sorted(self.required_changes),
            "excluded_changes": sorted(self.excluded_changes),
            "scope_boundaries": sorted(self.scope_boundaries),
            "acceptance_criteria": sorted(self.acceptance_criteria),
            "required_agents": sorted(self.required_agents),
            "dependencies": sorted(self.dependencies),
            "required_approvals": sorted(self.required_approvals),
            "verification_requirements": sorted(self.verification_requirements),
            "retry_policy": self.retry_policy,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def validate(self) -> list[str]:
        """Validates that mandatory fields are present and hash matches content."""
        errors: list[str] = []
        if not self.task_id or not self.task_id.strip():
            errors.append("Task ID cannot be empty.")
        if not self.purpose or not self.purpose.strip():
            errors.append("Task purpose cannot be empty.")
        if not self.requested_outcome or not self.requested_outcome.strip():
            errors.append("Requested outcome cannot be empty.")
        if not self.acceptance_criteria:
            errors.append("At least one acceptance criterion is required before execution.")

        current_hash = self.compute_hash()
        if self.spec_hash and self.spec_hash != current_hash:
            errors.append(
                f"Spec hash mismatch detected (expected {self.spec_hash[:8]}, computed {current_hash[:8]}). "
                "Requirements have been mutated after locking."
            )
        return errors

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskRequirementSpec:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class TaskCheckpoint:
    """Durable checkpoint enabling safe restart, crash recovery, and resume."""
    checkpoint_id: str
    task_id: str
    spec_hash: str
    state: str = TaskLifecycleState.PENDING.value
    current_step_id: str | None = None
    steps: dict[str, StepExecutionRecord] = field(default_factory=dict)
    completed_steps: list[str] = field(default_factory=list)
    step_results: dict[str, Any] = field(default_factory=dict)
    artifact_refs: list[str] = field(default_factory=list)
    task_retry_count: int = 0
    max_task_retries: int = 6
    unresolved_blockers: list[str] = field(default_factory=list)
    approvals_granted: list[str] = field(default_factory=list)
    verification_summary: dict[str, Any] | None = None
    timestamp: str = ""
    version: int = 1

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if not self.checkpoint_id:
            raw = f"{self.task_id}:{self.version}:{self.state}:{time.time()}"
            self.checkpoint_id = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "task_id": self.task_id,
            "spec_hash": self.spec_hash,
            "state": self.state,
            "current_step_id": self.current_step_id,
            "steps": {k: v.to_dict() if isinstance(v, StepExecutionRecord) else v for k, v in self.steps.items()},
            "completed_steps": self.completed_steps,
            "step_results": self.step_results,
            "artifact_refs": [a.to_dict() if hasattr(a, "to_dict") else a for a in self.artifact_refs],
            "task_retry_count": self.task_retry_count,
            "max_task_retries": self.max_task_retries,
            "unresolved_blockers": self.unresolved_blockers,
            "approvals_granted": self.approvals_granted,
            "verification_summary": self.verification_summary,
            "timestamp": self.timestamp,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskCheckpoint:
        steps_raw = data.get("steps", {})
        parsed_steps: dict[str, StepExecutionRecord] = {}
        for sid, sval in steps_raw.items():
            if isinstance(sval, dict):
                parsed_steps[sid] = StepExecutionRecord.from_dict(sval)
            elif isinstance(sval, StepExecutionRecord):
                parsed_steps[sid] = sval
        data_copy = dict(data)
        data_copy["steps"] = parsed_steps
        return cls(**{k: v for k, v in data_copy.items() if k in cls.__dataclass_fields__})


@dataclass
class ExecutionReport:
    """Final comprehensive evidence-based report of autonomous execution."""
    task_id: str
    final_state: str
    success: bool
    completed_steps: list[str] = field(default_factory=list)
    failed_step: str | None = None
    unresolved_blockers: list[str] = field(default_factory=list)
    retry_stats: dict[str, Any] = field(default_factory=dict)
    verification_verdict: str = "UNVERIFIED"
    frozen_file_check: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
