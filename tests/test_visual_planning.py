"""Visual Planning (VIDEO_ENGINE/stages/visual_planning.py): the media-mix design. The planner CLI is a fake; no network. Run: python -m pytest tests/test_visual_planning.py -q
The contract of visual_planning.json 2.0, the repairs and checks, the media mix against the shares chosen at upload, the planner call (one repair retry, nothing derived), the stored plan and its
hand-overs. The registry contract itself is in tests/test_media_kinds.py."""
import importlib
import json
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from SYSTEM.core import media_kinds as mk
from VIDEO_ENGINE.stages import promptgen, review, scene_segmentation
from VIDEO_ENGINE.stages import visual_planning as vp

FIXTURE = Path(__file__).parent / "fixtures" / "plan_sample"
REPS = ("object_in_context", "process_diagram", "comparison", "timeline", "chart", "map", "typography", "abstract_graphic")
REAL = {1: "image", 3: "image", 6: "image", 7: "video"}                 # ~28% images + ~9% video of the fixture's 70 s


def project(tmp_path, media=None, aspect=None):
    for f in FIXTURE.iterdir():
        if f.is_file():
            shutil.copyfile(f, tmp_path / f.name)
    info = {"id": "t", "name": "t", **({"aspect": aspect} if aspect else {}), **({"media": mk.normalise(media)} if media is not None else {})}
    (tmp_path / "project.json").write_text(json.dumps(info), encoding="utf-8")
    return tmp_path, json.loads((tmp_path / "scene_plan.json").read_text(encoding="utf-8"))


def raw_for(sp, real=None, mutate=None, ai_prompt=False):
    """What a good planner answer looks like: a drawn (or real, for the scenes in `real` = {scene id: image | video}) primary element and one headline from the scene's own words; then changed by
    `mutate` to break exactly one rule."""
    real = real or {}
    scenes = []
    for k, s in enumerate(sp["scenes"], 1):
        text = s["params"].get("text") or (s["keywords"][0]["text"] if s["keywords"] else " ".join(s["meaning"].split()[:3]))
        place = lambda region, prio: {"region": region, "priority": prio, "avoid_overlap": True}
        if s["id"] in real:
            media = {"query": "office workers at desks", "alt_queries": ["open plan office", "people at computers"], "why": "shows the workplace the narration talks about", "fallback": "a flat illustration of desks and chairs"}
            if ai_prompt and real[s["id"]] == "image":
                media["ai_prompt"] = "office workers at their desks, soft light, wide angle, documentary style"
            hero = {"element_id": f"{real[s['id']]}_main", "type": real[s["id"]], "role": "primary", "required": True, "visual_description": "office workers at their desks", "placement": place("full_frame", 1),
                    "depth_layer": "background", "media": media}
        else:
            hero = {"element_id": "gfx_main", "type": "graphic", "role": "primary", "required": True, "visual_description": f"a drawn picture of idea {k}", "placement": place("center", 1)}
        els = [hero, {"element_id": "text_main", "type": "text", "role": "supporting", "required": True, "visual_description": "the headline", "content": text, "language": "en",
                      "text_purpose": "title", "placement": place("lower_safe_area", 2)}]
        if s["params"].get("icon"):
            els.append({"element_id": "icon_main", "type": "icon", "role": "supporting", "required": False, "visual_description": "a pictogram", "placement": place("upper_right", 3),
                        "registry_requirements": {"icon": s["params"]["icon"], "category": None, "search_descriptors": []}})
        scenes.append({"plan_scene_id": s["id"], "scene_objective": {"core_meaning": s["meaning"], "audience_takeaway": "the idea", "narrative_role": "explanation"},
                       "visual_concept": {"description": f"idea {k}", "representation": REPS[k % len(REPS)], "primary_focus": f"focus {k}"}, "elements": els,
                       "element_relationships": [], "motion_hints": []})
    raw = {"visual_style": {"category": "documentary", "tone": "curious", "density": "medium"}, "scenes": scenes}
    if mutate:
        mutate(raw)
    return raw


def scene(plan, i=0):
    return plan["scenes"][i]


def codes(plan):
    return [n["code"] for s in plan["scenes"] for n in s["validation_notes"]]


# ---------- contract, stages, exact narration ----------
def test_a_valid_planner_answer_becomes_the_visual_plan_with_every_field_of_the_contract(tmp_path):
    d, sp = project(tmp_path)
    plan, problems = vp.assemble(d, sp, raw_for(sp, REAL))
    assert problems == [] and plan["source"] == "llm" and plan["llm"]["status"] == "applied" and plan["validation"]["errors"] == [] and plan["validation"]["warnings"] == []
    assert plan["schema_version"] == "2.0" and {"project", "visual_style", "scenes", "stages", "validation", "llm", "needs_review", "media_mix", "totals"} <= set(plan)
    assert plan["project"] == {"visual_mode": "motion_graphics", "aspect_ratio": "16:9", "width": 1920, "height": 1080, "fps": 30, "media": mk.DEFAULT_MEDIA}
    s = scene(plan)
    assert {"scene_id", "source_segment_ids", "narration", "scene_objective", "visual_concept", "hero", "counts", "elements", "element_relationships", "media_requirements", "motion_hints",
            "continuity", "validation_notes"} <= set(s) and "asset_requirements" not in s
    assert s["scene_id"] == "scene_01" and s["plan_scene_id"] == 1 and s["hero"] == "image"
    assert {"element_id", "type", "role", "required", "visual_description", "placement", "media"} <= set(s["elements"][0])
    assert plan["validation"]["checks"]["passed"] == plan["validation"]["checks"]["total"] > 0                  # no probability: the checks that passed


def test_the_eight_stages_are_reported_and_stage_five_is_the_media_mix(tmp_path):
    d, sp = project(tmp_path)
    plan, _ = vp.assemble(d, sp, raw_for(sp, REAL))
    assert [x["name"] for x in plan["stages"]] == list(vp.STAGES) and len(plan["stages"]) == 8 and plan["stages"][4]["name"] == "Media Mix"
    assert [x["status"] for x in plan["stages"]] == ["completed"] * 8 and "4 real picture(s) or clip(s)" in plan["stages"][4]["detail"]


