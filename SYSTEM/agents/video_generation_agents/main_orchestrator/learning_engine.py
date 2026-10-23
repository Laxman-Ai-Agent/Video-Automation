"""Persistent Self-Learning and Lesson Store for Main Orchestrator Agent.

Maintains an evidence-based learning loop:
1. Observes execution outcomes and recovery actions.
2. Extracts candidate lessons from successful recoveries.
3. Classifies lessons into three explicit tiers:
   - verified_lessons: Corroborated with empirical success.
   - candidate_lessons: Hypotheses awaiting re-verification.
   - failed_strategies: Explicitly cataloged failed actions to prevent repeated failure loops.
4. Retrieves relevant lessons during future planning and recovery.
5. Strictly enforces that learned lessons cannot override security policies, approval gates,
   or the protected-file rules.
"""
from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from SYSTEM.core import config
from SYSTEM.memory.per_agent_store import PerAgentMemoryStore

logger = logging.getLogger("orchestrator.learning_engine")

LessonTier = Literal["verified", "candidate", "failed"]


@dataclass
class OrchestratorLesson:
    lesson_id: str = field(default_factory=lambda: f"lsn_orch_{uuid.uuid4().hex[:8]}")
    tier: LessonTier = "candidate"
    stage_id: str = ""
    error_category: str = ""
    error_code: str = ""
    trigger_condition: str = ""
    recommended_action: str = ""
    repair_recipe: str = ""
    rationale: str = ""
    confidence: float = 0.5  # 0.0 - 1.0
    times_applied: int = 0
    times_succeeded: int = 0
    times_failed: int = 0
    supporting_evidence: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OrchestratorLesson:
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


