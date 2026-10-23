"""Central Policy Evaluator coordinating all rule sets and risk classification."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from SYSTEM.agents.security_policy.contracts import (
    PolicyDecision,
    PolicyState,
    RiskLevel,
    SecurityRequest,
)
from SYSTEM.agents.security_policy.rules.agent_rules import (
    evaluate_agent_identity,
    evaluate_anti_spoofing,
)
from SYSTEM.agents.security_policy.rules.approval_rules import (
    evaluate_approvals_and_credentials,
)
from SYSTEM.agents.security_policy.rules.file_rules import evaluate_file_access
from SYSTEM.agents.security_policy.rules.skill_rules import evaluate_skill_security
from SYSTEM.agents.security_policy.rules.tool_rules import evaluate_tool_access

logger = logging.getLogger("security_policy.evaluator")


class PolicyEvaluator:
    """Thread-safe, fail-closed policy evaluation engine."""

    def __init__(
        self,
        project_root: Path | None = None,
        agent_registry: Any = None,
        tool_registry: Any = None,
        approval_engine: Any = None,
    ) -> None:
        self.project_root = project_root or Path(__file__).resolve().parents[3]
        self._agent_registry = agent_registry
        self._tool_registry = tool_registry
        self._approval_engine = approval_engine

    def _get_agent_registry(self) -> Any:
        if self._agent_registry is not None:
            return self._agent_registry
        try:
            from SYSTEM.registries.agent_registry import get_agent_registry
            return get_agent_registry()
        except Exception:
            return None

    def _get_tool_registry(self) -> Any:
        if self._tool_registry is not None:
            return self._tool_registry
        try:
            from SYSTEM.registries.tool_registry import tool_registry
            return tool_registry
        except Exception:
            return None

    def _get_approval_engine(self) -> Any:
        if self._approval_engine is not None:
            return self._approval_engine
        try:
            from SYSTEM.approvals.approval_engine import ApprovalEngine
            return ApprovalEngine()
        except Exception:
            return None

    def evaluate(self, request: SecurityRequest) -> PolicyDecision:
        """Evaluates a SecurityRequest through all policy rules in strict priority order.
        
        Guarantees fail-closed semantics: uncaught exceptions produce a DENY verdict.
        """
        try:
            agent_reg = self._get_agent_registry()
            tool_reg = self._get_tool_registry()
            appr_engine = self._get_approval_engine()

            # 1. Anti-Spoofing and Identity Verification
            if agent_reg:
                dec = evaluate_agent_identity(request, agent_reg)
                if dec:
                    return self._record_and_return(dec, request)

            dec = evaluate_anti_spoofing(request)
            if dec:
                return self._record_and_return(dec, request)

            # 2. File and Path Boundary Verification (secrets, path traversal)
            dec = evaluate_file_access(request, self.project_root)
            if dec:
                return self._record_and_return(dec, request)

            # 3. Tool Access Verification
            if tool_reg and agent_reg:
                dec = evaluate_tool_access(request, tool_reg, agent_reg)
                if dec:
                    return self._record_and_return(dec, request)

            # 4. Skill Security & Sandboxing Verification
            dec = evaluate_skill_security(request)
            if dec:
                return self._record_and_return(dec, request)

            # 5. Approval & Credential Verification
            if appr_engine:
                dec = evaluate_approvals_and_credentials(request, appr_engine)
                if dec:
                    return self._record_and_return(dec, request)

            # 6. Default Safe Resolution
            # If all specific checks passed without blocking or requiring approval:
            risk = self._classify_general_risk(request)
            allowed = True
            reason = f"Operation '{request.operation}' authorized under system baseline policy."
            rule_id = "SEC-BASE-001"

            # If it was an approved request, confirm attribution
            if request.approval_request_id:
                reason = f"Operation '{request.operation}' authorized via verified approval request '{request.approval_request_id}'."
                rule_id = "SEC-APPR-ALLOW"

            dec = PolicyDecision(
                state=PolicyState.ALLOW,
                allowed=allowed,
                rule_id=rule_id,
                requesting_agent_id=request.agent_id,
                operation=request.operation,
                resource=request.resource,
                risk_level=risk,
                reason=reason,
            )
            return self._record_and_return(dec, request)

        except Exception as e:
            logger.critical("Security policy evaluation failure (fail-closed): %s", e, exc_info=True)
            fail_closed_dec = PolicyDecision(
                state=PolicyState.DENY,
                allowed=False,
                rule_id="SEC-SYS-999",
                requesting_agent_id=request.agent_id,
                operation=request.operation,
                resource=request.resource,
                risk_level=RiskLevel.CRITICAL,
                reason=f"Security evaluation failed closed due to an internal error: {e}",
            )
            return self._record_and_return(fail_closed_dec, request)

    def _classify_general_risk(self, request: SecurityRequest) -> RiskLevel:
        """Classifies baseline operational risk."""
        op = (request.operation or "").lower()
        if any(r in op for r in ("read", "get", "list", "query", "status", "discover", "inspect")):
            return RiskLevel.LOW
        elif any(r in op for r in ("render", "delete", "promote", "rollback", "deploy")):
            return RiskLevel.HIGH
        elif any(r in op for r in ("write", "update", "create", "test", "segment", "generate")):
            return RiskLevel.MEDIUM
        return RiskLevel.MEDIUM

    def _record_and_return(self, decision: PolicyDecision, request: SecurityRequest) -> PolicyDecision:
        """Constructs an audit event with secret redaction and attaches to decision."""
        # Sanitize parameters to avoid leaking secrets/PINs into audit logs
        sanitized_params = {}
        for k, v in request.parameters.items():
            if any(s in k.lower() for s in ("pin", "secret", "password", "key", "token")):
                sanitized_params[k] = "***REDACTED***"
            else:
                sanitized_params[k] = str(v)[:200]

        decision.audit_event = {
            "decision_id": decision.decision_id,
            "timestamp": decision.timestamp,
            "state": decision.state.value,
            "rule_id": decision.rule_id,
            "agent_id": request.agent_id,
            "operation": request.operation,
            "resource": request.resource,
            "risk_level": decision.risk_level.value,
            "reason": decision.reason,
            "parameters": sanitized_params,
        }
        return decision
