import json

from SYSTEM.policies import llm_review
from VIDEO_ENGINE.stages import timeline_approval


def test_the_review_sees_every_transition_and_scene_the_summary_counts(tmp_path, monkeypatch):
    """Regression: the payload listed only 6 transitions / 8 scenes but counted them all, so a reviewer of an 8-scene timeline saw 'total 7, listed 6' and rejected it for a missing transition."""
    monkeypatch.setattr(timeline_approval, "fingerprint", lambda *a, **k: "now")
    trans = [{"transition_id": f"t{i}", "from_scene": f"s{i}", "to_scene": f"s{i + 1}", "type": "fade", "applied_frames": 12, "supported": True} for i in range(12)]
    items = [{"scene_id": f"s{i}", "start_frame": i * 30, "end_frame": i * 30 + 30} for i in range(13)]
    (tmp_path / "timeline.json").write_text(json.dumps({"transitions": trans, "tracks": [{"track_type": "composition", "items": items}]}))
    p = llm_review.build_stage_payload(tmp_path, "approval", "16:9")
    assert p["transitions_summary"]["total"] == len(p["transitions"]) == 12
    assert len(p["timeline_scenes"]) == 13


def test_a_decision_about_an_older_build_is_not_evidence_for_the_current_timeline(tmp_path, monkeypatch):
    """Regression: the approval review was shown the approval of an older build, reported a fingerprint mismatch and rejected a clean timeline."""
    monkeypatch.setattr(timeline_approval, "fingerprint", lambda *a, **k: "now")
    (tmp_path / "timeline_approval_history.json").write_text(json.dumps({"events": [{"kind": "decision", "decision": "approved", "timeline_fingerprint": "old"}]}))
    p = llm_review.build_stage_payload(tmp_path, "approval", "16:9")
    assert p["latest_decision"] is None and "older builds" in p["superseded_decisions"] and p["current_timeline_fingerprint"] == "now"
    (tmp_path / "timeline_approval_history.json").write_text(json.dumps({"events": [{"kind": "decision", "decision": "approved", "timeline_fingerprint": "now"}]}))
    assert llm_review.build_stage_payload(tmp_path, "approval", "16:9")["latest_decision"]["decision"] == "approved"
