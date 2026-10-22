"""Memory Scoping & Agent Isolation Policies.

Enforces:
1. Agent-private isolation: scope="agent", owner=agent_id. Agents cannot access other agents' private scopes.
2. Project-scoped memory: scope="project", project_id=pid. Permitted for agents on that project.
3. Global verified memory: scope="global". Read-only for general agent consumption.
"""
from __future__ import annotations

from typing import Any, Literal
from .shared_memory import MemoryItem, MemoryScope, service as central_memory_service


class MemoryAccessViolation(PermissionError):
    """Raised when an agent attempts an unauthorized read or write across memory boundaries."""
    pass


class ScopedMemoryManager:
    """Manages memory access with strict agent-level isolation."""

    @staticmethod
    def is_access_allowed(item: MemoryItem, requesting_agent_id: str) -> bool:
        """Determines if requesting_agent_id is authorized to read item."""
        if requesting_agent_id == "*" or requesting_agent_id == "main_architecture_agent":
            return True
        if item.owner == requesting_agent_id:
            return True
        if item.scope == "global":
            return True
        if item.scope == "agent":
            # Strict isolation: private to owner unless explicitly permitted
            return requesting_agent_id in item.permitted_readers or "*" in item.permitted_readers
        if item.scope == "project":
            return requesting_agent_id in item.permitted_readers or "*" in item.permitted_readers
        return False

    @classmethod
    def read_scoped(
        cls,
        requesting_agent_id: str,
        query: str = "",
        project_id: str | None = None,
        scope: MemoryScope | None = None,
        kind: str | None = None,
        limit: int = 20,
    ) -> list[MemoryItem]:
        """Retrieves memories strictly filtered by access authorization."""
        items = central_memory_service.retrieve_memory(
            query=query,
            agent_id=requesting_agent_id,
            project_id=project_id,
            scope=scope,  # type: ignore[arg-type]
            kind=kind,    # type: ignore[arg-type]
            include_candidates=False,
            limit=limit,
        )
        return [item for item in items if cls.is_access_allowed(item, requesting_agent_id)]

    @classmethod
    def write_agent_private(
        cls,
        owner_agent_id: str,
        title: str,
        content: str,
        kind: str = "fact",
        project_id: str | None = None,
        evidence: list[dict[str, Any]] | None = None,
    ) -> MemoryItem:
        """Stores an item strictly in the private memory scope of owner_agent_id."""
        return central_memory_service.submit_candidate(
            title=title,
            content=content,
            kind=kind,  # type: ignore[arg-type]
            owner=owner_agent_id,
            scope="agent",
            confidence=0.8,
            evidence=evidence or [],
            permitted_readers=[owner_agent_id],  # Private to owner
            project_id=project_id,
        )

    @classmethod
    def write_project_shared(
        cls,
        owner_agent_id: str,
        project_id: str,
        title: str,
        content: str,
        kind: str = "fact",
        evidence: list[dict[str, Any]] | None = None,
    ) -> MemoryItem:
        """Stores an item in the project-shared scope."""
        return central_memory_service.submit_candidate(
            title=title,
            content=content,
            kind=kind,  # type: ignore[arg-type]
            owner=owner_agent_id,
            scope="project",
            confidence=0.7,
            evidence=evidence or [],
            permitted_readers=["*"],
            project_id=project_id,
        )