def test_narration_and_times_are_copied_from_the_source_and_the_planner_cannot_change_them(tmp_path):
    d, sp = project(tmp_path)
    tr = json.loads((tmp_path / "transcript.json").read_text(encoding="utf-8"))
    plan, _ = vp.assemble(d, sp, raw_for(sp))
    for s, ps in zip(plan["scenes"], sp["scenes"]):
        assert (s["narration"]["start_seconds"], s["narration"]["end_seconds"]) == (ps["start"], ps["end"])
    words = [w["w"] for seg in tr["segments"] for w in seg["words"] if sp["scenes"][0]["start"] <= (w["start"] + w["end"]) / 2 <= sp["scenes"][0]["end"]]
    assert scene(plan)["narration"]["text"] == " ".join(words)                                       # exact source words, never rewritten
    plan2, problems = vp.assemble(d, sp, raw_for(sp, mutate=lambda r: r["scenes"][0].update(narration={"text": "rewritten", "start_seconds": 99})))
    assert problems and any("narration" in m for m in problems) and plan2 == {}                      # extra keys are rejected: the planner owns no narration or time


def test_a_scene_with_no_transcript_words_gets_no_invented_narration_or_times(tmp_path):
    d, sp = project(tmp_path)
    tr = json.loads((tmp_path / "transcript.json").read_text(encoding="utf-8"))
    for seg in tr["segments"]:
        seg["words"] = []
    (tmp_path / "transcript.json").write_text(json.dumps(tr), encoding="utf-8")
    plan, _ = vp.assemble(d, sp, raw_for(sp))
    n = scene(plan)["narration"]
    assert n["text"] == "" and n["timestamp_source"] in ("scene_plan", "audio_analysis") and (n["start_seconds"], n["end_seconds"]) == (sp["scenes"][0]["start"], sp["scenes"][0]["end"])
    assert any("no narration" in w for w in plan["validation"]["warnings"])                           # said, not hidden


def test_telugu_narration_is_kept_exactly_and_telugu_on_screen_text_is_allowed(tmp_path):
    d, sp = project(tmp_path)
    tr = json.loads((tmp_path / "transcript.json").read_text(encoding="utf-8"))
    tr["segments"][0]["words"][0]["w"] = "నమస్తే"
    (tmp_path / "transcript.json").write_text(json.dumps(tr, ensure_ascii=False), encoding="utf-8")
    plan, problems = vp.assemble(d, sp, raw_for(sp, mutate=lambda r: next(e for e in r["scenes"][0]["elements"] if e["type"] == "text").update(content="నమస్తే", language="te")))
    assert problems == [] and scene(plan)["narration"]["text"].startswith("నమస్తే")
    assert next(e for e in scene(plan)["elements"] if e["type"] == "text")["content"] == "నమస్తే"        # no transliteration, no rewrite


# ---------- the media mix ----------
def test_every_scene_counts_its_elements_by_kind_and_the_plan_totals_them(tmp_path):
    d, sp = project(tmp_path)
    plan, _ = vp.assemble(d, sp, raw_for(sp, REAL))
    assert scene(plan)["counts"] == {"text": 1, "icon": 0, "graphic": 0, "background": 0, "image": 1, "video": 0, "page": 0}
    assert scene(plan, 2)["counts"] == {"text": 1, "icon": 1, "graphic": 0, "background": 0, "image": 1, "video": 0, "page": 0}           # scene 3: a photo, a headline and its icon
    assert scene(plan, 6)["counts"]["video"] == 1 and scene(plan, 1)["counts"]["graphic"] == 1
    assert plan["totals"] == {g: sum(s["counts"][g] for s in plan["scenes"]) for g in mk.GROUPS} and plan["totals"]["image"] == 3 and plan["totals"]["video"] == 1


def test_the_plan_reports_what_it_carries_and_asks_for_no_share(tmp_path):
    d, sp = project(tmp_path)
    plan, _ = vp.assemble(d, sp, raw_for(sp, REAL))
    mix = plan["media_mix"]
    assert set(mix) == {"actual", "scenes", "ai_images", "note"} and sum(mix["actual"].values()) == 100               # no target, no tolerance: media is unlimited
    assert mix["scenes"]["image"] == ["scene_01", "scene_03", "scene_06"] and mix["scenes"]["video"] == ["scene_07"] and mix["actual"]["image"] == 28 and mix["actual"]["video"] == 9
    none, _ = vp.assemble(d, sp, raw_for(sp))                                                              # nothing real at all is as valid as a lot of it
    assert none["media_mix"]["actual"] == {"motion": 100, "image": 0, "video": 0} and none["validation"]["warnings"] == []


def test_a_real_element_becomes_a_requirement_with_its_queries_and_its_fallback(tmp_path):
    d, sp = project(tmp_path)
    plan, _ = vp.assemble(d, sp, raw_for(sp, REAL))
    req = scene(plan)["media_requirements"]
    assert len(req) == 1 and req[0]["requirement_id"] == "req_image_main" and req[0]["element_id"] == "image_main" and req[0]["media_type"] == "image"
    assert req[0]["query"] == "office workers at desks" and req[0]["alt_queries"] == ["open plan office", "people at computers"] and req[0]["fallback"].startswith("a flat illustration")
    assert req[0]["must_be_real"] is False and req[0]["ai_prompt"] is None and req[0]["region"] == "full_frame"
    assert scene(plan, 1)["media_requirements"] == []                                                       # a drawn scene asks for nothing


def test_a_real_element_without_its_media_object_is_refused_and_a_drawn_one_never_keeps_one(tmp_path):
    d, sp = project(tmp_path)
    plan, problems = vp.assemble(d, sp, raw_for(sp, REAL, mutate=lambda r: r["scenes"][0]["elements"][0].pop("media")))
    assert plan == {} and any("needs a media object" in m for m in problems)
    plan, problems = vp.assemble(d, sp, raw_for(sp, mutate=lambda r: r["scenes"][0]["elements"][0].update(media={"query": "an office", "fallback": "x flat"})))
    assert problems == [] and scene(plan)["elements"][0]["media"] is None                                  # only a real element has one


def test_a_search_query_in_telugu_or_too_long_is_an_error(tmp_path):
    d, sp = project(tmp_path)
    _, problems = vp.assemble(d, sp, raw_for(sp, REAL, mutate=lambda r: r["scenes"][0]["elements"][0]["media"].update(query="కార్యాలయం పనివాళ్ళు")))
    assert any("2 to 6 plain English words" in m for m in problems)
    _, problems = vp.assemble(d, sp, raw_for(sp, REAL, mutate=lambda r: r["scenes"][0]["elements"][0]["media"].update(query="a very long search query with far too many words in it")))
    assert any("2 to 6 plain English words" in m for m in problems)


