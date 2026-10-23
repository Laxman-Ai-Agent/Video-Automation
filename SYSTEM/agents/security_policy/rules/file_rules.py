"""File and path access boundary rules for Security Policy Agent."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from SYSTEM.agents.security_policy.contracts import (
    PolicyDecision,
    PolicyState,
    RiskLevel,
    SecurityRequest,
)

PROTECTED_SECRET_PATTERNS = [
    ".env",
    ".git",
    "id_rsa",
    "id_ed25519",
    "secret",
    "credentials",
]


def evaluate_file_access(request: SecurityRequest, project_root: Path) -> Optional[PolicyDecision]:
    """Validates file operations (read, write, modify, delete) against path boundaries and protected secrets."""
    operation = (request.operation or "").lower()
    if not (operation.startswith("file_") or "file" in operation or operation in ("read", "write", "delete", "modify", "patch", "overwrite")):
        return None

    resource_str = request.resource or request.parameters.get("path") or request.parameters.get("file_path") or ""
    if not resource_str:
        return PolicyDecision(
            state=PolicyState.DENY,
            rule_id="SEC-FILE-000",
            requesting_agent_id=request.agent_id,
            operation=request.operation,
            resource="",
            risk_level=RiskLevel.MEDIUM,
            reason="File operation requested without specifying a target file or resource path.",
            missing_evidence=["file_path"],
        )

    # Normalize path
    norm_path = resource_str.replace("\\", "/").strip()
    norm_lower = norm_path.lower()

    # 1. Protected secrets and credentials
    for sec_pat in PROTECTED_SECRET_PATTERNS:
        if sec_pat in norm_lower:
            # Check if request has verified elevated authentication
            has_elevated_auth = (
                request.role in ("system_admin", "security_officer", "laxman_admin", "admin")
                and request.approval_request_id is not None
            )
            if not has_elevated_auth:
                return PolicyDecision(
                    state=PolicyState.DENY,
                    rule_id="SEC-FILE-002",
                    requesting_agent_id=request.agent_id,
                    operation=request.operation,
                    resource=resource_str,
                    risk_level=RiskLevel.CRITICAL,
                    reason=f"Access to protected credential/secret pattern '{sec_pat}' denied without elevated authentication.",
                    missing_evidence=["elevated_operator_credentials"],
                )

    # 2. Path traversal outside project root
    try:
        raw_path = Path(resource_str)
        if raw_path.is_absolute():
            resolved = raw_path.resolve()
        else:
            resolved = (project_root / raw_path).resolve()

        resolved_root = project_root.resolve()
        # Verify confinement
        try:
            resolved.relative_to(resolved_root)
        except ValueError:
            return PolicyDecision(
                state=PolicyState.DENY,
                rule_id="SEC-FILE-003",
                requesting_agent_id=request.agent_id,
                operation=request.operation,
                resource=resource_str,
                risk_level=RiskLevel.HIGH,
                reason=f"Path traversal outside project root boundary is forbidden: '{resource_str}'.",
            )
    except Exception as e:
        return PolicyDecision(
            state=PolicyState.DENY,
            rule_id="SEC-FILE-004",
            requesting_agent_id=request.agent_id,
            operation=request.operation,
            resource=resource_str,
            risk_level=RiskLevel.HIGH,
            reason=f"Malformed or unsafe filesystem path: {e}",
        )

    # 3. Destructive deletion operations require confirmation or approval
    if "delete" in operation or operation == "file_delete":
        if not request.approval_request_id:
            return PolicyDecision(
                state=PolicyState.APPROVAL_REQUIRED,
                rule_id="SEC-FILE-005",
                requesting_agent_id=request.agent_id,
                operation=request.operation,
                resource=resource_str,
                risk_level=RiskLevel.HIGH,
                approval_required=True,
                reason=f"File deletion operation on '{resource_str}' requires operator approval.",
            )

    return None
