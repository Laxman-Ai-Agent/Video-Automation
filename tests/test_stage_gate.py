"""A stage with unresolved errors or warnings must not let the next stage start; it resumes once they are resolved.

Covers the three places that enforce it: the orchestrator's eligibility check, the run-route dependency and the pipeline view (BLOCKED downstream stages).
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from VIDEO_ENGINE.pipeline import orchestrator, stage_gate


def _report(pdir: Path, stage_file: str, steps: list[tuple[str, str]]) -> None:
    (pdir / stage_file).write_text(json.dumps({"stages": [{"n": i + 1, "name": f"Step {i + 1}", "status": st, "detail": d} for i, (st, d) in enumerate(steps)]}), encoding="utf-8")


@pytest.fixture
def pdir(tmp_path: Path) -> Path:
    p = tmp_path / "proj_gate"
    p.mkdir()
    return p


def test_clean_report_blocks_nothing(pdir):
    _report(pdir, "motion_planning.json", [("completed", "ok"), ("completed", "ok")])
    assert stage_gate.unresolved(pdir, "motion_plan", "16:9") == []


def test_warning_and_error_steps_are_unresolved(pdir):
    _report(pdir, "motion_planning.json", [("completed", "ok"), ("warning", "scene_01 overlaps"), ("failed", "bad id")])
    issues = stage_gate.unresolved(pdir, "motion_plan", "16:9")
    assert [(i["name"], i["severity"]) for i in issues] == [("Step 2", "warning"), ("Step 3", "error")]


def test_errors_can_never_be_accepted(pdir):
    _report(pdir, "motion_planning.json", [("warning", "w"), ("failed", "e")])
    with pytest.raises(ValueError):
        stage_gate.accept_warnings(pdir, "motion_plan", "16:9", "ship it")


def test_accepting_needs_a_note_and_something_to_accept(pdir):
    _report(pdir, "motion_planning.json", [("warning", "w")])
    with pytest.raises(ValueError):
        stage_gate.accept_warnings(pdir, "motion_plan", "16:9", "   ")
    _report(pdir, "motion_generation.json", [("completed", "ok")])
    with pytest.raises(ValueError):
        stage_gate.accept_warnings(pdir, "motion_gen", "16:9", "nothing to accept")


def test_acceptance_is_bound_to_exactly_these_warnings(pdir):
    _report(pdir, "motion_planning.json", [("warning", "scene_01 overlaps")])
    stage_gate.accept_warnings(pdir, "motion_plan", "16:9", "library has no primitive")
    assert stage_gate.unresolved(pdir, "motion_plan", "16:9") == []
    _report(pdir, "motion_planning.json", [("warning", "scene_01 overlaps"), ("warning", "a NEW warning")])      # the report changed: the old decision does not cover it
    assert len(stage_gate.unresolved(pdir, "motion_plan", "16:9")) == 2


def _state(**stage_status: str):
    return SimpleNamespace(stages={k: SimpleNamespace(status=v, reusable=False) for k, v in stage_status.items()})


def test_orchestrator_blocks_next_stage_then_resumes(pdir, monkeypatch):
    monkeypatch.setattr(orchestrator.pipeline_state, "load_pipeline_state", lambda _p: _state(motion_plan="completed"))
    _report(pdir, "motion_planning.json", [("completed", "ok"), ("warning", "scene_01 overlaps")])

    blocked = orchestrator.evaluate_stage_eligibility(pdir, "motion_gen", "16:9")
    assert blocked["eligible"] is False
    assert any("motion_plan" in b and "unresolved" in b for b in blocked["blockers"])

    _report(pdir, "motion_planning.json", [("completed", "ok"), ("completed", "fixed")])                         # the issue is resolved by the stage itself
    assert orchestrator.evaluate_stage_eligibility(pdir, "motion_gen", "16:9")["eligible"] is True


def test_orchestrator_resumes_after_a_person_accepts_the_warnings(pdir, monkeypatch):
    monkeypatch.setattr(orchestrator.pipeline_state, "load_pipeline_state", lambda _p: _state(motion_plan="completed"))
    _report(pdir, "motion_planning.json", [("warning", "scene_01 overlaps")])
    assert orchestrator.evaluate_stage_eligibility(pdir, "motion_gen", "16:9")["eligible"] is False
    stage_gate.accept_warnings(pdir, "motion_plan", "16:9", "reviewed, harmless")
    assert orchestrator.evaluate_stage_eligibility(pdir, "motion_gen", "16:9")["eligible"] is True


def test_orchestrator_never_resumes_past_an_error(pdir, monkeypatch):
    monkeypatch.setattr(orchestrator.pipeline_state, "load_pipeline_state", lambda _p: _state(motion_plan="completed"))
    _report(pdir, "motion_planning.json", [("failed", "bad id")])
    assert orchestrator.evaluate_stage_eligibility(pdir, "motion_gen", "16:9")["eligible"] is False


def test_run_route_refuses_to_start_and_allows_after_resolution(pdir, monkeypatch):
    from UI.backend import pipeline_view
    from UI.backend.errors import ApiError
    from UI.backend.routes import pipeline as routes
    monkeypatch.setattr(routes.store, "project_dir", lambda _pid: pdir)
    monkeypatch.setattr(pipeline_view, "aspect_of", lambda _p: "16:9")
    monkeypatch.setattr(orchestrator.pipeline_state, "load_pipeline_state", lambda _p: _state(motion_plan="completed"))
    check = routes._gate("motion_gen")
    _report(pdir, "motion_planning.json", [("warning", "scene_01 overlaps")])
    with pytest.raises(ApiError) as e:
        check("proj_gate")
    assert getattr(e.value, "status", getattr(e.value, "status_code", None)) == 409
    _report(pdir, "motion_planning.json", [("completed", "ok")])
    check("proj_gate")                                                                                              # no exception: the stage may start


def test_view_shows_downstream_stages_blocked_not_ready_and_clears_them(pdir, monkeypatch):
    from UI.backend import pipeline_view
    monkeypatch.setattr(pipeline_view, "aspect_of", lambda _p: "16:9")
    _report(pdir, "motion_planning.json", [("warning", "scene_01 overlaps")])

    def stages():
        return [{"id": "motion_plan", "label": "Motion Planning", "status": "completed", "detail": ""},
                {"id": "motion_gen", "label": "Motion Generation", "status": "queued", "detail": "ready"},
                {"id": "timeline", "label": "Timeline Build", "status": "queued", "detail": "ready"}]

    out = pipeline_view._enrich_stages_with_timings(pdir, stages(), "proj_gate")
    assert [s["status"] for s in out] == ["completed", "blocked", "blocked"]
    assert "Motion Planning" in out[1]["detail"]

    _report(pdir, "motion_planning.json", [("completed", "ok")])
    out = pipeline_view._enrich_stages_with_timings(pdir, stages(), "proj_gate")
    assert [s["status"] for s in out] == ["completed", "queued", "waiting"]                      # next stage runnable; the one after it waits for it
    assert "Motion Generation" in out[2]["waiting_for"]


def test_route_refuses_while_upstream_is_running_or_failed_and_allows_when_completed(pdir, monkeypatch):
    from UI.backend import pipeline_view
    from UI.backend.errors import ApiError
    from UI.backend.routes import pipeline as routes
    from SYSTEM.core import pipeline_state
    monkeypatch.setattr(routes.store, "project_dir", lambda _pid: pdir)
    monkeypatch.setattr(pipeline_view, "aspect_of", lambda _p: "16:9")
    for state in ("running", "failed", "blocked"):
        monkeypatch.setattr(pipeline_state, "load_pipeline_state", lambda _p, s=state: _state(analyzer=s))
        with pytest.raises(ApiError):
            routes._gate("segmentation")("proj_gate")                                         # Audio Analyzer not successful: Scene Segmentation must not start
    monkeypatch.setattr(pipeline_state, "load_pipeline_state", lambda _p: _state(analyzer="completed"))
    routes._gate("segmentation")("proj_gate")                                                 # completed and clean: it may start
    monkeypatch.setattr(pipeline_state, "load_pipeline_state", lambda _p: _state())
    routes._gate("segmentation")("proj_gate")                                                 # no record yet: the route's own input checks decide (missing analysis JSON ...)


def test_view_marks_every_stage_after_a_running_one_as_waiting(pdir, monkeypatch):
    from UI.backend import pipeline_view
    monkeypatch.setattr(pipeline_view, "aspect_of", lambda _p: "16:9")
    stages = [{"id": "analyzer", "label": "Audio Analysis", "status": "running", "detail": ""},
              {"id": "segmentation", "label": "Scene Segmentation", "status": "queued", "detail": "ready"},
              {"id": "planning", "label": "Visual Planning", "status": "queued", "detail": "ready"}]
    out = pipeline_view._enrich_stages_with_timings(pdir, stages, "proj_gate")
    assert [s["status"] for s in out] == ["running", "waiting", "waiting"]
    assert "Audio Analysis" in out[1]["detail"]


def test_policy_permitted_warnings_pass_only_with_the_stages_own_verdict(tmp_path):
    from VIDEO_ENGINE.pipeline import stage_gate
    rep = {"status": "completed_with_warnings", "stages": [{"n": 6, "name": "Frame Timing", "status": "warning", "detail": "sub-frame audio tail"}]}
    (tmp_path / "timeline_build_report.json").write_text(json.dumps(rep), encoding="utf-8")
    assert stage_gate.unresolved(tmp_path, "timeline", "16:9") == []
    rep["status"] = "blocked"                                              # the stage's verdict is not permissive: the warning blocks
    (tmp_path / "timeline_build_report.json").write_text(json.dumps(rep), encoding="utf-8")
    assert len(stage_gate.unresolved(tmp_path, "timeline", "16:9")) == 1
    mv = {"readiness": "needs_review", "stages": [{"n": 7, "name": "Layout", "status": "warning", "detail": "overlap"}]}
    (tmp_path / "motion_timeline_validation.json").write_text(json.dumps(mv), encoding="utf-8")
    assert len(stage_gate.unresolved(tmp_path, "motion_validation", "16:9")) == 1       # a person must judge it
