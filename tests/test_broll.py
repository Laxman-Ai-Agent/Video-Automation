"""Full-frame B-roll: the planner may put a real video clip across the whole frame (photos and reference pages stay in cards), the code generator is told how to draw it, and the plan version
moved so older plans are made again. Run: python -m pytest tests/test_broll.py -q"""
from VIDEO_ENGINE.stages import motion_animation as ma
from VIDEO_ENGINE.stages import visual_planning as vp
from SYSTEM.core import llm_gateway


def test_the_planner_may_use_a_clip_as_full_frame_broll_but_photos_stay_in_cards():
    rules = vp.media_rules({"ai_images": False})
    assert "FULL-FRAME B-ROLL" in rules and "placement.region 'full_frame'" in rules and "depth_layer 'background'" in rules
    assert "Real photographs (type image) and reference pages must ALWAYS be embedded" in rules              # photos and reference pages: still never a full-frame slide
    assert "never stands alone" in rules and "device frame" in rules                                          # a clip carries drawn words with it; a screencast stays framed
    assert "video clips (type video) must ALWAYS be embedded" not in rules                                    # the old blanket rule is gone


def test_the_plan_version_moved_so_a_plan_made_with_the_old_instructions_is_made_again():
    assert vp.VERSION >= 4


def test_the_code_generator_is_told_to_draw_a_full_frame_clip_as_the_background_of_its_shot(tmp_path, monkeypatch):
    seen = []

    def execute(req):
        seen.append(req)
        raise RuntimeError("stop")
    monkeypatch.setattr(llm_gateway.gateway, "execute", execute)
    try:
        ma.generate_scene_tsx_via_llm(tmp_path, 1, 3.0, "Title", "Sub", [], ["#0f172a"], "16:9")
    except ma.AnimationCodegenError:
        pass
    prompt = seen[0].system_prompt
    assert "B-ROLL" in prompt and 'placement.region is "full_frame"' in prompt and "BACKGROUND of its shot" in prompt and "<OffthreadVideo muted>" in prompt
    assert "NO loop prop" in prompt and "<Loop durationInFrames=" in prompt and "muted loop" not in prompt          # a loop prop does not exist on OffthreadVideo (tsc TS2322, found by a real scene)
    assert "framed card with objectFit contain" in prompt                                                       # reference pages are still never full-bleed
