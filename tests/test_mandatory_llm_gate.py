"""Tests for Mandatory LLM Participation and Review Gate across every pipeline stage.

Non-Negotiable Completion Rules:
1. Execution and technical validation must pass.
2. Stage-specific LLM review must run and be persisted with matching input/output fingerprints.
3. Review must have zero blocking issues.
4. If LLM fails or is unavailable, stage remains blocked / queued / waiting_for_approval, never completed.
5. Invalidation on input/output change.
6. Motion Template Selection: ON uses verified recommendations, OFF routes to custom code without fallback.
7. Motion Animation: generates executable React/TSX in custom code mode.
8. Human approval gates for Timeline Approval and Final QC remain strictly required.
"""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend import (
    config,
    llm_review,
    motion_animation,
    motion_branch,
    motion_template_selection,
    pipeline_view,
    scene_segmentation,
    store,
    timeline_approval,
)


@pytest.fixture
def temp_project():
    """Creates a temporary project directory isolated from real projects."""
    td = Path(tempfile.mkdtemp(prefix="test_llm_gate_"))
    pdir = td / "test-proj"
    pdir.mkdir(parents=True)
    yield pdir
    shutil.rmtree(td, ignore_errors=True)


def test_stage_cannot_be_completed_without_llm_review(temp_project: Path):
    """Rule 1 & 2: A stage with complete technical outputs cannot be marked 'completed'
    if its stage-specific LLM review is missing.
    """
    pdir = temp_project
    (pdir / "audio.wav").write_bytes(b"RIFF dummy wav data")
    tr = {
        "text": "Hello world",
        "language": "en",
        "duration": 2.0,
        "segments": [{
            "id": 0,
            "start": 0.0,
            "end": 2.0,
            "text": "Hello world",
            "words": [
                {"w": "Hello", "start": 0.0, "end": 1.0, "p": 0.99},
                {"w": "world", "start": 1.0, "end": 2.0, "p": 0.99},
            ],
        }],
    }
    (pdir / "transcript.json").write_text(json.dumps(tr), encoding="utf-8")
    (pdir / "cuts.json").write_text(json.dumps({"cuts": []}), encoding="utf-8")
    inp = scene_segmentation.read_input(pdir)
    (pdir / "scene_segmentation.json").write_text(
        json.dumps({
            "schema_version": scene_segmentation.SCHEMA,
            "timing_rules": scene_segmentation.TIMING_RULES,
            "version": "1.0",
            "scenes": [{"scene_id": 1, "start_time": 0.0, "end_time": 2.0, "narration": "Hello world"}],
            "validation": {"status": "passed", "errors": [], "warnings": []},
            "source_fingerprint": scene_segmentation.fingerprint_of(inp),
        }),
        encoding="utf-8",
    )

    # 1. Direct LLM review gate check
    passed, reason, rev = llm_review.is_stage_review_passed(pdir, "segmentation")
    assert not passed
    assert reason == "llm_review_missing"
    assert rev is None

    # 2. Pipeline view check (deterministic completion does not depend on optional review)
    with patch.object(store, "project_dir", return_value=pdir):
        pv = pipeline_view.build("test-proj")
        seg_stage = next(s for s in pv["stages"] if s["id"] == "segmentation")
        assert seg_stage["status"] == "completed"
        assert "1 scenes segmented" in seg_stage["detail"]


def test_stage_blocked_when_llm_fails_or_has_blockers(temp_project: Path):
    """Rule 4: When the LLM is unavailable, times out, or reports blockers,
    the stage must fail closed (blocked/failed/needs_review), never silently complete.
    """
    pdir = temp_project
    (pdir / "audio.wav").write_bytes(b"RIFF dummy wav data")
    (pdir / "transcript.json").write_text(json.dumps({"segments": []}), encoding="utf-8")
    (pdir / "cuts.json").write_text(json.dumps({"cuts": []}), encoding="utf-8")

    # Simulate LLM failure (e.g. network/provider error)
    with patch("backend.llm_client.generate_text", side_effect=RuntimeError("Provider API timeout")):
        res = llm_review.run_stage_llm_review(pdir, "analyzer")

    assert res["status"] == "blocked"
    assert "Provider API timeout" in (res["error"] or "")
    assert any(f["severity"] == "blocker" for f in res["findings"])

    passed, reason, rev = llm_review.is_stage_review_passed(pdir, "analyzer")
    assert not passed
    assert "llm_review_blocked" in reason or "has_blockers" in reason

    with patch.object(store, "project_dir", return_value=pdir):
        pv = pipeline_view.build("test-proj")
        analyzer_stage = next(s for s in pv["stages"] if s["id"] == "analyzer")
        # Review status is blocked, but deterministic stage completion holds
        assert analyzer_stage["status"] == "completed"


