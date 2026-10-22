"""Visual plan (backend/visual_plan.py + routes/visual.py): visual_plan.json is derived from the real analysis, edits touch only the edited fields, regeneration and
approval work on one scene and never on the others. The Claude CLI is a fake. Run: python -m pytest tests/test_m9_visual.py -q"""
import importlib
import json

import pytest

from backend import promptgen, visual_plan

_r = importlib.import_module("test_m9_review")
client, proj = _r.client, _r.proj


@pytest.fixture(autouse=True)
def no_cli(monkeypatch):
    def refuse(user, **kw):
        raise promptgen.GenError("no CLI in tests")
    monkeypatch.setattr(promptgen, "run_claude", refuse)


def plan(c, pid):
    r = c.get(f"/projects/{pid}/visual-plan")
    assert r.status_code == 200, r.text
    return r.json()


def scene_of(c, pid, n=0):
    return plan(c, pid)["plan"]["scenes"][n]


def save(c, pid, sid, revision, *changes):
    return c.put(f"/projects/{pid}/visual-plan/scenes/{sid}", json={"revision": revision, "changes": [{"path": p, "value": v} for p, v in changes]})


def test_the_plan_has_exactly_the_scenes_of_the_analysis_with_their_real_data(proj):
    c, pid, pdir = proj
    analysis = c.get(f"/projects/{pid}/review").json()["analysis"]["scenes"]
    p = plan(c, pid)
    assert [s["number"] for s in p["plan"]["scenes"]] == [a["id"] for a in analysis]
    assert [s["id"] for s in p["plan"]["scenes"]] == [f"scene_{a['id']:02d}" for a in analysis]
    first = p["plan"]["scenes"][0]
    assert (first["start"], first["end"]) == (analysis[0]["start"], analysis[0]["end"]) and first["narration_en"] == analysis[0]["narration_en"]
    assert first["shots"] and first["approval"]["status"] == "approved" and first["approval"]["auto"] is True and first["meta"]["revision"] == 1   # valid = approved by default
    assert (pdir / "visual_plan.json").exists() and p["all_approved"] is all(s["approval"]["status"] == "approved" for s in p["plan"]["scenes"])
    assert set(p["issues"]) == {s["id"] for s in p["plan"]["scenes"]} and "issues" not in first   # findings are sent beside the scenes, not stored in them
    assert first["counts"]["shots"] == len(first["shots"])


def test_assets_use_the_prompt_slots_as_their_ids(proj):
    c, pid, pdir = proj
    slots = {p["slot"] for p in json.loads((pdir / "prompts_map.json").read_text(encoding="utf-8"))["prompts"]}
    ids = {a["id"] for s in plan(c, pid)["plan"]["scenes"] for sh in s["shots"] for a in sh["assets"] if a["type"] == "image"}
    assert ids == slots


def test_reading_twice_changes_nothing_and_a_missing_plan_is_a_clear_error(proj):
    c, pid, pdir = proj
    assert not (pdir / "visual_plan.json").exists()
    plan(c, pid)
    first = (pdir / "visual_plan.json").read_bytes()
    plan(c, pid)
    assert (pdir / "visual_plan.json").read_bytes() == first
    new = _r.create(c).json()["id"]
    r = c.get(f"/projects/{new}/visual-plan")
    assert r.status_code == 409 and r.json()["error"]["code"] == "plan_missing"


def test_saving_changes_only_the_edited_field_and_keeps_every_other_scene(proj):
    c, pid, pdir = proj
    before = plan(c, pid)["plan"]
    s0 = before["scenes"][0]
    r = save(c, pid, s0["id"], s0["meta"]["revision"], (["shots", 0, "camera", "movement"], "Slow orbit"), (["purpose"], "A new purpose"))
    assert r.status_code == 200, r.text
    after = plan(c, pid)["plan"]
    new = after["scenes"][0]
    assert new["shots"][0]["camera"]["movement"] == "Slow orbit" and new["purpose"] == "A new purpose"
    assert new["meta"]["revision"] == 2 and new["meta"]["edited"] is True and new["approval"]["status"] == "approved"   # checked again after the edit: still valid
    assert new["meta"]["edited_paths"] == ["purpose", "shots / 0 / camera / movement"]
    expected = json.loads(json.dumps(s0))
    expected["shots"][0]["camera"]["movement"] = "Slow orbit"
    expected["purpose"] = "A new purpose"
    for k in ("meta", "approval"):
        new.pop(k)
        expected.pop(k)
    assert new == expected                                              # nothing else in the scene changed
    assert after["scenes"][1:] == before["scenes"][1:]                  # other scenes are untouched
    assert json.loads((pdir / "visual_plan.json").read_text(encoding="utf-8"))["scenes"][0]["purpose"] == "A new purpose"


