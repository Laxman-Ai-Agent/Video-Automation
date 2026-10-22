"""The `dome` kind of the `shape` layer (VIDEO_ENGINE/remotion/src/components/ShapeAnim.tsx, domeGeometry.ts): rendered by the REAL renderer (Chrome) and measured, in both aspect ratios, and checked against the
renderer's own composition schema. The geometry itself is covered by `npx tsx scripts/motion_checks.ts` (and tests/test_motion_planning.py runs it).
Run: python -m pytest tests/test_dome_render.py -q"""
import importlib
import json
import shutil
import subprocess

import numpy as np
import pytest
from PIL import Image

from backend import motion_generation as mg

_mo = importlib.import_module("test_motion_only_mode")
FIXTURE, REMOTION = _mo.FIXTURE, _mo.REMOTION
BODY, WINDOW = "#f2e6d0", "#2a9d9f"


def rgb(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], dtype=float)


def share(img, color, tol=40):
    return float((np.abs(img - rgb(color)).sum(axis=2) < tol).mean())


def test_the_python_side_repeats_the_dome_geometry_of_the_renderer():
    ts = (REMOTION / "src" / "components" / "domeGeometry.ts").read_text(encoding="utf-8")
    assert f"DOME_RATIOS = [{', '.join(f'{x:g}' for x in mg.DOME_RATIOS)}]" in ts and f"DOME_GAP = {mg.DOME_GAP:g};" in ts
    layer = {"type": "shape", "kind": "dome", "from": [100, 900], "to": [700, 900], "count": 3}
    x0, y0, x1, y1 = mg.rect_of_layer(layer, 1920, 1080)
    assert (x0, x1, y1) == (100 / 1920, 700 / 1920, 900 / 1080) and abs((y1 - y0) * 1080 - 600 / (2 * (1 + 0.7 + 0.5) + 0.2)) < 1e-6        # the tallest dome of a cluster of 3 filling 600 px
    one = mg.rect_of_layer({**layer, "count": 1}, 1920, 1080)
    assert abs((one[3] - one[1]) * 1080 - 300) < 1e-6                                                     # a single dome is a half-disc: as high as its radius


@pytest.mark.parametrize("aspect,size", [("16:9", (1920, 1080)), ("9:16", (1080, 1920))])
def test_a_dome_cluster_is_really_drawn_by_the_renderer_in_its_colours_and_only_inside_its_box(tmp_path, aspect, size):
    why = _mo._ready()
    if why:
        pytest.skip(why)
    pdir = tmp_path / "p"
    pdir.mkdir()
    for f in ("scene_plan.json", "transcript.json"):
        shutil.copyfile(FIXTURE / f, pdir / f)
    r = subprocess.run(f'npx tsx scripts/build_composition.ts "{pdir}" --no-images --aspect {aspect}', cwd=REMOTION, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, (r.stderr or r.stdout)[-500:]
    comp_file = pdir / ("composition_9x16.json" if aspect == "9:16" else "composition.json")
    comp = json.loads(comp_file.read_text(encoding="utf-8"))
    comp["meta"]["audio"] = "audio_test.wav"
    W, H = size
    first = comp["scenes"][0]
    x1, x2, base = round(0.3 * W), round(0.7 * W), round(0.9 * H)
    dome = {"type": "shape", "kind": "dome", "elementId": "habitat", "from": [x1, base], "to": [x2, base], "count": 3, "color": BODY, "fill": BODY, "window": WINDOW, "width": 4, "at": first["start"] + 0.3, "dur": 0.6, "z": 40}
    with_dome = json.loads(json.dumps(comp))
    with_dome["scenes"][0]["layers"].append(dome)
    path = tmp_path / "with.json"
    path.write_text(mg.dumps(with_dome), encoding="utf-8")
    val = mg.validate_composition(path)
    assert val["zod"] is True and not val["unknown"], val                                                  # the renderer's own schema accepts it and has a component for the layer type
    frame = round(first["start"] * 30) + 90                                                                # 3 s into the scene: drawn, filled and lit
    early = round((first["start"] + 0.3) * 30)                                                             # the moment it starts to be drawn: nothing filled yet
    cases = [{"name": "with", "frame": frame, "props": with_dome}, {"name": "without", "frame": frame, "props": comp}, {"name": "early", "frame": early, "props": with_dome}]
    base_dir = tmp_path / "probe"
    base_dir.mkdir()
    (base_dir / "cases.json").write_text(json.dumps({"scale": 0.5, "publicDir": str(REMOTION / "public"), "cases": cases}, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run(f'npx tsx scripts/caption_probe.ts "{base_dir / "cases.json"}" "{base_dir / "out"}"', cwd=REMOTION, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1500)
    if r.returncode != 0 and "fetchFontData" in (r.stderr + r.stdout):
        pytest.skip("the web fonts could not be downloaded at render time (network)")
    assert r.returncode == 0, (r.stderr or r.stdout)[-600:]
    img = {n: np.array(Image.open(base_dir / "out" / f"{n}.png").convert("RGB")).astype(float) for n in ("with", "without", "early")}
    h, w = img["with"].shape[:2]
    rect = mg.rect_of_layer(dome, W, H)
    X0, Y0, X1, Y1 = round(rect[0] * w), round(rect[1] * h), round(rect[2] * w), round(rect[3] * h)
    box = lambda im: im[Y0:Y1 + 1, X0:X1 + 1]
    assert share(box(img["with"]), BODY) > 0.2 and share(box(img["with"]), WINDOW) > 0.005, (share(box(img["with"]), BODY), share(box(img["with"]), WINDOW))     # half-discs filled in its colour, lit windows in theirs
    assert share(box(img["without"]), BODY) < 0.02 and share(box(img["without"]), WINDOW) < 0.002                                               # the same frame without the layer has neither
    assert share(box(img["early"]), BODY) < share(box(img["with"]), BODY) / 4                                                                    # it is drawn over time, not there from the first frame
    outside = np.abs(img["with"] - img["without"]).sum(axis=2) > 60
    outside[max(Y0 - 4, 0):Y1 + 5, max(X0 - 4, 0):X1 + 5] = False
    assert float(outside.mean()) < 0.001                                                                                                         # nothing else on the frame changed: the dome is drawn only inside its box
    top_row = box(img["with"])[: max(1, (Y1 - Y0) // 12)]
    assert share(top_row, BODY, 60) < 0.5                                                                                                        # the top of the box is not a solid block: it is round domes, not a rectangle
