"""Timeline Approval, Stage 12 (backend/timeline_approval.py, its gate in timeline_gate and in the render step, the routes). The real planner, composition builder and Timeline Build make the fixture project; the review
stills are written to the format of Stage 10's preview (generating real stills is Stage 10's own tested job). Nothing here renders a video: the render worker is replaced by a function that fails the test if it is
called without an approval. Run: python -m pytest tests/test_timeline_approval.py -q"""
import importlib
import json
import os
import shutil
import wave

import pytest

from backend import jobs
from backend import motion_branch
from backend import motion_gen_report as mgr
from backend import motion_planning as mp
from backend import motion_validation as mv
from backend import motion_validation_preview as pv
from backend import pipeline, render, timeline_approval as ta, timeline_build as tb, timeline_gate

_g = importlib.import_module("test_motion_generation")
_mo = importlib.import_module("test_motion_only_mode")
_v = importlib.import_module("test_motion_validation")
make, client = _g.make, _g.client
A = "16:9"


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    d, *_ = make(tmp_path_factory.mktemp("tap"), with_vp=False)
    (d / "motion_plan.json").unlink()
    assert pipeline.execute(d, "motion-plan", pipeline.Ctx())["status"] == "ran"
    assert pipeline.execute(d, "motion-build", pipeline.Ctx())["status"] == "ran"
    wav = _mo.wav_bytes()
    for name in {"audio.wav", json.loads((d / "composition.json").read_text(encoding="utf-8"))["meta"]["audio"]}:
        (d / name).write_bytes(wav)
    return d


@pytest.fixture
def pd(built, tmp_path, monkeypatch):
    d = tmp_path / "p"
    shutil.copytree(built, d)
    for f in ("motion_timeline_validation.json", "motion_validation_exceptions.json", *(tb.names(A)[k] for k in ("timeline", "report", "attempt")), *(ta.names(A)[k] for k in ("history", "review"))):
        (d / f).unlink(missing_ok=True)
    shutil.rmtree(d / "motion_validation_preview", ignore_errors=True)
    monkeypatch.setattr(mv, "blockers", lambda *a, **k: [])             # Stage 10 and the upstream gates have their own tests: here they say "current and ready"
    monkeypatch.setattr(mp, "blockers", lambda *a, **k: None)
    monkeypatch.setattr(mgr, "blockers", lambda *a, **k: None)
    monkeypatch.setattr(motion_branch, "blockers", lambda *a, **k: [])    # (the fixture's audio is replaced after Motion Generation ran, so the branch's own freshness check would object: not what is tested here)
    return d


stills = _mo.stills                                  # (written in test_motion_only_mode: the Motion-Only tests approve through Stage 12 too)


def reviewable(d):
    """A project whose timeline is built, whose pre-render check passed and whose review stills match: ready_for_review."""
    assert pipeline.execute(d, "motion-validate", pipeline.Ctx())["status"] == "ran"
    assert tb.run(d, A)["status"] in tb.OK
    stills(d)
    return d


def acks(state):
    return [{"key": r["key"], "acknowledged": True} for r in state["requirements"]]


def body(state, decision="approved", key="k1", who="Asha", **over):
    return {"decision": decision, "review_id": state["review_id"], "expected_fingerprint": state["fingerprint"], "decision_by": who, "idempotency_key": key, "warning_acknowledgements": acks(state), **over}


def events(d):
    f = d / ta.names(A)["history"]
    return json.loads(f.read_text(encoding="utf-8"))["events"] if f.exists() else []


def touch(d):
    f = d / "composition.json"
    f.write_text(f.read_text(encoding="utf-8") + " ", encoding="utf-8")


# ---------- readiness: nothing is reviewable until it is built, current and has a matching preview ----------
def test_nothing_can_be_decided_until_the_timeline_is_built_current_and_has_matching_stills(pd):
    s = ta.state(pd, A)
    assert s["status"] == "not_ready" and not s["approval_allowed"] and s["blockers"] and s["manifest"] is None
    with pytest.raises(ta.ApprovalError) as e:
        ta.decide(pd, A, {"decision": "approved", "review_id": "x", "expected_fingerprint": "y", "decision_by": "Asha", "idempotency_key": "k"})
    assert e.value.code == "timeline_not_ready" and events(pd) == []
    assert pipeline.execute(pd, "motion-validate", pipeline.Ctx())["status"] == "ran" and tb.run(pd, A)["status"] in tb.OK
    s = ta.state(pd, A)                                                                                       # built and current, but no stills yet
    assert s["status"] == "not_ready" and any("review preview" in b for b in s["blockers"]) and not s["preview"]["verified"]
    stills(pd)
    assert ta.state(pd, A)["status"] == "ready_for_review"