def test_invalid_values_are_refused_and_nothing_is_saved(proj):
    c, pid, pdir = proj
    s0 = scene_of(c, pid)
    rev = s0["meta"]["revision"]
    cases = [(["shots", 0, "start"], 99.0), (["shots", 0, "end"], -1.0), (["shots", 0, "camera", "zoom_from"], "big"), (["narration_en"], "x"), (["id"], "other"), (["shots"], []), (["nope"], 1)]
    for path, value in cases:
        r = save(c, pid, s0["id"], rev, (path, value))
        assert r.status_code in (404, 409, 422), (path, r.text)
    assert scene_of(c, pid) == s0


def test_a_stale_revision_is_refused_so_edits_are_never_overwritten_silently(proj):
    c, pid, _ = proj
    s0 = scene_of(c, pid)
    assert save(c, pid, s0["id"], 1, (["purpose"], "first")).status_code == 200
    r = save(c, pid, s0["id"], 1, (["purpose"], "second"))
    assert r.status_code == 409 and r.json()["error"]["code"] == "scene_changed"
    assert scene_of(c, pid)["purpose"] == "first"


def test_valid_scenes_are_approved_by_default_and_reopen_and_approve_still_work(proj):
    c, pid, pdir = proj
    scenes = plan(c, pid)["plan"]["scenes"]
    assert all(s["approval"]["status"] == "approved" for s in scenes) and visual_plan.approved(pdir, pid) is True
    assert json.loads((pdir / "visual_plan.json").read_text(encoding="utf-8"))["scenes"][0]["approval"]["approved_at"]
    r = c.post(f"/projects/{pid}/visual-plan/scenes/{scenes[0]['id']}/approval", json={"action": "reopen"})
    assert r.json()["scene"]["approval"]["status"] == "in_progress" and r.json()["all_approved"] is False
    assert plan(c, pid)["plan"]["scenes"][0]["approval"]["status"] == "in_progress"      # a reopened scene stays open: it is not approved again behind the user's back
    r = c.post(f"/projects/{pid}/visual-plan/scenes/{scenes[0]['id']}/approval", json={"action": "approve"})
    assert r.status_code == 200 and r.json()["scene"]["approval"]["status"] == "approved" and r.json()["all_approved"] is True
    assert c.post(f"/projects/{pid}/visual-plan/scenes/{scenes[0]['id']}/approval", json={"action": "nope"}).status_code == 422


def test_editing_revalidates_the_scene_and_a_reopened_one_is_approved_again_when_valid(proj):
    c, pid, _ = proj
    s0 = scene_of(c, pid)
    c.post(f"/projects/{pid}/visual-plan/scenes/{s0['id']}/approval", json={"action": "reopen"})
    rev = scene_of(c, pid)["meta"]["revision"]
    r = save(c, pid, s0["id"], rev, (["mood"], "calm"))
    assert r.status_code == 200 and r.json()["scene"]["approval"]["status"] == "approved"      # the answer already carries the new status
    assert scene_of(c, pid)["approval"]["status"] == "approved"


