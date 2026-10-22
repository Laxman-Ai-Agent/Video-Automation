"""Learning Case Collector for Capability Finder Agent.

Captures, redacts, correlates, and durably records capability-discovery decisions,
downstream task execution outcomes, and reviewer feedback.
"""
from __future__ import annotations

import json
import logging
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from SYSTEM.core.resilience import sanitize_secrets

logger = logging.getLogger("capability_finder.learning.case_collector")

HISTORY_DIR = Path(__file__).resolve().parent.parent / "history"
CASES_FILE = HISTORY_DIR / "learning_cases.jsonl"
_CASE_LOCK = threading.RLock()




def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class LearningCase:
    """Immutable record capturing an individual capability discovery decision and its outcome."""
    case_id: str = field(default_factory=lambda: f"lcase_{uuid.uuid4().hex[:12]}")
    schema_version: int = 1
    task_id: str = ""
    correlation_id: str = ""
    agent_id: str = "capability_finder"
    project_id: str = ""
    timestamp: str = field(default_factory=_utc_now)
    query: str = ""
    parsed_requirement: dict[str, Any] = field(default_factory=dict)
    candidates_considered: list[dict[str, Any]] = field(default_factory=list)
    decision_recommendation: Literal["REUSE", "ADAPT", "CREATE_SKILL", "CREATE_AGENT"] = "REUSE"
    suggested_delegate_id: str | None = None
    constraints: dict[str, Any] = field(default_factory=dict)
    evidence_refs: list[dict[str, Any]] = field(default_factory=list)
    actual_outcome: Literal["succeeded", "failed", "inconclusive", "pending"] = "pending"
    outcome_detail: str | None = None
    verification_status: Literal["passed", "failed", "unverified", "inconclusive"] = "unverified"
    reviewer_feedback: list[dict[str, Any]] = field(default_factory=list)
    applied_knowledge_version: str = "1.0.0"
    failure_category: str | None = None
    is_redacted: bool = True
    discovery_result: dict[str, Any] = field(default_factory=dict)
    execution_outcome: dict[str, Any] = field(default_factory=dict)
    outcome_attribution: dict[str, Any] = field(default_factory=dict)
    environment_state: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LearningCase:
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


