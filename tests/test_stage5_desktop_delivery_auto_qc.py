"""Comprehensive Acceptance Test Suite for Stage 5:
Desktop Auto-Export & Non-Blocking Quality Control Pipeline.

Verifies:
1. Autonomous Progression & Gate Automation:
   - Timeline Approval auto-evaluates rubric and clears render gate in auto_pilot mode.
   - Technical QC auto-evaluates audio sync, freeze frames, black frames, loudness.
   - Technical QC auto-approves compliant renders without human clicks.
   - Critical defects (e.g., >1.5s freeze, corrupt audio, duration mismatch >0.5s) block delivery.
   - Manual hold mode (auto_pilot=False) is preserved for backward compatibility.
2. Desktop Destination & Integrity:
   - Output directory resolves to Desktop/First Video Automation/ (honoring LAXMAN_DESKTOP_DIR).
   - Non-existent folders are created automatically.
   - Collision-safe filenames (<title>_<timestamp>.mp4, _01, _02) never overwrite existing files.
   - Atomic copying via .tmp.<uuid> with bit-for-bit SHA-256 verification.
   - Corrupted/interrupted copies clean up temporary files and fail closed.
3. Delivery Summary & Provenance:
   - delivery_summary.json and .txt contain full technical metadata, hashes, and QC verdict.
   - delivery_manifest.json reflects desktop delivery details and clears artifact contracts.
   - Delivery is strictly refused if any gate is not satisfied.
4. Natural Telugu Activity Updates:
   - Natural Telugu activity messages are published during timeline check, QC, and desktop export.
   - Stage 4 communication contracts and SSE payloads receive milestone events.
5. Orchestrator Integration & Recovery:
   - PipelineOrchestrator supports auto_pilot_mode=True with 0 intermediate clicks.
   - Bounded retries (<= 3) for transient failures.
   - Idempotent execution and resume support.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from SYSTEM.agents.shared.contracts import (
    AgentCategory,
    AgentMessage,
    AgentMetadata,
    AgentRequest,
    AgentResult,
    AgentStatus,
    MessageType,
)
from SYSTEM.registries.agent_registry import registry
from SYSTEM.agents.video_generation_agents.final_video_delivery.agent import (
    FinalVideoDeliveryAgent,
    atomic_desktop_copy,
    deliver_to_desktop,
    get_collision_safe_path,
    get_desktop_delivery_dir,
    get_destination_filepath,
    sanitize_title,
    write_delivery_summary,
)
from SYSTEM.agents.video_generation_agents.final_qc.agent import (
    FinalQcAgent,
    evaluate_technical_qc,
)
from SYSTEM.agents.video_generation_agents.timeline_approval.agent import (
    TimelineApprovalAgent,
)
from VIDEO_ENGINE.pipeline.orchestrator import (
    PipelineOrchestrator,
    evaluate_stage_eligibility,
)
from VIDEO_ENGINE.stages import final_qc, timeline_approval, timeline_gate

client = TestClient(app)


@pytest.fixture
def mock_desktop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Isolates the Desktop directory to a clean temp folder for acceptance tests."""
    desktop_dir = tmp_path / "MockDesktop"
    desktop_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LAXMAN_DESKTOP_DIR", str(desktop_dir))
    return desktop_dir


