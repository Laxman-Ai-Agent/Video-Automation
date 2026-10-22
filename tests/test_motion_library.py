"""The motion library (VIDEO_ENGINE/remotion/src/motion): pure checks (timing, visibility, Telugu, determinism, presets, bounds, selection), the switch in
build_composition.ts (off = unchanged), and REAL renders of every text and graphic preset at 1920x1080 and 1080x1920 (ink inside the safe area, nothing
before the start frame, identical pixels when a frame is rendered twice). Run: python -m pytest tests/test_motion_library.py -q"""
import json
import os
import shutil
import socket
import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from backend import config

ROOT = config.PROJECT_ROOT
REMOTION = ROOT / "VIDEO_ENGINE" / "remotion"
FIXTURE = Path(__file__).parent / "fixtures" / "plan_sample"


def run(cmd: str, env: dict | None = None, timeout: int = 1500) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=REMOTION, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, env={**os.environ, **(env or {})})


def _need_node():
    if shutil.which("npx") is None or not (REMOTION / "node_modules").exists():
        pytest.skip("node / remotion dependencies are not available")


def test_pure_checks_of_the_library():
    """90+ checks: presets, timing, visibility in English and Telugu, determinism, masks, composition bounds, selection, integration."""
    _need_node()
    r = run("npx tsx scripts/motion_checks.ts")
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert r.returncode == 0 and out["ok"], out["failed"]
    assert out["count"] >= 90 and out["text_presets"] >= 40 and out["exits"] >= 8 and out["emphasis"] >= 8


def _listing() -> dict:
    _need_node()
    return json.loads(run("npx tsx scripts/motion_list.ts").stdout.strip().splitlines()[-1])


def test_presets_are_organised_in_categories():
    lst = _listing()
    assert len(lst["text"]) >= 40 and len(lst["graphics"]) >= 40 and len(lst["masks"]) >= 12
    assert {p["category"] for p in lst["text"]} >= {"entrance", "reveal", "typography", "kinetic", "depth"}
    assert {p["category"] for p in lst["graphics"]} == {"line", "shape", "frame", "connect", "hud", "cinematic", "data", "map"}
    assert all(p["label"] and len(p["desc"]) > 10 for p in lst["text"] + lst["graphics"])


# ---------- the switch: off = the composition is exactly what it was ----------
def _build(tmp: Path, aspect: str, env: dict) -> dict:
    for f in ("scene_plan.json", "transcript.json"):
        shutil.copyfile(FIXTURE / f, tmp / f)
    r = run(f'npx tsx scripts/build_composition.ts "{tmp}" --aspect {aspect}', env=env)
    assert r.returncode == 0, (r.stderr or r.stdout)[-600:]
    return json.loads((tmp / ("composition_9x16.json" if aspect == "9:16" else "composition.json")).read_text(encoding="utf-8"))


@pytest.mark.parametrize("aspect", ["16:9", "9:16"])
def test_switch_off_keeps_the_classic_composition_and_on_adds_motion(tmp_path, aspect):
    _need_node()
    dirs = {n: tmp_path / n for n in ("off", "off2", "on", "on2")}
    for d in dirs.values():
        d.mkdir()
    off = _build(dirs["off"], aspect, {"A2V_MOTION": "0"})
    assert off == _build(dirs["off2"], aspect, {})                                          # explicit off and unset are the same
    types = {l["type"] for s in off["scenes"] for l in s["layers"]}
    assert not any(t.startswith("motion_") for t in types) and "motion" not in off["meta"]  # nothing of the library without the switch
    on = _build(dirs["on"], aspect, {"A2V_MOTION": "1"})
    types_on = [l["type"] for s in on["scenes"] for l in s["layers"]]
    assert "motion_text" in types_on and "motion_scene" in types_on and on["meta"]["motion"] == "rich"
    assert (on["meta"]["width"], on["meta"]["height"], len(on["scenes"])) == (off["meta"]["width"], off["meta"]["height"], len(off["scenes"]))
    classic_text = [(s["id"], l["text"]) for s in off["scenes"] for l in s["layers"] if l["type"] == "text" and l.get("text")]
    rich_text = [(s["id"], l["text"]) for s in on["scenes"] for l in s["layers"] if l["type"] in ("text", "motion_text") and l.get("text")]
    assert classic_text == rich_text                                                        # every script text is still there, in the same scene
    kind = lambda s: (s["id"], s["start"], s["end"], (s.get("transition_out") or {}).get("type"))
    assert [kind(s) for s in on["scenes"]] == [kind(s) for s in off["scenes"]]                # same scenes, same cut times, same transition types ...
    assert all(a["transition_out"]["dur"] < b["transition_out"]["dur"] for a, b in zip(on["scenes"], off["scenes"]) if a.get("transition_out"))   # ... but a faster change (pace x1.3)
    assert [l for s in on["scenes"] for l in s["layers"] if l["type"] == "image"] == [l for s in off["scenes"] for l in s["layers"] if l["type"] == "image"]
    presets = [next((l["preset"] for l in s["layers"] if l["type"] == "motion_text"), None) for s in on["scenes"]]
    shown = [p for p in presets if p]
    assert len(set(shown)) >= min(4, len(shown)) and all(a != b for a, b in zip(presets, presets[1:]) if a and b)    # variety, never the same twice in a row
    assert _build(dirs["on2"], aspect, {"A2V_MOTION": "1"}) == on                           # deterministic
    (tmp_path / "check.json").write_text(json.dumps(on), encoding="utf-8")
    r = run('npx tsx -e "import {CompositionSchema} from \'./src/schema\'; import {readFileSync} from \'node:fs\'; const r=CompositionSchema.safeParse(JSON.parse(readFileSync(process.argv[1],\'utf-8\'))); console.log(r.success?\'OK\':JSON.stringify(r.error.issues.slice(0,3)))" "' + str(tmp_path / "check.json") + '"')
    assert "OK" in r.stdout, r.stdout + r.stderr                                            # the renderer's own schema accepts it


