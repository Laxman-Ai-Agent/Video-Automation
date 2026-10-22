"""FastAPI routes for Agent Registry inspection and durable Agent Communication log."""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from SYSTEM.agents.shared import communication
from SYSTEM.registries.agent_registry import registry
from SYSTEM.agents.shared.contracts import AgentMessage, ArtifactRef, MessageType

router = APIRouter(tags=["agents"])


class SendMessageBody(BaseModel):
    stage_id: str
    sender_agent_id: str
    content: str
    recipient_agent_ids: list[str] = Field(default_factory=list)
    message_type: str = MessageType.AGENT_MESSAGE.value
    artifact_refs: list[dict[str, Any]] = Field(default_factory=list)
    run_id: str | None = None
    correlation_id: str | None = None
    parent_message_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    task_id: str | None = None
    telugu_activity: str | None = None
    progress_percent: float | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    source_agent_id: str | None = None
    target_agent_id: str | None = None


@router.get("/agents")
def list_agents(
    include_system: bool = Query(default=False),
    all: bool = Query(default=False),
) -> list[dict[str, Any]]:
    """Lists canonical agents in the registry with their metadata, capabilities, and statuses."""
    if include_system or all:
        return [a.to_dict() for a in registry.list_all_agents()]
    return [a.to_dict() for a in registry.list_video_agents()]


@router.get("/agents/{agent_id}")
def get_agent(agent_id: str) -> dict[str, Any]:
    """Retrieves metadata and capabilities for a specific agent."""
    meta = registry.get(agent_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found in registry")
    return meta.to_dict()


@router.get("/projects/{pid}/agent-communications")
def get_project_communications(
    pid: str,
    agent_id: str | None = None,
    stage_id: str | None = None,
    message_type: str | None = None,
    status: str | None = None,
    search: str | None = None,
    task_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: int | None = None,
    reverse: bool = Query(default=True),
) -> dict[str, Any]:
    """Queries project-scoped communications with filtering, bounded limits, and pagination."""
    msgs = communication.query_messages(
        project_id=pid,
        agent_id=agent_id,
        stage_id=stage_id,
        message_type=message_type,
        status=status,
        search=search,
        task_id=task_id,
        limit=limit,
        cursor=cursor,
        reverse=reverse,
    )
    return {
        "project_id": pid,
        "count": len(msgs),
        "messages": [m.to_dict() for m in msgs],
    }


@router.post("/projects/{pid}/agent-communications", status_code=201)
def send_project_communication(pid: str, body: SendMessageBody) -> dict[str, Any]:
    """Appends an authentic agent message to the project's canonical communications.jsonl log."""
    # Verify sender agent exists in registry
    sender = body.sender_agent_id or body.source_agent_id or ""
    if not registry.get(sender):
        raise HTTPException(status_code=400, detail=f"Sender agent '{sender}' is not registered")

    msg = communication.publish_message(
        project_id=pid,
        stage_id=body.stage_id,
        sender_agent_id=sender,
        recipient_agent_ids=body.recipient_agent_ids,
        message_type=body.message_type,
        content=body.content,
        artifact_refs=body.artifact_refs,
        run_id=body.run_id,
        correlation_id=body.correlation_id,
        parent_message_id=body.parent_message_id,
        metadata=body.metadata,
        task_id=body.task_id,
        telugu_activity=body.telugu_activity,
        progress_percent=body.progress_percent,
        details=body.details,
        source_agent_id=body.source_agent_id or sender,
        target_agent_id=body.target_agent_id,
    )
    return msg.to_dict()


@router.get("/projects/{pid}/agent-communications/stream")
async def stream_project_communications(pid: str):
    """Server-Sent Events (SSE) endpoint providing live, real-time message stream for the project."""
    async def event_generator():
        async for event in communication.subscribe_events(pid):
            yield f"event: {event['event']}\ndata: {event['data']}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/stream/events")
@router.get("/stream/events")
async def stream_events_global(pid: str | None = None, project_id: str | None = None):
    """Server-Sent Events (SSE) endpoint matching Stage 4 /api/stream/events specification."""
    target_pid = pid or project_id or "default"

    async def event_generator():
        async for event in communication.subscribe_events(target_pid):
            yield f"event: {event['event']}\ndata: {event['data']}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


from SYSTEM.history.agent_growth_store import growth_store


@router.get("/agents/{agent_id}/growth")
def get_agent_growth(agent_id: str) -> dict[str, Any]:
    """Retrieves capability readiness growth snapshots and maturity metrics for an agent."""
    return growth_store.get_agent_growth(agent_id)


@router.get("/agents/{agent_id}/upgrades")
def list_agent_upgrades(agent_id: str) -> list[dict[str, Any]]:
    """Retrieves verified upgrade history records for an agent."""
    return growth_store.get_agent_upgrades(agent_id)


@router.post("/agents/{agent_id}/upgrades")
def record_agent_upgrade(agent_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Appends a verified upgrade record for an agent."""
    body["agent_id"] = agent_id
    return growth_store.record_agent_upgrade(body)


@router.get("/agents/{agent_id}/intelligence")
def get_agent_intelligence(agent_id: str) -> dict[str, Any]:
    """Returns combined intelligence profile: registry metadata, growth metrics, and upgrade history."""
    meta = registry.get(agent_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found in registry")
    growth = growth_store.get_agent_growth(agent_id)
    upgrades = growth_store.get_agent_upgrades(agent_id)
    return {
        "metadata": meta.to_dict(),
        "growth": growth,
        "upgrades": upgrades,
    }

