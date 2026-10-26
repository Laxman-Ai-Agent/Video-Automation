"""While a stage runs, its subtasks never show the previous run's report: only what the new run has written."""
import json
import os
import time

from UI.backend import pipeline_view
from UI.backend import step_llm_check
from UI.backend.routes import pipeline as routes

STEPS = {"stages": [{"n": 1, "name": "Semantic Understanding", "status": "completed", "checks_passed": 3, "checks_total": 3}]}


def _setup(monkeypatch, tmp_path, started, report_age):
    (tmp_path / "visual_planning.json").write_text(json.dumps(STEPS), encoding="utf-8")
    t = time.time() - report_age
    os.utime(tmp_path / "visual_planning.json", (t, t))
    monkeypatch.setattr(routes.store, "project_dir", lambda pid: tmp_path)
    monkeypatch.setattr(pipeline_view, "aspect_of", lambda pdir: "16:9")
    monkeypatch.setattr(pipeline_view, "run_started_at", lambda pid, stage: started)
    monkeypatch.setattr(step_llm_check, "start", lambda *a: False)                       # no background LLM calls in a test
    monkeypatch.setattr(step_llm_check, "load", lambda *a: {"steps": {}, "running": False, "active_step": None})


def test_running_stage_hides_the_report_of_the_previous_run(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path, started=time.time() - 60, report_age=3600)
    out = routes.get_stage_subtasks("p", "planning")
    assert out["steps"] == [] and out["report"] is None and out["overall_progress"] is None


def test_running_stage_shows_what_the_new_run_wrote(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path, started=time.time() - 3600, report_age=60)
    assert [s["n"] for s in routes.get_stage_subtasks("p", "planning")["steps"]] == [1]


def test_a_stage_that_is_not_running_shows_its_last_report(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path, started=None, report_age=3600)
    assert [s["n"] for s in routes.get_stage_subtasks("p", "planning")["steps"]] == [1]


def test_a_running_stage_never_takes_an_earlier_runs_start(tmp_path, monkeypatch):
    """The start of a running stage is this run's own: an old record of a finished run, or "now", would hide the report the run writes."""
    (tmp_path / "pipeline_state.json").write_text(json.dumps({"stages": {"planning": {"status": "completed", "started_at": 1000.0}}}), encoding="utf-8")
    monkeypatch.setattr(pipeline_view.jobs, "current", lambda pid: object())             # a running job that has no start time of its own
    own, unknown = [{"id": "planning", "status": "running", "started_at": 5000.0}], [{"id": "planning", "status": "running"}]
    assert pipeline_view._enrich_stages_with_timings(tmp_path, own, "p")[0]["started_at"] == 5000.0
    assert pipeline_view._enrich_stages_with_timings(tmp_path, unknown, "p")[0]["started_at"] is None


def test_a_step_still_running_is_not_sent_to_the_llm(monkeypatch, tmp_path):
    monkeypatch.setattr(step_llm_check, "steps", lambda *a: ([{"n": 1, "status": "completed"}, {"n": 2, "status": "running"}, {"n": 3, "status": "pending"}], {}, None))
    monkeypatch.setattr(step_llm_check, "load", lambda *a: {"steps": {}})
    assert step_llm_check.pending(tmp_path, "assets", "16:9") == 1                           # only the finished step has a result to check


def test_asset_collection_shows_its_own_progress_only_while_its_run_is_alive(monkeypatch, tmp_path):
    from VIDEO_ENGINE.stages import asset_collection as ac
    from VIDEO_ENGINE.stages import live_steps
    rep = live_steps.LiveSteps(tmp_path / ac.REPORT, ac.STEPS)
    rep.step(1, "completed", "4 requirement(s)", 4, 4)
    rep.step(2, "running", "searching 'river' (1 of 4 done)", 1, 4)
    monkeypatch.setattr(ac, "input_fingerprint", lambda *a: "x")
    monkeypatch.setattr(pipeline_view, "_runs_now", lambda pid, stage: True)
    live = pipeline_view._assets_stage(tmp_path, "16:9", True)
    assert live["status"] == "running" and live["percent"] == 25.0 and "Search licensed sources: searching" in live["detail"] and live["started_at"] == rep.started
    monkeypatch.setattr(pipeline_view, "_runs_now", lambda pid, stage: False)               # the run was stopped and left the report on "running"
    assert pipeline_view._assets_stage(tmp_path, "16:9", True)["status"] != "running"
