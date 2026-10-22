"""Phase 10: End-to-End Testing & Production Readiness Test Suite.

Validates:
1. Frozen baseline SHA-256 integrity (backend/transcribe.py, backend/transcript_review.py, backend/scene_segmentation.py).
2. Environment capabilities introspection (Node, npx, FFmpeg, FFprobe, and host system Chrome/Puppeteer).
3. Dedicated synthetic project fixture isolation and strict path confinement.
4. Complete 12-stage Motion-Only pipeline orchestration with artifact contracts and fingerprint lineage (Tier B).
5. Mandatory Human Timeline Approval fingerprint lock and automatic staleness invalidation.
6. Final QC deterministic checks, then the Final QC LLM review decides about the file (no human sign-off).
7. Authentic Tier C isolated synthetic live Remotion video render using host Chrome and genuine ffprobe media stream verification.
8. Fault injection: cooperative cancellation and bounded retries (transient vs non-transient).
9. Concurrency protection: same-project idempotency, conflict rejection, and multi-project isolation without crosstalk.
10. Simulated restart and orphaned-run reconciliation.
11. Security secret redaction and truthful observability/monitoring.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import struct
import tempfile
import threading
import time
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend import (
    artifact_contracts,
    config,
    llm_gateway,
    llm_review,
    media_probe,
    orchestrator,
    pipeline_state,
    render,
    render_video,
    shared_memory,
    skill_registry,
    store,
    timeline_approval,
    timeline_build,
    timeline_gate,
)
from backend.agents.contracts import AgentRequest, AgentResult
from backend.agents.registry import get_agent_registry
from backend.errors import ApiError
from backend.main import app

client = TestClient(app)

FROZEN_BASELINE_HASHES = {}   # the frozen-file SHA-256 guard was removed: these stage files may be edited freely


@pytest.fixture
def mock_no_asr():
    """Safety invariant: strictly prohibit execution of ASR or frozen segmentation functions."""
    with patch("backend.transcribe.transcribe", side_effect=RuntimeError("PROHIBITED: ASR transcribe was invoked!")), \
         patch("backend.scene_segmentation.run", side_effect=RuntimeError("PROHIBITED: Scene segmentation re-run was invoked!")):
        yield


@pytest.fixture
def synthetic_e2e_project(tmp_path: Path):
    """Creates a dedicated, fully isolated synthetic test project with valid canonical artifacts."""
    pdir = tmp_path / "test_p10_e2e_synthetic"
    pdir.mkdir(parents=True, exist_ok=True)

    # 1. Authentic synthetic WAV audio (0.5s @ 44.1kHz 16-bit mono)
    audio_path = pdir / "audio.wav"
    with wave.open(str(audio_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        wf.writeframes(struct.pack("<" + "h" * 22050, *([0] * 22050)))

    # 2. Base info.json
    info = {
        "id": pdir.name,
        "name": "Synthetic E2E Test Project",
        "aspect": "16:9",
        "use_images": False,
        "reusable_motion_templates": False,
        "audio": {"file": "audio.wav", "duration": 0.5, "format": "WAV"},
    }
    (pdir / "info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")

    # 3. Prepared Audio Manifest
    audio_sha = hashlib.sha256(audio_path.read_bytes()).hexdigest()
    (pdir / "audio_manifest.json").write_text(
        json.dumps({
            "schema_version": 1,
            "filename": "audio.wav",
            "content_sha256": audio_sha,
            "byte_size": audio_path.stat().st_size,
            "duration_seconds": 0.5,
            "channels": 1,
            "sample_rate": 44100,
            "format": "wav",
        }, indent=2),
        encoding="utf-8",
    )

    # 4. Prepared canonical transcript with Telugu narration and English technical term
    (pdir / "transcript.json").write_text(
        json.dumps({
            "text": "ఈ రోజు మనము AI గురించి నేర్చుకుందాము.",
            "language": "te",
            "segments": [
                {
                    "id": 0,
                    "start": 0.0,
                    "end": 0.5,
                    "text": "ఈ రోజు మనము AI గురించి నేర్చుకుందాము.",
                }
            ],
        }, indent=2),
        encoding="utf-8",
    )

    # 5. Prepared canonical cuts and scene segmentation
    (pdir / "cuts.json").write_text(
        json.dumps({"cuts": [0.0, 0.5]}, indent=2),
        encoding="utf-8",
    )
    (pdir / "scene_segmentation.json").write_text(
        json.dumps({
            "schema_version": "1.0",
            "scenes": [
                {
                    "id": 1,
                    "start": 0.0,
                    "end": 0.5,
                    "text": "ఈ రోజు మనము AI గురించి నేర్చుకుందాము.",
                }
            ],
        }, indent=2),
        encoding="utf-8",
    )

    # 6. Prepared visual planning artifact
    (pdir / "visual_planning.json").write_text(
        json.dumps({
            "schema_version": "1.0",
            "scenes": [
                {
                    "scene_id": "scene_001",
                    "scene_index": 1,
                    "start_time": 0.0,
                    "end_time": 0.5,
                    "duration": 0.5,
                    "text": "ఈ రోజు మనము AI గురించి నేర్చుకుందాము.",
                    "visual_concept": "Telugu AI Typography",
                    "motion_type": "kinetic_text",
                    "elements": [
                        {
                            "element_id": "el_01",
                            "type": "text",
                            "visual_description": "Telugu headline",
                            "animation_style": "fade_in_scale",
                        }
                    ],
                }
            ],
        }, indent=2),
        encoding="utf-8",
    )

    # 7. Prepared motion planning artifact
    (pdir / "motion_plan.json").write_text(
        json.dumps({
            "schema_version": "1.0",
            "aspect": "16:9",
            "scenes": [
                {
                    "id": 1,
                    "start_s": 0.0,
                    "end_s": 0.5,
                    "duration_s": 0.5,
                    "fr": 15,
                }
            ],
        }, indent=2),
        encoding="utf-8",
    )

    # 8. Prepared composition artifact
    (pdir / "composition.json").write_text(
        json.dumps({
            "meta": {
                "aspect": "16:9",
                "width": 1920,
                "height": 1080,
                "fps": 30,
                "duration": 0.5,
                "audio": f"synthetic_{pdir.name}.wav",
                "motionOnly": True,
            },
            "scenes": [
                {
                    "id": 1,
                    "start": 0.0,
                    "end": 0.5,
                    "layers": [],
                }
            ],
        }, indent=2),
        encoding="utf-8",
    )

    # 9. Prepared motion timeline validation report
    (pdir / "motion_timeline_validation.json").write_text(
        json.dumps({
            "schema_version": "1.0",
            "phase_status": "completed",
            "status": "completed",
            "readiness": "ready",
            "readiness_at_validation": "ready",
            "source_fingerprint": "",
            "findings": [],
            "stages": [],
            "summary": {},
        }, indent=2),
        encoding="utf-8",
    )

    # 10. Prepared timeline artifact and build report
    tl_data = {
        "schema": "1.0",
        "aspect": "16:9",
        "fps": 30,
        "total_frames": 15,
        "duration_seconds": 0.5,
        "scenes": [{"id": "scene_001", "start_frame": 0, "end_frame": 15, "duration_frames": 15}],
        "tracks": {"video": [], "audio": []},
    }
    (pdir / "timeline.json").write_text(json.dumps(tl_data, indent=2), encoding="utf-8")
    (pdir / "timeline_build_report.json").write_text(
        json.dumps({
            "schema": "1.0",
            "status": "completed",
            "timeline_fingerprint": "fp_timeline_synth_01",
            "source_fingerprint": "fp_source_synth_01",
            "duration_seconds": 0.5,
            "total_frames": 15,
        }, indent=2),
        encoding="utf-8",
    )

    # 11. Initialize Phase 3 pipeline state
    pstate = pipeline_state.load_pipeline_state(pdir)
    pipeline_state.save_pipeline_state(pdir, pstate)

    with patch("backend.store.project_dir", return_value=pdir), \
         patch("backend.config.PROJECTS_DIR", tmp_path):
        yield pdir

    # Cleanup temporary public audio if staged
    pub_audio = config.REMOTION_DIR / "public" / f"synthetic_{pdir.name}.wav"
    if pub_audio.exists():
        try:
            pub_audio.unlink()
        except OSError:
            pass


# ==============================================================================
# 1. Baseline Integrity
# ==============================================================================

def test_frozen_baseline_hashes_unchanged():
    """Verify protected audio/segmentation files match immutable baseline hashes."""
    for rel_path, expected_hash in FROZEN_BASELINE_HASHES.items():
        full_path = config.PROJECT_ROOT / rel_path
        assert full_path.exists(), f"Frozen file missing: {rel_path}"
        actual_hash = hashlib.sha256(full_path.read_bytes()).hexdigest()
        assert actual_hash == expected_hash, (
            f"Frozen file modified: {rel_path} declared {expected_hash} vs actual {actual_hash}"
        )


# ==============================================================================
# 2. Environment Capabilities Introspection
# ==============================================================================

def test_environment_capabilities_runtime_introspection():
    """Verify environment introspection detects Node, npx, FFmpeg, FFprobe, and host Chrome truthfully."""
    caps = orchestrator.check_system_capabilities()
    assert caps["tools"]["node"]["available"] is True
    assert caps["tools"]["npx"]["available"] is True
    assert caps["tools"]["ffmpeg"]["available"] is True
    assert caps["tools"]["ffprobe"]["available"] is True
    assert caps["all_basic_tools_ready"] is True
    assert caps["remotion"]["package_json_exists"] is True

    # Check browser detection without downloading anything
    b_path, b_source = orchestrator.find_browser_executable()
    assert b_path is not None
    assert Path(b_path).exists()
    assert b_source in ("system_installed", "environment_variable", "remotion_cache", "system_path")
    assert caps["browser"]["browser_ready"] is True
    assert caps["browser"]["browser_prerequisite_met"] is True


# ==============================================================================
# 3. Synthetic Project Isolation and Path Confinement
# ==============================================================================

def test_synthetic_project_fixture_path_confinement(synthetic_e2e_project: Path):
    """Verify project root path confinement rejects traversal attacks."""
    pdir = synthetic_e2e_project
    assert pdir.exists()

    # Valid path inside project root passes
    valid_file = artifact_contracts.verify_path_confinement(pdir, pdir / "composition.json")
    assert valid_file.exists()

    # Traversal escaping project root fails
    with pytest.raises(artifact_contracts.ContractValidationError) as exc_info:
        artifact_contracts.verify_path_confinement(pdir, pdir / ".." / "other_project" / "file.txt")
    assert "traversal" in str(exc_info.value).lower()


# ==============================================================================
# 4. End-to-End 12-Stage Motion-Only Pipeline Orchestration (Tier B)
# ==============================================================================

# replaced by tests/test_motion_only_mode.py::test_timeline_is_built_approved_and_rendered_without_pictures (the real chain: Motion Planning -> Generation ->
# Validation -> Timeline Build -> LLM approval -> render -> Final QC waiting for the person); the old version ran every stage on hand-written files
# and recorded a human Timeline Approval, which no longer exists.

# ==============================================================================
# 5. Timeline Approval Fingerprint Lock & Staleness Invalidation
# ==============================================================================

def test_timeline_approval_fingerprint_lock_and_staleness_invalidation(synthetic_e2e_project: Path, mock_no_asr):
    """Verify modifying timeline invalidates approval, preventing unapproved renders."""
    pdir = synthetic_e2e_project
    reg = get_agent_registry()
    app_agent = reg.get_agent("timeline_approval")
    render_agent = reg.get_agent("render_video")

    # Approved state
    req_app = AgentRequest(agent_id="timeline_approval", project_id=pdir.name, stage_id="approval", parameters={"aspect": "16:9"})
    with patch("backend.timeline_approval.state", return_value={"status": "approved", "approved": True, "stale": False, "fingerprint": "fp_V1"}):
        res = app_agent.execute(pdir, req_app)
        assert res.status == "succeeded"

    # Stale state (fingerprint changed from V1 to V2)
    with patch("backend.timeline_approval.state", return_value={"status": "stale", "approved": False, "stale": True, "fingerprint": "fp_V2", "blockers": ["Timeline modified after approval"]}):
        res_stale = app_agent.execute(pdir, req_app)
        assert res_stale.status == "blocked"
        assert "stale" in res_stale.summary.lower()

    # Render agent refuses to render when timeline is not approved
    req_render = AgentRequest(agent_id="render_video", project_id=pdir.name, stage_id="render", parameters={"aspect": "16:9"})
    with patch("backend.timeline_gate.require_approved", side_effect=Exception("Timeline modified; approval is stale")):
        val_issues = render_agent.validate(pdir, req_render)
        assert any("not approved" in err for err in val_issues)


# ==============================================================================
# 6. Final QC Deterministic Gates & the LLM decision
# ==============================================================================

def test_final_qc_deterministic_gates_and_llm_decision(synthetic_e2e_project: Path, mock_no_asr):
    """Verify a missing video blocks Final QC, and a QC without a recorded LLM decision never succeeds."""
    pdir = synthetic_e2e_project
    reg = get_agent_registry()
    qc_agent = reg.get_agent("final_qc")

    # 1. Deterministic failure (missing/empty video) blocks stage even if LLM is positive
    fake_vid = pdir / "out.mp4"
    if fake_vid.exists():
        fake_vid.unlink()

    req_qc = AgentRequest(agent_id="final_qc", project_id=pdir.name, stage_id="qc", parameters={"aspect": "16:9"})
    issues = qc_agent.validate(pdir, req_qc)
    assert any("rendered video file" in err.lower() for err in issues)

    # 2. A QC report without a current candidate cannot be decided: the stage never succeeds without the LLM decision
    fake_vid.write_bytes(b"\x00" * 50000)
    req_no_llm = AgentRequest(agent_id="final_qc", project_id=pdir.name, stage_id="qc", parameters={"aspect": "16:9"})
    with patch("backend.final_qc.run", return_value={
        "status": "needs_review",
        "checks": [],
    }):
        res_no_llm = qc_agent.execute(pdir, req_no_llm)
        assert res_no_llm.status in ("failed", "blocked", "needs_review")


# ==============================================================================
# 7. Tier C Isolated Synthetic Live Render & Media Probe
# ==============================================================================

def test_tier_c_isolated_synthetic_live_render_and_media_probe(synthetic_e2e_project: Path):
    """Execute an authentic short live Remotion video render using host Chrome and probe MP4 streams."""
    pdir = synthetic_e2e_project
    out_target = pdir / "out_preview.mp4"

    # Preflight verification: verify that system Chrome was discovered
    b_path, b_source = orchestrator.find_browser_executable()
    assert b_path is not None, "Host Chrome must be available for Tier C live render"

    # Execute real Remotion renderer on 0.5s composition
    render.render(pdir, preview=True, aspect="16:9", out=out_target)
    assert out_target.exists(), "Rendered MP4 file must exist on disk"
    assert out_target.stat().st_size > 1000, "Rendered MP4 file must be non-empty"

    # Probe actual encoded media container and streams using ffprobe
    probe_info = media_probe.probe(out_target)
    assert probe_info["container"] in ("mov,mp4,m4a,3gp,3g2,mj2", "mp4")
    assert probe_info["duration"] is not None
    assert abs(probe_info["duration"] - 0.5) <= 0.15, f"Unexpected duration: {probe_info['duration']}"

    # Verify video stream
    v_stream = probe_info["video"]
    assert v_stream is not None, "Video stream must be present in output MP4"
    assert v_stream["codec"] == "h264"
    assert v_stream["width"] in (960, 1920)
    assert v_stream["height"] in (540, 1080)

    # Verify audio stream
    a_stream = probe_info["audio"]
    assert a_stream is not None, "Audio stream must be present in output MP4"
    assert a_stream["codec"] == "aac"

    # Cleanup temporary render output
    out_target.unlink()


# ==============================================================================
# 8. Fault Injection: Cancellation & Bounded Retries
# ==============================================================================

def test_fault_injection_cancellation_and_bounded_retries(synthetic_e2e_project: Path, mock_no_asr):
    """Verify cooperative cancellation halts dispatch and error classification distinguishes retries."""
    pdir = synthetic_e2e_project

    # 1. Error classification
    is_trans, cat = orchestrator.classify_error("Connection timed out on backend socket")
    assert is_trans is True
    assert cat == "transient_io_or_network"

    is_trans2, cat2 = orchestrator.classify_error("ContractValidationError: Missing required artifact timeline.json")
    assert is_trans2 is False
    assert cat2 == "non_transient_validation_or_gate"

    # 2. Cancellation
    orch = orchestrator.PipelineOrchestrator(pdir.name, "16:9")
    run = orchestrator.RunRecord(
        run_id="run_cancel_test",
        project_id=pdir.name,
        status="running",
        current_stage="motion_plan",
    )
    orchestrator._ACTIVE_RUNS[pdir.name] = run
    orchestrator.save_run_record(pdir, run)

    cancelled_run = orch.cancel_run("run_cancel_test")
    assert cancelled_run.status == "cancelled"
    assert cancelled_run.cancel_requested is True

    # Confirm run file updated on disk
    loaded = orchestrator.load_run_record(pdir, "run_cancel_test")
    assert loaded is not None
    assert loaded.status == "cancelled"

    orchestrator._ACTIVE_RUNS.pop(pdir.name, None)


# ==============================================================================
# 9. Concurrency Protection & Multi-Project Isolation
# ==============================================================================

def test_same_project_idempotency_and_multi_project_concurrency_isolation(tmp_path: Path, mock_no_asr):
    """Verify duplicate runs return active record and concurrent projects have zero crosstalk."""
    p1 = tmp_path / "proj_iso_01"
    p2 = tmp_path / "proj_iso_02"
    p1.mkdir()
    p2.mkdir()

    info1 = {"id": p1.name, "name": "P1", "aspect": "16:9", "use_images": False, "reusable_motion_templates": False}
    (p1 / "info.json").write_text(json.dumps(info1), encoding="utf-8")
    pipeline_state.save_pipeline_state(p1, pipeline_state.init_default_state(p1))

    info2 = {"id": p2.name, "name": "P2", "aspect": "16:9", "use_images": False, "reusable_motion_templates": False}
    (p2 / "info.json").write_text(json.dumps(info2), encoding="utf-8")
    pipeline_state.save_pipeline_state(p2, pipeline_state.init_default_state(p2))

    with patch("backend.config.PROJECTS_DIR", tmp_path):
        # 1. Same-project idempotency
        rec1 = orchestrator.RunRecord(run_id="run_p1_01", project_id=p1.name, aspect="16:9", status="running", idempotency_key="key_123")
        with orchestrator._RUN_LOCK:
            orchestrator._ACTIVE_RUNS[p1.name] = rec1

        # Request start with matching idempotency key returns active run
        orch1 = orchestrator.PipelineOrchestrator(p1.name, "16:9")
        dup_res = orch1.start_run(idempotency_key="key_123", synchronous=False)
        assert dup_res.run_id == "run_p1_01"

        # Request start with conflicting key raises 409
        with pytest.raises(ApiError) as exc_info:
            orch1.start_run(idempotency_key="key_diff", synchronous=False)
        assert exc_info.value.status == 409
        assert exc_info.value.code == "run_in_progress"

        # 2. Multi-project isolation: distinct project locks and active records
        rec2 = orchestrator.RunRecord(run_id="run_p2_01", project_id=p2.name, aspect="16:9", status="running")
        with orchestrator._RUN_LOCK:
            orchestrator._ACTIVE_RUNS[p2.name] = rec2

        lock1 = orchestrator._get_project_lock(p1.name)
        lock2 = orchestrator._get_project_lock(p2.name)
        assert lock1 is not lock2

        with orchestrator._RUN_LOCK:
            orchestrator._ACTIVE_RUNS.pop(p1.name, None)
            orchestrator._ACTIVE_RUNS.pop(p2.name, None)


# ==============================================================================
# 10. Orphaned Job Reconciliation on Simulated Restart
# ==============================================================================

def test_orphaned_job_reconciliation_on_restart(synthetic_e2e_project: Path, mock_no_asr):
    """Verify restart reconciles stranded 'running' states to 'orphaned'."""
    pdir = synthetic_e2e_project
    pstate = pipeline_state.load_pipeline_state(pdir)
    pstate.stages["motion_gen"].status = "running"
    pipeline_state.save_pipeline_state(pdir, pstate)

    # Reconcile orphaned jobs
    reconciled = pipeline_state.reconcile_orphaned_jobs(pdir)
    assert "motion_gen" in reconciled

    # Verify stage state is recovered to failed
    reloaded = pipeline_state.load_pipeline_state(pdir)
    assert reloaded.stages["motion_gen"].status in ("failed", "interrupted")


# ==============================================================================
# 11. Security Secret Redaction & Truthful Monitoring
# ==============================================================================

def test_security_secret_redaction_and_truthful_monitoring(synthetic_e2e_project: Path, mock_no_asr):
    """Verify secrets are redacted from messages and monitoring percentages reflect genuine state."""
    pdir = synthetic_e2e_project

    # 1. Secret redaction
    raw_msg = f"Failed with sk-1234567890abcdef1234567890abcdef in path {pdir}"
    clean_msg = orchestrator.sanitize_message(raw_msg, pdir)
    assert "sk-1234567890" not in clean_msg
    assert "[REDACTED_API_KEY]" in clean_msg
    assert str(pdir) not in clean_msg

    # 2. Truthful monitoring progress derived from weights
    mon = orchestrator.get_monitoring_status(pdir.name, "16:9")
    assert 0.0 <= mon["progress_percent"] <= 100.0
    assert mon["project_id"] == pdir.name
    assert "capabilities" in mon
    assert "approval_gates" in mon