class CaseCollector:
    """Thread-safe persistent collector for capability discovery learning cases."""

    def __init__(self, persistence_file: Path | None = None, storage_file: Path | None = None) -> None:
        self._persistence_file = storage_file or persistence_file or CASES_FILE
        self._cases: dict[str, LearningCase] = {}
        self._task_index: dict[str, str] = {}
        self._init_storage()

    def record_case(self, case: LearningCase) -> str:
        """Records an existing LearningCase object with secret sanitization."""
        with _CASE_LOCK:
            # Sanitize textual inputs
            if getattr(case, "query", None):
                case.query = sanitize_secrets(case.query)
            if isinstance(getattr(case, "parsed_requirement", None), dict):
                for k, v in case.parsed_requirement.items():
                    if isinstance(v, str):
                        case.parsed_requirement[k] = sanitize_secrets(v)
            if isinstance(getattr(case, "discovery_result", None), dict):
                for k, v in case.discovery_result.items():
                    if isinstance(v, str):
                        case.discovery_result[k] = sanitize_secrets(v)
            if isinstance(getattr(case, "execution_outcome", None), dict):
                for k, v in case.execution_outcome.items():
                    if isinstance(v, str):
                        case.execution_outcome[k] = sanitize_secrets(v)
            if isinstance(getattr(case, "environment_state", None), dict):
                for k, v in case.environment_state.items():
                    if isinstance(v, str):
                        case.environment_state[k] = sanitize_secrets(v)

            self._cases[case.case_id] = case
            if case.task_id:
                self._task_index[case.task_id] = case.case_id
            if case.correlation_id:
                self._task_index[case.correlation_id] = case.case_id

            self._append_to_disk(case)
            return case.case_id

    def _init_storage(self) -> None:
        with _CASE_LOCK:
            self._persistence_file.parent.mkdir(parents=True, exist_ok=True)
            if self._persistence_file.exists():
                try:
                    with open(self._persistence_file, "r", encoding="utf-8") as f:
                        for line in f:
                            line_str = line.strip()
                            if not line_str:
                                continue
                            try:
                                data = json.loads(line_str)
                                case = LearningCase.from_dict(data)
                                self._cases[case.case_id] = case
                                if case.task_id:
                                    self._task_index[case.task_id] = case.case_id
                                if case.correlation_id:
                                    self._task_index[case.correlation_id] = case.case_id
                            except Exception:
                                continue
                except Exception as e:
                    logger.warning(f"Could not load existing learning cases from {self._persistence_file}: {e}")

    def record_discovery_case(
        self,
        query: str,
        parsed_requirement: dict[str, Any],
        candidates_considered: list[dict[str, Any]],
        decision_recommendation: Literal["REUSE", "ADAPT", "CREATE_SKILL", "CREATE_AGENT"],
        suggested_delegate_id: str | None,
        constraints: dict[str, Any],
        evidence_refs: list[dict[str, Any]],
        task_id: str = "",
        correlation_id: str = "",
        project_id: str = "",
        applied_knowledge_version: str = "1.0.0",
    ) -> LearningCase:
        """Records a new decision-time learning case."""
        with _CASE_LOCK:
            case = LearningCase(
                task_id=task_id,
                correlation_id=correlation_id,
                project_id=project_id,
                query=sanitize_secrets(query),
                parsed_requirement=parsed_requirement,
                candidates_considered=candidates_considered[:10],
                decision_recommendation=decision_recommendation,
                suggested_delegate_id=suggested_delegate_id,
                constraints=constraints,
                evidence_refs=evidence_refs,
                applied_knowledge_version=applied_knowledge_version,
            )
            self._cases[case.case_id] = case
            if task_id:
                self._task_index[task_id] = case.case_id
            if correlation_id:
                self._task_index[correlation_id] = case.case_id

            self._append_to_disk(case)
            return case

    def attach_outcome(
        self,
        case_id_or_task_id: str,
        outcome: Literal["succeeded", "failed", "inconclusive", "pending"],
        outcome_detail: str | None = None,
        verification_status: Literal["passed", "failed", "unverified", "inconclusive"] = "unverified",
        failure_category: str | None = None,
    ) -> LearningCase | None:
        """Associates downstream task execution or test verification outcome with an existing case."""
        with _CASE_LOCK:
            case_id = self._task_index.get(case_id_or_task_id, case_id_or_task_id)
            case = self._cases.get(case_id)
            if not case:
                return None

            case.actual_outcome = outcome
            case.outcome_detail = sanitize_secrets(outcome_detail or "")
            case.verification_status = verification_status
            case.failure_category = failure_category

            self._rewrite_disk()
            return case

    def attach_feedback(
        self,
        case_id_or_task_id: str,
        feedback: dict[str, Any],
    ) -> LearningCase | None:
        """Attaches explicit reviewer feedback to a case."""
        with _CASE_LOCK:
            case_id = self._task_index.get(case_id_or_task_id, case_id_or_task_id)
            case = self._cases.get(case_id)
            if not case:
                return None

            case.reviewer_feedback.append(feedback)
            self._rewrite_disk()
            return case

    def get_case(self, case_id: str) -> LearningCase | None:
        """Retrieves a learning case by case_id."""
        with _CASE_LOCK:
            return self._cases.get(case_id)

    def list_cases(
        self,
        filter_outcome: str | None = None,
        limit: int = 100,
    ) -> list[LearningCase]:
        """Lists recorded learning cases with optional outcome filtering."""
        with _CASE_LOCK:
            cases = list(self._cases.values())
            if filter_outcome:
                cases = [c for c in cases if c.actual_outcome == filter_outcome]
            return cases[-limit:]

    def _append_to_disk(self, case: LearningCase) -> None:
        try:
            with open(self._persistence_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(case.to_dict()) + "\n")
        except Exception as e:
            logger.error(f"Failed to append case to {self._persistence_file}: {e}")

    def _rewrite_disk(self) -> None:
        try:
            with open(self._persistence_file, "w", encoding="utf-8") as f:
                for c in self._cases.values():
                    f.write(json.dumps(c.to_dict()) + "\n")
        except Exception as e:
            logger.error(f"Failed to rewrite cases to {self._persistence_file}: {e}")

    def clear(self) -> None:
        """Clears memory and disk storage (primarily for test isolation)."""
        with _CASE_LOCK:
            self._cases.clear()
            self._task_index.clear()
            if self._persistence_file.exists():
                try:
                    self._persistence_file.unlink()
                except Exception:
                    pass


case_collector = CaseCollector()
