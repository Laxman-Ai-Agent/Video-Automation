"""Protected Action Execution Guard.

Enforces server-side Laxman Approval checks immediately before executing consequential side-effects.
"""
from __future__ import annotations

from typing import Any

from .approval_engine import ApprovalGuardError, ApprovalRequest, approval_engine


def require_approved_action(request_id: str, expected_fingerprint: str) -> ApprovalRequest:
    """Verifies and consumes an approved request before a protected side-effect executes.

    Raises ApprovalGuardError if the request does not exist, is not approved, or if
    the action fingerprint does not match the approved state.
    """
    return approval_engine.consume_approval(request_id, expected_fingerprint)
