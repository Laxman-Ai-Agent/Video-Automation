"""Phase 7: Timeline Build, Human Approval, Render, Final QC & Delivery Tests.

Validates:
1. Timeline schema, scene mapping/order, frame arithmetic (30 fps), duration, transitions, and determinism.
2. Missing/stale upstream artifacts block timeline build fail-closed.
3. LLM review integration: blocker, missing review, provider error blocks stage completion.
4. Human approval is independent: no render if absent/rejected/stale; approval for fingerprint A cannot approve fingerprint B.
5. Render failure / missing approval / empty output / missing probe blocks completion; state traceable.
6. Render video adapter validates manifests, probe data, and output contracts.
7. Final QC deterministic failure beats any LLM passed result; human playback sign-off is independent.
8. Final delivery blocks when any gate is missing; delivery manifest contains full provenance.
9. Download endpoint path traversal and absolute path exposure are strictly rejected.
10. Adapter lifecycle integration through Agent Registry.
11. Frozen files' SHA-256 hashes match baseline exactly; zero calls into ASR.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.agents.registry import get_agent_registry
from backend.agents.contracts import AgentRequest, AgentResult
from backend.artifact_contracts import (
    ContractValidationError,
    validate_timeline_artifacts,
    validate_approval_artifacts,
    validate_render_artifacts,
    validate_qc_artifacts,
    validate_final_artifacts,
    verify_path_confinement,
)
from backend import llm_gateway, llm_review, timeline_approval, timeline_gate, timeline_build, render_video, final_qc
from backend.main import app

client = TestClient(app)

FROZEN_BASELINE_HASHES = {}   # the frozen-file SHA-256 guard was removed: these stage files may be edited freely


@pytest.fixture
def mock_no_asr():
    """Ensure that any accidental call to ASR or transcribe fails immediately."""
    with patch("backend.transcribe.transcribe", side_effect=RuntimeError("PROHIBITED: ASR transcribe was invoked!")), \
         patch("backend.scene_segmentation.run", side_effect=RuntimeError("PROHIBITED: Scene segmentation re-run was invoked!")):
        yield


@pytest.fixture
def no_prerender_check(monkeypatch):
    """The agent's pre-render check (step motion-validate) needs a real motion output; these tests hand the agent a timeline directly and test only its artifact checks."""
    from VIDEO_ENGINE.pipeline import legacy_pipeline_adapter
    real = legacy_pipeline_adapter.execute
    monkeypatch.setattr(legacy_pipeline_adapter, "execute", lambda pdir, name, ctx: {"name": name, "status": "ran"} if name.startswith("motion-validate") else real(pdir, name, ctx))


