"""Visual Planning (backend/visual_planning.py), roadmap improvements/Visual_Planning_Complete_Roadmap: the 8 stages, the contract, both modes, validation and recovery, the planner
integration (autoplan) and the API. The Claude CLI is a fake; no network. Run: python -m pytest tests/test_visual_planning.py -q"""
import importlib
import json
import shutil
import time
from unittest.mock import patch

import pytest

from backend import autoplan, promptgen
from backend import visual_planning as vp
from backend.models import PromptsMap, ScenePlan

_m7 = importlib.import_module("test_m7")
_m9 = importlib.import_module("test_m9_autoplan")
client, create, FIXTURE = _m7.client, _m7.create, _m7.FIXTURE
auto, settle, upload_and_transcribe = _m9.auto, _m9.settle, _m9.upload_and_transcribe


def project(tmp_path, images=False, aspect=None):
    for f in FIXTURE.iterdir():
        if f.is_file():
            shutil.copyfile(f, tmp_path / f.name)
    info = {"id": "t", "name": "t", "use_images": images, **({"aspect": aspect} if aspect else {})}
    (tmp_path / "project.json").write_text(json.dumps(info), encoding="utf-8")
    return tmp_path, json.loads((tmp_path / "scene_plan.json").read_text(encoding="utf-8")), json.loads((tmp_path / "prompts_map.json").read_text(encoding="utf-8"))


def raw_for(sp, pm, images=False, mutate=None):
    """What a good planner answer looks like (made from the same derivation, so every rule is satisfied), then changed by `mutate` to break exactly one rule."""
    ctx = {"plan": ScenePlan.model_validate(sp), "prompts": PromptsMap.model_validate(pm).prompts, "images": images}
    n = len(ctx["plan"].scenes)
    scenes = [vp._derive_scene(ctx, s, k, n) for k, s in enumerate(ctx["plan"].scenes, 1)]
    for s in scenes:
        s["uncertainty"] = []
    raw = {"visual_style": {"category": "documentary", "tone": "curious", "density": "medium"}, "scenes": scenes}
    if mutate:
        mutate(raw)
    return raw


def scene(plan, i=0):
    return plan["scenes"][i]


# ---------- contract, stages, exact narration ----------
def test_a_valid_planner_answer_becomes_the_visual_plan_with_every_field_of_the_contract(tmp_path):
    d, sp, pm = project(tmp_path)
    plan, problems = vp.assemble(d, sp, pm, raw_for(sp, pm))
    assert problems == [] and plan["source"] == "llm" and plan["llm"]["status"] == "applied" and plan["validation"]["errors"] == []
    assert {"schema_version", "project", "visual_style", "scenes", "stages", "validation", "llm", "needs_review"} <= set(plan)
    assert plan["project"] == {"visual_mode": "motion_only", "aspect_ratio": "16:9", "width": 1920, "height": 1080, "fps": 30}
    s = scene(plan)
    assert {"scene_id", "source_segment_ids", "narration", "scene_objective", "visual_concept", "elements", "element_relationships", "asset_requirements", "motion_hints", "continuity",
            "validation_notes"} <= set(s)
    assert s["scene_id"] == "scene_01" and s["plan_scene_id"] == 1
    assert {"element_id", "type", "role", "required", "visual_description", "placement"} <= set(s["elements"][0])
    assert plan["validation"]["checks"]["passed"] == plan["validation"]["checks"]["total"] > 0                  # no probability: the checks that passed


def test_the_eight_stages_are_reported_and_a_derived_plan_does_not_claim_the_planner_judged_the_meaning(tmp_path):
    d, sp, pm = project(tmp_path)
    good, _ = vp.assemble(d, sp, pm, raw_for(sp, pm))
    assert [x["name"] for x in good["stages"]] == list(vp.STAGES) and len(good["stages"]) == 8
    assert [x["status"] for x in good["stages"]][5:] == ["completed"] * 3
    derived, _ = vp.assemble(d, sp, pm, None)
    assert derived["source"] == "derived_from_scene_plan" and derived["llm"]["status"] == "not_provided" and derived["needs_review"] is True
    assert [x["status"] for x in derived["stages"][:5]] == ["warning"] * 5 and "not judged by Claude" in derived["stages"][0]["detail"]
    assert derived["validation"]["confidence"] == "reduced" and good["validation"]["confidence"] == "supported_by_llm"


def test_narration_and_times_are_copied_from_the_source_and_the_planner_cannot_change_them(tmp_path):
    d, sp, pm = project(tmp_path)
    tr = json.loads((tmp_path / "transcript.json").read_text(encoding="utf-8"))
    plan, _ = vp.assemble(d, sp, pm, raw_for(sp, pm))
    for s, ps in zip(plan["scenes"], sp["scenes"]):
        assert (s["narration"]["start_seconds"], s["narration"]["end_seconds"]) == (ps["start"], ps["end"])
    words = [w["w"] for seg in tr["segments"] for w in seg["words"] if sp["scenes"][0]["start"] <= (w["start"] + w["end"]) / 2 <= sp["scenes"][0]["end"]]
    assert scene(plan)["narration"]["text"] == " ".join(words)                                       # exact source words, never rewritten
    bad = raw_for(sp, pm, mutate=lambda r: r["scenes"][0].update(narration={"text": "rewritten", "start_seconds": 99}))
    plan2, problems = vp.assemble(d, sp, pm, bad)
    assert problems and any("narration" in m for m in problems) and plan2["source"] == "derived_from_scene_plan"          # extra keys are rejected: the planner owns no narration or time


def test_a_scene_with_no_transcript_words_gets_no_invented_narration_or_times(tmp_path):
    d, sp, pm = project(tmp_path)
    tr = json.loads((tmp_path / "transcript.json").read_text(encoding="utf-8"))
    for seg in tr["segments"]:
        seg["words"] = []
    (tmp_path / "transcript.json").write_text(json.dumps(tr), encoding="utf-8")
    plan, _ = vp.assemble(d, sp, pm, None)
    n = scene(plan)["narration"]
    assert n["text"] == "" and n["timestamp_source"] in ("scene_plan", "audio_analysis") and (n["start_seconds"], n["end_seconds"]) == (sp["scenes"][0]["start"], sp["scenes"][0]["end"])
    assert any("no narration" in w for w in plan["validation"]["warnings"])                           # said, not hidden


def test_telugu_narration_is_kept_exactly_and_telugu_on_screen_text_is_allowed(tmp_path):
    d, sp, pm = project(tmp_path)
    tr = json.loads((tmp_path / "transcript.json").read_text(encoding="utf-8"))
    tr["segments"][0]["words"][0]["w"] = "నమస్తే"
    (tmp_path / "transcript.json").write_text(json.dumps(tr, ensure_ascii=False), encoding="utf-8")

    def telugu(r):
        next(e for e in r["scenes"][0]["elements"] if e["type"] == "text").update(content="నమస్తే", language="te")
    plan, problems = vp.assemble(d, sp, pm, raw_for(sp, pm, mutate=telugu))
    assert problems == [] and scene(plan)["narration"]["text"].startswith("నమస్తే")
    assert next(e for e in scene(plan)["elements"] if e["type"] == "text")["content"] == "నమస్తే"        # no transliteration, no rewrite


# ---------- elements, relationships, hierarchy ----------
def test_duplicate_element_ids_block_the_plan_and_are_reported(tmp_path):
    d, sp, pm = project(tmp_path)

    def dup(r):
        r["scenes"][1]["elements"][1]["element_id"] = r["scenes"][1]["elements"][0]["element_id"]
    _, problems = vp.assemble(d, sp, pm, raw_for(sp, pm, mutate=dup))
    assert any("element ids repeat" in m for m in problems)


def test_a_relationship_to_a_missing_element_is_removed_and_no_element_is_deleted(tmp_path):
    d, sp, pm = project(tmp_path)

    def broken(r):
        r["scenes"][1]["element_relationships"].append({"source": "text_main", "target": "ghost", "relation": "labels", "description": None})
    plan, problems = vp.assemble(d, sp, pm, raw_for(sp, pm, mutate=broken))
    s = scene(plan, 1)
    assert problems == [] and all(r["target"] != "ghost" for r in s["element_relationships"])
    assert any(n["code"] == "relationship_removed" for n in s["validation_notes"]) and any(e["element_id"] == "text_main" for e in s["elements"])


def test_an_unknown_relation_word_is_rejected_by_the_schema(tmp_path):
    d, sp, pm = project(tmp_path)
    plan, problems = vp.assemble(d, sp, pm, raw_for(sp, pm, mutate=lambda r: r["scenes"][1]["element_relationships"].append({"source": "text_main", "target": "image_s02_0", "relation": "likes"})))
    assert problems and plan["source"] == "derived_from_scene_plan"


def test_every_scene_has_a_primary_element_and_decoration_cannot_replace_a_required_concept(tmp_path):
    d, sp, pm = project(tmp_path, images=False)

    def only_decoration(r):
        for e in r["scenes"][0]["elements"]:
            e["role"] = "decoration"
            e["required"] = False
    _, problems = vp.assemble(d, sp, pm, raw_for(sp, pm, images=False, mutate=only_decoration))
    assert any("no primary element" in m for m in problems)
    assert all(any(e["role"] == "primary" for e in s["elements"]) for s in vp.assemble(d, sp, pm, None)[0]["scenes"])           # the derived plan always has one


def test_a_cluttered_scene_is_a_warning(tmp_path):
    d, sp, pm = project(tmp_path)

    def clutter(r):
        r["scenes"][0]["elements"] += [vp._el(f"extra_{i}", "graphic", "decoration", "spark", required=False, prio=5) for i in range(6)]
    plan, problems = vp.assemble(d, sp, pm, raw_for(sp, pm, mutate=clutter))
    assert problems == [] and any("clutter" in w for w in plan["validation"]["warnings"])


def test_a_supporting_element_with_a_higher_priority_than_the_primary_is_a_warning(tmp_path):
    d, sp, pm = project(tmp_path)

    def flip(r):
        els = r["scenes"][1]["elements"]
        els[0]["placement"]["priority"] = 3
        els[1]["placement"]["priority"] = 1
    plan, _ = vp.assemble(d, sp, pm, raw_for(sp, pm, mutate=flip))
    assert any("higher priority than the primary" in w for w in plan["validation"]["warnings"])


# ---------- text and typography ----------
def test_on_screen_text_is_kept_apart_from_the_narration_and_a_sentence_overlay_is_flagged(tmp_path):
    d, sp, pm = project(tmp_path)
    nar = vp.assemble(d, sp, pm, None)[0]["scenes"][0]["narration"]["text"]

    def overlay(r):
        next(e for e in r["scenes"][0]["elements"] if e["type"] == "text")["content"] = nar
    plan, _ = vp.assemble(d, sp, pm, raw_for(sp, pm, mutate=overlay))
    assert any("repeats the narration" in w or "too long" in w for w in plan["validation"]["warnings"])
    assert plan["scenes"][0]["narration"]["text"] == nar                                               # the narration itself is untouched


