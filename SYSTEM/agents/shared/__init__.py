"""Shared Agent infrastructure, base classes, contracts, and lifecycle adapters."""
from .base_agent import BaseAgent
from .contracts import (
    AgentCategory,
    AgentMessage,
    AgentMetadata,
    AgentRequest,
    AgentResult,
    AgentStatus,
    ArtifactRef,
    MessageType,
)
from .communication import (
    publish_lifecycle_event,
    publish_message,
    query_messages,
    subscribe_events,
)
stream_messages = subscribe_events
from .memory_adapter import AgentMemoryAdapter
from .lifecycle import AgentLifecycleManager
from .telugu_activity_mapper import (
    TeluguActivityMapper,
    telugu_activity_mapper,
    map_activity,
    map_handoff,
    map_review_feedback,
    calculate_progress,
    AGENT_TELUGU_NAMES,
    STAGE_WEIGHTS,
    MILESTONE_MESSAGES,
)

__all__ = [
    "BaseAgent",
    "AgentCategory",
    "AgentMetadata",
    "AgentRequest",
    "AgentResult",
    "AgentStatus",
    "ArtifactRef",
    "MessageType",
    "AgentMessage",
    "publish_lifecycle_event",
    "publish_message",
    "query_messages",
    "subscribe_events",
    "stream_messages",
    "AgentMemoryAdapter",
    "AgentLifecycleManager",
    "TeluguActivityMapper",
    "telugu_activity_mapper",
    "map_activity",
    "map_handoff",
    "map_review_feedback",
    "calculate_progress",
    "AGENT_TELUGU_NAMES",
    "STAGE_WEIGHTS",
    "MILESTONE_MESSAGES",
]

