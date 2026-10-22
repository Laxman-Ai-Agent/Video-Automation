"""The user's edits in visual_plan.json reach the composition (only the edited fields), and building the timeline never takes a scene's approval away.
Run: python -m pytest tests/test_m9_edits.py -q"""
import json

from backend import visual_plan


def plan_scene(number, edited, paths, text="New text", zoom_to=1.2):
    return {"number": number, "meta": {"edited": edited, "edited_paths": paths},
            "shots": [{"text": [{"content": text, "mark": "other", "position": None, "font_style": "big", "start": 2.0}],
                       "graphics": [{"type": "icon", "name": "star", "position": "tr", "animation": "pop", "start": 1.0, "duration": 0.5}],
                       "camera": {"movement": "push-in", "zoom_from": 1.0, "zoom_to": zoom_to, "focus": [0.5, 0.5]},
                       "transition": {"type": "wipe", "duration": 0.5}}],
            "effects": []}


def comp_scene(n):
    return {"id": n, "camera": {"move": "push-in", "from": 1, "to": 1.05, "focus": [0.1, 0.1]},
            "layers": [{"type": "text", "text": "Old text", "mark": "old", "style": "big", "at": 1.0},
                       {"type": "icon", "lucide": "heart", "pos": "tl", "enter": {"anim": "fade", "at": 3.0, "dur": 1.0}}],
            "transition_out": {"type": "fade", "dur": 0.6}}


def test_only_the_edited_fields_are_written_into_the_composition(tmp_path):
    (tmp_path / "visual_plan.json").write_text(json.dumps({"scenes": [
        plan_scene(1, True, ["shots / 0 / text / 0 / content", "shots / 0 / camera / zoom_to", "shots / 0 / graphics / 0 / name", "shots / 0 / transition / type"]),
        plan_scene(2, False, [], text="Never applied")]}), encoding="utf-8")
    comp = {"scenes": [comp_scene(1), comp_scene(2)]}
    written = visual_plan.apply_edits(tmp_path, comp)
    one, two = comp["scenes"]
    assert written == 4
    assert one["layers"][0]["text"] == "New text" and one["layers"][0]["mark"] == "old"       # edited field written, the unedited one kept
    assert one["camera"]["to"] == 1.2 and one["camera"]["from"] == 1 and one["camera"]["focus"] == [0.1, 0.1]
    assert one["layers"][1]["lucide"] == "star" and one["layers"][1]["pos"] == "tl"
    assert one["transition_out"] == {"type": "wipe", "dur": 0.6}
    assert two == comp_scene(2)                                                                # a scene that was never edited is untouched


def test_without_a_visual_plan_the_composition_is_unchanged(tmp_path):
    comp = {"scenes": [comp_scene(1)]}
    assert visual_plan.apply_edits(tmp_path, comp) == 0 and comp == {"scenes": [comp_scene(1)]}


def test_the_source_hash_ignores_what_the_timeline_build_writes_into_the_composition():
    row = {"id": 1, "start": 0, "end": 5, "narration": "x", "narration_en": "x", "meaning": "m", "concept": "c", "mood": "k", "mode": "mixed", "pattern": "hero_only", "keywords": []}
    before = visual_plan._source_hash(row, comp_scene(1), [{"n": 1}], None)
    built = comp_scene(1)
    built["layers"].append({"type": "image", "slot": "s01_0", "file": "projects/p/s01_0.png"})
    built["camera"]["focus"] = [0.7, 0.2]
    assert visual_plan._source_hash(row, built, [{"n": 1}], None) == before
    assert visual_plan._source_hash({**row, "meaning": "changed"}, built, [{"n": 1}], None) != before     # a real change of the analysis still shows


def test_a_layer_switched_off_in_the_timeline_is_written_into_the_composition_and_back_on_removes_it(tmp_path):
    vs = plan_scene(1, True, ["layers / 1 / enabled"])
    vs["layers"] = [{"id": "scene_01_layer_01", "type": "text", "enabled": True}, {"id": "scene_01_layer_02", "type": "icon", "enabled": False}]
    (tmp_path / "visual_plan.json").write_text(json.dumps({"scenes": [vs]}), encoding="utf-8")
    comp = {"scenes": [comp_scene(1)]}
    assert visual_plan.apply_edits(tmp_path, comp) == 1
    assert comp["scenes"][0]["layers"][1]["enabled"] is False and "enabled" not in comp["scenes"][0]["layers"][0]      # only the edited layer, only when off
    vs["layers"][1]["enabled"] = True
    (tmp_path / "visual_plan.json").write_text(json.dumps({"scenes": [vs]}), encoding="utf-8")
    visual_plan.apply_edits(tmp_path, comp)
    assert "enabled" not in comp["scenes"][0]["layers"][1]


def test_the_on_off_switch_can_be_saved_even_when_the_plan_was_made_before_the_switch_existed():
    scene = {"layers": [{"id": "a", "type": "text"}], "shots": [], "effects": [], "motion_graphics": []}
    assert visual_plan._apply(scene, [{"path": ["layers", 0, "enabled"], "value": False}]) == ["layers / 0 / enabled"]
    assert scene["layers"][0]["enabled"] is False
    try:
        visual_plan._apply(scene, [{"path": ["layers", 5, "enabled"], "value": False}])
        raise AssertionError("a layer that does not exist must be refused")
    except visual_plan.PlanError as e:
        assert e.code == "field_missing"


def test_a_switched_off_image_layer_is_not_checked_and_does_not_need_its_file(tmp_path, monkeypatch):
    from backend import config, prerender_checks, render
    comp = {"meta": {"fps": 30, "width": 1920, "height": 1080, "duration": 5.0}, "scenes": [
        {"id": 1, "start": 0, "end": 5, "layers": [{"type": "image", "slot": "s01_0", "file": "no/such/file.png", "enabled": False}]}]}
    rep = prerender_checks.Report("16:9")
    prerender_checks.check_media(rep, comp, tmp_path, "16:9", None, {})
    assert rep.findings == []                                                       # not an empty slot, not a missing file: it is switched off
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(render, "check_disk", lambda *a, **k: None)
    path = render.comp_path(tmp_path, "16:9")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(comp), encoding="utf-8")
    render.preflight(tmp_path)                                                      # no "missing files" problem for a layer that is off
    comp["scenes"][0]["layers"][0]["enabled"] = True
    path.write_text(json.dumps(comp), encoding="utf-8")
    try:
        render.preflight(tmp_path)
        raise AssertionError("the same layer switched on needs its file")
    except Exception as e:
        assert "missing files" in str(e)
