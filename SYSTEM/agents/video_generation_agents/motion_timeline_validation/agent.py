"""Dedicated implementation module for Motion Validation Agent v2.0.0.
Agent ID: motion_timeline_validation
Stage ID: motion_validation

Autonomous evidence-driven validation and visual quality assessment system featuring:
- 12-rule deterministic technical validation preservation.
- VisualQualityAssessor: Computer vision heuristics on preview stills and LLM review.
- SemanticAlignmentEngine: Visual plan fidelity and 3D graceful fallback verification.
- QualityScoreAggregator: 4-Dimensional Quality Architecture (Technical, Visual, Semantic, Runtime).
- AutonomousRepairCoordinator: Bounded auto-repair loop (max 2 attempts) for actionable defects.
- Autonomous memory reflection and learning.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from SYSTEM.agents.shared.base_agent import BaseAgent
from SYSTEM.agents.shared.contracts import AgentMetadata, AgentRequest, AgentResult, AgentStatus, ArtifactRef
from SYSTEM.agents.video_generation_agents.motion_timeline_validation.validation_intelligence import (
    AutonomousRepairCoordinator,
    QualityScoreAggregator,
    SemanticAlignmentEngine,
    VisualQualityAssessor,
    evaluate_quality_and_alignment,
)
from SYSTEM.memory import store

logger = logging.getLogger("motion_validation.agent")


class MotionValidationAgent(BaseAgent):
    """A09: Motion & Timeline Validation Agent v2.0.0.

    Validates composition, timing, resources, visual composition, and semantic fidelity.
    """

    def __init__(self, metadata: AgentMetadata | None = None) -> None:
        if metadata is None:
            metadata = AgentMetadata(
                agent_id="motion_timeline_validation",
                name="Motion Validation Agent",
                version="2.0.0",
                stage_id="motion_validation",
                purpose="Autonomous visual quality assessment, semantic alignment, 4D scoring, and bounded recovery for motion output",
            )
        super().__init__(metadata)
        self.visual_assessor = VisualQualityAssessor()
        self.semantic_engine = SemanticAlignmentEngine()
        self.repair_coordinator = AutonomousRepairCoordinator()
        self.aggregator = QualityScoreAggregator()

    def validate(self, project_dir: Path, request: AgentRequest) -> list[str]:
        aspect = request.parameters.get("aspect", "16:9")
        sfx = "_9x16" if aspect == "9:16" else ""
        comp = project_dir / f"composition{sfx}.json"
        mplan = project_dir / f"motion_plan{sfx}.json"
        splan = project_dir / "scene_plan.json"

        if not comp.exists() and not mplan.exists() and not splan.exists():
            return ["Missing composition.json, motion_plan.json, or scene_plan.json for motion validation"]
        return []

    def execute(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        aspect = request.parameters.get("aspect", "16:9")
        force = request.parameters.get("force", False)
        auto_repair = request.parameters.get("auto_repair", True)
        max_attempts = int(request.parameters.get("max_repair_attempts", 2))

        sfx = "_9x16" if aspect == "9:16" else ""
        val_path = project_dir / f"motion_timeline_validation{sfx}.json"
        preview_dir = project_dir / f"motion_validation_preview{sfx}"
        intel_report_path = project_dir / f"motion_validation_intelligence{sfx}.json"

        t0 = time.perf_counter()
        from VIDEO_ENGINE.stages import motion_validation

        # 1. Run or Load Deterministic Validation (12 stages)
        try:
            rep = motion_validation.load(project_dir, aspect)
            if rep is None or rep.get("stale") or force:
                rep = motion_validation.run(project_dir, aspect, force=force)
        except Exception as e:
            logger.error(f"Deterministic validation failed: {e}", exc_info=True)
            return AgentResult(
                agent_id=self.agent_id,
                stage_id="motion_validation",
                project_id=project_dir.name,
                status="failed",
                error=str(e),
                summary=f"Deterministic validation failed to run: {e}",
            )

        # 2. Visual Quality Assessment on Preview Stills
        vis_results = self.visual_assessor.assess(project_dir, aspect=aspect)

        # 3. Semantic Alignment & 3D Fallback Assessment
        sem_results = self.semantic_engine.evaluate(project_dir, aspect=aspect)

        # 4. 4-Dimensional Quality Aggregation
        assessment = self.aggregator.aggregate(rep, vis_results, sem_results)

        # 5. Bounded Autonomous Repair (if repairable findings exist)
        repair_summary: dict[str, Any] = {"repaired_count": 0, "attempts": 0}
        if auto_repair and assessment.get("repairable_findings", 0) > 0:
            repair_summary = self.repair_coordinator.coordinate_repair(
                project_dir=project_dir,
                aspect=aspect,
                findings=assessment.get("unified_findings", []),
                max_attempts=max_attempts,
            )
            # If repairs were made, re-run deterministic validation and re-aggregate
            if repair_summary.get("repaired_count", 0) > 0:
                try:
                    rep = motion_validation.run(project_dir, aspect, force=True)
                    vis_results = self.visual_assessor.assess(project_dir, aspect=aspect)
                    sem_results = self.semantic_engine.evaluate(project_dir, aspect=aspect)
                    assessment = self.aggregator.aggregate(rep, vis_results, sem_results)
                except Exception as e:
                    logger.warning(f"Re-validation after repair encountered error: {e}")

        # 6. Save Enriched Quality Assessment
        intel_payload = {
            "schema_version": "2.0",
            "quality_dimensions": assessment["quality_dimensions"],
            "readiness": assessment["readiness"],
            "deterministic_readiness": assessment["deterministic_readiness"],
            "category_counts": assessment["category_counts"],
            "unified_findings": assessment["unified_findings"],
            "visual_assessment": vis_results,
            "semantic_alignment": sem_results,
            "repair_summary": repair_summary,
            "timings_ms": round((time.perf_counter() - t0) * 1000),
        }
        intel_report_path.write_text(json.dumps(intel_payload, indent=2, ensure_ascii=False), encoding="utf-8")

        # The validation report is written only by motion_validation (its own quality_assessment included): rewriting it here made its LLM review stale on every run.

        # 7. Collect Outputs
        outputs: list[ArtifactRef] = []
        if val_path.exists():
            outputs.append(ArtifactRef(path=str(val_path), description="Motion Validation Report JSON"))
        if intel_report_path.exists():
            outputs.append(
                ArtifactRef(
                    path=str(intel_report_path),
                    description="Motion Validation Intelligence Report JSON (4D Quality & Findings)",
                )
            )
        if preview_dir.exists():
            outputs.append(ArtifactRef(path=str(preview_dir), description="Rendered Preview Stills Directory"))

        # 8. Record Autonomous Memory Reflection
        q_dims = assessment["quality_dimensions"]
        status_map = {
            "ready": "succeeded",
            "ready_with_warnings": "succeeded",
            "needs_review": "needs_review",
            "blocked": "blocked",
            "failed": "failed",
            "stale": "needs_review",
        }
        agent_status = status_map.get(assessment["readiness"], "needs_review")

        try:
            self.memory.record_experience(
                task_type="motion_timeline_validation",
                outcome=agent_status,
                project_id=project_dir.name,
                metrics={
                    "overall_score": q_dims.get("overall", 0.0),
                    "technical_score": q_dims.get("technical", 0.0),
                    "visual_score": q_dims.get("visual", 0.0),
                    "semantic_score": q_dims.get("semantic", 0.0),
                    "runtime_score": q_dims.get("runtime", 0.0),
                    "total_findings": assessment.get("total_findings", 0),
                    "repaired_count": repair_summary.get("repaired_count", 0),
                    "readiness": assessment["readiness"],
                },
                reflection=(
                    f"Motion Validation evaluated with overall quality {q_dims.get('overall')} "
                    f"(Tech: {q_dims.get('technical')}, Visual: {q_dims.get('visual')}, "
                    f"Semantic: {q_dims.get('semantic')}, Runtime: {q_dims.get('runtime')}). "
                    f"Readiness: {assessment['readiness']}. Repaired {repair_summary.get('repaired_count')} defects."
                ),
            )
        except Exception as e:
            logger.info(f"Memory recording skipped: {e}")

        return AgentResult(
            agent_id=self.agent_id,
            stage_id="motion_validation",
            project_id=project_dir.name,
            status=agent_status,
            output_refs=outputs,
            metadata={
                "quality_dimensions": q_dims,
                "readiness": assessment["readiness"],
                "total_findings": assessment.get("total_findings", 0),
                "repaired_count": repair_summary.get("repaired_count", 0),
            },
            summary=(
                f"Motion timeline validation completed with readiness '{assessment['readiness']}'. "
                f"Overall Quality: {q_dims.get('overall')}/100. Repaired: {repair_summary.get('repaired_count', 0)}."
            ),
        )


# Backward-compatibility alias
MotionValidationAdapter = MotionValidationAgent
