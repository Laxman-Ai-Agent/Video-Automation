"""Agent Experience Contract & Schema Validation for Per-Agent Memory.

Represents a granular task execution experience recorded by an individual agent:
- Scoped strictly to the owning agent's canonical identity.
- Contains truthful context, verified outcome, error category, and measurable metrics.
- Carries evidence references and optional outcome reflections / candidate lessons.
- Auto-sanitizes credentials and sensitive secrets.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from SYSTEM.core.resilience import redact_secrets

OutcomeStatus = Literal["succeeded", "failed", "blocked", "needs_review"]
EvaluationStatus = Literal["unreviewed", "evaluated", "approved", "rejected"]

ERROR_CATEGORIES: set[str] = {
    "validation_error",
    "runtime_error",
    "timeout",
    "syntax_error",
    "security_block",
    "dependency_missing",
    "codec_error",
    "alignment_error",
    "boundary_error",
    "unknown_error",
}


@dataclass
class AgentExperience:
    """Strongly-typed record of an agent's task experience within its private memory partition."""
    experience_id: str
    agent_id: str
    task_type: str
    task_id: str
    project_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    outcome: OutcomeStatus = "succeeded"
    error_category: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    reflection: dict[str, Any] | str | None = None
    proposed_lesson: dict[str, Any] | None = None
    evidence: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.5
    evaluation_status: EvaluationStatus = "unreviewed"
    timestamp: str = ""
    schema_version: int = 1

    def __post_init__(self) -> None:
        if not self.experience_id:
            self.experience_id = f"exp-{self.agent_id}-{uuid.uuid4().hex[:10]}"
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if self.confidence < 0.0:
            self.confidence = 0.0
        elif self.confidence > 1.0:
            self.confidence = 1.0

        # Auto-sanitize context and reflection for credentials/secrets
        self._sanitize()

    def _sanitize(self) -> None:
        """Sanitizes sensitive information from context and reflection strings."""
        if isinstance(self.context, dict):
            clean_ctx = {}
            for k, v in self.context.items():
                if isinstance(v, str):
                    clean_v, _ = redact_secrets(v)
                    clean_ctx[k] = clean_v
                else:
                    clean_ctx[k] = v
            self.context = clean_ctx

        if isinstance(self.reflection, str):
            clean_ref, _ = redact_secrets(self.reflection)
            self.reflection = clean_ref
        elif isinstance(self.reflection, dict):
            clean_ref = {}
            for k, v in self.reflection.items():
                if isinstance(v, str):
                    clean_v, _ = redact_secrets(v)
                    clean_ref[k] = clean_v
                else:
                    clean_ref[k] = v
            self.reflection = clean_ref

    def to_dict(self) -> dict[str, Any]:
        """Serializes experience to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentExperience:
        """Constructs an AgentExperience from a dictionary with schema filtering."""
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


def validate_experience(data: dict[str, Any]) -> list[str]:
    """Validates structural schema and required fields of an experience record."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Experience record must be a dictionary."]

    required_fields = ["agent_id", "task_type", "task_id", "outcome"]
    for f in required_fields:
        if not data.get(f):
            errors.append(f"Missing required field: '{f}'")

    aid = data.get("agent_id", "")
    if aid and not re.match(r"^[a-z0-9_.-]+$", aid):
        errors.append(f"Invalid path-safe agent_id: {aid!r}")

    outcome = data.get("outcome")
    if outcome and outcome not in ("succeeded", "failed", "blocked", "needs_review"):
        errors.append(f"Invalid outcome status: {outcome!r}")

    metrics = data.get("metrics")
    if metrics is not None and not isinstance(metrics, dict):
        errors.append("'metrics' must be a dictionary when provided.")

    return errors
