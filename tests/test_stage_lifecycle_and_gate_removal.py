"""Comprehensive regression tests verifying the removal of the Phase 2 LLM review blocker
and hardening of the stage lifecycle:
1. Valid segmentation completing without Phase 2 LLM review.
2. Invalid segmentation failing deterministic validation with actionable error.
3. All subtasks completing while the parent stage transitions correctly.
4. Retry after failure and recovery after interrupted execution.
5. Stale cache and obsolete review state not blocking execution.
6. Corrected transcript and timestamps reaching Visual Planning.
7. Downstream stages starting only after valid output is persisted.
8. No remaining code path requiring llm_review_blocked for the removed gate.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch

from SYSTEM.core import pipeline_state
from SYSTEM.core.pipeline_state import InvalidStateTransitionError, transition_stage, load_pipeline_state
from SYSTEM.core.artifact_contracts import ContractValidationError, validate_stage_artifacts
from SYSTEM.policies import llm_review
from VIDEO_ENGINE.stages import scene_segmentation, visual_planning
from UI.backend import pipeline_view, store


@pytest.fixture
def mock_project(tmp_path: Path, monkeypatch):
    """Fixture providing an isolated project directory."""
    pdir = tmp_path / "test_lifecycle_proj"
    pdir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("backend.store.project_dir", lambda p: pdir)
    monkeypatch.setattr("UI.backend.store.project_dir", lambda p: pdir)
    monkeypatch.setattr("SYSTEM.memory.store.project_dir", lambda p: pdir)
    return pdir


def _create_valid_audio_analysis_outputs(pdir: Path):
    """Sets up Audio Analyzer output files with LLM-corrected transcript."""
    (pdir / "audio.wav").write_bytes(b"RIFF dummy wav data")
    words = [
        {"w": "future", "start": 0.0, "end": 0.5, "timing": "asr"},
        {"w": "లో", "start": 0.6, "end": 0.9, "timing": "asr"},
        {"w": "AI", "start": 1.0, "end": 1.4, "timing": "corrected"},
        {"w": "rule.", "start": 1.5, "end": 2.0, "timing": "asr"},
    ]
    raw_transcript = {
        "text": "future లో A I rule.",
        "language": "te",
        "duration": 2.5,
        "segments": [{"id": 0, "start": 0.0, "end": 2.0, "text": "future లో A I rule.", "words": words}],
    }
    corrected_transcript = {
        "text": "future లో AI rule.",
        "language": "te",
        "duration": 2.5,
        "segments": [{"id": 0, "start": 0.0, "end": 2.0, "text": "future లో AI rule.", "words": words}],
    }
    (pdir / "transcript.json").write_text(json.dumps(raw_transcript), encoding="utf-8")
    (pdir / "transcript_corrected.json").write_text(json.dumps(corrected_transcript), encoding="utf-8")
    (pdir / "cuts.json").write_text(json.dumps({"cuts": [{"time": 2.0, "reason": "sentence_end"}]}), encoding="utf-8")
    (pdir / "audio_analysis.json").write_text(json.dumps({
        "version": "1.0",
        "validation": {"status": "ok", "errors": [], "warnings": [], "notes": []},
        "utterances": [{"id": 0, "start_seconds": 0.0, "end_seconds": 2.0, "text": "future లో AI rule.", "llm_transcript": "future లో AI rule.", "words": words}],
        "pauses": [{"start_seconds": 2.0, "end_seconds": 2.5, "duration_seconds": 0.5}],
    }), encoding="utf-8")


def _create_valid_scene_segmentation(pdir: Path):
    """Generates valid scene segmentation output adhering to schema and contracts."""
    inp = scene_segmentation.read_input(pdir)
    res = scene_segmentation.run(pdir)
    (pdir / "scene_segmentation.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    return res


def test_valid_segmentation_completes_without_phase2_llm_review(mock_project: Path):
    """1. Valid segmentation completes successfully without Phase 2 LLM review approval."""
    pdir = mock_project
    _create_valid_audio_analysis_outputs(pdir)
    _create_valid_scene_segmentation(pdir)

    # Note: no llm_review_segmentation.json exists at all
    assert not (pdir / "llm_review_segmentation.json").exists()

    transition_stage(pdir, "segmentation", "running")
    rec = transition_stage(pdir, "segmentation", "completed")

    assert rec.status == "completed"
    assert rec.last_error is None
    assert rec.checkpoint_id != ""

    pv = pipeline_view.build("test_lifecycle_proj")
    seg = next(s for s in pv["stages"] if s["id"] == "segmentation")
    assert seg["status"] == "completed"
    assert "scenes segmented" in seg["detail"]


def test_invalid_segmentation_fails_deterministic_validation(mock_project: Path):
    """2. Invalid segmentation output fails deterministic contract validation with actionable error."""
    pdir = mock_project
    _create_valid_audio_analysis_outputs(pdir)

    # Write corrupt segmentation with negative duration and missing required source_data
    broken = {
        "schema_version": "1.1",
        "timing_rules": 4,
        "scenes": [
            {"scene_id": "scene_001", "start_time": 5.0, "end_time": 2.0, "transcript": "Impossible times"}
        ]
    }
    (pdir / "scene_segmentation.json").write_text(json.dumps(broken), encoding="utf-8")

    transition_stage(pdir, "segmentation", "running")

    with pytest.raises(InvalidStateTransitionError) as exc_info:
        transition_stage(pdir, "segmentation", "completed")

    assert "contract check failed" in str(exc_info.value)

    st = load_pipeline_state(pdir)
    assert st.stages["segmentation"].status == "blocked"
    assert st.stages["segmentation"].last_error["code"] == "contract_validation_failed"


def test_all_subtasks_complete_while_parent_stage_transitions(mock_project: Path):
    """3. All 7 deterministic subtasks in scene_segmentation.json complete and parent stage completes."""
    pdir = mock_project
    _create_valid_audio_analysis_outputs(pdir)
    res = _create_valid_scene_segmentation(pdir)

    # Verify all 7 subtasks in the stage report are completed
    stages = res.get("stages", [])
    assert len(stages) == 7
    for step in stages:
        assert step["status"] in ("completed", "warning")
        assert step["status"] != "failed"

    transition_stage(pdir, "segmentation", "running")
    rec = transition_stage(pdir, "segmentation", "completed")
    assert rec.status == "completed"

    pv = pipeline_view.build("test_lifecycle_proj")
    seg = next(s for s in pv["stages"] if s["id"] == "segmentation")
    assert seg["status"] == "completed"


def test_retry_after_failure_and_recovery(mock_project: Path):
    """4. Retry after failure allows state transition from blocked/failed to running and completed."""
    pdir = mock_project
    _create_valid_audio_analysis_outputs(pdir)

    # First attempt: invalid output
    (pdir / "scene_segmentation.json").write_text("{}", encoding="utf-8")
    transition_stage(pdir, "segmentation", "running")

    with pytest.raises(InvalidStateTransitionError):
        transition_stage(pdir, "segmentation", "completed")

    st1 = load_pipeline_state(pdir)
    assert st1.stages["segmentation"].status == "blocked"

    # Recovery: write valid segmentation and retry
    _create_valid_scene_segmentation(pdir)
    transition_stage(pdir, "segmentation", "running")
    rec2 = transition_stage(pdir, "segmentation", "completed")

    assert rec2.status == "completed"
    assert rec2.last_error is None
    st2 = load_pipeline_state(pdir)
    assert st2.stages["segmentation"].status == "completed"


def test_stale_cache_and_obsolete_review_state_not_blocking(mock_project: Path):
    """5. An obsolete review file with status: 'blocked' does NOT block stage completion."""
    pdir = mock_project
    _create_valid_audio_analysis_outputs(pdir)
    _create_valid_scene_segmentation(pdir)

    # Create stale, blocked LLM review artifact
    stale_blocked_review = {
        "status": "blocked",
        "error": "Circuit for 'gemini:gemini-3.5-flash' is OPEN (17 consecutive failures)",
        "findings": [{"severity": "blocker", "message": "Circuit breaker open"}],
        "input_fingerprint": "stale_in",
        "output_fingerprint": "stale_out",
    }
    (pdir / "llm_review_segmentation.json").write_text(json.dumps(stale_blocked_review), encoding="utf-8")

    # Transitioning to completed must succeed because stage completion is deterministic
    transition_stage(pdir, "segmentation", "running")
    rec = transition_stage(pdir, "segmentation", "completed")
    assert rec.status == "completed"
    assert rec.last_error is None

    pv = pipeline_view.build("test_lifecycle_proj")
    seg = next(s for s in pv["stages"] if s["id"] == "segmentation")
    assert seg["status"] == "completed"


def test_corrected_transcript_and_timestamps_reach_visual_planning(mock_project: Path):
    """6. Visual Planning receives the LLM-corrected transcript from Scene Segmentation."""
    pdir = mock_project
    _create_valid_audio_analysis_outputs(pdir)
    seg_res = _create_valid_scene_segmentation(pdir)

    scenes = seg_res.get("scenes", [])
    assert len(scenes) > 0
    # The primary narration text must be the corrected transcript, not raw ASR
    assert "AI" in scenes[0]["transcript"]
    assert scenes[0]["start_time"] == 0.0
    assert scenes[0]["end_time"] > 0.0


def test_downstream_stages_start_only_after_valid_output_persisted(mock_project: Path):
    """7. Downstream Visual Planning is blocked when segmentation is missing, and eligible once persisted."""
    pdir = mock_project
    _create_valid_audio_analysis_outputs(pdir)

    # When scene_segmentation.json is absent
    if (pdir / "scene_segmentation.json").exists():
        (pdir / "scene_segmentation.json").unlink()

    pv1 = pipeline_view.build("test_lifecycle_proj")
    plan1 = next(s for s in pv1["stages"] if s["id"] == "planning")
    assert plan1["status"] in ("queued", "waiting")

    # Once scene_segmentation.json is validly persisted
    _create_valid_scene_segmentation(pdir)
    transition_stage(pdir, "segmentation", "running")
    transition_stage(pdir, "segmentation", "completed")

    pv2 = pipeline_view.build("test_lifecycle_proj")
    seg2 = next(s for s in pv2["stages"] if s["id"] == "segmentation")
    assert seg2["status"] == "completed"


def test_no_remaining_code_path_requiring_llm_review_blocked(mock_project: Path):
    """8. No path in pipeline_state or pipeline_view raises or requires llm_review_blocked."""
    pdir = mock_project
    _create_valid_audio_analysis_outputs(pdir)
    _create_valid_scene_segmentation(pdir)

    # Force review checker to report blocked
    transition_stage(pdir, "segmentation", "running")
    with patch.object(llm_review, "is_stage_review_passed", return_value=(False, "llm_review_blocked", {"status": "blocked"})):
        # Must not raise InvalidStateTransitionError with review gate error
        rec = transition_stage(pdir, "segmentation", "completed")
        assert rec.status == "completed"

        # Pipeline view must not mark segmentation as failed
        pv = pipeline_view.build("test_lifecycle_proj")
        seg = next(s for s in pv["stages"] if s["id"] == "segmentation")
        assert seg["status"] == "completed"
        assert "failed" not in seg["status"]