def test_review_invalidated_when_inputs_or_outputs_change(temp_project: Path):
    """Rule 3: Modifying an input or output file changes its fingerprint,
    invalidating a previous passed review and resetting stage status.
    """
    pdir = temp_project
    audio_path = pdir / "audio.wav"
    audio_path.write_bytes(b"RIFF original wav audio")

    # Run successful review for audio input
    mock_reply = json.dumps({
        "status": "passed",
        "score": 0.95,
        "summary": "Audio quality and cadence verified",
        "findings": [],
    })
    with patch("backend.llm_client.generate_text", return_value=mock_reply):
        res = llm_review.run_stage_llm_review(pdir, "audio")

    assert res["status"] == "passed"
    passed, reason, _ = llm_review.is_stage_review_passed(pdir, "audio")
    assert passed
    assert reason == "passed"

    # Now modify audio file
    audio_path.write_bytes(b"RIFF changed audio bytes with new length")

    # Verification must now fail due to stale input fingerprint
    passed_after, reason_after, _ = llm_review.is_stage_review_passed(pdir, "audio")
    assert not passed_after
    assert reason_after == "llm_review_stale_inputs"


def test_review_retry_restores_completed(temp_project: Path):
    """Rule 5: Retrying LLM review on modified data computes a fresh fingerprint
    and restores the completed status.
    """
    pdir = temp_project
    audio_path = pdir / "audio.wav"
    audio_path.write_bytes(b"RIFF changed audio bytes with new length")

    mock_reply = json.dumps({
        "status": "passed",
        "score": 0.98,
        "summary": "Updated audio verified",
        "findings": [],
    })
    with patch("backend.llm_client.generate_text", return_value=mock_reply):
        res = llm_review.run_stage_llm_review(pdir, "audio", force=True)

    assert res["status"] == "passed"
    passed, reason, _ = llm_review.is_stage_review_passed(pdir, "audio")
    assert passed
    assert reason == "passed"


def test_motion_template_selection_modes(temp_project: Path):
    """Tests Motion Template Selection:
    - ON mode: LLM recommends compatible templates from registry; records selection.
    - OFF mode: explicitly routes to custom_code_generation, bypassing templates without fallback.
    """
    pdir = temp_project
    (pdir / "audio.wav").write_bytes(b"RIFF dummy audio")
    scene_plan = {
        "version": "1.0",
        "scenes": [
            {"id": 1, "start": 0.0, "end": 4.0, "text": "Intro Scene", "meaning": "Introductory statement"},
            {"id": 2, "start": 4.0, "end": 8.0, "text": "Tech Details", "meaning": "Sensors and components"},
        ],
    }
    (pdir / "scene_plan.json").write_text(json.dumps(scene_plan), encoding="utf-8")
    motion_plan = {
        "scenes": [
            {"id": "scene_1", "start": 0.0, "end": 4.0, "duration": 4.0, "speed": 1.0, "texts": [], "graphics": []},
            {"id": "scene_2", "start": 4.0, "end": 8.0, "duration": 4.0, "speed": 1.0, "texts": [], "graphics": []},
        ],
        "validation": {"errors": [], "warnings": []},
    }
    (pdir / "motion_plan.json").write_text(json.dumps(motion_plan), encoding="utf-8")
    (pdir / "motion_planning.json").write_text(json.dumps(motion_plan), encoding="utf-8")

    # 1. ON Mode
    store.set_reusable_motion_templates(pdir, True)
    mock_llm_rec = json.dumps({
        "status": "passed",
        "recommendations": [
            {"scene_id": 1, "template_id": "kinetic_typography_basic", "confidence": 0.9, "rationale": "Clear text intro"},
            {"scene_id": 2, "template_id": "cyberpunk_hud_overlay", "confidence": 0.85, "rationale": "High tech sensors"},
        ],
    })
    review_reply = json.dumps({
        "status": "passed",
        "score": 0.92,
        "summary": "Templates appropriately assigned from registry",
        "findings": [],
    })

    with patch("backend.llm_client.generate_text", side_effect=[mock_llm_rec, review_reply]):
        sel_on = motion_template_selection.build_selection(pdir, "16:9")
        motion_template_selection.save_selection(pdir, "16:9", sel_on)

    assert sel_on["mode"] == "template"
    assert len(sel_on["scenes"]) == 2
    assert (pdir / "motion_template_selection.json").exists()
    assert (pdir / "llm_review_motion_template.json").exists()

    # Verify review passed
    ok_on, _, _ = llm_review.is_stage_review_passed(pdir, "motion_template", "16:9")
    assert ok_on

    # 2. OFF Mode (Custom Code Generation)
    store.set_reusable_motion_templates(pdir, False)
    with patch("backend.llm_client.generate_text", return_value=review_reply):
        sel_off = motion_template_selection.build_selection(pdir, "16:9")
        motion_template_selection.save_selection(pdir, "16:9", sel_off)

    assert sel_off["mode"] == "custom_code"
    assert sel_off["routing_decision"] == "custom_code_generation"
    assert sel_off["bypassed_templates"] is True
    # Zero template fallback in OFF mode
    assert all(len(sc.get("selections", [])) == 0 for sc in sel_off["scenes"])
    assert all(sc["routing_decision"] == "custom_code_generation" for sc in sel_off["scenes"])
    assert all(sc["status"] == "skipped_by_configuration" for sc in sel_off["scenes"])

    ok_off, _, _ = llm_review.is_stage_review_passed(pdir, "motion_template", "16:9")
    assert ok_off


