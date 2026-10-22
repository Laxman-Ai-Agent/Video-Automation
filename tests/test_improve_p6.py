"""Phase 6 of improvement/MASTER_PLAN.md: extra pre-render rules (A2V_VALIDATION). A positive and a negative case for each rule, and proof that
missing media or a crashing check can never produce an "all clear"."""
import json
import shutil
from pathlib import Path

import pytest

from backend import config, prerender_checks as pc, quality
from backend.prerender_checks import ERROR, INFO, WARNING, Report

FIX = Path(__file__).parent / "fixtures"


def comp(scenes, aspect="16:9", subtitles=False, words=None):
    w, h = (1920, 1080) if aspect == "16:9" else (1080, 1920)
    c = {"meta": {"fps": 30, "width": w, "height": h, "audio": "audio.wav", "duration": scenes[-1]["end"], "subtitles": subtitles}, "scenes": scenes}
    if words:
        c["words"] = words
    return c


def scene(i, a, b, layers, **kw):
    return {"id": i, "start": a, "end": b, "layers": layers, **kw}


TEXT = {"type": "text", "style": "caption", "text": "Hello", "at": 1.0}
IMG = {"type": "image", "slot": "s01_0", "file": "img_01.png"}


def run(c, tmp_path, aspect="16:9", match=None, prompts=None, audio=1.0):
    rep = Report(aspect)
    if audio is not None:
        (tmp_path / "audio.wav").write_bytes(b"x")
    quality.extend(rep, c, tmp_path, aspect, match, prompts or {}, audio)
    return rep


def rules(rep, sev=None):
    return sorted(f.rule for f in rep.findings if sev is None or f.severity == sev)


# ---------- meta, audio ----------
def test_aspect_mismatch_and_missing_meta(tmp_path):
    assert "aspect_mismatch" in rules(run(comp([scene(1, 0, 5, [TEXT])]), tmp_path, aspect="9:16"), ERROR)
    assert "aspect_mismatch" not in rules(run(comp([scene(1, 0, 5, [TEXT])], "9:16"), tmp_path, aspect="9:16"))
    c = comp([scene(1, 0, 5, [TEXT])])
    del c["meta"]["audio"]
    assert "render_config" in rules(run(c, tmp_path), ERROR)


def test_audio_missing_is_an_error_only_when_there_is_no_audio(tmp_path):
    assert "audio_missing" in rules(run(comp([scene(1, 0, 5, [TEXT])]), tmp_path, audio=None), ERROR)
    assert "audio_missing" not in rules(run(comp([scene(1, 0, 5, [TEXT])]), tmp_path, audio=5.0))


# ---------- prompts, review, empty scenes ----------
PROMPTS = {"s01_0": {"n": 1, "slot": "s01_0", "scene": 1, "role": "main", "required": True}, "s02_0": {"n": 2, "slot": "s02_0", "scene": 2, "role": "main", "required": True}}


def test_required_prompt_without_a_picture_layer_is_reported(tmp_path):
    c = comp([scene(1, 0, 5, [IMG, TEXT]), scene(2, 5, 9, [TEXT])])
    assert "prompt_not_in_video" in rules(run(c, tmp_path, prompts=PROMPTS), WARNING)
    c = comp([scene(1, 0, 5, [IMG, TEXT]), scene(2, 5, 9, [{"type": "image", "slot": "s02_0", "file": "img_02.png"}, TEXT])])
    assert "prompt_not_in_video" not in rules(run(c, tmp_path, prompts=PROMPTS))


def test_match_needing_review_is_reported_with_its_reason(tmp_path):
    match = {"matches": [{"n": 1, "file": "a.png", "status": "review", "note": "medium confidence - please confirm"}, {"n": 2, "file": "b.png", "status": "ok"}]}
    rep = run(comp([scene(1, 0, 5, [TEXT])]), tmp_path, match=match, prompts=PROMPTS)
    hits = [f for f in rep.findings if f.rule == "needs_review"]
    assert len(hits) == 1 and hits[0].scene == 1 and "medium confidence" in hits[0].message


def test_empty_scene(tmp_path):
    only_bg = scene(1, 0, 5, [{"type": "background", "kind": "gradient"}, {"type": "image", "slot": "s01_0", "file": None}, {"type": "text", "text": "  "}])
    assert "empty_scene" in rules(run(comp([only_bg]), tmp_path))
    assert "empty_scene" not in rules(run(comp([scene(1, 0, 5, [{"type": "background"}, TEXT])]), tmp_path))


# ---------- icons ----------
@pytest.mark.skipif(quality.icon_names() is None, reason="lucide-react is not installed")
def test_unknown_icon_is_reported_and_known_one_is_not(tmp_path):
    bad = {"type": "icon", "lucide": "no-such-icon-xyz", "pos": [960, 400]}
    good = {"type": "icon", "lucide": "map-pin", "pos": [960, 400]}
    assert "icon_unknown" in rules(run(comp([scene(1, 0, 5, [bad])]), tmp_path))
    assert "icon_unknown" not in rules(run(comp([scene(1, 0, 5, [good])]), tmp_path))


