"""Durable Agent Communication Protocol & Audit Log.

Canonical Storage:
  projects/<project-id>/agent-communications/communications.jsonl
  One UTF-8 JSON object per line, append-only, concurrency-safe.
"""
from __future__ import annotations

import asyncio
import datetime
import json
import threading
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator

from SYSTEM.memory import store
try:
    from backend import config
except ImportError:
    import config
from SYSTEM.core.resilience import redact_secrets
from .contracts import AgentMessage, ArtifactRef, MessageType

_PROJECT_LOCKS: dict[str, threading.Lock] = {}
_LOCK_MUTEX = threading.Lock()
_SUBSCRIBERS: dict[str, set[asyncio.Queue]] = {}
_SUBSCRIBERS_MUTEX = threading.Lock()

def _get_project_lock(pid: str) -> threading.Lock:
    with _LOCK_MUTEX:
        if pid not in _PROJECT_LOCKS:
            _PROJECT_LOCKS[pid] = threading.Lock()
        return _PROJECT_LOCKS[pid]


def redact_object(obj: Any) -> tuple[Any, list[str]]:
    """Recursively redacts strings inside dicts/lists/values."""
    applied: list[str] = []
    if isinstance(obj, str):
        r, a = redact_secrets(obj)
        applied.extend(a)
        return r, applied
    elif isinstance(obj, dict):
        new_dict = {}
        for k, v in obj.items():
            if any(s in k.lower() for s in ("password", "secret", "api_key", "token", "auth")):
                new_dict[k] = "[REDACTED_SECRET]"
                applied.append("secret_field")
            else:
                rv, ra = redact_object(v)
                new_dict[k] = rv
                applied.extend(ra)
        return new_dict, applied
    elif isinstance(obj, list):
        new_list = []
        for item in obj:
            rv, ra = redact_object(item)
            new_list.append(rv)
            applied.extend(ra)
        return new_list, applied
    return obj, applied


def get_communications_dir(pid: str | Path) -> Path:
    if isinstance(pid, Path):
        pdir = pid
    else:
        try:
            pdir = store.project_dir(pid)
        except Exception:
            pdir = config.PROJECTS_DIR / pid
    cdir = pdir / "agent-communications"
    cdir.mkdir(parents=True, exist_ok=True)
    return cdir


def get_communications_file(pid: str) -> Path:
    return get_communications_dir(pid) / "communications.jsonl"


def _notify_subscribers(pid: str, message_dict: dict[str, Any]) -> None:
    with _SUBSCRIBERS_MUTEX:
        queues = list(_SUBSCRIBERS.get(pid, set()))
    for q in queues:
        try:
            q.put_nowait(message_dict)
        except Exception:
            pass


def append_message(project_id: str, message: AgentMessage) -> AgentMessage:
    """Appends an AgentMessage to the project's canonical communications.jsonl log in a concurrency-safe manner."""
    lock = _get_project_lock(project_id)
    cfile = get_communications_file(project_id)

    # Redact sensitive data from content and metadata
    content, c_applied = redact_secrets(message.content)
    meta, m_applied = redact_object(message.metadata)
    message.content = content
    message.metadata = meta
    message.redactions_applied = list(set(message.redactions_applied + c_applied + m_applied))

    if not message.message_id:
        message.message_id = str(uuid.uuid4())
    if not message.timestamp:
        message.timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if not message.project_id:
        message.project_id = project_id

    # Auto-populate Telugu activity and progress if not provided
    try:
        from SYSTEM.agents.shared.telugu_activity_mapper import telugu_activity_mapper
        if not message.telugu_activity:
            t_text, prog = telugu_activity_mapper.map_message_to_telugu(message)
            message.telugu_activity = t_text
            if message.progress_percent is None:
                message.progress_percent = prog
        elif message.progress_percent is None:
            message.progress_percent = telugu_activity_mapper.calculate_progress(
                stage_id=message.stage_id,
                status=message.status,
            )
    except Exception:
        if not message.telugu_activity:
            message.telugu_activity = "పని పురోగతిలో ఉంది."

    with lock:
        # Determine monotonic sequence
        seq = 1
        if cfile.exists():
            try:
                with open(cfile, "r", encoding="utf-8") as f:
                    seq = sum(1 for line in f if line.strip()) + 1
            except OSError:
                seq = 1
        message.sequence = seq

        # Append exactly one line UTF-8 JSON
        raw_json = json.dumps(message.to_dict(), ensure_ascii=False)
        with open(cfile, "a", encoding="utf-8") as f:
            f.write(raw_json + "\n")
            f.flush()

    # Notify any live SSE streams
    _notify_subscribers(project_id, message.to_dict())
    return message


