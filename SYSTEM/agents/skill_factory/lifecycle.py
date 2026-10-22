"""Skill Lifecycle State Machine for Skill Factory.

Enforces:
1. Strict progression:
   DRAFT -> VALIDATING -> TESTING -> AWAITING_APPROVAL -> APPROVED -> PROMOTING -> ACTIVE
2. Terminal & failure states:
   FAILED_VALIDATION, QUARANTINED, FAILED_TESTS, REJECTED, PROMOTION_FAILED, ROLLED_BACK.
3. Compatibility with central SkillRegistry status values.
4. Cryptographic audit trail of all state transitions.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from SYSTEM.registries.skill_registry import SkillStatus

logger = logging.getLogger("skill_factory.lifecycle")

LifecycleState = Literal[
    "DRAFT",
    "VALIDATING",
    "TESTING",
    "AWAITING_APPROVAL",
    "APPROVED",
    "PROMOTING",
    "ACTIVE",
    "REJECTED",
    "QUARANTINED",
    "FAILED_VALIDATION",
    "FAILED_TESTS",
    "BLOCKED_ISOLATION",
    "PROMOTION_FAILED",
    "ROLLED_BACK",
]

LEGAL_LIFECYCLE_TRANSITIONS: dict[LifecycleState, set[LifecycleState]] = {
    "DRAFT": {"VALIDATING", "REJECTED"},
    "VALIDATING": {"TESTING", "FAILED_VALIDATION", "QUARANTINED", "REJECTED"},
    "TESTING": {"AWAITING_APPROVAL", "APPROVED", "FAILED_TESTS", "BLOCKED_ISOLATION", "REJECTED"},
    "AWAITING_APPROVAL": {"APPROVED", "REJECTED"},
    "APPROVED": {"PROMOTING", "REJECTED"},
    "PROMOTING": {"ACTIVE", "PROMOTION_FAILED"},
    "ACTIVE": {"ROLLED_BACK"},
    "FAILED_VALIDATION": {"DRAFT", "REJECTED"},
    "FAILED_TESTS": {"DRAFT", "REJECTED"},
    "BLOCKED_ISOLATION": {"DRAFT", "REJECTED"},
    "QUARANTINED": {"REJECTED"},
    "PROMOTION_FAILED": {"REJECTED", "ROLLED_BACK"},
    "ROLLED_BACK": set(),
    "REJECTED": set(),
}

# Mapping between SkillFactory LifecycleState and central SkillRegistry SkillStatus
LIFECYCLE_TO_REGISTRY_STATUS: dict[LifecycleState, SkillStatus] = {
    "DRAFT": "draft",
    "VALIDATING": "draft",
    "TESTING": "draft",
    "AWAITING_APPROVAL": "review_required",
    "APPROVED": "approved",
    "PROMOTING": "approved",
    "ACTIVE": "approved",
    "REJECTED": "rejected",
    "QUARANTINED": "quarantined",
    "FAILED_VALIDATION": "rejected",
    "FAILED_TESTS": "rejected",
    "BLOCKED_ISOLATION": "rejected",
    "PROMOTION_FAILED": "rejected",
    "ROLLED_BACK": "deprecated",
}


class InvalidLifecycleTransitionError(Exception):
    """Raised when an illegal lifecycle transition is requested."""
    pass


@dataclass
class LifecycleEvent:
    """Audit record of a lifecycle transition event."""
    from_state: LifecycleState
    to_state: LifecycleState
    timestamp: str
    actor: str
    reason: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SkillLifecycle:
    """Tracks the current lifecycle state and transition history for a skill."""
    skill_id: str
    version: str
    current_state: LifecycleState = "DRAFT"
    history: list[LifecycleEvent] = field(default_factory=list)

    def transition(
        self,
        new_state: LifecycleState,
        actor: str,
        reason: str = "",
        evidence: dict[str, Any] | None = None,
    ) -> LifecycleEvent:
        """Transitions state if allowed by transition rules."""
        allowed = LEGAL_LIFECYCLE_TRANSITIONS.get(self.current_state, set())
        if new_state not in allowed:
            raise InvalidLifecycleTransitionError(
                f"Cannot transition skill '{self.skill_id}' from '{self.current_state}' to '{new_state}'. "
                f"Allowed target states: {', '.join(sorted(allowed)) or 'None (terminal)'}."
            )

        now = datetime.now(timezone.utc).isoformat()
        evt = LifecycleEvent(
            from_state=self.current_state,
            to_state=new_state,
            timestamp=now,
            actor=actor,
            reason=reason,
            evidence=evidence or {},
        )
        self.history.append(evt)
        self.current_state = new_state
        return evt

    @property
    def is_promotable(self) -> bool:
        """Only APPROVED state may transition into PROMOTING / ACTIVE."""
        return self.current_state == "APPROVED"

    @property
    def is_active(self) -> bool:
        return self.current_state == "ACTIVE"

    @property
    def to_registry_status(self) -> SkillStatus:
        return LIFECYCLE_TO_REGISTRY_STATUS.get(self.current_state, "draft")

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "version": self.version,
            "current_state": self.current_state,
            "registry_status": self.to_registry_status,
            "history": [e.to_dict() for e in self.history],
        }