def test_a_media_query_with_a_brand_or_a_word_made_from_one_is_a_warning_the_fixer_can_solve(tmp_path):
    """Real case: 'youtuber recording video camera tripod' (a word made from YouTube) passed the checks and only the LLM review noticed it."""
    d, sp = project(tmp_path)
    brand = lambda r: r["scenes"][0]["elements"][0]["media"].update(query="youtuber recording video camera tripod")
    plan, problems = vp.assemble(d, sp, raw_for(sp, REAL, mutate=brand))
    assert problems == [] and "brand_query" in codes(plan) and "brand_query" in vp.FIX_HINTS
    alt = lambda r: r["scenes"][0]["elements"][0]["media"].update(alt_queries=["open plan office", "Instagram reel studio"])
    assert "brand_query" in codes(vp.assemble(d, sp, raw_for(sp, REAL, mutate=alt))[0])
    plain = lambda r: r["scenes"][0]["elements"][0]["media"].update(query="painter at a canvas, apple on the desk")      # canvas and apple are ordinary words
    assert "brand_query" not in codes(vp.assemble(d, sp, raw_for(sp, REAL, mutate=plain))[0])


def test_a_real_picture_with_nothing_drawn_saying_the_meaning_is_a_warning(tmp_path):
    """A real photo or clip may be a mood or a metaphor (the planner is told to), when text or a graphic says what the narration means."""
    d, sp = project(tmp_path)
    plan, problems = vp.assemble(d, sp, raw_for(sp, REAL))
    assert problems == [] and "real_media_alone" not in codes(plan)
    alone = lambda r: r["scenes"][0].update(elements=[e for e in r["scenes"][0]["elements"] if e["type"] not in ("text", "label", "graphic", "diagram", "chart", "data_visualization")])
    plan, problems = vp.assemble(d, sp, raw_for(sp, REAL, mutate=alone))
    assert problems == [] and "real_media_alone" in codes(plan) and "real_media_alone" in vp.FIX_HINTS


def test_images_and_video_are_always_allowed_inside_the_motion_graphics(tmp_path):
    for raw in (None, {"ai_images": True}):
        (tmp_path / str(bool(raw))).mkdir()
        d, sp = project(tmp_path / str(bool(raw)), media=raw)
        plan, problems = vp.assemble(d, sp, raw_for(sp, REAL))
        assert problems == [] and plan["totals"]["image"] == 3 and plan["totals"]["video"] == 1 and not any(c == "media_family_off" for c in codes(plan))
        assert scene(plan, 6)["hero"] == "video" and len(scene(plan)["media_requirements"]) == 1
        text = vp.spec(mk.normalise(raw))
        assert "100% Motion Graphics production" in text and "- image (" in text and "- video (" in text and "- reference (" in text


def test_the_ai_prompt_is_kept_when_ai_pictures_are_wanted_derived_when_missing_and_dropped_otherwise(tmp_path):
    d, sp = project(tmp_path, media={"ai_images": True})
    plan, _ = vp.assemble(d, sp, raw_for(sp, REAL, ai_prompt=True))
    assert scene(plan)["media_requirements"][0]["ai_prompt"].startswith("office workers at their desks") and scene(plan, 6)["media_requirements"][0]["ai_prompt"] is None   # a video has none
    plan, _ = vp.assemble(d, sp, raw_for(sp, REAL))
    assert sp["style"]["suffix"] in scene(plan)["media_requirements"][0]["ai_prompt"] and "ai_prompt_derived" in codes(plan)
    (tmp_path / "off").mkdir()
    d2, sp2 = project(tmp_path / "off")
    plan, _ = vp.assemble(d2, sp2, raw_for(sp2, REAL, ai_prompt=True))
    assert scene(plan)["media_requirements"][0]["ai_prompt"] is None                                       # not wanted: dropped


def test_a_real_picture_that_fills_the_frame_is_a_backdrop_and_a_text_over_it_is_fine(tmp_path):
    d, sp = project(tmp_path)
    plan, _ = vp.assemble(d, sp, raw_for(sp, REAL))
    w = " ".join(plan["validation"]["warnings"])
    assert "text_over_primary" not in codes(plan) and "share an area of the frame" not in w
    plan, _ = vp.assemble(d, sp, raw_for(sp, REAL, mutate=lambda r: r["scenes"][0]["elements"][0]["placement"].update(region="lower_safe_area")))      # the same picture NOT as a backdrop, on the text's own area
    assert "layout_overlap" in codes(plan)


def test_more_real_elements_than_a_scene_can_hold_is_a_warning(tmp_path):
    d, sp = project(tmp_path)

    def many(n):
        def add(r):
            for i in range(n - 1):
                e = json.loads(json.dumps(r["scenes"][0]["elements"][0]))
                e.update(element_id=f"extra_{i}", role="supporting")
                e["placement"]["region"] = ("left", "right", "upper_safe_area", "lower_safe_area", "center")[i % 5]
                r["scenes"][0]["elements"].append(e)
        return add
    plan, problems = vp.assemble(d, sp, raw_for(sp, REAL, mutate=many(3)))
    assert problems == [] and not any("real pictures or clips" in w for w in plan["validation"]["warnings"])           # a bento of three pictures is fine: media is unlimited
    plan, problems = vp.assemble(d, sp, raw_for(sp, REAL, mutate=many(vp.rules.MAX_REAL_PER_SCENE + 1)))
    assert problems == [] and any(f"{vp.rules.MAX_REAL_PER_SCENE + 1} real pictures or clips" in w for w in plan["validation"]["warnings"])


def reference(section=None, query="Mount Everest", region="right"):
    media = {"query": query, "alt_queries": ["Everest"], "why": "the narration states its height", "fallback": "a flat card with the height as a drawn number"}
    if section:
        media["section"] = section
    return {"element_id": "ref_main", "type": "reference", "role": "supporting", "required": False, "visual_description": "the infobox of the article", "placement": {"region": region, "priority": 3}, "media": media}


def test_a_reference_asks_for_a_wikipedia_infobox_or_table_by_the_articles_title(tmp_path):
    d, sp = project(tmp_path)
    plan, problems = vp.assemble(d, sp, raw_for(sp, REAL, mutate=lambda r: r["scenes"][2]["elements"].append(reference("table"))))
    assert problems == [] and scene(plan, 2)["counts"]["page"] == 1 and scene(plan, 2)["hero"] == "image"            # the primary photo of the scene stays the hero
    req = next(r for r in scene(plan, 2)["media_requirements"] if r["media_type"] == "reference")
    assert req["query"] == "Mount Everest" and req["section"] == "table" and req["ai_prompt"] is None and plan["totals"]["page"] == 1
    plan, _ = vp.assemble(d, sp, raw_for(sp, mutate=lambda r: r["scenes"][1]["elements"].append(reference())))
    assert next(r for r in scene(plan, 1)["media_requirements"])["section"] == "infobox"                              # the default part of the article
    plan, _ = vp.assemble(d, sp, raw_for(sp, REAL))
    assert all(r.get("section") is None for s in plan["scenes"] for r in s["media_requirements"] if r["media_type"] != "reference")      # only a reference has a section


