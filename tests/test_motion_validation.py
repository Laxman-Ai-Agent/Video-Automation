"""Motion & Timeline Validation, Stage 10 (backend/motion_validation.py, motion_validation_rules.py, motion_validation_preview.py, the step, the gate, the API). Real planner and real composition
builder on a fixture project (made without a stored Visual Plan or Scene Segmentation, the way old projects are: the validator says so, it does not hide it); tampered artifacts go through the
same code. Run: python -m pytest tests/test_motion_validation.py -q"""
import hashlib
import importlib
import json
import shutil

import pytest
from PIL import Image

from backend import motion_validation as mv
from backend import motion_validation_preview as pv
from backend import motion_validation_rules as R
from backend import pipeline

_g = importlib.import_module("test_motion_generation")
_mo = importlib.import_module("test_motion_only_mode")
make, client = _g.make, _g.client
ASPECT = "16:9"
REASON = "accepted for this test run"


@pytest.fixture(scope="module")
def built(tmp_path_factory, llm_codegen_stub_module):
    d, *_ = make(tmp_path_factory.mktemp("val"))
    (d / "motion_plan.json").unlink()
    assert pipeline.execute(d, "motion-plan", pipeline.Ctx())["status"] == "ran"
    assert pipeline.execute(d, "motion-build", pipeline.Ctx())["status"] == "ran"
    wav = _mo.wav_bytes()                                                                                        # a real project has its audio: the fixture's is a 1 s dummy (its length is a review finding)
    for name in {"audio.wav", json.loads((d / "composition.json").read_text(encoding="utf-8"))["meta"]["audio"]}:
        (d / name).write_bytes(wav)
    return d


@pytest.fixture
def pd(built, tmp_path):
    """A private copy of the built project: a test may tamper with it."""
    d = tmp_path / "p"
    shutil.copytree(built, d)
    for f in ("motion_timeline_validation.json", "motion_validation_exceptions.json"):
        (d / f).unlink(missing_ok=True)
    return d


def upstream(d) -> dict:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in d.iterdir() if p.is_file() and not p.name.startswith(("motion_timeline_validation", "motion_validation_", "llm_review_motion_validation"))}      # its report and its own LLM review


def finding(rep, rule, scene=None):
    return next((f for f in rep["findings"] if f["rule_id"] == rule and (scene is None or f["scene_id"] == scene)), None)


def touch_composition(d):
    f = d / "composition.json"
    f.write_text(f.read_text(encoding="utf-8").replace('"duration":', '"duration": ', 1), encoding="utf-8")


def write_comp(d, comp):
    (d / "composition.json").write_text(mv.mg.dumps(comp), encoding="utf-8")


# ---------- the report ----------
def test_a_run_writes_one_report_with_12_stages_provenance_and_no_false_green(pd):
    before = upstream(pd)
    rep = mv.run(pd, ASPECT)
    assert [s["stage_id"] for s in rep["stages"]] == [s[0] for s in mv.STAGES] and [s["n"] for s in rep["stages"]] == list(range(1, 13))
    assert rep["phase"] == "motion_timeline_validation" and rep["phase_status"] == "completed" and rep["project_id"] == pd.name
    assert rep["validator"] == {"version": mv.VERSION, "rule_set_version": mv.RULE_SET} and rep["config"]["aspect_ratio"] == ASPECT and rep["config"]["fps"] == 30
    assert {"visual_plan_fingerprint", "motion_plan_fingerprint", "motion_generation_fingerprint", "composition_fingerprint", "renderer_registry_fingerprint"} <= set(rep["inputs"])
    assert rep["summary"]["errors"] == 0 and rep["summary"]["blockers"] == 0 and rep["summary"]["scenes_checked"] == rep["summary"]["scenes_expected"] > 0
    assert rep["readiness"] in ("ready_with_warnings", "needs_review")                                          # an old project (no Scene Segmentation) is never plain "ready"
    assert finding(rep, "input.exists") and finding(rep, "preview.evidence_present") is None                    # the legacy sources are a visible finding; the run made its own preview
    assert rep["preview"]["evidence_generated"] is True and rep["preview"]["technical_checks_passed"] is True
    assert upstream(pd) == before                                                                              # read-only: no artifact upstream was touched
    assert mv.load(pd, ASPECT)["stale"] is False and not list(pd.glob("motion_timeline_validation*.tmp"))
    assert json.loads((pd / "motion_timeline_validation.json").read_text(encoding="utf-8"))["source_fingerprint"] == rep["source_fingerprint"]
    for s in rep["stages"]:
        assert s["checks_passed"] <= s["checks_total"]
    live = [f for f in rep["findings"] if f["status"] == "unresolved"]
    assert rep["summary"]["warnings"] == sum(f["severity"] == "warning" for f in live) and rep["summary"]["info"] == sum(f["severity"] == "info" for f in live)