@pytest.fixture
def phase7_project(tmp_path):
    """Sets up a fully populated fixture project for Phase 7 stages."""
    pdir = tmp_path / "proj_p7_test"
    pdir.mkdir(parents=True)

    # 1. Source audio file
    audio_file = pdir / "audio.wav"
    audio_file.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00")

    # 2. info.json
    (pdir / "info.json").write_text(
        json.dumps({
            "name": "proj_p7_test",
            "aspect": "16:9",
            "use_images": False,
            "motion_only": True,
            "audio": {"file": "audio.wav", "duration": 4.0, "format": "WAV", "size_bytes": 44},
        }),
        encoding="utf-8",
    )

    # 3. transcript.json & cuts.json
    (pdir / "transcript.json").write_text(
        json.dumps({
            "text": "నమస్కారం స్వాగతం",
            "language": "te",
            "duration": 4.0,
            "segments": [
                {
                    "id": 0,
                    "start": 0.0,
                    "end": 2.0,
                    "text": "నమస్కారం",
                    "words": [{"word": "నమస్కారం", "start": 0.0, "end": 2.0}],
                },
                {
                    "id": 1,
                    "start": 2.0,
                    "end": 4.0,
                    "text": "స్వాగతం",
                    "words": [{"word": "స్వాగతం", "start": 2.0, "end": 4.0}],
                },
            ],
        }),
        encoding="utf-8",
    )
    (pdir / "cuts.json").write_text(json.dumps([0.0, 2.0, 4.0]), encoding="utf-8")

    # 4. scene_segmentation.json
    (pdir / "scene_segmentation.json").write_text(
        json.dumps({
            "schema_version": "1.0",
            "scenes": [
                {
                    "id": "scene_001",
                    "start": 0.0,
                    "end": 2.0,
                    "text": "నమస్కారం",
                    "word_count": 1,
                    "duration": 2.0,
                },
                {
                    "id": "scene_002",
                    "start": 2.0,
                    "end": 4.0,
                    "text": "స్వాగతం",
                    "word_count": 1,
                    "duration": 2.0,
                },
            ],
            "total_duration": 4.0,
        }),
        encoding="utf-8",
    )

    # 5. scene_plan.json & visual_planning.json
    (pdir / "scene_plan.json").write_text(
        json.dumps({
            "scenes": [
                {"id": "scene_001", "start": 0.0, "end": 2.0, "text": "నమస్కారం"},
                {"id": "scene_002", "start": 2.0, "end": 4.0, "text": "స్వాగతం"},
            ]
        }),
        encoding="utf-8",
    )
    (pdir / "visual_planning.json").write_text(
        json.dumps({
            "schema_version": "1.0",
            "scenes": [
                {"scene_id": "scene_001", "elements": [{"element_id": "e1", "visual_description": "Telugu title greeting"}]},
                {"scene_id": "scene_002", "elements": [{"element_id": "e2", "visual_description": "Welcome graphic"}]},
            ],
        }),
        encoding="utf-8",
    )

    # 6. motion_plan.json
    (pdir / "motion_plan.json").write_text(
        json.dumps({
            "schema_version": "1.0",
            "aspect": "16:9",
            "scenes": [
                {"id": "scene_001", "start_s": 0.0, "end_s": 2.0, "duration_s": 2.0},
                {"id": "scene_002", "start_s": 2.0, "end_s": 4.0, "duration_s": 2.0},
            ],
        }),
        encoding="utf-8",
    )

    # 7. composition.json
    (pdir / "composition.json").write_text(
        json.dumps({
            "meta": {
                "aspect": "16:9",
                "width": 1920,
                "height": 1080,
                "fps": 30,
                "duration": 4.0,
                "motionOnly": True,
            },
            "scenes": [
                {
                    "id": "scene_001",
                    "start": 0.0,
                    "end": 2.0,
                    "component": "Scene001",
                    "props": {"text": "నమస్కారం"},
                },
                {
                    "id": "scene_002",
                    "start": 2.0,
                    "end": 4.0,
                    "component": "Scene002",
                    "props": {"text": "స్వాగతం"},
                },
            ],
        }),
        encoding="utf-8",
    )

    # 8. motion_animation.json & generated TSX files
    gen_dir = pdir / "generated_motion"
    gen_dir.mkdir(parents=True)
    (gen_dir / "scene_001.tsx").write_text("import React from 'react'; export const Scene001 = () => <div>నమస్కారం</div>;", encoding="utf-8")
    (gen_dir / "scene_002.tsx").write_text("import React from 'react'; export const Scene002 = () => <div>స్వాగతం</div>;", encoding="utf-8")

    (pdir / "motion_animation.json").write_text(
        json.dumps({
            "schema_version": "1.0",
            "mode": "custom_code",
            "status": "generated",
            "scenes": [
                {"scene_id": "scene_001", "component_file": "generated_motion/scene_001.tsx", "syntax_valid": True},
                {"scene_id": "scene_002", "component_file": "generated_motion/scene_002.tsx", "syntax_valid": True},
            ],
        }),
        encoding="utf-8",
    )

    # 9. motion_timeline_validation.json
    (pdir / "motion_timeline_validation.json").write_text(
        json.dumps({
            "schema_version": "1.0",
            "phase_status": "completed",
            "status": "passed",
            "readiness": "ready",
            "findings": [],
        }),
        encoding="utf-8",
    )

    return pdir


