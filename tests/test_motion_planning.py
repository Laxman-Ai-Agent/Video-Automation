"""Motion Planning (backend/motion_planning.py + motion_scenes.py + the motion-plan step): the checked plan motion_planning.json, its 13 stages, the rules and the repairs, the registry,
the frame rule, determinism, the Visual Plan being followed, the API. The motion library is the real one (registry and planner); there is no network and no Claude call.
Run: python -m pytest tests/test_motion_planning.py -q"""
import importlib
import json

import pytest

from backend import motion_planning as mpl
from backend import motion_scenes as ms
from backend import pipeline
from backend import visual_planning as vp
from backend.transition_audit import KNOWN

_v = importlib.import_module("test_visual_planning")
_m7 = importlib.import_module("test_m7")
project, raw_for = _v.project, _v.raw_for
client, create = _m7.client, _m7.create
TRANS = sorted(KNOWN)


def make(tmp_path, images=False, with_vp=True, mutate=None):
    """A project with a Visual Plan (derived from its scene plan) and a motion plan shaped like the planner's, one for every scene; `mutate(mp)` breaks one rule."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    d, sp, pm = project(tmp_path, images=images)
    plan = None
    if with_vp:
        plan, problems = vp.assemble(d, sp, pm, raw_for(sp, pm, images=images))
        assert problems == []
        vp.save(d, plan)
    scenes = []
    for i, s in enumerate(sp["scenes"]):
        texts = [e["content"] for e in (plan["scenes"][i]["elements"] if plan else []) if e.get("content")] or [f"Scene {s['id']}"]
        a, b = s["start"], s["end"]
        scenes.append({
            "id": s["id"], "start": a, "end": b, "pattern": s["pattern"], "pictures": 0,
            "texts": [{"text": t, "style": "headline", "preset": "cinematic-fade", "exit": "fade-out", "emphasis": "pulse", "enter_s": 0.5, "at": round(a + 0.2, 2), "until": None, "exit_s": 0.36,
                       "emphasis_at": [round(a + 0.5, 2)], "source": "visual_plan" if plan else "scene_plan", "dir": "left", "k": 1.0} for t in texts[:1]],
            "graphics": [{"preset": "floating-dots", "atmosphere": True, "speed": 1.4, "start": a, "end": None, "exit_s": 0.36, "box": [0, 0, 1, 1], "why": "atmosphere"},
                         {"preset": "route-line", "atmosphere": False, "speed": 1.4, "start": round(a + 0.3, 2), "end": None, "exit_s": 0.36, "box": [0.1, 0.12, 0.3, 0.2], "why": "topic"}],
            "transition": None if i == len(sp["scenes"]) - 1 else {"type": TRANS[i % len(TRANS)], "dur": 0.43}, "icons": [], "classic_texts": [], "other_layers": [],
            "why": {"texts": "visual_plan" if plan else "scene_plan", "decor": {}, "intents": [], "mood": "", "importance": 0.6}})
    mp = {"version": 1, "aspect": "16:9", "mode": "with-pictures" if images else "motion-only", "speed": 1.4, "fps": 30, "scenes": scenes}
    if mutate:
        mutate(mp)
    (d / "motion_plan.json").write_text(json.dumps(mp), encoding="utf-8")
    return d, sp, pm, plan, mp


def build(d):
    return mpl.build(d, "16:9", run_tests=False)


def codes(plan):
    return {n["code"] for s in plan["scenes"] for n in s["validation_notes"]}


# ---------- the plan, the 13 stages, the frame rule ----------
def test_a_valid_plan_has_the_13_stages_no_errors_and_follows_one_frame_rule(tmp_path):
    d, *_ = make(tmp_path)
    plan = build(d)
    assert [s["name"] for s in plan["stages"]] == ["Motion Plan Reader", "Element Resolver", "Preset Registry Lookup", "Effect Reuse Engine", "Animation Builder", "Animation Engine Adapter",
                                                  "Composition & Transition Builder", "Timing & Audio Sync", "Layout Validator", "Code & Plan Validator", "Motion Test Runner", "Error Repair Handler",
                                                  "Remotion Output Adapter"]
    assert [s["n"] for s in plan["stages"]] == list(range(1, 14)) and plan["validation"]["errors"] == []
    assert next(s for s in plan["stages"] if s["n"] == 11)["status"] == "warning"                       # not run here: said, not claimed
    assert mpl.fr(1.0166) == 30 and mpl.fr(1.0167) == 31 and mpl.fr(0.0166) == 0 and mpl.fr(0.5) == 15 and mpl.fr(2.0) == 60      # floor(seconds x 30 + 0.5): 30.5 frames rounds up, like Math.round
    for s in plan["scenes"]:
        assert s["timing"]["start_frame"] == mpl.fr(s["timing"]["start"]) and s["timing"]["end_frame"] > s["timing"]["start_frame"]
        for a in s["sequence"]:
            assert a["start_frame"] == mpl.fr(a["start"]) and a["end_frame"] > a["start_frame"]            # the end is after the start, in frames too
            assert s["timing"]["start"] - 0.05 <= a["start"] and a["end"] <= s["timing"]["end"] + 0.05      # nothing outside its scene
            assert a["registry"] is None or a["registry"]["id"] == a["preset"]                           # every preset that is named was found in the registry
    mpl.PlanM.model_validate(plan)                                                                     # the contract


def test_the_scene_ids_are_those_of_the_visual_plan_and_every_visual_element_is_in_the_plan(tmp_path):
    d, sp, pm, vplan, _ = make(tmp_path)
    plan = build(d)
    assert [s["scene_id"] for s in plan["scenes"]] == [s["scene_id"] for s in vplan["scenes"]]
    for s, v in zip(plan["scenes"], vplan["scenes"]):
        assert {e["element_id"] for e in v["elements"]} <= {e["element_id"] for e in s["elements"]}
        assert all(e["status"] in ("resolved", "fallback", "unresolved") for e in s["elements"])
    assert plan["visual_plan"]["fingerprint"] == vplan["source_fingerprint"]


def test_the_same_inputs_give_the_same_plan(tmp_path):
    d, *_ = make(tmp_path)
    a, b = build(d), build(d)
    a.pop("timings_seconds"), b.pop("timings_seconds")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_actions_have_dependencies_in_the_order_establish_reveal_enter_emphasis_exit(tmp_path):
    d, *_ = make(tmp_path)
    s = build(d)["scenes"][0]
    phases = [a["phase"] for a in s["sequence"]]
    assert phases == sorted(phases, key=lambda p: mpl.PHASE_RANK[p]) and phases[0] == "establish"
    by = {a["action_id"]: a for a in s["sequence"]}
    assert all(d_ in by for a in s["sequence"] for d_ in a["depends_on"]) and ms.acyclic(s["sequence"])
    enter = next(a for a in s["sequence"] if a["phase"] == "enter")
    assert next(a for a in s["sequence"] if a["phase"] == "exit")["depends_on"] == [enter["action_id"]]


def test_a_dependency_cycle_is_detected():
    assert ms.acyclic([{"action_id": "a", "depends_on": []}, {"action_id": "b", "depends_on": ["a"]}]) is True
    assert ms.acyclic([{"action_id": "a", "depends_on": ["b"]}, {"action_id": "b", "depends_on": ["a"]}]) is False


# ---------- registry, parameters, mode ----------
def test_an_id_that_is_not_in_the_registry_blocks_the_plan_and_is_never_executed(tmp_path):
    d, *_ = make(tmp_path, mutate=lambda mp: mp["scenes"][0]["graphics"][0].update(preset="no-such-graphic"))
    plan = build(d)
    assert any("no-such-graphic" in e for e in plan["validation"]["errors"]) and "unknown_registry_id" in codes(plan)
    assert next(s for s in plan["stages"] if s["n"] == 3)["status"] == "failed" and next(s for s in plan["stages"] if s["n"] == 12)["status"] == "failed"
    assert plan["reuse"]["new_presets_added"] == 0 and plan["reuse"]["ids_not_in_registry"] >= 1


def test_an_unknown_text_preset_is_repaired_to_a_calm_one_and_the_repair_is_recorded(tmp_path):
    d, *_ = make(tmp_path, mutate=lambda mp: mp["scenes"][0]["texts"][0].update(preset="no-such-text"))
    plan = build(d)
    rep = [r for r in plan["repairs"] if r["field"] == "preset"]
    assert rep and rep[0]["from"] == "no-such-text" and rep[0]["to"] == "cinematic-fade" and plan["validation"]["errors"] == []
    assert next(s for s in plan["stages"] if s["n"] == 12)["status"] == "warning"
    assert next(a for a in plan["scenes"][0]["sequence"] if a["phase"] == "enter")["preset"] == "cinematic-fade"


def test_a_time_outside_the_scene_is_clamped_and_recorded(tmp_path):
    d, sp, *_ = make(tmp_path, mutate=lambda mp: mp["scenes"][0]["graphics"][0].update(start=mp["scenes"][0]["start"] - 2))
    plan = build(d)
    assert any(r["field"] == "start" and "clamped" in r["reason"] for r in plan["repairs"]) and plan["validation"]["errors"] == []
    assert min(a["start"] for a in plan["scenes"][0]["sequence"]) >= plan["scenes"][0]["timing"]["start"]


def test_telugu_text_needs_a_preset_that_can_draw_it(tmp_path):
    reg = mpl.registry()
    bad = next(k for k, v in reg["text"].items() if not v.get("indic"))
    d, *_ = make(tmp_path, mutate=lambda mp: mp["scenes"][0]["texts"][0].update(text="నమస్తే", preset=bad))
    plan = build(d)
    assert any("cannot draw Telugu" in e for e in plan["validation"]["errors"]) and next(s for s in plan["stages"] if s["n"] == 6)["status"] == "failed"


def test_motion_only_has_no_pictures_and_the_mode_must_match_the_project(tmp_path):
    d, *_ = make(tmp_path, mutate=lambda mp: mp["scenes"][0].update(pictures=1))
    assert any("has a picture" in e for e in build(d)["validation"]["errors"])
    d2, *_ = make(tmp_path / "b", mutate=lambda mp: mp.update(mode="with-pictures"))
    assert any("Use Images is OFF" in e for e in build(d2)["validation"]["errors"])


def test_a_transition_may_not_repeat_the_previous_one_or_be_longer_than_the_scenes_allow(tmp_path):
    def repeat(mp):
        mp["scenes"][1]["transition"]["type"] = mp["scenes"][0]["transition"]["type"]
    assert any("repeats the previous" in e for e in build(make(tmp_path, mutate=repeat)[0])["validation"]["errors"])
    assert any("must be 0.25-" in e for e in build(make(tmp_path / "b", mutate=lambda mp: mp["scenes"][0]["transition"].update(dur=50))[0])["validation"]["errors"])
    assert any("is not in the transition library" in e for e in build(make(tmp_path / "c", mutate=lambda mp: mp["scenes"][0]["transition"].update(type="spin-of-doom"))[0])["validation"]["errors"])


def test_a_scene_must_have_something_that_moves_but_a_picture_scene_is_moved_by_its_camera(tmp_path):
    def bare(mp):
        mp["scenes"][0].update(texts=[], graphics=[])
    plan = build(make(tmp_path, mutate=bare)[0])
    assert any("nothing that moves" in e for e in plan["validation"]["errors"])
    d, *_ = make(tmp_path / "b", images=True, mutate=lambda mp: mp["scenes"][0].update(texts=[], graphics=[], pictures=1))
    assert not any("nothing that moves" in e for e in build(d)["validation"]["errors"])


def test_code_in_the_plan_is_refused(tmp_path):
    d, *_ = make(tmp_path, mutate=lambda mp: mp["scenes"][0]["graphics"][0].update(why="function(x) => x"))
    assert any("code-like" in e for e in build(d)["validation"]["errors"])


# ---------- the Visual Plan is followed, not invented ----------
def test_a_required_on_screen_text_of_the_visual_plan_may_not_be_missing_from_the_motion_plan(tmp_path):
    d, sp, pm, vplan, _ = make(tmp_path)
    s0 = next(s for s in vplan["scenes"] if any(e["type"] in ("text", "label") and e.get("content") for e in s["elements"]))
    gone = next(e for e in s0["elements"] if e["type"] in ("text", "label") and e.get("content"))["content"]
    mp = json.loads((d / "motion_plan.json").read_text(encoding="utf-8"))
    for sc in mp["scenes"]:
        sc["texts"] = [t for t in sc["texts"] if t["text"] != gone]
    (d / "motion_plan.json").write_text(json.dumps(mp), encoding="utf-8")
    plan = build(d)
    assert any(f"'{gone}'" in e and "not in the motion plan" in e for e in plan["validation"]["errors"])


def test_an_element_the_library_cannot_draw_on_its_own_is_a_recorded_fallback_not_an_invented_id(tmp_path):
    d, sp, pm, vplan, _ = make(tmp_path)
    stored = json.loads((d / "visual_planning.json").read_text(encoding="utf-8"))
    stored["scenes"][0]["elements"].append({"element_id": "node_x", "type": "diagram", "role": "supporting", "required": True, "visual_description": "a network", "content": None, "language": None,
                                            "text_purpose": None, "appearance": {}, "placement": {"region": "center", "priority": 2, "avoid_overlap": True}, "registry_requirements": None, "constraints": []})
    (d / "visual_planning.json").write_text(json.dumps(stored), encoding="utf-8")
    plan = build(d)
    el = next(e for e in plan["scenes"][0]["elements"] if e["element_id"] == "node_x")
    assert el["status"] == "fallback" and el["registry_id"] is None and el["fallback"]["id"] == "route-line"
    assert plan["validation"]["errors"] == [] and any("not drawn one by one" in w for w in plan["validation"]["warnings"])


def test_a_project_without_a_visual_plan_still_plans_and_says_the_elements_cannot_be_traced(tmp_path):
    d, *_ = make(tmp_path, with_vp=False)
    plan = build(d)
    assert plan["visual_plan"]["file"] is None and plan["validation"]["errors"] == [] and any("no Visual Plan" in w for w in plan["validation"]["warnings"])
    assert len(plan["scenes"]) and all(s["elements"] for s in plan["scenes"])


def test_the_plan_is_stale_when_its_inputs_change_and_a_blocking_error_stops_generation(tmp_path):
    d, *_ = make(tmp_path)
    mpl.save(d, "16:9", build(d))
    assert mpl.load(d, "16:9")["stale"] is False and mpl.blockers(d, "16:9") is None
    mp = json.loads((d / "motion_plan.json").read_text(encoding="utf-8"))
    mp["speed"] = 1.1
    (d / "motion_plan.json").write_text(json.dumps(mp), encoding="utf-8")
    assert mpl.load(d, "16:9")["stale"] is True and "out of date" in mpl.blockers(d, "16:9")


# ---------- the step (the real planner), the API ----------
def test_the_motion_plan_step_follows_the_visual_plan_text_writes_the_checked_plan_and_resumes(tmp_path):
    d, sp, pm, vplan, _ = make(tmp_path)
    (d / "motion_plan.json").unlink()
    r = pipeline.execute(d, "motion-plan", pipeline.Ctx())
    assert r["status"] == "ran", r
    plan = mpl.load(d, "16:9")
    assert plan and plan["stale"] is False and plan["validation"]["errors"] == [] and plan["visual_plan"]["text_and_hints_used"] is True
    planned = {a["params"]["text"] for s in plan["scenes"] for a in s["sequence"] if a["phase"] == "enter" and a["params"].get("text")}
    wanted = {e["content"].strip() for s in vplan["scenes"] for e in s["elements"] if e["type"] in ("text", "label") and e.get("content")}
    assert wanted and wanted <= planned                                                                 # the words of the Visual Plan, not the scene plan's
    assert pipeline.execute(d, "motion-plan", pipeline.Ctx())["status"] == "fresh"                         # unchanged inputs: nothing runs again


def test_the_motion_planning_api_reads_without_starting_anything_and_refuses_a_project_without_a_plan(client):
    pid = create(client).json()["id"]
    r = client.get(f"/projects/{pid}/motion-planning")
    assert r.status_code == 409 and r.json()["error"]["code"] == "motion_plan_missing"
    r = client.post(f"/projects/{pid}/motion-planning/run")
    assert r.status_code == 409 and r.json()["error"]["code"] == "plan_missing"


# ---------- Solve warnings ----------
def _fixable(tmp_path):
    """Scene 1: a graphic on the planned text area, a text that starts too late to be read, a required element the library cannot draw. (The other scenes of this fixture have warnings of their own.)"""
    d, sp, pm, vplan, mp = make(tmp_path)
    stored = json.loads((d / "visual_planning.json").read_text(encoding="utf-8"))
    el = next(e for e in stored["scenes"][0]["elements"] if e["type"] in ("text", "label"))
    el["placement"]["region"] = "upper_right"
    stored["scenes"][0]["elements"].append({"element_id": "node_x", "type": "diagram", "role": "supporting", "required": True, "visual_description": "a network", "content": None, "language": None,
                                            "text_purpose": None, "appearance": {}, "placement": {"region": "center", "priority": 2, "avoid_overlap": True}, "registry_requirements": None, "constraints": []})
    (d / "visual_planning.json").write_text(json.dumps(stored), encoding="utf-8")
    s0 = mp["scenes"][0]
    assert s0["end"] - s0["start"] >= 3
    s0["graphics"][1]["box"] = [0.66, 0.23, 0.2, 0.1]
    s0["texts"][0]["at"] = round(s0["end"] - 1.0, 2)
    s0["texts"][0]["emphasis_at"] = [round(s0["end"] - 0.7, 2)]
    (d / "motion_plan.json").write_text(json.dumps(mp), encoding="utf-8")
    mpl.save(d, "16:9", build(d))
    return d, mp


def _own(warnings, scene="scene_01"):
    return [w for w in warnings if w.startswith(scene) and ("overlaps the area" in w or "needs about" in w or "not drawn one by one" in w)]


def _apply(d, mp):
    """What build_composition.ts --fixes does to the plan."""
    fx = json.loads((d / "motion_fixes.json").read_text(encoding="utf-8"))["scenes"]
    for s in mp["scenes"]:
        f = fx.get(str(s["id"]), {})
        for g in s["graphics"]:
            g["box"] = (f.get("box") or {}).get(g["preset"], g["box"])
        for i, t in enumerate(s["texts"]):
            t["at"] = (f.get("textAt") or {}).get(str(i), t["at"])
    (d / "motion_plan.json").write_text(json.dumps(mp), encoding="utf-8")


def test_solve_moves_the_graphic_off_the_text_area_starts_the_short_text_earlier_and_accepts_the_fallback(tmp_path):
    d, mp = _fixable(tmp_path)
    before = mpl.load(d, "16:9")["validation"]["warnings"]
    assert len(_own(before)) == 3
    done = mpl.solve(d, "16:9")
    assert done["moved"] >= 1 and done["earlier"] == 1 and done["accepted"] >= 1 and done["before"] == len(before)
    fx = json.loads((d / "motion_fixes.json").read_text(encoding="utf-8"))
    box = fx["scenes"]["1"]["box"]["route-line"]
    assert vp._overlap((box[0], box[1], box[0] + box[2], box[1] + box[3]), vp.region_box("upper_right")) == 0 and box[2:] == [0.2, 0.1]            # same size, clear of the text area
    s0 = mp["scenes"][0]
    at = fx["scenes"]["1"]["textAt"]["0"]
    assert at < s0["texts"][0]["at"] and at >= s0["start"] and (s0["end"] - 0.36) - at >= 0.5 + 0.8 + 0.3 * len(s0["texts"][0]["text"].split())      # on screen until its EXIT starts, not until the scene ends
    assert "scene_01" in fx["accepted"] and fx["before"] == len(before)


def test_solve_is_recorded_in_the_plan_and_what_cannot_be_solved_stays_a_warning(tmp_path):
    d, mp = _fixable(tmp_path)
    mpl.solve(d, "16:9")
    _apply(d, mp)
    plan = build(d)
    warnings = plan["validation"]["warnings"]
    assert plan["validation"]["errors"] == [] and _own(warnings) == [] and not any("overlaps the area" in w for w in warnings)
    assert any("is not an element of the Visual Plan" in w for w in warnings) and any("repeats the previous" in w for w in warnings)         # not solvable by this button: still said
    wf = plan["warning_fix"]
    assert wf["status"] == "partly" and wf["after"] == len(warnings) < wf["before"] and "scene_01" in wf["accepted"] and {c["kind"] for c in wf["changes"]} == {"graphic_moved", "text_earlier"}
    note = next(n for n in plan["scenes"][0]["validation_notes"] if n["code"] == "element_fallback")
    assert note["severity"] == "info" and note["message"].endswith("still NOT drawn") and wf["not_drawn"] >= 2                       # kept in the scene, no longer a warning
    mpl.save(d, "16:9", plan)
    stored = (d / "motion_fixes.json").read_text(encoding="utf-8")
    assert mpl.solve(d, "16:9") == {"moved": 0, "earlier": 0, "accepted": 0, "kept": [], "before": len(warnings)} and (d / "motion_fixes.json").read_text(encoding="utf-8") == stored      # nothing left it can solve


def test_solve_needs_a_current_plan_and_the_api_refuses_a_project_without_one(client, tmp_path):
    d, _ = _fixable(tmp_path)
    mp = json.loads((d / "motion_plan.json").read_text(encoding="utf-8"))
    mp["speed"] = 1.1
    (d / "motion_plan.json").write_text(json.dumps(mp), encoding="utf-8")
    with pytest.raises(mpl.MotionError, match="out of date"):
        mpl.solve(d, "16:9")
    pid = create(client).json()["id"]
    r = client.post(f"/projects/{pid}/motion-planning/fix-warnings")
    assert r.status_code == 409 and r.json()["error"]["code"] == "motion_plan_missing"


def test_solve_never_moves_a_graphic_onto_the_text_the_renderer_really_draws(tmp_path):
    d, mp = _fixable(tmp_path)
    mp["scenes"][0]["texts"][0]["drawn_box"] = [0.1, 0.38, 0.9, 0.53]                   # where the renderer draws the headline (build_composition.ts: same rules as MotionTextLayer)
    mp["scenes"][0]["graphics"][1]["box"] = [0.3, 0.4, 0.2, 0.1]                         # on that text, but NOT on the area the Visual Plan planned for it
    (d / "motion_plan.json").write_text(json.dumps(mp), encoding="utf-8")
    mpl.save(d, "16:9", build(d))
    assert any("where the renderer draws it" in w for w in mpl.load(d, "16:9")["validation"]["warnings"])
    mpl.solve(d, "16:9")
    box = json.loads((d / "motion_fixes.json").read_text(encoding="utf-8"))["scenes"]["1"]["box"]["route-line"]
    assert vp._overlap((box[0], box[1], box[0] + box[2], box[1] + box[3]), (0.1, 0.38, 0.9, 0.53)) == 0                # the plan's text area is not the only text to keep clear
    assert vp._overlap((box[0], box[1], box[0] + box[2], box[1] + box[3]), vp.region_box("upper_right")) == 0


def test_without_a_free_place_the_warning_stays_and_nothing_is_forced(tmp_path):
    d, mp = _fixable(tmp_path)
    mp["scenes"][0]["texts"][0]["drawn_box"] = [0.0, 0.0, 1.0, 1.0]                      # a text over the whole frame: no place is clear of it
    mp["scenes"][0]["graphics"][1]["box"] = [0.3, 0.4, 0.2, 0.1]
    (d / "motion_plan.json").write_text(json.dumps(mp), encoding="utf-8")
    mpl.save(d, "16:9", build(d))
    done = mpl.solve(d, "16:9")
    assert any("no place for 'route-line'" in k for k in done["kept"])
    fx = json.loads((d / "motion_fixes.json").read_text(encoding="utf-8"))
    assert "box" not in fx["scenes"].get("1", {})                                       # not moved: the warning stays for review
    _apply(d, mp)
    assert any("where the renderer draws it" in w for w in build(d)["validation"]["warnings"])


def test_a_text_that_cannot_fit_between_the_scene_start_and_its_exit_is_reported_not_forced(tmp_path):
    d, mp = _fixable(tmp_path)
    s0 = mp["scenes"][0]
    s0["texts"][0]["text"] = "one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen"       # needs far more time than the scene has
    s0["texts"][0]["at"] = round(s0["end"] - 1.0, 2)
    (d / "motion_plan.json").write_text(json.dumps(mp), encoding="utf-8")
    mpl.save(d, "16:9", build(d))
    done = mpl.solve(d, "16:9")
    assert done["earlier"] == 0 and any("shorten the text or lengthen the scene" in k for k in done["kept"])


def test_solving_again_keeps_what_was_decided_before_and_a_hand_edit_of_the_fixes_file(tmp_path):
    d, mp = _fixable(tmp_path)
    mpl.solve(d, "16:9")
    f = json.loads((d / "motion_fixes.json").read_text(encoding="utf-8"))
    f["scenes"]["3"] = {"box": {"route-line": [0.4, 0.7, 0.3, 0.2]}}                       # a decision the user wrote by hand
    f["changes"].append({"scene": "scene_03", "kind": "graphic_moved", "preset": "route-line", "why": "by hand"})
    (d / "motion_fixes.json").write_text(json.dumps(f), encoding="utf-8")
    _apply(d, mp)
    mpl.save(d, "16:9", build(d))
    mpl.solve(d, "16:9")
    g = json.loads((d / "motion_fixes.json").read_text(encoding="utf-8"))
    assert g["scenes"]["3"] == {"box": {"route-line": [0.4, 0.7, 0.3, 0.2]}} and g["scenes"]["1"] == f["scenes"]["1"] and any(c["why"] == "by hand" for c in g["changes"]) and g["before"] == f["before"]


def test_motion_generation_refuses_a_checked_plan_that_is_out_of_date_or_has_errors(tmp_path):
    d, sp, pm, vplan, _ = make(tmp_path)
    (d / "motion_plan.json").unlink()
    assert pipeline.execute(d, "motion-plan", pipeline.Ctx())["status"] == "ran"
    plan = mpl.load(d, "16:9")
    plan["validation"]["errors"] = ["scene_01: a blocking error"]                                   # as written by a plan with an error
    mpl.save(d, "16:9", plan)
    with pytest.raises(pipeline.StepError, match="blocking error"):
        pipeline.execute(d, "motion-build", pipeline.Ctx())
    mp = json.loads((d / "motion_plan.json").read_text(encoding="utf-8"))
    mp["speed"] = 1.1                                                                               # the selector's plan changed after it was checked
    (d / "motion_plan.json").write_text(json.dumps(mp), encoding="utf-8")
    plan["validation"]["errors"] = []
    mpl.save(d, "16:9", plan)
    with pytest.raises(pipeline.StepError, match="out of date"):
        pipeline.execute(d, "motion-build", pipeline.Ctx())


# ---------- the elements the diagram builder draws (VIDEO_ENGINE/remotion/src/motion/diagram.ts) ----------
def _with_diagram(tmp_path, placed, skipped=(), el_desc="A flat teal disc representing Earth", el_type="graphic", drawn_box=None):
    d, sp, pm, vplan, mp = make(tmp_path)
    stored = json.loads((d / "visual_planning.json").read_text(encoding="utf-8"))
    stored["scenes"][0]["elements"].append({"element_id": "earth_x", "type": el_type, "role": "supporting", "required": True, "visual_description": el_desc, "content": None, "language": None,
                                            "text_purpose": None, "appearance": {}, "placement": {"region": "left", "priority": 2, "avoid_overlap": True}, "registry_requirements": None, "constraints": []})
    (d / "visual_planning.json").write_text(json.dumps(stored), encoding="utf-8")
    for q in placed:
        q["at"] = round(mp["scenes"][0]["start"] + 0.4, 2)                                          # inside the scene
    mp["scenes"][0]["diagram"] = {"placed": placed, "skipped": list(skipped), "moved": [], "replaced": []}
    if drawn_box:
        mp["scenes"][0]["texts"][0]["drawn_box"] = drawn_box
    (d / "motion_plan.json").write_text(json.dumps(mp), encoding="utf-8")
    return d, build(d)


def _disc(box=(0.1, 0.7, 0.07, 0.12), pid="shape:circle", eid="earth_x", status="resolved"):
    return {"element_id": eid, "kind": "disc", "layer": "shape", "id": pid, "box": list(box), "at": 10.4, "status": status, "note": "plain flat disc"}


def test_a_drawn_element_is_resolved_with_a_primitive_id_and_has_its_own_action(tmp_path):
    d, plan = _with_diagram(tmp_path, [_disc()])
    el = next(e for e in plan["scenes"][0]["elements"] if e["element_id"] == "earth_x")
    assert el["status"] == "resolved" and el["registry_id"] == "shape:circle" and el["registry_kind"] == "primitive"
    act = next(a for a in plan["scenes"][0]["sequence"] if a["target"] == "earth_x")
    assert act["preset"] == "shape:circle" and act["registry"]["kind"] == "primitive" and act["start"] < act["end"]
    assert plan["validation"]["errors"] == [] and not any("earth_x" in w for w in plan["validation"]["warnings"])


def test_a_stand_in_is_approximate_and_said_so_and_an_unknown_primitive_blocks_the_plan(tmp_path):
    d, plan = _with_diagram(tmp_path / "a", [{**_disc(pid="icon:users", status="approximate"), "kind": "icon", "layer": "icon", "note": "a generic people icon"}], el_desc="One group of astronaut silhouettes")
    el = next(e for e in plan["scenes"][0]["elements"] if e["element_id"] == "earth_x")
    assert el["status"] == "approximate" and any(n["code"] == "element_approximate" and n["severity"] == "info" for n in plan["scenes"][0]["validation_notes"])
    d, plan = _with_diagram(tmp_path / "b", [_disc(pid="shape:hexagon")])
    assert any("shape:hexagon" in e for e in plan["validation"]["errors"])


def test_a_drawn_element_must_exist_in_the_visual_plan_stay_off_the_text_and_inside_the_safe_area(tmp_path):
    d, plan = _with_diagram(tmp_path / "a", [_disc(eid="invented_planet")])
    assert any("invented_planet" in e and "not an element of the Visual Plan" in e for e in plan["validation"]["errors"])
    d, plan = _with_diagram(tmp_path / "b", [_disc(box=(0.3, 0.4, 0.07, 0.12))], drawn_box=[0.09, 0.38, 0.91, 0.53])
    assert any("lies on the text" in w and "earth_x" in w for w in plan["validation"]["warnings"])
    d, plan = _with_diagram(tmp_path / "c", [_disc(box=(0.01, 0.7, 0.07, 0.12))])
    assert any("reaches outside the safe area" in w for w in plan["validation"]["warnings"])


def test_an_element_the_diagram_builder_refused_stays_a_recorded_fallback_with_its_reason(tmp_path):
    d, plan = _with_diagram(tmp_path, [], skipped=[{"element_id": "earth_x", "reason": "no dome primitive: the library draws discs, lines, frames and icons only"}])
    el = next(e for e in plan["scenes"][0]["elements"] if e["element_id"] == "earth_x")
    assert el["status"] == "fallback" and "no dome primitive" in el["fallback"]["reason"]
    assert any("not drawn one by one" in w and "no dome primitive" in w for w in plan["validation"]["warnings"])


def test_the_region_table_of_the_diagram_builder_is_the_one_of_the_visual_plan():
    import subprocess
    r = subprocess.run("npx tsx scripts/motion_list.ts", cwd=pipeline._REMOTION, shell=True, capture_output=True, text=True, encoding="utf-8", timeout=120)
    ts = json.loads(next(x for x in r.stdout.splitlines() if x.startswith("{")))["region_boxes"]
    assert {k: (list(v) if v else None) for k, v in vp.REGION_BOX.items()} == ts
    ids = {p["id"] for p in json.loads(next(x for x in r.stdout.splitlines() if x.startswith("{")))["primitives"]}
    from backend import resource_library as rl
    assert {i for i in ids if not i.startswith("resource:")} == {"shape:circle", "shape:dome", "icon:rocket", "icon:users", "icon:book-open"}
    assert {i for i in ids if i.startswith("resource:")} == {"resource:" + c["id"] for c in rl.icon_candidates()}      # the verified registry icons, nothing else


def test_the_automatic_solve_loop_stops_after_three_attempts_counted_on_disk(tmp_path):
    from backend import motion_autofix as af
    d, _ = _fixable(tmp_path)
    done = {"moved": 1, "earlier": 0, "accepted": 0, "kept": []}
    for i in range(af.MAX_AUTO_FIXES):
        assert len(af.count(d, done)["attempts"]) == i + 1
    assert len(af.state(d)["attempts"]) == af.MAX_AUTO_FIXES                   # a "refresh": the count is read from the file
    with pytest.raises(af.Exhausted):
        af.count(d, done)
    assert len(af.state(d)["attempts"]) == af.MAX_AUTO_FIXES                   # the refused attempt added nothing
    (d / "scene_plan.json").write_text((d / "scene_plan.json").read_text(encoding="utf-8") + " ", encoding="utf-8")
    assert af.state(d)["attempts"] == []                                       # a new scene plan is a new run