def test_a_number_said_in_words_is_as_grounded_as_the_digits(tmp_path):
    d, sp, pm = project(tmp_path)
    en = json.loads((tmp_path / "transcript_en.json").read_text(encoding="utf-8"))
    en["segments"][0]["en"] = "The trip takes eight months"
    (tmp_path / "transcript_en.json").write_text(json.dumps(en), encoding="utf-8")
    s0 = sp["scenes"][0]
    en["segments"][0]["start"], en["segments"][0]["end"] = s0["start"], s0["start"] + 1
    (tmp_path / "transcript_en.json").write_text(json.dumps(en), encoding="utf-8")

    def label(value):
        def f(r):
            next(e for e in r["scenes"][0]["elements"] if e["type"] == "text")["content"] = value
        return f
    plan, problems = vp.assemble(d, sp, pm, raw_for(sp, pm, mutate=label("8 months")))
    assert problems == [] and not any("number that is not in the narration" in w for w in plan["validation"]["warnings"])
    plan, problems = vp.assemble(d, sp, pm, raw_for(sp, pm, mutate=label("9 months")))
    assert any("number that is not in the narration" in w for w in plan["validation"]["warnings"])           # a different number is still flagged


def test_an_invented_number_in_a_label_is_refused_but_a_stated_one_passes(tmp_path):
    d, sp, pm = project(tmp_path)

    def number(value):
        def f(r):
            next(e for e in r["scenes"][0]["elements"] if e["type"] == "text")["content"] = value
        return f
    _, problems = vp.assemble(d, sp, pm, raw_for(sp, pm, mutate=number("97% faster")))
    assert any("number that is not in the narration" in m for m in problems)
    _, ok = vp.assemble(d, sp, pm, raw_for(sp, pm, mutate=number("AI agents")))
    assert ok == []


def test_text_must_be_grounded_and_at_most_two_text_elements(tmp_path):
    d, sp, pm = project(tmp_path)

    def noise(r):
        s = r["scenes"][0]
        next(e for e in s["elements"] if e["type"] == "text")["content"] = "Quantum blockchain revolution"
        s["elements"] += [vp._el("t2", "label", "explanatory", "x", content="Agents", language="en", region="lower_safe_area", prio=4),
                          vp._el("t3", "label", "explanatory", "y", content="Build", language="en", region="lower_safe_area", prio=5)]
    plan, problems = vp.assemble(d, sp, pm, raw_for(sp, pm, mutate=noise))
    w = " ".join(plan["validation"]["warnings"])
    assert problems == [] and "mostly not from the narration" in w and "3 text elements" in w


def test_text_over_the_whole_frame_has_no_safe_area_but_a_side_placement_is_fine(tmp_path):
    d, sp, pm = project(tmp_path)
    put = lambda region: (lambda r: next(e for e in r["scenes"][0]["elements"] if e["type"] == "text")["placement"].update(region=region))
    plan, _ = vp.assemble(d, sp, pm, raw_for(sp, pm, mutate=put("full_frame")))
    assert any("safe area" in w for w in plan["validation"]["warnings"])
    for region in ("right", "left", "top", "bottom", "upper_left"):                                        # placement intents: the layout stage keeps them inside the safe area
        plan, _ = vp.assemble(d, sp, pm, raw_for(sp, pm, mutate=put(region)))
        assert not any("safe area" in w for w in plan["validation"]["warnings"]), region


# ---------- registry ----------
def test_a_real_icon_is_resolved_and_an_unknown_one_becomes_a_search_descriptor(tmp_path, monkeypatch):
    from backend import quality
    monkeypatch.setattr(quality, "icon_names", lambda: frozenset({"Code", "Heart"}))
    d, sp, pm = project(tmp_path)
    plan, problems = vp.assemble(d, sp, pm, raw_for(sp, pm))
    icon = next(e for e in scene(plan, 2)["elements"] if e["type"] == "icon")                           # scene 3 uses "code"
    assert problems == [] and icon["registry_requirements"]["icon"] == "code" and icon["registry_requirements"]["resolved"] is True

    def fake_icon(r):
        next(e for e in r["scenes"][2]["elements"] if e["type"] == "icon")["registry_requirements"]["icon"] = "no-such-icon"
    plan, _ = vp.assemble(d, sp, pm, raw_for(sp, pm, mutate=fake_icon))
    reg = next(e for e in scene(plan, 2)["elements"] if e["type"] == "icon")["registry_requirements"]
    assert reg["icon"] is None and reg["resolved"] is False and "no such icon" in reg["search_descriptors"]       # never an unvalidated id


def test_when_the_registry_cannot_be_read_the_icon_is_not_guessed(tmp_path, monkeypatch):
    from backend import quality
    monkeypatch.setattr(quality, "icon_names", lambda: None)
    d, sp, pm = project(tmp_path)
    plan, _ = vp.assemble(d, sp, pm, raw_for(sp, pm))
    reg = next(e for e in scene(plan, 2)["elements"] if e["type"] == "icon")["registry_requirements"]
    assert reg["icon"] == "code" and reg["resolved"] is None


# ---------- modes ----------
def test_motion_only_mode_has_no_image_or_video_requirement_anywhere(tmp_path):
    d, sp, pm = project(tmp_path, images=False)
    derived, problems = vp.assemble(d, sp, pm, None)
    assert problems == [] and derived["project"]["visual_mode"] == "motion_only"
    assert all(not s["asset_requirements"] and all(e["type"] not in ("image", "video") for e in s["elements"]) for s in derived["scenes"])
    assert all(any(e["role"] == "primary" for e in s["elements"]) for s in derived["scenes"])               # still realisable: a drawn concept, text, icon, chart ...
    plan, problems = vp.assemble(d, sp, pm, raw_for(sp, pm, images=True))                                  # a planner that ignored the mode
    assert problems == [] and all(not s["asset_requirements"] and all(e["type"] not in ("image", "video") for e in s["elements"]) for s in plan["scenes"])
    assert any(n["code"] == "mode_image_element" for s in plan["scenes"] for n in s["validation_notes"]) and plan["needs_review"]        # repaired, and said so


def test_the_aspect_ratio_of_the_project_sets_the_size(tmp_path):
    d, sp, pm = project(tmp_path, aspect="9:16")
    plan, _ = vp.assemble(d, sp, pm, None)
    assert plan["project"]["aspect_ratio"] == "9:16" and (plan["project"]["width"], plan["project"]["height"]) == (1080, 1920)


# ---------- motion hints, style, continuity ----------
def test_motion_hints_are_intents_never_presets_or_timing(tmp_path):
    d, sp, pm = project(tmp_path)
    plan, _ = vp.assemble(d, sp, pm, raw_for(sp, pm, mutate=lambda r: r["scenes"][0]["motion_hints"].append({"element_id": "text_main", "intent": "emphasize_growth", "description": "use preset zoom-in with easing ease-out over 500 ms"})))
    h = next(h for h in scene(plan)["motion_hints"] if h["intent"] == "emphasize_growth")
    assert h["description"] is None and any(n["code"] == "motion_detail" for n in scene(plan)["validation_notes"])
    _, problems = vp.assemble(d, sp, pm, raw_for(sp, pm, mutate=lambda r: r["scenes"][0]["motion_hints"].append({"intent": "Zoom In Fast!"})))
    assert problems                                                                                      # not even a valid intent token
    text = json.dumps(plan)
    assert '"preset"' not in text and '"easing"' not in text and '"keyframes"' not in text


def test_style_comes_from_the_scene_plan_and_continuity_links_the_scenes(tmp_path):
    d, sp, pm = project(tmp_path)
    plan, _ = vp.assemble(d, sp, pm, raw_for(sp, pm))
    assert plan["visual_style"]["palette"] == sp["style"]["palette"] and plan["visual_style"]["style_suffix"] == sp["style"]["suffix"]
    assert scene(plan)["continuity"]["previous_scene_id"] is None and scene(plan)["continuity"]["next_scene_id"] == "scene_02"
    assert plan["scenes"][-1]["continuity"]["next_scene_id"] is None and plan["scenes"][3]["continuity"]["previous_scene_id"] == "scene_03"


def test_the_same_concept_twice_in_a_row_and_an_off_palette_colour_are_warnings(tmp_path):
    d, sp, pm = project(tmp_path)

    def same(r):
        r["scenes"][1]["visual_concept"].update(representation=r["scenes"][0]["visual_concept"]["representation"], primary_focus=r["scenes"][0]["visual_concept"]["primary_focus"])
        r["scenes"][0]["elements"][0]["appearance"] = {"color": "#123456"}
    plan, problems = vp.assemble(d, sp, pm, raw_for(sp, pm, mutate=same))
    w = " ".join(plan["validation"]["warnings"])
    assert problems == [] and "repeats the concept" in w and "not in the project palette" in w


def test_a_scene_the_planner_left_out_is_derived_and_said_so(tmp_path):
    d, sp, pm = project(tmp_path)
    plan, problems = vp.assemble(d, sp, pm, raw_for(sp, pm, mutate=lambda r: r["scenes"].pop(3)))
    assert problems == [] and len(plan["scenes"]) == len(sp["scenes"]) and any(n["code"] == "scene_derived" for n in plan["scenes"][3]["validation_notes"])


def test_a_scene_that_is_not_in_the_scene_plan_is_a_problem(tmp_path):
    d, sp, pm = project(tmp_path)
    _, problems = vp.assemble(d, sp, pm, raw_for(sp, pm, mutate=lambda r: r["scenes"][0].update(plan_scene_id=99)))
    assert any("not in the scene plan" in m for m in problems)


def test_the_same_input_gives_the_same_ids_and_order(tmp_path):
    d, sp, pm = project(tmp_path)
    a = vp.assemble(d, sp, pm, raw_for(sp, pm))[0]
    b = vp.assemble(d, sp, pm, raw_for(sp, pm))[0]
    ids = lambda p: [(s["scene_id"], [e["element_id"] for e in s["elements"]], [x["requirement_id"] for x in s["asset_requirements"]]) for s in p["scenes"]]
    assert ids(a) == ids(b) and a["source_fingerprint"] == b["source_fingerprint"]


# ---------- stored plan, old projects, staleness ----------
def test_a_project_made_before_visual_planning_is_read_as_a_derived_plan_and_nothing_is_written(tmp_path):
    d, sp, pm = project(tmp_path)
    before = sorted(p.name for p in d.iterdir())
    plan = vp.load(d)
    assert plan["stored"] is False and plan["source"] == "derived_from_scene_plan" and len(plan["scenes"]) == len(sp["scenes"])
    assert sorted(p.name for p in d.iterdir()) == before                                                  # old projects stay readable and untouched
    assert vp.load(tmp_path / "nowhere") is None


