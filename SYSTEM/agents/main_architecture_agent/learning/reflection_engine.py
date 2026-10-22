"""Reflection Engine for Main Architecture Agent.

Analyzes raw execution experiences, detects recurring patterns and failures,
and synthesizes evidence-backed Lesson items with rigorous confidence scoring.
"""
from __future__ import annotations

import collections
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from .experience_collector import ExperienceRecord, experience_collector


@dataclass
class LessonItem:
    lesson_id: str = field(default_factory=lambda: f"lsn_{uuid.uuid4().hex[:10]}")
    lesson_type: Literal[
        "routing_failure",
        "routing_success",
        "dependency_error",
        "prerequisite_missing",
        "user_correction",
        "excessive_retries",
        "latency_inefficiency",
    ] = "routing_failure"
    description: str = ""
    confidence: float = 0.5  # 0.0 to 1.0
    status: Literal["hypothesis", "validated", "rejected"] = "hypothesis"
    applicable_categories: list[str] = field(default_factory=list)
    limitations: str = ""
    supporting_experience_ids: list[str] = field(default_factory=list)
    target_mutation_field: str = ""
    suggested_mutation: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LessonItem:
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


@dataclass
class ReflectionReport:
    report_id: str = field(default_factory=lambda: f"ref_{uuid.uuid4().hex[:8]}")
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    analyzed_experience_count: int = 0
    lessons: list[LessonItem] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["lessons"] = [l.to_dict() if isinstance(l, LessonItem) else l for l in self.lessons]
        return d


class ReflectionEngine:
    """Performs statistical and heuristic reflection over task experiences."""

    def __init__(
        self,
        min_sample_for_validation: int = 2,
        collector: ExperienceCollector | None = None,
    ) -> None:
        self.min_sample_for_validation = min_sample_for_validation
        self._collector = collector

    @property
    def collector(self) -> ExperienceCollector:
        return self._collector or experience_collector

    def reflect_on_experiences(
        self,
        experiences: list[ExperienceRecord] | None = None,
        mark_processed: bool = True,
    ) -> ReflectionReport:
        """Analyzes a set of experiences and derives structured lessons."""
        if experiences is None:
            experiences = self.collector.get_unreflected_experiences(limit=50)

        if not experiences:
            return ReflectionReport(
                analyzed_experience_count=0,
                summary="No unreflected experiences available for reflection.",
            )

        lessons: list[LessonItem] = []

        # 1. Analyze Agent Routing Failures & Errors
        agent_failures: dict[str, list[ExperienceRecord]] = collections.defaultdict(list)
        agent_successes: dict[str, list[ExperienceRecord]] = collections.defaultdict(list)
        user_corrections: list[ExperienceRecord] = []
        retry_heavy_experiences: list[ExperienceRecord] = []

        for exp in experiences:
            if exp.user_feedback and exp.user_feedback.get("corrected_agent"):
                user_corrections.append(exp)

            if exp.retries > 1:
                retry_heavy_experiences.append(exp)

            for agent in exp.selected_agents:
                if exp.status == "failed" or exp.status == "blocked":
                    agent_failures[agent].append(exp)
                elif exp.status == "succeeded":
                    agent_successes[agent].append(exp)

        # Pattern A: Repeated Agent Routing Failures
        for agent, fails in agent_failures.items():
            fail_count = len(fails)
            exp_ids = [f.experience_id for f in fails]
            confidence = min(0.9, 0.4 + (0.2 * fail_count))
            status = "validated" if fail_count >= self.min_sample_for_validation else "hypothesis"

            # Determine root error category
            err_cats = collections.Counter([f.error_category or "unknown" for f in fails])
            primary_err = err_cats.most_common(1)[0][0]

            fallback_target = "motion_planning" if agent == "motion_template_selection" else "capability_finder"
            lessons.append(LessonItem(
                lesson_type="routing_failure",
                description=f"Agent '{agent}' failed {fail_count} times primarily due to '{primary_err}'. Fallback route needed.",
                confidence=confidence,
                status=status,
                applicable_categories=[primary_err],
                limitations=f"Based on sample of {fail_count} recent executions.",
                supporting_experience_ids=exp_ids,
                target_mutation_field="fallback_routes",
                suggested_mutation={agent: fallback_target},
            ))

        # Pattern B: User Corrections (High Signal)
        if user_corrections:
            for exp in user_corrections:
                correction = exp.user_feedback or {}
                original = correction.get("original_agent") or (exp.selected_agents[0] if exp.selected_agents else "unknown")
                suggested = correction.get("corrected_agent")
                if suggested and original:
                    lessons.append(LessonItem(
                        lesson_type="user_correction",
                        description=f"User explicitly corrected agent '{original}' to '{suggested}' for goal: {exp.goal[:50]}.",
                        confidence=0.85,
                        status="validated",
                        applicable_categories=["user_preference"],
                        limitations="Direct explicit user operator feedback.",
                        supporting_experience_ids=[exp.experience_id],
                        target_mutation_field="agent_routing_preferences",
                        suggested_mutation={"target_agent": suggested, "replace_agent": original},
                    ))

        # Pattern C: Excessive Retries / Latency
        if retry_heavy_experiences:
            exp_ids = [e.experience_id for e in retry_heavy_experiences]
            lessons.append(LessonItem(
                lesson_type="excessive_retries",
                description=f"{len(retry_heavy_experiences)} tasks required multiple retries, indicating fragile dependency or timeout thresholds.",
                confidence=0.7,
                status="validated" if len(retry_heavy_experiences) >= self.min_sample_for_validation else "hypothesis",
                supporting_experience_ids=exp_ids,
                target_mutation_field="retry_policies",
                suggested_mutation={"action": "increase_initial_delay", "backoff_factor": 2.0},
            ))

        # Pattern D: High-Performing Agent Routing Confirmation
        for agent, succs in agent_successes.items():
            if len(succs) >= 3 and agent not in agent_failures:
                lessons.append(LessonItem(
                    lesson_type="routing_success",
                    description=f"Agent '{agent}' achieved consistent 100% success across {len(succs)} executions.",
                    confidence=0.9,
                    status="validated",
                    supporting_experience_ids=[s.experience_id for s in succs],
                    target_mutation_field="agent_routing_preferences",
                    suggested_mutation={"preferred_agent": agent, "weight_boost": 0.2},
                ))

        if mark_processed:
            self.collector.mark_reflected([e.experience_id for e in experiences])

        report = ReflectionReport(
            analyzed_experience_count=len(experiences),
            lessons=lessons,
            summary=f"Analyzed {len(experiences)} experiences; derived {len(lessons)} lessons ({sum(1 for l in lessons if l.status == 'validated')} validated).",
        )
        return report


reflection_engine = ReflectionEngine()
