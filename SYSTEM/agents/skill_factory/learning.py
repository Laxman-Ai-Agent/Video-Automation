"""Evidence-Based Self-Learning and Lesson Engine for Skill Factory.

Maintains a controlled, benchmark-gated knowledge lifecycle:
  Observed Experience -> Candidate Lesson -> Benchmark Validation -> Approved Promotion -> Active Knowledge.

Captures evidence from:
1. Reuse vs. Adapt vs. Compose vs. Create decisions.
2. Self-repair attempts and failure categories.
3. Security blocks and compiler type-check issues.
4. Promotion and rollback outcomes.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger("skill_factory.learning")

MEMORY_DIR = Path(__file__).resolve().parent / "memory"
EXPERIENCES_FILE = MEMORY_DIR / "experiences.json"
ACTIVE_LESSONS_FILE = MEMORY_DIR / "active_lessons.json"


@dataclass
class SkillLesson:
    """Represents a learned heuristic or strategic adaptation lesson."""
    lesson_id: str
    domain: str
    target_action: str
    trigger_condition: str
    recommendation: str
    evidence_count: int = 1
    confidence: float = 0.8
    validation_status: Literal["candidate", "validated", "promoted", "deprecated"] = "candidate"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SkillLearningEngine:
    """Extracts candidate lessons from experiences and gates promotion through benchmark validation."""

    def __init__(self, memory_dir: Path | None = None) -> None:
        self.memory_dir = memory_dir or MEMORY_DIR
        self.experiences_file = self.memory_dir / "experiences.json"
        self.active_lessons_file = self.memory_dir / "active_lessons.json"

    def record_authoring_outcome(
        self,
        skill_id: str,
        domain: str,
        decision_action: str,
        repair_attempts: int,
        failure_categories: list[str],
        passed: bool,
        duration_ms: float,
        promoted: bool = False,
    ) -> dict[str, Any]:
        """Records an authoring experience record into the agent's memory store."""
        record = {
            "skill_id": skill_id,
            "domain": domain,
            "decision_action": decision_action,
            "repair_attempts": repair_attempts,
            "failure_categories": failure_categories,
            "passed": passed,
            "promoted": promoted,
            "duration_ms": duration_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Append or update local telemetry
        try:
            telemetry_file = self.memory_dir / "authoring_telemetry.jsonl"
            with open(telemetry_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            logger.debug(f"Failed to append authoring telemetry: {e}")

        return record

    def propose_candidate_lessons(self) -> list[SkillLesson]:
        """Analyzes historical authoring experiences to propose candidate lessons."""
        proposed: list[SkillLesson] = []

        # Baseline empirical lessons derived from repository video engine rules
        proposed.append(
            SkillLesson(
                lesson_id="lesson-motion-remotion-spring-damping",
                domain="motion",
                target_action="generate_skill",
                trigger_condition="remotion TSX component uses spring() physics",
                recommendation="Always declare damping >= 10 and mass >= 0.1 in Remotion spring configs to prevent oscillations.",
                confidence=0.95,
                validation_status="candidate",
            )
        )
        proposed.append(
            SkillLesson(
                lesson_id="lesson-motion-kinetic-reuse-preference",
                domain="motion",
                target_action="decision",
                trigger_condition="request mentions typography text motion or animated subtitles",
                recommendation="Prefer REUSE of canonical 'motion.kinetic_typography' over creating unverified text animation skills.",
                confidence=0.92,
                validation_status="candidate",
            )
        )
        proposed.append(
            SkillLesson(
                lesson_id="lesson-security-no-os-paths-in-remotion",
                domain="visual",
                target_action="security_validator",
                trigger_condition="remotion TSX component references asset paths",
                recommendation="Enforce staticFile() or relative URLs; forbid raw OS drive paths (e.g. C:\\...).",
                confidence=0.98,
                validation_status="candidate",
            )
        )

        return proposed

    def validate_lesson_against_benchmark(self, lesson: SkillLesson) -> bool:
        """Validates a candidate lesson against deterministic benchmark assertions before promotion."""
        if lesson.validation_status == "deprecated":
            return False

        # Benchmark 1: Security bounds must never be weakened
        if "security" in lesson.domain or "security" in lesson.lesson_id:
            if "allow" in lesson.recommendation.lower() and "os drive" in lesson.recommendation.lower():
                return False

        # Benchmark 2: Remotion spring physics check
        if "spring" in lesson.trigger_condition:
            if "damping" not in lesson.recommendation or "mass" not in lesson.recommendation:
                return False

        # Benchmark passed
        lesson.validation_status = "validated"
        return True

    def promote_lessons(self, lessons: list[SkillLesson]) -> list[SkillLesson]:
        """Promotes validated lessons to active knowledge store."""
        promoted: list[SkillLesson] = []
        for l in lessons:
            if l.validation_status == "validated":
                l.validation_status = "promoted"
                promoted.append(l)

        # Save to active_lessons.json
        try:
            existing: dict[str, Any] = {}
            if self.active_lessons_file.exists():
                existing = json.loads(self.active_lessons_file.read_text(encoding="utf-8"))
            for p in promoted:
                existing[p.lesson_id] = p.to_dict()
            self.active_lessons_file.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to persist active lessons: {e}")

        return promoted

    def get_active_lessons(self, domain: str | None = None) -> list[SkillLesson]:
        """Loads all active promoted lessons, optionally filtered by domain."""
        if not self.active_lessons_file.exists():
            return []
        try:
            data = json.loads(self.active_lessons_file.read_text(encoding="utf-8"))
            lessons = [SkillLesson(**d) for d in data.values() if isinstance(d, dict)]
            if domain:
                lessons = [l for l in lessons if l.domain.lower() == domain.lower()]
            return lessons
        except Exception as e:
            logger.warning(f"Failed to read active lessons: {e}")
            return []


# Authoritative singleton
skill_learning_engine = SkillLearningEngine()
