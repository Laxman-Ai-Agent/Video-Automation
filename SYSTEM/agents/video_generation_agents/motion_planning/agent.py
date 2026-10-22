"""Dedicated implementation module for Motion Planning Agent.
Agent ID: motion_planning
Stage ID: motion_plan
Version: 2.0.0
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from SYSTEM.agents.shared.base_agent import BaseAgent
from SYSTEM.agents.shared.contracts import AgentMetadata, AgentRequest, AgentResult, AgentStatus, ArtifactRef
from SYSTEM.agents.video_generation_agents.motion_planning.motion_intelligence import (
    MotionIntelligenceEngine,
    MotionIntelligenceResult,
)
from SYSTEM.memory import store

logger = logging.getLogger("motion_planning")


class MotionPlanningAgent(BaseAgent):
    """A06: Motion Planning Agent (v2.0.0 Complete LLM Intelligence Upgrade).
    Transforms visual plans and scene segmentation into cinematic, audio-aware,
    temporally synchronized, collision-safe motion plans.
    """

    def __init__(self, metadata: AgentMetadata | None = None) -> None:
        if metadata is None:
            metadata = AgentMetadata(
                agent_id="motion_planning",
                name="Motion Planning Agent",
                version="2.0.0",
                status=AgentStatus.IMPLEMENTED,
                stage_id="motion_plan",
                capabilities=[
                    "kinetic-typography-math",
                    "spring-curve-solver",
                    "transition-scheduling",
                    "cinematic-camera-choreography",
                    "audio-reactive-intelligence",
                    "collision-resolution",
                ],
            )
        super().__init__(metadata)
        self.intelligence_engine = MotionIntelligenceEngine()

    def validate(self, project_dir: Path, request: AgentRequest) -> list[str]:
        vf = project_dir / "visual_planning.json"
        spf = project_dir / "scene_plan.json"
        ssf = project_dir / "scene_segmentation.json"
        if not (vf.exists() or spf.exists() or ssf.exists()):
            return ["Missing visual planning, scene plan, or segmentation files for motion planning"]
        return []

    def _load_input_scenes(self, project_dir: Path) -> list[dict[str, Any]]:
        """Extracts scene records from visual_planning.json, scene_plan.json, or scene_segmentation.json."""
        # 1. Try visual_planning.json
        vf = project_dir / "visual_planning.json"
        if vf.exists():
            try:
                data = json.loads(vf.read_text(encoding="utf-8"))
                scenes = data.get("scenes", [])
                if scenes:
                    return scenes
            except Exception:
                pass

        # 2. Try scene_plan.json
        spf = project_dir / "scene_plan.json"
        if spf.exists():
            try:
                data = json.loads(spf.read_text(encoding="utf-8"))
                scenes = data.get("scenes", [])
                if scenes:
                    return scenes
            except Exception:
                pass

        # 3. Try scene_segmentation.json
        ssf = project_dir / "scene_segmentation.json"
        if ssf.exists():
            try:
                data = json.loads(ssf.read_text(encoding="utf-8"))
                scenes = data.get("scenes", [])
                if scenes:
                    return scenes
            except Exception:
                pass

        return []

    def execute(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        aspect = getattr(request, "parameters", {}).get("aspect", "16:9")
        sfx = "_9x16" if aspect == "9:16" else ""
        mp = project_dir / f"motion_plan{sfx}.json"
        force = bool(getattr(request, "parameters", {}).get("force"))

        # 1. Load input scenes
        scenes = self._load_input_scenes(project_dir)
        if not scenes:
            return AgentResult(
                agent_id=self.agent_id,
                stage_id="motion_plan",
                project_id=project_dir.name,
                status="blocked",
                summary="No scenes found in visual_planning.json, scene_plan.json, or scene_segmentation.json",
            )

        # 2. Execute Cinematic Motion Intelligence Engine
        intel_result: MotionIntelligenceResult = self.intelligence_engine.plan_motion_intelligence(
            project_dir=project_dir,
            scenes=scenes,
            aspect=aspect,
        )

        # 3. Generate or enrich motion_plan.json: also when the existing plan was made from older inputs, else the run "completes" with a stale plan
        from VIDEO_ENGINE.pipeline import legacy_pipeline_adapter
        from VIDEO_ENGINE.stages import motion_branch
        step = motion_branch.names(aspect)[0]
        stale = mp.exists() and not legacy_pipeline_adapter.is_fresh(project_dir, step)
        try:
            from VIDEO_ENGINE.stages import visual_planning
            has_handoff = bool(visual_planning.handoff(project_dir).get("scenes"))
        except Exception:
            has_handoff = False
        if (not mp.exists() or force or stale) and has_handoff:
            # A real Visual Plan: the canonical step builds the plan with the motion library's deterministic selector (registry presets and transitions,
            # the Visual Plan's timeline windows and on-screen texts), links it to the Visual Plan, validates it, runs the LLM review and records it as
            # current. An invalid plan raises here and the stage fails with the reason instead of "completing".
            try:
                legacy_pipeline_adapter.execute(project_dir, step, legacy_pipeline_adapter.Ctx())
            except Exception as e:
                logger.error("Motion planning execution error: %s", e)
                return AgentResult(
                    agent_id=self.agent_id,
                    stage_id="motion_plan",
                    project_id=project_dir.name,
                    status="failed",
                    summary=f"Motion planning build failed: {e}",
                )
            sfx_ = "_9x16" if aspect == "9:16" else ""
            (project_dir / f"motion_intelligence{sfx_}.json").write_text(json.dumps(intel_result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")   # the pacing analysis, kept beside the plan
        elif not mp.exists() or force or stale:
            try:
                # Compile via Intelligence Engine
                self.intelligence_engine.compile_motion_plan_json(
                    project_dir=project_dir,
                    scenes=scenes,
                    aspect=aspect,
                    intelligence=intel_result,
                )

                # Execute deterministic checks and validation build
                try:
                    from VIDEO_ENGINE.stages import motion_planning
                    checked = motion_planning.build(project_dir, aspect)
                    motion_planning.save(project_dir, aspect, checked)
                    legacy_pipeline_adapter.record_fresh(project_dir, step)        # the pipeline view now sees this plan as current
                except Exception as build_err:
                    logger.debug("Deterministic motion_planning.build skipped/notice: %s", build_err)

                # Optional LLM review gate
                try:
                    from SYSTEM.policies import llm_review
                    llm_review.run_stage_llm_review(project_dir, "motion_plan", aspect)
                except Exception as rev_err:
                    logger.debug("Motion planning LLM review skipped/notice: %s", rev_err)

            except Exception as e:
                logger.error("Motion planning execution error: %s", e)
                return AgentResult(
                    agent_id=self.agent_id,
                    stage_id="motion_plan",
                    project_id=project_dir.name,
                    status="failed",
                    summary=f"Motion planning build failed: {e}",
                )

        # 4. Record self-learning reflection in agent memory
        try:
            if hasattr(self, "memory") and self.memory is not None:
                exp_payload = {
                    "task_type": "motion_planning",
                    "task_id": request.correlation_id or f"req-mp-{int(time.time())}",
                    "project_id": project_dir.name,
                    "outcome": "succeeded",
                    "metrics": {
                        "scenes_count": len(intel_result.scene_strategies),
                        "variety_count": intel_result.continuity_report.get("variety_count", 1),
                        "average_wpm": intel_result.audio_telemetry.get("global", {}).get("average_wpm", 0.0),
                        "latency_ms": intel_result.llm_metadata.get("latency_ms", 0),
                    },
                    "reflection": {
                        "status": "success",
                        "summary": f"Motion planning completed for {len(scenes)} scenes with {intel_result.continuity_report.get('variety_count', 1)} motion strategies.",
                        "takeaway": f"Pacing classified as {intel_result.audio_telemetry.get('global', {}).get('pace_tier', 'moderate')}; continuity repairs: {intel_result.continuity_report.get('repairs_count', 0)}.",
                    },
                    "confidence": 0.95 if intel_result.status == "completed" else 0.85,
                }
                self.memory.add_experience(exp_payload)
        except Exception as e:
            logger.debug("Memory reflection recording skipped: %s", e)

        # 5. Assemble outputs
        outputs: list[ArtifactRef] = []
        if mp.exists():
            outputs.append(ArtifactRef(path=str(mp), description="Motion Plan JSON"))
        planning_json = project_dir / f"motion_planning{sfx}.json"
        if planning_json.exists():
            outputs.append(ArtifactRef(path=str(planning_json), description="Motion Planning Specification JSON"))
        intel_json = project_dir / f"motion_intelligence{sfx}.json"
        if intel_json.exists():
            outputs.append(ArtifactRef(path=str(intel_json), description="Cinematic Motion Intelligence Specification JSON"))

        metadata = {
            "scenes_count": len(intel_result.scene_strategies),
            "intelligence_status": intel_result.status,
            "llm_used": intel_result.llm_metadata.get("llm_used", False),
            "average_wpm": intel_result.audio_telemetry.get("global", {}).get("average_wpm", 0.0),
            "strategies_variety": intel_result.continuity_report.get("variety_count", 1),
            "repairs_count": intel_result.continuity_report.get("repairs_count", 0),
            "aspect": aspect,
        }

        return AgentResult(
            agent_id=self.agent_id,
            stage_id="motion_plan",
            project_id=project_dir.name,
            status="succeeded" if mp.exists() else "failed",
            output_refs=outputs,
            summary="Motion typography and element placements planned",
            metadata=metadata,
        )


# Backward-compatibility alias
MotionPlanningAdapter = MotionPlanningAgent