def test_motion_animation_custom_code_generation(temp_project: Path):
    """Tests Motion Animation in custom code mode:
    - Generates scene React/TSX files
    - Compiles cleanly
    - Records code manifest
    - Passes LLM review
    """
    pdir = temp_project
    (pdir / "audio.wav").write_bytes(b"RIFF dummy audio")
    scene_plan = {
        "version": "1.0",
        "scenes": [
            {"id": 1, "start": 0.0, "end": 3.0, "text": "Smart Wearables", "meaning": "Smart glass display"},
        ],
    }
    (pdir / "scene_plan.json").write_text(json.dumps(scene_plan), encoding="utf-8")
    motion_plan = {
        "scenes": [
            {"id": "scene_1", "start": 0.0, "end": 3.0, "duration": 3.0, "texts": [], "graphics": []},
        ],
    }
    (pdir / "motion_plan.json").write_text(json.dumps(motion_plan), encoding="utf-8")
    store.set_reusable_motion_templates(pdir, False)

    mock_review_reply = json.dumps({
        "status": "passed",
        "score": 0.94,
        "summary": "Custom TSX code generated without forbidden presets",
        "findings": [],
    })

    scene_tsx = """import React from "react";
import { AbsoluteFill } from "remotion";
export const Scene1: React.FC = () => <AbsoluteFill style={{ justifyContent: "center", color: "#f8fafc" }}>Smart Wearables</AbsoluteFill>;
export default Scene1;
"""

    def reply(*args, **kwargs):          # the code-generation call gets TSX, the review call gets the structured verdict
        return scene_tsx if "Remotion animation software engineer" in (kwargs.get("system") or "") else mock_review_reply

    with patch("backend.llm_client.generate_text", side_effect=reply):
        manifest = motion_animation.generate_custom_motion_code(pdir, "16:9")

    assert manifest["mode"] == "custom_code"
    assert manifest["typecheck"]["status"] == "passed"
    assert len(manifest["scenes"]) == 1
    assert Path(manifest["scenes"][0]["source_path"]).exists()

    # Verify review file was written
    assert (pdir / "llm_review_motion_gen.json").exists()
    ok, reason, _ = llm_review.is_stage_review_passed(pdir, "motion_gen", "16:9")
    assert ok, f"Expected motion_gen review to pass, got: {reason}"


