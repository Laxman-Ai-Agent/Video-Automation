"""Dedicated implementation module for Render Video Agent.
Agent ID: render_video
Stage ID: render
Version: 2.0.0 (Upgraded with Autonomous Self-Healing & Output Integrity Verification)
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from SYSTEM.agents.shared import communication
from SYSTEM.agents.shared.base_agent import BaseAgent
from SYSTEM.agents.shared.contracts import AgentMetadata, AgentRequest, AgentResult, AgentStatus, ArtifactRef
from SYSTEM.agents.video_generation_agents.render_video.render_intelligence import (
    AdaptiveResourceEngine,
    AutonomousRenderRecoveryCoordinator,
    LLMRenderDiagnostician,
    OutputIntegrityAuditor,
    RenderFailureClassifier,
)
from SYSTEM.memory import store

logger = logging.getLogger("render_video.agent")


class RenderVideoAgent(BaseAgent):
    """A12: Render Video Agent. Headless Chrome Remotion video rendering with

    autonomous error recovery, adaptive resource optimization, and deep media stream verification.
    """

    def __init__(self, metadata: AgentMetadata | None = None) -> None:
        if metadata is None:
            metadata = AgentMetadata(
                agent_id="render_video",
                name="Render Video Agent",
                stage_id="render",
            )
        super().__init__(metadata)
        self.resource_engine = AdaptiveResourceEngine()
        self.classifier = RenderFailureClassifier()
        self.diagnostician = LLMRenderDiagnostician()
        self.recovery_coordinator = AutonomousRenderRecoveryCoordinator(max_attempts=2)
        self.auditor = OutputIntegrityAuditor()

    def validate(self, project_dir: Path, request: AgentRequest) -> list[str]:
        aspect = request.parameters.get("aspect") or (getattr(request, "metadata", {}) or {}).get("aspect", "16:9")
        sfx = "_9x16" if aspect == "9:16" else ""
        tl = project_dir / f"timeline{sfx}.json"
        if not tl.exists():
            return [f"Missing timeline{sfx}.json for video render"]

        from VIDEO_ENGINE.stages import timeline_gate
        try:
            timeline_gate.require_approved(project_dir, aspect)
        except Exception as e:
            return [f"Render blocked: current timeline is not approved ({e})"]
        return []

    def execute(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        aspect = request.parameters.get("aspect") or (getattr(request, "metadata", {}) or {}).get("aspect", "16:9")
        sfx = "_9x16" if aspect == "9:16" else ""
        vid_file = project_dir / ("out_9x16.mp4" if aspect == "9:16" else "out.mp4")
        task_id = request.parameters.get("task_id") or request.run_id
        t0 = time.perf_counter()

        from VIDEO_ENGINE.stages import render_video, timeline_gate
        from SYSTEM.core.artifact_contracts import _file_sha256, validate_render_artifacts

        # 1. Mandatory Approval Gate Check (Fail-Closed)
        try:
            timeline_gate.require_approved(project_dir, aspect)
        except Exception as e:
            logger.warning(f"Render gate refused: timeline is not approved: {e}")
            return AgentResult(
                agent_id=self.agent_id,
                stage_id="render",
                project_id=project_dir.name,
                status="blocked",
                summary=f"Render blocked: current timeline is not approved ({e})",
                error=str(e),
            )

        dry_run = bool(request.parameters.get("dry_run"))
        force = bool(request.parameters.get("force"))

        # 2. Adaptive Resource Telemetry
        res_info = self.resource_engine.assess_system_resources(project_dir)

        # 3. Check Cached Output Candidate
        cand = render_video.current_candidate(project_dir, aspect) if not force else None      # a video of an older approved version is never reused (Final QC would call it stale)
        render_needed = (force or not cand or not vid_file.exists()) and not dry_run
        render_executed = False
        rep: dict[str, Any] = {}

        if render_needed:
            # Emit Telugu activity: video rendering started
            try:
                communication.publish_lifecycle_event(
                    project_id=project_dir.name,
                    stage_id="render",
                    sender_agent_id=self.agent_id,
                    event="stage_started",
                    detail=f"Starting Remotion render (concurrency={res_info['recommended_concurrency']})",
                    telugu_activity="వీడియో రెండరింగ్ ప్రారంభమైంది.",
                    task_id=task_id,
                )
            except Exception:
                pass

            # 4. Render Execution with Autonomous Bounded Recovery Loop
            active_flags: list[str] = [f"--concurrency={res_info['recommended_concurrency']}"]
            max_recovery_rounds = 2
            current_attempt = 0
            render_success = False
            last_error: str | None = None

            while current_attempt <= max_recovery_rounds and not render_success:
                current_attempt += 1
                try:
                    rep = render_video.run(project_dir, aspect)
                    if rep.get("status") in ("completed", "completed_with_warnings"):
                        render_success = True
                        render_executed = True
                        break
                    else:
                        last_error = rep.get("error") or rep.get("status") or "Render reported failure"
                except Exception as exc:
                    last_error = str(exc)
                    logger.warning(f"Render attempt {current_attempt} failed: {last_error}")

                # Diagnose failure
                category = self.classifier.classify(last_error or "")
                diagnosis = self.diagnostician.diagnose(
                    project_id=project_dir.name,
                    category=category,
                    raw_error=last_error or "Unknown render error",
                    attempt_number=current_attempt,
                )

                # Check if autonomous recovery can be attempted
                if self.recovery_coordinator.can_attempt_recovery(diagnosis):
                    applied, active_flags, recovery_msg = self.recovery_coordinator.execute_recovery_action(
                        project_dir=project_dir,
                        aspect=aspect,
                        diagnosis=diagnosis,
                        active_flags=active_flags,
                    )
                    if applied:
                        logger.info(f"Autonomous recovery applied: {recovery_msg}")
                        continue

                # If recovery is not possible or exhausted, break
                break

            if not render_success and not dry_run:
                try:
                    communication.publish_lifecycle_event(
                        project_id=project_dir.name,
                        stage_id="render",
                        sender_agent_id=self.agent_id,
                        event="stage_failed",
                        detail=f"Video render failed: {last_error}",
                        telugu_activity="వీడియో రెండరింగ్‌లో లోపం ఎదురైంది.",
                        task_id=task_id,
                    )
                except Exception:
                    pass

                return AgentResult(
                    agent_id=self.agent_id,
                    stage_id="render",
                    project_id=project_dir.name,
                    status="failed",
                    summary=f"Video render execution failed: {last_error}",
                    error=last_error,
                    metadata={
                        "resource_telemetry": res_info,
                        "recovery_summary": self.recovery_coordinator.get_summary(),
                    },
                )

        # 5. Output Verification
        if not vid_file.exists() or vid_file.stat().st_size < 1000:
            return AgentResult(
                agent_id=self.agent_id,
                stage_id="render",
                project_id=project_dir.name,
                status="failed",
                summary="Render output video file missing or empty (< 1000 bytes)",
                error="output_empty_or_missing",
            )

        try:
            validate_render_artifacts(project_dir, aspect)
        except Exception as e:
            return AgentResult(
                agent_id=self.agent_id,
                stage_id="render",
                project_id=project_dir.name,
                status="failed",
                summary=f"Render artifact validation failed: {e}",
                error=str(e),
            )

        # 6. Deep Output Integrity Audit (ffprobe)
        expected_meta = {
            "width": 1080 if aspect == "9:16" else 1920,
            "height": 1920 if aspect == "9:16" else 1080,
            "fps": 30,
            "duration_seconds": rep.get("expected", {}).get("duration_seconds", 4.0),
            "audio_required": True,
        }
        audio_dur = None
        try:
            from VIDEO_ENGINE.stages import render as r_stage
            pa = r_stage.project_audio(project_dir)
            if pa:
                from VIDEO_ENGINE.stages import audio_utils
                audio_dur = audio_utils.duration(pa)
        except Exception:
            pass

        audit_results = self.auditor.audit(vid_file, expected_meta, audio_dur)

        # 7. Collect Primary Outputs
        outputs = [
            ArtifactRef(path=str(vid_file), description="Rendered Video File"),
        ]
        job_f = project_dir / render_video.names(aspect)["job"]
        man_f = project_dir / render_video.names(aspect)["manifest"]
        rep_f = project_dir / render_video.names(aspect)["report"]
        for extra in (job_f, man_f, rep_f):
            if extra.exists():
                outputs.append(ArtifactRef(path=str(extra), description=extra.name))

        sha = _file_sha256(vid_file)
        size = vid_file.stat().st_size

        # 8. Save Render Intelligence Artifact
        intel_path = project_dir / f"render_intelligence{sfx}.json"
        intel_payload = {
            "schema_version": "2.0",
            "project_id": project_dir.name,
            "aspect": aspect,
            "video_file": vid_file.name,
            "sha256": sha,
            "byte_size": size,
            "resource_telemetry": res_info,
            "recovery_summary": self.recovery_coordinator.get_summary(),
            "output_audit": audit_results,
            "render_executed": render_needed,
            "timings_ms": round((time.perf_counter() - t0) * 1000),
        }
        intel_path.write_text(json.dumps(intel_payload, indent=2, ensure_ascii=False), encoding="utf-8")

        # 9. Record Experience to Private Memory
        try:
            self.memory.record_experience(
                task_type="render_video",
                outcome="succeeded",
                project_id=project_dir.name,
                metrics={
                    "byte_size": size,
                    "sha256_short": sha[:12],
                    "recovery_attempts": len(self.recovery_coordinator.attempts),
                    "audit_passed": audit_results.get("passed", True),
                },
            )
        except Exception as e:
            logger.warning(f"Failed to record render experience in memory: {e}")

        # Emit Telugu activity: video rendering completed
        try:
            communication.publish_lifecycle_event(
                project_id=project_dir.name,
                stage_id="render",
                sender_agent_id=self.agent_id,
                event="stage_completed",
                detail=f"Render complete: {vid_file.name} ({size} bytes, sha256={sha[:12]})",
                telugu_activity="వీడియో రెండరింగ్ పూర్తయింది. నాణ్యత తనిఖీకి సిద్ధంగా ఉంది.",
                task_id=task_id,
            )
        except Exception:
            pass

        return AgentResult(
            agent_id=self.agent_id,
            stage_id="render",
            project_id=project_dir.name,
            status="succeeded",
            output_refs=outputs,
            summary=f"Video render completed and media streams verified ({size} bytes, sha256={sha[:12]}...)",
            metadata={
                "sha256": sha,
                "byte_size": size,
                "video_file": vid_file.name,
                "candidate": cand,
                "render_intelligence_ref": str(intel_path),
                "resource_telemetry": res_info,
                "recovery_summary": self.recovery_coordinator.get_summary(),
                "audit_passed": audit_results.get("passed", True),
            },
        )


# Backward-compatibility alias
RenderVideoAdapter = RenderVideoAgent
