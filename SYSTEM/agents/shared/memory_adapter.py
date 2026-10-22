"""Agent-specific Memory Adapter enforcing logical isolation through Central Memory Service."""
from __future__ import annotations

from typing import Any
from SYSTEM.memory.memory_service import memory_service
from SYSTEM.memory.memory_scoping import MemoryAccessViolation


class AgentMemoryAdapter:
    """Provides an isolated memory interface bound to a specific agent_id."""

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self._service = memory_service

    def retrieve_private(
        self,
        query: str = "",
        project_id: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Retrieves memories strictly belonging to this agent's private scope."""
        return self._service.get_scoped_memories(
            agent_id=self.agent_id,
            query=query,
            project_id=project_id,
            scope="agent",
            limit=limit,
        )

    def store_private(
        self,
        title: str,
        content: str,
        kind: str = "fact",
        project_id: str | None = None,
        evidence: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Saves knowledge into this agent's private scope."""
        return self._service.store_agent_memory(
            agent_id=self.agent_id,
            title=title,
            content=content,
            kind=kind,
            project_id=project_id,
            evidence=evidence,
        )

    def retrieve_project_shared(
        self,
        project_id: str,
        query: str = "",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Retrieves shared memories for a project."""
        return self._service.get_scoped_memories(
            agent_id=self.agent_id,
            query=query,
            project_id=project_id,
            scope="project",
            limit=limit,
        )

    def store_project_shared(
        self,
        project_id: str,
        title: str,
        content: str,
        kind: str = "fact",
        evidence: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Contributes a shared observation to a project."""
        return self._service.store_project_memory(
            agent_id=self.agent_id,
            project_id=project_id,
            title=title,
            content=content,
            kind=kind,
            evidence=evidence,
        )

    def retrieve_global_knowledge(
        self,
        query: str = "",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Retrieves global verified system knowledge."""
        return self._service.get_scoped_memories(
            agent_id=self.agent_id,
            query=query,
            scope="global",
            limit=limit,
        )

    def record_experience(
        self,
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
        """Records a granular task execution experience into this agent's private partition."""
        from SYSTEM.memory.per_agent_store import per_agent_store
        exp = per_agent_store.record_experience(
            agent_id=self.agent_id,
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

    def retrieve_experiences(
        self,
        task_type: str | None = None,
        query: str = "",
        outcome: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Retrieves past task experiences strictly from this agent's private partition."""
        from SYSTEM.memory.per_agent_store import per_agent_store
        exps = per_agent_store.retrieve_agent_experiences(
            agent_id=self.agent_id,
            task_type=task_type,
            query=query,
            outcome=outcome,
            limit=limit,
        )
        return [e.to_dict() for e in exps]

