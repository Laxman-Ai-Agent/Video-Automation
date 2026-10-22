"""Immutable security, permission, and coordination audit history."""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class AuditRecord:
    """Immutable audit record for agent security, tool access, and gate checks."""
    audit_id: str = field(default_factory=lambda: f"aud_{uuid.uuid4().hex[:12]}")
    event_type: str = "security_check"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    agent_id: str = ""
    target: str = ""
    outcome: str = "allowed"  # 'allowed', 'denied', 'flagged'
    reason: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuditRecord:
        return cls(**data)