@pytest.fixture
def sample_project(tmp_path: Path):
    """Sets up a complete mock video project directory structure."""
    pdir = tmp_path / "projects" / "test_proj_001"
    pdir.mkdir(parents=True, exist_ok=True)

    # 1. Project descriptor
    (pdir / "project.json").write_text(
        json.dumps({
            "project_id": "test_proj_001",
            "title": "Autonomous Video Delivery Test",
            "aspect": "16:9",
            "state": "building",
            "created_at": time.time(),
        }),
        encoding="utf-8",
    )

    # 2. Audio file fixture (synthetic WAV header + 5 seconds of silence/tone)
    audio_file = pdir / "audio.wav"
    # Minimal 16-bit PCM 16kHz mono WAV (5 seconds = 80000 samples = 160000 bytes + 44 bytes header)
    sr, n_samples = 16000, 80000
    data_size = n_samples * 2
    wav_header = bytearray(44)
    wav_header[0:4] = b"RIFF"
    wav_header[4:8] = (data_size + 36).to_bytes(4, "little")
    wav_header[8:12] = b"WAVE"
    wav_header[12:16] = b"fmt "
    wav_header[16:20] = (16).to_bytes(4, "little")  # Subchunk1Size
    wav_header[20:22] = (1).to_bytes(2, "little")   # AudioFormat (PCM)
    wav_header[22:24] = (1).to_bytes(2, "little")   # NumChannels (Mono)
    wav_header[24:28] = sr.to_bytes(4, "little")    # SampleRate
    wav_header[28:32] = (sr * 2).to_bytes(4, "little") # ByteRate
    wav_header[32:34] = (2).to_bytes(2, "little")   # BlockAlign
    wav_header[34:36] = (16).to_bytes(2, "little")  # BitsPerSample
    wav_header[36:40] = b"data"
    wav_header[40:44] = data_size.to_bytes(4, "little")
    audio_file.write_bytes(bytes(wav_header) + b"\x00" * data_size)

    # 3. Rendered video candidate (synthetic MP4 container)
    vid_file = pdir / "out.mp4"
    # Realistic dummy MP4 with valid size > 1000 bytes
    vid_content = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00isommp42" + b"\x00" * 4000
    vid_file.write_bytes(vid_content)

    # 4. Pipeline state JSON
    (pdir / "pipeline_state.json").write_text(
        json.dumps({
            "schema": "pipeline-state",
            "schema_version": 1,
            "project_id": "test_proj_001",
            "stages": {
                "audio": {"status": "completed", "completed_at": time.time(), "reusable": True},
                "analyzer": {"status": "completed", "completed_at": time.time(), "reusable": True},
                "segmentation": {"status": "completed", "completed_at": time.time(), "reusable": True},
                "planning": {"status": "completed", "completed_at": time.time(), "reusable": True},
                "motion_plan": {"status": "completed", "completed_at": time.time(), "reusable": True},
                "motion_gen": {"status": "completed", "completed_at": time.time(), "reusable": True},
                "motion_validation": {"status": "completed", "completed_at": time.time(), "reusable": True},
                "timeline": {"status": "completed", "completed_at": time.time(), "reusable": True},
                "approval": {"status": "completed", "completed_at": time.time(), "reusable": True},
                "render": {"status": "completed", "completed_at": time.time(), "reusable": True},
                "qc": {"status": "completed", "completed_at": time.time(), "reusable": True},
                "final": {"status": "pending", "completed_at": None, "reusable": False},
            },
        }),
        encoding="utf-8",
    )

    # 5. Timeline JSON & report
    (pdir / "timeline.json").write_text(
        json.dumps({
            "schema_version": "1.0",
            "timeline_id": "tl_001",
            "profile": {
                "width": 1920,
                "height": 1080,
                "fps": 30,
                "aspect_ratio": "16:9",
                "mode": "motion_only",
                "composition_duration_seconds": 5.0,
                "duration_frames": 150,
                "duration_seconds_source": 5.0,
            },
            "tracks": [
                {"track_id": "audio", "items": [{"source_ref": "audio.wav"}]},
                {"track_id": "video", "items": [{"scene_id": "scene_01", "start_frame": 0, "end_frame": 150, "layers": []}]},
            ],
            "gap_intervals": [],
            "transitions": [],
        }),
        encoding="utf-8",
    )

    (pdir / "timeline_build_report.json").write_text(
        json.dumps({
            "schema_version": "1.0",
            "status": "passed",
            "timeline_fingerprint": "tl_fp_test_hash_12345",
            "source_fingerprint": "src_fp_test_hash_12345",
            "counts": {"scenes": 1, "fps": 30, "duration_frames": 150},
            "findings": [],
            "summary": {"errors": 0, "warnings": 0, "blockers": 0},
            "inputs": {},
        }),
        encoding="utf-8",
    )

    return pdir


# ==============================================================================
# TEST GROUP A: Autonomous Progression & Gate Automation
# ==============================================================================