def test_opening_and_preparing_the_review_approves_nothing_and_shows_every_limitation_honestly(pd):
    reviewable(pd)
    mine = ("timeline.json", "timeline_build_report.json")
    before = {n: (pd / n).read_bytes() for n in mine}
    s = ta.prepare_review(pd, A)
    m = s["manifest"]
    assert s["status"] == "ready_for_review" and not s["approved"] and events(pd) == [] and (pd / ta.names(A)["review"]).exists()
    assert m["scene_count"] == len(m["scenes"]) > 0 and m["timeline_fingerprint"] == s["fingerprint"] and m["preview"]["verified"] and m["preview"]["note"].startswith("quarter-size stills")
    assert m["review_coverage"]["stills_reviewed_by_person"] is False and m["review_coverage"]["motion_playback_reviewed"] is False
    codes = {r["code"] for r in s["requirements"]}
    assert {"stills_not_reviewed_by_person", "motion_playback_not_reviewed"} <= codes                           # the coverage nobody has is a limitation, never silently green
    assert {n: (pd / n).read_bytes() for n in mine} == before                                                  # the timeline itself was not touched


# ---------- the decision ----------
def test_an_approval_needs_every_acknowledgement_the_name_and_the_current_version_and_is_read_back(pd):
    reviewable(pd)
    s = ta.state(pd, A)
    with pytest.raises(ta.ApprovalError) as e:
        ta.decide(pd, A, body(s, warning_acknowledgements=acks(s)[:-1]))
    assert e.value.code == "acknowledgement_required" and len(e.value.blockers) == 1 and events(pd) == []        # one missing: nothing is recorded
    with pytest.raises(ta.ApprovalError, match="name"):
        ta.decide(pd, A, body(s, who=" "))
    with pytest.raises(ta.ApprovalError) as e:
        ta.decide(pd, A, {**body(s), "expected_fingerprint": "0" * 16})
    assert e.value.code == "timeline_changed" and events(pd) == []
    out = ta.decide(pd, A, body(s))
    ev = events(pd)
    assert out["outcome"] == "recorded" and out["status"] == "approved" and out["approved"] and len(ev) == 1      # one record, read back
    d = ev[0]
    assert d["decision"] == "approved" and d["timeline_fingerprint"] == s["fingerprint"] and d["decided_by"] == "Asha" and d["decided_by_source"] == "self_declared"
    assert d["review_coverage"] == {"stills_reviewed_by_person": False, "motion_playback_reviewed": False} and len(d["warning_acknowledgements"]) == len(s["requirements"])
    assert {r["rule_id"] for r in ta.state(pd, A)["requirements"]} == {r["rule_id"] for r in s["requirements"]}   # acknowledging removed no warning


def test_the_same_request_twice_and_a_second_approval_of_the_same_version_make_one_record(pd):
    reviewable(pd)
    s = ta.state(pd, A)
    ta.decide(pd, A, body(s, key="same"))
    again = ta.decide(pd, A, body(s, key="same"))
    other = ta.decide(pd, A, body(s, key="different"))
    assert again["outcome"] == "already_recorded" and other["outcome"] == "already_approved" and len(events(pd)) == 1


def test_changes_requested_needs_a_reason_blocks_the_version_and_changes_nothing_in_the_timeline(pd):
    reviewable(pd)
    s = ta.state(pd, A)
    tl = (pd / "timeline.json").read_bytes()
    with pytest.raises(ta.ApprovalError, match="reason"):
        ta.decide(pd, A, body(s, "changes_requested", key="c0"))
    out = ta.decide(pd, A, body(s, "changes_requested", key="c1", comments=[{"scene_id": "scene_08", "time_seconds": 48.2, "severity": "major", "text": "Review the settlement visual."}]))
    assert out["status"] == "changes_requested" and ta.gate(pd, A) and (pd / "timeline.json").read_bytes() == tl
    with pytest.raises(ta.ApprovalError) as e:
        ta.decide(pd, A, body(s, key="c2"))
    assert e.value.code == "changes_requested_for_this_version"


def test_a_withdrawal_ends_the_approval_and_is_recorded(pd):
    reviewable(pd)
    s = ta.state(pd, A)
    ta.decide(pd, A, body(s))
    assert ta.gate(pd, A) == []
    out = ta.decide(pd, A, {**body(s, "withdrawn", key="w1"), "warning_acknowledgements": []})
    assert out["status"] == "ready_for_review" and ta.gate(pd, A) and [e["decision"] for e in events(pd)] == ["approved", "withdrawn"]