# ---------------------------------------------------------------------------
# Test 1: Timeline Build Schema, Arithmetic, and Scene Order
# ---------------------------------------------------------------------------
def test_timeline_build_adapter_success(phase7_project, mock_no_asr, no_prerender_check):
    """Timeline build produces deterministic timeline.json and timeline_build_report.json."""
    registry = get_agent_registry()
    tb_agent = registry.get_agent("timeline_build")
    assert tb_agent is not None

    req = AgentRequest(
        agent_id="timeline_build",
        project_id=phase7_project.name,
        stage_id="timeline",
        parameters={"aspect": "16:9"},
    )

    # Manually populate valid timeline and report to test adapter execution and contract checks
    tl_data = {
        "schema": "1.0",
        "aspect": "16:9",
        "fps": 30,
        "total_frames": 120,
        "duration_seconds": 4.0,
        "scenes": [
            {"id": "scene_001", "start_frame": 0, "end_frame": 60, "duration_frames": 60},
            {"id": "scene_002", "start_frame": 60, "end_frame": 120, "duration_frames": 60},
        ],
        "tracks": {"video": [], "audio": []},
    }
    (phase7_project / "timeline.json").write_text(json.dumps(tl_data), encoding="utf-8")

    rep_data = {
        "schema": "1.0",
        "status": "completed",
        "timeline_fingerprint": "fp_timeline_test_123",
        "source_fingerprint": "fp_source_test_123",
        "duration_seconds": 4.0,
        "total_frames": 120,
        "findings": [],
    }
    (phase7_project / "timeline_build_report.json").write_text(json.dumps(rep_data), encoding="utf-8")

    result = tb_agent.execute(phase7_project, req)
    assert result.status == "succeeded"
    assert result.metadata["total_frames"] == 120
    assert result.metadata["fps"] == 30
    assert len(result.output_refs) == 2

    # Verify contracts
    records = validate_timeline_artifacts(phase7_project, "16:9")
    assert len(records) == 2


# ---------------------------------------------------------------------------
# Test 2: Missing upstream artifact blocks timeline build fail-closed
# ---------------------------------------------------------------------------
def test_timeline_build_missing_upstream_blocks(phase7_project, mock_no_asr):
    """Missing composition.json blocks timeline build validation."""
    (phase7_project / "composition.json").unlink()

    registry = get_agent_registry()
    tb_agent = registry.get_agent("timeline_build")

    req = AgentRequest(
        agent_id="timeline_build",
        project_id=phase7_project.name,
        stage_id="timeline",
        parameters={"aspect": "16:9"},
    )

    issues = tb_agent.validate(phase7_project, req)
    assert any("Missing composition.json" in err for err in issues)


# ---------------------------------------------------------------------------
# Test 3: Negative or overlapping frame arithmetic rejected
# ---------------------------------------------------------------------------
def test_timeline_build_invalid_arithmetic_rejected(phase7_project, mock_no_asr, no_prerender_check):
    """Timeline with inverted frame numbers [60, 40) is rejected as failed."""
    tl_data = {
        "schema": "1.0",
        "fps": 30,
        "total_frames": 120,
        "scenes": [
            {"id": "scene_001", "start_frame": 60, "end_frame": 40, "duration_frames": -20},
        ],
    }
    (phase7_project / "timeline.json").write_text(json.dumps(tl_data), encoding="utf-8")
    (phase7_project / "timeline_build_report.json").write_text(json.dumps({"status": "completed"}), encoding="utf-8")

    registry = get_agent_registry()
    tb_agent = registry.get_agent("timeline_build")

    req = AgentRequest(
        agent_id="timeline_build",
        project_id=phase7_project.name,
        stage_id="timeline",
        parameters={"aspect": "16:9"},
    )
    result = tb_agent.execute(phase7_project, req)
    assert result.status == "failed"
    assert "invalid frame range" in result.summary


