"""FastAPI routes for approval requests, their LLM decisions, and the audit trail."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from SYSTEM.approvals.approval_engine import (
    ApprovalEngineError,
    ApprovalNotFoundError,
    approval_engine,
)
from SYSTEM.core.errors import ApiError

router = APIRouter(prefix="/approvals", tags=["approvals"])


class CreateApprovalPayload(BaseModel):
    requester_agent_id: str
    category: Literal["video_engine_agent", "system_subagent", "orchestrator"]
    action_type: str
    risk_level: Literal["low", "medium", "high", "critical"] = "medium"
    action_summary: str
    idempotency_key: str
    payload_for_fingerprint: dict[str, Any]
    affected_files: list[str] = Field(default_factory=list)
    upstream_evidence: dict[str, Any] = Field(default_factory=dict)
    expected_outcomes: list[str] = Field(default_factory=list)
    reversibility: Literal["reversible", "rerunnable", "irreversible"] = "rerunnable"
    rollback_plan: str = ""
    project_id: str | None = None
    expires_in_hours: int = 24


@router.get("/status")
def get_approval_status() -> dict[str, Any]:
    """Returns the pending request count."""
    return {"pending_count": len(approval_engine.list_requests(status="pending"))}


@router.get("")
def list_approvals(
    status: str | None = None,
    category: str | None = None,
    project_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """Lists approval requests with filtering, pending items prioritized first."""
    requests = approval_engine.list_requests(
        status=status,
        category=category,
        project_id=project_id,
        limit=limit,
    )
    return [r.to_dict() for r in requests]


@router.get("/audit")
def get_approval_audit_trail(
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    """Returns recent events from the append-only approvals audit log."""
    return approval_engine.get_audit_trail(limit=limit)


@router.get("/{request_id}")
def get_approval_detail(request_id: str) -> dict[str, Any]:
    """Retrieves full details for a specific approval request."""
    req = approval_engine.get_request(request_id)
    if not req:
        raise ApiError(404, "request_not_found", f"Approval request '{request_id}' not found")
    return req.to_dict()


@router.post("", status_code=201)
def create_approval_request(body: CreateApprovalPayload) -> dict[str, Any]:
    """Submits a new permission request to the Laxman Approval queue."""
    req = approval_engine.submit_request(
        requester_agent_id=body.requester_agent_id,
        category=body.category,
        action_type=body.action_type,
        risk_level=body.risk_level,
        action_summary=body.action_summary,
        idempotency_key=body.idempotency_key,
        payload_for_fingerprint=body.payload_for_fingerprint,
        affected_files=body.affected_files,
        upstream_evidence=body.upstream_evidence,
        expected_outcomes=body.expected_outcomes,
        reversibility=body.reversibility,
        rollback_plan=body.rollback_plan,
        project_id=body.project_id,
        expires_in_hours=body.expires_in_hours,
    )
    return req.to_dict()


@router.post("/{request_id}/llm-decide")
def llm_decide_approval(request_id: str) -> dict[str, Any]:
    """The LLM reviewer decides a pending request (approved, rejected or changes requested); no person decides."""
    try:
        return approval_engine.llm_decide(request_id).to_dict()
    except ApprovalNotFoundError:
        raise ApiError(404, "request_not_found", f"Approval request '{request_id}' not found")
    except ApprovalEngineError as e:
        raise ApiError(e.status_code, e.code, str(e))
