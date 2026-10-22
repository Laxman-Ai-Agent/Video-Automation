"""Tool access, permissions, and execution boundaries rules."""
from __future__ import annotations

from typing import Any, Optional

from SYSTEM.agents.security_policy.contracts import (
    PolicyDecision,
    PolicyState,
    RiskLevel,
    SecurityRequest,
)


def evaluate_tool_access(request: SecurityRequest, tool_registry: Any, agent_registry: Any) -> Optional[PolicyDecision]:
    """Validates that requested tool invocation aligns with tool permissions and agent allowlist."""
    tool_id = request.parameters.get("tool_id") or (
        request.resource if request.operation in ("invoke_tool", "tool_invocation", "run_tool") else None
    )
    if not tool_id:
        return None

    # 1. Check ToolRegistry existence
    tool_def = tool_registry.get(tool_id)
    if tool_def is None:
        return PolicyDecision(
            state=PolicyState.BLOCKED,
            rule_id="SEC-TOOL-001",
            requesting_agent_id=request.agent_id,
            operation=request.operation,
            resource=tool_id,
            risk_level=RiskLevel.MEDIUM,
            reason=f"Tool '{tool_id}' is not registered in the authoritative ToolRegistry.",
            missing_evidence=["registered_tool_definition"],
        )

    # 2. Check Agent allowlist
    agent_meta = agent_registry.get(request.agent_id)
    if agent_meta and agent_meta.allowed_tools:
        if tool_id not in agent_meta.allowed_tools and "*" not in agent_meta.allowed_tools:
            return PolicyDecision(
                state=PolicyState.DENY,
                rule_id="SEC-TOOL-002",
                requesting_agent_id=request.agent_id,
                operation=request.operation,
                resource=tool_id,
                risk_level=RiskLevel.HIGH,
                reason=f"Agent '{request.agent_id}' is not authorized to invoke tool '{tool_id}'. Allowed tools: {sorted(agent_meta.allowed_tools)}.",
            )

    # 3. Check Tool Permission Level
    perm_level = getattr(tool_def, "permission_level", "read_only")
    if perm_level == "admin":
        has_admin_auth = (
            request.role in ("system_admin", "security_officer", "laxman_admin", "admin")
            and request.approval_request_id is not None
        )
        if not has_admin_auth:
            return PolicyDecision(
                state=PolicyState.DENY,
                rule_id="SEC-TOOL-003",
                requesting_agent_id=request.agent_id,
                operation=request.operation,
                resource=tool_id,
                risk_level=RiskLevel.CRITICAL,
                reason=f"Invocation of admin tool '{tool_id}' requires verified elevated administrator authentication.",
                missing_evidence=["elevated_operator_credentials"],
            )

    elif perm_level == "privileged":
        # Privileged tool (e.g. laxman_approvals) requires either system coordinator or human operator context
        is_coordinator = request.agent_id in ("main_architecture_agent", "main_orchestrator", "timeline_approval", "security_policy")
        has_operator_cred = request.approval_request_id is not None
        if not is_coordinator and not has_operator_cred:
            return PolicyDecision(
                state=PolicyState.DENY,
                rule_id="SEC-TOOL-004",
                requesting_agent_id=request.agent_id,
                operation=request.operation,
                resource=tool_id,
                risk_level=RiskLevel.HIGH,
                reason=f"Invocation of privileged tool '{tool_id}' is restricted to coordinators or verified operators.",
            )

    return None
