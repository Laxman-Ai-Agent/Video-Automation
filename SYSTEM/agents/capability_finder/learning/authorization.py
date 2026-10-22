"""Authorization and Operator Authentication for Capability Finder Learning.

Defines:
1. Strongly-typed AuthenticatedOperator model separating authenticated identity, role, and credentials.
2. Anti-spoofing enforcement: unauthenticated caller strings (e.g. authorized_by="system_admin")
   are strictly rejected without cryptographic/credential verification.
3. Privilege escalation prevention: caller-supplied role strings never grant a role.
4. Integration with Laxman Approval infrastructure (ApprovalEngine: a person approves in the UI).
5. Multi-tier role and permission boundaries (standard vs elevated high-risk roles).
6. Immutable audit attribution derived strictly from authenticated credentials.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Optional

logger = logging.getLogger("capability_finder.learning.authorization")

TRUSTED_OPERATOR_ROLES: set[str] = {
    "operator",
    "qa_operator",
    "lead_operator",
    "system_admin",
    "security_officer",
    "laxman_admin",
    "admin",
}

STANDARD_OPERATOR_ROLES: set[str] = {
    "operator",
    "qa_operator",
    "lead_operator",
}

ELEVATED_SECURITY_ROLES: set[str] = {
    "system_admin",
    "security_officer",
    "laxman_admin",
    "admin",
}

AuthMethod = Literal["approval_engine", "trusted_context"]


class SecurityAuthError(Exception):
    """Raised when an operation fails authentication, permission, or anti-spoofing gates."""
    pass


@dataclass
class AuthenticatedOperator:
    """Strongly-typed, verified identity of an authorized human or system operator."""
    operator_id: str
    role: str
    auth_method: AuthMethod
    verified_at: str
    approval_request_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        norm_role = self.role.strip().lower()
        if norm_role not in TRUSTED_OPERATOR_ROLES:
            raise SecurityAuthError(
                f"Unauthorized operator role '{self.role}'. "
                f"Must be a trusted role ({', '.join(sorted(TRUSTED_OPERATOR_ROLES))})."
            )
        self.role = norm_role

    def attribution_string(self) -> str:
        """Returns canonical audit attribution string, e.g. 'laxman_operator (operator)'."""
        return f"{self.operator_id} ({self.role})"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def verify_elevated_role(operator: AuthenticatedOperator, action_desc: str = "operation") -> None:
    """Ensures the operator possesses elevated security privileges."""
    if operator.role not in ELEVATED_SECURITY_ROLES:
        raise SecurityAuthError(
            f"Elevated authorization required for {action_desc}. Operator role '{operator.role}' "
            f"is not permitted. Permitted roles: {', '.join(sorted(ELEVATED_SECURITY_ROLES))}."
        )


def authenticate_operator(
    operator: AuthenticatedOperator | None = None,
    authorized_by: str | None = None,
    operator_id: str | None = None,
    role: str | None = None,
    approval_request_id: str | None = None,
    expected_fingerprint: str | None = None,
    consume_approval: bool = True,
) -> AuthenticatedOperator:
    """Authenticates the requesting operator against the ApprovalEngine.

    Anti-Spoofing Rules:
    1. A caller-supplied role/identity string alone (e.g. authorized_by="system_admin")
       always raises SecurityAuthError.
    2. Identity and role come only from a trusted AuthenticatedOperator (internal backend
       context) or from an approved Laxman approval request, which is consumed once.
    """
    # Path 1: Pre-authenticated operator object from trusted server context
    if operator is not None:
        if not isinstance(operator, AuthenticatedOperator):
            raise SecurityAuthError(f"Expected AuthenticatedOperator instance, got {type(operator).__name__}")
        if operator.role not in TRUSTED_OPERATOR_ROLES:
            raise SecurityAuthError(f"Unauthorized operator role '{operator.role}' in provided operator object.")
        return operator

    # Path 2: Approval Engine request verification
    if approval_request_id is not None and str(approval_request_id).strip():
        req_id = str(approval_request_id).strip()
        try:
            from SYSTEM.approvals.approval_engine import approval_engine
            req = approval_engine.get_request(req_id)
            if req is None:
                raise SecurityAuthError(f"Approval request '{req_id}' not found.")
            if req.status != "approved":
                raise SecurityAuthError(
                    f"Approval request '{req_id}' is not approved (status: '{req.status}')."
                )

            if expected_fingerprint and req.action_fingerprint != expected_fingerprint:
                raise SecurityAuthError(
                    f"Approval request '{req_id}' fingerprint mismatch: expected '{expected_fingerprint}', "
                    f"found '{req.action_fingerprint}'."
                )

            if consume_approval:
                # Single-use consumption
                approval_engine.consume_approval(req_id, req.action_fingerprint)
        except SecurityAuthError:
            raise
        except Exception as e:
            raise SecurityAuthError(f"Approval verification failed: {e}") from e

        # Role and identity derived strictly from ApprovalEngine decision, not caller strings
        op_id = req.reviewer or "Laxman"
        now_ts = datetime.now(timezone.utc).isoformat()
        return AuthenticatedOperator(
            operator_id=op_id,
            role="laxman_admin",
            auth_method="approval_engine",
            verified_at=now_ts,
            approval_request_id=req_id,
            metadata={"decision_at": req.decision_at, "decision_reason": req.decision_reason, "risk_level": req.risk_level},
        )

    # Path 3: Role-spoofing attempt detected (string provided without credentials)
    if authorized_by or role or operator_id:
        claimed = authorized_by or role or operator_id
        raise SecurityAuthError(
            f"Authorization refused: caller-supplied role/identity string '{claimed}' cannot grant "
            f"authorization without credentials. An approved request ID is required to prevent role spoofing."
        )

    # Path 4: Missing all authorization parameters
    raise SecurityAuthError(
        "Authorization refused: explicit credentials (an approved approval_request_id) or "
        "AuthenticatedOperator context is required."
    )
