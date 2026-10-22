"""Skill lifecycle, execution boundaries, and promotion security rules."""
from __future__ import annotations

from typing import Any, Optional

from SYSTEM.agents.security_policy.contracts import (
    PolicyDecision,
    PolicyState,
    RiskLevel,
    SecurityRequest,
)


def evaluate_skill_security(request: SecurityRequest) -> Optional[PolicyDecision]:
    """Validates skill-related operations against sandbox isolation, declarative classification, and promotion gates."""
    operation = (request.operation or "").lower()
    if not (operation.startswith("skill_") or "skill" in operation or operation in ("promote_skill", "rollback_skill", "test_skill")):
        return None

    skill_id = request.resource or request.parameters.get("skill_id") or ""
    is_executable = request.parameters.get("is_executable", False)
    content = request.parameters.get("content", "")
    manifest_type = request.parameters.get("manifest_type", "declarative")

    # Determine if skill is executable based on parameters or content inspection
    if not is_executable and content:
        # Check for python execution markers
        if any(marker in content for marker in ("def ", "import ", "class ", "exec(", "eval(", "__import__")):
            is_executable = True

    # 1. Skill Discovery & Inspection (Always safe & low-risk)
    if operation in ("skill_discovery", "discover_skill", "list_skills", "inspect_skill"):
        return PolicyDecision(
            state=PolicyState.ALLOW,
            rule_id="SEC-SKILL-000",
            requesting_agent_id=request.agent_id,
            operation=request.operation,
            resource=skill_id,
            risk_level=RiskLevel.LOW,
            reason="Skill discovery and metadata inspection are low-risk read operations.",
        )

    # 2. Declarative vs Executable Skill Authoring/Testing
    if operation in ("create_skill", "author_skill", "test_skill"):
        if not is_executable:
            return PolicyDecision(
                state=PolicyState.ALLOW,
                rule_id="SEC-SKILL-001",
                requesting_agent_id=request.agent_id,
                operation=request.operation,
                resource=skill_id,
                risk_level=RiskLevel.LOW,
                reason="Declarative Markdown/JSON skills are safe and do not require executable container isolation.",
            )
        else:
            # Executable skill requires sandbox preflight
            sandbox_available = request.parameters.get("sandbox_available", True)
            if not sandbox_available:
                return PolicyDecision(
                    state=PolicyState.BLOCKED,
                    rule_id="SEC-SKILL-002",
                    requesting_agent_id=request.agent_id,
                    operation=request.operation,
                    resource=skill_id,
                    risk_level=RiskLevel.HIGH,
                    reason="Fail-closed: Testing executable skills requires active sandbox isolation backend.",
                    missing_evidence=["active_sandbox_backend"],
                )

    # 3. Skill Promotion to Shared Library
    if operation in ("promote_skill", "skill_promotion"):
        if not request.approval_request_id:
            return PolicyDecision(
                state=PolicyState.APPROVAL_REQUIRED,
                rule_id="SEC-SKILL-003",
                requesting_agent_id=request.agent_id,
                operation=request.operation,
                resource=skill_id,
                risk_level=RiskLevel.HIGH,
                approval_required=True,
                reason=f"Promotion of skill '{skill_id}' to the shared production library requires Laxman approval.",
                missing_evidence=["approval_request_id"],
            )

    # 4. Skill Rollback
    if operation in ("rollback_skill", "skill_rollback"):
        if not request.approval_request_id:
            return PolicyDecision(
                state=PolicyState.APPROVAL_REQUIRED,
                rule_id="SEC-SKILL-004",
                requesting_agent_id=request.agent_id,
                operation=request.operation,
                resource=skill_id,
                risk_level=RiskLevel.HIGH,
                approval_required=True,
                reason=f"Rollback of skill '{skill_id}' requires operator credentials or Laxman approval.",
            )

    return None
