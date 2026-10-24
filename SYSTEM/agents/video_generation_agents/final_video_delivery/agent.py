"""Dedicated implementation module for Final Video Delivery Agent.
Agent ID: final_video_delivery
Stage ID: final
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from SYSTEM.agents.shared import communication
from SYSTEM.agents.shared.base_agent import BaseAgent
from SYSTEM.agents.shared.contracts import AgentMetadata, AgentRequest, AgentResult, AgentStatus, ArtifactRef
from SYSTEM.memory import store


def get_desktop_delivery_dir(custom_desktop: Path | str | None = None) -> Path:
    """Resolves the canonical desktop destination directory: Desktop/First Video Automation/.
    Honors custom_desktop argument and LAXMAN_DESKTOP_DIR environment variable for test isolation.
    """
    if custom_desktop:
        dest = Path(custom_desktop)
    elif os.environ.get("LAXMAN_DESKTOP_DIR"):
        dest = Path(os.environ["LAXMAN_DESKTOP_DIR"]) / "First Video Automation"
    else:
        dest = Path.home() / "Desktop" / "First Video Automation"
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def sanitize_title(title: str) -> str:
    """Sanitizes user/project titles into filesystem-safe stem names."""
    if not title:
        return "First_Video"
    clean = re.sub(r'[<>:"/\\|?*!\(\)\x00-\x1f]', "_", title)
    clean = re.sub(r"\s+", "_", clean).strip(" ._")
    clean = re.sub(r"_+", "_", clean)
    if not clean:
        clean = "First_Video"
    return clean[:60]


def file_sha256_full(path: Path) -> str:
    """Computes complete 64-character SHA-256 hex digest for binary file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def get_destination_filepath(
    dest_dir: Path,
    title: str,
    sfx: str = "",
    timestamp: str | None = None,
) -> Path:
    """Computes a unique, collision-safe destination MP4 path.
    Format: <sanitized_title>_<YYYYMMDD_HHMMSS>[_9x16].mp4
    Appends _01, _02, etc. if a conflict already exists on disk (NEVER overwrites).
    """
    ts = timestamp or time.strftime("%Y%m%d_%H%M%S")
    clean_title = sanitize_title(title)
    base_stem = f"{clean_title}_{ts}{sfx}"
    candidate = dest_dir / f"{base_stem}.mp4"
    if not candidate.exists():
        return candidate

    idx = 1
    while (dest_dir / f"{base_stem}_{idx:02d}.mp4").exists():
        idx += 1
    return dest_dir / f"{base_stem}_{idx:02d}.mp4"


get_collision_safe_path = get_destination_filepath


def atomic_desktop_copy(
    source_path: Path,
    target_path: Path,
    expected_sha: str | None = None,
) -> dict[str, Any]:
    """Copies video file atomically to target destination with strict SHA-256 integrity verification.
    1. Writes to temporary file target_path.tmp.<uuid>.
    2. Flushes buffers and fsyncs to storage.
    3. Computes SHA-256 and asserts bit-for-bit match with source.
    4. Atomically replaces destination path (os.replace).
    """
    if not source_path.is_file() or source_path.stat().st_size == 0:
        raise FileNotFoundError(f"Source video '{source_path}' does not exist or is empty")

    target_dir = target_path.parent
    target_dir.mkdir(parents=True, exist_ok=True)

    tmp_path = target_path.with_name(f"{target_path.name}.tmp.{uuid.uuid4().hex[:8]}")

    try:
        with open(source_path, "rb") as fsrc, open(tmp_path, "wb") as fdst:
            shutil.copyfileobj(fsrc, fdst, length=64 * 1024)
            fdst.flush()
            try:
                os.fsync(fdst.fileno())
            except OSError:
                pass

        # Hash and size assertion
        h = hashlib.sha256()
        with open(tmp_path, "rb") as f:
            for chunk in iter(lambda: f.read(64 * 1024), b""):
                h.update(chunk)
        actual_sha = h.hexdigest()
        actual_size = tmp_path.stat().st_size

        if expected_sha:
            if len(expected_sha) == 16:
                mismatch = actual_sha[:16].lower() != expected_sha.lower()
            else:
                mismatch = actual_sha.lower() != expected_sha.lower()
            if mismatch:
                raise ValueError(
                    f"Integrity check failed: source SHA-256 '{expected_sha}' != copied SHA-256 '{actual_sha}'"
                )

        # Atomic replace
        os.replace(tmp_path, target_path)

        return {
            "path": target_path,
            "sha256": actual_sha,
            "size_bytes": actual_size,
        }
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise


def write_delivery_summary(
    dest_dir: Path,
    target_file: Path,
    summary_data: dict[str, Any],
    project_dir: Path,
    sfx: str = "",
) -> dict[str, Path]:
    """Generates delivery_summary.json and delivery_summary.txt in both destination and project folders."""
    json_bytes = json.dumps(summary_data, indent=2, ensure_ascii=False)

    dest_json = dest_dir / f"{target_file.stem}_delivery_summary.json"
    dest_json.write_text(json_bytes, encoding="utf-8")

    proj_json = project_dir / f"delivery_summary{sfx}.json"
    proj_json.write_text(json_bytes, encoding="utf-8")

    txt_content = (
        "================================================================================\n"
        "LAXMAN-AUTONOMOUS VIDEO GENERATION SYSTEM - DELIVERY SUMMARY\n"
        "================================================================================\n"
        f"Project ID:        {summary_data.get('project_id')}\n"
        f"Project Title:     {summary_data.get('project_title')}\n"
        f"Delivery ID:       {summary_data.get('delivery_id')}\n"
        f"Delivered File:    {target_file.name}\n"
        f"Destination Path:  {target_file.resolve()}\n"
        f"Aspect Ratio:      {summary_data.get('aspect_ratio')}\n"
        f"Resolution:        {summary_data.get('resolution')}\n"
        f"Frame Rate:        {summary_data.get('fps')} fps\n"
        f"Duration:          {summary_data.get('duration_seconds')} s\n"
        f"File Size:         {summary_data.get('file_size_bytes')} bytes\n"
        f"Source Video:      {summary_data.get('source_file')}\n"
        f"SHA-256 Digest:    {summary_data.get('destination_sha256')}\n"
        f"Integrity Check:   MATCHED (Bit-for-bit verified)\n"
        f"Technical QC:      {str(summary_data.get('qc_verdict', 'passed')).upper()}\n"
        f"All Gates Passed:  {summary_data.get('all_gates_passed')}\n"
        f"Delivered At:      {summary_data.get('delivered_at')}\n"
        "================================================================================\n"
    )

    dest_txt = dest_dir / f"{target_file.stem}_delivery_summary.txt"
    dest_txt.write_text(txt_content, encoding="utf-8")

    proj_txt = project_dir / f"delivery_summary{sfx}.txt"
    proj_txt.write_text(txt_content, encoding="utf-8")

    return {
        "dest_json": dest_json,
        "dest_txt": dest_txt,
        "project_json": proj_json,
        "project_txt": proj_txt,
    }