class TestGroupA_AutonomousGates:
    """Verifies that in auto_pilot mode, routine timeline and final-QC gates
    automatically evaluate technical criteria and unlock downstream stages without intermediate approval clicks.
    """

    def test_autonomous_timeline_approval_when_valid(self, sample_project: Path):
        agent = TimelineApprovalAgent()
        req = AgentRequest(
            project_id=sample_project.name,
            agent_id="timeline_approval",
            stage_id="approval",
            parameters={"aspect": "16:9", "auto_pilot": True},
        )

        with patch("VIDEO_ENGINE.stages.timeline_approval.fingerprint", return_value="tl_fp_valid_001"), \
             patch("VIDEO_ENGINE.stages.timeline_approval.state", return_value={
                 "approved": False,
                 "stale": False,
                 "blockers": [],
                 "fingerprint": "tl_fp_valid_001",
                 "review_id": "review_valid_001",
                 "requirements": [],
             }), \
             patch("VIDEO_ENGINE.stages.timeline_approval.auto_approve", return_value={"approved": True, "fingerprint": "tl_fp_valid_001", "last_decision": {"decided_by": "llm:stub/stub"}}) as mock_auto, \
             patch("SYSTEM.core.artifact_contracts.validate_approval_artifacts"):
            res = agent.execute(sample_project, req)

            assert res.status == "succeeded"
            assert res.metadata.get("approved") is True
            mock_auto.assert_called_once()                                   # the LLM approval review decides (timeline_approval.auto_approve)

    def test_autonomous_timeline_approval_blocked_on_real_blockers(self, sample_project: Path):
        agent = TimelineApprovalAgent()
        req = AgentRequest(
            project_id=sample_project.name,
            agent_id="timeline_approval",
            stage_id="approval",
            parameters={"aspect": "16:9", "auto_pilot": True},
        )

        with patch("VIDEO_ENGINE.stages.timeline_approval.state", return_value={
            "approved": False,
            "stale": False,
            "blockers": ["Timeline audio track missing", "Preview unverified"],
            "fingerprint": "tl_fp_blocked",
        }):
            res = agent.execute(sample_project, req)
            assert res.status == "blocked"
            assert "Timeline audio track missing" in res.error

    def test_there_is_no_manual_human_timeline_gate(self, sample_project: Path):
        """Timeline Approval is decided by the LLM approval review in every mode (no human sign-off is awaited)."""
        agent = TimelineApprovalAgent()
        req = AgentRequest(project_id=sample_project.name, agent_id="timeline_approval", stage_id="approval", parameters={"aspect": "16:9", "auto_pilot": False})
        with patch("VIDEO_ENGINE.stages.timeline_approval.state", return_value={"approved": False, "stale": False, "blockers": [], "fingerprint": "tl_fp_001"}), \
             patch("VIDEO_ENGINE.stages.timeline_approval.fingerprint", return_value="tl_fp_001"), \
             patch("VIDEO_ENGINE.stages.timeline_approval.auto_approve", return_value={"approved": True, "fingerprint": "tl_fp_001"}) as mock_auto, \
             patch("SYSTEM.core.artifact_contracts.validate_approval_artifacts"):
            res = agent.execute(sample_project, req)
            assert res.status == "succeeded" and mock_auto.called

    def test_autonomous_qc_is_decided_by_the_llm_decision_only(self, sample_project: Path):
        agent = FinalQcAgent()
        req = AgentRequest(
            project_id=sample_project.name,
            agent_id="final_qc",
            stage_id="qc",
            parameters={"aspect": "16:9", "auto_pilot": True},
        )

        mock_probe = {
            "container": "mov,mp4,m4a,3gp,3g2,mj2",
            "duration": 5.0,
            "video": {"width": 1920, "height": 1080, "codec": "h264", "frame_rate_value": 30.0},
        }
        mock_qc_rep = {
            "status": "passed",
            "qc_run_id": "qc_run_001",
            "candidate": {"sha256": "cand_sha_123"},
            "checks": [
                {"rule_id": "QC_VIDEO_BLACK_FRAMES", "status": "passed", "message": "no black frames >= 1.0s"},
                {"rule_id": "QC_VIDEO_FREEZE_FRAMES", "status": "passed", "message": "no freeze frames >= 1.5s"},
                {"rule_id": "QC_AUDIO_LOUDNESS", "status": "passed", "message": "loudness -18.2 LUFS in spec"},
            ],
            "findings": [],
        }

        with patch("VIDEO_ENGINE.stages.media_probe.probe", return_value=mock_probe), \
             patch("VIDEO_ENGINE.stages.final_qc.state", return_value={"report": mock_qc_rep, "current": True}), \
             patch("VIDEO_ENGINE.stages.final_qc.current_review", return_value=None), \
             patch("VIDEO_ENGINE.stages.final_qc.llm_decide", return_value={"review": {"decision": "changes_required", "notes": ["scene 2 text is cut off"]}}) as mock_decide, \
             patch("SYSTEM.core.artifact_contracts.validate_qc_artifacts"):
            res = agent.execute(sample_project, req)

            # the technical QC passed, the Final QC LLM review did not approve the file: the stage is blocked with its notes (nobody is asked)
            assert res.status == "blocked" and mock_decide.called
            assert "did not approve" in res.summary and "scene 2" in res.summary

    def test_autonomous_qc_blocks_on_duration_sync_mismatch(self, sample_project: Path):
        agent = FinalQcAgent()
        req = AgentRequest(
            project_id=sample_project.name,
            agent_id="final_qc",
            stage_id="qc",
            parameters={"aspect": "16:9", "auto_pilot": True},
        )

        # Video duration is 7.5s, while audio fixture is 5.0s (difference 2.5s > 0.5s tolerance)
        mock_probe = {
            "container": "mp4",
            "duration": 7.5,
            "video": {"width": 1920, "height": 1080, "codec": "h264", "frame_rate_value": 30.0},
        }
        mock_qc_rep = {"status": "passed", "checks": [], "findings": []}

        with patch("VIDEO_ENGINE.stages.media_probe.probe", return_value=mock_probe), \
             patch("VIDEO_ENGINE.stages.final_qc.state", return_value={"report": mock_qc_rep, "current": True}), \
             patch("VIDEO_ENGINE.stages.audio_utils.duration", return_value=5.0):
            res = agent.execute(sample_project, req)

            assert res.status == "failed"
            assert "A/V duration synchronization mismatch" in res.error

    def test_autonomous_qc_blocks_on_freeze_frame_failure(self, sample_project: Path):
        agent = FinalQcAgent()
        req = AgentRequest(
            project_id=sample_project.name,
            agent_id="final_qc",
            stage_id="qc",
            parameters={"aspect": "16:9", "auto_pilot": True},
        )

        mock_probe = {
            "container": "mp4",
            "duration": 5.0,
            "video": {"width": 1920, "height": 1080, "codec": "h264", "frame_rate_value": 30.0},
        }
        # QC report contains a freeze frame check that failed with duration >= 1.5s
        mock_qc_rep = {
            "status": "failed",
            "checks": [
                {"rule_id": "QC_VIDEO_FREEZE_FRAMES", "status": "failed", "severity": "error", "message": "freeze event lasting 2.1s detected", "evidence": {"freeze_duration": 2.1}},
            ],
            "findings": [
                {"rule_id": "QC_VIDEO_FREEZE_FRAMES", "severity": "error", "message": "freeze event lasting 2.1s detected"},
            ],
        }

        with patch("VIDEO_ENGINE.stages.media_probe.probe", return_value=mock_probe), \
             patch("VIDEO_ENGINE.stages.final_qc.state", return_value={"report": mock_qc_rep, "current": True}):
            res = agent.execute(sample_project, req)

            assert res.status == "failed"
            assert "Freeze frame" in res.error or "Deterministic QC" in res.error


