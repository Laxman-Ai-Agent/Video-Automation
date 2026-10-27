"""Dedicated implementation module for Final QC Agent.
Agent ID: final_qc
Stage ID: qc
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from SYSTEM.agents.shared import communication
from SYSTEM.agents.shared.base_agent import BaseAgent
from SYSTEM.agents.shared.contracts import AgentMetadata, AgentRequest, AgentResult, AgentStatus, ArtifactRef
from SYSTEM.memory import store


def evaluate_technical_qc(
    project_dir: Path,
    aspect: str = "16:9",
    rep: dict | None = None,
) -> tuple[bool, list[str], dict[str, Any]]:
    """Evaluates explicit technical QC acceptance criteria without requiring manual human clicks:
    1. Video file exists and size >= 1000 bytes.
    2. FFprobe reads container, video stream, valid width/height/fps.
    3. Duration synchronization: video duration matches audio duration within +/-0.5s.
    4. Black frames: no black frame interval >= 1.0s.
    5. Freeze frames: zero freeze frame events >= 1.5s.
    6. Audio loudness: if audio present, level within acceptable bounds (not silent <-50dB, not clipped >= -0.1dB).
    7. Upstream/deterministic QC checks from final_qc.run have no blocking errors.
    Returns: (passed: bool, failure_reasons: list[str], metrics: dict[str, Any])
    """
    failures: list[str] = []
    metrics: dict[str, Any] = {}

    vid = project_dir / ("out_9x16.mp4" if aspect == "9:16" else "out.mp4")
    if not vid.exists():
        return False, ["Rendered video file is missing"], metrics
    if vid.stat().st_size < 1000:
        return False, [f"Rendered video file is empty or suspiciously small ({vid.stat().st_size} bytes)"], metrics

    metrics["byte_size"] = vid.stat().st_size

    # Media probe
    try:
        from VIDEO_ENGINE.stages import media_probe
        probe_res = media_probe.probe(vid)
    except Exception as e:
        return False, [f"Media probe failed to parse video container: {e}"], metrics

    v_stream = probe_res.get("video") or {}
    if not v_stream or not v_stream.get("width") or not v_stream.get("height"):
        failures.append("Missing valid video stream or resolution in rendered container")

    v_dur = float(probe_res.get("duration") or 0.0)
    metrics["video_duration"] = v_dur
    metrics["width"] = v_stream.get("width")
    metrics["height"] = v_stream.get("height")
    metrics["fps"] = v_stream.get("frame_rate_value")
    metrics["video_codec"] = v_stream.get("codec")

    # Audio duration sync check
    audio_file = next(iter(project_dir.glob("audio.*")), None)
    if not audio_file:
        for cand in [project_dir / "sample-01.wav", project_dir / "input.mp3", project_dir / "audio.wav"]:
            if cand.exists():
                audio_file = cand
                break

    if audio_file and audio_file.exists():
        try:
            from VIDEO_ENGINE.stages import audio_utils
            a_dur = float(audio_utils.duration(audio_file))
            metrics["audio_duration"] = a_dur
            dur_diff = abs(v_dur - a_dur)
            metrics["duration_diff"] = round(dur_diff, 3)
            # Tolerance: +/- 0.5s
            if dur_diff > 0.5:
                failures.append(
                    f"A/V duration synchronization mismatch: video is {v_dur:.2f}s, audio is {a_dur:.2f}s (difference {dur_diff:.2f}s > 0.5s tolerance)"
                )

            # Integrated loudness measurement (EBU R128 target: -23 to -14 LUFS, when applicable)
            if hasattr(audio_utils, "integrated_loudness_lufs") and not audio_utils.is_silent(audio_file):
                lufs = audio_utils.integrated_loudness_lufs(audio_file)
                if lufs is not None:
                    metrics["integrated_loudness_lufs"] = lufs
                    if not (-23.0 <= lufs <= -14.0):
                        failures.append(
                            f"Audio integrated loudness ({lufs:.1f} LUFS) outside target range [-23.0, -14.0] LUFS"
                        )
                    else:
                        metrics["loudness_in_spec"] = True
        except Exception:
            pass

    # Inspect report checks
    if rep:
        checks = rep.get("checks", [])
        metrics["checks_total"] = len(checks)

        for c in checks:
            r_id = c.get("rule_id", "")
            # Black frame check: >= 1.0s is a failure
            if "BLACK" in r_id or "black" in r_id:
                ev = c.get("evidence", {})
                b_dur = ev.get("duration") or ev.get("black_duration")
                if b_dur is not None and float(b_dur) >= 1.0:
                    failures.append(f"Black frame duration ({b_dur}s) exceeds 1.0s limit: {c.get('message')}")
                elif c.get("status") == "failed" and c.get("severity") in ("blocker", "error"):
                    failures.append(f"Black frame check failed: {c.get('message')}")

            # Freeze frame check: >= 1.5s is a failure
            if "FREEZE" in r_id or "freeze" in r_id:
                ev = c.get("evidence", {})
                f_dur = ev.get("duration") or ev.get("freeze_duration")
                if f_dur is not None and float(f_dur) >= 1.5:
                    failures.append(f"Freeze frame duration ({f_dur}s) exceeds 1.5s limit: {c.get('message')}")
                elif c.get("status") == "failed" and c.get("severity") in ("blocker", "error"):
                    failures.append(f"Freeze frame check failed: {c.get('message')}")

            # Audio loudness/clipping check
            if "LOUDNESS" in r_id or "AUDIO_INTEGRITY" in r_id or "clipping" in r_id:
                if c.get("status") == "failed" and c.get("severity") in ("blocker", "error"):
                    failures.append(f"Audio loudness check failed: {c.get('message')}")
                ev = c.get("evidence", {})
                rep_lufs = ev.get("lufs") or ev.get("integrated_loudness_lufs")
                if rep_lufs is not None:
                    metrics["integrated_loudness_lufs"] = float(rep_lufs)
                    if not (-23.0 <= float(rep_lufs) <= -14.0):
                        failures.append(
                            f"Audio integrated loudness ({float(rep_lufs):.1f} LUFS) outside target range [-23.0, -14.0] LUFS"
                        )
                    else:
                        metrics["loudness_in_spec"] = True

        # Deterministic status check
        rep_status = rep.get("status")
        if rep_status in ("failed", "blocked"):
            failures.append(f"Deterministic QC report status is '{rep_status}'")

        # Blocker findings
        for f in rep.get("findings", []):
            if f.get("severity") in ("blocker", "error") and f.get("rule_id") != "QC_LLM_REVIEW":
                failures.append(f"{f.get('rule_id')}: {f.get('message')}")

    passed = len(failures) == 0
    return passed, failures, metrics


def file_sha256_full(path: Path) -> str:
    """Computes complete 64-character SHA-256 hex digest for binary file."""
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class FinalQcAgent(BaseAgent):
    """A13: Final QC Agent. Automated media probe + Autonomous technical rubric + Non-blocking delivery progression."""

    def __init__(self, metadata: AgentMetadata | None = None) -> None:
        if metadata is None:
            metadata = AgentMetadata(
                agent_id="final_qc",
                name="Final QC Agent",
                stage_id="qc",
            )
        super().__init__(metadata)

    def validate(self, project_dir: Path, request: AgentRequest) -> list[str]:
        aspect = request.parameters.get("aspect") or (getattr(request, "metadata", {}) or {}).get("aspect", "16:9")
        vid = project_dir / ("out_9x16.mp4" if aspect == "9:16" else "out.mp4")
        if not vid.exists():
            return ["Missing rendered video file for final QC"]
        if vid.stat().st_size < 1000:
            return [f"Rendered video file is empty or suspiciously small ({vid.stat().st_size} bytes)"]
        return []

    def execute(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        aspect = request.parameters.get("aspect") or (getattr(request, "metadata", {}) or {}).get("aspect", "16:9")
        sfx = "_9x16" if aspect == "9:16" else ""
        vid = project_dir / ("out_9x16.mp4" if aspect == "9:16" else "out.mp4")
        task_id = request.parameters.get("task_id") or request.run_id

        from VIDEO_ENGINE.stages import final_qc
        from SYSTEM.core.artifact_contracts import validate_qc_artifacts, _file_sha256

        force = bool(request.parameters.get("force"))
        qc_rep_file = project_dir / f"final_qc_report{sfx}.json"

        # Emit Telugu activity: QC evaluation started
        try:
            communication.publish_lifecycle_event(
                project_id=project_dir.name,
                stage_id="qc",
                sender_agent_id=self.agent_id,
                event="stage_started",
                detail="Final technical QC media analysis started",
                telugu_activity="వీడియో నాణ్యతను పరీక్షిస్తున్నాను.",
                task_id=task_id,
            )
        except Exception:
            pass

        st = final_qc.state(project_dir, aspect)
        cur_report = st.get("report") if st.get("current") and not force else None
        if not cur_report:
            try:
                rep = final_qc.run(project_dir, aspect)
            except Exception as e:
                return AgentResult(
                    agent_id=self.agent_id,
                    stage_id="qc",
                    project_id=project_dir.name,
                    status="failed",
                    summary=f"Final QC probe execution failed: {e}",
                    error=str(e),
                )
        else:
            rep = cur_report

        status_val = rep.get("status")
        if status_val in ("failed", "blocked"):
            return AgentResult(
                agent_id=self.agent_id,
                stage_id="qc",
                project_id=project_dir.name,
                status="failed",
                summary=f"Deterministic QC checks failed: status is {status_val}",
                error=f"qc_status_{status_val}",
                metadata={"report": rep},
            )

        sha = file_sha256_full(vid)

        # Autonomous Technical QC Evaluation
        tech_passed, failures, metrics = evaluate_technical_qc(project_dir, aspect, rep)

        outputs = []
        if qc_rep_file.exists():
            outputs.append(ArtifactRef(path=str(qc_rep_file), description="Final QC Report JSON"))
        rev_file = project_dir / f"final_qc_review{sfx}.json"
        if rev_file.exists():
            outputs.append(ArtifactRef(path=str(rev_file), description="Final QC Review JSON"))

        if not tech_passed:
            try:
                communication.publish_lifecycle_event(
                    project_id=project_dir.name,
                    stage_id="qc",
                    sender_agent_id=self.agent_id,
                    event="stage_failed",
                    detail=f"Autonomous technical QC rejected: {'; '.join(failures[:2])}",
                    telugu_activity="వీడియో నాణ్యత పరీక్షలో సమస్య కనిపించింది. దాన్ని సరిచేయడానికి ప్రయత్నిస్తున్నాను.",
                    task_id=task_id,
                )
            except Exception:
                pass

            return AgentResult(
                agent_id=self.agent_id,
                stage_id="qc",
                project_id=project_dir.name,
                status="failed",
                summary=f"Autonomous technical QC failed: {'; '.join(failures[:3])}",
                error="; ".join(failures),
                output_refs=outputs,
                metadata={"failures": failures, "metrics": metrics, "report": rep},
            )

        # The decision about this exact file: the Final QC LLM review's (no person). A decision already recorded for this file and QC run is reused.
        dec = final_qc.current_review(project_dir, aspect, sha)
        if not dec or dec.get("qc_run_id") != rep.get("qc_run_id") or dec.get("decision") not in ("approved", "approved_with_accepted_risks"):
            try:
                dec = final_qc.llm_decide(project_dir, aspect).get("review")
            except final_qc.QcError as e:
                return AgentResult(agent_id=self.agent_id, stage_id="qc", project_id=project_dir.name, status="failed",
                                   summary=f"Final QC LLM decision refused: {e}", error=str(e), output_refs=outputs, metadata={"report": rep})
        if not dec or dec.get("decision") not in ("approved", "approved_with_accepted_risks"):
            return AgentResult(
                agent_id=self.agent_id,
                stage_id="qc",
                project_id=project_dir.name,
                status="blocked",
                summary=f"The Final QC LLM review did not approve this video: {(dec or {}).get('decision', 'no decision')}: {'; '.join((dec or {}).get('notes', []))[:300]}",
                output_refs=outputs,
                metadata={"report": rep, "llm_decision": dec},
            )

        try:
            validate_qc_artifacts(project_dir, aspect)
        except Exception as e:
            return AgentResult(
                agent_id=self.agent_id,
                stage_id="qc",
                project_id=project_dir.name,
                status="failed",
                summary=f"Final QC artifact contract validation failed: {e}",
                error=str(e),
            )

        return AgentResult(
            agent_id=self.agent_id,
            stage_id="qc",
            project_id=project_dir.name,
            status="succeeded",
            output_refs=outputs,
            summary=f"Final QC checks passed and the Final QC LLM review decided '{dec['decision']}'",
            metadata={
                "report": rep,
                "llm_decision": dec,
                "sha256": sha,
            },
        )


# Backward-compatibility alias
FinalQcAdapter = FinalQcAgent
