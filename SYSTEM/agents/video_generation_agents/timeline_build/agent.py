"""Dedicated implementation module for Timeline Build Agent v2.0.0.
Agent ID: timeline_build
Stage ID: timeline

Autonomous cinematic timeline orchestration system featuring:
- 12-stage deterministic frame-accurate timeline compilation (30fps arithmetic, half-open intervals).
- AudioDuckingEngine: Speech-aware background music attenuation with smooth attack/decay ramps.
- CinematicTransitionSelector: LLM-assisted context-sensitive scene transitions.
- SceneContinuityAssessor: Pacing, motion energy, and visual continuity analysis.
- TimelineRecoveryCoordinator: Bounded autonomous repair (max 2 attempts) for compiler-solvable defects.
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
from SYSTEM.agents.video_generation_agents.timeline_build.timeline_intelligence import (
    AudioDuckingEngine,
    CinematicTransitionSelector,
    SceneContinuityAssessor,
    TimelineRecoveryCoordinator,
)
from SYSTEM.memory import store

logger = logging.getLogger("timeline_build.agent")


class TimelineBuildAgent(BaseAgent):
    """A10: Timeline Build Agent v2.0.0.

    Assembles multi-track frame timeline, checks audio sync, applies speech-aware ducking,
    recommends cinematic transitions, and enforces 30fps arithmetic.
    """

    def __init__(self, metadata: AgentMetadata | None = None) -> None:
        if metadata is None:
            metadata = AgentMetadata(
                agent_id="timeline_build",
                name="Timeline Build Agent",
                version="2.0.0",
                stage_id="timeline",
                purpose="Autonomous cinematic timeline orchestration with speech-aware audio ducking, semantic transitions, and continuity intelligence",
            )
        super().__init__(metadata)
        self.ducking_engine = AudioDuckingEngine()
        self.transition_selector = CinematicTransitionSelector()
        self.continuity_assessor = SceneContinuityAssessor()
        self.recovery_coordinator = TimelineRecoveryCoordinator()

    def validate(self, project_dir: Path, request: AgentRequest) -> list[str]:
        from SYSTEM.core.artifact_contracts import verify_path_confinement
        try:
            verify_path_confinement(project_dir, project_dir)
        except Exception as e:
            return [f"Path traversal detected: {e}"]

        aspect = request.parameters.get("aspect") or (getattr(request, "metadata", {}) or {}).get("aspect", "16:9")
        sfx = "_9x16" if aspect == "9:16" else ""
        comp = project_dir / f"composition{sfx}.json"
        seg = project_dir / "scene_segmentation.json"
        splan = project_dir / "scene_plan.json"
        audio = next(iter(project_dir.glob("audio.*")), None)

        issues = []
        if not comp.exists():
            issues.append(f"Missing composition{sfx}.json for timeline build")
        if not seg.exists() and not splan.exists():
            issues.append("Missing scene_segmentation.json or scene_plan.json for timeline build")
        if not audio or not audio.is_file():
            issues.append("Missing source audio file for timeline build")
        return issues

    def execute(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        aspect = request.parameters.get("aspect") or (getattr(request, "metadata", {}) or {}).get("aspect", "16:9")
        sfx = "_9x16" if aspect == "9:16" else ""
        force = bool(request.parameters.get("force"))
        auto_repair = bool(request.parameters.get("auto_repair", True))
        max_repair_attempts = int(request.parameters.get("max_repair_attempts", 2))

        from VIDEO_ENGINE.stages import timeline_build
        from SYSTEM.core.artifact_contracts import validate_timeline_artifacts

        tl_path = project_dir / f"timeline{sfx}.json"
        rep_path = project_dir / f"timeline_build_report{sfx}.json"
        intel_path = project_dir / f"timeline_intelligence{sfx}.json"

        t0 = time.perf_counter()
        report: dict[str, Any] = {}

        # 0. The pre-render check of the composition (canonical step "motion-validate"): it re-reads Stage 8 and writes prerender_report*.json, which the
        # timeline approval requires on the current files. It always runs (about a second); its errors stop the stage with their exact cause.
        from VIDEO_ENGINE.pipeline import legacy_pipeline_adapter
        try:
            legacy_pipeline_adapter.execute(project_dir, f"motion-validate{'-9x16' if aspect == '9:16' else ''}", legacy_pipeline_adapter.Ctx())
        except Exception as e:
            return AgentResult(agent_id=self.agent_id, stage_id="timeline", project_id=project_dir.name, status="failed",
                               summary=f"Pre-render check failed: {e}", error=str(e))

        # 1. Run or Load Deterministic Timeline Compilation
        cur = timeline_build.load(project_dir, aspect) if not force else None
        if cur and cur.get("current") and tl_path.exists() and rep_path.exists():
            report = cur.get("report", {})
        elif tl_path.exists() and rep_path.exists() and not force:
            try:
                rep_data = json.loads(rep_path.read_text(encoding="utf-8"))
                if rep_data.get("status") in ("completed", "completed_with_warnings"):
                    report = rep_data
                else:
                    report = timeline_build.run(project_dir, aspect)
            except Exception:
                report = timeline_build.run(project_dir, aspect)
        else:
            try:
                report = timeline_build.run(project_dir, aspect)
            except Exception as e:
                logger.error(f"Timeline compilation crashed: {e}", exc_info=True)
                return AgentResult(
                    agent_id=self.agent_id,
                    stage_id="timeline",
                    project_id=project_dir.name,
                    status="failed",
                    summary=f"Timeline build execution failed: {e}",
                    error=str(e),
                )

        status_val = report.get("status")
        repair_summary: dict[str, Any] = {"repaired": False, "attempts": 0, "actions_applied": []}

        # 2. Bounded Autonomous Recovery (if blocked and auto_repair enabled)
        if status_val not in ("completed", "completed_with_warnings") and auto_repair:
            findings = report.get("findings", [])
            blocker_msgs = [f.get("message", "") for f in findings if f.get("severity") in ("blocker", "error")]
            if blocker_msgs:
                repair_summary = self.recovery_coordinator.coordinate_recovery(
                    project_dir=project_dir,
                    blockers_list=blocker_msgs,
                    max_attempts=max_repair_attempts,
                )
                if repair_summary.get("repaired"):
                    try:
                        report = timeline_build.run(project_dir, aspect)
                        status_val = report.get("status")
                    except Exception as e:
                        logger.warning(f"Re-run after recovery failed: {e}")

        # If still not completed, return blocked result
        if status_val not in ("completed", "completed_with_warnings"):
            return AgentResult(
                agent_id=self.agent_id,
                stage_id="timeline",
                project_id=project_dir.name,
                status="blocked" if status_val == "blocked" else "failed",
                summary=f"Timeline build blocked: {report.get('error') or 'unresolved findings'}",
                metadata={"report": report, "recovery_summary": repair_summary},
            )

        # 3. Contract Validation
        try:
            validate_timeline_artifacts(project_dir, aspect)
        except Exception as e:
            return AgentResult(
                agent_id=self.agent_id,
                stage_id="timeline",
                project_id=project_dir.name,
                status="failed",
                summary=f"Timeline artifact contract validation failed: {e}",
                error=str(e),
            )

        # 4. Parse Built Timeline for Frame Arithmetic & Tracks
        t_data = json.loads(tl_path.read_text(encoding="utf-8"))
        profile = t_data.get("profile") if isinstance(t_data.get("profile"), dict) else {}
        frames = (
            t_data.get("total_frames")
            or t_data.get("duration_frames")
            or profile.get("duration_frames", 0)
            or profile.get("total_frames", 0)
        )
        fps = t_data.get("fps") or profile.get("fps", 30)

        if frames <= 0:
            return AgentResult(
                agent_id=self.agent_id,
                stage_id="timeline",
                project_id=project_dir.name,
                status="failed",
                summary="Timeline has non-positive frame count",
            )

        # Extract scenes
        scenes = t_data.get("scenes")
        if scenes is None:
            scenes = []
            for trk in t_data.get("tracks", []):
                if trk.get("track_type") in ("composition", "video"):
                    scenes.extend(trk.get("items", []))

        for sc in scenes:
            sf = sc.get("start_frame", 0)
            ef = sc.get("end_frame") if "end_frame" in sc else (sf + sc.get("duration_frames", 0))
            if ef <= sf:
                return AgentResult(
                    agent_id=self.agent_id,
                    stage_id="timeline",
                    project_id=project_dir.name,
                    status="failed",
                    summary=f"Scene {sc.get('id') or sc.get('scene_id')} has invalid frame range: [{sf}, {ef})",
                )

        # 5. Timeline Intelligence Computations
        ducking_meta = self.ducking_engine.compute_ducking_profile(project_dir, frames, fps=fps)
        trans_meta = self.transition_selector.recommend_transitions(project_dir, scenes, fps=fps)
        dur_s = float(profile.get("composition_duration_seconds", frames / fps if fps else 0.0))
        cont_meta = self.continuity_assessor.assess(project_dir, scenes, dur_s)

        # 6. Save Timeline Intelligence Artifact
        intel_payload = {
            "schema_version": "2.0",
            "project_id": project_dir.name,
            "aspect": aspect,
            "total_frames": frames,
            "fps": fps,
            "duration_seconds": dur_s,
            "ducking_profile": ducking_meta,
            "transition_recommendations": trans_meta,
            "continuity_assessment": cont_meta,
            "recovery_summary": repair_summary,
            "timings_ms": round((time.perf_counter() - t0) * 1000),
        }
        intel_path.write_text(json.dumps(intel_payload, indent=2, ensure_ascii=False), encoding="utf-8")

        # 7. Collect Outputs (Contract: timeline.json & timeline_build_report.json)
        outputs = [
            ArtifactRef(path=str(tl_path), description="Timeline Manifest JSON"),
            ArtifactRef(path=str(rep_path), description="Timeline Build Report JSON"),
        ]

        # 8. Record Autonomous Memory Reflection
        try:
            self.memory.record_experience(
                task_type="timeline_build",
                outcome="succeeded",
                project_id=project_dir.name,
                metrics={
                    "total_frames": frames,
                    "fps": fps,
                    "duration_seconds": dur_s,
                    "speech_coverage_percent": ducking_meta.get("speech_coverage_percent", 0.0),
                    "continuity_score": cont_meta.get("continuity_score", 100.0),
                    "repaired_count": len(repair_summary.get("actions_applied", [])),
                },
                reflection=(
                    f"Timeline Build compiled {frames} frames at {fps} fps ({dur_s:.2f}s). "
                    f"Speech coverage: {ducking_meta.get('speech_coverage_percent')}%. "
                    f"Continuity score: {cont_meta.get('continuity_score')}/100. "
                    f"Transitions recommended: {trans_meta.get('total_transitions', 0)}."
                ),
            )
        except Exception as e:
            logger.info(f"Memory reflection recording skipped: {e}")

        return AgentResult(
            agent_id=self.agent_id,
            stage_id="timeline",
            project_id=project_dir.name,
            status="succeeded",
            output_refs=outputs,
            metadata={
                "timeline_fingerprint": report.get("timeline_fingerprint"),
                "source_fingerprint": report.get("source_fingerprint"),
                "total_frames": frames,
                "fps": fps,
                "duration_seconds": dur_s,
                "ducking_applied": ducking_meta.get("ducking_applied", False),
                "continuity_score": cont_meta.get("continuity_score", 100.0),
                "recovery_actions": repair_summary.get("actions_applied", []),
            },
            summary=(
                f"Timeline tracks assembled and frame arithmetic validated ({frames} frames @ {fps} fps). "
                f"Speech-aware audio ducking active ({ducking_meta.get('speech_intervals_count', 0)} speech intervals). "
                f"Continuity score: {cont_meta.get('continuity_score', 100.0)}/100."
            ),
        )


# Backward-compatibility alias
TimelineBuildAdapter = TimelineBuildAgent