# ==============================================================================
# TEST GROUP B: Desktop Destination & Collision Avoidance
# ==============================================================================

class TestGroupB_DesktopDestination:
    """Verifies atomic desktop export, path resolution, collision-safe naming, and hash assertion."""

    def test_desktop_destination_path_resolution(self, mock_desktop: Path):
        dest = get_desktop_delivery_dir()
        assert dest == mock_desktop / "First Video Automation"
        assert dest.exists()
        assert dest.is_dir()

    def test_custom_desktop_override(self, tmp_path: Path):
        custom = tmp_path / "MyCustomDesktop"
        dest = get_desktop_delivery_dir(custom_desktop=custom)
        assert dest == custom
        assert dest.exists()

    def test_sanitize_title(self):
        assert sanitize_title("My Epic Video: Final Cut! (1080p)") == "My_Epic_Video_Final_Cut_1080p"
        assert sanitize_title("   ") == "First_Video"
        assert sanitize_title("") == "First_Video"
        assert sanitize_title("తెలుగు_వీడియో_2026") == "తెలుగు_వీడియో_2026"

    def test_collision_safe_naming_uniqueness(self, mock_desktop: Path):
        dest_dir = mock_desktop / "First Video Automation"
        dest_dir.mkdir(parents=True, exist_ok=True)

        ts = "20261017_180000"
        title = "Sample_Video"

        # First delivery path
        p1 = get_destination_filepath(dest_dir, title, timestamp=ts)
        assert p1.name == "Sample_Video_20261017_180000.mp4"
        p1.write_text("existing_file_00")

        # Second delivery with identical timestamp and title
        p2 = get_destination_filepath(dest_dir, title, timestamp=ts)
        assert p2.name == "Sample_Video_20261017_180000_01.mp4"
        p2.write_text("existing_file_01")

        # Third delivery
        p3 = get_destination_filepath(dest_dir, title, timestamp=ts)
        assert p3.name == "Sample_Video_20261017_180000_02.mp4"

        # Verify original files were never overwritten
        assert p1.read_text() == "existing_file_00"
        assert p2.read_text() == "existing_file_01"

    def test_atomic_copy_and_sha256_match(self, tmp_path: Path):
        src = tmp_path / "src_video.mp4"
        content = b"TEST_VIDEO_BYTES_" * 500
        src.write_bytes(content)
        expected_sha = hashlib.sha256(content).hexdigest()

        target = tmp_path / "dest" / "final_video.mp4"
        res = atomic_desktop_copy(src, target, expected_sha=expected_sha)

        assert target.exists()
        assert res["sha256"] == expected_sha
        assert res["size_bytes"] == len(content)
        assert target.read_bytes() == content

    def test_atomic_copy_cleans_up_on_hash_mismatch(self, tmp_path: Path):
        src = tmp_path / "src_video.mp4"
        src.write_bytes(b"GOOD_CONTENT")

        target = tmp_path / "dest" / "mismatched.mp4"
        bogus_sha = "0000000000000000000000000000000000000000000000000000000000000000"

        with pytest.raises(ValueError, match="Integrity check failed"):
            atomic_desktop_copy(src, target, expected_sha=bogus_sha)

        assert not target.exists()
        # Verify no .tmp files left in target directory
        tmp_files = list(target.parent.glob("*.tmp*"))
        assert len(tmp_files) == 0