# ---------- invalidation: the status is recomputed from the record and the CURRENT inputs ----------
def test_any_change_to_the_version_makes_the_approval_stale_but_the_history_keeps_it(pd):
    reviewable(pd)
    s = ta.state(pd, A)
    ta.decide(pd, A, body(s))
    touch(pd)                                                                                                  # a composition change: the timeline is built from other inputs now
    st = ta.state(pd, A)
    assert st["status"] == "stale" and not st["approved"] and st["history"][0]["stale"] is True and ta.gate(pd, A)
    assert timeline_gate.state(pd, A)["approved"] is False and timeline_gate.render_blockers(pd, A)


def test_a_decision_on_a_version_that_changed_while_the_page_was_open_is_refused_and_not_recorded(pd):
    reviewable(pd)
    s = ta.state(pd, A)
    touch(pd)
    with pytest.raises(ta.ApprovalError) as e:
        ta.decide(pd, A, body(s))
    assert e.value.code in ("timeline_changed", "timeline_not_ready") and events(pd) == []


def test_a_decision_is_voided_if_the_version_moves_while_it_is_being_written(pd, monkeypatch):
    reviewable(pd)
    s = ta.state(pd, A)
    real = ta._append

    def append_then_change(*a, **k):
        real(*a, **k)
        touch(pd)
    monkeypatch.setattr(ta, "_append", append_then_change)
    with pytest.raises(ta.ApprovalError) as e:
        ta.decide(pd, A, body(s))
    assert e.value.code == "timeline_changed" and events(pd)[0]["voided"] and ta.state(pd, A)["status"] != "approved"


# ---------- the preview must be proven to depict this version ----------
@pytest.mark.parametrize("break_it, why", [("file", "changed"), ("composition", "another version"), ("missing", "no preview")])
def test_a_preview_that_does_not_match_blocks_the_review(pd, break_it, why):
    reviewable(pd)
    man = pv.load(pd, A)
    if break_it == "file":
        (pv.folder(pd, A) / man["samples"][0]["file"]).write_bytes(b"not a png")
    elif break_it == "composition":
        man["composition_sha"] = "0" * 16
        (pv.folder(pd, A) / "manifest.json").write_text(json.dumps(man), encoding="utf-8")
    else:
        (pv.folder(pd, A) / "manifest.json").unlink()
    s = ta.state(pd, A)
    assert s["status"] == "not_ready" and not s["preview"]["verified"] and why in s["preview"]["reason"] and not s["approval_allowed"]


def test_review_coverage_is_only_what_a_person_recorded_and_playback_stays_unreviewed_here(pd):
    reviewable(pd)
    pv.review(pd, A, "stills", "Asha")
    s = ta.state(pd, A)
    codes = {r["code"] for r in s["requirements"]}
    assert s["review_coverage"]["stills_reviewed_by_person"] is True and "stills_not_reviewed_by_person" not in codes and "motion_playback_not_reviewed" in codes
    ta.decide(pd, A, body(s))
    assert events(pd)[0]["review_coverage"] == {"stills_reviewed_by_person": True, "motion_playback_reviewed": False}


# ---------- fail closed ----------
def test_a_record_that_cannot_be_written_or_read_never_shows_as_approved(pd, monkeypatch):
    reviewable(pd)
    s = ta.state(pd, A)
    real = os.replace

    def failing(src, dst):
        if str(dst).endswith("timeline_approval_history.json"):
            raise OSError("disk full (test)")
        return real(src, dst)
    monkeypatch.setattr(ta.os, "replace", failing)
    with pytest.raises(ta.ApprovalError) as e:
        ta.decide(pd, A, body(s))
    assert e.value.code == "approval_error" and events(pd) == [] and ta.state(pd, A)["status"] == "ready_for_review"
    monkeypatch.setattr(ta.os, "replace", real)
    (pd / ta.names(A)["history"]).write_text("{ not json", encoding="utf-8")
    bad = ta.state(pd, A)
    assert bad["status"] == "approval_error" and not bad["approved"] and ta.gate(pd, A) and not ta.legacy_state(pd, A)["approved"]


def test_a_job_that_is_running_stops_a_decision_but_does_not_change_what_the_version_is(pd, monkeypatch):
    reviewable(pd)
    s = ta.state(pd, A)
    monkeypatch.setattr(jobs, "is_running", lambda pid: pid == pd.name)                                       # an orchestrator run is in progress for this project
    with pytest.raises(ta.ApprovalError) as e:
        ta.decide(pd, A, body(s))
    assert e.value.code == "job_running" and ta.state(pd, A)["status"] == "ready_for_review"


