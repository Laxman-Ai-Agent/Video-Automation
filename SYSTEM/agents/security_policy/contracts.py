"""Contracts, schemas, and policy decision data structures for Security Policy Agent."""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class PolicyState(str, Enum):
    """Explicit policy evaluation outcomes."""
    ALLOW = "allow"
    DENY = "deny"
    APPROVAL_REQUIRED = "approval_required"
    BLOCKED = "blocked"


class RiskLevel(str, Enum):
    """Risk tiers for operations in the video automation system."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityRequest:
    """Standardized request submitted to the Security Policy Agent for evaluation."""
    agent_id: str
    operation: str
    resource: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)
    operator_id: Optional[str] = None
    role: Optional[str] = None
    approval_request_id: Optional[str] = None
    project_dir: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SecurityRequest:
        valid_keys = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)


@dataclass
class PolicyDecision:
    """Traceable, immutable record of a security policy decision."""
    decision_id: str = field(default_factory=lambda: f"pol_{uuid.uuid4().hex[:12]}")
    state: PolicyState = PolicyState.DENY
    allowed: bool = False
    rule_id: str = "SEC-DEFAULT-000"
    requesting_agent_id: str = ""
    operation: str = ""
    resource: str = ""
    risk_level: RiskLevel = RiskLevel.MEDIUM
    approval_required: bool = False
    approval_request_id: Optional[str] = None
    required_capabilities: list[str] = field(default_factory=list)
    required_role: Optional[str] = None
    missing_evidence: list[str] = field(default_factory=list)
    reason: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    audit_event: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.state, str):
            self.state = PolicyState(self.state)
        if isinstance(self.risk_level, str):
            self.risk_level = RiskLevel(self.risk_level)
        self.allowed = (self.state == PolicyState.ALLOW)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value
        d["risk_level"] = self.risk_level.value
        return d