def test_a_stored_plan_is_stale_when_the_scene_plan_changes(tmp_path):
    d, sp, pm = project(tmp_path)
    vp.save(d, vp.assemble(d, sp, pm, raw_for(sp, pm))[0])
    assert vp.load(d)["stale"] is False and vp.load(d)["stored"] is True
    sp["scenes"][0]["meaning"] = "something else"
    (d / "scene_plan.json").write_text(json.dumps(sp), encoding="utf-8")
    assert vp.load(d)["stale"] is True


# ---------- handoffs ----------
def test_no_picture_slot_is_mapped_and_motion_gets_ids_and_hints_only(tmp_path):
    d, sp, pm = project(tmp_path)
    vp.save(d, vp.assemble(d, sp, pm, raw_for(sp, pm))[0])
    assert vp.slot_map(d) == {}                                                                          # Motion-Only: no picture slot is linked to an element
    h = vp.motion_handoff(d)
    assert [x["scene_id"] for x in h] == [f"scene_{s['id']:02d}" for s in sp["scenes"]]
    assert all({"element_id", "type", "role", "required"} == set(e) for x in h for e in x["elements"]) and "preset" not in json.dumps(h)


# ---------- the planner (autoplan) ----------
class WithVisual:
    """The planner CLI answering with a visual_plan as well; `visual` = "good", "bad" or None (no visual_plan); `calls` lists the calls."""
    def __init__(self, visual="good"):
        self.visual, self.calls, self.users = visual, [], []

    def __call__(self, user, system="", timeout=0):
        if system == autoplan.TRANSLATE_SYSTEM:
            self.calls.append("translate")
            return json.dumps({"segments": []})
        self.calls.append("plan")
        self.users.append(user)
        read = lambda n: json.loads((FIXTURE / n).read_text(encoding="utf-8"))
        sp, pm = read("scene_plan.json"), read("prompts_map.json")
        out = {"scene_plan": sp, "prompts_map": pm}
        if self.visual == "good":
            out["visual_plan"] = raw_for(sp, pm)
        elif self.visual == "bad":
            out["visual_plan"] = {"scenes": [{"plan_scene_id": 1}]}
        return "Here is the plan:\n" + json.dumps(out)


def test_the_planner_writes_the_visual_plan_with_the_plan_and_publishes_it_before_the_plan_is_ready(auto, monkeypatch):
    c, llm = auto
    fake = WithVisual("good")
    monkeypatch.setattr(promptgen, "run_claude", fake)
    pid, pdir = upload_and_transcribe(c)
    assert settle(c, pid)["state"] == "done" and fake.calls == ["translate", "plan"], fake.users[-1][-700:]
    plan = json.loads((pdir / "visual_planning.json").read_text(encoding="utf-8"))
    assert plan["source"] == "llm" and plan["llm"]["status"] == "applied" and plan["validation"]["errors"] == []
    assert vp.load(pdir)["stale"] is False                                                              # the fingerprint matches the files that were published
    assert "visual_plan" in autoplan.PLAN_SYSTEM and "visual_plan" in autoplan._instructions(True) and "MOTION-ONLY" in autoplan._instructions(False)


def test_a_planner_answer_without_a_visual_plan_is_derived_flagged_and_does_not_fail_the_plan(auto):
    c, llm = auto                                                                                      # the fake of test_m9 answers scene_plan and prompts_map only
    pid, pdir = upload_and_transcribe(c)
    assert settle(c, pid)["state"] == "done" and llm.calls == ["translate", "plan"]
    plan = json.loads((pdir / "visual_planning.json").read_text(encoding="utf-8"))
    assert plan["source"] == "derived_from_scene_plan" and plan["llm"]["status"] == "not_provided" and plan["needs_review"] is True


def test_an_invalid_visual_plan_is_retried_once_then_derived_and_the_scene_plan_still_publishes(auto, monkeypatch):
    c, llm = auto
    fake = WithVisual("bad")
    monkeypatch.setattr(promptgen, "run_claude", fake)
    pid, pdir = upload_and_transcribe(c)
    g = settle(c, pid)
    assert g["state"] == "done" and fake.calls == ["translate", "plan", "plan"]                          # one bounded repair attempt
    plan = json.loads((pdir / "visual_planning.json").read_text(encoding="utf-8"))
    assert plan["source"] == "derived_from_scene_plan" and plan["llm"]["status"] == "rejected" and plan["llm"]["problems"] and plan["needs_review"]
    assert (pdir / "scene_plan.json").exists() and (pdir / "prompts_map.json").exists()


# ---------- a project that already has its scene plan ----------
def test_visual_planning_over_an_existing_plan_never_changes_the_scene_plan(tmp_path):
    d, sp, pm = project(tmp_path)
    before = {n: (d / n).read_bytes() for n in ("scene_plan.json", "prompts_map.json", "composition.json", "prompts.txt")}
    seen = []

    def ask(user, system="", timeout=0):
        seen.append((system, user))
        return json.dumps({"visual_plan": raw_for(sp, pm)})
    plan = vp.run(d, ask=ask)
    assert plan["source"] == "llm" and (d / "visual_planning.json").exists() and len(seen) == 1 and seen[0][0] == vp.VISUAL_SYSTEM
    assert {n: (d / n).read_bytes() for n in before} == before                                           # the user's plan and prompts are untouched
    assert "MOTION-ONLY MODE" in seen[0][1] and "IMAGE MODE" not in seen[0][1]


def test_visual_planning_retries_once_with_the_problems_then_derives(tmp_path):
    d, sp, pm = project(tmp_path)
    asked = []

    def ask(user, system="", timeout=0):
        asked.append(user)
        return json.dumps({"visual_plan": {"scenes": [{"plan_scene_id": 1}]}})
    plan = vp.run(d, ask=ask)
    assert len(asked) == 2 and "Your previous answer had these problems" in asked[1]
    assert plan["source"] == "derived_from_scene_plan" and plan["llm"]["status"] == "rejected" and plan["needs_review"]


def test_without_claude_the_plan_is_derived_with_the_reason_never_blank(tmp_path):
    d, sp, pm = project(tmp_path)

    def down(user, system="", timeout=0):
        raise promptgen.GenError("the Claude CLI was not found on this machine")
    plan = vp.run(d, ask=down)
    assert plan["llm"]["status"] == "unavailable" and "not found" in plan["llm"]["problems"][0] and plan["needs_review"] and len(plan["scenes"]) == len(sp["scenes"])
    assert all(s["elements"] for s in plan["scenes"])


# ---------- solve the warnings of the stored plan ----------
def cluttered_plan(tmp_path):
    """A stored plan whose scene 1 has the 'cluttered' warning (7 elements) and whose other scenes have none."""
    d, sp, pm = project(tmp_path)

    def clutter(r):
        r["scenes"][0]["elements"] += [vp._el(f"extra_{i}", "graphic", "decoration", "spark", required=False, prio=5) for i in range(6)]
    plan, problems = vp.assemble(d, sp, pm, raw_for(sp, pm, mutate=clutter))
    assert problems == [] and vp.warned(plan).keys() == {1}
    vp.save(d, plan)
    return d, sp, pm, plan


def test_solving_warnings_asks_only_about_the_scenes_with_warnings_and_keeps_every_other_scene(tmp_path):
    d, sp, pm, old = cluttered_plan(tmp_path)
    asked = []

    def ask(user, system="", timeout=0):
        asked.append(user)
        fixed = vp._to_llm(old["scenes"][0])
        fixed["elements"] = [e for e in fixed["elements"] if not e["element_id"].startswith("extra_")]           # the fix: the decoration is dropped
        return json.dumps({"visual_plan": {"scenes": [fixed]}})
    before = {n: (d / n).read_bytes() for n in ("scene_plan.json", "prompts_map.json", "composition.json", "prompts.txt")}
    plan = vp.fix_warnings(d, ask=ask)
    assert len(asked) == 1 and "SOLVE ONLY THE WARNINGS" in asked[0] and old["validation"]["warnings"][0] in asked[0] and "at most 6 elements" in asked[0]   # the real warning and its hint
    assert asked[0].count('"meaning"') == 1                                                                   # only the scene with the warning is in the question (one row)
    assert plan["validation"]["warnings"] == [] and plan["warning_fix"]["status"] == "solved" and plan["warning_fix"]["before"] == 1 and plan["warning_fix"]["after"] == 0
    assert plan["warning_fix"]["scenes"] == ["scene_01"]
    assert [json.dumps(s, sort_keys=True) for s in plan["scenes"][1:]] == [json.dumps(s, sort_keys=True) for s in old["scenes"][1:]]       # every other scene is exactly as it was
    assert len(plan["scenes"][0]["elements"]) == len(old["scenes"][0]["elements"]) - 6
    assert {n: (d / n).read_bytes() for n in before} == before                                               # the scene plan and the prompts are untouched
    assert vp.load(d)["warning_fix"]["status"] == "solved" and list((d / "plan_backups").iterdir())          # saved, and the plan that was there is kept in plan_backups


def test_a_fix_that_does_not_reduce_the_warnings_keeps_the_old_plan_and_says_so(tmp_path):
    d, sp, pm, old = cluttered_plan(tmp_path)
    plan = vp.fix_warnings(d, ask=lambda user, system="", timeout=0: json.dumps({"visual_plan": {"scenes": [vp._to_llm(old["scenes"][0])]}}))   # Claude returns the scene unchanged
    assert plan["warning_fix"]["status"] == "no_improvement" and plan["warning_fix"]["before"] == plan["warning_fix"]["after"] == 1
    assert json.dumps(plan["scenes"], sort_keys=True) == json.dumps(old["scenes"], sort_keys=True) and plan["validation"]["warnings"] == old["validation"]["warnings"]   # nothing was hidden


def test_solving_retries_once_with_the_problems_then_fails_without_changing_the_plan(tmp_path):
    d, sp, pm, old = cluttered_plan(tmp_path)
    asked = []

    def ask(user, system="", timeout=0):
        asked.append(user)
        return json.dumps({"visual_plan": {"scenes": [{"plan_scene_id": 2}]}})                                # not the scene that was asked about
    with pytest.raises(promptgen.GenError, match="could not be used"):
        vp.fix_warnings(d, ask=ask)
    assert len(asked) == 2 and "Your previous answer had these problems" in asked[1] and "the answer has no scene 1" in asked[1]
    assert vp.load(d)["validation"]["warnings"] == old["validation"]["warnings"] and "warning_fix" not in vp.load(d)


def test_a_plan_without_warnings_has_nothing_to_solve_and_no_job_starts(tmp_path):
    d, sp, pm = project(tmp_path)
    plan, _ = vp.assemble(d, sp, pm, raw_for(sp, pm))
    vp.save(d, plan)
    assert vp.warned(plan) == {} and vp.fix_warnings(d, ask=lambda *a, **k: pytest.fail("Claude must not be asked")) == plan
    with pytest.raises(vp.review.ReviewError, match="no warnings"):
        vp.start_fix(d)