def test_motion_flag_is_part_of_the_cache_fingerprint(monkeypatch):
    from backend import fingerprint
    monkeypatch.delenv("A2V_MOTION", raising=False)
    monkeypatch.setenv("A2V_FINGERPRINTS", "1")
    off = fingerprint.versioned("fill-9x16", "abc")
    monkeypatch.setenv("A2V_MOTION", "1")
    assert fingerprint.versioned("fill-9x16", "abc") != off                                 # switching the library on or off never reuses the other mode's composition


# ---------- real renders of every preset, both aspect ratios ----------
def _render_ready() -> str | None:
    if not (REMOTION / "node_modules" / "@remotion" / "renderer").exists():
        return "remotion dependencies are not installed"
    try:
        [socket.create_connection((h, 443), timeout=4).close() for h in ("fonts.googleapis.com", "fonts.gstatic.com")]
    except OSError:
        return "Google Fonts unreachable (the renderer fetches the fonts at render time)"
    return None


SIZES = {"16_9": (1920, 1080), "9_16": (1080, 1920)}
EN = "The Moon is slowly drifting away from Earth"
TE = "భూమి చుట్టూ తిరిగే చంద్రుడు"
SAFE = 0.05
SCALE = 0.5
TE_PRESETS = ["cinematic-fade", "word-reveal", "char-reveal", "blur-reveal", "line-reveal", "typewriter", "kinetic", "mask-reveal"]


def _comp(items, w, h):
    return {"meta": {"fps": 30, "width": w, "height": h, "audio": "audio_test.wav", "duration": 9.0, "subtitles": False, "palette": ["#0B1D26", "#F2A541", "#2A9D8F"]},
            "scenes": [{"id": 1, "start": 0, "end": 9, "camera": {"move": "static", "from": 1, "to": 1, "focus": [0.5, 0.5]},
                        "layers": [{"type": "background", "kind": "gradient", "colors": ["#0B1D26", "#143A4A"], "z": 0}] + ([{"type": "motion_scene", "z": 8, "items": items}] if items else [])}]}


def _text(preset, text=EN, **kw):
    return {"kind": "text", "preset": preset, "text": text, "style": "headline", "start": 0.5, "end": 9, "box": [0.08, 0.35, 0.84, 0.3], "seed": "t", "mark": text.split(" ")[1], "emphasisAt": [2.0], **kw}


def _gfx(preset, **kw):
    return {"kind": "gfx", "preset": preset, "label": "Mars", "value": 72, "data": [3, 5, 2, 8], "start": 0.5, "end": 9, "box": [0.2, 0.3, 0.6, 0.35], "seed": "g", **kw}


