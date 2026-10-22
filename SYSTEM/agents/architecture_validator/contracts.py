"""Contracts and finding schemas for Architecture Validator Agent.

Defines:
- FindingSeverity (BLOCKING_ERROR, WARNING, INFO)
- FindingCategory (AGENT_REGISTRY, CAPABILITY_REGISTRY, DEPENDENCY_GRAPH, VIDEO_PIPELINE, CONTRACT, SECURITY_BOUNDARY)
- ArchitectureFinding
- AuditResult
- ValidationMode
"""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal


class FindingSeverity(str, Enum):
    BLOCKING_ERROR = "blocking_error"
    WARNING = "warning"
    INFO = "info"


class FindingCategory(str, Enum):
    AGENT_REGISTRY = "agent_registry"
    CAPABILITY_REGISTRY = "capability_registry"
    DEPENDENCY_GRAPH = "dependency_graph"
    VIDEO_PIPELINE = "video_pipeline"
    CONTRACT = "contract"
    SECURITY_BOUNDARY = "security_boundary"


ValidationMode = Literal[
    "full_architecture_audit",
    "agent_registry_audit",
    "capability_registry_audit",
    "dependency_graph_audit",
    "video_pipeline_audit",
    "contract_audit",
    "security_boundary_audit",
    "targeted_audit",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ArchitectureFinding:
    """Represents a discrete finding produced during architecture validation."""
    finding_id: str = field(default_factory=lambda: f"find_{uuid.uuid4().hex[:8]}")
    category: FindingCategory = FindingCategory.AGENT_REGISTRY
    severity: FindingSeverity = FindingSeverity.WARNING
    component: str = ""
    message: str = ""
    evidence: str = ""
    remediation: str = ""
    expected: str | None = None
    actual: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "category": self.category.value if isinstance(self.category, FindingCategory) else str(self.category),
            "severity": self.severity.value if isinstance(self.severity, FindingSeverity) else str(self.severity),
            "component": self.component,
            "message": self.message,
            "evidence": self.evidence,
            "remediation": self.remediation,
            "expected": self.expected,
            "actual": self.actual,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArchitectureFinding:
        cat = data.get("category", FindingCategory.AGENT_REGISTRY.value)
        sev = data.get("severity", FindingSeverity.WARNING.value)
        return cls(
            finding_id=data.get("finding_id", f"find_{uuid.uuid4().hex[:8]}"),
            category=FindingCategory(cat) if cat in [c.value for c in FindingCategory] else FindingCategory.AGENT_REGISTRY,
            severity=FindingSeverity(sev) if sev in [s.value for s in FindingSeverity] else FindingSeverity.WARNING,
            component=data.get("component", ""),
            message=data.get("message", ""),
            evidence=data.get("evidence", ""),
            remediation=data.get("remediation", ""),
            expected=data.get("expected"),
            actual=data.get("actual"),
        )


@dataclass
class AuditResult:
    """Overall outcome of an architecture validation audit run."""
    audit_id: str = field(default_factory=lambda: f"arch_audit_{uuid.uuid4().hex[:8]}")
    action: str = "full_architecture_audit"
    status: Literal["passed", "failed", "warning", "blocked", "incomplete"] = "passed"
    summary: str = ""
    findings: list[ArchitectureFinding] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=_utc_now)
    duration_ms: float = 0.0

    @property
    def blocking_error_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == FindingSeverity.BLOCKING_ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == FindingSeverity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == FindingSeverity.INFO)

    def finalize_status(self) -> None:
        """Derives final status from findings: blocking errors force failed status."""
        if self.blocking_error_count > 0:
            self.status = "failed"
        elif self.warning_count > 0:
            self.status = "warning"
        elif self.status not in ("blocked", "incomplete"):
            self.status = "passed"

        self.metrics.update({
            "total_findings": len(self.findings),
            "blocking_errors": self.blocking_error_count,
            "warnings": self.warning_count,
            "info": self.info_count,
        })

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "action": self.action,
            "status": self.status,
            "summary": self.summary,
            "findings": [f.to_dict() for f in self.findings],
            "metrics": self.metrics,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
        }