def test_the_fix_refuses_a_plan_that_is_out_of_date(tmp_path):
    d, sp, pm, old = cluttered_plan(tmp_path)
    stale = json.loads((d / "visual_planning.json").read_text(encoding="utf-8"))
    stale["source_fingerprint"] = "changed"
    (d / "visual_planning.json").write_text(json.dumps(stale), encoding="utf-8")
    with pytest.raises(promptgen.GenError, match="out of date"):
        vp.fix_warnings(d, ask=lambda *a, **k: pytest.fail("Claude must not be asked"))


def test_garbage_answers_are_handled_safely(tmp_path):
    d, sp, pm = project(tmp_path)
    for text in ("not json at all", "{}", '{"visual_plan": null}', '{"visual_plan": 5}'):
        plan = vp.run(d, ask=lambda *a, text=text, **k: text)
        assert plan["source"] == "derived_from_scene_plan" and plan["llm"]["status"] == "rejected"


def test_run_needs_a_scene_plan(tmp_path):
    (tmp_path / "project.json").write_text("{}", encoding="utf-8")
    with pytest.raises(promptgen.GenError):
        vp.run(tmp_path, ask=lambda *a, **k: "{}")


# ---------- the API ----------
def test_the_api_reads_the_plan_runs_only_on_request_and_never_starts_a_second_job(client, monkeypatch):
    pid = create(client).json()["id"]
    assert client.get(f"/projects/{pid}/visual-planning").status_code == 409                                  # no scene plan yet
    pdir = _m7.install_plan(pid)
    for n in ("transcript.json", "transcript_corrected.json"):                                              # Stage 2's verified transcript (Visual Planning requires it)
        shutil.copyfile(FIXTURE / "transcript.json", pdir / n)
    r = client.get(f"/projects/{pid}/visual-planning")
    assert r.status_code == 200, r.text[:300]
    assert r.json()["stored"] is False and r.json()["source"] == "derived_from_scene_plan" and len(r.json()["stages"]) == 8      # reading starts nothing
    assert not (pdir / "visual_planning.json").exists()
    sp, pm = (json.loads((pdir / n).read_text(encoding="utf-8")) for n in ("scene_plan.json", "prompts_map.json"))
    calls = []

    def slow(*a, **k):
        calls.append(1)
        time.sleep(0.3)
        return json.dumps({"visual_plan": raw_for(sp, pm)})
    monkeypatch.setattr(promptgen, "run_claude", slow)
    first = client.post(f"/projects/{pid}/visual-planning/run")
    second = client.post(f"/projects/{pid}/visual-planning/run")
    assert first.status_code == second.status_code == 202 and first.json()["started"] == second.json()["started"]
    assert settle(client, pid)["state"] == "done" and len(calls) == 1
    got = client.get(f"/projects/{pid}/visual-planning").json()
    assert got["stored"] is True and got["source"] == "llm" and got["stale"] is False


def test_a_blocking_error_in_the_stored_visual_plan_shows_in_the_pipeline_stage(client):
    pid = create(client).json()["id"]
    pdir = _m7.install_plan(pid)
    sp, pm = (json.loads((pdir / n).read_text(encoding="utf-8")) for n in ("scene_plan.json", "prompts_map.json"))
    plan = vp.assemble(pdir, sp, pm, None)[0]
    plan["validation"]["errors"] = ["scene_01 has no primary element"]
    vp.save(pdir, plan)
    stage = next(s for s in client.get(f"/projects/{pid}/pipeline").json()["stages"] if s["id"] == "planning")
    assert stage["status"] == "failed" and "visual plan" in stage["detail"]


# ---------- the canonical source: Scene Segmentation (one planned scene for each of its scenes, its times, its pauses) ----------
_seg = importlib.import_module("test_scene_segmentation")
from backend import scene_segmentation  # noqa: E402
from backend.visual_planning import mapping_errors  # noqa: E402


def seg_project(d, images=False, info=True, bounds=None, step=None):
    """Three sentences with 0.3 s pauses, segmented into 3 scenes (one per sentence), and a scene plan made the way the planner makes it from them: planned scene k runs from the start of
    canonical scene k (the first from 0) to the start of the next one (the last to the audio end), so it covers its scene and the pause after it. `bounds` replaces those boundaries.
    `step` = seconds per word: the default scenes are ~1.5 s, which Scene Segmentation rightly warns about (short scene); a step of 1.2 s gives scenes it accepts without a warning."""
    if step is None:
        _seg.three_sentences(d)
    else:
        a = _seg.sentence(["మన", "గుండె", "కొట్టుకుంటుంది."], 0.0, step)
        b = _seg.sentence(["అది", "రక్తాన్ని", "పంపిస్తుంది."], a[-1].end + 0.3, step)
        _seg.project(d, [a, b, _seg.sentence(["కానీ", "వ్యాయామం", "అవసరం."], b[-1].end + 0.3, step)])
    with patch.object(scene_segmentation, "SOFT_MIN", 1.0 if step is None else scene_segmentation.SOFT_MIN):      # scenes of ~1.5 s: a last scene this short would join the one before it (own tests), these tests need three scenes
        seg = scene_segmentation.run(d, ask=_seg.Ask(_seg.scenes_of([1], [2], [3])))
    duration = json.loads((d / "transcript.json").read_text(encoding="utf-8"))["duration"]
    b = bounds or [0.0, *[s["start_time"] for s in seg["scenes"][1:]], duration]
    scenes = [{"id": k, "start": b[k - 1], "end": b[k], "meaning": f"idea {k}", "concept": f"concept {k}", "mood": "calm", "mode": "image-composite", "pattern": "hero_text",
               "keywords": [], "params": {"text": f"Heart {k}"}} for k in range(1, len(b))]
    sp = {"style": {"suffix": "cinematic documentary", "palette": ["#0B1D26", "#2A9D8F", "#F2A541"]}, "scenes": scenes}
    pm = {"prompts": [{"n": k, "scene": k, "slot": f"s{k:02d}_0", "role": "main", "ratio": "16:9", "required": True, "bg": "full", "text": f"A heart, scene {k}"} for k in range(1, len(b))]}
    (d / "scene_plan.json").write_text(json.dumps(sp), encoding="utf-8")
    (d / "prompts_map.json").write_text(json.dumps(pm), encoding="utf-8")
    if info:
        (d / "project.json").write_text(json.dumps({"id": "t", "name": "t", "use_images": images}), encoding="utf-8")
    return seg, sp, pm


def codes(plan):
    return [n["code"] for s in plan["scenes"] for n in s["validation_notes"]]


def test_a_plan_that_follows_scene_segmentation_keeps_its_scenes_times_and_pauses(tmp_path):
    seg, sp, pm = seg_project(tmp_path)
    plan, problems = vp.assemble(tmp_path, sp, pm, None)
    assert problems == [] and plan["validation"]["errors"] == []
    assert plan["source_mapping"]["canonical_scenes"] == plan["source_mapping"]["planned_scenes"] == 3
    for s, c in zip(plan["scenes"], seg["scenes"]):                                                    # the canonical start and end, exactly, and the canonical narration
        assert (s["narration"]["start_seconds"], s["narration"]["end_seconds"]) == (c["start_time"], c["end_time"]) and s["narration"]["text"] == c["transcript"]
        assert s["source_mapping"]["source"] == "scene_segmentation" and s["source_mapping"]["segmentation_scene_id"] == c["scene_id"] and s["narration"]["timestamp_source"] == "scene_segmentation"
    gaps = [s["source_mapping"]["gap_after_seconds"] for s in plan["scenes"]]
    assert gaps[:2] == [0.3, 0.3] and gaps[2] is None                                                    # the pauses are kept, not closed
    assert plan["scenes"][1]["narration"]["start_seconds"] - plan["scenes"][0]["narration"]["end_seconds"] == pytest.approx(0.3)
    assert plan["validation"]["checks"]["by_rule"]["gaps_preserved"] == {"passed": 2, "total": 2}
    assert plan["stages"][7]["status"] in ("completed", "warning") and "3 planned scenes against 3 Scene Segmentation scenes" in plan["stages"][7]["detail"]


def test_nine_canonical_scenes_that_became_ten_planned_scenes_are_an_error_not_a_clean_pass(tmp_path):
    seg, sp, pm = seg_project(tmp_path)
    b = [0.0, seg["scenes"][1]["start_time"], 2.0, seg["scenes"][2]["start_time"], sp["scenes"][-1]["end"]]            # the planner split canonical scene 2 in two
    seg2, sp, pm = seg_project(tmp_path, bounds=b, info=False)
    assert len(sp["scenes"]) == 4 and len(seg2["scenes"]) == 3
    plan, problems = vp.assemble(tmp_path, sp, pm, None)
    assert plan["validation"]["status"] == "error" and problems
    assert any("Scene Segmentation has 3 scenes but the scene plan has 4" in m for m in plan["validation"]["errors"])
    assert plan["stages"][7]["status"] == "failed" and plan["source_mapping"]["canonical_scenes"] == 3 and plan["source_mapping"]["planned_scenes"] == 4
    assert vp.plan_mismatch(tmp_path)[0].startswith("Scene Segmentation has 3 scenes but the scene plan has 4")


def test_a_planned_start_that_differs_from_the_canonical_start_names_the_scene_and_the_seconds(tmp_path):
    seg, sp, pm = seg_project(tmp_path)
    b = [0.0, seg["scenes"][1]["start_time"] - 0.2, seg["scenes"][2]["start_time"], sp["scenes"][-1]["end"]]
    _, sp, pm = seg_project(tmp_path, bounds=b, info=False)
    plan, _ = vp.assemble(tmp_path, sp, pm, None)
    assert plan["validation"]["status"] == "error"
    assert any(f"the plan starts at {b[1]:g} s but Scene Segmentation scene_002 starts at {seg['scenes'][1]['start_time']:g} s" in m for m in plan["validation"]["errors"])


def test_a_planned_end_that_differs_from_the_canonical_end_is_an_error(tmp_path):
    seg, sp, pm = seg_project(tmp_path)
    early = [0.0, seg["scenes"][0]["end_time"] - 0.5, seg["scenes"][2]["start_time"], sp["scenes"][-1]["end"]]            # scene 1 ends before its own narration ends
    _, sp, pm = seg_project(tmp_path, bounds=early, info=False)
    plan, _ = vp.assemble(tmp_path, sp, pm, None)
    assert any("the plan ends at" in m and "scene_001" in m for m in plan["validation"]["errors"])
    late = [0.0, seg["scenes"][1]["start_time"], seg["scenes"][2]["start_time"], sp["scenes"][-1]["end"] + 5.0]            # the last scene runs past the audio
    _, sp, pm = seg_project(tmp_path, bounds=late, info=False)
    plan, _ = vp.assemble(tmp_path, sp, pm, None)
    assert any("scene_03: the plan ends at" in m for m in plan["validation"]["errors"])