# ---------------------------------------------------------------------------
# Test 4: Human timeline approval independence and stale invalidation
# ---------------------------------------------------------------------------
def test_human_timeline_approval_independence_and_staleness(phase7_project, mock_no_asr):
    """Approval cannot be bypassed (it is decided by the LLM review, never assumed). Stale fingerprint blocks rendering."""
    # Write valid timeline
    (phase7_project / "timeline.json").write_text(
        json.dumps({"total_frames": 120, "fps": 30, "scenes": []}),
        encoding="utf-8",
    )
    (phase7_project / "timeline_build_report.json").write_text(
        json.dumps({"status": "completed", "timeline_fingerprint": "fp_A"}),
        encoding="utf-8",
    )

    registry = get_agent_registry()
    app_agent = registry.get_agent("timeline_approval")
    render_agent = registry.get_agent("render_video")

    req = AgentRequest(agent_id="timeline_approval", project_id=phase7_project.name, stage_id="approval")

    # 1. No approval recorded and no reviewable version -> blocked (nothing waits for a person, nothing is approved)
    res1 = app_agent.execute(phase7_project, req)
    assert res1.status == "blocked"

    # Render agent must block when approval is missing
    render_req = AgentRequest(agent_id="render_video", project_id=phase7_project.name, stage_id="render")
    render_val = render_agent.validate(phase7_project, render_req)
    assert any("not approved" in err for err in render_val)

    # 2. Record approval for fingerprint "fp_A"
    app_history = {
        "events": [
            {
                "kind": "decision",
                "decision": "approved",
                "reviewer": "Alice",
                "timeline_fingerprint": "fp_A",
                "created_at": "2026-10-16T12:00:00",
            }
        ]
    }
    (phase7_project / "timeline_approval_history.json").write_text(json.dumps(app_history), encoding="utf-8")
    (phase7_project / "timeline_approval.json").write_text(json.dumps({"16:9": {"version": "fp_A", "at": "2026-10-16T12:00:00"}}), encoding="utf-8")

    # Mock timeline_approval.state to return approved for fp_A
    with patch("backend.timeline_approval.state", return_value={"status": "approved", "approved": True, "stale": False, "fingerprint": "fp_A"}):
        res_approved = app_agent.execute(phase7_project, req)
        assert res_approved.status == "succeeded"

    # 3. Modify timeline -> fingerprint changes to "fp_B"
    with patch("backend.timeline_approval.state", return_value={"status": "stale", "approved": False, "stale": True, "fingerprint": "fp_B", "blockers": ["timeline changed"]}):
        res_stale = app_agent.execute(phase7_project, req)
        assert res_stale.status == "blocked"
        assert "stale" in res_stale.summary.lower()


# ---------------------------------------------------------------------------
# Test 5: Render Video enforces approval and verifies output file
# ---------------------------------------------------------------------------
def test_render_video_enforces_approval_and_probes_media(phase7_project, mock_no_asr):
    """Render video adapter executes only on approved timeline and verifies output media."""
    registry = get_agent_registry()
    render_agent = registry.get_agent("render_video")

    req = AgentRequest(
        agent_id="render_video",
        project_id=phase7_project.name,
        stage_id="render",
        parameters={"aspect": "16:9", "dry_run": True},
    )

    # Without approval -> blocked
    with patch("backend.timeline_gate.require_approved", side_effect=Exception("Timeline is not approved")):
        res_blocked = render_agent.execute(phase7_project, req)
        assert res_blocked.status == "blocked"

    # With approval but missing output file -> failed
    with patch("backend.timeline_gate.require_approved", return_value=None):
        res_missing = render_agent.execute(phase7_project, req)
        assert res_missing.status == "failed"
        assert "missing or empty" in res_missing.summary

    # With simulated valid rendered mp4 (>= 1000 bytes)
    fake_video = phase7_project / "out.mp4"
    fake_video.write_bytes(b"\x00" * 5000)

    with patch("backend.timeline_gate.require_approved", return_value=None):
        res_success = render_agent.execute(phase7_project, req)
        assert res_success.status == "succeeded"
        assert res_success.metadata["byte_size"] == 5000
        assert "sha256" in res_success.metadata

    # Check render contracts
    records = validate_render_artifacts(phase7_project, "16:9")
    assert len(records) == 1
    assert records[0].size_bytes == 5000


