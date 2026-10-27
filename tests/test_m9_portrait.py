"""M9 tests: optional 9:16 export. 16:9 stays the default and must not change. Run: python -m pytest tests/test_m9_portrait.py -q"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from backend import config, pipeline, render
from backend.cli import parser
from backend.theme import THEME

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = Path(__file__).parent / "fixtures" / "plan_sample"
needs_node = pytest.mark.skipif(shutil.which("npx") is None, reason="npx not on PATH")


def build(tmp_path, *extra):
    work = tmp_path / "p"
    work.mkdir(exist_ok=True)
    for name in ("scene_plan.json", "transcript.json"):
        shutil.copyfile(SAMPLE / name, work / name)
    r = subprocess.run(f'npx tsx scripts/build_composition.ts "{work}" {" ".join(extra)}', cwd=ROOT / "VIDEO_ENGINE" / "remotion", shell=True,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-600:]
    return work


@pytest.fixture
def env(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    pdir = root / "projects" / "p1"
    pdir.mkdir(parents=True)
    (root / "VIDEO_ENGINE" / "remotion" / "public" / "projects" / "p1").mkdir(parents=True)
    monkeypatch.setattr(config, "PROJECT_ROOT", root)
    monkeypatch.setattr(config, "PROJECTS_DIR", root / "projects")
    return pdir


# ---------- 16:9 is untouched ----------
def test_default_paths_and_command_are_the_16x9_ones():
    p = Path("proj")
    assert render.output_path(p, False) == p / "out.mp4" and render.output_path(p, True) == p / "out_preview.mp4"
    assert render.comp_path(p) == p / "composition.json"
    cmd = render.build_command(p, True)
    assert f"--props={p / 'composition.json'}" in cmd and "--scale=0.5" in cmd and "--concurrency=3" in cmd
    assert cmd == render.build_command(p, True, "16:9")
    tall = render.build_command(p, False, "9:16")
    assert f"--props={p / 'composition_9x16.json'}" in tall and str(p / "out_9x16.mp4") in tall and "--concurrency=3" in tall


# ---------- the vertical composition ----------
@needs_node
def test_9x16_composition_is_a_separate_file_with_the_same_scenes_and_slots(tmp_path):
    work = build(tmp_path, "--aspect 9:16")
    assert not (work / "composition.json").exists()
    tall = json.loads((work / "composition_9x16.json").read_text(encoding="utf-8"))
    assert (tall["meta"]["width"], tall["meta"]["height"]) == (1080, 1920) and tall["meta"]["fps"] == 30
    flat = json.loads((SAMPLE / "composition.json").read_text(encoding="utf-8"))
    slots = lambda c: [(s["id"], l.get("slot")) for s in c["scenes"] for l in s["layers"] if l["type"] == "image"]
    assert slots(flat) == slots(tall)                       # same scene plan -> same image slots, so one set of images serves both
    assert [s["pattern"] for s in flat["scenes"]] == [s["pattern"] for s in tall["scenes"]]


@needs_node
def test_9x16_layers_stay_inside_the_frame_and_above_the_phone_ui_zone(tmp_path):
    work = build(tmp_path, "--aspect 9:16")
    tall = json.loads((work / "composition_9x16.json").read_text(encoding="utf-8"))
    W, H = 1080, 1920
    bad = []
    for s in tall["scenes"]:
        for l in s["layers"]:
            for key in ("pos", "from", "to", "target"):
                v = l.get(key)
                if isinstance(v, list) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v):
                    if not (0 <= v[0] <= W and 0 <= v[1] <= H):
                        bad.append((s["id"], l["type"], key, v))
            if isinstance(l.get("pos"), list) and len(l["pos"]) == 4:
                x, y, w, h = l["pos"]
                if x < 0 or y < 0 or x + w > W or y + h > H:
                    bad.append((s["id"], l["type"], "pos-box", l["pos"]))
            if l.get("box") and (l["box"][0] + l["box"][2] > W or l["box"][1] + l["box"][3] > H):
                bad.append((s["id"], l["type"], "box", l["box"]))
            if l["type"] in ("text", "icon", "counter") and isinstance(l.get("pos"), list) and l["pos"][1] > H * 0.84:
                bad.append((s["id"], l["type"], "bottom-zone", l["pos"]))     # phone apps cover the bottom ~16%
    assert bad == []


@needs_node
def test_unknown_aspect_is_refused(tmp_path):
    work = tmp_path / "p"
    work.mkdir()
    r = subprocess.run(f'npx tsx scripts/build_composition.ts "{work}" --aspect 4:3', cwd=ROOT / "VIDEO_ENGINE" / "remotion", shell=True, capture_output=True, text=True, timeout=120)
    assert r.returncode != 0 and "unknown aspect" in (r.stderr + r.stdout)


@needs_node
def test_layout_for_matches_theme_json():
    r = subprocess.run("npx tsx scripts/print_layout.ts", cwd=ROOT / "VIDEO_ENGINE" / "remotion", shell=True, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-400:]
    lay = json.loads(r.stdout)
    assert lay["landscape"]["type"] == THEME["type"] and lay["landscape"]["boxes"] == THEME["boxes"] and not lay["landscape"]["portrait"]
    assert lay["landscape"]["captionBottom"] == "8%" and lay["landscape"]["lowerThirdBottom"] == "12%" and lay["landscape"]["labelTop"] == "8%"
    p = lay["portrait"]
    assert p["portrait"] and p["boxes"] == THEME["portrait"]["boxes"] and (p["w"], p["h"]) == (1080, 1920)
    assert p["type"] == {k: int(v * THEME["portrait"]["typeScale"] + 0.5) for k, v in THEME["type"].items()}   # JS Math.round, not banker rounding
    assert 40 <= p["type"]["body"] < THEME["type"]["body"]      # smaller than 16:9 (the frame is narrower) but still readable on a phone


def test_portrait_boxes_cover_every_16x9_name_and_stay_inside_the_frame():
    wide, tall = THEME["boxes"], THEME["portrait"]["boxes"]
    assert set(wide) == set(tall)
    for name, (x, y, w, h) in tall.items():
        assert 0 <= x and 0 <= y and x + w <= 1.0001 and y + h <= 1.0001, name
    grid = [tall[f"grid-{i}"] for i in range(4)]                 # four rows, none over another
    for a, b in zip(grid, grid[1:]):
        assert a[1] + a[3] <= b[1] + 1e-9


# ---------- fill ----------
def tall_env(pdir):
    comp = {"meta": {"audio": "audio.wav", "duration": 5, "fps": 30, "width": 1080, "height": 1920},
            "scenes": [{"id": 1, "start": 0, "end": 5, "pattern": "hero_only", "camera": {"move": "push-in", "from": 1, "to": 1.1, "focus": [0.5, 0.5]},
                        "layers": [{"type": "image", "slot": "s01_0", "file": None, "z": 1, "anim": "ken-burns"}]}]}
    (pdir / "composition_9x16.json").write_text(json.dumps(comp), encoding="utf-8")
    (pdir / "composition.json").write_text(json.dumps({**comp, "meta": {**comp["meta"], "width": 1920, "height": 1080}}), encoding="utf-8")
    (pdir / "prompts_map.json").write_text(json.dumps({"prompts": [{"n": 1, "scene": 1, "slot": "s01_0", "role": "main", "ratio": "16:9", "text": "x"}]}), encoding="utf-8")
    (pdir / "match_report.json").write_text(json.dumps({"matches": [{"n": 1, "file": "01.png", "method": "filename", "status": "ok"}]}), encoding="utf-8")
    work = pdir / "assets" / "work"
    work.mkdir(parents=True)
    img = Image.new("RGB", (320, 180), (20, 20, 20))
    for x in range(200, 260):                                    # a bright block right of centre: the saliency focus
        for y in range(60, 120):
            img.putpixel((x, y), (250, 250, 250))
    img.save(work / "01.png")


# ---------- pipeline wiring ----------
def test_9x16_steps_and_chains_exist_and_do_not_replace_the_default_ones():
    assert pipeline.CHAINS["build"][-2:] == ("motion-build", "render-final") and pipeline.CHAINS["build-preview"][-2:] == ("motion-build", "render-preview")
    assert pipeline.CHAINS["build-9x16"][-2:] == ("motion-build-9x16", "render-final-9x16")
    assert pipeline.CHAINS["build-preview-9x16"][-2:] == ("motion-build-9x16", "render-preview-9x16")
    for name in pipeline.CHAINS["build-9x16"] + pipeline.CHAINS["build-preview-9x16"]:
        assert name in pipeline.STEPS


def test_9x16_outputs_and_fingerprints_are_separate(env):
    tall_env(env)
    (env / "audio.wav").write_bytes(b"RIFF0000")
    assert pipeline.STEPS["render-final-9x16"].outputs(env) == [env / "out_9x16.mp4"]
    assert pipeline.STEPS["render-preview-9x16"].outputs(env) == [env / "out_preview_9x16.mp4"]
    assert pipeline.STEPS["render-final"].outputs(env) == [env / "out.mp4"]
    assert pipeline.render_inputs(env, "final", "9:16") != pipeline.render_inputs(env, "final")
    assert pipeline.STEPS["render-final-9x16"].requires == ("composition_9x16.json", "audio.*")
    assert pipeline.STEPS["render-final"].requires == ("composition.json", "audio.*")


def test_render_profile_of_the_vertical_video_does_not_overwrite_the_16x9_one(env):
    tall_env(env)
    (env / "render_profile.json").write_text('{"mode": "final"}', encoding="utf-8")
    render.write_profile(env, True, [(150, 10.0)], 10.0, "9:16")
    assert json.loads((env / "render_profile.json").read_text(encoding="utf-8")) == {"mode": "final"}
    assert (env / "render_profile_9x16.json").exists()


def test_cli_accepts_aspect_and_defaults_to_16x9():
    ap = parser()
    assert ap.parse_args(["build", "p"]).aspect == "16:9"
    assert ap.parse_args(["build", "p", "--aspect", "9:16", "--preview"]).aspect == "9:16"
    with pytest.raises(SystemExit):
        ap.parse_args(["build", "p", "--aspect", "4:3"])
    with pytest.raises(ValueError):
        render.suffix("1:1")


# ---------- empty scenes (the 10-17 s and 46-52 s gaps of the demo preview: required images 4 and 9 were never supplied) ----------
@needs_node
def test_9x16_transitions_are_short_and_resolution_independent(tmp_path):
    comp = json.loads((build(tmp_path, "--aspect 9:16") / "composition_9x16.json").read_text(encoding="utf-8"))
    for s in comp["scenes"]:
        t = s.get("transition_out")
        if t:
            assert t["dur"] <= 1.0 and (s["end"] - s["start"]) >= 3 * t["dur"], s["id"]      # a transition can never hide a scene's content
    src = (ROOT / "VIDEO_ENGINE" / "remotion" / "src" / "transitions" / "custom.tsx").read_text(encoding="utf-8")
    assert "1920" not in src and "1080" not in src                                           # sizes come from useVideoConfig()