def test_the_pause_between_scenes_may_not_be_closed_or_changed(tmp_path):
    seg, sp, pm = seg_project(tmp_path)
    plan, _ = vp.assemble(tmp_path, sp, pm, None)
    tampered = json.loads(json.dumps(plan))
    tampered["scenes"][1]["narration"]["start_seconds"] -= 0.3                                           # scene 2 stretched back over the pause
    iss = vp.Issues()
    vp._check(tampered, vp.context(tmp_path, sp, pm), iss, True)
    got = [i["code"] for i in iss.items if i["severity"] == "error"]
    assert "gap_changed" in got and "timing" in got


def test_two_planned_scenes_mapped_to_the_same_canonical_scene_are_an_error(tmp_path):
    seg, sp, pm = seg_project(tmp_path)
    plan, _ = vp.assemble(tmp_path, sp, pm, None)
    plan["scenes"][2]["source_mapping"]["segmentation_scene_id"] = plan["scenes"][1]["source_mapping"]["segmentation_scene_id"]
    iss = vp.Issues()
    vp._check(plan, vp.context(tmp_path, sp, pm), iss, True)
    assert "source_mapping_duplicate" in [i["code"] for i in iss.items]


def test_a_canonical_scene_without_a_planned_scene_is_reported(tmp_path):
    seg, sp, pm = seg_project(tmp_path)
    sp["scenes"].pop()
    pm["prompts"].pop()
    plan, _ = vp.assemble(tmp_path, sp, pm, None)
    assert any("has no planned scene" in m for m in plan["validation"]["errors"]) and plan["validation"]["status"] == "error"


def test_without_scene_segmentation_the_scene_plan_is_the_source_and_the_plan_says_so(tmp_path):
    d, sp, pm = project(tmp_path)
    plan, _ = vp.assemble(d, sp, pm, None)
    assert plan["source_mapping"]["canonical_scenes"] is None and "only source" in plan["source_mapping"]["policy"]
    assert all(s["source_mapping"]["source"] == "scene_plan" and s["source_mapping"]["segmentation_scene_id"] is None for s in plan["scenes"])
    assert vp.plan_mismatch(d) == [] and "no Scene Segmentation to map to" in plan["stages"][7]["detail"]


def test_a_stale_scene_segmentation_is_not_a_canonical_source(tmp_path):
    seg_project(tmp_path)
    tr = json.loads((tmp_path / "transcript.json").read_text(encoding="utf-8"))
    tr["segments"][0]["words"][0]["w"] = "changed"                                                        # the transcript changed after the segmentation was made
    (tmp_path / "transcript.json").write_text(json.dumps(tr, ensure_ascii=False), encoding="utf-8")
    assert scene_segmentation.load_fresh(tmp_path) is None and vp.plan_mismatch(tmp_path) == []


def test_the_scene_plan_checks_of_the_planner_use_the_same_rule(tmp_path):
    seg, sp, pm = seg_project(tmp_path)
    duration = json.loads((tmp_path / "transcript.json").read_text(encoding="utf-8"))["duration"]
    assert mapping_errors(ScenePlan.model_validate(sp).scenes, seg, duration) == []
    _, sp2, _ = seg_project(tmp_path, bounds=[0.0, 2.0, seg["scenes"][2]["start_time"], duration], info=False)
    assert [e["code"] for e in mapping_errors(ScenePlan.model_validate(sp2).scenes, seg, duration)] == ["source_start", "source_end"] or mapping_errors(ScenePlan.model_validate(sp2).scenes, seg, duration)


# ---------- beats: several visual moments inside ONE scene, never a split of the scene ----------
def beat(raw, i, start, end, bid="beat_1", ids=None):
    s = raw["scenes"][i]
    s["beats"] = [{"beat_id": bid, "start_seconds": start, "end_seconds": end, "description": "the reveal", "element_ids": ids if ids is not None else [s["elements"][0]["element_id"]]}]


def test_beats_inside_their_scene_are_kept_and_a_beat_outside_it_is_refused(tmp_path):
    seg, sp, pm = seg_project(tmp_path)
    c = seg["scenes"][1]
    plan, problems = vp.assemble(tmp_path, sp, pm, raw_for(sp, pm, images=False, mutate=lambda r: beat(r, 1, c["start_time"] + 0.1, c["end_time"] - 0.1)))
    assert problems == [] and plan["scenes"][1]["beats"][0]["beat_id"] == "beat_1" and len(plan["scenes"]) == 3
    plan, problems = vp.assemble(tmp_path, sp, pm, raw_for(sp, pm, images=False, mutate=lambda r: beat(r, 1, c["start_time"] + 0.1, c["end_time"] + 0.4)))
    assert any("is not inside its scene" in m for m in problems)                                          # refused: the planner may not stretch a scene over its pause


def test_beats_must_be_in_order_and_may_only_show_elements_of_their_scene(tmp_path):
    seg, sp, pm = seg_project(tmp_path)
    c = seg["scenes"][0]

    def two(r):
        r["scenes"][0]["beats"] = [{"beat_id": "b2", "start_seconds": c["start_time"] + 1.0, "end_seconds": c["end_time"], "description": "late", "element_ids": []},
                                   {"beat_id": "b1", "start_seconds": c["start_time"], "end_seconds": c["start_time"] + 1.0, "description": "early", "element_ids": []}]
    _, problems = vp.assemble(tmp_path, sp, pm, raw_for(sp, pm, images=False, mutate=two))
    assert any("beats are not in order" in m for m in problems)
    plan, problems = vp.assemble(tmp_path, sp, pm, raw_for(sp, pm, images=False, mutate=lambda r: beat(r, 0, c["start_time"], c["end_time"], ids=["ghost"])))
    assert problems == [] and plan["scenes"][0]["beats"][0]["element_ids"] == [] and "beat_element" in codes(plan)          # the unknown element leaves the beat, the scene is kept


def test_a_motion_hint_for_an_unknown_element_is_dropped_but_a_scene_level_hint_is_allowed(tmp_path):
    seg, sp, pm = seg_project(tmp_path)

    def hints(r):
        r["scenes"][0]["motion_hints"] = [{"element_id": "ghost", "intent": "show_flow_direction", "description": None}, {"element_id": None, "intent": "slow_push_in", "description": "whole scene"}]
    plan, problems = vp.assemble(tmp_path, sp, pm, raw_for(sp, pm, images=False, mutate=hints))
    assert problems == [] and [h["intent"] for h in plan["scenes"][0]["motion_hints"]] == ["slow_push_in"] and "motion_hint_element" in codes(plan)


def test_a_motion_only_plan_that_follows_scene_segmentation_needs_no_picture(tmp_path):
    seg, sp, pm = seg_project(tmp_path, images=False)
    plan, problems = vp.assemble(tmp_path, sp, pm, raw_for(sp, pm, images=False))
    assert problems == [] and plan["project"]["visual_mode"] == "motion_only" and all(not s["asset_requirements"] for s in plan["scenes"])
    assert all(e["type"] not in ("image", "video") for s in plan["scenes"] for e in s["elements"])


def test_a_valid_plan_still_hands_motion_planning_the_same_ids_and_scene_plan_stays_readable(tmp_path):
    seg, sp, pm = seg_project(tmp_path, images=False)
    vp.save(tmp_path, vp.assemble(tmp_path, sp, pm, raw_for(sp, pm, images=False))[0])
    handoff = vp.motion_handoff(tmp_path)
    assert [h["plan_scene_id"] for h in handoff] == [s["id"] for s in sp["scenes"]] and all(h["elements"] for h in handoff)
    assert ScenePlan.model_validate_json((tmp_path / "scene_plan.json").read_text(encoding="utf-8"))          # Motion Planning still reads the unchanged scene plan


# ---------- run and the planner ----------
def test_run_makes_no_claude_call_for_a_plan_that_does_not_follow_scene_segmentation_and_the_result_is_an_error(tmp_path):
    seg, sp, pm = seg_project(tmp_path)
    seg_project(tmp_path, bounds=[0.0, seg["scenes"][1]["start_time"], 2.0, seg["scenes"][2]["start_time"], sp["scenes"][-1]["end"]], info=False)
    called = []
    plan = vp.run(tmp_path, ask=lambda *a, **k: called.append(1) or "{}")
    assert called == [] and plan["validation"]["status"] == "error" and plan["llm"]["status"] == "not_run" and plan["llm"]["problems"]
    assert vp.load(tmp_path)["validation"]["status"] == "error"                                           # what is saved says so


def test_replacing_a_mismatching_plan_keeps_the_old_files_and_writes_the_new_ones(tmp_path):
    seg, sp, pm = seg_project(tmp_path)
    seg_project(tmp_path, bounds=[0.0, seg["scenes"][1]["start_time"], 2.0, seg["scenes"][2]["start_time"], sp["scenes"][-1]["end"]], info=False)
    old = (tmp_path / "scene_plan.json").read_bytes()
    new = tmp_path / "staged"
    new.mkdir()
    seg_project(tmp_path, info=False)                                                                      # the plan that follows the segmentation, staged
    for n in ("scene_plan.json", "prompts_map.json"):
        shutil.copyfile(tmp_path / n, new / n)
    for n in ("composition.json", "prompts.txt"):
        (new / n).write_text("{}", encoding="utf-8")
    vp.save(new, vp.assemble(tmp_path, json.loads((new / "scene_plan.json").read_text(encoding="utf-8")), json.loads((new / "prompts_map.json").read_text(encoding="utf-8")), None, plan_dir=new)[0])
    (tmp_path / "scene_plan.json").write_bytes(old)                                                       # back to the mismatching plan that is live
    autoplan._publish(tmp_path, new, replace=True)
    backups = list((tmp_path / "plan_backups").glob("*/scene_plan.json"))
    assert len(backups) == 1 and backups[0].read_bytes() == old                                           # the replaced plan is kept, never deleted
    assert len(json.loads((tmp_path / "scene_plan.json").read_text(encoding="utf-8"))["scenes"]) == 3 and vp.plan_mismatch(tmp_path) == []


def test_a_failed_new_plan_leaves_the_old_one_untouched_and_the_run_button_is_the_only_start(client, monkeypatch):
    pid = create(client).json()["id"]
    pdir = _m7.config.PROJECTS_DIR / pid
    seg, sp, pm = seg_project(pdir, info=False, step=1.2)                                                  # scenes Scene Segmentation accepts without a warning (warnings would block the stage)
    mid = (seg["scenes"][1]["start_time"] + seg["scenes"][2]["start_time"]) / 2
    seg_project(pdir, bounds=[0.0, seg["scenes"][1]["start_time"], mid, seg["scenes"][2]["start_time"], sp["scenes"][-1]["end"]], info=False, step=1.2)
    (pdir / "transcript_corrected.json").write_bytes((pdir / "transcript.json").read_bytes())             # Stage 2's verified transcript (Visual Planning requires it)
    old = {n: (pdir / n).read_bytes() for n in ("scene_plan.json", "prompts_map.json")}
    stage = lambda: next(s for s in client.get(f"/projects/{pid}/pipeline").json()["stages"] if s["id"] == "planning")
    assert stage()["status"] == "failed" and "Scene Segmentation has 3 scenes" in stage()["detail"]       # a mismatch is a failure, never "completed"; reading it starts nothing
    assert client.get(f"/projects/{pid}/visual-planning").json()["validation"]["status"] == "error"
    time.sleep(0.3)
    assert not (pdir / "plan_backups").exists()

    def down(*a, **k):
        raise promptgen.GenError("not signed in")
    monkeypatch.setattr(promptgen, "run_claude", down)
    assert client.post(f"/projects/{pid}/visual-planning/run").status_code == 202                          # the Run button makes the plan again ...
    assert settle(client, pid)["state"] == "failed"                                                        # ... Claude is not available: it failed
    assert {n: (pdir / n).read_bytes() for n in old} == old and not (pdir / "plan_backups").exists()       # the old plan is untouched until a new one has passed every check