# ---------- the audio tail: measured, not assumed ----------
def _wav(path, seconds, loud_tail=False, sr=8000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        n = int(round(seconds * sr))
        w.writeframes(b"".join((b"\x10\x27" if loud_tail and i >= n - 40 else b"\x00\x00") for i in range(n)))


@pytest.mark.parametrize("loud, silent", [(False, True), (True, False)])
def test_the_audio_tail_the_renderer_cuts_is_measured_on_the_file(tmp_path, loud, silent):
    _wav(tmp_path / "audio.wav", 1.0 + 0.011, loud_tail=loud)
    T = {"profile": {"duration_frames": 30, "fps": 30, "duration_seconds_source": 1.011}, "tracks": [{"items": [{"source_ref": "audio.wav"}]}]}
    r = ta.audio_tail_impact(tmp_path, T, [{"end": 0.83}])
    assert r["measured"] and r["cut_is_digital_silence"] is silent and r["cut_seconds"] == 0.011 and r["speech_ends_before_cut_seconds"] == 0.17
    assert ("no audio content is lost" in r["conclusion"]) is silent


# ---------- the render gate: independent of the page ----------
def test_the_render_gate_blocks_without_a_current_approval_in_the_route_check_and_in_the_worker(pd, monkeypatch):
    reviewable(pd)
    called = []
    monkeypatch.setattr(render, "render", lambda *a, **k: called.append(1) or pd / "out.mp4")
    assert any("approve" in b for b in timeline_gate.render_blockers(pd, A))
    with pytest.raises(pipeline.StepError, match="needs the current timeline to be approved"):
        pipeline.execute(pd, "render-final", pipeline.Ctx())                                                   # the worker checks by itself
    assert called == []
    s = ta.state(pd, A)
    ta.decide(pd, A, body(s))
    assert timeline_gate.render_blockers(pd, A) == [] and timeline_gate.state(pd, A)["approved"]
    touch(pd)
    with pytest.raises(pipeline.StepError, match="approved"):
        pipeline.execute(pd, "render-final", pipeline.Ctx())                                                   # approved once, changed since: stopped inside the worker too
    assert called == []


def test_the_worker_may_run_its_own_job_and_a_preview_render_needs_no_approval(pd, monkeypatch):
    reviewable(pd)
    s = ta.state(pd, A)
    ta.decide(pd, A, body(s))
    monkeypatch.setattr(jobs, "is_running", lambda pid: pid == pd.name)                                       # the render job itself is the running job
    pipeline._approval_still_holds(pd, A, preview=False)                                                         # does not raise: its own job is not a blocker
    assert ta.gate(pd, A) and "job is running" in ta.gate(pd, A)[0]                                              # but any other new render is refused while a job runs
    monkeypatch.undo()
    pipeline._approval_still_holds(pd, A, preview=True)


# ---------- the API ----------
def test_the_api_reads_the_llm_decision_and_keeps_the_old_approve_route_out(client):
    """Stage 10 is decided by the LLM approval review inside the timeline job (timeline-approve), never by a click: Timeline Build -> Approval -> Render run without a person."""
    c = client
    pid, pdir = _v.api_project(c)
    r = c.get(f"/projects/{pid}/timeline-approval")
    assert r.status_code == 200 and r.json()["status"] == "not_ready" and not r.json()["approved"]          # no timeline yet
    assert c.post(f"/projects/{pid}/timeline/approve").status_code == 409                                      # the old one-click approval does not exist here
    r = c.post(f"/projects/{pid}/timeline-build/run")
    assert r.status_code == 202 and r.json()["steps"][-2:] == ["timeline-approve", "render-final"]
    assert _mo.wait_job(c, pid, timeout=240)["error"] is None
    st = c.get(f"/projects/{pid}/timeline-approval").json()
    assert st["status"] == "approved" and st["approved"]
    s = _mo.stages(c, pid)
    assert s["approval"]["status"] == "completed" and s["render"]["status"] == "completed" and (pdir / "out.mp4").exists()
def test_an_old_approval_does_not_block_a_decision_on_a_new_clean_version(pd, monkeypatch):
    reviewable(pd)
    s = ta.state(pd, A)
    ta.decide(pd, A, body(s))
    real = ta.fingerprint
    monkeypatch.setattr(ta, "fingerprint", lambda *a, **k: "f" * 16 if real(*a, **k) else None)       # a new built, previewed version: another fingerprint, nothing blocking
    st = ta.state(pd, A)
    assert st["status"] == "ready_for_review" and st["approval_allowed"] and not st["approved"]
    assert st["history"][0]["stale"] is True                                                           # the old approval stays in the history, marked stale
    assert ta.gate(pd, A)                                                                              # and still does not open the render gate
