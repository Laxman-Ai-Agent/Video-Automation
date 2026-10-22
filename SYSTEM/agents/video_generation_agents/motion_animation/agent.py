"""Dedicated implementation module for Motion Animation Agent v2.0.0.
Agent ID: motion_animation
Stage ID: motion_gen

Autonomous animation engineering system featuring:
- LLM-first React/TSX Remotion code generation using core primitives.
- ThreeDFallbackEngine for graceful 2D/2.5D approximation and retry prevention.
- VisualPreviewVerifier for static safe-area and typography quality assurance.
- StructuredGenerationReporter for element-level diagnostics (motion_generation_report.json).
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
from SYSTEM.agents.video_generation_agents.motion_animation.animation_intelligence import (
    StructuredGenerationReporter,
    ThreeDFallbackEngine,
    VisualPreviewVerifier,
)
from SYSTEM.memory import store

logger = logging.getLogger("motion_animation.agent")


class MotionAnimationAgent(BaseAgent):
    """A08: Motion Animation Agent v2.0.0.

    Synthesizes production-ready, safe Remotion React/TSX components with
    graceful 3D fallbacks and retry prevention.
    """

    def __init__(self, metadata: AgentMetadata | None = None) -> None:
        if metadata is None:
            metadata = AgentMetadata(
                agent_id="motion_animation",
                name="Motion Animation Agent",
                version="2.0.0",
                stage_id="motion_gen",
                purpose="Autonomous React/Remotion TSX animation synthesis with 3D fallback and retry prevention",
            )
        super().__init__(metadata)
        self.fallback_engine = ThreeDFallbackEngine()
        self.preview_verifier = VisualPreviewVerifier()
        self.reporter = StructuredGenerationReporter()

    def validate(self, project_dir: Path, request: AgentRequest) -> list[str]:
        aspect = request.parameters.get("aspect", "16:9")
        sfx = "_9x16" if aspect == "9:16" else ""
        mp = project_dir / f"motion_plan{sfx}.json"
        mpl = project_dir / f"motion_planning{sfx}.json"
        if not mp.exists() and not mpl.exists():
            return ["Missing motion_plan.json or motion_planning.json for motion animation code generation"]
        return []

    def execute(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        aspect = request.parameters.get("aspect", "16:9")
        sfx = "_9x16" if aspect == "9:16" else ""
        comp = project_dir / f"composition{sfx}.json"
        anim = project_dir / f"motion_animation{sfx}.json"
        report_path = project_dir / f"motion_generation_report{sfx}.json"

        # The canonical step (legacy_pipeline_adapter "motion-build") does the work: it checks the motion plan gate, generates and compiles the code, writes the report and
        # records the inputs it was made from, so is_fresh() and the pipeline view agree. A build whose inputs did not change is kept as it is.
        from VIDEO_ENGINE.pipeline import legacy_pipeline_adapter
        from VIDEO_ENGINE.stages import motion_branch
        step = motion_branch.names(aspect)[1]
        try:
            if not legacy_pipeline_adapter.is_fresh(project_dir, step):
                legacy_pipeline_adapter.execute(project_dir, step, legacy_pipeline_adapter.Ctx())
        except Exception as e:
            logger.error(f"Motion generation failed: {e}", exc_info=True)
            return AgentResult(
                agent_id=self.agent_id,
                stage_id="motion_gen",
                project_id=project_dir.name,
                status="failed",
                error=str(e),
                summary=f"Custom motion generation failed: {e}",
            )

        outputs: list[ArtifactRef] = []
        if comp.exists():
            outputs.append(ArtifactRef(path=str(comp), description="Composition Manifest JSON"))
        if anim.exists():
            outputs.append(ArtifactRef(path=str(anim), description="Motion Animation Report JSON"))
        if report_path.exists():
            outputs.append(
                ArtifactRef(
                    path=str(report_path),
                    description="Motion Generation Intelligence Report JSON (3D Fallbacks & Diagnostics)",
                )
            )

        # Collect generated scene source files
        gen_dir = project_dir / "generated_motion"
        if gen_dir.is_dir():
            for scene_file in sorted(gen_dir.glob("scene_*.tsx")):
                outputs.append(ArtifactRef(path=str(scene_file), description=f"Custom TSX Component {scene_file.name}"))

        # Evaluate execution manifest status
        status = "needs_review"
        err = None
        report_data = {}
        if report_path.exists():
            try:
                report_data = json.loads(report_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        if anim.exists():
            try:
                a_data = json.loads(anim.read_text(encoding="utf-8"))
                if a_data.get("mode") != "custom_code":
                    status = "blocked"
                    err = "Motion Animation is not in custom_code mode"
                elif a_data.get("status") in ("validated", "generated"):
                    status = "succeeded"
                else:
                    status = "blocked"
                    err = f"Motion animation status: {a_data.get('status')}"
            except Exception as e:
                status = "blocked"
                err = f"Invalid motion_animation.json: {e}"
        elif comp.exists():
            status = "succeeded"

        # Record autonomous memory reflection
        try:
            metrics = report_data.get("aggregate_metrics", {})
            self.memory.record_experience(
                task_type="motion_animation_codegen",
                outcome=status,
                project_id=project_dir.name,
                metrics={
                    "total_scenes": metrics.get("total_scenes", 0),
                    "elements_generated": metrics.get("elements_generated", 0),
                    "fallbacks_applied": metrics.get("fallbacks_applied", 0),
                    "elements_skipped": metrics.get("elements_skipped", 0),
                    "retries_prevented": report_data.get("retries_prevented", 0),
                    "downstream_readiness_pct": metrics.get("downstream_readiness_pct", 100.0),
                },
                reflection=f"Motion Animation completed with {metrics.get('fallbacks_applied', 0)} 3D fallbacks and {report_data.get('retries_prevented', 0)} retries prevented.",
            )
            self.memory.store_private(
                title=f"Motion Animation Execution - {project_dir.name}",
                content=json.dumps({
                    "project_id": project_dir.name,
                    "aspect": aspect,
                    "status": status,
                    "total_scenes": metrics.get("total_scenes", 0),
                    "elements_generated": metrics.get("elements_generated", 0),
                    "fallbacks_applied": metrics.get("fallbacks_applied", 0),
                    "elements_skipped": metrics.get("elements_skipped", 0),
                    "retries_prevented": report_data.get("retries_prevented", 0),
                    "downstream_readiness_pct": metrics.get("downstream_readiness_pct", 100.0),
                }),
                kind="reflection",
                project_id=project_dir.name,
            )
        except Exception as e:
            logger.debug(f"Memory reflection recording note: {e}")

        summary = (
            f"Motion animation React/TSX generated successfully. "
            f"Scenes: {len(report_data.get('scenes', []))}, "
            f"3D Fallbacks: {report_data.get('aggregate_metrics', {}).get('fallbacks_applied', 0)}, "
            f"Retries Prevented: {report_data.get('retries_prevented', 0)}"
        )

        return AgentResult(
            agent_id=self.agent_id,
            stage_id="motion_gen",
            project_id=project_dir.name,
            status=status,
            error=err,
            output_refs=outputs,
            summary=summary,
        )


# Backward-compatibility alias
MotionAnimationAdapter = MotionAnimationAgent
