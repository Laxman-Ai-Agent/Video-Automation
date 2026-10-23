"""Data contracts and schemas for the 14 logical agents, runtime lifecycle, and inter-agent communication."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Literal


class AgentStatus(str, Enum):
    IMPLEMENTED = "implemented"
    ADAPTER_ONLY = "adapter_only"
    PLANNED = "planned"
    BLOCKED = "blocked"
    DEPRECATED = "deprecated"


class AgentCategory(str, Enum):
    ORCHESTRATOR = "orchestrator"
    VIDEO_ENGINE_AGENT = "video_engine_agent"
    SYSTEM_SUBAGENT = "system_subagent"


class MessageType(str, Enum):
    AGENT_MESSAGE = "agent_message"
    HANDOFF = "handoff"
    DECISION = "decision"
    REVIEW_FEEDBACK = "review_feedback"
    TOOL_RESULT = "tool_result"
    LIFECYCLE_EVENT = "lifecycle_event"
    BLOCKED = "blocked"
    FAILED = "failed"
    COMPLETED = "completed"


@dataclass
class ArtifactRef:
    path: str
    sha256: str | None = None
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class AgentMessage:
    schema_version: int = 1
    message_id: str = ""
    sequence: int = 0
    timestamp: str = ""
    project_id: str = ""
    run_id: str | None = None
    correlation_id: str | None = None
    stage_id: str = ""
    sender_agent_id: str = ""
    recipient_agent_ids: list[str] = field(default_factory=list)
    message_type: str = MessageType.AGENT_MESSAGE.value
    content: str = ""
    artifact_refs: list[ArtifactRef] = field(default_factory=list)
    status: str = "sent"
    parent_message_id: str | None = None
    redactions_applied: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    # Stage 4 backward-compatible fields
    task_id: str | None = None
    telugu_activity: str | None = None
    progress_percent: float | None = None
    details: dict[str, Any] = field(default_factory=dict)
    source_agent_id: str | None = None
    target_agent_id: str | None = None

    @property
    def agent_id(self) -> str:
        return self.sender_agent_id or self.source_agent_id or ""

    @agent_id.setter
    def agent_id(self, val: str) -> None:
        self.sender_agent_id = val
        self.source_agent_id = val

    @property
    def technical_message(self) -> str:
        return self.content

    @technical_message.setter
    def technical_message(self, val: str) -> None:
        self.content = val

    @property
    def event_id(self) -> str:
        return self.message_id

    @event_id.setter
    def event_id(self, val: str) -> None:
        self.message_id = val

    @property
    def event_type(self) -> str:
        return self.message_type

    @event_type.setter
    def event_type(self, val: str) -> None:
        self.message_type = val

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["artifact_refs"] = [a.to_dict() if isinstance(a, ArtifactRef) else a for a in self.artifact_refs]
        d["agent_id"] = self.agent_id
        d["technical_message"] = self.technical_message
        d["event_id"] = self.event_id
        d["event_type"] = self.event_type
        if not d.get("source_agent_id"):
            d["source_agent_id"] = self.sender_agent_id
        if not d.get("target_agent_id") and self.recipient_agent_ids:
            d["target_agent_id"] = self.recipient_agent_ids[0]
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentMessage:
        raw_refs = data.get("artifact_refs", [])
        artifact_refs = [
            ArtifactRef(**r) if isinstance(r, dict) else r
            for r in raw_refs
        ]
        content = data.get("content") if data.get("content") is not None else (data.get("technical_message") or "")
        sender = data.get("sender_agent_id") or data.get("source_agent_id") or data.get("agent_id") or ""
        msg_id = data.get("message_id") or data.get("event_id") or ""
        msg_type = data.get("message_type") or data.get("event_type") or MessageType.AGENT_MESSAGE.value
        recipients = data.get("recipient_agent_ids", [])
        if not recipients and data.get("target_agent_id"):
            recipients = [data["target_agent_id"]]

        return cls(
            schema_version=data.get("schema_version", 1),
            message_id=msg_id,
            sequence=data.get("sequence", 0),
            timestamp=data.get("timestamp", ""),
            project_id=data.get("project_id", ""),
            run_id=data.get("run_id"),
            correlation_id=data.get("correlation_id") or data.get("event_id"),
            stage_id=data.get("stage_id", ""),
            sender_agent_id=sender,
            recipient_agent_ids=recipients,
            message_type=msg_type,
            content=content,
            artifact_refs=artifact_refs,
            status=data.get("status", "sent"),
            parent_message_id=data.get("parent_message_id"),
            redactions_applied=data.get("redactions_applied", []),
            metadata=data.get("metadata", {}),
            task_id=data.get("task_id"),
            telugu_activity=data.get("telugu_activity"),
            progress_percent=data.get("progress_percent"),
            details=data.get("details", {}),
            source_agent_id=data.get("source_agent_id") or sender,
            target_agent_id=data.get("target_agent_id") or (recipients[0] if recipients else None),
        )


@dataclass
class AgentMetadata:
    agent_id: str
    name: str
    version: str = "1.0.0"
    category: AgentCategory = AgentCategory.VIDEO_ENGINE_AGENT
    status: AgentStatus = AgentStatus.IMPLEMENTED
    purpose: str = ""
    capabilities: list[str] = field(default_factory=list)
    inputs_schema: str | None = None
    outputs_schema: str | None = None
    stage_id: str | None = None
    allowed_tools: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    owner: str = "agent-system"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value if isinstance(self.status, AgentStatus) else str(self.status)
        d["category"] = self.category.value if isinstance(self.category, AgentCategory) else str(self.category)
        return d


@dataclass
class AgentRequest:
    project_id: str = ""
    agent_id: str = ""
    stage_id: str = ""
    task_id: str | None = None
    run_id: str | None = None
    correlation_id: str | None = None
    parent_message_id: str | None = None
    input_refs: list[ArtifactRef] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    agent_id: str
    stage_id: str = ""
    project_id: str = ""
    status: Literal["succeeded", "blocked", "needs_review", "failed"] = "succeeded"
    output_refs: list[ArtifactRef] = field(default_factory=list)
    summary: str = ""
    error: str | None = None
    review_feedback: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.status == "succeeded"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["output_refs"] = [a.to_dict() if isinstance(a, ArtifactRef) else a for a in self.output_refs]
        d["success"] = self.success
        return d