def test_icon_outside_safe_area(tmp_path):
    out = {"type": "icon", "lucide": "star", "pos": [1900, 540], "size": 160}
    inside = {"type": "icon", "lucide": "star", "pos": [960, 540], "size": 160}
    assert "icon_position" in rules(run(comp([scene(1, 0, 5, [out])]), tmp_path))
    assert "icon_position" not in rules(run(comp([scene(1, 0, 5, [inside])]), tmp_path))
    low = {"type": "icon", "lucide": "star", "pos": [540, 1700], "size": 160}                # inside the bottom 16% that phone apps cover
    assert "icon_position" in rules(run(comp([scene(1, 0, 5, [low])], "9:16"), tmp_path, aspect="9:16"))


# ---------- repeats ----------
def test_repeated_transition_and_camera(tmp_path):
    fade = {"type": "fade", "dur": 0.5}
    c = comp([scene(1, 0, 3, [TEXT], transition_out=fade), scene(2, 3, 6, [TEXT], transition_out=fade), scene(3, 6, 9, [TEXT], transition_out={"type": "wipe", "dur": 0.5})])
    assert rules(run(c, tmp_path), WARNING).count("transition_repeat") == 1
    cam = {"move": "push-in", "from": 1, "to": 1.1, "focus": [0.5, 0.5]}
    c = comp([scene(i, 3 * (i - 1), 3 * i, [TEXT], camera=cam) for i in (1, 2, 3)])
    assert "camera_repeat" in rules(run(c, tmp_path), INFO)
    c = comp([scene(1, 0, 3, [TEXT], camera=cam), scene(2, 3, 6, [TEXT], camera={**cam, "move": "pull-out"}), scene(3, 6, 9, [TEXT], camera=cam)])
    assert "camera_repeat" not in rules(run(c, tmp_path))


# ---------- shots ----------
def _shot(i, a, b):
    return {"id": f"scene_01_shot_{i:02d}", "scene": 1, "start": a, "end": b, "transition": None, "transition_dur": 0.0}


def test_shot_gap_is_an_error_and_good_shots_are_clean(tmp_path):
    bad = scene(1, 0, 12, [TEXT], shots=[_shot(1, 0, 4), _shot(2, 5, 12)])
    good = scene(1, 0, 12, [TEXT], shots=[_shot(1, 0, 6), _shot(2, 6, 12)])
    assert "shot_gap" in rules(run(comp([bad]), tmp_path), ERROR)
    assert not [f for f in run(comp([good]), tmp_path).findings if f.rule.startswith("shot_")]


# ---------- text ----------
def test_subtitle_word_wider_than_safe_width(tmp_path):
    long_word = "క" * 60
    words = [{"w": long_word, "start": 0, "end": 1}]
    assert "subtitle_width" in rules(run(comp([scene(1, 0, 5, [TEXT])], subtitles=True, words=words), tmp_path))
    ok = [{"w": "తెలుగు", "start": 0, "end": 1}]
    assert "subtitle_width" not in rules(run(comp([scene(1, 0, 5, [TEXT])], subtitles=True, words=ok), tmp_path))
    assert "subtitle_width" not in rules(run(comp([scene(1, 0, 5, [TEXT])], subtitles=False, words=words), tmp_path))     # subtitles are off: nothing to check


def test_text_on_the_focus_point(tmp_path):
    cam = {"move": "push-in", "from": 1, "to": 1.1, "focus": [0.5, 0.5]}
    on = {"type": "text", "style": "big-highlight", "text": "Big", "pos": [800, 500], "at": 1}
    off = {"type": "text", "style": "big-highlight", "text": "Big", "pos": [100, 100], "at": 1}
    assert "text_over_subject" in rules(run(comp([scene(1, 0, 5, [IMG, on], camera=cam)]), tmp_path))
    assert "text_over_subject" not in rules(run(comp([scene(1, 0, 5, [IMG, off], camera=cam)]), tmp_path))
    assert "text_over_subject" not in rules(run(comp([scene(1, 0, 5, [on], camera=cam)]), tmp_path))                  # no picture: nothing to cover


# ---------- highlight timing ----------
def test_headline_far_from_a_spoken_word(tmp_path):
    shutil.copy(FIX / "plan_sample" / "transcript.json", tmp_path / "transcript.json")
    far = {"type": "text", "style": "big-highlight", "text": "Routine tasks", "at": 58.0}       # nearest word starts 0.25 s away
    near = {"type": "text", "style": "big-highlight", "text": "Routine tasks", "at": 57.75}
    assert "highlight_timing" in rules(run(comp([scene(8, 51.89, 62.25, [far])]), tmp_path), INFO)
    assert "highlight_timing" not in rules(run(comp([scene(8, 51.89, 62.25, [near])]), tmp_path))