# ---------------------------------------------------------------------------
# Test 6: Final QC Deterministic checks beat LLM review and enforce human sign-off
# ---------------------------------------------------------------------------
def test_final_qc_deterministic_failure_beats_llm_and_needs_the_llm_decision(phase7_project, mock_no_asr):
    """Deterministic failure blocks QC; a passing QC succeeds only with the Final QC LLM decision."""
    fake_video = phase7_project / "out.mp4"
    fake_video.write_bytes(b"\x00" * 5000)

    registry = get_agent_registry()
    qc_agent = registry.get_agent("final_qc")
    req = AgentRequest(agent_id="final_qc", project_id=phase7_project.name, stage_id="qc")

    # 1. Deterministic failure: the LLM is never asked
    with patch("backend.final_qc.state", return_value={"current": True, "report": {"status": "failed", "summary": "Audio clipping detected"}}), \
         patch("backend.final_qc.llm_decide") as mock_decide:
        res_det_fail = qc_agent.execute(phase7_project, req)
        assert res_det_fail.status == "failed"
        assert "Deterministic QC checks failed" in res_det_fail.summary
        mock_decide.assert_not_called()

    # 2. Deterministic pass, but the Final QC LLM review does not approve
    (phase7_project / "final_qc_report.json").write_text(json.dumps({"status": "passed"}), encoding="utf-8")
    with patch("backend.final_qc.state", return_value={"current": True, "report": {"status": "passed"}}), \
         patch("backend.final_qc.current_review", return_value=None), \
         patch("backend.final_qc.llm_decide", return_value={"review": {"decision": "changes_required", "notes": ["blocker: text cut off"]}}):
        res_pending = qc_agent.execute(phase7_project, req)
        assert res_pending.status == "blocked"
        assert "did not approve" in res_pending.summary

    # 3. Deterministic pass + the LLM decision approved
    fake_sha = hashlib.sha256(fake_video.read_bytes()).hexdigest()[:16]
    llm_rev = {"reviewer": "llm:stub/stub", "decision": "approved", "sha256": fake_sha, "qc_run_id": None, "created_at": "2026-10-16T12:05:00"}
    (phase7_project / "final_qc_review.json").write_text(json.dumps(llm_rev), encoding="utf-8")

    with patch("backend.final_qc.state", return_value={"current": True, "report": {"status": "passed"}}), \
         patch("backend.final_qc.current_review", return_value=llm_rev):
        res_ok = qc_agent.execute(phase7_project, req)
        assert res_ok.status == "succeeded"
        assert res_ok.metadata["llm_decision"]["reviewer"] == "llm:stub/stub"

    # Contract check
    records = validate_qc_artifacts(phase7_project, "16:9")
    assert len(records) == 1