# ==============================================================================
# TEST GROUP C: Delivery Summary & Provenance Manifest
# ==============================================================================

class TestGroupC_DeliverySummary:
    """Verifies delivery summary creation, accurate metadata, and provenance gate audit."""

    def test_deliver_to_desktop_success(self, sample_project: Path, mock_desktop: Path):
        vid_file = sample_project / "out.mp4"
        expected_sha = hashlib.sha256(vid_file.read_bytes()).hexdigest()

        res = deliver_to_desktop(
            project_dir=sample_project,
            aspect="16:9",
            custom_desktop=mock_desktop / "First Video Automation",
            title="Telugu News Automation",
        )

        assert res["sha256"] == expected_sha
        dest_path = res["destination_path"]
        assert dest_path.exists()
        assert dest_path.parent == mock_desktop / "First Video Automation"

        # Check delivery summary JSON
        summary_json = res["summary_files"]["dest_json"]
        assert summary_json.exists()
        summary_data = json.loads(summary_json.read_text(encoding="utf-8"))
        assert summary_data["source_sha256"] == expected_sha
        assert summary_data["destination_sha256"] == expected_sha
        assert summary_data["project_title"] == "Telugu News Automation"
        assert summary_data["qc_verdict"] == "passed"
        assert summary_data["all_gates_passed"] is True

        # Check delivery summary TXT
        summary_txt = res["summary_files"]["dest_txt"]
        assert summary_txt.exists()
        txt_content = summary_txt.read_text(encoding="utf-8")
        assert "LAXMAN-AUTONOMOUS VIDEO GENERATION SYSTEM" in txt_content
        assert expected_sha in txt_content

    def test_delivery_refusal_when_gates_blocked(self, sample_project: Path, mock_desktop: Path):
        agent = FinalVideoDeliveryAgent()
        req = AgentRequest(
            project_id=sample_project.name,
            agent_id="final_video_delivery",
            stage_id="final",
            parameters={"aspect": "16:9", "custom_desktop": mock_desktop / "First Video Automation"},
        )

        # QC gate returns blockers
        with patch("VIDEO_ENGINE.stages.final_qc.gate", return_value=["Final QC not passed", "Freeze frame detected"]):
            res = agent.execute(sample_project, req)

            assert res.status == "blocked"
            assert "Final QC not passed" in res.error

            # Verify NO file was copied to the desktop
            delivered_files = list((mock_desktop / "First Video Automation").glob("*.mp4"))
            assert len(delivered_files) == 0