def test_a_reference_is_always_available_and_is_part_of_the_image_family(tmp_path):
    d, sp = project(tmp_path)
    plan, problems = vp.assemble(d, sp, raw_for(sp, mutate=lambda r: r["scenes"][1]["elements"].append(reference())))
    ref = next(e for e in scene(plan, 1)["elements"] if e["element_id"] == "ref_main")
    assert problems == [] and ref["type"] == "reference" and mk.family_of("reference") == "image" and len(scene(plan, 1)["media_requirements"]) == 1
    on = vp.spec(mk.normalise(None))
    assert "- reference (image)" in on and "article's exact title" in on and "media.section" in on


# ---------- elements, relationships, hierarchy ----------
def test_duplicate_element_ids_block_the_plan_and_are_reported(tmp_path):
    d, sp = project(tmp_path)
    _, problems = vp.assemble(d, sp, raw_for(sp, mutate=lambda r: r["scenes"][1]["elements"][1].update(element_id=r["scenes"][1]["elements"][0]["element_id"])))
    assert any("element ids repeat" in m for m in problems)


def test_a_relationship_to_a_missing_element_is_removed_and_no_element_is_deleted(tmp_path):
    d, sp = project(tmp_path)
    plan, problems = vp.assemble(d, sp, raw_for(sp, mutate=lambda r: r["scenes"][1]["element_relationships"].append({"source": "text_main", "target": "ghost", "relation": "labels", "description": None})))
    s = scene(plan, 1)
    assert problems == [] and all(r["target"] != "ghost" for r in s["element_relationships"]) and "relationship_removed" in [n["code"] for n in s["validation_notes"]]
    assert any(e["element_id"] == "text_main" for e in s["elements"])


def test_an_unknown_relation_word_is_rejected_by_the_schema(tmp_path):
    d, sp = project(tmp_path)
    plan, problems = vp.assemble(d, sp, raw_for(sp, mutate=lambda r: r["scenes"][1]["element_relationships"].append({"source": "text_main", "target": "gfx_main", "relation": "likes"})))
    assert problems and plan == {}


def test_every_scene_needs_a_primary_element(tmp_path):
    d, sp = project(tmp_path)

    def only_decoration(r):
        for e in r["scenes"][0]["elements"]:
            e["role"], e["required"] = "decoration", False
    _, problems = vp.assemble(d, sp, raw_for(sp, mutate=only_decoration))
    assert any("no primary element" in m for m in problems)


def test_a_scene_may_have_as_many_elements_as_its_idea_needs(tmp_path):
    d, sp = project(tmp_path)

    def many(r):
        r["scenes"][0]["elements"] += [{"element_id": f"extra_{i}", "type": "graphic", "role": "decoration", "required": False, "visual_description": "spark", "placement": {"region": "center", "priority": 5}} for i in range(6)]
    plan, problems = vp.assemble(d, sp, raw_for(sp, mutate=many))
    assert problems == [] and not any("clutter" in w for w in plan["validation"]["warnings"])           # there is no cap on elements: Final QC judges what the picture looks like


# ---------- text, regions, registry ----------
def test_a_sentence_overlay_is_flagged_and_the_narration_is_untouched(tmp_path):
    d, sp = project(tmp_path)
    nar = vp.assemble(d, sp, raw_for(sp))[0]["scenes"][0]["narration"]["text"]
    plan, _ = vp.assemble(d, sp, raw_for(sp, mutate=lambda r: next(e for e in r["scenes"][0]["elements"] if e["type"] == "text").update(content=nar)))
    assert any("repeats the narration" in w or "too long" in w for w in plan["validation"]["warnings"]) and plan["scenes"][0]["narration"]["text"] == nar


def test_an_invented_number_in_a_label_is_refused_but_a_stated_one_passes(tmp_path):
    d, sp = project(tmp_path)
    number = lambda v: (lambda r: next(e for e in r["scenes"][0]["elements"] if e["type"] == "text").update(content=v))
    _, problems = vp.assemble(d, sp, raw_for(sp, mutate=number("97% faster")))
    assert any("number that is not in the narration" in m for m in problems)
    assert vp.assemble(d, sp, raw_for(sp, mutate=number("AI agents")))[1] == []


def test_text_over_the_whole_frame_has_no_safe_area_but_a_side_placement_is_fine(tmp_path):
    d, sp = project(tmp_path)
    put = lambda region: (lambda r: next(e for e in r["scenes"][0]["elements"] if e["type"] == "text")["placement"].update(region=region))
    plan, _ = vp.assemble(d, sp, raw_for(sp, mutate=put("full_frame")))
    assert any("safe area" in w for w in plan["validation"]["warnings"])
    for region in ("right", "left", "top", "bottom", "upper_left"):
        plan, _ = vp.assemble(d, sp, raw_for(sp, mutate=put(region)))
        assert not any("safe area" in w for w in plan["validation"]["warnings"]), region


def test_a_scene_may_show_several_texts_and_the_planner_is_told_there_is_no_text_cap(tmp_path):
    d, sp = project(tmp_path)
    label = lambda: {"element_id": "tool_names", "type": "label", "role": "explanatory", "required": True, "visual_description": "the names", "content": "AI agents", "placement": {"region": "upper_safe_area", "priority": 4}}
    plan, problems = vp.assemble(d, sp, raw_for(sp, mutate=lambda r: r["scenes"][0]["elements"].append(label())))
    assert problems == [] and scene(plan)["counts"]["text"] == 2                                         # a pattern no longer limits the texts of a scene
    ask = Planner(raw_for(sp, REAL))
    vp.run(d, ask=ask)
    assert "max_texts" not in ask.asked[0][1] and "`items` of that element" in ask.asked[0][1] and "empty rectangle with grey lines" in ask.asked[0][1]


def card(items, **kw):
    return {"element_id": "card_a", "type": "graphic", "role": "supporting", "required": False, "visual_description": "a glass card", "placement": {"region": "right", "priority": 4}, "items": items, **kw}