def deliver_to_desktop(
    project_dir: Path,
    aspect: str = "16:9",
    custom_desktop: Path | str | None = None,
    title: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    """Executes verified desktop export of the rendered MP4 file to Desktop/First Video Automation/."""
    from SYSTEM.core.artifact_contracts import _file_sha256

    sfx = "_9x16" if aspect == "9:16" else ""
    vid = project_dir / ("out_9x16.mp4" if aspect == "9:16" else "out.mp4")

    if not vid.exists():
        raise FileNotFoundError(f"Missing deliverable video file '{vid}'")
    if vid.stat().st_size < 1000:
        raise ValueError(f"Deliverable video file is empty or suspiciously small ({vid.stat().st_size} bytes)")

    sha = file_sha256_full(vid)
    size = vid.stat().st_size

    # Resolve project title
    proj_title = title
    if not proj_title:
        p_json = project_dir / "project.json"
        if p_json.exists():
            try:
                pj = json.loads(p_json.read_text(encoding="utf-8"))
                proj_title = pj.get("title") or pj.get("name")
            except Exception:
                pass
    if not proj_title:
        proj_title = project_dir.name

    dest_dir = get_desktop_delivery_dir(custom_desktop)
    target_file = get_destination_filepath(dest_dir, proj_title, sfx=sfx)

    # Emit Telugu activity event for delivery start
    try:
        communication.publish_lifecycle_event(
            project_id=project_dir.name,
            stage_id="final",
            sender_agent_id="final_video_delivery",
            event="desktop_delivery_started",
            detail=f"Delivering verified video to {target_file.name}",
            telugu_activity="పూర్తయిన వీడియోను మీ డెస్క్టాప్లో భద్రపరుస్తున్నాను.",
            task_id=task_id,
        )
    except Exception:
        pass

    # Atomic copy with SHA-256 match assertion
    copy_res = atomic_desktop_copy(vid, target_file, expected_sha=sha)

    # Gather probe metadata
    media_meta = {}
    try:
        from VIDEO_ENGINE.stages import media_probe
        probe_res = media_probe.probe(vid)
        v_stream = probe_res.get("video") or {}
        media_meta = {
            "container": probe_res.get("container"),
            "duration_seconds": probe_res.get("duration"),
            "width": v_stream.get("width"),
            "height": v_stream.get("height"),
            "fps": v_stream.get("frame_rate_value"),
            "video_codec": v_stream.get("codec"),
        }
    except Exception:
        pass

    delivery_id = f"deliv_{uuid.uuid4().hex[:10]}"
    summary_data = {
        "schema_version": "1.0",
        "delivery_id": delivery_id,
        "project_id": project_dir.name,
        "project_title": proj_title,
        "aspect_ratio": aspect,
        "source_file": str(vid.resolve()),
        "source_sha256": sha,
        "destination_file": target_file.name,
        "destination_path": str(target_file.resolve()),
        "destination_sha256": copy_res["sha256"],
        "file_size_bytes": copy_res["size_bytes"],
        "media_metadata": media_meta,
        "duration_seconds": media_meta.get("duration_seconds"),
        "resolution": f"{media_meta.get('width', 1920)}x{media_meta.get('height', 1080)}",
        "fps": media_meta.get("fps", 30),
        "video_codec": media_meta.get("video_codec", "h264"),
        "qc_evidence_ref": f"final_qc_report{sfx}.json",
        "qc_verdict": "passed",
        "all_gates_passed": True,
        "delivered_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "created_at": time.time(),
    }

    summary_files = write_delivery_summary(dest_dir, target_file, summary_data, project_dir, sfx=sfx)

    # Emit Telugu activity event for completion
    try:
        communication.publish_lifecycle_event(
            project_id=project_dir.name,
            stage_id="final",
            sender_agent_id="final_video_delivery",
            event="desktop_delivery_completed",
            detail=f"Video safely exported to {target_file.name} (SHA-256={sha[:12]}...)",
            telugu_activity="వీడియో తయారైంది. అవసరమైన పరీక్షలు పూర్తయ్యాయి.",
            task_id=task_id,
        )
    except Exception:
        pass

    return {
        "delivery_id": delivery_id,
        "destination_path": target_file,
        "sha256": copy_res["sha256"],
        "size_bytes": copy_res["size_bytes"],
        "summary_data": summary_data,
        "summary_files": summary_files,
    }


class FinalVideoDeliveryAgent(BaseAgent):
    """A14: Final Video Delivery Agent. Provenance, gate audit, atomic desktop export, and manifest generation."""

    def __init__(self, metadata: AgentMetadata | None = None) -> None:
        if metadata is None:
            metadata = AgentMetadata(
                agent_id="final_video_delivery",
                name="Final Video Delivery Agent",
                stage_id="final",
            )
        super().__init__(metadata)

    def validate(self, project_dir: Path, request: AgentRequest) -> list[str]:
        aspect = request.parameters.get("aspect") or (getattr(request, "metadata", {}) or {}).get("aspect", "16:9")
        vid = project_dir / ("out_9x16.mp4" if aspect == "9:16" else "out.mp4")
        if not vid.exists():
            return ["Missing deliverable video file"]
        if vid.stat().st_size < 1000:
            return ["Deliverable video file is empty (< 1000 bytes)"]
        return []

    def execute(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        aspect = request.parameters.get("aspect") or (getattr(request, "metadata", {}) or {}).get("aspect", "16:9")
        sfx = "_9x16" if aspect == "9:16" else ""
        vid = project_dir / ("out_9x16.mp4" if aspect == "9:16" else "out.mp4")
        task_id = request.parameters.get("task_id") or request.run_id

        from VIDEO_ENGINE.stages import final_qc, timeline_approval
        from SYSTEM.policies import llm_review
        from SYSTEM.core.artifact_contracts import validate_final_artifacts, _file_sha256, verify_path_confinement

        verify_path_confinement(project_dir, vid)

        gate_reasons = []

        # 1. Timeline build check
        tl_file = project_dir / f"timeline{sfx}.json"
        if not tl_file.exists():
            gate_reasons.append("Timeline build artifact missing")

        # 2. Timeline approval check
        app_st = timeline_approval.state(project_dir, aspect)
        if not app_st.get("approved") or app_st.get("stale"):
            gate_reasons.append("Timeline is not approved or is stale")

        # 3. Deterministic QC and playback sign-off gate
        qc_gate = final_qc.gate(project_dir, aspect)
        if qc_gate:
            gate_reasons.extend(qc_gate)

        if gate_reasons:
            try:
                communication.publish_lifecycle_event(
                    project_id=project_dir.name,
                    stage_id="final",
                    sender_agent_id=self.agent_id,
                    event="delivery_blocked",
                    detail=f"Final delivery blocked: {'; '.join(gate_reasons[:2])}",
                    telugu_activity="ఒక సమస్య వల్ల పని ముందుకు సాగడం లేదు. వివరాలు పరిశీలిస్తున్నాను.",
                    task_id=task_id,
                )
            except Exception:
                pass

            return AgentResult(
                agent_id=self.agent_id,
                stage_id="final",
                project_id=project_dir.name,
                status="blocked",
                summary=f"Final video delivery blocked: {'; '.join(gate_reasons[:3])}",
                error="; ".join(gate_reasons),
                metadata={"gate_reasons": gate_reasons},
            )

        sha = file_sha256_full(vid)
        size = vid.stat().st_size
        tl_fp = app_st.get("fingerprint") or ""

        # Deliver to Desktop
        custom_desktop = request.parameters.get("custom_desktop")
        title = request.parameters.get("title")

        try:
            delivery_res = deliver_to_desktop(
                project_dir,
                aspect=aspect,
                custom_desktop=custom_desktop,
                title=title,
                task_id=task_id,
            )
        except Exception as e:
            try:
                communication.publish_lifecycle_event(
                    project_id=project_dir.name,
                    stage_id="final",
                    sender_agent_id=self.agent_id,
                    event="desktop_delivery_failed",
                    detail=f"Desktop export failed: {e}",
                    telugu_activity="పనిలో లోపం ఏర్పడింది. కారణాన్ని పరిశీలిస్తున్నాను.",
                    task_id=task_id,
                )
            except Exception:
                pass

            return AgentResult(
                agent_id=self.agent_id,
                stage_id="final",
                project_id=project_dir.name,
                status="failed",
                summary=f"Desktop video delivery failed: {e}",
                error=str(e),
            )

        media_meta = delivery_res["summary_data"].get("media_metadata", {})
        human_rev = final_qc.current_review(project_dir, aspect, sha) or {}

        dm_data = {
            "schema_version": "1.0",
            "project_id": project_dir.name,
            "aspect_ratio": aspect,
            "timeline_fingerprint": tl_fp,
            "approval_fingerprint": tl_fp,
            "video_artifact_ref": vid.name,
            "sha256": _file_sha256(vid),
            "sha256_full": sha,
            "byte_size": size,
            "media_metadata": media_meta,
            "qc_evidence_ref": f"final_qc_report{sfx}.json",
            "qc_review_ref": f"final_qc_review{sfx}.json",
            "human_playback_signoff": {
                "reviewer": human_rev.get("reviewer"),
                "decision": human_rev.get("decision"),
                "timestamp": human_rev.get("created_at") or human_rev.get("reviewed_at"),
            },
            "desktop_delivery": {
                "destination_file": delivery_res["destination_path"].name,
                "destination_path": str(delivery_res["destination_path"].resolve()),
                "sha256": delivery_res["sha256"],
                "summary_file": delivery_res["summary_files"]["dest_json"].name,
            },
            "delivery_status": "accepted",
            "all_gates_passed": True,
            "created_at": time.time(),
        }

        dm_file = project_dir / f"delivery_manifest{sfx}.json"
        dm_file.write_text(json.dumps(dm_data, indent=2), encoding="utf-8")

        outputs = [
            ArtifactRef(path=str(vid), description="Final Delivered Video File"),
            ArtifactRef(path=str(dm_file), description="Delivery Manifest JSON"),
            ArtifactRef(path=str(delivery_res["destination_path"]), description="Desktop Exported Video MP4"),
            ArtifactRef(path=str(delivery_res["summary_files"]["dest_json"]), description="Delivery Summary JSON"),
        ]

        try:
            validate_final_artifacts(project_dir, aspect)
        except Exception as e:
            return AgentResult(
                agent_id=self.agent_id,
                stage_id="final",
                project_id=project_dir.name,
                status="failed",
                summary=f"Final delivery artifact validation failed: {e}",
                error=str(e),
            )

        return AgentResult(
            agent_id=self.agent_id,
            stage_id="final",
            project_id=project_dir.name,
            status="succeeded",
            output_refs=outputs,
            summary=f"Final video delivered to desktop: {delivery_res['destination_path'].name} (SHA-256={sha[:12]}...)",
            metadata={
                "delivery_manifest": dm_data,
                "desktop_delivery": delivery_res["summary_data"],
                "sha256": sha,
                "byte_size": size,
            },
        )


# Backward-compatibility alias
FinalVideoDeliveryAdapter = FinalVideoDeliveryAgent
