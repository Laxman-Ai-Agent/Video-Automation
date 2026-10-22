"""Candidate Lesson Generator for Capability Finder.

Identifies recurring failure patterns and verified reviewer feedback to generate
declarative, versioned LessonProposal candidates without modifying production code.
Enforces minimum evidence thresholds to avoid overfitting on isolated anomalies.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from .case_collector import CaseCollector, LearningCase, case_collector


@dataclass
class LessonProposal:
    """Structured proposal representing a learned candidate decision rule."""
    proposal_id: str = field(default_factory=lambda: f"prop_{uuid.uuid4().hex[:12]}")
    schema_version: int = 1
    version: str = "1.1.0"
    title: str = ""
    description: str = ""
    observed_pattern: str = ""
    affected_domain: str = "general"
    rule_type: Literal["routing_preference", "constraint_override", "synonym_expansion", "prerequisite_guard"] = "routing_preference"
    rule_content: dict[str, Any] = field(default_factory=dict)
    supporting_case_ids: list[str] = field(default_factory=list)
    counterexample_case_ids: list[str] = field(default_factory=list)
    evidence_quality: float = 0.5
    risk_level: Literal["low", "medium", "high"] = "low"
    status: Literal["OBSERVED", "CANDIDATE", "EVALUATING", "APPROVED", "REJECTED", "SUPERSEDED"] = "CANDIDATE"
    author: str = "capability_finder.learning"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    evaluated_at: str | None = None
    evaluation_summary: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LessonProposal:
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


class LessonGenerator:
    """Clusters historical cases and reviewer feedback into declarative candidate lesson proposals."""

    def __init__(
        self,
        collector: CaseCollector | None = None,
        min_evidence_threshold: int = 2,
    ) -> None:
        self._collector = collector or case_collector
        self.min_evidence_threshold = min_evidence_threshold

    def generate_proposals(self) -> list[LessonProposal]:
        """Scans learning cases for recurring patterns meeting the evidence threshold."""
        cases = self._collector.list_cases()
        proposals: list[LessonProposal] = []

        # 1. Cluster cases with reviewer corrections (deduplicated by case_id)
        correction_clusters: dict[tuple[str, str], dict[str, LearningCase]] = defaultdict(dict)
        for c in cases:
            for fb in c.reviewer_feedback:
                suggested_delegate = fb.get("suggested_delegate_id")
                suggested_action = fb.get("suggested_action")
                if suggested_delegate or suggested_action:
                    key = (c.parsed_requirement.get("domain", "general"), suggested_delegate or suggested_action)
                    correction_clusters[key][c.case_id] = c

        for (domain, target), cluster_dict in correction_clusters.items():
            unique_cases = list(cluster_dict.values())
            if len(unique_cases) >= self.min_evidence_threshold:
                supporting_ids = sorted([c.case_id for c in unique_cases])
                pattern_desc = f"Reviewers repeatedly corrected {len(unique_cases)} cases in domain '{domain}' recommending target '{target}'."
                proposal = LessonProposal(
                    title=f"Routing Preference for {domain.title()} -> {target}",
                    description=f"Directs requests in domain '{domain}' towards target '{target}' based on verified reviewer feedback.",
                    observed_pattern=pattern_desc,
                    affected_domain=domain,
                    rule_type="routing_preference",
                    rule_content={
                        "target_domain": domain,
                        "preferred_delegate_id": target,
                        "boost_score": 0.25,
                    },
                    supporting_case_ids=supporting_ids,
                    evidence_quality=min(1.0, 0.5 + 0.1 * len(unique_cases)),
                    risk_level="low",
                    status="CANDIDATE",
                )
                proposals.append(proposal)

        # 2. Cluster attributable failure categories (deduplicated by case_id)
        failure_clusters: dict[tuple[str, str], dict[str, LearningCase]] = defaultdict(dict)
        for c in cases:
            if c.actual_outcome == "failed" and c.failure_category:
                key = (c.parsed_requirement.get("domain", "general"), c.failure_category)
                failure_clusters[key][c.case_id] = c

        for (domain, failure_cat), cluster_dict in failure_clusters.items():
            unique_cases = list(cluster_dict.values())
            if len(unique_cases) >= self.min_evidence_threshold:
                supporting_ids = sorted([c.case_id for c in unique_cases])
                pattern_desc = f"Observed {len(unique_cases)} repeated failures in domain '{domain}' categorized as '{failure_cat}'."
                proposal = LessonProposal(
                    title=f"Prerequisite Guard for {domain.title()} ({failure_cat})",
                    description=f"Applies strict constraint check for {failure_cat} in {domain} requests to prevent recurring failures.",
                    observed_pattern=pattern_desc,
                    affected_domain=domain,
                    rule_type="prerequisite_guard",
                    rule_content={
                        "domain": domain,
                        "failure_category": failure_cat,
                        "require_strict_verification": True,
                    },
                    supporting_case_ids=supporting_ids,
                    evidence_quality=min(1.0, 0.6 + 0.1 * len(unique_cases)),
                    risk_level="medium",
                    status="CANDIDATE",
                )
                proposals.append(proposal)

        return proposals


lesson_generator = LessonGenerator()