def test_a_scene_with_an_error_stays_unapproved_with_the_reason_and_the_exact_field(proj):
    c, pid, pdir = proj
    s0 = plan(c, pid)["plan"]["scenes"][0]
    f = pdir / "visual_plan.json"
    data = json.loads(f.read_text(encoding="utf-8"))
    data["scenes"][0]["shots"][0]["end"] = s0["end"] + 5          # a shot that runs past its scene
    f.write_text(json.dumps(data), encoding="utf-8")
    p = plan(c, pid)
    sc = p["plan"]["scenes"][0]
    assert sc["approval"]["status"] == "needs_edit" and sc["approval"]["reason"].startswith("Fix before approval:") and p["all_approved"] is False
    errors = [i for i in p["issues"][s0["id"]] if i["severity"] == "error"]
    assert errors and errors[0]["path"] == ["shots", 0, "end"] and "outside the scene" in errors[0]["message"]
    r = c.post(f"/projects/{pid}/visual-plan/scenes/{s0['id']}/approval", json={"action": "approve"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_values"                # not even by hand
    assert plan(c, pid)["plan"]["scenes"][1]["approval"]["status"] == "approved"                  # the other scenes are not affected


def test_a_warning_never_blocks_approval_but_an_error_does():
    def scene():
        return {"id": "scene_01", "number": 1, "start": 0, "end": 4, "shots": [{"id": "a", "start": 0, "end": 4, "assets": []}], "approval": {"status": "pending"}}
    warn, err = visual_plan._issue("warning", "scene 1: length 2.6s (typical 3-15s)"), visual_plan._issue("error", "scene 1: unknown pattern 'x'")
    s = scene()
    visual_plan.judge(s, {1: [warn]})
    assert s["approval"]["status"] == "approved" and s["approval"]["reason"] is None
    assert [i["severity"] for i in visual_plan.scene_issues(s, {1: [warn, err]})] == ["error", "warning"]     # errors first, nothing hidden
    s = scene()
    visual_plan.judge(s, {1: [warn, err]})
    assert s["approval"]["status"] == "needs_edit" and "unknown pattern" in s["approval"]["reason"]


def fake_scene_answer(scene):
    """A valid answer for a scene: two shots splitting it in the middle, every asset named in the first shot."""
    mid = round((scene["start"] + scene["end"]) / 2, 2)
    ids = [a["id"] for sh in scene["shots"] for a in sh["assets"]]
    return json.dumps({"purpose": "Generated purpose", "shots": [
        {"start": scene["start"], "end": mid, "purpose": "first", "visual_description": "wide", "asset_ids": ids, "camera": {"shot_type": "Wide", "angle": "Eye level", "movement": "Push-in"},
         "text": [{"content": "HELLO", "position": "center", "font_style": "bold", "animation": "Fade", "start": scene["start"] + 0.2}], "graphics": [], "transition": {"type": "Crossfade", "duration": 0.4}},
        {"start": mid, "end": scene["end"], "purpose": "second", "visual_description": "close", "asset_ids": [], "camera": {"movement": "Pan"}, "text": [], "graphics": [], "transition": None}],
        "layers": [], "motion_graphics": [], "effects": []})


def test_regenerating_replaces_only_that_scene_and_never_touches_assets_or_prompts(proj, monkeypatch):
    c, pid, pdir = proj
    before = plan(c, pid)["plan"]
    prompts = (pdir / "prompts_map.json").read_bytes()
    target = before["scenes"][1]
    monkeypatch.setattr(promptgen, "run_claude", lambda user, system="", timeout=0: fake_scene_answer(target))
    r = c.post(f"/projects/{pid}/visual-plan/scenes/{target['id']}/regenerate", json={})
    assert r.status_code == 200, r.text
    new = r.json()["scene"]
    assert [s["id"] for s in new["shots"]] == [f"{target['id']}_shot_01", f"{target['id']}_shot_02"] and new["purpose"] == "Generated purpose"
    assert new["counts"]["shots"] == 2 and new["counts"]["text_elements"] == 1
    assert {a["id"] for sh in new["shots"] for a in sh["assets"]} == {a["id"] for sh in target["shots"] for a in sh["assets"]}      # the same assets
    after = plan(c, pid)["plan"]
    assert after["scenes"][0] == before["scenes"][0] and after["scenes"][2:] == before["scenes"][2:]
    assert (pdir / "prompts_map.json").read_bytes() == prompts


def test_regenerating_over_edits_or_an_approval_needs_confirmation(proj, monkeypatch):
    c, pid, _ = proj
    s0 = scene_of(c, pid)
    monkeypatch.setattr(promptgen, "run_claude", lambda user, system="", timeout=0: fake_scene_answer(s0))
    save(c, pid, s0["id"], 1, (["purpose"], "my own words"))
    r = c.post(f"/projects/{pid}/visual-plan/scenes/{s0['id']}/regenerate", json={})
    assert r.status_code == 409 and r.json()["error"]["code"] == "confirm_overwrite"
    assert scene_of(c, pid)["purpose"] == "my own words"
    r = c.post(f"/projects/{pid}/visual-plan/scenes/{s0['id']}/regenerate", json={"confirm_overwrite": True})
    assert r.status_code == 200 and scene_of(c, pid)["purpose"] == "Generated purpose" and scene_of(c, pid)["meta"]["edited"] is False


def test_a_failed_or_invalid_generation_changes_nothing(proj, monkeypatch):
    c, pid, _ = proj
    s0 = scene_of(c, pid)
    r = c.post(f"/projects/{pid}/visual-plan/scenes/{s0['id']}/regenerate", json={})                          # the CLI is not available
    assert r.status_code == 502 and r.json()["error"]["code"] == "generation_failed"
    monkeypatch.setattr(promptgen, "run_claude", lambda user, system="", timeout=0: json.dumps({"shots": [{"start": 0, "end": 999, "asset_ids": []}]}))
    r = c.post(f"/projects/{pid}/visual-plan/scenes/{s0['id']}/regenerate", json={})
    assert r.status_code == 502 and r.json()["error"]["code"] == "generated_plan_invalid"
    assert scene_of(c, pid) == s0


def test_a_broken_file_is_reported_not_overwritten(proj):
    c, pid, pdir = proj
    plan(c, pid)
    (pdir / "visual_plan.json").write_text("{not json", encoding="utf-8")
    r = c.get(f"/projects/{pid}/visual-plan")
    assert r.status_code == 409 and r.json()["error"]["code"] == "visual_plan_broken"
    assert (pdir / "visual_plan.json").read_text(encoding="utf-8") == "{not json"


def test_a_changed_analysis_updates_untouched_scenes_and_flags_the_ones_the_user_worked_on(proj):
    c, pid, pdir = proj
    scenes = plan(c, pid)["plan"]["scenes"]
    save(c, pid, scenes[0]["id"], 1, (["purpose"], "mine"))
    sp = json.loads((pdir / "scene_plan.json").read_text(encoding="utf-8"))
    sp["scenes"][0]["concept"] = "a different concept"
    sp["scenes"][1]["concept"] = "another different concept"
    (pdir / "scene_plan.json").write_text(json.dumps(sp), encoding="utf-8")
    new = plan(c, pid)["plan"]["scenes"]
    assert new[0]["purpose"] == "mine" and new[0]["approval"]["status"] == "needs_edit" and new[0]["approval"]["reason"]
    assert new[1]["concept"] == "another different concept" and new[1]["approval"]["status"] == "approved"


def test_motion_graphics_derivation_and_editing_flow(proj):
    c, pid, pdir = proj
    comp = json.loads((pdir / "composition.json").read_text(encoding="utf-8"))
    comp["scenes"][0]["layers"].append({
        "type": "counter", "to": 2030, "unit": "years", "at": 1.5, "dur": 2.0, "pos": [960, 500], "z": 5
    })
    comp["scenes"][0]["layers"].append({
        "type": "chart", "kind": "bar", "data": [{"label": "A", "value": 10}], "at": 2.0, "dur": 1.5, "z": 6
    })
    comp["scenes"][0]["layers"].append({
        "type": "callout", "kind": "circle", "color": "#ff0000", "target": [100, 200], "at": 0.5, "dur": 1.0, "z": 7
    })
    (pdir / "composition.json").write_text(json.dumps(comp), encoding="utf-8")

    # Visual plan should derive motion graphics from composition layers
    p = plan(c, pid)
    s0 = p["plan"]["scenes"][0]
    motion = s0.get("motion_graphics", [])
    assert len(motion) == 3
    assert motion[0]["type"] == "number counter" and motion[0]["value"] == 2030 and motion[0]["unit"] == "years"
    assert motion[1]["type"] == "bar chart" and len(motion[1]["data"]) == 1
    assert motion[2]["type"] == "callout circle" and motion[2]["kind"] == "circle"

    # User edits motion graphics (e.g. changes target counter value)
    save(c, pid, s0["id"], 1, (["motion_graphics", 0, "value"], 2050), (["motion_graphics", 0, "unit"], "mars"))

    # apply_edits must write user's edited values back to composition.json
    comp_target = json.loads((pdir / "composition.json").read_text(encoding="utf-8"))
    written = visual_plan.apply_edits(pdir, comp_target)
    assert written >= 2
    counter_layer = next(l for l in comp_target["scenes"][0]["layers"] if l["type"] == "counter")
    assert counter_layer["to"] == 2050
    assert counter_layer["unit"] == "mars"
