"""Experience Collector for Main Architecture Agent.

Captures, redacts, deduplicates, and durably records end-to-end task outcomes,
delegated subagent executions, failures, recovery actions, and user feedback.
"""
from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from SYSTEM.core.resilience import sanitize_secrets

EXPERIENCES_FILE = Path(__file__).resolve().parent.parent / "history" / "experiences.jsonl"
_COLLECTOR_LOCK = threading.Lock()




@dataclass
class ExperienceRecord:
    experience_id: str = field(default_factory=lambda: f"exp_{uuid.uuid4().hex[:12]}")
    task_id: str = ""
    correlation_id: str = ""
    project_id: str = ""
    session_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    goal: str = ""
    constraints: dict[str, Any] = field(default_factory=dict)
    strategy_version: str = "1.0.0"
    plan: list[dict[str, Any]] = field(default_factory=list)
    selected_agents: list[str] = field(default_factory=list)
    selected_skills: list[str] = field(default_factory=list)
    selected_tools: list[str] = field(default_factory=list)
    status: Literal["succeeded", "failed", "blocked"] = "succeeded"
    acceptance_result: dict[str, Any] = field(default_factory=dict)
    retries: int = 0
    recovery_actions: list[str] = field(default_factory=list)
    error_category: str | None = None
    error_detail: str | None = None
    duration_ms: float = 0.0
    llm_cost_estimate: float = 0.0
    user_feedback: dict[str, Any] | None = None
    evidence_refs: list[str] = field(default_factory=list)
    reflected: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperienceRecord:
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


class ExperienceCollector:
    """Thread-safe collector and query interface for Master Agent experiences."""

    def __init__(self, storage_path: Path | None = None) -> None:
        self.storage_path = storage_path or EXPERIENCES_FILE
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = _COLLECTOR_LOCK
        self._known_task_ids: set[str] = set()
        self._load_index()

    def _load_index(self) -> None:
        with self._lock:
            if not self.storage_path.exists():
                return
            with open(self.storage_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        tid = record.get("task_id")
                        if tid:
                            self._known_task_ids.add(tid)
                    except Exception:
                        continue

    def record_experience(self, exp: ExperienceRecord) -> ExperienceRecord:
        """Sanitizes, deduplicates, and appends an experience record."""
        # Sanitize sensitive content
        exp.goal = sanitize_secrets(exp.goal)
        if exp.error_detail:
            exp.error_detail = sanitize_secrets(exp.error_detail)

        with self._lock:
            # Deduplicate by task_id if provided
            if exp.task_id and exp.task_id in self._known_task_ids:
                return exp

            if exp.task_id:
                self._known_task_ids.add(exp.task_id)

            line = json.dumps(exp.to_dict()) + "\n"
            with open(self.storage_path, "a", encoding="utf-8") as f:
                f.write(line)

            # Store in agent-private scoped memory
            try:
                from SYSTEM.memory.memory_scoping import ScopedMemoryManager
                ScopedMemoryManager.write_agent_private(
                    owner_agent_id="main_architecture_agent",
                    title=f"Experience {exp.experience_id}: {exp.goal[:60]}",
                    content=f"Goal: {exp.goal} | Status: {exp.status} | Agents: {','.join(exp.selected_agents)}",
                    kind="pattern",
                    project_id=exp.project_id or None,
                    evidence=[{"ref_type": "experience", "ref_id": exp.experience_id, "status": exp.status}],
                )
            except Exception:
                pass

            return exp

    record_task_experience = record_experience

    def query_experiences(
        self,
        goal_pattern: str | None = None,
        status: str | None = None,
        agent_id: str | None = None,
        limit: int = 50,
    ) -> list[ExperienceRecord]:
        """Queries recorded experiences filtered by criteria."""
        results: list[ExperienceRecord] = []
        with self._lock:
            if not self.storage_path.exists():
                return []

            with open(self.storage_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if status and data.get("status") != status:
                            continue
                        if agent_id and agent_id not in data.get("selected_agents", []):
                            continue
                        if goal_pattern and goal_pattern.lower() not in data.get("goal", "").lower():
                            continue
                        results.append(ExperienceRecord.from_dict(data))
                    except Exception:
                        continue

        return results[-limit:]

    get_experiences = query_experiences

    def get_unreflected_experiences(self, limit: int = 50) -> list[ExperienceRecord]:
        """Returns experiences that have not yet been processed by the Reflection Engine."""
        unreflected: list[ExperienceRecord] = []
        with self._lock:
            if not self.storage_path.exists():
                return []

            with open(self.storage_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if not data.get("reflected", False):
                            unreflected.append(ExperienceRecord.from_dict(data))
                    except Exception:
                        continue
        return unreflected[:limit]

    def mark_reflected(self, experience_ids: set[str] | list[str]) -> None:
        """Marks specified experience records as reflected."""
        exp_id_set = set(experience_ids)
        if not exp_id_set:
            return

        with self._lock:
            if not self.storage_path.exists():
                return

            updated_lines = []
            with open(self.storage_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if data.get("experience_id") in exp_id_set:
                            data["reflected"] = True
                        updated_lines.append(json.dumps(data) + "\n")
                    except Exception:
                        updated_lines.append(line + "\n")

            with open(self.storage_path, "w", encoding="utf-8") as f:
                f.writelines(updated_lines)

    def record_user_feedback(self, task_id: str, feedback: dict[str, Any]) -> bool:
        """Appends or updates user feedback on an existing experience record."""
        with self._lock:
            if not self.storage_path.exists():
                return False
            updated = False
            new_lines = []
            with open(self.storage_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if data.get("task_id") == task_id:
                            data["user_feedback"] = feedback
                            updated = True
                        new_lines.append(json.dumps(data) + "\n")
                    except Exception:
                        new_lines.append(line + "\n")
            if updated:
                with open(self.storage_path, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
            return updated


experience_collector = ExperienceCollector()
