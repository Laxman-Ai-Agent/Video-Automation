"""Approval engine verification rules: an approved, unchanged Laxman approval request is the only credential."""
from __future__ import annotations

import logging
from typing import Any, Optional

from SYSTEM.agents.security_policy.contracts import (
    PolicyDecision,
    PolicyState,
    RiskLevel,
    SecurityRequest,
)

logger = logging.getLogger("security_policy.rules.approval")


def evaluate_approvals_and_credentials(request: SecurityRequest, approval_engine: Any) -> Optional[PolicyDecision]:
    """Evaluates operations presenting an approval request, verifying its integrity and state."""
    # 1. Evaluate Approval Request if supplied
    if request.approval_request_id is not None:
        appr_id = request.approval_request_id.strip()
        appr_req = approval_engine.get_request(appr_id)
        if appr_req is None:
            return PolicyDecision(
                state=PolicyState.DENY,
                rule_id="SEC-APPR-001",
                requesting_agent_id=request.agent_id,
                operation=request.operation,
                resource=request.resource,
                risk_level=RiskLevel.HIGH,
                reason=f"Approval request '{appr_id}' not found in the authoritative queue.",
                missing_evidence=["valid_approval_request"],
            )

        if appr_req.status != "approved":
            return PolicyDecision(
                state=PolicyState.DENY,
                rule_id="SEC-APPR-002",
                requesting_agent_id=request.agent_id,
                operation=request.operation,
                resource=request.resource,
                risk_level=RiskLevel.HIGH,
                reason=f"Approval request '{appr_id}' cannot grant access; status is '{appr_req.status}' (must be 'approved').",
                missing_evidence=["approved_status"],
            )

        # Action / scope binding check: ensure approval applies to the requested action
        if appr_req.action_type and request.operation:
            # Check if action_type is compatible with operation
            norm_action = appr_req.action_type.lower()
            norm_op = request.operation.lower()
            if norm_action not in norm_op and norm_op not in norm_action:
                return PolicyDecision(
                    state=PolicyState.DENY,
                    rule_id="SEC-APPR-006",
                    requesting_agent_id=request.agent_id,
                    operation=request.operation,
                    resource=request.resource,
                    risk_level=RiskLevel.HIGH,
                    reason=f"Scope mismatch: Approval '{appr_id}' was granted for action '{appr_req.action_type}', but requested operation is '{request.operation}'.",
                )

        # Action fingerprint verification if payload is provided
        if request.payload and hasattr(appr_req, "action_fingerprint") and appr_req.action_fingerprint:
            try:
                from SYSTEM.approvals.approval_engine import compute_action_fingerprint
                expected_fp = compute_action_fingerprint(
                    action_type=appr_req.action_type,
                    target_id=appr_req.project_id,
                    payload=request.payload,
                )
                if appr_req.action_fingerprint != expected_fp:
                    return PolicyDecision(
                        state=PolicyState.DENY,
                        rule_id="SEC-APPR-003",
                        requesting_agent_id=request.agent_id,
                        operation=request.operation,
                        resource=request.resource,
                        risk_level=RiskLevel.HIGH,
                        reason="Cryptographic action fingerprint mismatch: Payload has changed since approval was granted.",
                        missing_evidence=["matching_action_fingerprint"],
                    )
            except Exception as e:
                logger.error("Fingerprint computation failed: %s", e)

    # 2. High-risk operations require an approved request
    high_risk_ops = ("render_video", "video_rendering", "final_video_delivery", "delete_project", "rollback_pipeline")
    if request.operation in high_risk_ops:
        if not request.approval_request_id:
            return PolicyDecision(
                state=PolicyState.APPROVAL_REQUIRED,
                rule_id="SEC-APPR-005",
                requesting_agent_id=request.agent_id,
                operation=request.operation,
                resource=request.resource,
                risk_level=RiskLevel.HIGH,
                approval_required=True,
                reason=f"High-risk operation '{request.operation}' requires verified Laxman approval before execution.",
                missing_evidence=["approval_request_id"],
            )

    return None
