import json

from SYSTEM.policies import llm_review
from VIDEO_ENGINE.stages import timeline_approval


def test_a_decision_about_an_older_build_is_not_evidence_for_the_current_timeline(tmp_path, monkeypatch):
    """Regression: the approval review was shown the approval of an older build, reported a fingerprint mismatch and rejected a clean timeline."""
    monkeypatch.setattr(timeline_approval, "fingerprint", lambda *a, **k: "now")
    (tmp_path / "timeline_approval_history.json").write_text(json.dumps({"events": [{"kind": "decision", "decision": "approved", "timeline_fingerprint": "old"}]}))
    p = llm_review.build_stage_payload(tmp_path, "approval", "16:9")
    assert p["latest_decision"] is None and "older builds" in p["superseded_decisions"] and p["current_timeline_fingerprint"] == "now"
    (tmp_path / "timeline_approval_history.json").write_text(json.dumps({"events": [{"kind": "decision", "decision": "approved", "timeline_fingerprint": "now"}]}))
    assert llm_review.build_stage_payload(tmp_path, "approval", "16:9")["latest_decision"]["decision"] == "approved"