# ---------- the handoff to Motion Planning (the real plan-only step), stale plans, the user's edits ----------
import shutil as _shutil  # noqa: E402

from backend import pipeline, visual_plan  # noqa: E402

needs_node = pytest.mark.skipif(_shutil.which("node") is None or _shutil.which("npx") is None, reason="the motion library needs node")


def motion_project(d):
    """A Motion-Only project that follows Scene Segmentation, with its visual plan saved (what the user has after Visual Planning)."""
    seg, sp, pm = seg_project(d, images=False)
    (d / "cuts.json").write_text(json.dumps({"cuts": []}), encoding="utf-8")
    plan, problems = vp.assemble(d, sp, pm, raw_for(sp, pm, images=False))
    assert problems == []
    vp.save(d, plan)
    return seg, sp, pm, plan


@needs_node
def test_motion_planning_runs_from_the_current_visual_plan_and_every_scene_reaches_it(tmp_path):
    seg, sp, pm, plan = motion_project(tmp_path)
    r = pipeline.execute(tmp_path, "motion-plan", pipeline.Ctx())                                        # the real plan-only step: the motion library, no render, no Claude
    assert r["status"] == "ran" and "from the Visual Plan (llm)" in r["msg"]
    m = json.loads((tmp_path / "motion_plan.json").read_text(encoding="utf-8"))
    h = m["visual_plan"]
    assert h["file"] == "visual_planning.json" and h["fingerprint"] == plan["source_fingerprint"] and h["validation"] in ("ok", "warning")
    assert [s["id"] for s in m["scenes"]] == [s["plan_scene_id"] for s in h["scenes"]] == [1, 2, 3]
    for ms, hs, c, ps in zip(m["scenes"], h["scenes"], seg["scenes"], sp["scenes"]):                     # the same intervals, and the canonical times and narration scene behind them
        assert (ms["start"], ms["end"]) == (hs["timeline_start"], hs["timeline_end"]) == (ps["start"], ps["end"])                 # Motion Planning holds the scene plus the pause (scene_plan.json)
        assert (hs["start"], hs["end"]) == (hs["plan_start"], hs["plan_end"]) == (c["start_time"], c["end_time"]) and hs["segmentation_scene_id"] == c["scene_id"]   # the plan's own times are canonical
        assert hs["elements"] and all({"element_id", "type", "role", "required"} == set(e) for e in hs["elements"])


@needs_node
def test_a_new_visual_plan_makes_the_motion_plan_stale_and_an_unchanged_one_does_not_run_again(tmp_path):
    seg, sp, pm, plan = motion_project(tmp_path)
    pipeline.execute(tmp_path, "motion-plan", pipeline.Ctx())
    assert pipeline.is_fresh(tmp_path, "motion-plan") and pipeline.execute(tmp_path, "motion-plan", pipeline.Ctx())["status"] == "fresh"
    again = json.loads(json.dumps(plan))
    again["scenes"][0]["visual_concept"]["description"] = "another idea"                                    # a new visual plan (another run)
    vp.save(tmp_path, again)
    assert not pipeline.is_fresh(tmp_path, "motion-plan")                                                  # the motion plan made for the old one is not shown as current


def test_motion_planning_refuses_a_visual_plan_that_is_out_of_date_or_does_not_follow_scene_segmentation(tmp_path):
    seg, sp, pm, plan = motion_project(tmp_path)
    assert vp.blockers(tmp_path) is None
    sp["scenes"][0]["meaning"] = "changed after the visual plan was made"
    (tmp_path / "scene_plan.json").write_text(json.dumps(sp), encoding="utf-8")
    assert "out of date" in vp.blockers(tmp_path)
    with pytest.raises(pipeline.StepError, match="Motion Planning waits for Visual Planning"):
        pipeline.execute(tmp_path, "motion-plan", pipeline.Ctx())
    assert not (tmp_path / "motion_plan.json").exists()                                                    # nothing was planned from a stale plan
    seg_project(tmp_path, bounds=[0.0, seg["scenes"][1]["start_time"], 2.0, seg["scenes"][2]["start_time"], sp["scenes"][-1]["end"]], info=False)
    assert "does not follow Scene Segmentation" in vp.blockers(tmp_path)


def test_a_visual_plan_with_blocking_errors_stops_motion_planning(tmp_path):
    seg, sp, pm, plan = motion_project(tmp_path)
    plan["validation"]["errors"] = ["scene_01 has no primary element"]
    vp.save(tmp_path, plan)
    assert "blocking error" in vp.blockers(tmp_path)


def test_a_project_without_a_stored_visual_plan_is_not_blocked_and_hands_over_the_derived_plan(tmp_path):
    seg_project(tmp_path, images=False)
    assert vp.blockers(tmp_path) is None
    h = vp.handoff(tmp_path)
    assert h["file"] is None and h["source"] == "derived_from_scene_plan" and len(h["scenes"]) == 3


def test_the_motion_run_route_refuses_a_visual_plan_that_is_not_current(client):
    pid = create(client).json()["id"]
    pdir = _m7.config.PROJECTS_DIR / pid
    seg, sp, pm, plan = motion_project(pdir)
    sp["scenes"][0]["meaning"] = "changed"
    (pdir / "scene_plan.json").write_text(json.dumps(sp), encoding="utf-8")
    r = client.post(f"/projects/{pid}/motion/run")
    assert r.status_code == 409 and r.json()["error"]["code"] == "visual_plan_not_current" and "out of date" in r.json()["error"]["message"]


def test_the_user_edits_of_a_scene_that_changed_are_kept_backed_up_and_not_written_into_the_new_scene(client):
    pid = create(client).json()["id"]
    pdir = _m7.install_plan(pid)
    data = visual_plan.ensure(pdir, pid)
    scene = data["scenes"][0]
    scene["meta"].update(edited=True, edited_paths=["shots / 0 / text / 0 / content"])
    scene["shots"][0]["text"] = [{"content": "EDITED BY THE USER", "mark": "x", "position": None, "font_style": "big", "start": 1.0}]
    (pdir / "visual_plan.json").write_text(json.dumps(data), encoding="utf-8")
    comp = json.loads((pdir / "composition.json").read_text(encoding="utf-8"))
    texts = lambda c: [layer.get("text") for layer in c["scenes"][0]["layers"] if layer["type"] == "text"]
    fresh = json.loads(json.dumps(comp))
    assert visual_plan.apply_edits(pdir, fresh) >= 1 and "EDITED BY THE USER" in texts(fresh)             # the control: while the analysis is the same, the edit is written
    sp = json.loads((pdir / "scene_plan.json").read_text(encoding="utf-8"))
    sp["scenes"][0]["meaning"] = "the analysis of this scene moved on"                                      # the scene was planned again
    (pdir / "scene_plan.json").write_text(json.dumps(sp), encoding="utf-8")
    stale = json.loads(json.dumps(comp))
    assert visual_plan.apply_edits(pdir, stale) == 0 and stale["scenes"][0] == comp["scenes"][0]            # not written into a scene that is not the one the user edited
    kept = json.loads((pdir / "visual_plan.json").read_text(encoding="utf-8"))["scenes"][0]
    assert kept["meta"]["edited"] and kept["shots"][0]["text"][0]["content"] == "EDITED BY THE USER"        # their work is still in the file ...
    assert kept["approval"]["status"] == "needs_edit" and kept["approval"]["reason"] == visual_plan.STALE_REASON   # ... marked for their attention
    backups = list((pdir / "plan_backups").glob("*/visual_plan.json"))
    assert backups and "EDITED BY THE USER" in backups[0].read_text(encoding="utf-8")                      # and copied before the file was brought in line


def test_replacing_the_scene_plan_also_keeps_the_users_edits_file(tmp_path):
    seg_project(tmp_path)
    (tmp_path / "visual_plan.json").write_text('{"scenes": [{"number": 1, "meta": {"edited": true}}]}', encoding="utf-8")
    new = tmp_path / "staged"
    new.mkdir()
    for n in ("scene_plan.json", "prompts_map.json"):
        shutil.copyfile(tmp_path / n, new / n)
    for n in ("composition.json", "prompts.txt", "visual_planning.json"):
        (new / n).write_text("{}", encoding="utf-8")
    autoplan._publish(tmp_path, new, replace=True)
    assert [b.read_text(encoding="utf-8") for b in (tmp_path / "plan_backups").glob("*/visual_plan.json")] == ['{"scenes": [{"number": 1, "meta": {"edited": true}}]}']
    assert (tmp_path / "visual_plan.json").exists()                                                         # the live file is untouched (only backed up)


# ---------- Motion-Only conversions agree with the output ----------
def test_a_picture_that_is_converted_in_motion_only_says_so_in_the_element_and_in_one_note_per_scene(tmp_path):
    seg, sp, pm = seg_project(tmp_path, images=False)
    plan, problems = vp.assemble(tmp_path, sp, pm, raw_for(sp, pm, images=True))                           # a planner that kept the pictures of the old workflow
    assert problems == []
    for s in plan["scenes"]:
        notes = [n for n in s["validation_notes"] if n["code"] == "mode_image_element"]
        assert len(notes) == 1 and "Motion-Only" in notes[0]["message"] and s["asset_requirements"] == []      # one note per scene
        pics = [e for e in s["elements"] if e["element_id"].startswith("image_")]
        assert pics and all(e["type"] == "graphic" and any("flat graphic, no photo" in c for c in e["constraints"]) for e in pics)
        assert all(e["registry_requirements"] and e["registry_requirements"]["search_descriptors"] for e in pics)
    assert not [e for s in plan["scenes"] for e in s["elements"] if e["type"] in ("image", "video")] and plan["validation"]["status"] == "warning"
    assert len(plan["validation"]["warnings"]) == 3                                                         # the warnings are exactly those conversions, nothing else


def test_a_motion_only_plan_that_never_used_pictures_has_no_conversion_warning(tmp_path):
    seg, sp, pm = seg_project(tmp_path, images=False)
    plan, _ = vp.assemble(tmp_path, sp, pm, raw_for(sp, pm, images=False))
    assert not [w for w in plan["validation"]["warnings"] if "Motion-Only" in w] and "mode_image_element" not in codes(plan)          # (the repeated-concept warnings of this tiny fixture are unrelated)


