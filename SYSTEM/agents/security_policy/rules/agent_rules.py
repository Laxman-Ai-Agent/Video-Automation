"""Agent identity, registration, capabilities, and anti-spoofing rules."""
from __future__ import annotations

from typing import Any, Optional

from SYSTEM.agents.capability_finder.learning.authorization import (
    ELEVATED_SECURITY_ROLES,
    STANDARD_OPERATOR_ROLES,
    TRUSTED_OPERATOR_ROLES,
)
from SYSTEM.agents.security_policy.contracts import (
    PolicyDecision,
    PolicyState,
    RiskLevel,
    SecurityRequest,
)


def evaluate_agent_identity(request: SecurityRequest, registry: Any) -> Optional[PolicyDecision]:
    """Validates that the requesting agent is properly registered in AgentRegistry."""
    agent_id = (request.agent_id or "").strip()
    if not agent_id:
        return PolicyDecision(
            state=PolicyState.DENY,
            rule_id="SEC-AGT-001",
            requesting_agent_id="",
            operation=request.operation,
            resource=request.resource,
            risk_level=RiskLevel.HIGH,
            reason="Requesting agent ID is empty or missing.",
            missing_evidence=["valid_agent_id"],
        )

    # Check AgentRegistry
    agent_meta = registry.get(agent_id)
    if agent_meta is None:
        return PolicyDecision(
            state=PolicyState.DENY,
            rule_id="SEC-AGT-002",
            requesting_agent_id=agent_id,
            operation=request.operation,
            resource=request.resource,
            risk_level=RiskLevel.HIGH,
            reason=f"Agent '{agent_id}' is not registered in the authoritative AgentRegistry.",
            missing_evidence=["registered_agent_metadata"],
        )

    return None


def evaluate_anti_spoofing(request: SecurityRequest) -> Optional[PolicyDecision]:
    """Enforces strict anti-spoofing: arbitrary role strings or claims without credentials are rejected."""
    # 1. Self-approval prevention
    if request.agent_id == "security_policy" and request.operation in ("approve", "promote_skill", "modify_policy", "grant_access"):
        return PolicyDecision(
            state=PolicyState.DENY,
            rule_id="SEC-AUTH-001",
            requesting_agent_id=request.agent_id,
            operation=request.operation,
            resource=request.resource,
            risk_level=RiskLevel.CRITICAL,
            reason="Security Policy Agent cannot self-approve its own restricted operations.",
        )

    # 2. Check unverified role claims
    claimed_role = (request.role or "").strip().lower()
    if claimed_role:
        # Check if role is even a recognized trusted role
        if claimed_role not in TRUSTED_OPERATOR_ROLES:
            return PolicyDecision(
                state=PolicyState.DENY,
                rule_id="SEC-AUTH-002",
                requesting_agent_id=request.agent_id,
                operation=request.operation,
                resource=request.resource,
                risk_level=RiskLevel.HIGH,
                reason=f"Claimed operator role '{request.role}' is not a recognized trusted role.",
                missing_evidence=["recognized_role_specification"],
            )

        # Anti-spoofing check: claiming an elevated role without an approved Laxman approval request
        if claimed_role in ELEVATED_SECURITY_ROLES:
            if not request.approval_request_id:
                return PolicyDecision(
                    state=PolicyState.DENY,
                    rule_id="SEC-AUTH-003",
                    requesting_agent_id=request.agent_id,
                    operation=request.operation,
                    resource=request.resource,
                    risk_level=RiskLevel.CRITICAL,
                    reason=f"Unauthenticated role spoofing rejected. Claimed elevated role '{claimed_role}' requires an approved Approval Request ID.",
                    missing_evidence=["verified_credentials", "approval_request_id"],
                )

    return None