def test_findings_name_scene_element_rule_evidence_owner_and_have_stable_ids(pd):
    a = mv.run(pd, ASPECT, force=True)
    b = mv.run(pd, ASPECT, force=True)
    assert [f["finding_id"] for f in a["findings"]] == [f["finding_id"] for f in b["findings"]] and len({f["finding_id"] for f in a["findings"]}) == len(a["findings"])
    for f in a["findings"]:
        assert {"finding_id", "rule_id", "severity", "status", "scene_id", "element_id", "message", "evidence", "owner_stage", "suggested_action", "can_auto_fix"} <= set(f) and f["can_auto_fix"] is False


def test_unknown_drawn_geometry_is_said_and_never_counted_as_a_pass(pd):
    rep = mv.run(pd, ASPECT)
    lay = next(s for s in rep["stages"] if s["stage_id"] == "layout_collision")
    unknown = [f for f in rep["findings"] if f["rule_id"] == "layout.renderer_geometry_known"]
    assert lay["checks_skipped"] == len(unknown) and (lay["status"] == "warning" if unknown else True) and rep["summary"]["checks_skipped"] >= len(unknown)


# ---------- stale, missing, failed: never green ----------
def test_a_changed_input_makes_the_report_stale_the_gate_stops_and_the_next_run_blocks(pd):
    mv.run(pd, ASPECT)
    touch_composition(pd)
    rep = mv.load(pd, ASPECT)
    assert rep["stale"] is True and rep["readiness"] == "stale" and rep["readiness_at_validation"] in mv.READY + ("needs_review",)
    assert "out of date" in mv.blockers(pd, ASPECT)[0]
    again = mv.run(pd, ASPECT)                                                                                   # Motion Generation's own report no longer matches the composition: Stage 2 blocks
    assert again["readiness"] == "blocked" and finding(again, "input.fingerprint_current")["severity"] == "blocker"
    assert all(s["status"] == "skipped_due_to_dependency" for s in again["stages"][2:10])                       # the dependent stages are not "completed"


def test_a_missing_input_is_a_precise_blocker_and_the_dependent_stages_do_not_run(pd):
    (pd / "motion_generation.json").unlink()
    rep = mv.run(pd, ASPECT)
    assert rep["readiness"] == "blocked" and any(f["element_id"] == "motion_generation.json" and f["owner_stage"] == "motion_generation" and f["severity"] == "blocker" for f in rep["findings"] if f["rule_id"] == "input.exists")
    assert all(s["status"] == "skipped_due_to_dependency" for s in rep["stages"][1:10]) and rep["stages"][0]["status"] == "blocked" and mv.blockers(pd, ASPECT)


