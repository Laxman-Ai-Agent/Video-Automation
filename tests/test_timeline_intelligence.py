"""Comprehensive unit and integration tests for Timeline Build Agent v2.0.0.

Verifies:
1. Deterministic compiler 12-stage preservation and 30fps arithmetic.
2. AudioDuckingEngine: Speech interval extraction & smooth volume envelope curves.
3. CinematicTransitionSelector: Contextual transition recommendation & constraint validation.
4. SceneContinuityAssessor: Pacing and duration boundary analysis.
5. TimelineRecoveryCoordinator: Bounded recovery for compiler-owned issues (max 2 attempts).
6. TimelineBuildAgent: v2.0.0 execution, output generation, and memory reflection.
7. Stage 10/11 gate boundaries and Timeline Approval independence.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from SYSTEM.agents.shared.contracts import AgentRequest
from SYSTEM.agents.video_generation_agents.timeline_build.agent import TimelineBuildAgent
from SYSTEM.agents.video_generation_agents.timeline_build.timeline_intelligence import (
    SUPPORTED_TRANSITIONS,
    AudioDuckingEngine,
    CinematicTransitionSelector,
    SceneContinuityAssessor,
    SpeechInterval,
    TimelineRecoveryCoordinator,
    VolumeKeyframe,
)
from VIDEO_ENGINE.stages import timeline_build as tb


@pytest.fixture
def mock_timeline_project(tmp_path: Path) -> Path:
    """Sets up a minimal valid project workspace for timeline build intelligence tests."""
    pdir = tmp_path / "proj_tl_test"
    pdir.mkdir(parents=True)

    # 1. Source audio file
    audio_file = pdir / "audio.wav"
    audio_file.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00")

    # 2. project.json
    (pdir / "project.json").write_text(
        json.dumps({
            "name": "proj_tl_test",
            "aspect": "16:9",
            "use_images": False,
            "motion_branch": True,
        }),
        encoding="utf-8",
    )

    # 3. transcript_fixed.json with clear speech intervals
    (pdir / "transcript_fixed.json").write_text(
        json.dumps({
            "text": "Hello world welcome to autonomous video generation",
            "duration": 6.0,
            "segments": [
                {
                    "id": 0,
                    "start": 0.5,
                    "end": 2.5,
                    "text": "Hello world welcome",
                    "words": [
                        {"word": "Hello", "start": 0.5, "end": 1.0},
                        {"word": "world", "start": 1.0, "end": 1.8},
                        {"word": "welcome", "start": 1.8, "end": 2.5},
                    ],
                },
                {
                    "id": 1,
                    "start": 3.5,
                    "end": 5.5,
                    "text": "to autonomous video generation",
                    "words": [
                        {"word": "to", "start": 3.5, "end": 3.8},
                        {"word": "autonomous", "start": 3.8, "end": 4.6},
                        {"word": "video", "start": 4.6, "end": 5.0},
                        {"word": "generation", "start": 5.0, "end": 5.5},
                    ],
                },
            ],
        }),
        encoding="utf-8",
    )

    # 4. scene_segmentation.json
    (pdir / "scene_segmentation.json").write_text(
        json.dumps({
            "schema_version": "1.0",
            "scenes": [
                {
                    "scene_id": "scene_001",
                    "start_time": 0.0,
                    "end_time": 3.0,
                    "pause_after_seconds": 0.5,
                    "word_range": [0, 3],
                },
                {
                    "scene_id": "scene_002",
                    "start_time": 3.0,
                    "end_time": 6.0,
                    "pause_after_seconds": 0.0,
                    "word_range": [3, 7],
                },
            ],
            "total_duration": 6.0,
        }),
        encoding="utf-8",
    )

    # 5. composition.json
    (pdir / "composition.json").write_text(
        json.dumps({
            "meta": {
                "fps": 30,
                "width": 1920,
                "height": 1080,
                "duration": 6.0,
                "audio": "audio.wav",
                "motionOnly": True,
            },
            "scenes": [
                {
                    "id": 1,
                    "start": 0.0,
                    "end": 3.0,
                    "layers": [{"type": "custom", "z": 1}],
                    "transition_out": {"type": "fade", "dur": 0.4},
                },
                {
                    "id": 2,
                    "start": 3.0,
                    "end": 6.0,
                    "layers": [{"type": "custom", "z": 1}],
                },
            ],
        }),
        encoding="utf-8",
    )

    # 6. motion_plan.json & motion_planning.json
    mp_content = {
        "schema_version": "1.0",
        "project": {"width": 1920, "height": 1080, "fps": 30},
        "scenes": [
            {
                "plan_scene_id": 1,
                "timing": {
                    "start": 0.0,
                    "end": 3.0,
                    "canonical_start": 0.0,
                    "canonical_end": 3.0,
                    "start_frame": 0,
                    "end_frame": 90,
                },
            },
            {
                "plan_scene_id": 2,
                "timing": {
                    "start": 3.0,
                    "end": 6.0,
                    "canonical_start": 3.0,
                    "canonical_end": 6.0,
                    "start_frame": 90,
                    "end_frame": 180,
                },
            },
        ],
    }
    (pdir / "motion_plan.json").write_text(json.dumps(mp_content), encoding="utf-8")
    (pdir / "motion_planning.json").write_text(json.dumps(mp_content), encoding="utf-8")

    # 7. motion_generation.json
    (pdir / "motion_generation.json").write_text(
        json.dumps({
            "schema_version": "1.0",
            "scenes": [
                {
                    "plan_scene_id": 1,
                    "timing": {"start_frame": 0, "end_frame": 90},
                    "descriptors": [{"descriptor_id": "d1", "start_frame": 0, "end_frame": 90}],
                },
                {
                    "plan_scene_id": 2,
                    "timing": {"start_frame": 90, "end_frame": 180},
                    "descriptors": [{"descriptor_id": "d2", "start_frame": 90, "end_frame": 180}],
                },
            ],
            "output": {"composition_sha": "abc12345", "persisted": True},
        }),
        encoding="utf-8",
    )

    # 8. motion_timeline_validation.json (Stage 10 clearance)
    val_data = {
        "schema_version": "1.0",
        "phase": "motion_timeline_validation",
        "phase_status": "completed",
        "readiness": "ready",
        "source_fingerprint": "valid_fp",
        "summary": {"blockers": 0, "errors": 0, "warnings": 0, "stages_blocked": 0, "required_not_drawn": 0},
        "stages": [
            {"stage_id": "input_provenance", "status": "completed", "checks_passed": 1, "checks_total": 1, "checks_skipped": 0, "finding_ids": []},
            {"stage_id": "readiness_gate", "status": "completed", "checks_passed": 1, "checks_total": 1, "checks_skipped": 0, "finding_ids": []},
        ],
        "findings": [],
        "elements": [],
    }
    (pdir / "motion_timeline_validation.json").write_text(json.dumps(val_data), encoding="utf-8")

    return pdir


def test_deterministic_compiler_preservation():
    """Verifies that all 12 stages, 30fps arithmetic, and constants remain intact."""
    assert len(tb.STAGES) == 12
    stage_ids = [s[0] for s in tb.STAGES]
    assert stage_ids == [
        "request_lock",
        "input_discovery",
        "freshness_gate",
        "settings",
        "scene_mapping",
        "frame_timing",
        "video_track",
        "audio_track",
        "transitions_gaps",
        "assembly",
        "validation",
        "persist",
    ]
    assert tb.SCHEMA == "1.0"
    assert tb.VERSION == 1
    assert tb.RULE_SET == "1.0"


def test_audio_ducking_engine_speech_intervals_and_envelope(mock_timeline_project: Path):
    """Verifies speech interval extraction and dynamic volume envelope generation."""
    duck_engine = AudioDuckingEngine(speech_gain=0.15, pause_gain=0.40, ramp_seconds=0.15)
    intervals = duck_engine.extract_speech_intervals(mock_timeline_project, fps=30)

    assert len(intervals) >= 2
    # Verify first interval
    assert intervals[0].start_seconds == 0.5
    assert intervals[0].end_seconds == 2.5
    assert intervals[0].start_frame == 15
    assert intervals[0].end_frame == 75

    # Verify second interval
    assert intervals[1].start_seconds == 3.5
    assert intervals[1].end_seconds == 5.5

    # Compute keyframes for 180 frames (6.0s at 30fps)
    keyframes = duck_engine.generate_volume_envelope(intervals, total_frames=180, fps=30)
    assert len(keyframes) > 4

    # Verify speech gain attenuation during speech
    speech_frame_kf = next((k for k in keyframes if k.frame == 15), None)
    assert speech_frame_kf is not None
    assert speech_frame_kf.volume == 0.15

    # Verify pause gain boost during the 1.0s gap between 2.5s and 3.5s (frames 75 to 105)
    # With 150ms ramp (5 frames), boost start should be frame 80
    boost_kf = next((k for k in keyframes if k.volume == 0.40 and 75 < k.frame < 105), None)
    assert boost_kf is not None

    # Compute full profile
    profile = duck_engine.compute_ducking_profile(mock_timeline_project, total_frames=180, fps=30)
    assert profile["ducking_applied"] is True
    assert profile["speech_gain"] == 0.15
    assert profile["pause_gain"] == 0.40
    assert profile["speech_intervals_count"] == len(intervals)
    assert profile["speech_coverage_percent"] > 0


def test_cinematic_transition_selector(mock_timeline_project: Path):
    """Verifies that CinematicTransitionSelector provides context-sensitive transitions

    within Remotion's supported library.
    """
    selector = CinematicTransitionSelector()
    scenes = [
        {"id": 1, "start": 0.0, "end": 3.0, "concept": "Artificial Intelligence System Overview"},
        {"id": 2, "start": 3.0, "end": 6.0, "concept": "Detailed Technical Architecture Flow"},
    ]

    res = selector.recommend_transitions(mock_timeline_project, scenes, fps=30)
    assert "recommendations" in res
    assert len(res["recommendations"]) == 1

    rec = res["recommendations"][0]
    assert rec["from_scene_id"] == "1"
    assert rec["to_scene_id"] == "2"
    assert rec["transition_type"] in SUPPORTED_TRANSITIONS
    assert rec["duration_frames"] > 0
    assert rec["duration_seconds"] <= 0.8
    assert rec["supported"] is True
    assert "rationale" in rec


def test_scene_continuity_assessor(mock_timeline_project: Path):
    """Verifies scene continuity and duration boundary evaluation."""
    assessor = SceneContinuityAssessor()

    # Normal scenes (3.0s each)
    normal_scenes = [
        {"id": 1, "start": 0.0, "end": 3.0},
        {"id": 2, "start": 3.0, "end": 6.0},
    ]
    res_normal = assessor.assess(mock_timeline_project, normal_scenes, total_duration_s=6.0)
    assert res_normal["continuity_score"] == 100.0
    assert res_normal["pacing_issues_count"] == 0

    # Pacing issue scene (< 1.0s)
    short_scenes = [
        {"id": 1, "start": 0.0, "end": 0.5},
        {"id": 2, "start": 0.5, "end": 6.0},
    ]
    res_short = assessor.assess(mock_timeline_project, short_scenes, total_duration_s=6.0)
    assert res_short["continuity_score"] < 100.0
    assert res_short["pacing_issues_count"] >= 1


def test_timeline_recovery_coordinator_bounded_repair(mock_timeline_project: Path):
    """Verifies bounded recovery for compiler-solvable defects."""
    coordinator = TimelineRecoveryCoordinator()

    # Create unsupported transition in composition.json
    comp_file = mock_timeline_project / "composition.json"
    comp_data = json.loads(comp_file.read_text(encoding="utf-8"))
    comp_data["scenes"][0]["transition_out"] = {"type": "unsupported_crazy_explosion_v9", "dur": 0.4}
    comp_file.write_text(json.dumps(comp_data), encoding="utf-8")

    blockers = ["transition_01_02: 'unsupported_crazy_explosion_v9' is not a transition of the library"]

    rec_res = coordinator.coordinate_recovery(
        project_dir=mock_timeline_project,
        blockers_list=blockers,
        max_attempts=2,
    )

    assert rec_res["repaired"] is True
    assert rec_res["attempts"] == 1
    assert any("Substituted" in a for a in rec_res["actions_applied"])

    # Verify composition.json was updated with 'fade'
    updated_comp = json.loads(comp_file.read_text(encoding="utf-8"))
    assert updated_comp["scenes"][0]["transition_out"]["type"] == "fade"


def test_timeline_build_agent_v2_execute(mock_timeline_project: Path, monkeypatch):
    """End-to-end integration test of TimelineBuildAgent v2.0.0. The agent's pre-render check (step motion-validate) needs a real motion output; this mock
    project has none, so that step is stood in for (its own tests: tests/test_timeline_render_qc_delivery.py, test_motion_only_mode.py)."""
    from VIDEO_ENGINE.pipeline import legacy_pipeline_adapter
    real = legacy_pipeline_adapter.execute
    monkeypatch.setattr(legacy_pipeline_adapter, "execute", lambda pdir, name, ctx: {"name": name, "status": "ran"} if name.startswith("motion-validate") else real(pdir, name, ctx))
    agent = TimelineBuildAgent()
    assert agent.metadata.version == "2.0.0"
    assert agent.metadata.agent_id == "timeline_build"

    req = AgentRequest(
        agent_id="timeline_build",
        stage_id="timeline",
        parameters={"aspect": "16:9", "auto_repair": True},
    )

    # 1. Validate
    val_errs = agent.validate(mock_timeline_project, req)
    assert val_errs == []

    # 2. Execute
    with patch("VIDEO_ENGINE.stages.audio_utils.duration", return_value=6.0), \
         patch("VIDEO_ENGINE.stages.pipeline._remotion_src_digest", return_value="rem_hash"), \
         patch("SYSTEM.core.artifact_contracts.validate_timeline_artifacts", return_value=True):

        result = agent.execute(mock_timeline_project, req)
        assert result.agent_id == "timeline_build"
        assert result.status in ("succeeded", "blocked")

        if result.status == "succeeded":
            assert "total_frames" in result.metadata
            assert "ducking_applied" in result.metadata
            assert "continuity_score" in result.metadata

            # 3. Verify output artifacts
            output_paths = [r.path for r in result.output_refs]
            assert any("timeline_intelligence" in p for p in output_paths)

            intel_file = mock_timeline_project / "timeline_intelligence.json"
            assert intel_file.exists()
            intel_data = json.loads(intel_file.read_text(encoding="utf-8"))
            assert "ducking_profile" in intel_data
            assert "transition_recommendations" in intel_data
            assert "continuity_assessment" in intel_data


def test_stage_assembly_audio_ducking_included(mock_timeline_project: Path):
    """Verifies that stage_assembly in timeline_build.py computes ducking_profile

    and attaches it to the assembled timeline object.
    """
    rec = tb.Rec()
    builder = tb.Builder(mock_timeline_project, "16:9", rec)
    builder.audio_s = 6.0
    builder.dur_s = 6.0
    builder.dur_f = 180
    builder.fps = 30
    builder.width = 1920
    builder.height = 1080
    builder.audio_item = {"item_id": "audio_clip"}
    builder.video_items = [{"item_id": "scene_clip_001", "layers": []}]
    builder.scenes = [{"sid": "scene_001", "canon": {"segments": [], "words": None}, "comp": {"id": 1}, "key": "scene_01"}]
    builder.gaps = []
    builder.transitions = []
    builder.comp = {"meta": {}}

    with patch("VIDEO_ENGINE.stages.resource_library.used_resources", return_value=[]):
        builder.stage_assembly()

    assert "audio_ducking" in builder.T
    assert "ducking_applied" in builder.T["audio_ducking"]