def test_every_run_keeps_the_previous_visual_plan(tmp_path):
    d, sp, pm = project(tmp_path)
    ask = lambda *a, **k: json.dumps({"visual_plan": raw_for(sp, pm)})
    vp.run(d, ask=ask)
    first = (d / "visual_planning.json").read_bytes()
    vp.run(d, ask=ask)
    backups = list((d / "plan_backups").glob("*/visual_planning.json"))
    assert len(backups) == 1 and backups[0].read_bytes() == first                                           # the plan that was replaced is kept


# ---------- canonical times, pauses, layout regions, the safe area, paths and the concept (rules checked against the source fixtures, never against one audio) ----------
def base_plan(d, mutate=None):
    seg, sp, pm = seg_project(d, images=False)
    plan, problems = vp.assemble(d, sp, pm, raw_for(sp, pm, images=False, mutate=mutate))
    assert problems == []
    return seg, sp, pm, plan


def recheck(d, sp, pm, plan, mutate=None):
    """The stage-8 rules run again over a plan that was changed after it was assembled: the issues they find."""
    plan = json.loads(json.dumps(plan))
    if mutate:
        mutate(plan)
    iss = vp.Issues()
    vp._check(plan, vp.context(d, sp, pm), iss, True)
    return iss


def found(iss, code, severity=None):
    return [i for i in iss.items if i["code"] == code and (severity is None or i["severity"] == severity)]


def test_plan_end_is_the_canonical_end_and_the_pause_after_it_is_stored_apart(tmp_path):
    seg, sp, pm, plan = base_plan(tmp_path)
    scenes = plan["scenes"]
    for k, (s, c) in enumerate(zip(scenes, seg["scenes"])):
        m = s["source_mapping"]
        assert (m["plan_start"], m["plan_end"]) == (c["start_time"], c["end_time"]) == (s["narration"]["start_seconds"], s["narration"]["end_seconds"])      # the scene never includes the pause
        nxt = seg["scenes"][k + 1]["start_time"] if k + 1 < len(seg["scenes"]) else None
        assert m["gap_after_seconds"] == (None if nxt is None else round(nxt - c["end_time"], 3))                                   # the pause, from the canonical previous end and next start
        assert (m["timeline_end"] == nxt) if nxt is not None else m["timeline_end"] >= m["plan_end"]                               # the timeline holds the scene until the next one starts
        if nxt is not None:
            assert m["timeline_end"] - m["plan_end"] == pytest.approx(m["gap_after_seconds"])
    assert all(a["source_mapping"]["timeline_end"] <= b["source_mapping"]["timeline_start"] + vp.EPS for a, b in zip(scenes, scenes[1:]))      # no overlap on the timeline
    assert all(a["source_mapping"]["plan_end"] <= b["source_mapping"]["plan_start"] for a, b in zip(scenes, scenes[1:]))                        # nor between the scenes themselves
    assert any(s["source_mapping"]["gap_after_seconds"] for s in scenes) and not found(recheck(tmp_path, sp, pm, plan), "plan_interval")


def test_a_scene_end_that_swallows_the_pause_a_wrong_gap_or_a_timeline_overlap_is_a_critical_error(tmp_path):
    seg, sp, pm, plan = base_plan(tmp_path)
    gap = plan["scenes"][0]["source_mapping"]["gap_after_seconds"]
    swallowed = recheck(tmp_path, sp, pm, plan, lambda p: p["scenes"][0]["source_mapping"].update(plan_end=p["scenes"][0]["source_mapping"]["plan_end"] + gap))
    assert found(swallowed, "plan_interval", "error") and "pause" in found(swallowed, "plan_interval")[0]["message"]
    wrong = recheck(tmp_path, sp, pm, plan, lambda p: p["scenes"][0]["source_mapping"].update(gap_after_seconds=gap + 0.2))
    assert found(wrong, "gap_after_seconds", "error")
    last = recheck(tmp_path, sp, pm, plan, lambda p: p["scenes"][-1]["source_mapping"].update(gap_after_seconds=0.3))
    assert found(last, "gap_after_seconds", "error")                                                           # the last scene has no pause after it
    overlap = recheck(tmp_path, sp, pm, plan, lambda p: p["scenes"][1]["source_mapping"].update(timeline_start=p["scenes"][0]["source_mapping"]["timeline_end"] - 0.5))
    assert found(overlap, "timeline_overlap", "error")
    short = recheck(tmp_path, sp, pm, plan, lambda p: p["scenes"][0]["source_mapping"].update(timeline_end=p["scenes"][0]["source_mapping"]["plan_end"]))
    assert found(short, "timeline_interval", "error")                                                          # the pause must be held on the timeline until the next scene
    for iss in (swallowed, wrong, overlap, short):                                                             # a critical timing failure is never a successful validation, and the last stage shows it
        assert vp._stages(plan, iss, True)[7]["status"] == "failed"


def test_the_hand_over_to_motion_planning_carries_both_the_canonical_and_the_timeline_interval(tmp_path):
    seg, sp, pm, plan = base_plan(tmp_path)
    vp.save(tmp_path, plan)
    for h, ps, c in zip(vp.motion_handoff(tmp_path), sp["scenes"], seg["scenes"]):
        assert (h["plan_start"], h["plan_end"]) == (c["start_time"], c["end_time"]) and (h["timeline_start"], h["timeline_end"]) == (ps["start"], ps["end"])
    h = vp.handoff(tmp_path)
    assert vp.link_errors([{"id": s["id"], "start": s["start"], "end": s["end"]} for s in sp["scenes"]], h) == []
    assert vp.link_errors([{"id": 1, "start": 0.0, "end": h["scenes"][0]["plan_end"]}, *[{"id": s["id"], "start": s["start"], "end": s["end"]} for s in sp["scenes"][1:]]], h)   # a scene cut at its narration end is not the scene Motion Planning holds


def region_of(scene, eid):
    return next(e for e in scene["elements"] if e["element_id"] == eid)["placement"]["region"]


def clashes_of(scene, aspect="16:9"):
    return vp.clashes(scene["elements"], scene["element_relationships"], aspect)


def test_an_unsupported_or_placeholder_region_is_replaced_by_a_supported_one_and_the_change_is_recorded(tmp_path):
    def bad(raw):
        raw["scenes"][0]["elements"].append(vp._el("bars_compare", "graphic", "explanatory", "two bars", region="below_center_placeholder", prio=2))
    seg, sp, pm, plan = base_plan(tmp_path, bad)
    s = plan["scenes"][0]
    now = region_of(s, "bars_compare")
    assert now in vp.REGION_BOX and not vp.PLACEHOLDER.search(now) and now != "below_center_placeholder"
    assert [n for n in s["validation_notes"] if n["code"] == "region_replaced" and "below_center_placeholder" in n["message"] and now in n["message"]]
    assert all(e["placement"]["region"] in vp.REGION_BOX and not vp.PLACEHOLDER.search(json.dumps(e["placement"])) for p in plan["scenes"] for e in p["elements"])
    assert plan["validation"]["status"] == "warning" and "region_unknown" not in codes(plan)                  # recorded, never silent, never kept
    assert not clashes_of(s)                                                                                   # the replacement does not land on another element


def test_a_region_that_is_not_supported_or_a_placeholder_left_in_a_plan_is_an_error(tmp_path):
    seg, sp, pm, plan = base_plan(tmp_path)
    iss = recheck(tmp_path, sp, pm, plan, lambda p: p["scenes"][0]["elements"][0]["placement"].update(region="below_center_placeholder"))
    assert found(iss, "region_unknown", "error") and found(iss, "placeholder", "error")
    iss = recheck(tmp_path, sp, pm, plan, lambda p: p["scenes"][0]["elements"][0].update(visual_description="TBD"))
    assert found(iss, "placeholder", "error")


def test_the_safe_area_policy_is_one_for_the_whole_plan_and_every_text_sits_inside_it_clear_of_the_primary_visual(tmp_path):
    def contrary(raw):
        raw["visual_style"]["safe_area_policy"] = "keep the lower safe area free"
    seg, sp, pm, plan = base_plan(tmp_path, contrary)
    assert plan["visual_style"]["safe_area_policy"] == vp.SAFE_AREA_POLICY and "caption band" in vp.SAFE_AREA_POLICY
    m = vp.config.SAFE_AREA["margin"]
    ui = 1 - vp.config.SAFE_AREA["portrait_ui_bottom"]
    for aspect in ("16:9", "9:16"):
        for name in vp.REGIONS:
            b = vp.region_box(name, aspect)
            assert name == "full_frame" or b is None or (b[0] >= m - 1e-9 and b[1] >= m - 1e-9 and b[2] <= 1 - m + 1e-9 and b[3] <= 1 - m + 1e-9 and b[0] < b[2] and b[1] < b[3]), (name, aspect, b)
            assert aspect == "16:9" or name == "full_frame" or b is None or b[3] <= ui + 1e-9                  # nothing behind the phone controls in 9:16
    for s in plan["scenes"]:
        assert not [1 for a, b in clashes_of(s) if (a["type"] in vp.TEXT_TYPES) != (b["type"] in vp.TEXT_TYPES) and "primary" in (a["role"], b["role"])]
    assert [e["placement"]["region"] for e in plan["scenes"][0]["elements"] if e["type"] in vp.TEXT_TYPES] == ["lower_safe_area"]


def test_a_text_over_the_primary_visual_two_texts_in_one_band_or_a_text_over_the_whole_frame_are_reported(tmp_path):
    seg, sp, pm, plan = base_plan(tmp_path)
    text = lambda p: next(e for e in p["scenes"][0]["elements"] if e["type"] in vp.TEXT_TYPES)
    over = recheck(tmp_path, sp, pm, plan, lambda p: text(p).update(placement={"region": "center", "priority": 3, "avoid_overlap": True}))
    assert found(over, "text_over_primary", "warning") and found(over, "layout_overlap")
    two = recheck(tmp_path, sp, pm, plan, lambda p: p["scenes"][0]["elements"].append(vp._el("t2", "label", "explanatory", "x", content="Heart", language="en", region="lower_safe_area", prio=5)))
    assert found(two, "layout_overlap")
    full = recheck(tmp_path, sp, pm, plan, lambda p: text(p).update(placement={"region": "full_frame", "priority": 3, "avoid_overlap": True}))
    assert found(full, "text_outside_safe_area")
    assert not [i for i in recheck(tmp_path, sp, pm, plan).items if i["code"] != "repeated_concept"]             # the control: the unchanged plan has none of these (the fixture scenes share one concept)