def publish_message(
    project_id: str,
    stage_id: str,
    sender_agent_id: str,
    content: str,
    recipient_agent_ids: list[str] | None = None,
    message_type: str | MessageType = MessageType.AGENT_MESSAGE,
    artifact_refs: list[ArtifactRef | dict[str, Any]] | None = None,
    run_id: str | None = None,
    correlation_id: str | None = None,
    parent_message_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    status: str = "sent",
    task_id: str | None = None,
    telugu_activity: str | None = None,
    progress_percent: float | None = None,
    details: dict[str, Any] | None = None,
    source_agent_id: str | None = None,
    target_agent_id: str | None = None,
) -> AgentMessage:
    """Convenience helper to create and persist an AgentMessage."""
    type_str = message_type.value if isinstance(message_type, MessageType) else str(message_type)
    converted_refs: list[ArtifactRef] = []
    if artifact_refs:
        for r in artifact_refs:
            if isinstance(r, ArtifactRef):
                converted_refs.append(r)
            elif isinstance(r, dict):
                converted_refs.append(ArtifactRef(**r))

    msg = AgentMessage(
        project_id=project_id,
        stage_id=stage_id,
        sender_agent_id=sender_agent_id,
        recipient_agent_ids=recipient_agent_ids or [],
        message_type=type_str,
        content=content,
        artifact_refs=converted_refs,
        run_id=run_id,
        correlation_id=correlation_id,
        parent_message_id=parent_message_id,
        metadata=metadata or {},
        status=status,
        task_id=task_id,
        telugu_activity=telugu_activity,
        progress_percent=progress_percent,
        details=details or {},
        source_agent_id=source_agent_id or sender_agent_id,
        target_agent_id=target_agent_id or ((recipient_agent_ids[0]) if recipient_agent_ids else None),
    )
    return append_message(project_id, msg)


def publish_lifecycle_event(
    project_id: str,
    stage_id: str,
    sender_agent_id: str,
    event: str,
    detail: str = "",
    artifact_refs: list[ArtifactRef] | None = None,
    metadata: dict[str, Any] | None = None,
    run_id: str | None = None,
    correlation_id: str | None = None,
    task_id: str | None = None,
    telugu_activity: str | None = None,
    progress_percent: float | None = None,
    details: dict[str, Any] | None = None,
) -> AgentMessage:
    """Publishes a non-dialogue runtime lifecycle event (e.g., stage_started, stage_completed)."""
    content = f"Lifecycle: {event}" + (f" - {detail}" if detail else "")
    meta = {"event": event, **(metadata or {})}
    status = "completed" if event == "completed" else ("failed" if event == "failed" else ("blocked" if event == "blocked" else "running"))
    return publish_message(
        project_id=project_id,
        stage_id=stage_id,
        sender_agent_id=sender_agent_id,
        recipient_agent_ids=[],
        message_type=MessageType.LIFECYCLE_EVENT,
        content=content,
        artifact_refs=artifact_refs,
        run_id=run_id,
        correlation_id=correlation_id,
        metadata=meta,
        status=status,
        task_id=task_id,
        telugu_activity=telugu_activity,
        progress_percent=progress_percent,
        details=details or {},
    )


def publish_review_feedback(
    project_id: str,
    stage_id: str,
    sender_agent_id: str | None = None,
    recipient_agent_id: str | None = None,
    status: str | None = None,
    score: float = 0.0,
    summary: str = "",
    findings: list[dict[str, Any]] | None = None,
    artifact_refs: list[ArtifactRef] | None = None,
    run_id: str | None = None,
    correlation_id: str | None = None,
    task_id: str | None = None,
    telugu_activity: str | None = None,
    progress_percent: float | None = None,
    details: dict[str, Any] | None = None,
    *,
    reviewer_agent_id: str | None = None,
    target_agent_ids: list[str] | str | None = None,
    verdict: str | None = None,
) -> AgentMessage:
    """Publishes structured review feedback from an LLM gate or reviewer."""
    src = sender_agent_id or reviewer_agent_id or ""
    tgt_raw = recipient_agent_id or target_agent_ids or ""
    if isinstance(tgt_raw, list):
        tgt_list = tgt_raw
        tgt = tgt_raw[0] if tgt_raw else ""
    else:
        tgt = str(tgt_raw)
        tgt_list = [tgt] if tgt else []
    clean_status = status or verdict or "reviewed"
    content = f"LLM Review verdict: {clean_status.upper()} (score: {score:.2f}) - {summary}"
    return publish_message(
        project_id=project_id,
        stage_id=stage_id,
        sender_agent_id=src,
        recipient_agent_ids=tgt_list,
        message_type=MessageType.REVIEW_FEEDBACK,
        content=content,
        artifact_refs=artifact_refs,
        run_id=run_id,
        correlation_id=correlation_id,
        metadata={"status": clean_status, "score": score, "findings": findings or []},
        status=clean_status,
        task_id=task_id,
        telugu_activity=telugu_activity,
        progress_percent=progress_percent,
        details=details or {},
        source_agent_id=src,
        target_agent_id=tgt,
    )