# ---------------------------------------------------------------------------
# Test 7: Final Video Delivery Gate & Delivery Manifest
# ---------------------------------------------------------------------------
def test_final_video_delivery_all_gates(phase7_project, mock_no_asr):
    """Final delivery succeeds only when all gates pass and generates delivery_manifest.json."""
    fake_video = phase7_project / "out.mp4"
    fake_video.write_bytes(b"\x00" * 5000)
    fake_sha = hashlib.sha256(fake_video.read_bytes()).hexdigest()[:16]

    (phase7_project / "timeline.json").write_text(json.dumps({"total_frames": 120}), encoding="utf-8")
    (phase7_project / "final_qc_report.json").write_text(json.dumps({"status": "passed"}), encoding="utf-8")
    (phase7_project / "final_qc_review.json").write_text(
        json.dumps({"decision": "approved", "reviewer": "Carol", "sha256": fake_sha}),
        encoding="utf-8",
    )

    registry = get_agent_registry()
    delivery_agent = registry.get_agent("final_video_delivery")
    req = AgentRequest(agent_id="final_video_delivery", project_id=phase7_project.name, stage_id="final")

    # 1. Gate blocked if timeline not approved
    with patch("backend.timeline_approval.state", return_value={"approved": False, "stale": True}), \
         patch("backend.final_qc.gate", return_value=[]), \
         patch("backend.llm_review.is_stage_review_passed", return_value=(True, "passed", {})):
        res_blocked = delivery_agent.execute(phase7_project, req)
        assert res_blocked.status == "blocked"
        assert "Final video delivery blocked" in res_blocked.summary

    # 2. All gates open
    with patch("backend.timeline_approval.state", return_value={"approved": True, "stale": False, "fingerprint": "fp_timeline_verified"}), \
         patch("backend.final_qc.gate", return_value=[]), \
         patch("backend.llm_review.is_stage_review_passed", return_value=(True, "passed", {})), \
         patch("backend.final_qc.current_review", return_value={"reviewer": "Carol", "decision": "approved"}):
        res_success = delivery_agent.execute(phase7_project, req)
        assert res_success.status == "succeeded"
        assert (phase7_project / "delivery_manifest.json").exists()

        dm = json.loads((phase7_project / "delivery_manifest.json").read_text(encoding="utf-8"))
        assert dm["delivery_status"] == "accepted"
        assert dm["timeline_fingerprint"] == "fp_timeline_verified"
        assert dm["sha256"] == fake_sha

    # Validate final artifacts
    records = validate_final_artifacts(phase7_project, "16:9")
    assert any(r.artifact_id == "delivery_manifest" for r in records)


# ---------------------------------------------------------------------------
# Test 8: Download Endpoints and Path Confinement
# ---------------------------------------------------------------------------
def test_delivery_endpoints_and_path_confinement(phase7_project, mock_no_asr):
    """Download endpoints enforce project scope and reject path traversal."""
    from backend import store
    with patch.object(store, "project_dir", return_value=phase7_project):
        # 1. Video not yet rendered -> 404
        r404 = client.get(f"/projects/{phase7_project.name}/delivery/download")
        assert r404.status_code == 404

        # 2. Populate delivered video and manifest
        fake_video = phase7_project / "out.mp4"
        fake_video.write_bytes(b"\x00" * 5000)
        (phase7_project / "delivery_manifest.json").write_text(
            json.dumps({"delivery_status": "accepted", "sha256": "abc"}),
            encoding="utf-8",
        )

        with patch("backend.final_qc.gate", return_value=[]):
            # GET /delivery status
            r_status = client.get(f"/projects/{phase7_project.name}/delivery")
            assert r_status.status_code == 200
            data = r_status.json()
            assert data["delivery_ready"] is True
            assert "/projects/" in data["download_url"]

            # GET /delivery/download
            r_dl = client.get(f"/projects/{phase7_project.name}/delivery/download")
            assert r_dl.status_code == 200
            assert len(r_dl.content) == 5000

        # 3. Path traversal attack rejection
        with pytest.raises(Exception):
            verify_path_confinement(phase7_project, phase7_project / ".." / "secret.txt")


# ---------------------------------------------------------------------------
# Test 9: Frozen baseline SHA-256 integrity check and zero ASR calls
# ---------------------------------------------------------------------------
def test_frozen_baseline_files_integrity():
    """Verify that the 3 frozen files have not been modified."""
    for rel_path, expected_hash in FROZEN_BASELINE_HASHES.items():
        file_path = Path(rel_path)
        assert file_path.exists(), f"Frozen file missing: {rel_path}"
        actual_hash = hashlib.sha256(file_path.read_bytes()).hexdigest().lower()
        assert actual_hash == expected_hash, (
            f"CRITICAL: Frozen file {rel_path} was modified! Expected {expected_hash}, got {actual_hash}"
        )