def test_every_reference_of_a_relationship_hint_or_beat_names_an_element_of_the_scene(tmp_path):
    seg, sp, pm, plan = base_plan(tmp_path)
    ids = lambda s: {e["element_id"] for e in s["elements"]}
    for s in plan["scenes"]:
        assert all(r["source"] in ids(s) and r["target"] in ids(s) for r in s["element_relationships"])
        assert all(h["element_id"] is None or h["element_id"] in ids(s) for h in s["motion_hints"])            # a scene-level hint (no element) is the only exception the schema allows
    first = plan["scenes"][0]["elements"][0]["element_id"]
    scene_level = recheck(tmp_path, sp, pm, plan, lambda p: p["scenes"][0]["motion_hints"].append({"element_id": None, "intent": "slow_push", "description": None}))
    assert not found(scene_level, "reference_invalid")
    assert found(recheck(tmp_path, sp, pm, plan, lambda p: p["scenes"][0]["motion_hints"].append({"element_id": "ghost", "intent": "slow_push", "description": None})), "reference_invalid", "error")
    assert found(recheck(tmp_path, sp, pm, plan, lambda p: p["scenes"][0]["element_relationships"].append({"source": "ghost", "target": first, "relation": "labels", "description": None})), "reference_invalid", "error")


def travel(extra, rels):
    """A scene with two places, something that travels between them, and the given extra elements and relationships."""
    def mutate(raw):
        s = raw["scenes"][0]
        s["elements"] = [vp._el("place_a", "graphic", "supporting", "start", region="left", prio=2), vp._el("place_b", "graphic", "supporting", "goal", region="right", prio=2),
                         vp._el("ship", "icon", "primary", "the ship", region="path_across_frame", prio=1, registry={"icon": None, "category": None, "search_descriptors": ["rocket"], "resolved": None}), *extra]
        s["element_relationships"], s["motion_hints"], s["asset_requirements"] = rels, [], []
        s["visual_concept"]["primary_focus"] = "ship"
    return mutate


def test_a_journey_needs_a_drawn_path_that_joins_its_places_and_something_that_follows_it(tmp_path):
    path = vp._el("route", "graphic", "explanatory", "dotted route", region="path_across_frame", prio=2)
    ok = [{"source": "route", "target": "place_a", "relation": "connects_to", "description": None}, {"source": "route", "target": "place_b", "relation": "connects_to", "description": None},
          {"source": "ship", "target": "route", "relation": "follows", "description": None}]
    seg, sp, pm, plan = base_plan(tmp_path, travel([path], ok))
    assert not [c for c in codes(plan) if c in ("moving_without_path", "path_not_connected", "mover_not_on_path", "layout_overlap")] and plan["validation"]["errors"] == []
    assert "moving_without_path" in codes(base_plan(tmp_path, travel([], []))[3])                              # an icon that "travels" with no path of its own
    assert "path_not_connected" in codes(base_plan(tmp_path, travel([path], ok[:1] + ok[2:]))[3])              # a path that joins only one place
    assert "mover_not_on_path" in codes(base_plan(tmp_path, travel([path], ok[:2]))[3])                        # the traveller is not related to the path


def test_a_graphic_in_the_path_region_that_joins_nothing_is_moved_out_of_it(tmp_path):
    """The planner put a row of cards in the path region: nothing travels along it and it joins no place, so it is a misplaced graphic (moved, noted), not a path with a warning."""
    cards = vp._el("worker_cards", "graphic", "primary", "row of person cards", region="path_across_frame", prio=1)

    def mutate(raw):
        s = raw["scenes"][0]
        s["elements"], s["element_relationships"], s["motion_hints"], s["asset_requirements"] = [cards], [], [], []
        s["visual_concept"]["primary_focus"] = "worker_cards"
    seg, sp, pm, plan = base_plan(tmp_path, mutate)
    s = plan["scenes"][0]
    assert "path_not_connected" not in codes(plan)
    assert [e["placement"]["region"] for e in s["elements"]] != ["path_across_frame"]
    assert [n for n in s["validation_notes"] if n["code"] == "path_region_replaced" and n["severity"] == "info"]


def test_a_progression_through_three_stops_is_one_scene_with_its_stops_a_path_and_beats_on_spoken_words(tmp_path):
    from backend.transcribe import load_transcript
    seg, sp, pm = seg_project(tmp_path, images=False)
    words = [w for s in load_transcript(tmp_path).segments for w in s.words]
    sc = seg["scenes"][0]
    inside = [w for w in words if sc["start_time"] - vp.EPS <= (w.start + w.end) / 2 <= sc["end_time"] + vp.EPS]
    assert len(inside) >= 3
    mid = len(inside) // 2

    def stops(raw):
        s = raw["scenes"][0]
        s["elements"] = [vp._el("start", "graphic", "supporting", "start", region="left", prio=2), vp._el("stop_1", "graphic", "supporting", "first stop", region="center", prio=2),
                         vp._el("goal", "graphic", "supporting", "goal", region="right", prio=2), vp._el("route", "graphic", "explanatory", "path", region="path_across_frame", prio=2),
                         vp._el("ship", "icon", "primary", "ship", region="path_across_frame", prio=1, registry={"icon": None, "category": None, "search_descriptors": ["rocket"], "resolved": None})]
        s["element_relationships"] = [{"source": "route", "target": t, "relation": "connects_to", "description": None} for t in ("start", "stop_1", "goal")] \
            + [{"source": "ship", "target": "route", "relation": "follows", "description": None}]
        s["beats"] = [{"beat_id": "b1", "start_seconds": inside[0].start, "end_seconds": inside[mid - 1].end, "description": "start to the first stop", "element_ids": ["start", "stop_1", "ship"]},
                      {"beat_id": "b2", "start_seconds": inside[mid].start, "end_seconds": inside[-1].end, "description": "first stop to the goal", "element_ids": ["stop_1", "goal", "ship"]}]
        s["motion_hints"], s["asset_requirements"] = [{"element_id": "ship", "intent": "show_flow_direction", "description": None}], []
        s["visual_concept"]["primary_focus"] = "ship"
    seg, sp, pm, plan = base_plan(tmp_path, stops)
    s = plan["scenes"][0]
    assert len(plan["scenes"]) == len(seg["scenes"]) and len(s["beats"]) == 2                                   # the scene is not split: its moments are beats
    assert all(s["narration"]["start_seconds"] <= b["start_seconds"] < b["end_seconds"] <= s["narration"]["end_seconds"] for b in s["beats"])
    assert not [c for c in codes(plan) if c in ("beat_off_word", "path_not_connected", "moving_without_path", "layout_overlap", "reference_invalid")]
    mid_word = recheck(tmp_path, sp, pm, plan, lambda p: p["scenes"][0]["beats"][0].update(end_seconds=(inside[0].start + inside[0].end) / 2))
    assert found(mid_word, "beat_off_word", "warning")                                                         # a moment that ends in the middle of a word is reported
    outside = recheck(tmp_path, sp, pm, plan, lambda p: p["scenes"][0]["beats"][1].update(end_seconds=sc["end_time"] + 1))
    assert found(outside, "beat_outside_scene", "error")


def test_one_figure_in_the_concept_means_one_figure_element_not_a_lone_one_plus_a_group(tmp_path):
    def figures(n):
        def mutate(raw):
            s = raw["scenes"][0]
            s["visual_concept"].update(description="A lone small figure on a vast empty plain", primary_focus="lone_figure")
            s["elements"] = [vp._el("lone_figure", "graphic", "primary", "a tiny human figure", region="center", prio=1),
                             *[vp._el(f"extra_{i}", "icon", "supporting", "a group of figures", region="lower_right", prio=2) for i in range(n)]]
            s["element_relationships"], s["motion_hints"], s["asset_requirements"] = [], [], []
        return mutate
    assert "concept_elements_disagree" not in codes(base_plan(tmp_path, figures(0))[3])
    assert "concept_elements_disagree" in codes(base_plan(tmp_path, figures(1))[3])


def test_motion_only_plans_never_ask_for_pictures_whatever_the_planner_wrote(tmp_path):
    seg, sp, pm, plan = base_plan(tmp_path, lambda raw: raw["scenes"][0]["elements"].append(vp._el("photo", "image", "supporting", "a photo", region="lower_left", prio=3)))
    assert plan["project"]["visual_mode"] == "motion_only" and plan["validation"]["errors"] == []
    assert not [e for s in plan["scenes"] for e in s["elements"] if e["type"] in ("image", "video")] and all(s["asset_requirements"] == [] for s in plan["scenes"])
    assert plan["validation"]["checks"]["by_rule"]["no_pictures"]["passed"] == plan["validation"]["checks"]["by_rule"]["no_pictures"]["total"] > 0


def test_the_instructions_to_claude_carry_the_regions_the_policy_the_path_and_the_one_picture_rules():
    text = vp.spec(False)
    assert vp.SAFE_AREA_POLICY in text and all(r in text for r in vp.REGIONS) and "path_across_frame" in text and "never imply exact distances" in text and "SAME composition" in text
    assert "Do not write safe_area_policy" in text


def test_a_beat_that_is_not_on_spoken_words_is_moved_to_the_nearest_word_boundary_and_one_outside_its_scene_is_not_hidden(tmp_path):
    from backend.transcribe import load_transcript
    seg, sp, pm = seg_project(tmp_path, images=False)
    words = [w for s in load_transcript(tmp_path).segments for w in s.words]
    sc = seg["scenes"][0]
    inside = [w for w in words if sc["start_time"] - vp.EPS <= (w.start + w.end) / 2 <= sc["end_time"] + vp.EPS]

    def beats(raw):
        ids = [e["element_id"] for e in raw["scenes"][0]["elements"]]
        raw["scenes"][0]["beats"] = [{"beat_id": "b1", "start_seconds": sc["start_time"], "end_seconds": (inside[0].start + inside[0].end) / 2 + 0.01, "description": "first", "element_ids": ids[:1]},
                                     {"beat_id": "b2", "start_seconds": inside[1].start + 0.2, "end_seconds": sc["end_time"], "description": "second", "element_ids": ids[:1]}]
    plan, problems = vp.assemble(tmp_path, sp, pm, raw_for(sp, pm, images=False, mutate=beats))
    assert problems == []
    got = plan["scenes"][0]["beats"]
    assert got[0]["end_seconds"] in {w.end for w in inside} and got[1]["start_seconds"] == inside[1].start                 # on spoken words now
    assert "beat_snapped" in codes(plan) and "beat_off_word" not in codes(plan)
    assert [n["severity"] for n in plan["scenes"][0]["validation_notes"] if n["code"] == "beat_snapped"] == ["info", "info"]        # recorded, not a warning

    def outside(raw):
        beats(raw)
        raw["scenes"][0]["beats"][1]["end_seconds"] = sc["end_time"] + 1
    plan, problems = vp.assemble(tmp_path, sp, pm, raw_for(sp, pm, images=False, mutate=outside))
    assert plan["scenes"][0]["beats"][1]["end_seconds"] == sc["end_time"] + 1 and problems and plan["validation"]["status"] == "error"   # not pulled inside to look valid
