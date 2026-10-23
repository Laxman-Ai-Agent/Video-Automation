"""Canonical Security Policy Agent for the Dark World Video Generation Agent System."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from SYSTEM.agents.security_policy.contracts import (
    PolicyDecision,
    PolicyState,
    RiskLevel,
    SecurityRequest,
)
from SYSTEM.agents.security_policy.enforcer import (
    SecurityPolicyEnforcer,
    SecurityPolicyViolationError,
)
from SYSTEM.agents.security_policy.evaluator import PolicyEvaluator
from SYSTEM.agents.shared.base_agent import BaseAgent
from SYSTEM.agents.shared.contracts import (
    AgentCategory,
    AgentMetadata,
    AgentRequest,
    AgentResult,
    AgentStatus,
)

logger = logging.getLogger("security_policy.agent")


class SecurityPolicyAgent(BaseAgent):
    """Canonical Security Policy Agent coordinating policy evaluation, risk classification,
    and enforcement boundaries for video generation automation."""

    def __init__(self, metadata: AgentMetadata | None = None) -> None:
        if metadata is None:
            metadata = AgentMetadata(
                agent_id="security_policy",
                name="Security Policy Agent",
                version="1.0.0",
                category=AgentCategory.SYSTEM_SUBAGENT,
                status=AgentStatus.IMPLEMENTED,
                purpose=(
                    "Evaluates security policies, agent permissions, tool access, file and sandbox "
                    "boundaries, approval requirements, and enforcement for the video automation system."
                ),
                capabilities=[
                    "policy-evaluation",
                    "agent-authorization",
                    "tool-access-control",
                    "file-boundary-enforcement",
                    "approval-verification",
                    "risk-classification",
                    "security-audit",
                ],
                allowed_tools=[
                    "agent_registry",
                    "tool_registry",
                    "approval_engine",
                    "policy_enforcer",
                    "hash_verifier",
                ],
                owner="system",
            )
        super().__init__(metadata)
        self.evaluator = PolicyEvaluator()
        self.enforcer = SecurityPolicyEnforcer(self.evaluator)

    def set_agent_registry(self, registry: Any) -> None:
        """Configures the agent registry reference used for policy checks."""
        self.evaluator._agent_registry = registry

    def validate(self, project_dir: Path, request: AgentRequest) -> list[str]:
        """Validates that a security request contains a recognized action."""
        action = request.parameters.get("action", "evaluate")
        allowed = {
            "evaluate",
            "evaluate_policy",
            "enforce",
            "check_agent_permission",
            "check_file_access",
            "check_tool_access",
            "check_approval",
            "status",
        }
        if action not in allowed:
            return [f"Unknown security action '{action}'. Allowed: {', '.join(sorted(allowed))}"]
        return []

    def execute(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        """Executes policy evaluation, enforcement, or specialized domain security checks."""
        action = request.parameters.get("action", "evaluate")

        if action in ("evaluate", "evaluate_policy"):
            return self._handle_evaluate(project_dir, request)
        elif action == "enforce":
            return self._handle_enforce(project_dir, request)
        elif action == "check_agent_permission":
            return self._handle_check_agent(project_dir, request)
        elif action == "check_file_access":
            return self._handle_check_file(project_dir, request)
        elif action == "check_tool_access":
            return self._handle_check_tool(project_dir, request)
        elif action == "check_approval":
            return self._handle_check_approval(project_dir, request)
        elif action == "status":
            return self._handle_status(project_dir, request)
        else:
            return AgentResult(
                agent_id=self.agent_id,
                status="failed",
                error=f"Unsupported action: {action}",
            )

    def _build_security_request(self, project_dir: Path, request: AgentRequest) -> SecurityRequest:
        """Extracts and normalizes parameters into a SecurityRequest."""
        params = request.parameters
        target_agent = params.get("target_agent_id") or params.get("agent_id") or request.agent_id
        operation = params.get("operation") or params.get("op") or "execute"
        resource = params.get("resource") or params.get("target") or params.get("path") or ""

        return SecurityRequest(
            agent_id=target_agent,
            operation=operation,
            resource=str(resource),
            parameters=params.get("parameters") or {k: v for k, v in params.items() if k not in ("action", "agent_id", "target_agent_id", "operation", "resource")},
            payload=params.get("payload", {}),
            operator_id=params.get("operator_id"),
            role=params.get("role"),
            approval_request_id=params.get("approval_request_id"),
            project_dir=str(project_dir) if project_dir else None,
            metadata=params.get("metadata", {}),
        )

    def _handle_evaluate(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        sec_req = self._build_security_request(project_dir, request)
        decision = self.evaluator.evaluate(sec_req)

        status = "succeeded"
        summary = (
            f"Policy evaluation completed: {decision.state.value.upper()} (Rule: {decision.rule_id}). "
            f"Risk: {decision.risk_level.value}. {decision.reason}"
        )

        return AgentResult(
            agent_id=self.agent_id,
            stage_id=request.stage_id or "security",
            project_id=request.project_id or "system",
            status=status,
            summary=summary,
            metadata={
                "decision": decision.to_dict(),
                "allowed": decision.allowed,
                "state": decision.state.value,
                "rule_id": decision.rule_id,
                "risk_level": decision.risk_level.value,
            },
        )

    def _handle_enforce(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        sec_req = self._build_security_request(project_dir, request)
        try:
            decision = self.enforcer.enforce(sec_req)
            return AgentResult(
                agent_id=self.agent_id,
                stage_id=request.stage_id or "security",
                project_id=request.project_id or "system",
                status="succeeded",
                summary=f"Enforcement passed: Operation '{decision.operation}' allowed by rule {decision.rule_id}.",
                metadata={
                    "decision": decision.to_dict(),
                    "enforced": True,
                    "allowed": True,
                },
            )
        except SecurityPolicyViolationError as sve:
            return AgentResult(
                agent_id=self.agent_id,
                stage_id=request.stage_id or "security",
                project_id=request.project_id or "system",
                status="failed",
                error=str(sve),
                summary=f"Enforcement BLOCKED: {sve.decision.reason} (Rule: {sve.decision.rule_id})",
                metadata={
                    "decision": sve.decision.to_dict(),
                    "enforced": True,
                    "allowed": False,
                    "violation": True,
                },
            )

    def _handle_check_agent(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        params = request.parameters
        sec_req = SecurityRequest(
            agent_id=params.get("target_agent_id", ""),
            operation=params.get("operation", "check_permission"),
            resource=params.get("resource", ""),
            role=params.get("role"),
            approval_request_id=params.get("approval_request_id"),
        )
        decision = self.evaluator.evaluate(sec_req)
        return AgentResult(
            agent_id=self.agent_id,
            status="succeeded",
            summary=f"Agent permission check: {decision.state.value.upper()} (Rule: {decision.rule_id}).",
            metadata={"decision": decision.to_dict(), "allowed": decision.allowed},
        )

    def _handle_check_file(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        params = request.parameters
        sec_req = SecurityRequest(
            agent_id=params.get("target_agent_id", request.agent_id),
            operation=params.get("operation", "file_read"),
            resource=params.get("path") or params.get("resource", ""),
            role=params.get("role"),
            approval_request_id=params.get("approval_request_id"),
        )
        decision = self.evaluator.evaluate(sec_req)
        return AgentResult(
            agent_id=self.agent_id,
            status="succeeded",
            summary=f"File access check: {decision.state.value.upper()} (Rule: {decision.rule_id}).",
            metadata={"decision": decision.to_dict(), "allowed": decision.allowed},
        )

    def _handle_check_tool(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        params = request.parameters
        sec_req = SecurityRequest(
            agent_id=params.get("target_agent_id", request.agent_id),
            operation="invoke_tool",
            resource=params.get("tool_id") or params.get("resource", ""),
            parameters={"tool_id": params.get("tool_id")},
            role=params.get("role"),
            approval_request_id=params.get("approval_request_id"),
        )
        decision = self.evaluator.evaluate(sec_req)
        return AgentResult(
            agent_id=self.agent_id,
            status="succeeded",
            summary=f"Tool access check: {decision.state.value.upper()} (Rule: {decision.rule_id}).",
            metadata={"decision": decision.to_dict(), "allowed": decision.allowed},
        )

    def _handle_check_approval(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        params = request.parameters
        sec_req = SecurityRequest(
            agent_id=params.get("target_agent_id", request.agent_id),
            operation=params.get("operation", "execute_approved_action"),
            resource=params.get("resource", ""),
            approval_request_id=params.get("approval_request_id"),
            payload=params.get("payload", {}),
        )
        decision = self.evaluator.evaluate(sec_req)
        return AgentResult(
            agent_id=self.agent_id,
            status="succeeded",
            summary=f"Approval verification: {decision.state.value.upper()} (Rule: {decision.rule_id}).",
            metadata={"decision": decision.to_dict(), "allowed": decision.allowed},
        )

    def _handle_status(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        return AgentResult(
            agent_id=self.agent_id,
            status="succeeded",
            summary="Security Policy Agent active with operational Evaluator and fail-closed Enforcer.",
            metadata={
                "agent_id": self.agent_id,
                "status": "operational",
                "rules": [
                    "SEC-AGT-001..002 (Identity & Registration)",
                    "SEC-AUTH-001..003 (Anti-spoofing & Role claims)",
                    "SEC-FILE-000, SEC-FILE-002..005 (Secrets, path confinement, destructive operations)",
                    "SEC-TOOL-001..004 (Tool allowlists & permissions)",
                    "SEC-SKILL-001..004 (Declarative vs executable, sandbox, promotion)",
                    "SEC-APPR-001..006 (Approval engine, fingerprints)",
                ],
            },
        )