# ---------- a crashing rule is visible; the verdict is honest ----------
def test_crashing_rule_becomes_a_visible_warning(tmp_path, monkeypatch):
    def boom(rep, ctx):
        raise RuntimeError("boom")
    monkeypatch.setattr(quality, "RULES", (boom,))
    rep = run(comp([scene(1, 0, 5, [TEXT])]), tmp_path)
    assert [f.rule for f in rep.findings] == ["check_failed"] and "NOT verified" in rep.findings[0].advice
    assert quality.verdict(rep) == "needs_attention"


def test_verdict_levels():
    rep = Report("16:9")
    rep.checked = {"scenes": 3, "image_layers": 2, "rules": 11}
    assert quality.verdict(rep) == "clear"
    rep.add(INFO, "x", 1, None, "m", "a")
    assert quality.verdict(rep) == "clear"                    # information alone does not block the all-clear
    rep.add(WARNING, "x", 1, None, "m", "a")
    assert quality.verdict(rep) == "needs_attention"
    rep.add(ERROR, "x", 1, None, "m", "a")
    assert quality.verdict(rep) == "blocked"
    empty = Report("16:9")
    empty.checked = {"scenes": 0, "image_layers": 0, "rules": 11}
    assert quality.verdict(empty) == "needs_attention"        # nothing was looked at


# ---------- integration with prerender_checks (real check() and write_report()) ----------
def _project(tmp_path: Path, scenes, prompts) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    shutil.copy(FIX / "audio_test.wav", tmp_path / "audio.wav")
    from backend import audio_utils
    scenes[-1]["end"] = audio_utils.duration(tmp_path / "audio.wav")
    (tmp_path / "composition.json").write_text(json.dumps(comp(scenes)), encoding="utf-8")
    (tmp_path / "prompts_map.json").write_text(json.dumps({"prompts": prompts}), encoding="utf-8")
    return tmp_path


def test_missing_media_never_gives_an_all_clear(tmp_path, monkeypatch):
    monkeypatch.setenv("A2V_VALIDATION", "1")
    first = list(PROMPTS.values())[:1]
    # (a) the slot exists but has no picture
    rep = pc.check(_project(tmp_path / "a", [scene(1, 0, 5, [{"type": "image", "slot": "s01_0", "file": None}, TEXT])], first))
    assert quality.verdict(rep) == "needs_attention" and "empty_slot" in rules(rep)
    # (b) a required prompt has no picture layer at all
    rep = pc.check(_project(tmp_path / "b", [scene(1, 0, 5, [TEXT])], first))
    assert quality.verdict(rep) == "needs_attention" and "prompt_not_in_video" in rules(rep)


def test_report_has_verdict_and_run_history_only_with_the_flag(tmp_path, monkeypatch):
    pdir = _project(tmp_path / "p", [scene(1, 0, 5, [IMG, TEXT])], list(PROMPTS.values())[:1])
    monkeypatch.delenv("A2V_VALIDATION", raising=False)
    pc.write_report(pdir, pc.check(pdir))
    off = json.loads(pc.report_path(pdir).read_text(encoding="utf-8"))
    assert "verdict" not in off and not (pdir / "validation_history.json").exists()               # flag off: the old report, unchanged
    monkeypatch.setenv("A2V_VALIDATION", "1")
    for _ in range(22):
        pc.write_report(pdir, pc.check(pdir))
    on = json.loads(pc.report_path(pdir).read_text(encoding="utf-8"))
    assert on["verdict"] in ("clear", "needs_attention") and on["run"]["checked"]["scenes"] == 1 and on["run"]["composition"] == "composition.json"
    hist = json.loads((pdir / "validation_history.json").read_text(encoding="utf-8"))
    assert len(hist) == 20 and hist[-1]["verdict"] == on["verdict"]                             # the last 20 runs are kept


def test_record_failure_says_unverified(tmp_path):
    quality.record_failure(tmp_path, "16:9", ValueError("broken json"))
    rep = json.loads(pc.report_path(tmp_path).read_text(encoding="utf-8"))
    assert rep["verdict"] == "unverified" and rep["ok"] is False and rep["findings"][0]["rule"] == "check_failed" and "NOT verified" in rep["findings"][0]["advice"]


def test_hooks_are_behind_the_flag(monkeypatch):
    root = Path(__file__).parent.parent / "VIDEO_ENGINE"
    pre = (root / "stages" / "prerender_checks.py").read_text(encoding="utf-8")
    assert pre.count('if config.improve("validation"):') == 2 and pre.index("quality.extend") < pre.index("return rep")
    pipe = (root / "pipeline" / "legacy_pipeline_adapter.py").read_text(encoding="utf-8")
    assert 'if config.improve("validation"):' in pipe and pipe.index("record_failure") > pipe.index("pre-render check skipped")
    monkeypatch.delenv("A2V_VALIDATION", raising=False)
    assert config.improve("validation") is False