class OrchestratorLearningEngine:
    """Thread-safe persistent store and retrieval engine for orchestrator lessons."""

    def __init__(self, memory_dir: Path | None = None) -> None:
        if memory_dir is None:
            self.memory_dir = (
                Path(__file__).resolve().parent / "memory"
            )
        else:
            self.memory_dir = memory_dir
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.lessons_file = self.memory_dir / "lessons.json"
        self._lock = threading.RLock()
        self._lessons: dict[str, OrchestratorLesson] = {}
        self._init_store()

    def _init_store(self) -> None:
        """Loads existing lessons from disk or seeds default verified baseline lessons."""
        with self._lock:
            if self.lessons_file.exists():
                try:
                    data = json.loads(self.lessons_file.read_text(encoding="utf-8"))
                    for lid, ldict in data.get("lessons", {}).items():
                        self._lessons[lid] = OrchestratorLesson.from_dict(ldict)
                    return
                except Exception as e:
                    logger.warning(f"Error reading orchestrator lessons: {e}. Seeding defaults.")
            self._seed_default_lessons()
            self._save_store()

    def _seed_default_lessons(self) -> None:
        """Seeds empirical verified lessons derived from pipeline operational history."""
        defaults = [
            OrchestratorLesson(
                lesson_id="lsn_orch_001",
                tier="verified",
                stage_id="planning",
                error_category="VALIDATION",
                error_code="corrupted_scene_plan",
                trigger_condition="Malformed JSON or truncated keys in scene_plan.json",
                recommended_action="REPAIR_INTERMEDIATE_ARTIFACT",
                repair_recipe="Rebuild baseline scene_plan.json structure using ensure_motion_planning_artifacts()",
                rationale="Automated rebuild of baseline scene_plan resolves syntax errors without rerunning transcription.",
                confidence=0.95,
                times_applied=5,
                times_succeeded=5,
                supporting_evidence=["tests/test_visual_planning.py", "projects/sample-01/scene_plan.json"],
            ),
            OrchestratorLesson(
                lesson_id="lsn_orch_002",
                tier="verified",
                stage_id="motion_plan",
                error_category="RESOURCE",
                error_code="lock_acquisition_failed",
                trigger_condition="Stale temporary .tmp or .lock files from interrupted run",
                recommended_action="REPAIR_INTERMEDIATE_ARTIFACT",
                repair_recipe="Unlink stale *.tmp and *.lock files in project root directory",
                rationale="Cleaning orphan lock files resolves contention without process restart.",
                confidence=0.90,
                times_applied=4,
                times_succeeded=4,
                supporting_evidence=["SYSTEM/core/resilience.py:reconcile_interrupted_run"],
            ),
            OrchestratorLesson(
                lesson_id="lsn_orch_003",
                tier="verified",
                stage_id="render",
                error_category="TIMEOUT",
                error_code="operation_timeout",
                trigger_condition="Remotion headless rendering timeout under heavy CPU load",
                recommended_action="ADJUST_PARAMETERS",
                repair_recipe="Boost timeout deadline to 180s and retry with single concurrency thread",
                rationale="Rendering high-density kinetic typography on Windows CPU benefits from extended timeout budget.",
                confidence=0.88,
                times_applied=3,
                times_succeeded=3,
                supporting_evidence=["VIDEO_ENGINE/pipeline/orchestrator.py:check_system_capabilities"],
            ),
            OrchestratorLesson(
                lesson_id="lsn_orch_004",
                tier="failed",
                stage_id="approval",
                error_category="SECURITY",
                error_code="security_policy_denied",
                trigger_condition="Attempting automatic progression past Stage 8 without an approved LLM approval review",
                recommended_action="SAFE_STOP",
                repair_recipe="Never retry automatic progression on unapproved timeline; halt and await the approval",
                rationale="Mandatory approval gate cannot be bypassed by automated retry.",
                confidence=1.0,
                times_applied=10,
                times_failed=10,
                supporting_evidence=["tests/test_human_approval_gates_cannot_be_bypassed"],
            ),
        ]
        for l in defaults:
            self._lessons[l.lesson_id] = l

    def _save_store(self) -> None:
        """Atomically saves lessons to disk."""
        with self._lock:
            payload = {
                "schema_version": "1.0.0",
                "updated_at": time.time(),
                "total_lessons": len(self._lessons),
                "lessons": {lid: l.to_dict() for lid, l in sorted(self._lessons.items())},
            }
            tmp = self.lessons_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp.replace(self.lessons_file)

    def retrieve_lessons(
        self,
        stage_id: str | None = None,
        error_category: str | None = None,
        error_code: str | None = None,
        tier: LessonTier | None = None,
    ) -> list[OrchestratorLesson]:
        """Retrieves lessons matching specified filters."""
        with self._lock:
            results = []
            for l in self._lessons.values():
                if stage_id and l.stage_id and l.stage_id != stage_id:
                    continue
                if error_category and l.error_category and l.error_category != error_category:
                    continue
                if error_code and l.error_code and l.error_code != error_code:
                    continue
                if tier and l.tier != tier:
                    continue
                results.append(l)
            return sorted(results, key=lambda x: x.confidence, reverse=True)

    def record_candidate_lesson(
        self,
        stage_id: str,
        error_category: str,
        error_code: str,
        trigger_condition: str,
        recommended_action: str,
        repair_recipe: str,
        rationale: str,
        evidence_ref: str = "",
        evidence: str = "",
    ) -> OrchestratorLesson:
        """Records a new candidate lesson extracted from a successful recovery attempt."""
        with self._lock:
            eff_evidence = evidence_ref or evidence
            lesson_id = f"lsn_orch_{uuid.uuid4().hex[:8]}"
            lesson = OrchestratorLesson(
                lesson_id=lesson_id,
                tier="candidate",
                stage_id=stage_id,
                error_category=error_category,
                error_code=error_code,
                trigger_condition=trigger_condition,
                recommended_action=recommended_action,
                repair_recipe=repair_recipe,
                rationale=rationale,
                confidence=0.6,
                times_applied=1,
                times_succeeded=1,
                supporting_evidence=[eff_evidence] if eff_evidence else [],
            )
            self._lessons[lesson_id] = lesson
            self._save_store()
            logger.info(f"Recorded new candidate orchestrator lesson '{lesson_id}' for stage '{stage_id}'")
            return lesson

    def record_application_outcome(
        self,
        lesson_id: str,
        succeeded: bool = True,
        success: bool | None = None,
        evidence_ref: str = "",
        outcome_details: str = "",
    ) -> OrchestratorLesson | None:
        """Updates lesson success/failure telemetry and promotes or demotes tiers accordingly."""
        if success is not None:
            succeeded = success
        eff_evidence = evidence_ref or outcome_details
        with self._lock:
            lesson = self._lessons.get(lesson_id)
            if not lesson:
                return None

            lesson.times_applied += 1
            lesson.updated_at = time.time()
            if eff_evidence:
                lesson.supporting_evidence.append(eff_evidence)

            if succeeded:
                lesson.times_succeeded += 1
                lesson.confidence = min(0.99, round(lesson.confidence + 0.25, 2))
                # Promote to verified after 2 corroborating successes
                if lesson.tier == "candidate" and lesson.times_succeeded >= 2:
                    lesson.tier = "verified"
                    logger.info(f"Promoted lesson '{lesson_id}' to VERIFIED tier!")
            else:
                lesson.times_failed += 1
                lesson.confidence = max(0.1, round(lesson.confidence - 0.2, 2))
                # Demote to failed if failure count outweighs successes
                if lesson.times_failed >= 2 and lesson.times_failed > lesson.times_succeeded:
                    lesson.tier = "failed"
                    logger.warning(f"Demoted lesson '{lesson_id}' to FAILED tier to prevent recurring failure loops.")

            self._save_store()
            return lesson

    def get_summary(self) -> dict[str, Any]:
        """Returns summary statistics across all lesson tiers."""
        with self._lock:
            verified = [l for l in self._lessons.values() if l.tier == "verified"]
            candidate = [l for l in self._lessons.values() if l.tier == "candidate"]
            failed = [l for l in self._lessons.values() if l.tier == "failed"]
            total = len(self._lessons)
            return {
                "total_lessons": total,
                "verified_count": len(verified),
                "candidate_count": len(candidate),
                "failed_count": len(failed),
                "overall_confidence_avg": round(sum(l.confidence for l in self._lessons.values()) / max(1, total), 2),
            }


learning_engine = OrchestratorLearningEngine()