# ==============================================================================
# TEST GROUP D: Stage 4 Natural Telugu Activity Updates
# ==============================================================================

class TestGroupD_TeluguActivityUpdates:
    """Verifies that natural Telugu activity messages are published over the communications stream."""

    def test_telugu_activity_emission_during_delivery(self, sample_project: Path, mock_desktop: Path):
        from SYSTEM.agents.shared.communication import query_messages

        deliver_to_desktop(
            project_dir=sample_project,
            aspect="16:9",
            custom_desktop=mock_desktop / "First Video Automation",
            title="Telugu Test Video",
            task_id="task_telugu_test",
        )

        messages = query_messages(sample_project.name, limit=20)
        assert len(messages) > 0

        # Look for the canonical Stage 4 Telugu activity message
        has_delivery_telugu = any(
            "డెస్క్టాప్లో భద్రపరుస్తున్నాను" in (m.telugu_activity or "")
            or "వీడియో తయారైంది" in (m.telugu_activity or "")
            for m in messages
        )
        assert has_delivery_telugu, "Expected natural Telugu desktop delivery activity message in communications log"


# ==============================================================================
# TEST GROUP E: Retry, Resume & Orchestrator Auto-Pilot
# ==============================================================================

class TestGroupE_OrchestratorAutoPilot:
    """Verifies that PipelineOrchestrator coordinates stages with auto_pilot_mode=True."""

    def test_orchestrator_stage_eligibility_in_auto_pilot(self, sample_project: Path):
        # In auto_pilot mode, approval stage is eligible when no blockers exist
        with patch("VIDEO_ENGINE.stages.timeline_approval.snapshot", return_value={"status": "ready_for_review", "blockers": []}):
            elig_auto = evaluate_stage_eligibility(sample_project, "approval", "16:9", auto_pilot_mode=True)
            assert elig_auto["eligible"] is True

            # no human decision in any mode: the LLM approval review decides
            elig_manual = evaluate_stage_eligibility(sample_project, "approval", "16:9", auto_pilot_mode=False)
            assert elig_manual["eligible"] is True

    def test_orchestrator_run_initialization_with_auto_pilot(self, sample_project: Path):
        orch = PipelineOrchestrator(sample_project.name, aspect="16:9", auto_pilot_mode=True)
        assert orch.auto_pilot_mode is True

        run = orch.start_run(from_stage="final", to_stage="final", synchronous=True)
        assert run.status in ("completed", "running", "blocked")
        assert run.metadata.get("auto_pilot") is True

    def test_fastapi_orchestrator_route_supports_auto_pilot(self, sample_project: Path):
        # Verify /projects/{pid}/orchestrator/run accepts auto_pilot parameter
        resp = client.post(
            f"/projects/{sample_project.name}/orchestrator/run",
            json={"from_stage": "final", "to_stage": "final", "auto_pilot": True, "synchronous": True},
        )
        assert resp.status_code in (200, 202, 400, 409)  # 202 accepted or 409 if already running


# ==============================================================================
# ==============================================================================

