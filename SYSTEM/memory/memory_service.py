"""Unified Central Memory Service Facade for SYSTEM agents."""
from __future__ import annotations

from typing import Any
from .shared_memory import MemoryItem, service as _raw_service
from .memory_scoping import ScopedMemoryManager, MemoryAccessViolation


class MemoryService:
    """Central Memory Service with agent-level isolation and project scoping."""

    def __init__(self) -> None:
        self.raw_service = _raw_service
        self.scoping = ScopedMemoryManager()

    def initialize(self) -> None:
        self.raw_service.initialize()

    def get_scoped_memories(
        self,
        agent_id: str,
        query: str = "",
        project_id: str | None = None,
        scope: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Retrieves verified memories authorized for agent_id."""
        self.initialize()
        items = self.scoping.read_scoped(
            requesting_agent_id=agent_id,
            query=query,
            project_id=project_id,
            scope=scope,  # type: ignore[arg-type]
            limit=limit,
        )
        return [i.to_dict() for i in items]

    def store_agent_memory(
        self,
        agent_id: str,
        title: str,
        content: str,
        kind: str = "fact",
        project_id: str | None = None,
        evidence: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Stores a private memory strictly accessible to agent_id."""
        self.initialize()
        item = self.scoping.write_agent_private(
            owner_agent_id=agent_id,
            title=title,
            content=content,
            kind=kind,
            project_id=project_id,
            evidence=evidence,
        )
        return item.to_dict()

    def store_project_memory(
        self,
        agent_id: str,
        project_id: str,
        title: str,
        content: str,
        kind: str = "fact",
        evidence: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Stores a shared project-scoped memory."""
        self.initialize()
        item = self.scoping.write_project_shared(
            owner_agent_id=agent_id,
            project_id=project_id,
            title=title,
            content=content,
            kind=kind,
            evidence=evidence,
        )
        return item.to_dict()

    def record_agent_experience(
        self,
        agent_id: str,
        task_type: str,
        outcome: str,
        context: dict[str, Any] | None = None,
        metrics: dict[str, Any] | None = None,
        error_category: str | None = None,
        task_id: str | None = None,
        project_id: str | None = None,
        evidence: list[dict[str, Any]] | None = None,
        reflection: str | dict[str, Any] | None = None,
        proposed_lesson: dict[str, Any] | None = None,
        confidence: float = 0.5,
    ) -> dict[str, Any]:
        """Records a task experience into the agent's private partition."""
        from SYSTEM.memory.per_agent_store import per_agent_store
        exp = per_agent_store.record_experience(
            agent_id=agent_id,
            task_type=task_type,
            outcome=outcome,
            context=context,
            metrics=metrics,
            error_category=error_category,
            task_id=task_id,
            project_id=project_id,
            evidence=evidence,
            reflection=reflection,
            proposed_lesson=proposed_lesson,
            confidence=confidence,
        )
        return exp.to_dict()

    def get_agent_experiences(
        self,
        agent_id: str,
        task_type: str | None = None,
        query: str = "",
        outcome: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Retrieves task experiences strictly from the agent's private partition."""
        from SYSTEM.memory.per_agent_store import per_agent_store
        exps = per_agent_store.retrieve_agent_experiences(
            agent_id=agent_id,
            task_type=task_type,
            query=query,
            outcome=outcome,
            limit=limit,
        )
        return [e.to_dict() for e in exps]


memory_service = MemoryService()