@pytest.fixture(scope="module")
def stills(tmp_path_factory):
    why = _render_ready()
    if why:
        pytest.skip(why)
    lst = _listing()
    base = tmp_path_factory.mktemp("motion")
    pub = base / "public"
    pub.mkdir()
    shutil.copy(REMOTION / "public" / "audio_test.wav", pub / "audio_test.wav")
    cases = []
    for s, (w, h) in SIZES.items():
        def add(name, items, frame):
            cases.append({"name": f"{name}__{s}", "frame": frame, "props": _comp(items, w, h)})
        add("empty", [], 150)
        add("before", [_text("blur-reveal", start=8.0)], 150)                      # the item starts after this frame: nothing may be drawn
        for p in lst["text"]:
            add(f"t_{p['id']}", [_text(p["id"])], 150)
        for pid in TE_PRESETS:
            add(f"te_{pid}", [_text(pid, TE)], 150)
        for g in lst["graphics"]:
            add(f"g_{g['id']}", [_gfx(g["id"])], 90)
        for i in (1, 2):                                                          # the same mid-entrance frame rendered twice
            add(f"det{i}_kinetic", [_text("kinetic")], 33)
            add(f"det{i}_radar", [_gfx("radar-sweep")], 70)
            add(f"det{i}_particles", [_gfx("particles-float")], 70)
        add("masks", [{"kind": "reveal", "preset": "iris-circle", "mask": "iris-circle", "start": 0.5, "end": 9, "box": [0.1, 0.1, 0.8, 0.6], "enterDur": 1.0, "content": {"type": "background", "kind": "gradient", "colors": ["#F2A541", "#2A9D8F"], "z": 0}}], 30)
    (base / "cases.json").write_text(json.dumps({"scale": SCALE, "publicDir": str(pub), "cases": cases}, ensure_ascii=False), encoding="utf-8")
    cmd = f'npx tsx scripts/caption_probe.ts "{base / "cases.json"}" "{base / "out"}"'
    r = None
    for _ in range(3):                                                            # the probe skips stills it already made: a rerun continues (a font download or a locked temp file can fail once)
        r = run(cmd, timeout=3000)
        if r.returncode == 0:
            break
    if r.returncode != 0 and "fetchFontData" in (r.stderr + r.stdout):
        pytest.skip("the web fonts could not be downloaded at render time (network), after 3 runs with retries: " + (r.stderr or r.stdout)[-300:].replace("\n", " "))
    assert r.returncode == 0, (r.stderr or r.stdout)[-800:]
    return base / "out", lst


def load(d: Path, name: str) -> np.ndarray:
    return np.array(Image.open(d / f"{name}.png").convert("RGB")).astype(int)


def ink(d: Path, name: str, s: str, thr: int = 24) -> np.ndarray:
    return np.abs(load(d, f"{name}__{s}") - load(d, f"empty__{s}")).max(axis=2) > thr


def inside_safe(mask: np.ndarray, s: str, margin=0.5 * SAFE) -> bool:
    ys, xs = np.where(mask)
    if not len(xs):
        return False
    h, w = mask.shape
    bottom = 0.87 if s == "9_16" else 1 - margin                                 # a phone covers the bottom 16% of a tall frame
    return xs.min() >= margin * w and xs.max() <= (1 - margin) * w and ys.min() >= margin * h and ys.max() <= bottom * h


@pytest.mark.parametrize("s", list(SIZES))
def test_every_text_preset_renders_visibly_inside_the_safe_area(stills, s):
    d, lst = stills
    bad = []
    for p in lst["text"]:
        m = ink(d, f"t_{p['id']}", s)
        if m.mean() < 0.002 or not inside_safe(m, s):
            bad.append((p["id"], round(float(m.mean()), 4)))
    assert not bad, bad                                                           # every one of the 40+ presets shows its text, inside the frame margins


@pytest.mark.parametrize("s", list(SIZES))
def test_telugu_text_renders_with_every_sampled_preset(stills, s):
    d, _ = stills
    bad = [p for p in TE_PRESETS if ink(d, f"te_{p}", s).mean() < 0.002 or not inside_safe(ink(d, f"te_{p}", s), s)]
    assert not bad, bad
    # the Telugu glyphs are really drawn (not tofu boxes): a long run of distinct ink columns inside the line
    cols = ink(d, "te_cinematic-fade", s).any(axis=0)
    assert cols.sum() > 40


@pytest.mark.parametrize("s", list(SIZES))
def test_every_graphic_preset_renders_inside_the_frame(stills, s):
    d, lst = stills
    bad = []
    for g in lst["graphics"]:
        m = ink(d, f"g_{g['id']}", s, thr=10)
        n = int(m.sum())
        if n < 3 or (g["category"] != "cinematic" and not inside_safe(m, s)):
            bad.append((g["id"], n))
    assert not bad, bad


@pytest.mark.parametrize("s", list(SIZES))
def test_nothing_is_drawn_before_the_start_frame(stills, s):
    d, _ = stills
    assert np.abs(load(d, f"before__{s}") - load(d, f"empty__{s}")).max() <= 2


@pytest.mark.parametrize("s", list(SIZES))
def test_same_frame_gives_identical_pixels(stills, s):
    d, _ = stills
    for n in ("kinetic", "radar", "particles"):
        assert np.array_equal(load(d, f"det1_{n}__{s}"), load(d, f"det2_{n}__{s}")), n
    assert ink(d, "det1_kinetic", s).any() and ink(d, "det1_radar", s, 10).any()   # and they are not just empty frames


@pytest.mark.parametrize("s", list(SIZES))
def test_mask_reveal_shows_part_of_the_picture(stills, s):
    d, _ = stills
    m = ink(d, "masks", s, 20)
    frac = float(m.mean())
    assert 0.02 < frac < 0.6                                                      # mid-transition: a part of the box is revealed, not all and not nothing