def test_a_card_carries_its_items_and_they_are_checked_like_every_other_text(tmp_path):
    d, sp = project(tmp_path)
    add = lambda items: (lambda r: r["scenes"][0]["elements"].append(card(items)))
    plan, problems = vp.assemble(d, sp, raw_for(sp, mutate=add([{"label": "AI agents", "caption": "do the work", "progress": 1}])))
    assert problems == [] and next(e for e in scene(plan)["elements"] if e["element_id"] == "card_a")["items"][0]["label"] == "AI agents"
    _, problems = vp.assemble(d, sp, raw_for(sp, mutate=add([{"label": "97% faster"}])))
    assert any("number that is not in the narration" in m for m in problems)                            # a statistic is never invented, in a card either
    plan, _ = vp.assemble(d, sp, raw_for(sp, mutate=add([{"label": "Quantum blockchain synergy platform"}])))
    assert any("(item of card_a) is mostly not from the narration" in w for w in plan["validation"]["warnings"])
    _, problems = vp.assemble(d, sp, raw_for(sp, mutate=add([{"label": "x", "progress": 2}])))          # a fill level is 0 to 1
    assert problems


def test_a_description_may_say_placeholder_but_an_unfinished_description_or_placeholder_text_is_rejected(tmp_path):
    """Real case: 'a post card showing a clothes photo placeholder' describes a phone mockup; it is no unfilled value. TBD in a description, or 'placeholder' as the on-screen text, is."""
    d, sp = project(tmp_path)
    first = lambda r: r["scenes"][0]["elements"][0]
    _, ok = vp.assemble(d, sp, raw_for(sp, mutate=lambda r: first(r).update(visual_description="A phone mockup with a photo placeholder and a caption bubble filling in")))
    assert ok == []
    _, unfinished = vp.assemble(d, sp, raw_for(sp, mutate=lambda r: first(r).update(visual_description="TBD")))
    assert unfinished
    _, text = vp.assemble(d, sp, raw_for(sp, mutate=lambda r: next(e for e in r["scenes"][0]["elements"] if e["type"] == "text").update(content="placeholder")))
    assert text


def test_an_unsupported_or_placeholder_region_is_replaced_by_a_supported_one_and_the_change_is_recorded(tmp_path):
    d, sp = project(tmp_path)
    plan, problems = vp.assemble(d, sp, raw_for(sp, mutate=lambda r: next(e for e in r["scenes"][0]["elements"] if e["type"] == "text")["placement"].update(region="somewhere nice")))
    t = next(e for e in scene(plan)["elements"] if e["type"] == "text")
    assert problems == [] and t["placement"]["region"] in vp.REGIONS and "region_replaced" in [n["code"] for n in scene(plan)["validation_notes"]]


def test_a_real_icon_is_resolved_and_an_unknown_one_becomes_a_search_descriptor(tmp_path, monkeypatch):
    from VIDEO_ENGINE.stages import quality
    monkeypatch.setattr(quality, "icon_names", lambda: frozenset({"Code", "Heart"}))
    d, sp = project(tmp_path)
    plan, problems = vp.assemble(d, sp, raw_for(sp))
    icon = next(e for e in scene(plan, 2)["elements"] if e["type"] == "icon")                           # scene 3 uses "code"
    assert problems == [] and icon["registry_requirements"]["icon"] == "code" and icon["registry_requirements"]["resolved"] is True
    plan, _ = vp.assemble(d, sp, raw_for(sp, mutate=lambda r: next(e for e in r["scenes"][2]["elements"] if e["type"] == "icon")["registry_requirements"].update(icon="no-such-icon")))
    reg = next(e for e in scene(plan, 2)["elements"] if e["type"] == "icon")["registry_requirements"]
    assert reg["icon"] is None and reg["resolved"] is False and "no such icon" in reg["search_descriptors"]


def test_the_aspect_ratio_of_the_project_sets_the_size(tmp_path):
    d, sp = project(tmp_path, aspect="9:16")
    plan, _ = vp.assemble(d, sp, raw_for(sp))
    assert plan["project"]["aspect_ratio"] == "9:16" and (plan["project"]["width"], plan["project"]["height"]) == (1080, 1920)


# ---------- motion hints, style, continuity, completeness ----------
def test_motion_hints_are_intents_never_presets_or_timing(tmp_path):
    d, sp = project(tmp_path)
    plan, _ = vp.assemble(d, sp, raw_for(sp, mutate=lambda r: r["scenes"][0]["motion_hints"].append({"element_id": "text_main", "intent": "emphasize_growth", "description": "use preset zoom-in with easing ease-out over 500 ms"})))
    h = next(h for h in scene(plan)["motion_hints"] if h["intent"] == "emphasize_growth")
    assert h["description"] is None and "motion_detail" in [n["code"] for n in scene(plan)["validation_notes"]]
    assert vp.assemble(d, sp, raw_for(sp, mutate=lambda r: r["scenes"][0]["motion_hints"].append({"intent": "Zoom In Fast!"})))[0] == {}


def test_style_comes_from_the_scene_plan_and_continuity_links_the_scenes(tmp_path):
    d, sp = project(tmp_path)
    plan, _ = vp.assemble(d, sp, raw_for(sp))
    assert plan["visual_style"]["palette"] == sp["style"]["palette"] and plan["visual_style"]["style_suffix"] == sp["style"]["suffix"]
    assert scene(plan)["continuity"]["previous_scene_id"] is None and scene(plan)["continuity"]["next_scene_id"] == "scene_02" and plan["scenes"][-1]["continuity"]["next_scene_id"] is None


def test_a_scene_the_planner_left_out_or_made_up_is_a_problem_and_nothing_is_derived(tmp_path):
    d, sp = project(tmp_path)
    plan, problems = vp.assemble(d, sp, raw_for(sp, mutate=lambda r: r["scenes"].pop(3)))
    assert plan == {} and "visual_plan has no scene 4" in problems
    assert any("not in the scene plan" in m for m in vp.assemble(d, sp, raw_for(sp, mutate=lambda r: r["scenes"][0].update(plan_scene_id=99)))[1])
    assert vp.assemble(d, sp, None) == ({}, ["the answer needs a visual_plan object"])


def test_the_same_input_gives_the_same_ids_and_order(tmp_path):
    d, sp = project(tmp_path)
    a, b = (vp.assemble(d, sp, raw_for(sp, REAL))[0] for _ in range(2))
    ids = lambda p: [(s["scene_id"], [e["element_id"] for e in s["elements"]], [x["requirement_id"] for x in s["media_requirements"]]) for s in p["scenes"]]
    assert ids(a) == ids(b) and a["source_fingerprint"] == b["source_fingerprint"]


