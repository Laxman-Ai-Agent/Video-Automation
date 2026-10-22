"""Security Policy Enforcement Point and execution boundary guard."""
from __future__ import annotations

import functools
import logging
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

from SYSTEM.agents.security_policy.contracts import (
    PolicyDecision,
    PolicyState,
    RiskLevel,
    SecurityRequest,
)
from SYSTEM.agents.security_policy.evaluator import PolicyEvaluator

logger = logging.getLogger("security_policy.enforcer")

F = TypeVar("F", bound=Callable[..., Any])


class SecurityPolicyViolationError(Exception):
    """Raised when an operation is denied or blocked by the Security Policy Enforcer."""

    def __init__(self, decision: PolicyDecision) -> None:
        self.decision = decision
        msg = (
            f"Security Policy Violation [{decision.rule_id}] - {decision.state.value.upper()}: "
            f"{decision.reason} (Agent: '{decision.requesting_agent_id}', Operation: '{decision.operation}', "
            f"Resource: '{decision.resource}')"
        )
        super().__init__(msg)


class SecurityPolicyEnforcer:
    """Enforcement boundary that intercepts proposed actions and guarantees fail-closed blocking of denied operations."""

    def __init__(self, evaluator: PolicyEvaluator | None = None) -> None:
        self.evaluator = evaluator or PolicyEvaluator()

    def enforce(self, request: SecurityRequest) -> PolicyDecision:
        """Evaluates policy and raises SecurityPolicyViolationError if state is not ALLOW.
        
        This guarantees that denied or approval-required operations CANNOT proceed through
        the guarded execution boundary.
        """
        decision = self.evaluator.evaluate(request)
        if decision.state != PolicyState.ALLOW:
            logger.warning(
                "Enforcement boundary blocked execution of [%s] by [%s] on [%s]: %s (Rule: %s)",
                decision.operation,
                decision.requesting_agent_id,
                decision.resource,
                decision.reason,
                decision.rule_id,
            )
            raise SecurityPolicyViolationError(decision)

        return decision

    def enforce_file_operation(
        self,
        agent_id: str,
        operation: str,
        file_path: str | Path,
        approval_request_id: str | None = None,
        role: str | None = None,
    ) -> PolicyDecision:
        """Enforces policy on file access operations (read, write, delete, patch)."""
        req = SecurityRequest(
            agent_id=agent_id,
            operation=operation,
            resource=str(file_path),
            approval_request_id=approval_request_id,
            role=role,
        )
        return self.enforce(req)

    def enforce_tool_invocation(
        self,
        agent_id: str,
        tool_id: str,
        parameters: dict[str, Any] | None = None,
        approval_request_id: str | None = None,
    ) -> PolicyDecision:
        """Enforces policy on tool invocation requests."""
        req = SecurityRequest(
            agent_id=agent_id,
            operation="invoke_tool",
            resource=tool_id,
            parameters=parameters or {},
            approval_request_id=approval_request_id,
        )
        return self.enforce(req)

    def enforce_protected_action(
        self,
        agent_id: str,
        operation: str,
        resource: str = "",
        parameters: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
        approval_request_id: str | None = None,
        role: str | None = None,
    ) -> PolicyDecision:
        """Enforces policy on high-risk operations (e.g. video rendering, skill promotion, data deletion)."""
        req = SecurityRequest(
            agent_id=agent_id,
            operation=operation,
            resource=resource,
            parameters=parameters or {},
            payload=payload or {},
            approval_request_id=approval_request_id,
            role=role,
        )
        return self.enforce(req)

    def guard(
        self,
        agent_id: str,
        operation: str,
        resource: str = "",
        approval_request_id: str | None = None,
    ) -> Callable[[F], F]:
        """Decorator that ensures the wrapped callable only executes if policy evaluates to ALLOW."""
        def decorator(func: F) -> F:
            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                req = SecurityRequest(
                    agent_id=agent_id,
                    operation=operation,
                    resource=resource,
                    approval_request_id=approval_request_id,
                )
                # This will raise SecurityPolicyViolationError if not allowed
                self.enforce(req)
                return func(*args, **kwargs)
            return wrapper  # type: ignore
        return decorator
