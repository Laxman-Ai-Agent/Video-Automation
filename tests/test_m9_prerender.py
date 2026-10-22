"""P6 pre-render validation (backend/prerender_checks.py): one test per rule. Run: python -m pytest tests/test_m9_prerender.py -q"""
import json
import shutil
import wave
from pathlib import Path

import pytest
from PIL import Image

from backend import cli, config, pipeline, prerender_checks as pc
from backend.pipeline import StepError

needs_ffmpeg = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg/ffprobe not on PATH")


@pytest.fixture
def env(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    pdir = root / "projects" / "p1"
    pdir.mkdir(parents=True)
    (root / "VIDEO_ENGINE" / "remotion" / "public" / "projects" / "p1").mkdir(parents=True)
    monkeypatch.setattr(config, "PROJECT_ROOT", root)
    monkeypatch.setattr(config, "PROJECTS_DIR", root / "projects")
    monkeypatch.setattr(config, "REMOTION_DIR", root / "VIDEO_ENGINE" / "remotion")       # the checks read the Remotion public folder from config.REMOTION_DIR
    return pdir


def image(env: Path, name: str, size=(1920, 1080)) -> str:
    path = config.REMOTION_DIR / "public" / "projects" / "p1" / name
    Image.new("RGB", size, (90, 120, 150)).save(path)
    return f"projects/p1/{name}"


def img(slot, file, **over):
    return {"type": "image", "slot": slot, "file": file, "z": 1, **over}


def scene(i, start, end, layers=(), **over):
    return {"id": i, "start": start, "end": end, "pattern": "hero_only", "camera": {"move": "static"}, "layers": list(layers), **over}


def write(env: Path, scenes, duration=None, aspect="16:9", match=None, prompts=None, fps=30):
    wide = aspect == "16:9"
    comp = {"meta": {"fps": fps, "width": 1920 if wide else 1080, "height": 1080 if wide else 1920, "audio": "audio.wav",
                     "duration": scenes[-1]["end"] if duration is None else duration}, "scenes": scenes}
    (env / ("composition.json" if wide else "composition_9x16.json")).write_text(json.dumps(comp), encoding="utf-8")
    if match is not None:
        (env / "match_report.json").write_text(json.dumps(match), encoding="utf-8")
    if prompts is not None:
        (env / "prompts_map.json").write_text(json.dumps({"prompts": prompts}), encoding="utf-8")


def prompt(n, slot, required=True, ratio="16:9"):
    return {"n": n, "scene": n, "slot": slot, "role": "main", "ratio": ratio, "required": required, "bg": "full", "text": "x"}


def rules(env, aspect="16:9"):
    return [f.rule for f in pc.check(env, aspect).findings]


def find(rep, rule):
    return [f for f in rep.findings if f.rule == rule]


# ---- empty / missing slots ----
def test_an_empty_required_slot_is_a_warning_naming_scene_slot_and_prompt(env):
    write(env, [scene(1, 0, 5, [img("s01_0", None)])], prompts=[prompt(4, "s01_0")])
    f = find(pc.check(env), "empty_slot")[0]
    assert (f.severity, f.scene, f.shot) == ("warning", 1, "s01_0")
    assert "prompt 4" in f.message and "upload" in f.advice


def test_an_empty_optional_slot_is_only_a_note(env):
    write(env, [scene(1, 0, 5, [img("s01_0", None)])], prompts=[prompt(4, "s01_0", required=False)])
    assert find(pc.check(env), "empty_slot")[0].severity == "info"


def test_a_file_that_does_not_exist_or_cannot_be_read_is_an_error(env):
    bad = config.REMOTION_DIR / "public" / "projects" / "p1" / "broken.png"
    bad.write_bytes(b"not an image")
    write(env, [scene(1, 0, 5, [img("s01_0", "projects/p1/gone.png"), img("s01_1", "projects/p1/broken.png")])])
    got = {f.rule: f for f in pc.check(env).errors}
    assert set(got) == {"missing_file", "unreadable_image"} and got["missing_file"].shot == "s01_0"


# ---- duplicates ----
def test_the_same_file_in_two_slots_is_reported_with_both_scenes(env):
    f = image(env, "a.png")
    write(env, [scene(1, 0, 5, [img("s01_0", f)]), scene(2, 5, 10, [img("s02_0", f)])])
    w = find(pc.check(env), "reused_asset")[0]
    assert "scene 1" in w.message and "scene 2" in w.message and w.severity == "warning"


def test_look_alike_images_are_a_warning_when_both_are_used_and_a_note_when_one_is_not(env):
    a, b = image(env, "a.png"), image(env, "b.png")
    write(env, [scene(1, 0, 5, [img("s01_0", a), img("s01_1", b)])],
          match={"matches": [{"n": 1, "file": "a.jpg"}, {"n": 2, "file": "b.jpg"}], "duplicates": [["a.jpg", "b.jpg"], ["a.jpg", "spare.jpg"]], "warnings": []})
    sev = sorted(f.severity for f in find(pc.check(env), "duplicate_images"))
    assert sev == ["info", "warning"]


# ---- crop and resolution ----
def test_a_wide_photo_in_a_vertical_frame_is_a_heavy_crop_but_fits_a_wide_frame(env):
    f = image(env, "wide.png", (1920, 1080))
    write(env, [scene(1, 0, 5, [img("s01_0", f, pos="full")])])
    assert "heavy_crop" not in rules(env)
    write(env, [scene(1, 0, 5, [img("s01_0", f, pos="full")])], aspect="9:16")
    w = find(pc.check(env, "9:16"), "heavy_crop")[0]
    assert w.severity == "warning" and "32%" in w.message and "9:16" in w.advice


def test_a_half_frame_box_crops_a_wide_photo_and_a_cutout_is_never_cropped(env):
    f = image(env, "wide.png", (1920, 1080))
    write(env, [scene(1, 0, 5, [img("s01_0", f, pos="left-half"), img("s01_1", f, pos="left-half", anim="float")])])
    found = find(pc.check(env), "heavy_crop")
    assert [x.shot for x in found] == ["s01_0"] and "50%" in found[0].message


def test_geometry_helpers_match_the_renderers_cover_rule():
    assert pc.visible_share((1920, 1080), (0, 0, 1080, 1920)) == pytest.approx(0.3164, abs=0.001)
    assert pc.visible_share((1000, 1000), (0, 0, 1920, 1080)) == pytest.approx(0.5625, abs=0.001)
    assert pc.visible_share((1920, 1080), (0, 0, 1920, 1080)) == 1.0
    assert pc.upscale((960, 540), (0, 0, 1920, 1080)) == 2.0


def test_an_image_that_must_be_enlarged_a_lot_is_soft_unless_low_res_already_says_so(env):
    small = image(env, "small.png", (640, 360))
    write(env, [scene(1, 0, 5, [img("s01_0", small, pos="full")])])
    assert "upscaled" in rules(env)
    write(env, [scene(1, 0, 5, [img("s01_0", small, pos="full")])], prompts=[prompt(1, "s01_0")],
          match={"matches": [{"n": 1, "file": "a.jpg"}], "duplicates": [], "warnings": [{"file": "a.jpg", "n": 1, "type": "low_res"}]})
    got = rules(env)
    assert "low_resolution" in got and "upscaled" not in got       # one message per cause


def test_match_step_marks_become_warnings_on_the_right_scene_and_slot(env):
    f = image(env, "a.png")
    g = image(env, "b.png")
    write(env, [scene(1, 0, 5, [img("s01_0", f)]), scene(2, 5, 10, [img("s02_0", g)])],
          prompts=[prompt(1, "s01_0"), prompt(2, "s02_0")],
          match={"matches": [], "duplicates": [], "warnings": [{"file": "a.jpg", "n": 1, "type": "blurry"}, {"file": "b.jpg", "n": 2, "type": "bad_ratio"}]})
    rep = pc.check(env)
    assert [(x.scene, x.shot) for x in find(rep, "blurry")] == [(1, "s01_0")]
    assert [(x.scene, x.shot) for x in find(rep, "bad_ratio")] == [(2, "s02_0")]


# ---- text and safe areas ----
def text(t, **over):
    return {"type": "text", "style": "big-highlight", "text": t, "z": 10, **over}


def test_pinned_text_that_leaves_the_safe_margin_is_flagged_in_a_wide_frame(env):
    write(env, [scene(1, 0, 5, [text("Beyond simple automation", pos=[170, 360])])])
    w = find(pc.check(env), "text_safe_area")
    assert len(w) == 1 and w[0].scene == 1 and "safe margin" in w[0].message
    write(env, [scene(1, 0, 5, [text("Short", pos=[170, 360])])])
    assert find(pc.check(env), "text_safe_area") == []


def test_in_a_vertical_frame_text_in_the_phone_ui_zone_is_flagged_but_wrapping_is_not(env):
    write(env, [scene(1, 0, 5, [text("A long headline that simply wraps", pos=[100, 600]), text("Low", style="label", pos=[100, 1750])])], aspect="9:16")
    got = find(pc.check(env, "9:16"), "text_safe_area")
    assert len(got) == 1 and "y=1750" in got[0].message and "phone" in got[0].advice


def test_a_caption_that_needs_many_lines_is_flagged(env):
    write(env, [scene(1, 0, 5, [text("word " * 80, style="caption")])])
    assert [f.rule for f in pc.check(env).findings if f.rule == "text_length"] == ["text_length"]
    write(env, [scene(1, 0, 5, [text("Short caption", style="caption")])])
    assert find(pc.check(env), "text_length") == []


# ---- timeline ----
def test_a_gap_and_an_overlap_between_scenes_are_errors(env):
    write(env, [scene(1, 0, 5), scene(2, 6, 10), scene(3, 9, 14)])
    got = {f.rule: f for f in pc.check(env).errors}
    assert got["timeline_gap"].scene == 2 and "1.00s" in got["timeline_gap"].message
    assert got["timeline_overlap"].scene == 3 and "1.00s" in got["timeline_overlap"].message


def test_one_frame_of_rounding_is_not_a_gap(env):
    write(env, [scene(1, 0, 5), scene(2, 5.03, 10)])
    assert pc.check(env).errors == []


def test_first_scene_must_start_at_zero_and_the_last_must_end_with_the_video(env):
    write(env, [scene(1, 1, 5), scene(2, 5, 10)], duration=12)
    got = {f.rule for f in pc.check(env).errors}
    assert "timeline_start" in got and "timeline_end" in got
    write(env, [scene(1, 0, 5), scene(2, 5, 10)], duration=10.2)
    rep = pc.check(env)
    assert rep.errors == [] and find(rep, "timeline_end")[0].severity == "warning"


def test_scene_lengths_zero_short_and_long(env):
    write(env, [scene(1, 0, 0.01), scene(2, 0.01, 0.6), scene(3, 0.6, 25)])
    got = {(f.scene, f.severity) for f in pc.check(env).findings if f.rule == "shot_duration"}
    assert got == {(1, "error"), (2, "warning"), (3, "warning")}


def test_a_transition_longer_than_half_its_scene_and_layers_outside_the_scene(env):
    write(env, [scene(1, 0, 2, [text("x", at=5), text("y", at=-1)], transition_out={"type": "fade", "dur": 1.5}), scene(2, 2, 8)])
    rep = pc.check(env)
    assert len(find(rep, "transition_length")) == 1
    assert len(find(rep, "layer_timing")) == 2


@needs_ffmpeg
def test_audio_and_video_lengths_that_differ_are_reported_but_never_block(env):
    with wave.open(str(env / "audio.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 16000 * 3)
    write(env, [scene(1, 0, 10)])
    f = find(pc.check(env), "audio_video_length")[0]
    assert f.severity == "warning" and "3.00s" in f.message and "far apart" in f.message
    write(env, [scene(1, 0, 3.1)])
    assert find(pc.check(env), "audio_video_length") == []         # 0.1 s is within tolerance


# ---- the report and the places it is used ----
def test_the_report_names_scene_shot_severity_message_and_advice_and_has_its_own_file_for_9x16(env):
    write(env, [scene(1, 0, 5, [img("s01_0", None)])], prompts=[prompt(1, "s01_0")])
    rep = pc.check(env)
    path = pc.write_report(env, rep)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert path.name == "prerender_report.json" and data["ok"] is True and data["summary"] == {"error": 0, "warning": 1, "info": 0}
    assert set(data["findings"][0]) == {"severity", "rule", "scene", "shot", "message", "advice"}
    assert "scene 1 / s01_0" in pc.format_text(rep) and "->" in pc.format_text(rep)
    write(env, [scene(1, 0, 5)], aspect="9:16")
    assert pc.write_report(env, pc.check(env, "9:16")).name == "prerender_report_9x16.json"
    assert path.exists()                                            # the 16:9 report is not overwritten


def test_only_genuine_errors_stop_a_render_warnings_are_counted_in_the_message(env):
    write(env, [scene(1, 0, 5, [img("s01_0", None)]), scene(2, 6, 10)])
    with pytest.raises(StepError, match="1.00s with no scene between"):
        pipeline._prerender(env, "16:9")
    write(env, [scene(1, 0, 5, [img("s01_0", None)]), scene(2, 5, 10)])
    assert pipeline._prerender(env, "16:9") == "1 warnings to review in prerender_report.json"
    write(env, [scene(1, 0, 5), scene(2, 5, 10)])
    assert pipeline._prerender(env, "16:9") == ""


def test_missing_files_are_left_to_the_render_preflight_not_blocked_twice(env):
    write(env, [scene(1, 0, 5, [img("s01_0", "projects/p1/gone.png")])])
    assert pc.check(env).errors and pc.check(env).blocking == []
    assert pipeline._prerender(env, "16:9") == ""


def test_a_bug_in_the_check_never_stops_a_video(env, monkeypatch):
    write(env, [scene(1, 0, 5)])
    monkeypatch.setattr(pc, "check", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert pipeline._prerender(env, "16:9") == ""
    assert "pre-render check skipped: boom" in (env / "log.txt").read_text(encoding="utf-8")


def test_cli_check_prints_the_report_and_exits_2_only_on_errors(env, capsys):
    write(env, [scene(1, 0, 5, [img("s01_0", None)])], prompts=[prompt(1, "s01_0")])
    assert cli.main(["check", "p1"]) == 0
    assert "1 warnings" in capsys.readouterr().out
    write(env, [scene(1, 0, 5), scene(2, 7, 10)])
    assert cli.main(["check", "p1"]) == 2
    assert cli.main(["check", "p1", "--aspect", "9:16"]) == 2       # no composition_9x16.json yet: a clear message, not a crash
    assert "does not exist yet" in capsys.readouterr().err


def test_the_real_plan_sample_has_a_clean_timeline(env):
    sample = Path(__file__).parent / "fixtures" / "plan_sample" / "composition.json"
    (env / "composition.json").write_text(sample.read_text(encoding="utf-8"), encoding="utf-8")
    rep = pc.check(env)
    assert [f.rule for f in rep.errors] == [] and rep.summary()["warning"] > 0      # every slot is still empty: warnings, not errors
