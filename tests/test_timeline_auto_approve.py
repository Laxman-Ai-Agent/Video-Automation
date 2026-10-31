"""Timeline Approval is decided by the LLM approval review (timeline_approval.auto_approve): approved only on a passing verdict, withdrawn when the audit fails, never on a rejection."""
import pytest

from backend import timeline_approval as ta


def _setup(monkeypatch, verdicts):
    state = {"status": "ready_for_review", "decisions": []}
    snap = lambda p, a: {"status": state["status"], "blockers": [], "fingerprint": "fp1", "review_id": "review_fp1", "requirements": [{"key": "k1"}]}
    monkeypatch.setattr(ta, "snapshot", snap)
    monkeypatch.setattr(ta, "state", lambda p, a, s=None: {"status": state["status"], "fingerprint": "fp1"})

    def decide(p, a, body, in_job=False):
        state["decisions"].append(body["decision"])
        state["status"] = "approved" if body["decision"] == "approved" else "ready_for_review"
        assert body["warning_acknowledgements"] if body["decision"] == "approved" else True
    monkeypatch.setattr(ta, "decide", decide)
    from backend import llm_review
    seq = iter(verdicts)
    monkeypatch.setattr(llm_review, "run_stage_llm_review", lambda *a, **k: next(seq))
    monkeypatch.setattr(llm_review, "is_stage_review_passed", lambda *a, **k: (state["status"] == "approved", "", None))
    from VIDEO_ENGINE.pipeline import legacy_pipeline_adapter as pa
    monkeypatch.setattr(pa, "execute", lambda *a, **k: {"status": "ran"})
    return state


def test_a_passing_review_approves_and_the_audit_confirms(monkeypatch):
    ok = {"status": "passed", "score": 0.9, "findings": []}
    st = _setup(monkeypatch, [ok, ok])
    ta.auto_approve(None, "16:9")
    assert st["decisions"] == ["approved"] and st["status"] == "approved"


def test_a_decision_that_was_not_recorded_is_never_reported_as_an_approval(monkeypatch):
    """Regression: re-approving an unchanged version after an audit withdrew it reused the old idempotency key, decide() recorded nothing ('already_recorded') and auto_approve still returned: the stage read
    'completed' while the status stayed ready_for_review and Render refused to start."""
    ok = {"status": "passed", "score": 0.9, "findings": []}
    st = _setup(monkeypatch, [ok, ok])
    monkeypatch.setattr(ta, "decide", lambda p, a, body, in_job=False: None)                       # nothing recorded
    monkeypatch.setattr(ta, "state", lambda p, a, s=None: {"status": "ready_for_review", "fingerprint": "fp1"})
    from backend import llm_review
    monkeypatch.setattr(llm_review, "is_stage_review_passed", lambda *a, **k: (True, "", None))
    with pytest.raises(ta.ApprovalError, match="not recorded"):
        ta.auto_approve(None, "16:9")
    assert st["decisions"] == []


def test_every_new_review_of_the_same_version_makes_a_new_decision_key():
    assert ta._review_tag({"output_fingerprint": "aaa"}, 1) != ta._review_tag({"output_fingerprint": "bbb"}, 1)
    assert ta._review_tag({"output_fingerprint": "aaa"}, 1) == ta._review_tag({"output_fingerprint": "aaa"}, 2)      # the same review result stays idempotent
    assert ta._review_tag({}, 3) == "3"


def test_a_rejected_version_is_rebuilt_once_and_never_approved(monkeypatch):
    bad = {"status": "needs_review", "score": 0.6, "summary": "audio drifts", "findings": [{"severity": "blocker", "message": "audio out of sync"}]}
    st = _setup(monkeypatch, [bad, bad])
    with pytest.raises(ta.ApprovalError, match="did not pass") as e:
        ta.auto_approve(None, "16:9")
    assert st["decisions"] == [] and "blocker: audio out of sync" in e.value.blockers


def test_a_failed_audit_withdraws_the_approval(monkeypatch):
    ok, bad = {"status": "passed", "score": 0.9, "findings": []}, {"status": "failed", "score": 0.2, "findings": []}
    st = _setup(monkeypatch, [ok, bad, ok, bad])
    with pytest.raises(ta.ApprovalError):
        ta.auto_approve(None, "16:9")
    assert st["decisions"] == ["approved", "withdrawn", "approved", "withdrawn"] and st["status"] != "approved"


def test_a_version_with_blockers_is_not_reviewed(monkeypatch):
    st = _setup(monkeypatch, [])
    monkeypatch.setattr(ta, "snapshot", lambda p, a: {"status": "not_ready", "blockers": ["timeline is stale"], "fingerprint": None, "review_id": None, "requirements": []})
    with pytest.raises(ta.ApprovalError, match="timeline is stale"):
        ta.auto_approve(None, "16:9")
    assert st["decisions"] == []


def test_a_timeline_job_runs_through_the_llm_approval_to_render_and_qc():
    from VIDEO_ENGINE.pipeline import jobs_adapter
    names = ("motion-validate", "timeline-build", "timeline-approve", "render-final")
    assert jobs_adapter._map_label_to_stages("timeline-build", names) == ("timeline", "qc")      # approval is never skipped on the way to render
    assert jobs_adapter._map_label_to_stages("build", ("render-final",)) == ("render", "final")
    full = ("motion-plan", "motion-build", "motion-validate", "timeline-build", "timeline-approve", "render-final")
    assert jobs_adapter._map_label_to_stages("timeline", full) == ("motion_plan", "qc")                 # the timeline built from the plan runs the motion stages first