# ---------- stored plan, staleness, blockers ----------
def test_there_is_no_derived_plan_for_a_project_that_never_ran_visual_planning(tmp_path):
    d, sp = project(tmp_path)
    before = sorted(p.name for p in d.iterdir())
    assert vp.load(d) is None and vp.blockers(d) == "there is no Visual Plan yet: run Visual Planning" and vp.load(tmp_path / "nowhere") is None
    assert sorted(p.name for p in d.iterdir()) == before                                                  # reading writes nothing


def test_a_stored_plan_is_stale_when_the_scene_plan_or_the_media_settings_change(tmp_path):
    d, sp = project(tmp_path)
    vp.save(d, vp.assemble(d, sp, raw_for(sp, REAL))[0])
    assert vp.load(d)["stale"] is False and vp.load(d)["stored"] is True and vp.blockers(d) is None
    info = json.loads((d / "project.json").read_text(encoding="utf-8"))
    (d / "project.json").write_text(json.dumps({**info, "media": mk.normalise({"ai_images": True})}), encoding="utf-8")
    assert vp.load(d)["stale"] is True and "out of date" in vp.blockers(d)
    (d / "project.json").write_text(json.dumps(info), encoding="utf-8")
    sp["scenes"][0]["meaning"] = "something else"
    (d / "scene_plan.json").write_text(json.dumps(sp), encoding="utf-8")
    assert vp.load(d)["stale"] is True


def test_a_plan_with_blocking_errors_blocks_motion_planning(tmp_path):
    d, sp = project(tmp_path)
    plan, _ = vp.assemble(d, sp, raw_for(sp))
    plan["validation"]["errors"] = ["scene_01 has no primary element"]
    vp.save(d, plan)
    assert "blocking error" in vp.blockers(d)


# ---------- handoffs ----------
def test_motion_planning_gets_ids_families_requirements_and_hints_and_no_presets(tmp_path):
    d, sp = project(tmp_path)
    vp.save(d, vp.assemble(d, sp, raw_for(sp, REAL))[0])
    h = vp.motion_handoff(d)
    assert [x["scene_id"] for x in h] == [f"scene_{s['id']:02d}" for s in sp["scenes"]] and h[0]["hero"] == "image" and h[1]["hero"] == "motion"
    assert {"element_id", "type", "family", "role", "required"} == set(h[0]["elements"][0]) and h[0]["elements"][0]["family"] == "image"
    assert h[0]["media_requirements"][0]["query"] == "office workers at desks" and "preset" not in json.dumps(h)
    hand = vp.handoff(d)
    assert hand["file"] == "visual_planning.json" and hand["fingerprint"] and vp.link_errors([{"id": s["id"], "start": s["start"], "end": s["end"]} for s in sp["scenes"]], hand) == []


# ---------- the planner call ----------
class Planner:
    """The planner CLI: answers with the given raw answers one after the other (the last one repeats) and keeps what it was asked."""
    def __init__(self, *answers):
        self.answers, self.asked = list(answers), []

    def __call__(self, user, system="", timeout=0):
        self.asked.append((system, user))
        a = self.answers[min(len(self.asked) - 1, len(self.answers) - 1)]
        return a if isinstance(a, str) else json.dumps({"visual_plan": a})


def test_run_asks_once_writes_the_plan_and_never_changes_the_scene_plan(tmp_path):
    d, sp = project(tmp_path)
    before = {n: (d / n).read_bytes() for n in ("scene_plan.json", "prompts_map.json", "composition.json", "prompts.txt")}
    ask = Planner(raw_for(sp, REAL))
    plan = vp.run(d, ask=ask)
    assert plan["source"] == "llm" and (d / "visual_planning.json").exists() and len(ask.asked) == 1 and ask.asked[0][0] == vp.VISUAL_SYSTEM
    assert {n: (d / n).read_bytes() for n in before} == before
    assert "100% Motion Graphics production" in ask.asked[0][1] and "type image, video or reference" in ask.asked[0][1] and "AI pictures are wanted" not in ask.asked[0][1] and "IMAGE MODE" not in ask.asked[0][1]


def test_the_instructions_follow_the_ai_pictures_setting_and_ask_for_no_share(tmp_path):
    d, sp = project(tmp_path, media={"ai_images": True})
    ask = Planner(raw_for(sp))
    vp.run(d, ask=ask)
    text = ask.asked[0][1]
    assert "ai_prompt" in text and "AI pictures are wanted" in text and "Never use an element of type" not in text


def test_a_plan_with_no_real_media_or_a_lot_of_it_needs_one_ask_only(tmp_path):
    d, sp = project(tmp_path)
    ask = Planner(raw_for(sp))
    plan = vp.run(d, ask=ask)
    assert len(ask.asked) == 1 and plan["media_mix"]["actual"]["motion"] == 100 and vp.blockers(d) is None                 # there is no share to reach: no second ask
    (tmp_path / "m").mkdir()
    d2, sp2 = project(tmp_path / "m")
    ask = Planner(raw_for(sp2, REAL))
    vp.run(d2, ask=ask)
    assert len(ask.asked) == 1


def test_an_invalid_answer_is_retried_once_with_the_problems_then_the_stage_fails_and_nothing_is_derived(tmp_path):
    d, sp = project(tmp_path)
    ask = Planner({"scenes": [{"plan_scene_id": 1}]})
    with pytest.raises(promptgen.GenError, match="did not pass the checks"):
        vp.run(d, ask=ask)
    assert len(ask.asked) == 2 and "Your previous answer had these problems" in ask.asked[1][1] and not (d / "visual_planning.json").exists()


def test_a_plan_with_blocking_errors_is_kept_for_the_page_and_the_stage_fails(tmp_path):
    d, sp = project(tmp_path)
    dup = lambda r: r["scenes"][1]["elements"][1].update(element_id=r["scenes"][1]["elements"][0]["element_id"])
    ask = Planner(raw_for(sp, mutate=dup))
    with pytest.raises(promptgen.GenError, match="element ids repeat"):
        vp.run(d, ask=ask)
    stored = json.loads((d / "visual_planning.json").read_text(encoding="utf-8"))
    assert stored["validation"]["errors"] and "blocking error" in vp.blockers(d)


def test_without_the_planner_the_stage_fails_with_the_reason_and_leaves_no_file(tmp_path):
    d, sp = project(tmp_path)

    def down(user, system="", timeout=0):
        raise promptgen.GenError("the Claude CLI was not found on this machine")
    with pytest.raises(promptgen.GenError, match="not found"):
        vp.run(d, ask=down)
    assert not (d / "visual_planning.json").exists()


