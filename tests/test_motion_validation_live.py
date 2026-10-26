"""Motion Validation shows its steps while it runs (live_steps), without asking the LLM about a step before the final report exists, and a stage that starts is at 0%."""
import json

from UI.backend import pipeline_view, step_llm_check
from VIDEO_ENGINE.stages import live_steps, motion_validation as mv


def test_the_run_writes_one_row_per_step_and_marks_them_live(tmp_path):
    live = live_steps.LiveSteps(tmp_path / mv.names("16:9")["live"], [s[2] for s in mv.STAGES], live=True)
    live.step(1, "running", "making the preview stills first")
    live.step(1, "completed", "9 of 9 checks passed", 9, 9)
    live.step(2, "running", "proving every input is current")
    got = live_steps.progress(tmp_path / mv.names("16:9")["live"])
    assert len(live.rows) == len(mv.STAGES) == 12 and got["percent"] == round(100 / 12, 1) and got["detail"].startswith("Fingerprint & Freshness")
    assert all(r.get("live") for r in live.rows if r["status"] != "pending")
    live.finish()
    assert live_steps.progress(tmp_path / mv.names("16:9")["live"]) is None                      # a finished run is not "in progress"


def test_a_live_step_is_never_sent_to_the_llm_and_the_live_report_is_used_only_while_the_stage_runs(tmp_path, monkeypatch):
    assert step_llm_check._recorded({"n": 1, "status": "completed", "live": True}) is False
    assert step_llm_check._recorded({"n": 1, "status": "completed"}) is True
    live = live_steps.LiveSteps(tmp_path / mv.names("16:9")["live"], ["a", "b"], live=True)
    live.step(1, "completed", "x", 1, 1)
    (tmp_path / mv.names("16:9")["report"]).write_text(json.dumps({"stages": [{"n": 1, "name": "final", "status": "completed"}]}), encoding="utf-8")
    from VIDEO_ENGINE.pipeline import orchestrator
    monkeypatch.setattr(orchestrator, "current_run", lambda pid: type("R", (), {"current_stage": "motion_validation"})())
    assert step_llm_check.steps(tmp_path, "motion_validation", "16:9")[0][0]["live"] is True        # running: the live steps
    monkeypatch.setattr(orchestrator, "current_run", lambda pid: None)
    assert [s["name"] for s in step_llm_check.steps(tmp_path, "motion_validation", "16:9")[0]] == ["final"]   # not running (a stopped run left the file on "running"): the real report
