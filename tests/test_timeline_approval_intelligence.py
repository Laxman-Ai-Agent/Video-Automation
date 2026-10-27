"""Comprehensive unit and integration test suite for Timeline Approval Agent (v2.0.0).

Verifies:
1. StructuralDiffAnalyzer: Scene additions, removals, modifications, and AST hashing.
2. VisualDiffAnalyzer: Preview still delta detection and honest fallback.
3. LLMTimelineAssessor: Quality review, pacing scoring, and disclosure handling.
4. ApprovalRiskClassifier: Separation of hard technical blockers from quality warnings.
5. TimelineApprovalAgent: Stale invalidation, auto-pilot rubric approval, and audit trail logging.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from SYSTEM.agents.shared.contracts import AgentRequest
from SYSTEM.agents.video_generation_agents.timeline_approval.agent import TimelineApprovalAgent
from SYSTEM.agents.video_generation_agents.timeline_approval.approval_intelligence import (
    ApprovalRiskClassifier,
    LLMTimelineAssessor,
    QualityFinding,
    StructuralDiffAnalyzer,
    VisualDiffAnalyzer,
)


@pytest.fixture
def mock_approval_project(tmp_path: Path) -> Path:
    """Sets up a minimal valid project workspace for timeline approval intelligence tests."""
    pdir = tmp_path / "proj_appr_test"
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
            "scenes": [
                {"id": "scene_001", "start_frame": 0, "end_frame": 60, "duration_frames": 60, "transition_out": {"type": "fade"}},
                {"id": "scene_002", "start_frame": 60, "end_frame": 120, "duration_frames": 60},
            ],
        }),
        encoding="utf-8",
    )

    # 3. composition.json
    (pdir / "composition.json").write_text(
        json.dumps({
            "meta": {"fps": 30, "width": 1920, "height": 1080, "duration": 4.0, "audio": "audio.wav"},
            "scenes": [
                {"id": "scene_001", "start": 0.0, "end": 2.0, "layers": []},
                {"id": "scene_002", "start": 2.0, "end": 4.0, "layers": []},
            ],
        }),
        encoding="utf-8",
    )

    # 4. generated_motion TSX files
    gen_dir = pdir / "generated_motion"
    gen_dir.mkdir(parents=True)
    (gen_dir / "scene_001.tsx").write_text("import React from 'react'; export const Scene001 = () => <div>Scene 1</div>;", encoding="utf-8")
    (gen_dir / "scene_002.tsx").write_text("import React from 'react'; export const Scene002 = () => <div>Scene 2</div>;", encoding="utf-8")

    return pdir


# ---------------------------------------------------------------------------
# Test 1: Structural Diff Analyzer
# ---------------------------------------------------------------------------
def test_structural_diff_analyzer(mock_approval_project: Path):
    analyzer = StructuralDiffAnalyzer()

    # Initial diff without prior approval
    diff1 = analyzer.analyze_diff(mock_approval_project, "16:9")
    assert diff1["has_previous_approval"] is False
    assert diff1["total_scenes_current"] == 2
    assert "scene_001" in diff1["added_scenes"]
    assert "scene_002" in diff1["added_scenes"]

    # Simulate prior approval in timeline_review.json
    rev_data = {
        "schema_version": "1.0",
        "scenes": [
            {"scene_id": "scene_001", "start_frame": 0, "end_frame": 60, "transition_out": {"type": "fade"}},
            {"scene_id": "scene_002", "start_frame": 60, "end_frame": 120},
        ],
    }
    (mock_approval_project / "timeline_review.json").write_text(json.dumps(rev_data), encoding="utf-8")
    (mock_approval_project / "timeline_approval_history.json").write_text(
        json.dumps({
            "schema_version": "1.0",
            "events": [
                {"event_id": "decision_prev123", "kind": "decision", "decision": "approved", "timeline_fingerprint": "fp_old"},
            ],
        }),
        encoding="utf-8",
    )

    diff2 = analyzer.analyze_diff(mock_approval_project, "16:9")
    assert diff2["has_previous_approval"] is True
    assert diff2["previous_approval_id"] == "decision_prev123"
    assert diff2["is_structural_identical"] is True
    assert diff2["unchanged_scenes"] == ["scene_001", "scene_002"]

    # Modify scene_002 frames to test delta detection
    tl_data = json.loads((mock_approval_project / "timeline.json").read_text(encoding="utf-8"))
    tl_data["scenes"][1]["end_frame"] = 150
    (mock_approval_project / "timeline.json").write_text(json.dumps(tl_data), encoding="utf-8")

    diff3 = analyzer.analyze_diff(mock_approval_project, "16:9")
    assert len(diff3["modified_scenes"]) == 1
    assert diff3["modified_scenes"][0]["scene_id"] == "scene_002"


# ---------------------------------------------------------------------------
# Test 2: Visual Diff Analyzer
# ---------------------------------------------------------------------------
def test_visual_diff_analyzer_honest_fallback(mock_approval_project: Path):
    analyzer = VisualDiffAnalyzer()

    # Previews directory absent
    res1 = analyzer.compare_previews(mock_approval_project, "16:9")
    assert res1["visual_diff_available"] is False
    assert "unavailable" in res1["reason"]

    # Create previews folder with stills but no previous baseline
    prev_dir = mock_approval_project / "previews"
    prev_dir.mkdir(parents=True)
    (prev_dir / "scene_001_mid.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

    res2 = analyzer.compare_previews(mock_approval_project, "16:9")
    assert res2["visual_diff_available"] is False
    assert res2["current_stills_count"] == 1
    assert "baseline" in res2["reason"]


# ---------------------------------------------------------------------------
# Test 3: LLM Timeline Assessor
# ---------------------------------------------------------------------------
def test_llm_timeline_assessor_fallback():
    assessor = LLMTimelineAssessor()

    tl_meta = {"duration_seconds": 4.0, "total_frames": 120, "fps": 30, "scene_count": 2}
    reqs = [{"key": "tail:cut", "category": "limitation", "text": "Tail cut is digital silence"}]
    diff = {"is_structural_identical": True, "modified_scenes": []}
    vis = {"visual_diff_available": False, "reason": "No baseline"}

    res = assessor.assess(
        project_id="test_proj",
        timeline_meta=tl_meta,
        requirements=reqs,
        diff_summary=diff,
        visual_diff_meta=vis,
    )

    assert res["status"] == "approved"
    assert res["pacing_score"] >= 80
    assert res["evaluation_mode"] == "metadata_based_only"
    assert len(res["findings"]) >= 1


def test_llm_timeline_assessor_with_gateway():
    assessor = LLMTimelineAssessor()

    mock_llm_resp = MagicMock()
    mock_llm_resp.status = "success"
    mock_llm_resp.provider = "mock_provider"
    mock_llm_resp.raw_text = json.dumps({
        "status": "approved",
        "confidence": 0.96,
        "summary": "Smooth 2-scene Telugu greeting composition with balanced pacing.",
        "pacing_score": 94,
        "continuity_score": 96,
        "findings": [
            {"category": "narrative_continuity_concern", "severity": "info", "message": "Pacing is optimal", "is_blocking": False}
        ],
    })

    with patch("SYSTEM.core.llm_gateway.gateway.execute", return_value=mock_llm_resp):
        res = assessor.assess(
            project_id="test_proj",
            timeline_meta={"duration_seconds": 4.0, "scene_count": 2},
            requirements=[],
            diff_summary={},
            visual_diff_meta={"visual_diff_available": True},
        )

        assert res["status"] == "approved"
        assert res["pacing_score"] == 94
        assert res["continuity_score"] == 96
        assert "llm" in res["assessor"]


# ---------------------------------------------------------------------------
# Test 4: Approval Risk Classifier
# ---------------------------------------------------------------------------
def test_approval_risk_classifier():
    classifier = ApprovalRiskClassifier()

    # 1. Clean timeline -> can auto approve
    res_clean = classifier.evaluate_risk(
        blockers=[],
        fingerprint="fp_valid_123",
        is_stale=False,
        llm_assessment={"findings": []},
        structural_diff={},
    )
    assert res_clean["can_auto_approve"] is True
    assert res_clean["risk_level"] == "low"

    # 2. Stale state -> hard blocker
    res_stale = classifier.evaluate_risk(
        blockers=[],
        fingerprint="fp_valid_123",
        is_stale=True,
        llm_assessment={"findings": []},
        structural_diff={},
    )
    assert res_stale["can_auto_approve"] is False
    assert res_stale["risk_level"] == "critical"
    assert any("stale" in b.lower() for b in res_stale["critical_blockers"])

    # 3. Deterministic blocker cannot be overruled
    res_blocked = classifier.evaluate_risk(
        blockers=["Composition missing audio file"],
        fingerprint="fp_valid_123",
        is_stale=False,
        llm_assessment={"findings": []},
        structural_diff={},
    )
    assert res_blocked["can_auto_approve"] is False
    assert any("Composition missing audio file" in b for b in res_blocked["critical_blockers"])


# ---------------------------------------------------------------------------
# Test 5: Timeline Approval Agent Execution & Audit Logging
# ---------------------------------------------------------------------------
def test_timeline_approval_agent_does_not_approve_a_version_the_llm_rejects(mock_approval_project: Path):
    """No human gate: the agent asks the LLM approval review (auto_approve); a stale or rejected version fails with the exact cause and is never approved."""
    from VIDEO_ENGINE.stages import timeline_approval as ta
    agent = TimelineApprovalAgent()
    req = AgentRequest(agent_id="timeline_approval", project_id=mock_approval_project.name, stage_id="approval")
    rejected = ta.ApprovalError("llm_review_rejected", "the LLM approval review did not pass (needs_review, score 0.6): audio drifts", ["blocker: audio out of sync"])
    with patch("VIDEO_ENGINE.stages.timeline_approval.state", return_value={"status": "stale", "approved": False, "stale": True, "blockers": ["Timeline changed"]}),          patch("VIDEO_ENGINE.stages.timeline_approval.fingerprint", return_value="fp_new_123"),          patch("VIDEO_ENGINE.stages.timeline_approval.auto_approve", side_effect=rejected):
        res = agent.execute(mock_approval_project, req)
        assert res.status == "failed"
        assert "did not approve" in res.summary and "audio out of sync" in res.error


def test_timeline_approval_agent_without_a_version_is_blocked(mock_approval_project: Path):
    agent = TimelineApprovalAgent()
    req = AgentRequest(agent_id="timeline_approval", project_id=mock_approval_project.name, stage_id="approval")
    with patch("VIDEO_ENGINE.stages.timeline_approval.state", return_value={"status": "not_ready", "approved": False, "stale": False, "blockers": ["no current timeline"]}),          patch("VIDEO_ENGINE.stages.timeline_approval.fingerprint", return_value=None):
        res = agent.execute(mock_approval_project, req)
        assert res.status == "blocked" and "no current timeline" in res.summary


def test_timeline_approval_agent_llm_approval(mock_approval_project: Path):
    agent = TimelineApprovalAgent()
    req = AgentRequest(agent_id="timeline_approval", project_id=mock_approval_project.name, stage_id="approval")

    state_before = {
        "status": "ready_for_review",
        "approved": False,
        "stale": False,
        "blockers": [],
        "requirements": [{"key": "req_1", "category": "limitation"}],
        "review_id": "rev_123",
    }
    state_after = {
        "status": "approved",
        "approved": True,
        "stale": False,
        "blockers": [],
        "fingerprint": "fp_valid_123",
        "last_decision": {"decided_by": "llm:claude_cli/claude-code"},
    }

    from SYSTEM.approvals.approval_engine import approval_engine
    audit_log = approval_engine._audit_file                            # the one audit writer (tests: a file in tmp_path)
    initial_audit_len = len(audit_log.read_text(encoding="utf-8").splitlines()) if audit_log.exists() else 0

    with patch("VIDEO_ENGINE.stages.timeline_approval.state", return_value=state_before),          patch("VIDEO_ENGINE.stages.timeline_approval.fingerprint", return_value="fp_valid_123"),          patch("VIDEO_ENGINE.stages.timeline_approval.auto_approve", return_value=state_after),          patch("SYSTEM.core.artifact_contracts.validate_approval_artifacts", return_value=None):

        res = agent.execute(mock_approval_project, req)

        assert res.status == "succeeded"
        assert res.metadata["approved"] is True
        assert "timeline_approval_intelligence_ref" in res.metadata

        # Check intelligence artifact written
        intel_file = mock_approval_project / "timeline_approval_intelligence.json"
        assert intel_file.exists()
        intel_data = json.loads(intel_file.read_text(encoding="utf-8"))
        assert intel_data["schema_version"] == "2.0"
        assert intel_data["decision"] == "approved_by_llm"
        assert "structural_diff" in intel_data

        # Check audit log appended
        new_audit_len = len(audit_log.read_text(encoding="utf-8").splitlines())
        assert new_audit_len == initial_audit_len + 1