def test_garbage_answers_are_handled_safely(tmp_path):
    d, sp = project(tmp_path)
    for text in ("not json at all", "{}", '{"visual_plan": null}', '{"visual_plan": 5}'):
        with pytest.raises(promptgen.GenError):
            vp.run(d, ask=Planner(text))
        assert not (d / "visual_planning.json").exists()


def test_run_needs_a_scene_plan(tmp_path):
    (tmp_path / "project.json").write_text("{}", encoding="utf-8")
    with pytest.raises(promptgen.GenError, match="no scene plan"):
        vp.run(tmp_path, ask=lambda *a, **k: "{}")


def test_every_run_keeps_the_previous_visual_plan(tmp_path):
    d, sp = project(tmp_path)
    vp.run(d, ask=Planner(raw_for(sp, REAL)))
    vp.run(d, ask=Planner(raw_for(sp, REAL)))
    assert list((d / "plan_backups").iterdir())


# ---------- solve the warnings of the stored plan ----------
def cluttered_plan(tmp_path):
    """A stored plan whose scene 1 has ONE warning (a text that is mostly not from the narration)."""
    d, sp = project(tmp_path)

    def ungrounded(r):
        next(e for e in r["scenes"][0]["elements"] if e["type"] == "text").update(content="Quantum blockchain synergy platform")
    plan, problems = vp.assemble(d, sp, raw_for(sp, REAL, mutate=ungrounded))
    assert problems == [] and vp.warned(plan).keys() == {1}
    vp.save(d, plan)
    return d, sp, plan


def test_solving_warnings_asks_only_about_the_scenes_with_warnings_and_keeps_every_other_scene(tmp_path):
    d, sp, old = cluttered_plan(tmp_path)
    asked = []

    def ask(user, system="", timeout=0):
        asked.append(user)
        fixed = vp._to_llm(old["scenes"][0])
        next(e for e in fixed["elements"] if e["type"] == "text").update(content="AI agents")
        return json.dumps({"visual_plan": {"scenes": [fixed]}})
    plan = vp.fix_warnings(d, ask=ask)
    assert len(asked) == 1 and "SOLVE ONLY THE WARNINGS" in asked[0] and old["validation"]["warnings"][0] in asked[0] and "words of this scene's own narration" in asked[0] and asked[0].count('"meaning"') == 1
    assert plan["validation"]["warnings"] == [] and plan["warning_fix"]["status"] == "solved" and plan["warning_fix"]["scenes"] == ["scene_01"]
    assert [json.dumps(s, sort_keys=True) for s in plan["scenes"][1:]] == [json.dumps(s, sort_keys=True) for s in old["scenes"][1:]]       # every other scene is exactly as it was
    assert len(plan["scenes"][0]["elements"]) == len(old["scenes"][0]["elements"]) and scene(plan)["media_requirements"] == old["scenes"][0]["media_requirements"]
    assert vp.load(d)["warning_fix"]["status"] == "solved" and list((d / "plan_backups").iterdir())


def test_a_fix_that_does_not_reduce_the_warnings_keeps_the_old_plan_and_says_so(tmp_path):
    d, sp, old = cluttered_plan(tmp_path)
    plan = vp.fix_warnings(d, ask=lambda user, system="", timeout=0: json.dumps({"visual_plan": {"scenes": [vp._to_llm(old["scenes"][0])]}}))
    assert plan["warning_fix"]["status"] == "no_improvement" and json.dumps(plan["scenes"], sort_keys=True) == json.dumps(old["scenes"], sort_keys=True)


def test_solving_retries_once_with_the_problems_then_fails_without_changing_the_plan(tmp_path):
    d, sp, old = cluttered_plan(tmp_path)
    asked = []

    def ask(user, system="", timeout=0):
        asked.append(user)
        return json.dumps({"visual_plan": {"scenes": [{"plan_scene_id": 2}]}})
    with pytest.raises(promptgen.GenError, match="could not be used"):
        vp.fix_warnings(d, ask=ask)
    assert len(asked) == 2 and "the answer has no scene 1" in asked[1] and "warning_fix" not in vp.load(d)


def test_a_step_retry_solves_only_the_warnings_that_step_raised(tmp_path):
    d, sp, old = cluttered_plan(tmp_path)
    note = next(n for n in old["scenes"][0]["validation_notes"] if n["code"] == "text_ungrounded")
    own, other = note["stage"], note["stage"] % 7 + 1                              # the step that raised it / another step (never the last one)
    assert vp.warned(old, own).keys() == {1} and vp.warned(old, len(vp.STAGES)).keys() == {1}      # the last step is the verdict on the whole plan
    assert vp.warned(old, other) == {}
    assert vp.fix_warnings(d, ask=lambda *a, **k: pytest.fail("the planner must not be asked"), stage=other) == old
    with pytest.raises(review.ReviewError, match=f"step {other} has no warning"):
        vp.start_fix(d, other)
    del note["stage"]                                                                # a plan made before notes carried their step: its warning counts for any step
    assert vp.warned(old, other).keys() == {1}


def test_a_plan_without_warnings_has_nothing_to_solve_and_no_job_starts(tmp_path):
    d, sp = project(tmp_path)
    plan, _ = vp.assemble(d, sp, raw_for(sp, REAL))
    vp.save(d, plan)
    assert vp.warned(plan) == {} and vp.fix_warnings(d, ask=lambda *a, **k: pytest.fail("the planner must not be asked")) == plan
    with pytest.raises(review.ReviewError, match="no warnings"):
        vp.start_fix(d)


def test_the_fix_refuses_a_plan_that_is_out_of_date(tmp_path):
    d, sp, old = cluttered_plan(tmp_path)
    stale = json.loads((d / "visual_planning.json").read_text(encoding="utf-8"))
    stale["source_fingerprint"] = "changed"
    (d / "visual_planning.json").write_text(json.dumps(stale), encoding="utf-8")
    with pytest.raises(promptgen.GenError, match="out of date"):
        vp.fix_warnings(d, ask=lambda *a, **k: pytest.fail("the planner must not be asked"))


# ---------- the canonical source: Scene Segmentation (one planned scene for each of its scenes, its times, its pauses) ----------
_seg = importlib.import_module("test_scene_segmentation")


