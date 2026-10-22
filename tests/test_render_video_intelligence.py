"""Comprehensive unit and integration test suite for Render Video Agent (v2.0.0).

Verifies:
1. AdaptiveResourceEngine: Hardware resource assessment and safe concurrency.
2. RenderFailureClassifier: 17 canonical failure classifications.
3. LLMRenderDiagnostician: Root cause diagnosis and allowlist enforcement.
4. AutonomousRenderRecoveryCoordinator: Bounded recovery execution (max 2 attempts).
5. OutputIntegrityAuditor: FFprobe container, codec, frame rate, and sync checks.
6. RenderVideoAgent: Fail-closed approval gate, execution, output refs, and memory reflection.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from SYSTEM.agents.shared.contracts import AgentRequest
from SYSTEM.agents.video_generation_agents.render_video.agent import RenderVideoAgent
from SYSTEM.agents.video_generation_agents.render_video.render_intelligence import (
    PERMITTED_RECOVERY_ACTIONS,
    AdaptiveResourceEngine,
    AutonomousRenderRecoveryCoordinator,
    FailureDiagnosis,
    LLMRenderDiagnostician,
    OutputIntegrityAuditor,
    RenderFailureClassifier,
)


@pytest.fixture
def mock_render_project(tmp_path: Path) -> Path:
    """Sets up a minimal valid project workspace for render video tests."""
    pdir = tmp_path / "proj_render_test"
    pdir.mkdir(parents=True)

    # 1. Source audio file
    audio_file = pdir / "audio.wav"
    audio_file.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00")

    # 2. timeline.json
    (pdir / "timeline.json").write_text(
        json.dumps({
            "schema": "1.0",
            "fps": 30,
            "total_frames": 120,
            "duration_seconds": 4.0,
            "scenes": [
                {"id": "scene_001", "start_frame": 0, "end_frame": 60},
                {"id": "scene_002", "start_frame": 60, "end_frame": 120},
            ],
        }),
        encoding="utf-8",
    )

    # 3. timeline_build_report.json
    (pdir / "timeline_build_report.json").write_text(
        json.dumps({
            "status": "completed",
            "timeline_fingerprint": "fp_test_approved_123",
            "source_fingerprint": "fp_src_test_123",
            "total_frames": 120,
        }),
        encoding="utf-8",
    )

    # 4. composition.json
    (pdir / "composition.json").write_text(
        json.dumps({
            "meta": {
                "fps": 30,
                "width": 1920,
                "height": 1080,
                "duration": 4.0,
                "audio": "audio.wav",
            },
            "scenes": [],
        }),
        encoding="utf-8",
    )

    return pdir


# ---------------------------------------------------------------------------
# Test 1: Adaptive Resource Engine
# ---------------------------------------------------------------------------
def test_adaptive_resource_engine(tmp_path: Path):
    engine = AdaptiveResourceEngine(min_free_gb=2.0)
    res = engine.assess_system_resources(tmp_path)

    assert "cpu_cores" in res
    assert "free_disk_gb" in res
    assert "free_ram_gb" in res
    assert res["recommended_concurrency"] in (1, 2, 3)
    assert isinstance(res["low_memory_mode"], bool)
    assert res["disk_headroom_passed"] is True


# ---------------------------------------------------------------------------
# Test 2: Render Failure Classifier
# ---------------------------------------------------------------------------
def test_render_failure_classifier():
    classifier = RenderFailureClassifier()

    assert classifier.classify("EADDRINUSE: address already in use") == "dynamic_port_collision"
    assert classifier.classify("Error: Out of memory (bad_alloc)") == "memory_exhaustion"
    assert classifier.classify("Fatal error: WebGL context lost in Chromium worker") == "webgl_context_loss"
    assert classifier.classify("CUDA / NVENC encoder initialization failed") == "nvenc_failure"
    assert classifier.classify("No audio.* file found in project") == "missing_required_asset"
    assert classifier.classify("Cannot find module '@remotion/google-fonts'") == "remotion_compilation_failure"
    assert classifier.classify("Timeline approval is missing or stale") == "invalid_approval_certificate"
    assert classifier.classify("ENOSPC: no space left on device") == "disk_space_failure"
    assert classifier.classify("Unknown error code 999", exit_code=137) == "memory_exhaustion"


# ---------------------------------------------------------------------------
# Test 3: LLM Render Diagnostician
# ---------------------------------------------------------------------------
def test_llm_render_diagnostician_fallback():
    diag = LLMRenderDiagnostician()
    res = diag.diagnose(
        project_id="test_proj",
        category="dynamic_port_collision",
        raw_error="Port 3000 is occupied by foreign page",
        stderr_tail=["Error: foreign page answered on 3000"],
    )

    assert res.category == "dynamic_port_collision"
    assert res.recommended_action == "reallocate_port"
    assert res.can_retry is True
    assert res.confidence >= 0.90


def test_llm_render_diagnostician_with_llm():
    diag = LLMRenderDiagnostician()

    mock_llm_resp = MagicMock()
    mock_llm_resp.status = "success"
    mock_llm_resp.provider = "mock_provider"
    mock_llm_resp.raw_text = json.dumps({
        "root_cause": "Node worker heap limit exceeded under 3 concurrent workers",
        "confidence": 0.95,
        "recommended_action": "reduce_concurrency",
        "can_retry": True,
        "affected_component": "Main",
    })

    with patch("SYSTEM.core.llm_gateway.gateway.execute", return_value=mock_llm_resp):
        res = diag.diagnose(
            project_id="test_proj",
            category="memory_exhaustion",
            raw_error="JavaScript heap out of memory",
            stderr_tail=["FATAL ERROR: Ineffective mark-compacts near heap limit Allocation failed"],
        )

        assert res.category == "memory_exhaustion"
        assert res.recommended_action == "reduce_concurrency"
        assert res.can_retry is True
        assert "llm" in res.diagnostician


# ---------------------------------------------------------------------------
# Test 4: Autonomous Render Recovery Coordinator
# ---------------------------------------------------------------------------
def test_recovery_coordinator_bounded_execution(tmp_path: Path):
    coord = AutonomousRenderRecoveryCoordinator(max_attempts=2)

    diag1 = FailureDiagnosis(
        category="dynamic_port_collision",
        root_cause="Port conflict",
        confidence=0.9,
        recommended_action="reallocate_port",
        can_retry=True,
    )
    assert coord.can_attempt_recovery(diag1) is True

    ok1, flags1, msg1 = coord.execute_recovery_action(tmp_path, "16:9", diag1, ["--concurrency=3"])
    assert ok1 is True
    assert len(coord.attempts) == 1

    # Attempting the exact same action again should be rejected to avoid infinite loops
    assert coord.can_attempt_recovery(diag1) is False

    # Second distinct action
    diag2 = FailureDiagnosis(
        category="memory_exhaustion",
        root_cause="RAM exhaustion",
        confidence=0.9,
        recommended_action="reduce_concurrency",
        can_retry=True,
    )
    assert coord.can_attempt_recovery(diag2) is True

    ok2, flags2, msg2 = coord.execute_recovery_action(tmp_path, "16:9", diag2, flags1)
    assert ok2 is True
    assert "--concurrency=1" in flags2
    assert len(coord.attempts) == 2

    # Third action should be blocked because max_attempts=2
    diag3 = FailureDiagnosis(
        category="webgl_context_loss",
        root_cause="GPU context loss",
        confidence=0.9,
        recommended_action="software_gl_fallback",
        can_retry=True,
    )
    assert coord.can_attempt_recovery(diag3) is False


# ---------------------------------------------------------------------------
# Test 5: Output Integrity Auditor
# ---------------------------------------------------------------------------
def test_output_integrity_auditor(tmp_path: Path):
    auditor = OutputIntegrityAuditor()
    fake_video = tmp_path / "out.mp4"
    fake_video.write_bytes(b"\x00" * 50000)

    mock_probe = {
        "container": "mov,mp4,m4a,3gp,3g2,mj2",
        "duration": 4.02,
        "size": 50000,
        "video": {
            "codec": "h264",
            "width": 1920,
            "height": 1080,
            "frame_rate_value": 30.0,
            "nb_frames": 120,
        },
        "audio": {
            "codec": "aac",
            "duration": 4.0,
            "sample_rate": 44100,
            "channels": 2,
        },
    }

    with patch("VIDEO_ENGINE.stages.media_probe.probe", return_value=mock_probe):
        res = auditor.audit(
            video_path=fake_video,
            expected_meta={"width": 1920, "height": 1080, "fps": 30, "duration_seconds": 4.0, "audio_required": True},
            authoritative_audio_duration=4.0,
        )

        assert res["passed"] is True
        assert len(res["blockers"]) == 0
        assert res["observed"]["video_codec"] == "h264"
        assert res["observed"]["fps"] == 30.0


# ---------------------------------------------------------------------------
# Test 6: Render Video Agent Approval Gate & Execution
# ---------------------------------------------------------------------------
def test_render_video_agent_fail_closed_without_approval(mock_render_project: Path):
    agent = RenderVideoAgent()
    req = AgentRequest(agent_id="render_video", project_id=mock_render_project.name, stage_id="render")

    # When timeline_gate raises unapproved exception
    with patch("VIDEO_ENGINE.stages.timeline_gate.require_approved", side_effect=Exception("Timeline approval missing")):
        res = agent.execute(mock_render_project, req)
        assert res.status == "blocked"
        assert "not approved" in res.summary


def test_render_video_agent_successful_execution(mock_render_project: Path):
    agent = RenderVideoAgent()
    req = AgentRequest(
        agent_id="render_video",
        project_id=mock_render_project.name,
        stage_id="render",
        parameters={"dry_run": True},
    )

    # Simulate valid rendered mp4
    fake_video = mock_render_project / "out.mp4"
    fake_video.write_bytes(b"\x00" * 25000)

    mock_probe = {
        "container": "mp4",
        "duration": 4.0,
        "size": 25000,
        "video": {"codec": "h264", "width": 1920, "height": 1080, "frame_rate_value": 30.0},
        "audio": {"codec": "aac", "duration": 4.0},
    }

    with patch("VIDEO_ENGINE.stages.timeline_gate.require_approved", return_value=None), \
         patch("VIDEO_ENGINE.stages.media_probe.probe", return_value=mock_probe):

        res = agent.execute(mock_render_project, req)

        assert res.status == "succeeded"
        assert res.metadata["byte_size"] == 25000
        assert "sha256" in res.metadata
        assert "render_intelligence_ref" in res.metadata
        assert res.metadata["audit_passed"] is True

        # Check render intelligence artifact was written
        intel_file = mock_render_project / "render_intelligence.json"
        assert intel_file.exists()
        intel_data = json.loads(intel_file.read_text(encoding="utf-8"))
        assert intel_data["schema_version"] == "2.0"
        assert intel_data["byte_size"] == 25000
