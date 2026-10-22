"""Durable execution history models and tracking for SYSTEM agents."""
from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


@dataclass
class ExecutionRecord:
    """Represents a discrete agent execution attempt."""
    execution_id: str = field(default_factory=lambda: f"exec_{uuid.uuid4().hex[:12]}")
    agent_id: str = ""
    task_id: str = ""
    project_id: str | None = None
    stage_id: str | None = None
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str | None = None
    duration_ms: float = 0.0
    status: Literal["running", "succeeded", "failed", "blocked", "cancelled"] = "running"
    inputs_summary: dict[str, Any] = field(default_factory=dict)
    outputs_summary: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    retry_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def mark_completed(self, status: Literal["succeeded", "failed", "blocked", "cancelled"], outputs: dict[str, Any] | None = None, error: str | None = None) -> None:
        self.status = status
        self.completed_at = datetime.now(timezone.utc).isoformat()
        if outputs:
            self.outputs_summary = outputs
        if error:
            self.error_message = error

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionRecord:
        return cls(**data)
