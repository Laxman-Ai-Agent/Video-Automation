"""Evaluation candidate promotion integration adapter.

Bridges between Candidate Proposals (config/eval_candidates.json, skills, shared memory)
and the centralized Approval Engine (LLM-decided).
"""
from __future__ import annotations

from typing import Any

from ..approval_engine import ApprovalRequest, approval_engine


def submit_candidate_promotion_request(
    candidate_id: str,
    candidate_type: str,
    target_id: str,
    title: str,
    description: str,
    risk_level: str = "medium",
    evidence: list[dict[str, Any]] | None = None,
    proposed_content: Any = None,
) -> ApprovalRequest:
    """Creates a central approval request for promoting an evaluation candidate and lets the LLM reviewer decide it (the returned request carries the decision)."""
    idempotency_key = f"candidate_promote_{candidate_id}_{target_id}"

    payload = {
        "candidate_id": candidate_id,
        "candidate_type": candidate_type,
        "target_id": target_id,
        "content_summary": str(proposed_content)[:500] if proposed_content else "",
    }

    req = approval_engine.submit_request(
        requester_agent_id="evaluation_engine",
        category="system_subagent",
        action_type=f"{candidate_type}_promotion",
        risk_level=risk_level if risk_level in ("low", "medium", "high", "critical") else "medium",  # type: ignore[arg-type]
        action_summary=f"Authorize promotion of candidate '{title}' ({candidate_type} -> {target_id})",
        idempotency_key=idempotency_key,
        payload_for_fingerprint=payload,
        upstream_evidence={
            "candidate_id": candidate_id,
            "candidate_type": candidate_type,
            "target_id": target_id,
            "description": description,
            "evidence": evidence or [],
        },
        expected_outcomes=[
            f"Promote candidate to verified production {candidate_type}",
            "Update central catalog / memory registry",
        ],
        reversibility="reversible",
        rollback_plan=f"Demote or quarantine {target_id}; restore previous baseline",
    )
    return approval_engine.llm_decide(req.request_id) if req.status == "pending" else req
