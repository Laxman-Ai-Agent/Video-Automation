"""Authoritative Central History Service for SYSTEM agents."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from .audit_history import AuditRecord
from .decision_history import DecisionRecord
from .execution_history import ExecutionRecord

try:
    from SYSTEM.core import config
    HISTORY_DIR = config.PROJECT_ROOT / "config" / "history"
except ImportError:
    HISTORY_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "history"


class HistoryService:
    """Thread-safe persistent store for agent execution, decision, and audit trails."""

    def __init__(self, history_dir: Path | None = None) -> None:
        self.history_dir = history_dir or HISTORY_DIR
        self._lock = threading.RLock()
        self._execution_file = self.history_dir / "executions.jsonl"
        self._decision_file = self.history_dir / "decisions.jsonl"
        self._audit_file = self.history_dir / "audits.jsonl"
        self._init_files()

    def _init_files(self) -> None:
        with self._lock:
            self.history_dir.mkdir(parents=True, exist_ok=True)
            for f in (self._execution_file, self._decision_file, self._audit_file):
                if not f.exists():
                    f.touch()

    def record_execution(self, record: ExecutionRecord) -> ExecutionRecord:
        with self._lock:
            with open(self._execution_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record.to_dict()) + "\n")
        return record

    def record_decision(self, record: DecisionRecord) -> DecisionRecord:
        with self._lock:
            with open(self._decision_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record.to_dict()) + "\n")
        return record

    def record_audit(self, record: AuditRecord) -> AuditRecord:
        with self._lock:
            with open(self._audit_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record.to_dict()) + "\n")
        return record

    def query_executions(
        self,
        agent_id: str | None = None,
        project_id: str | None = None,
        task_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        results = []
        with self._lock:
            if not self._execution_file.exists():
                return []
            with open(self._execution_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        row = json.loads(line)
                        if agent_id and row.get("agent_id") != agent_id:
                            continue
                        if project_id and row.get("project_id") != project_id:
                            continue
                        if task_id and row.get("task_id") != task_id:
                            continue
                        results.append(row)
                    except Exception:
                        continue
        return results[-limit:]

    def query_decisions(
        self,
        agent_id: str | None = None,
        project_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        results = []
        with self._lock:
            if not self._decision_file.exists():
                return []
            with open(self._decision_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        row = json.loads(line)
                        if agent_id and row.get("agent_id") != agent_id:
                            continue
                        if project_id and row.get("project_id") != project_id:
                            continue
                        results.append(row)
                    except Exception:
                        continue
        return results[-limit:]

    def query_audits(
        self,
        agent_id: str | None = None,
        event_type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        results = []
        with self._lock:
            if not self._audit_file.exists():
                return []
            with open(self._audit_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        row = json.loads(line)
                        if agent_id and row.get("agent_id") != agent_id:
                            continue
                        if event_type and row.get("event_type") != event_type:
                            continue
                        results.append(row)
                    except Exception:
                        continue
        return results[-limit:]


history_service = HistoryService()
