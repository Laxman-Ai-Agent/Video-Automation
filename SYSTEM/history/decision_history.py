"""Decision history tracking rationale, chosen options, and delegation reasoning."""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class DecisionRecord:
    """Represents an autonomous or delegated decision made by an agent."""
    decision_id: str = field(default_factory=lambda: f"dec_{uuid.uuid4().hex[:12]}")
    agent_id: str = ""
    decision_type: str = "delegation"  # e.g., 'delegation', 'approval_gate', 'template_choice', 'retry'
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    rationale: str = ""
    chosen_option: str = ""
    alternatives_considered: list[str] = field(default_factory=list)
    project_id: str | None = None
    task_id: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DecisionRecord:
        return cls(**data)