def test_a_validator_that_crashes_leaves_a_failed_report_never_the_old_green_one(pd, monkeypatch):
    mv.run(pd, ASPECT)
    monkeypatch.setattr(R, "stage_timing_frame", lambda x, v: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        mv.run(pd, ASPECT, force=True)
    rep = mv.load(pd, ASPECT)
    assert rep["phase_status"] == "failed" and rep["readiness"] == "failed" and "boom" in rep["error"] and "failed" in mv.blockers(pd, ASPECT)[0]


def test_an_input_that_changes_while_the_validation_runs_gives_stale_not_green(pd):
    rep = mv.run(pd, ASPECT)
    out = mv.commit(pd, ASPECT, json.loads(json.dumps(rep)), "another-fingerprint")
    assert out["readiness"] == "stale" and any(f["rule_id"] == "report.commit_freshness" and f["severity"] == "blocker" for f in out["findings"])


def test_a_report_that_reads_back_different_is_an_error_not_a_success(pd, monkeypatch):
    seen = []
    real = mv.canon
    monkeypatch.setattr(mv, "canon", lambda o: real(o) + str(len(seen.append(1) or seen)) if isinstance(o, dict) and "phase_status" in o else real(o))      # the second canon (the read back) differs
    with pytest.raises(mv.ValidationError, match="read back"):
        mv.run(pd, ASPECT)


# ---------- cache and invalidation ----------
def test_unchanged_stages_are_reused_and_only_the_stages_of_a_changed_input_run_again(pd):
    first = mv.run(pd, ASPECT)
    assert first["cache"]["stages_reused"] == 0
    second = mv.run(pd, ASPECT)
    assert all(s["cache"]["hit"] for s in second["stages"] if s["stage_id"] in mv.STAGE_INPUTS)
    assert [f["finding_id"] for f in second["findings"]] == [f["finding_id"] for f in first["findings"]] and second["summary"]["checks_passed"] == first["summary"]["checks_passed"]
    assert not any(s["cache"]["hit"] for s in mv.run(pd, ASPECT, force=True)["stages"])
    (pd / "motion_fixes.json").write_text(json.dumps({"version": 1, "accepted": [], "scenes": {}, "changes": []}), encoding="utf-8")        # the fix ledger: only the stages that read it are redone
    hits = {s["stage_id"]: s["cache"]["hit"] for s in mv.run(pd, ASPECT)["stages"]}
    assert hits["element_completeness"] is False and hits["transition_readiness"] is True and hits["animation_preset"] is True


def test_a_new_rule_set_version_invalidates_every_stage(pd, monkeypatch):
    mv.run(pd, ASPECT)
    monkeypatch.setattr(mv, "RULE_SET", "9.9")
    rep = mv.run(pd, ASPECT)
    assert rep["cache"]["stages_reused"] == 0 and rep["rule_set"] == "9.9"


# ---------- exceptions: explicit, authorized, fingerprint-bound ----------
def with_finding(pd, rule="element.required_has_drawable", severity="blocker", exceptionable=True):
    """The real report plus one more finding (the fingerprint is made from the inputs, so the stored report stays current)."""
    rep = mv.run(pd, ASPECT)
    f = {"finding_id": f"{rule}:scene_01:x", "rule_id": rule, "stage_id": "element_completeness", "severity": severity, "status": "unresolved", "scene_id": "scene_01", "element_id": "x", "message": "m",
         "evidence": {}, "owner_stage": "motion_generation", "suggested_action": "", "can_auto_fix": False, "exceptionable": exceptionable, "exception": None, "occurrences": 1}
    rep["findings"].append(f)
    rep["stages"][4]["finding_ids"].append(f["finding_id"])
    rep["stages"][4]["status"] = "blocked" if severity in ("blocker", "error") else "warning"
    (pd / "motion_timeline_validation.json").write_text(json.dumps(rep, ensure_ascii=False), encoding="utf-8")
    return f


def test_a_required_visual_that_is_not_drawn_blocks_until_an_explicit_exception_and_it_stays_visible(pd, monkeypatch):
    monkeypatch.setattr(mv, "REVIEW_RULES", frozenset())                                                         # the fixture's dummy 1 s audio is a review warning of its own: this test is about the blocker
    f = with_finding(pd)
    cur = mv.load(pd, ASPECT)
    assert cur["readiness"] == "blocked" and mv.blockers(pd, ASPECT)
    for who, why, fp in (("", "a real reason here", cur["source_fingerprint"]), ("Asha", "short", cur["source_fingerprint"]), ("Asha", "a real reason here", "wrong")):
        with pytest.raises(mv.ValidationError):
            mv.record_exception(pd, ASPECT, f["finding_id"], who, why, fp)
    assert mv.load(pd, ASPECT)["readiness"] == "blocked"                                                         # a generic "accepted" never bypasses it
    rec = mv.record_exception(pd, ASPECT, f["finding_id"], "Asha", "the dome is cut from this edit, the narration still works", cur["source_fingerprint"])
    assert rec["applies_to_fingerprint"] == cur["source_fingerprint"] and rec["decision_by"] == "Asha" and rec["expires_when_inputs_change"] is True
    after = mv.load(pd, ASPECT)
    ff = next(x for x in after["findings"] if x["finding_id"] == f["finding_id"])
    assert after["readiness"] == "ready_with_warnings" and ff["status"] == "accepted_for_version" and ff["severity"] == "blocker" and after["summary"]["accepted_exceptions"] == 1
    assert after["stages"][4]["status"] == "warning" and after["summary"]["stages_blocked"] == 0                    # the stage no longer reads blocked, the finding still reads accepted_for_version
    assert mv.blockers(pd, ASPECT) == []
    assert mv.record_exception(pd, ASPECT, f["finding_id"], "Asha", "the dome is cut from this edit, the narration still works", cur["source_fingerprint"]) == rec     # idempotent
    mv.revoke_exception(pd, ASPECT, rec["exception_id"])
    assert mv.load(pd, ASPECT)["readiness"] == "blocked" and mv.ledger(pd, ASPECT)[0]["revoked_at"]            # the decision and its withdrawal both stay in the ledger


def test_an_error_or_another_blocker_can_never_be_accepted(pd):
    f = with_finding(pd, rule="timing.within_parent", severity="error", exceptionable=False)
    with pytest.raises(mv.ValidationError, match="cannot be accepted"):
        mv.record_exception(pd, ASPECT, f["finding_id"], "Asha", "a real reason here", mv.load(pd, ASPECT)["source_fingerprint"])
    assert mv.load(pd, ASPECT)["readiness"] == "blocked"


def test_an_exception_expires_when_an_input_changes(pd):
    f = with_finding(pd)
    fp = mv.load(pd, ASPECT)["source_fingerprint"]
    mv.record_exception(pd, ASPECT, f["finding_id"], "Asha", "the dome is cut from this edit, the narration still works", fp)
    (pd / "motion_fixes.json").write_text(json.dumps({"version": 1, "accepted": [], "scenes": {}, "changes": []}), encoding="utf-8")
    cur = mv.load(pd, ASPECT)
    assert cur["stale"] is True and cur["readiness"] == "stale" and mv.blockers(pd, ASPECT)
    with pytest.raises(mv.ValidationError, match="out of date"):
        mv.record_exception(pd, ASPECT, f["finding_id"], "Asha", "the dome is cut from this edit, the narration still works", fp)


def test_review_warnings_need_a_decision_and_an_accepted_one_gives_ready_with_warnings(pd):
    f = with_finding(pd, rule="layout.text_graphic_collision", severity="warning")
    cur = mv.load(pd, ASPECT)
    assert cur["readiness"] == "needs_review" and cur["summary"]["unresolved_review_items"] >= 1 and "need a decision" in mv.blockers(pd, ASPECT)[0]
    mv.record_exception(pd, ASPECT, f["finding_id"], "Asha", "the line is meant to cross the title", cur["source_fingerprint"])
    assert mv.load(pd, ASPECT)["readiness"] in ("ready_with_warnings", "needs_review")


def test_readiness_rules_never_call_a_blocker_an_error_a_skipped_check_or_a_failed_stage_green():
    f = lambda sev, rule, status="unresolved": {"severity": sev, "rule_id": rule, "status": status}
    ok = [{"status": "completed", "checks_skipped": 0}]
    assert mv.readiness_of([], ok) == "ready" and mv.readiness_of([f("info", "x")], ok) == "ready"
    assert mv.readiness_of([f("warning", "timing.emphasis_alignment")], ok) == "ready_with_warnings"
    assert mv.readiness_of([f("warning", "layout.safe_margins")], ok) == "needs_review"
    assert mv.readiness_of([f("blocker", "x")], ok) == "blocked" and mv.readiness_of([f("error", "x")], ok) == "blocked"
    assert mv.readiness_of([f("blocker", "x", "accepted_for_version")], ok) == "ready_with_warnings"
    assert mv.readiness_of([], [{"status": "completed", "checks_skipped": 1}]) == "ready_with_warnings"          # a skipped check is not a pass
    assert mv.readiness_of([], [{"status": "skipped_due_to_dependency", "checks_skipped": 0}]) == "blocked"
    assert mv.readiness_of([], [{"status": "failed", "checks_skipped": 0}]) == "failed"


# ---------- rules ----------
def test_scenes_that_overlap_or_leave_an_unplanned_gap_are_errors(pd):
    comp = json.loads((pd / "composition.json").read_text(encoding="utf-8"))
    comp["scenes"][1]["start"] = round(comp["scenes"][1]["start"] + 0.5, 3)
    write_comp(pd, comp)
    x, v = R.X(pd, ASPECT), mv.V()
    R.stage_timing_frame(x, v)
    assert any(f["rule_id"] == "timing.no_prohibited_overlap" and f["severity"] == "error" for f in v.findings.values())


# ---------- the preview evidence ----------
def fake_preview(pd, blank=False):
    gen = json.loads((pd / "motion_generation.json").read_text(encoding="utf-8"))
    folder = pv.folder(pd, ASPECT)
    folder.mkdir(exist_ok=True)
    samples = []
    for i, smp in enumerate(pv.sample_plan(json.loads((pd / "composition.json").read_text(encoding="utf-8")))):
        name = f"{smp['scene_id']}_{smp['kind']}_{smp['frame']:05d}.png"
        img = Image.new("RGB", (48, 27), (10, 10, 10))
        if not (blank and i == 0):
            img.putdata([((x * 5) % 255, (y * 9) % 255, 90) for y in range(27) for x in range(48)])
        img.save(folder / name)
        samples.append({**smp, "file": name, "time_s": 0, "sha": mv.sha((folder / name).read_bytes()), **pv._measure(folder / name)})
    man = {"sampling_rule_version": pv.RULE_VERSION, "composition_sha": gen["output"]["composition_sha"], "renderer_digest": pipeline._remotion_src_digest(), "scale": pv.SCALE, "samples": samples, "reviews": []}
    (folder / "manifest.json").write_text(json.dumps(man), encoding="utf-8")
    return man


def test_the_sampling_is_deterministic_and_covers_every_scene_and_transition(pd):
    comp = json.loads((pd / "composition.json").read_text(encoding="utf-8"))
    a = pv.sample_plan(comp)
    assert a == pv.sample_plan(comp) and {s["scene_id"] for s in a} == {f"scene_{s['id']:02d}" for s in comp["scenes"]}
    assert sum(1 for s in a if s["kind"] == "transition") == sum(1 for s in comp["scenes"] if s.get("transition_out"))
    for s in comp["scenes"]:
        mine = [x["frame"] for x in a if x["scene_id"] == f"scene_{s['id']:02d}" and x["kind"] != "transition"]
        assert mine == sorted(mine) and all(pv.mp.fr(s["start"]) <= f <= pv.mp.fr(s["end"]) for f in mine)


def test_preview_evidence_separates_generated_decoded_reviewed_by_a_person_and_motion_watched(pd):
    rep = mv.run(pd, ASPECT)                                                                                   # the run makes the stills itself (fully automatic): evidence, not a person's review
    p = rep["preview"]
    assert p["evidence_generated"] is True and p["technical_checks_passed"] is True and p["stills_reviewed_by_person"] is False and p["motion_playback_reviewed"] is False
    assert finding(rep, "preview.evidence_present") is None and rep["preview_evidence"] and all(not s["human_reviewed"] for s in rep["preview_evidence"])
    pv.review(pd, ASPECT, "stills", "Asha")
    p = mv.run(pd, ASPECT)["preview"]
    assert p["stills_reviewed_by_person"] is True and p["motion_playback_reviewed"] is False and p["reviews"][0]["by"] == "Asha"      # looking at stills is not watching the motion
    with pytest.raises(mv.ValidationError):
        pv.review(pd, ASPECT, "stills", "")


def test_a_blank_or_broken_or_outdated_preview_frame_is_a_warning_not_a_pass(pd):
    fake_preview(pd, blank=True)
    rep = mv.run(pd, ASPECT)
    assert finding(rep, "preview.not_blank") and rep["preview"]["technical_checks_passed"] is False
    (pv.folder(pd, ASPECT) / pv.load(pd, ASPECT)["samples"][1]["file"]).write_bytes(b"not a png")
    assert finding(mv.run(pd, ASPECT), "preview.frames_decode")
    man = pv.load(pd, ASPECT)
    man["composition_sha"] = "old"
    (pv.folder(pd, ASPECT) / "manifest.json").write_text(json.dumps(man), encoding="utf-8")
    rep = mv.run(pd, ASPECT)                                                                                   # an outdated preview is made again by the run, never trusted
    assert finding(rep, "preview.evidence_current") is None and pv.load(pd, ASPECT)["composition_sha"] != "old" and rep["preview"]["technical_checks_passed"] is True


@pytest.mark.real_remotion_still
def test_a_still_that_fails_once_is_tried_again_and_one_that_always_fails_stops_the_preview(pd, monkeypatch, tmp_path):
    calls = []

    class R:
        def __init__(self, ok):
            self.returncode, self.stdout, self.stderr = (0 if ok else 1), "", "Failed to fetch"

    def flaky(cmd, **kw):
        calls.append(1)
        if len(calls) >= 3:
            (tmp_path / "x.png").write_bytes(b"png")
        return R(len(calls) >= 3)

    monkeypatch.setattr(pv.subprocess, "run", flaky)
    monkeypatch.setattr(pv.time, "sleep", lambda s: None)                     # the backoff between tries is not waited for in a test
    pv._still(tmp_path, pd / "composition.json", 5, tmp_path / "x.png")
    assert len(calls) == 3
    monkeypatch.setattr(pv.subprocess, "run", lambda cmd, **kw: R(False))
    with pytest.raises(mv.ValidationError, match=f"after {pv.ATTEMPTS} tries"):
        pv._still(tmp_path, pd / "composition.json", 5, tmp_path / "y.png")


def test_a_preview_is_refused_without_a_current_motion_generation_and_a_review_without_a_preview(pd):
    assert pv.load(pd, ASPECT) is None
    with pytest.raises(mv.ValidationError):
        pv.review(pd, ASPECT, "stills", "Asha")
    (pd / "motion_generation.json").unlink()
    with pytest.raises(mv.ValidationError):
        pv.generate(pd, ASPECT)


# ---------- the gate and the API ----------
def api_project(c):
    pid = _mo.make(c, False)
    pdir = _mo.with_plan(pid)
    assert c.post(f"/projects/{pid}/motion/run").status_code == 202
    assert _mo.wait_job(c, pid, timeout=240)["error"] is None
    return pid, pdir


def accept_all(c, pid, rep):
    """Test helper only: no route lets a person accept a finding any more; the ledger function is called directly (it has no production caller)."""
    from backend import pipeline_view, store
    pdir = store.project_dir(pid)
    for f in [f for f in rep["findings"] if f["exceptionable"] and f["status"] == "unresolved"]:
        mv.record_exception(pdir, pipeline_view.aspect_of(pdir), f["finding_id"], "Asha", REASON, rep["source_fingerprint"])


def test_the_api_reports_and_runs_and_never_starts_a_build_and_has_no_route_to_accept_a_finding(client):
    c = client
    pid, pdir = api_project(c)
    r = c.get(f"/projects/{pid}/motion-timeline-validation")
    assert r.status_code == 200 and r.json()["phase_status"] == "completed"                                  # /motion/run = Motion Planning -> Generation -> Validation
    ids = [s["id"] for s in c.get(f"/projects/{pid}/pipeline").json()["stages"]]
    assert ids[ids.index("motion_gen") + 1] == "motion_validation" and ids[ids.index("motion_validation") + 1] == "timeline"
    r = c.post(f"/projects/{pid}/motion-timeline-validation/run")
    assert r.status_code == 202 and r.json()["steps"] == ["motion-validation"]
    assert _mo.wait_job(c, pid, timeout=240)["error"] is None
    rep = c.get(f"/projects/{pid}/motion-timeline-validation").json()
    assert rep["phase_status"] == "completed" and rep["stale"] is False and len(rep["stages"]) == 12 and rep["readiness"] in ("ready", "needs_review", "ready_with_warnings", "blocked")
    assert not (pdir / "out.mp4").exists() and _mo.stages(c, pid)["timeline"]["status"] == "queued"            # validation never builds the timeline or renders
    assert _mo.stages(c, pid)["motion_validation"]["status"] == {"ready": "completed", "needs_review": "waiting_for_approval", "ready_with_warnings": "completed", "blocked": "failed"}[rep["readiness"]]
    for f in rep["findings"][:1]:                                                                              # no route lets a person accept a finding or say they looked at the preview
        assert c.post(f"/projects/{pid}/motion-timeline-validation/findings/{f['finding_id']}/exception", json={"decision_by": "Asha", "reason": REASON, "applies_to_fingerprint": rep["source_fingerprint"]}).status_code in (404, 405)
    assert c.post(f"/projects/{pid}/motion-timeline-validation/preview/review", json={"level": "stills", "by": "Asha"}).status_code in (404, 405)
    assert c.get(f"/projects/{pid}/motion-timeline-validation/preview/nothing.png").status_code == 404
    assert c.get(f"/projects/{pid}/motion-timeline-validation/preview/..%2Fproject.json").status_code in (404, 422)
    assert c.get("/projects/no-such-project/motion-timeline-validation").status_code == 404


def test_the_timeline_waits_for_stage_10_and_a_stale_result_never_lets_the_render_through(client, monkeypatch):
    c = client
    pid, pdir = api_project(c)
    from backend import timeline_gate
    assert c.post(f"/projects/{pid}/motion-timeline-validation/run").status_code == 202
    assert _mo.wait_job(c, pid, timeout=240)["error"] is None
    accept_all(c, pid, c.get(f"/projects/{pid}/motion-timeline-validation").json())
    if c.get(f"/projects/{pid}/motion-timeline-validation").json()["readiness"] not in mv.READY:
        pytest.skip("this fixture has an error or blocker that cannot be accepted: covered by the other tests")
    assert not any("Motion & Timeline Validation" in b for b in timeline_gate.render_blockers(pdir, ASPECT))
    monkeypatch.setattr(mv, "RULE_SET", "9.9")                                                                  # what Stage 10 was made from changes (here its rule set; upstream is untouched): the green result is out of date at once
    assert any("Motion & Timeline Validation is out of date" in b for b in timeline_gate.render_blockers(pdir, ASPECT))
    touch_composition(pdir)
    assert timeline_gate.render_blockers(pdir, ASPECT)                                                           # and a changed composition stops it as well (Motion Generation is out of date too)