def seg_project(d, bounds=None):
    """Three sentences with 0.3 s pauses, segmented into 3 scenes, and a scene plan made the way the planner makes it: planned scene k runs from the start of canonical scene k (the first from 0)
    to the start of the next one (the last to the audio end). `bounds` replaces those boundaries."""
    _seg.three_sentences(d)
    with patch.object(scene_segmentation, "SOFT_MIN", 1.0):
        seg = scene_segmentation.run(d, ask=_seg.Ask(_seg.scenes_of([1], [2], [3])))
    duration = json.loads((d / "transcript.json").read_text(encoding="utf-8"))["duration"]
    b = bounds or [0.0, *[s["start_time"] for s in seg["scenes"][1:]], duration]
    scenes = [{"id": k, "start": b[k - 1], "end": b[k], "meaning": f"idea {k}", "concept": f"concept {k}", "mood": "calm", "mode": "image-composite", "pattern": "hero_text",
               "keywords": [], "params": {"text": f"Heart {k}"}} for k in range(1, len(b))]
    sp = {"style": {"suffix": "cinematic documentary", "palette": ["#0B1D26", "#2A9D8F", "#F2A541"]}, "scenes": scenes}
    (d / "scene_plan.json").write_text(json.dumps(sp), encoding="utf-8")
    (d / "project.json").write_text(json.dumps({"id": "t", "name": "t"}), encoding="utf-8")
    return seg, sp


def test_a_plan_that_follows_scene_segmentation_keeps_its_scenes_times_and_pauses(tmp_path):
    seg, sp = seg_project(tmp_path)
    plan, problems = vp.assemble(tmp_path, sp, raw_for(sp))
    assert problems == [] and plan["validation"]["errors"] == [] and plan["source_mapping"]["canonical_scenes"] == plan["source_mapping"]["planned_scenes"] == 3
    for s, c in zip(plan["scenes"], seg["scenes"]):
        assert (s["narration"]["start_seconds"], s["narration"]["end_seconds"]) == (c["start_time"], c["end_time"]) and s["narration"]["text"] == c["transcript"]
        assert s["source_mapping"]["source"] == "scene_segmentation" and s["source_mapping"]["segmentation_scene_id"] == c["scene_id"]
    assert [s["source_mapping"]["gap_after_seconds"] for s in plan["scenes"]] == [0.3, 0.3, None]                  # the pauses are kept, not closed
    assert plan["validation"]["checks"]["by_rule"]["gaps_preserved"] == {"passed": 2, "total": 2} and "3 planned scenes against 3 Scene Segmentation scenes" in plan["stages"][7]["detail"]


def test_nine_canonical_scenes_that_became_ten_planned_scenes_are_an_error_not_a_clean_pass(tmp_path):
    seg, sp = seg_project(tmp_path)
    b = [0.0, seg["scenes"][1]["start_time"], 2.0, seg["scenes"][2]["start_time"], sp["scenes"][-1]["end"]]            # the planner split canonical scene 2 in two
    _, sp = seg_project(tmp_path, bounds=b)
    assert len(sp["scenes"]) == 4
    plan, problems = vp.assemble(tmp_path, sp, raw_for(sp))
    assert plan["validation"]["status"] == "error" and problems and any("Scene Segmentation has 3 scenes but the scene plan has 4" in m for m in plan["validation"]["errors"])
    assert plan["stages"][7]["status"] == "failed" and vp.plan_mismatch(tmp_path)[0].startswith("Scene Segmentation has 3 scenes but the scene plan has 4")


def test_a_planned_start_or_end_that_differs_from_the_canonical_one_names_the_scene_and_the_seconds(tmp_path):
    seg, sp = seg_project(tmp_path)
    b = [0.0, seg["scenes"][1]["start_time"] - 0.2, seg["scenes"][2]["start_time"], sp["scenes"][-1]["end"]]
    _, sp = seg_project(tmp_path, bounds=b)
    plan, _ = vp.assemble(tmp_path, sp, raw_for(sp))
    assert any(f"the plan starts at {b[1]:g} s but Scene Segmentation scene_002 starts at {seg['scenes'][1]['start_time']:g} s" in m for m in plan["validation"]["errors"])
    late = [0.0, seg["scenes"][1]["start_time"], seg["scenes"][2]["start_time"], sp["scenes"][-1]["end"] + 5.0]
    _, sp = seg_project(tmp_path, bounds=late)
    plan, _ = vp.assemble(tmp_path, sp, raw_for(sp))
    assert any("scene_03: the plan ends at" in m for m in plan["validation"]["errors"])


def test_run_refuses_a_scene_plan_that_does_not_follow_scene_segmentation_without_asking_the_planner(tmp_path):
    seg, sp = seg_project(tmp_path)
    b = [0.0, seg["scenes"][1]["start_time"], 2.0, seg["scenes"][2]["start_time"], sp["scenes"][-1]["end"]]
    seg_project(tmp_path, bounds=b)
    with pytest.raises(promptgen.GenError, match="does not follow Scene Segmentation"):
        vp.run(tmp_path, ask=lambda *a, **k: pytest.fail("the planner must not be asked"))


def test_with_captions_on_a_subtitle_text_is_asked_against_and_reported(tmp_path):
    """Real case: the plan drew its own subtitle in the lower area, the caption layer drew the narration on top of it and the Final QC found two overlapping caption lines."""
    assert "CAPTIONS ARE ON" not in vp.spec(mk.normalise(None)) and "CAPTIONS ARE ON" in vp.spec(mk.normalise(None), True)
    d, sp = project(tmp_path)
    info = json.loads((d / "project.json").read_text(encoding="utf-8"))
    (d / "project.json").write_text(json.dumps({**info, "captions": True}), encoding="utf-8")
    sub = lambda r: next(e for e in r["scenes"][0]["elements"] if e["type"] == "text").update(text_purpose="subtitle")
    plan, _ = vp.assemble(d, sp, raw_for(sp, mutate=sub))
    assert any("caption layer already shows it" in w for w in plan["validation"]["warnings"])
    (d / "project.json").write_text(json.dumps({**info, "captions": False}), encoding="utf-8")
    plan, _ = vp.assemble(d, sp, raw_for(sp, mutate=sub))
    assert not any("caption layer already shows it" in w for w in plan["validation"]["warnings"])


def test_the_captions_option_makes_a_plan_made_without_it_stale_and_changes_nothing_when_off(tmp_path):
    d, sp = project(tmp_path)
    info = json.loads((d / "project.json").read_text(encoding="utf-8"))
    put = lambda on: (d / "project.json").write_text(json.dumps({**info, "captions": on}), encoding="utf-8")
    put(False)
    off = vp.fingerprint(d)
    (d / "project.json").write_text(json.dumps({k: v for k, v in info.items() if k != "captions"}), encoding="utf-8")
    assert vp.fingerprint(d) == off                      # an old project (no key) keeps its plan
    put(True)
    assert vp.fingerprint(d) != off
