"""Timeline Build, Stage 11 (backend/timeline_build.py, the step, the chain, the API). The real planner and the real composition builder make the fixture project (no stored Visual Plan or Scene
Segmentation: the builder says so, it does not hide it); tampered artifacts go through the same code. The Stage 10 verdict is a separate stage with its own tests: here it is cleared by
`clear_gates` except in the tests that prove the gate itself. Run: python -m pytest tests/test_timeline_build.py -q"""
import hashlib
import importlib
import json
import os
import shutil

import pytest

from backend import motion_gen_report as mgr
from backend import motion_planning as mp
from backend import motion_validation as mv
from backend import pipeline
from backend import timeline_build as tb

_g = importlib.import_module("test_motion_generation")
_mo = importlib.import_module("test_motion_only_mode")
_v = importlib.import_module("test_motion_validation")
make, client = _g.make, _g.client
ASPECT = "16:9"


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    d, *_ = make(tmp_path_factory.mktemp("tlb"))
    (d / "motion_plan.json").unlink()
    assert pipeline.execute(d, "motion-plan", pipeline.Ctx())["status"] == "ran"
    assert pipeline.execute(d, "motion-build", pipeline.Ctx())["status"] == "ran"
    wav = _mo.wav_bytes()
    for name in {"audio.wav", json.loads((d / "composition.json").read_text(encoding="utf-8"))["meta"]["audio"]}:
        (d / name).write_bytes(wav)
    return d


@pytest.fixture
def pd(built, tmp_path):
    d = tmp_path / "p"
    shutil.copytree(built, d)
    for f in ("motion_timeline_validation.json", "motion_validation_exceptions.json", *(tb.names(ASPECT)[k] for k in ("timeline", "report", "attempt"))):
        (d / f).unlink(missing_ok=True)
    return d


@pytest.fixture
def clear_gates(monkeypatch):
    """Stage 10 and the two upstream gates are tested elsewhere: here they say 'current and ready' so the Timeline Build itself is what is tested."""
    monkeypatch.setattr(mv, "blockers", lambda *a, **k: [])
    monkeypatch.setattr(mp, "blockers", lambda *a, **k: None)
    monkeypatch.setattr(mgr, "blockers", lambda *a, **k: None)


def upstream(d) -> dict:
    skip = ("timeline", "motion_timeline_validation", "motion_validation_")
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in d.iterdir() if p.is_file() and not p.name.startswith(skip)}


def edit_comp(d, fn):
    f = d / "composition.json"
    comp = json.loads(f.read_text(encoding="utf-8"))
    fn(comp)
    f.write_text(json.dumps(comp, ensure_ascii=False), encoding="utf-8")


def touch(d):
    f = d / "composition.json"
    f.write_text(f.read_text(encoding="utf-8") + " ", encoding="utf-8")


def rule(rep, rid):
    return next((f for f in rep["findings"] if f["rule_id"] == rid), None)


# ---------- the build ----------
def test_a_build_publishes_a_timeline_that_matches_the_composition_and_changes_nothing_upstream(pd, clear_gates):
    before = upstream(pd)
    rep = tb.run(pd, ASPECT)
    comp = json.loads((pd / "composition.json").read_text(encoding="utf-8"))
    T = json.loads((pd / "timeline.json").read_text(encoding="utf-8"))
    assert rep["status"] in tb.OK and rep["summary"]["blockers"] == 0 and rep["summary"]["errors"] == 0
    assert rep["persistence"] == {"published": True, "written": True, "read_back_ok": True, "digest_equal": True, "inputs_rechecked": True}
    assert [s["stage_id"] for s in rep["stages"]] == [s[0] for s in tb.STAGES] and rep["stages"][-1]["status"] == "completed"
    clips = T["tracks"][1]["items"]
    fps = comp["meta"]["fps"]
    assert len(clips) == len(comp["scenes"]) == rep["counts"]["scenes"] and T["profile"]["duration_frames"] == mp.fr(comp["meta"]["duration"], fps)
    for c, s in zip(clips, comp["scenes"]):                                                                      # the ONE rule, half-open intervals
        assert (c["start_frame"], c["end_frame"]) == (mp.fr(s["start"], fps), mp.fr(s["end"], fps)) and c["end_frame"] > c["start_frame"] and len(c["layers"]) == len(s["layers"])
    assert clips[0]["start_frame"] == 0 and clips[-1]["end_frame"] == T["profile"]["duration_frames"] and all(a["end_frame"] == b["start_frame"] for a, b in zip(clips, clips[1:]))
    assert T["timing"]["interval_convention"] == "half_open" and T["approval"] == {"status": "not_approved", "approved_fingerprint": None} and rep["approval"]["status"] == "not_approved"
    assert len(T["tracks"][0]["items"]) == 1 and T["tracks"][0]["items"][0]["playback_rate"] == 1.0                    # one audio clip, normal speed
    assert all(t["supported"] and t["start_frame"] == t["boundary_frame"] for t in T["transitions"]) and all(g["policy"] == "hold_previous_scene" for g in T["gap_intervals"])
    st = tb.load(pd, ASPECT)
    assert st["current"] and st["coherent"] and tb.blockers(pd, ASPECT) == []
    assert upstream(pd) == before                                                                              # nothing upstream was touched
    assert not (pd / "timeline_approval.json").exists() and not (pd / "out.mp4").exists() and not list(pd.glob("*.tmp"))