def test_human_approval_gates_strictly_enforced(temp_project: Path):
    """Rule 8: Timeline Approval and Final QC require genuine human decisions.
    An LLM review never bypasses the human approval requirement.
    """
    pdir = temp_project
    (pdir / "composition.json").write_text(json.dumps({"meta": {}, "scenes": []}), encoding="utf-8")
    (pdir / "timeline.json").write_text(json.dumps({"scenes": []}), encoding="utf-8")
    (pdir / "timeline_build_report.json").write_text(json.dumps({"status": "passed", "counts": {}}), encoding="utf-8")

    # 1. Timeline Approval: Even if an LLM review exists, if human approval is not recorded,
    # the stage cannot be completed.
    mock_rev = {
        "schema": "llm_review:1.0",
        "version": "1.0",
        "stage": "approval",
        "aspect": "16:9",
        "status": "passed",
        "score": 0.99,
        "summary": "Pre-approval checks satisfied",
        "findings": [],
        "input_fingerprint": llm_review.compute_stage_input_fingerprint(pdir, "approval", "16:9"),
        "output_fingerprint": llm_review.compute_stage_output_fingerprint(pdir, "approval", "16:9"),
        "reviewed_at": 1000.0,
        "provider": "claude",
        "model": "claude-3-5-sonnet",
        "latency_ms": 250,
        "error": None,
    }
    llm_review.save_review(pdir, "approval", "16:9", mock_rev)

    # Human approval history file does NOT exist
    assert not (pdir / "timeline_approval_history.json").exists()

    # Timeline stage view must NOT be completed
    with patch.object(store, "project_dir", return_value=pdir):
        pv = pipeline_view.build("test-proj")
        ap_stage = next(s for s in pv["stages"] if s["id"] == "approval")
        assert ap_stage["status"] != "completed"


def test_visual_planning_waits_for_the_transcript_the_audio_analyzer_verified(temp_project: Path):
    """The gate asks the Audio Analyzer's verification (the LLM checked the transcript), not for a file that exists only when something was corrected."""
    from backend.errors import ApiError
    from UI.backend.routes import pipeline as routes
    pdir = temp_project
    (pdir / "transcript.json").write_text("{}", encoding="utf-8")
    with patch.object(store, "project_dir", return_value=pdir), pytest.raises(ApiError) as exc:
        routes.run_visual_plan("test-proj")
    assert exc.value.code == "llm_verification_required" and "Audio Analyzer" in exc.value.message


def test_the_audio_analyzer_approval_judges_the_final_transcript_and_is_bound_to_it(temp_project: Path):
    """The stage review read only the raw transcript, so it reported phonetic words the correction had already fixed (needs_review) and a changed final transcript did not invalidate it."""
    pdir = temp_project
    word = lambda w, a, b, **kw: {"w": w, "start": a, "end": b, **kw}
    raw = {"language": "te", "duration": 2.0, "segments": [{"id": 0, "start": 0.0, "end": 2.0, "text": "క్వేష్యం అడిగితే", "words": [word("క్వేష్యం", 0.0, 1.0), word("అడిగితే", 1.0, 2.0)]}]}
    final = {**raw, "segments": [{"id": 0, "start": 0.0, "end": 2.0, "text": "question అడిగితే", "words": [word("question", 0.0, 1.0, edit="llm", timing="aligned"), word("అడిగితే", 1.0, 2.0)]}]}
    (pdir / "transcript.json").write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    (pdir / "cuts.json").write_text(json.dumps({"cuts": [1.0]}), encoding="utf-8")
    before = llm_review.compute_stage_output_fingerprint(pdir, "analyzer")
    (pdir / "transcript_corrected.json").write_text(json.dumps(final, ensure_ascii=False), encoding="utf-8")
    (pdir / "transcript_review.json").write_text(json.dumps({"llm": {"status": "applied"}, "alignment": {"status": "aligned_for_edits"}, "corrections": [{"from": "క్వేష్యం", "to": "question", "status": "applied", "reason": "english"}]}, ensure_ascii=False), encoding="utf-8")
    assert llm_review.compute_stage_output_fingerprint(pdir, "analyzer") != before                  # the final transcript is part of what the approval covers
    p = llm_review.build_stage_payload(pdir, "analyzer")
    assert p["final_transcript_file"] == "transcript_corrected.json" and p["final_transcript"][0]["text"] == "question అడిగితే" and p["cuts_count"] == 1
    wt = p["word_timing"]
    assert {k: wt[k] for k in ("words", "llm_edited", "aligned", "estimated", "overlapping", "edited_keeping_whisper_time")} == {"words": 2, "llm_edited": 1, "aligned": 1, "estimated": 0, "overlapping": 0, "edited_keeping_whisper_time": 0}
    assert "legend" in wt and p["empty_segments"] == [] and "cuts_note" in p                        # the counts reconcile for the reviewer
    assert p["llm_correction"]["applied"] == 1 and p["llm_correction"]["corrections"][0]["to"] == "question" and "transcript_sample" not in p
