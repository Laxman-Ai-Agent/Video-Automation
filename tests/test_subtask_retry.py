"""Retry of one subtask: a Visual Planning step with warnings solves only its own warnings, any other step gets its LLM check asked again, and nothing else runs."""
import json

import pytest

from UI.backend import step_llm_check
from UI.backend.errors import ApiError
from UI.backend.routes import pipeline as routes
from VIDEO_ENGINE.stages import review, visual_planning


def _setup(monkeypatch, tmp_path, status):
    monkeypatch.setattr(routes.store, "project_dir", lambda pid: tmp_path)
    monkeypatch.setattr(routes.pipeline_view, "aspect_of", lambda pdir: "16:9")
    monkeypatch.setattr(step_llm_check, "steps", lambda *a: ([{"n": 4, "name": "Relationships", "status": status}], {}, None))
    calls = []
    monkeypatch.setattr(visual_planning, "start_fix", lambda pdir, stage=None: calls.append(("fix", stage)))
    monkeypatch.setattr(step_llm_check, "recheck", lambda pdir, stage_id, aspect, n: calls.append(("check", stage_id, n)) or True)
    return calls


def test_a_planning_step_with_warnings_solves_only_its_own_warnings(monkeypatch, tmp_path):
    calls = _setup(monkeypatch, tmp_path, "warning")
    assert routes.retry_stage_subtask("p", "planning", 4) == {"kind": "solve_warnings", "started": True}
    assert calls == [("fix", 4)]


def test_any_other_step_gets_its_llm_check_asked_again(monkeypatch, tmp_path):
    calls = _setup(monkeypatch, tmp_path, "completed")
    assert routes.retry_stage_subtask("p", "planning", 4)["kind"] == "llm_check"
    assert routes.retry_stage_subtask("p", "segmentation", 4)["kind"] == "llm_check"
    assert calls == [("check", "planning", 4), ("check", "segmentation", 4)]


def test_a_step_that_does_not_exist_or_cannot_be_solved_says_why(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path, "warning")
    with pytest.raises(ApiError) as e:
        routes.retry_stage_subtask("p", "planning", 9)
    assert e.value.status == 404
    monkeypatch.setattr(visual_planning, "start_fix", lambda pdir, stage=None: (_ for _ in ()).throw(review.ReviewError("step 4 has no warning that can be solved here")))
    with pytest.raises(ApiError) as e:
        routes.retry_stage_subtask("p", "planning", 4)
    assert e.value.status == 409


def test_recheck_drops_only_that_steps_check(monkeypatch, tmp_path):
    f = step_llm_check._checks_file(tmp_path, "planning", "16:9")
    f.write_text(json.dumps({"steps": {"3": {"verdict": "confirms", "hash": "a"}, "4": {"verdict": "questions", "hash": "b"}}}), encoding="utf-8")
    monkeypatch.setattr(step_llm_check, "start", lambda *a: True)
    assert step_llm_check.recheck(tmp_path, "planning", "16:9", 4) is True
    assert list(json.loads(f.read_text(encoding="utf-8"))["steps"]) == ["3"]
    step_llm_check._running.add((tmp_path.name, "planning"))                          # a check of the stage runs: nothing is dropped, nothing started
    try:
        assert step_llm_check.recheck(tmp_path, "planning", "16:9", 3) is False
        assert list(json.loads(f.read_text(encoding="utf-8"))["steps"]) == ["3"]
    finally:
        step_llm_check._running.discard((tmp_path.name, "planning"))