def test_the_same_inputs_are_reused_and_a_rebuild_is_semantically_identical(pd, clear_gates):
    first = tb.run(pd, ASPECT)
    raw = (pd / "timeline.json").read_bytes()
    again = tb.run(pd, ASPECT)
    assert again.get("reused") is True and (pd / "timeline.json").read_bytes() == raw                           # nothing was rebuilt
    for f in ("timeline.json", "timeline_build_report.json", "timeline_build_attempt.json"):
        (pd / f).unlink()
    rebuilt = tb.run(pd, ASPECT)
    assert rebuilt.get("reused") is None and rebuilt["timeline_fingerprint"] == first["timeline_fingerprint"]    # deterministic: same inputs, same digest


def test_a_new_publish_keeps_the_last_good_pair_in_a_backup(pd, clear_gates):
    tb.run(pd, ASPECT)
    touch(pd)                                                                                                  # a new composition digest, nothing that breaks a rule
    rep = tb.run(pd, ASPECT)
    assert rep["status"] in tb.OK and len(list((pd / "timeline_backup").glob("*/timeline.json"))) == 1 and len(list((pd / "timeline_backup").glob("*/timeline_build_report.json"))) == 1


# ---------- the gates ----------
def test_a_stage_10_that_has_not_cleared_the_output_stops_the_build_and_nothing_is_published(pd):
    rep = tb.run(pd, ASPECT)                                                                                   # Stage 10 has not run: the real gate
    assert rep["status"] == "blocked" and rule(rep, "freshness.stage10_ready") and rep["persistence"]["published"] is False
    assert not (pd / "timeline.json").exists() and (pd / "timeline_build_attempt.json").exists()
    assert tb.load(pd, ASPECT)["status"] == "blocked" and tb.blockers(pd, ASPECT)
    skipped = [s["stage_id"] for s in rep["stages"] if s["status"] == "skipped_due_to_dependency"]
    assert "scene_mapping" in skipped and "validation" in skipped                                              # nothing was assembled from blocked inputs


def test_a_missing_input_is_a_precise_blocker(pd, clear_gates):
    (pd / "motion_generation.json").unlink()
    rep = tb.run(pd, ASPECT)
    assert rep["status"] == "blocked" and rule(rep, "input.exists")["evidence"]["file"] == "motion_generation.json" and not (pd / "timeline.json").exists()


def test_a_changed_input_makes_the_timeline_stale_and_the_last_good_one_is_kept_for_comparison(pd, clear_gates):
    tb.run(pd, ASPECT)
    raw = (pd / "timeline.json").read_bytes()
    touch(pd)
    st = tb.load(pd, ASPECT)
    assert st["status"] == "stale" and st["stale"] and not st["current"] and "changed" in tb.blockers(pd, ASPECT)[0] and (pd / "timeline.json").read_bytes() == raw


# ---------- the checks on the built object ----------
def test_a_hole_between_scenes_is_a_blocker_and_the_good_timeline_survives(pd, clear_gates):
    ok = tb.run(pd, ASPECT)
    raw = (pd / "timeline.json").read_bytes()
    edit_comp(pd, lambda c: c["scenes"][1].update(start=round(c["scenes"][1]["start"] + 0.4, 3)))
    rep = tb.run(pd, ASPECT)
    assert rep["status"] == "blocked" and rule(rep, "time.frames_match_plan") and rep["persistence"]["published"] is False          # the plan's frames disagree: nothing is assembled from it
    assert (pd / "timeline.json").read_bytes() == raw and ok["status"] in tb.OK and tb.load(pd, ASPECT)["status"] == "blocked"      # the failed attempt did not replace it


def test_a_transition_the_renderer_cannot_draw_or_would_shorten_is_reported_not_hidden(pd, clear_gates):
    def bad(c):
        c["scenes"][0]["transition_out"] = {"type": "nope", "dur": 0.4}
        c["scenes"][1]["transition_out"] = {"type": "fade", "dur": 99}
    edit_comp(pd, bad)
    rep = tb.run(pd, ASPECT)
    assert rep["status"] == "blocked" and rule(rep, "transition.supported")["severity"] == "blocker" and rule(rep, "transition.not_clamped")["severity"] == "warning"
    ev = rule(rep, "transition.not_clamped")["evidence"]
    assert ev["applied_frames"] < ev["requested_frames"]


