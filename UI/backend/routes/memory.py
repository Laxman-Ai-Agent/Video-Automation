"""FastAPI routes for Central Shared Memory service and candidate review."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from SYSTEM.memory import shared_memory

router = APIRouter(prefix="/memory", tags=["memory"])


class MemoryCandidateRequest(BaseModel):
    title: str
    content: str
    kind: str
    owner: str = "user"
    scope: str = "global"
    confidence: float = 0.5
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    permitted_readers: list[str] = Field(default_factory=lambda: ["*"])
    project_id: str | None = None


class MemoryPromoteRequest(BaseModel):
    reviewer: str
    verification_method: str
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class MemoryRejectRequest(BaseModel):
    reviewer: str
    reason: str


class MemorySupersedeRequest(BaseModel):
    old_memory_id: str
    new_memory_id: str
    reason: str


@router.get("")
def list_memory(
    query: str = "",
    agent_id: str = "*",
    project_id: str | None = None,
    scope: str | None = None,
    kind: str | None = None,
    include_candidates: bool = False,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict[str, Any]]:
    """Retrieves memory items matching query, scope, kind, and authorization filters."""
    items = shared_memory.service.retrieve_memory(
        query=query,
        agent_id=agent_id,
        project_id=project_id,
        scope=scope,  # type: ignore[arg-type]
        kind=kind,    # type: ignore[arg-type]
        include_candidates=include_candidates,
        limit=limit,
    )
    return [i.to_dict() for i in items]


@router.get("/{memory_id}")
def get_memory_item(memory_id: str) -> dict[str, Any]:
    """Retrieves a single memory item by ID."""
    item = shared_memory.service.get_memory(memory_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Memory item '{memory_id}' not found")
    return item.to_dict()


@router.post("/candidates", status_code=201)
def submit_candidate(body: MemoryCandidateRequest) -> dict[str, Any]:
    """Submits an unverified memory candidate into proposed status with secret redaction."""
    item = shared_memory.service.submit_candidate(
        title=body.title,
        content=body.content,
        kind=body.kind,  # type: ignore[arg-type]
        owner=body.owner,
        scope=body.scope,  # type: ignore[arg-type]
        confidence=body.confidence,
        evidence=body.evidence,
        permitted_readers=body.permitted_readers,
        project_id=body.project_id,
    )
    return item.to_dict()


@router.post("/{memory_id}/promote")
def promote_memory_item(memory_id: str, body: MemoryPromoteRequest) -> dict[str, Any]:
    """Promotes a proposed memory candidate to 'verified' with explicit reviewer verification."""
    try:
        updated = shared_memory.service.promote_memory(
            memory_id=memory_id,
            reviewer=body.reviewer,
            verification_method=body.verification_method,
            evidence=body.evidence,
        )
        return updated.to_dict()
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Memory item '{memory_id}' not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{memory_id}/reject")
def reject_memory_item(memory_id: str, body: MemoryRejectRequest) -> dict[str, Any]:
    """Rejects a proposed memory candidate."""
    try:
        updated = shared_memory.service.reject_memory(
            memory_id=memory_id,
            reviewer=body.reviewer,
            reason=body.reason,
        )
        return updated.to_dict()
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Memory item '{memory_id}' not found")


@router.post("/supersede")
def supersede_memory_item(body: MemorySupersedeRequest) -> dict[str, Any]:
    """Supersedes an older memory item with a newer one."""
    try:
        old, new = shared_memory.service.supersede_memory(
            old_memory_id=body.old_memory_id,
            new_memory_id=body.new_memory_id,
            reason=body.reason,
        )
        return {"old": old.to_dict(), "new": new.to_dict()}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