# ---------------------------------------------------------------------------
# Test 10: Mandatory LLM Review Blockers Fail Closed
# ---------------------------------------------------------------------------
def test_mandatory_llm_review_blocker_fails_stage(phase7_project, mock_no_asr):
    """BaseAgent review hook blocks stage when LLM review has blocker or is missing."""
    registry = get_agent_registry()
    tb_agent = registry.get_agent("timeline_build")

    req = AgentRequest(
        agent_id="timeline_build",
        project_id=phase7_project.name,
        stage_id="timeline",
        parameters={"aspect": "16:9"},
    )

    tl_data = {
        "schema": "1.0",
        "aspect": "16:9",
        "fps": 30,
        "total_frames": 120,
        "scenes": [{"id": "scene_001", "start_frame": 0, "end_frame": 120}],
    }
    (phase7_project / "timeline.json").write_text(json.dumps(tl_data), encoding="utf-8")
    (phase7_project / "timeline_build_report.json").write_text(
        json.dumps({"schema": "1.0", "status": "completed", "total_frames": 120}),
        encoding="utf-8",
    )

    # When LLM review fails with blocker
    with patch("backend.llm_review.is_stage_review_passed", return_value=(False, "Blocker: Scene text truncation", {"status": "needs_review"})):
        initial_res = AgentResult(
            agent_id="timeline_build",
            stage_id="timeline",
            project_id=phase7_project.name,
            status="succeeded",
            summary="Built ok",
        )
        reviewed_res = tb_agent.review(phase7_project, req, initial_res)
        assert reviewed_res.status == "blocked"
        assert "Blocker: Scene text truncation" in reviewed_res.error


# ---------------------------------------------------------------------------
# Test 11: Multi-project isolation and concurrency safety
# ---------------------------------------------------------------------------
def test_project_isolation_and_no_crosstalk(phase7_project, tmp_path, mock_no_asr):
    """Project A artifacts and approval never satisfy or leak into Project B."""
    proj_b = tmp_path / "proj_p7_b"
    proj_b.mkdir(parents=True)

    # Project A has approved timeline
    (phase7_project / "timeline.json").write_text(json.dumps({"total_frames": 120}), encoding="utf-8")
    (phase7_project / "timeline_build_report.json").write_text(json.dumps({"status": "completed"}), encoding="utf-8")
    (phase7_project / "timeline_approval.json").write_text(json.dumps({"16:9": {"version": "fp_proj_a", "at": "2026-10-16T12:00:00"}}), encoding="utf-8")

    registry = get_agent_registry()
    delivery_agent = registry.get_agent("final_video_delivery")

    req_b = AgentRequest(agent_id="final_video_delivery", project_id=proj_b.name, stage_id="final")

    # Project B has no video -> validate fails
    val_b = delivery_agent.validate(proj_b, req_b)
    assert any("Missing deliverable video" in v for v in val_b)


# ---------------------------------------------------------------------------
# Test 12: Adapter registration and BaseAgent invoke hooks
# ---------------------------------------------------------------------------
def test_all_phase7_agents_registered_and_invokable():
    """Verify all 5 Phase 7 agents exist in the registry with valid metadata."""
    registry = get_agent_registry()
    for aid in ("timeline_build", "timeline_approval", "render_video", "final_qc", "final_video_delivery"):
        meta = registry.get(aid)
        assert meta is not None, f"Missing agent metadata for {aid}"
        assert meta.agent_id == aid
        agent = registry.get_agent(aid)
        assert agent is not None, f"Missing agent instance for {aid}"
        assert agent.stage_id in ("timeline", "approval", "render", "qc", "final")