def test_an_audio_the_renderer_would_cut_is_a_blocker(pd, clear_gates):
    (pd / "audio.wav").write_bytes(importlib.import_module("test_m7").wav_bytes(80))                         # longer than the 70 s composition: the renderer would cut it
    rep = tb.run(pd, ASPECT)
    assert rule(rep, "audio.not_truncated")["severity"] == "blocker" and rep["status"] == "blocked" and not (pd / "timeline.json").exists()


def test_a_scene_missing_from_the_composition_is_not_silently_dropped(pd, clear_gates):
    edit_comp(pd, lambda c: c["scenes"].pop())
    rep = tb.run(pd, ASPECT)
    assert rep["status"] == "blocked" and rule(rep, "scene.count_matches") and not (pd / "timeline.json").exists()


def test_an_input_that_changes_while_the_timeline_is_built_is_never_published(pd, clear_gates, monkeypatch):
    real = tb.Builder.stage_validation

    def touch_then_validate(self):
        touch(pd)
        real(self)
    monkeypatch.setattr(tb.Builder, "stage_validation", touch_then_validate)
    rep = tb.run(pd, ASPECT)
    assert rep["status"] == "blocked" and rule(rep, "prov.fingerprint_current") and not (pd / "timeline.json").exists()


def test_a_failed_write_keeps_the_last_good_pair_and_leaves_no_partial_file(pd, clear_gates, monkeypatch):
    tb.run(pd, ASPECT)
    raw, rep0 = (pd / "timeline.json").read_bytes(), (pd / "timeline_build_report.json").read_bytes()
    touch(pd)
    real = os.replace

    def failing(src, dst):
        if str(dst).endswith("timeline.json"):
            raise OSError("disk full (test)")
        return real(src, dst)
    monkeypatch.setattr(tb.os, "replace", failing)
    with pytest.raises(OSError):
        tb.run(pd, ASPECT)
    assert (pd / "timeline.json").read_bytes() == raw and (pd / "timeline_build_report.json").read_bytes() == rep0 and not list(pd.glob("*.tmp"))
    assert tb.load(pd, ASPECT)["attempt"]["status"] == "failed"


def test_two_builds_at_once_are_refused(pd, clear_gates):
    lock = tb._running.setdefault(str(pd.resolve()), tb.threading.Lock())
    lock.acquire()
    try:
        with pytest.raises(tb.BuildError, match="already running"):
            tb.run(pd, ASPECT)
    finally:
        lock.release()


# ---------- the step, the chain and the API ----------
def test_the_step_is_in_the_motion_only_timeline_chain_after_the_gate_and_stops_a_job_instead_of_going_green(pd):
    assert pipeline.CHAINS["timeline"][-4:] == ("motion-validate", "timeline-build", "timeline-approve", "render-final") and pipeline.CHAINS["timeline-build"] == ("motion-validate", "timeline-build", "timeline-approve", "render-final")      # the LLM approval then the render follow the build
    with pytest.raises(pipeline.StepError, match="Timeline Build is blocked"):
        pipeline.execute(pd, "timeline-build", pipeline.Ctx())                                                    # Stage 10 has not run: a stopped job, not a green stage


def test_the_api_builds_reads_and_hands_the_version_to_the_llm_approval_and_the_render(client):
    c = client
    pid, pdir = _v.api_project(c)
    assert c.get(f"/projects/{pid}/timeline-build").status_code == 409 and c.get(f"/projects/{pid}/timeline-build").json()["error"]["code"] == "timeline_build_missing"
    assert c.get(f"/projects/{pid}/timeline-build/timeline").status_code == 409
    assert c.post(f"/projects/{pid}/motion-timeline-validation/run").status_code == 202 and _mo.wait_job(c, pid, timeout=240)["error"] is None
    r = c.post(f"/projects/{pid}/timeline-build/run")
    assert r.status_code == 202 and r.json()["steps"] == ["motion-validate", "timeline-build", "timeline-approve", "render-final"]      # no person between the build, the approval and the render
    assert _mo.wait_job(c, pid, timeout=240)["error"] is None
    st = c.get(f"/projects/{pid}/timeline-build").json()
    assert st["status"] in tb.OK and st["current"] and st["blockers"] == [] and st["report"]["approval"]["status"] == "not_approved" and len(st["report"]["stages"]) == 12
    T = c.get(f"/projects/{pid}/timeline-build/timeline").json()
    assert T["project_id"] == pid and T["tracks"][1]["items"] and T["source_fingerprint"] == st["report"]["source_fingerprint"]
    stage = _mo.stages(c, pid)
    assert stage["timeline"]["status"] == "completed" and stage["approval"]["status"] == "completed" and stage["render"]["status"] == "completed"      # approved by the LLM review, then rendered
    assert (pdir / "out.mp4").exists()
