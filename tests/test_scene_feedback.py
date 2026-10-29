"""Phase 5b: what Final QC saw in the rendered video goes back to the scene it names, and only that scene is written again, once per plan.
Run: python -m pytest tests/test_scene_feedback.py -q"""
import json

import pytest

from SYSTEM.core import llm_gateway
from SYSTEM.memory import store
from SYSTEM.policies import llm_review
from VIDEO_ENGINE.pipeline.orchestrator import PipelineOrchestrator
from VIDEO_ENGINE.stages import config, motion_animation as ma, scene_feedback as sf


def _finding(sev, cat, scene, msg="m", rec=None):
    return {"severity": sev, "category": cat, "message": msg, "scene_id": scene, "recommendation": rec}


@pytest.fixture
def pdir(tmp_path, monkeypatch):
    p = tmp_path / "p"
    p.mkdir()
    (p / "scene_plan.json").write_text(json.dumps({"scenes": [{"id": 1}, {"id": 2}]}), encoding="utf-8")
    (p / "visual_planning.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(llm_review, "review_is_current", lambda pdir, stage, aspect="16:9": True)
    return p


def _review(monkeypatch, findings):
    monkeypatch.setattr(llm_review, "load_review", lambda pdir, stage, aspect="16:9": {"findings": findings})


def test_a_visual_finding_with_a_scene_becomes_that_scenes_note_and_nothing_else_does(pdir, monkeypatch):
    _review(monkeypatch, [_finding("warning", "visual", "scene_002", "empty entry frame", "regenerate scene 2: show content earlier"),
                          _finding("error", "visual", 8, "text cut off"),
                          _finding("info", "visual", "scene_001", "a remark"),                       # a remark is not a request
                          _finding("warning", "transitions", "scene_001", "cut washes"),            # another category
                          _finding("warning", "visual", None, "no scene named")])                   # nothing to point at
    assert sf.apply(pdir, "16:9") == ["2", "8"]
    assert sf.note_for(pdir, "16:9", 2) == "empty entry frame regenerate scene 2: show content earlier"
    assert sf.note_for(pdir, "16:9", "8") == "text cut off" and sf.note_for(pdir, "16:9", 1) is None


def test_there_is_one_round_per_plan_and_a_new_plan_starts_again(pdir, monkeypatch):
    _review(monkeypatch, [_finding("warning", "visual", "scene_002", "a")])
    assert sf.apply(pdir, "16:9") == ["2"]
    _review(monkeypatch, [_finding("warning", "visual", "scene_002", "b")])                          # the second look still finds something: the round is spent
    assert sf.apply(pdir, "16:9") == [] and sf.note_for(pdir, "16:9", 2) == "a"
    (pdir / "visual_planning.json").write_text('{"v": 2}', encoding="utf-8")                          # another plan: no notes, a full budget
    assert sf.note_for(pdir, "16:9", 2) is None and sf.apply(pdir, "16:9") == ["2"]
    assert sf.note_for(pdir, "16:9", 2) == "b"


def test_no_current_review_or_no_finding_asks_for_nothing(pdir, monkeypatch):
    _review(monkeypatch, [_finding("info", "visual", "scene_002")])
    assert sf.apply(pdir, "16:9") == [] and not sf.path(pdir, "16:9").exists()
    _review(monkeypatch, [_finding("error", "visual", "scene_002")])
    monkeypatch.setattr(llm_review, "review_is_current", lambda *a, **k: False)                     # a verdict about another video is not acted on
    assert sf.apply(pdir, "16:9") == []


def test_the_note_is_in_the_scene_fingerprint_only_when_it_exists_and_in_the_prompt(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path)
    p = store.create("Fb", "16:9")
    (p / "scene_plan.json").write_text(json.dumps({"scenes": [{"id": 2, "start": 0, "end": 3, "meaning": "m"}], "style": {"palette": ["#000"]}}), encoding="utf-8")

    class Stop(Exception):
        pass
    seen = {}

    def capture(**inputs):
        seen.clear()
        seen.update(inputs)
        raise Stop
    monkeypatch.setattr(ma, "scene_input_fingerprint", capture)
    for expect in (False, True):
        if expect:
            sf.path(p, "16:9").write_text(json.dumps({"plan": sf._plan_key(p), "rounds": 1, "notes": {"2": "show content earlier"}}), encoding="utf-8")
        with pytest.raises(Stop):
            ma.generate_custom_motion_code(p)
        assert ("feedback" in seen) is expect and (seen.get("feedback") == "show content earlier" or not expect)
    prompts = []

    def execute(req):
        prompts.append(req.user_prompt)
        raise RuntimeError("stop")
    monkeypatch.setattr(llm_gateway.gateway, "execute", execute)
    with pytest.raises(ma.AnimationCodegenError):
        ma.generate_scene_tsx_via_llm(p, 2, 3.0, "T", "", [], ["#000"], feedback="show content earlier")
    assert "LOOKED at the rendered video" in prompts[0] and "show content earlier" in prompts[0]
    with pytest.raises(ma.AnimationCodegenError):
        ma.generate_scene_tsx_via_llm(p, 2, 3.0, "T", "", [], ["#000"])
    assert "LOOKED at the rendered video" not in prompts[1]


def test_a_note_makes_motion_generation_stale_and_no_note_changes_nothing(tmp_path):
    p = tmp_path / "p"
    p.mkdir()
    before = llm_review.compute_stage_input_fingerprint(p, "motion_gen")
    assert llm_review.compute_stage_input_fingerprint(p, "motion_gen") == before
    sf.path(p, "16:9").write_text("{}", encoding="utf-8")
    assert llm_review.compute_stage_input_fingerprint(p, "motion_gen") != before


def test_the_run_writes_the_named_scenes_again_once_and_then_stops(tmp_path, monkeypatch):
    calls = []

    class Run:
        run_id, correlation_id = "r", "c"
    o = object.__new__(PipelineOrchestrator)
    o.pdir, o.aspect, o.project_id = tmp_path, "16:9", "p"
    monkeypatch.setattr("VIDEO_ENGINE.pipeline.orchestrator.communication.publish_lifecycle_event", lambda **k: calls.append(("event", k["detail"])))
    monkeypatch.setattr(o, "_execute_run", lambda run, **kw: calls.append(("run", kw)))
    rounds = [["2", "8"], []]
    monkeypatch.setattr(sf, "apply", lambda pdir, aspect: rounds.pop(0))
    assert o._visual_fix(Run(), 3) is True and calls[-1] == ("run", {"from_stage": "motion_gen", "resume": False, "max_retries": 3}) and "2, 8" in calls[0][1]
    calls.clear()
    assert o._visual_fix(Run(), 3) is False and calls == []                                          # the round is spent: nothing runs again