def publish_handoff(
    project_id: str,
    stage_id: str,
    sender_agent_id: str | None = None,
    recipient_agent_id: str | None = None,
    reason: str = "",
    artifact_refs: list[ArtifactRef] | None = None,
    metadata: dict[str, Any] | None = None,
    run_id: str | None = None,
    correlation_id: str | None = None,
    task_id: str | None = None,
    telugu_activity: str | None = None,
    progress_percent: float | None = None,
    details: dict[str, Any] | None = None,
    *,
    from_agent: str | None = None,
    to_agents: list[str] | str | None = None,
) -> AgentMessage:
    """Publishes a verified handoff between pipeline agents."""
    src = sender_agent_id or from_agent or ""
    tgt_raw = recipient_agent_id or to_agents or ""
    if isinstance(tgt_raw, list):
        tgt = tgt_raw[0] if tgt_raw else ""
        tgt_list = tgt_raw
    else:
        tgt = str(tgt_raw)
        tgt_list = [tgt] if tgt else []
    content = f"Handoff from {src} to {tgt}: {reason}"
    return publish_message(
        project_id=project_id,
        stage_id=stage_id,
        sender_agent_id=src,
        recipient_agent_ids=tgt_list,
        message_type=MessageType.HANDOFF,
        content=content,
        artifact_refs=artifact_refs,
        run_id=run_id,
        correlation_id=correlation_id,
        metadata=metadata or {},
        status="sent",
        task_id=task_id,
        telugu_activity=telugu_activity,
        progress_percent=progress_percent,
        details=details or {},
        source_agent_id=src,
        target_agent_id=tgt,
    )


def query_messages(
    project_id: str,
    agent_id: str | None = None,
    stage_id: str | None = None,
    message_type: str | None = None,
    status: str | None = None,
    search: str | None = None,
    task_id: str | None = None,
    limit: int = 100,
    cursor: int | None = None,
    reverse: bool = True,
) -> list[AgentMessage]:
    """Queries project-scoped communications with filtering, pagination, and sorting."""
    cfile = get_communications_file(project_id)
    if not cfile.exists():
        return []

    lock = _get_project_lock(project_id)
    messages: list[AgentMessage] = []

    with lock:
        try:
            with open(cfile, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        msg = AgentMessage.from_dict(data)
                        messages.append(msg)
                    except (json.JSONDecodeError, ValueError):
                        continue
        except OSError:
            return []

    # Apply filters
    filtered: list[AgentMessage] = []
    for m in messages:
        if cursor is not None and m.sequence <= cursor:
            continue
        if task_id and m.task_id != task_id and m.correlation_id != task_id:
            continue
        if agent_id and m.sender_agent_id != agent_id and agent_id not in m.recipient_agent_ids:
            continue
        if stage_id and m.stage_id != stage_id:
            continue
        if message_type and m.message_type != message_type:
            continue
        if status and m.status != status:
            continue
        if search:
            q = search.lower()
            if (
                q not in m.content.lower()
                and q not in m.sender_agent_id.lower()
                and q not in m.stage_id.lower()
                and (not m.telugu_activity or q not in m.telugu_activity.lower())
            ):
                continue
        filtered.append(m)

    if reverse:
        filtered.sort(key=lambda m: m.sequence, reverse=True)
    else:
        filtered.sort(key=lambda m: m.sequence, reverse=False)

    return filtered[:limit]


async def subscribe_events(
    project_id: str,
    poll_interval: float | None = None,
    catch_up: bool = True,
) -> AsyncGenerator[dict[str, Any], None]:
    """Async generator yielding live message dicts for Server-Sent Events (SSE)."""
    q: asyncio.Queue = asyncio.Queue()
    with _SUBSCRIBERS_MUTEX:
        if project_id not in _SUBSCRIBERS:
            _SUBSCRIBERS[project_id] = set()
        _SUBSCRIBERS[project_id].add(q)

    timeout_s = poll_interval if poll_interval is not None else 15.0

    try:
        # Initial connection event
        yield {"event": "connected", "data": json.dumps({"status": "connected", "project_id": project_id})}

        # Catch up pre-existing messages if requested
        if catch_up:
            try:
                recent = query_messages(project_id, limit=20)
                for m in recent:
                    yield {"event": "message", "data": json.dumps(m.to_dict())}
            except Exception:
                pass

        while True:
            # Wait for message with periodic heartbeat keep-alive
            try:
                msg = await asyncio.wait_for(q.get(), timeout=timeout_s)
                yield {"event": "message", "data": json.dumps(msg)}
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "keep-alive"}
    finally:
        with _SUBSCRIBERS_MUTEX:
            if project_id in _SUBSCRIBERS and q in _SUBSCRIBERS[project_id]:
                _SUBSCRIBERS[project_id].remove(q)
