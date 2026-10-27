"""Verification of registered resources by a REAL render (docs/resources.md). A resource becomes `verified` only after this module drew it with the project's own Remotion renderer, in a
gallery composition (a fixture, not a project), in 16:9 and 9:16, and measured that it really changed pixels against an empty-background baseline; every scene is rendered twice (16:9) and
the two stills must be identical (determinism). Nothing here touches a project, an approval or the network (the default font stack of the project still loads Google Fonts, as before).
Measurements are pixel facts, not a human review: a person still has to look at the previews (`resource-library/previews/`)."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import time
import wave
from pathlib import Path

import numpy as np
from PIL import Image

from . import config, resource_library as rl

ASPECTS = {"16:9": (1920, 1080), "9:16": (1080, 1920)}
SCENE = 2.0                                     # seconds per gallery scene
SAMPLE_AT = 1.6                                 # the still is taken this long after a scene starts (every entrance is finished)
SCALE = 0.5
FPS = 30
PALETTE = ["#0b1220", "#d9582b", "#2a9d9f", "#f2e6d0"]
SILENCE = "resource-gallery-silence.wav"
PREVIEWS = rl.ROOT / "previews"
REPORTS = config.PROJECT_ROOT / "reports" / "RESOURCE_MANAGER" / "verification"
THRESH = {"icon": 0.005, "chart": 0.01, "gfx": 0.0015, "background_mean": 2.0}
TEXTS = {"tel": "అంగారక గ్రహంపై మానవులు", "conj": "శ్రీ క్ష్మ స్త్రీ ప్రభుత్వం", "en": "Mars 2040: 1,200 km"}


# ---------------------------------------------------------------- the gallery composition (real layers of the existing renderer)
def build_gallery(aspect: str, entries: list[rl.Entry]) -> tuple[dict, list[dict]]:
    W, H = ASPECTS[aspect]
    wide = W > H
    scenes: list[dict] = []
    plan: list[dict] = []

    def add(kind: str, name: str, mk, cells: dict | None = None, extra: dict | None = None) -> None:
        i = len(scenes)
        t0 = i * SCENE
        scenes.append({"id": i + 1, "start": t0, "end": t0 + SCENE, "camera": {"move": "static", "from": 1, "to": 1, "focus": [0.5, 0.5]},
                       "layers": [{"type": "background", "colors": [PALETTE[0], PALETTE[2]], "z": 0}, *mk(t0)]})
        plan.append({"scene": i + 1, "kind": kind, "name": name, "frame": round((t0 + SAMPLE_AT) * FPS), "cells": cells or {}, **(extra or {})})

    add("baseline", "baseline", lambda t0: [])
    icons = [e for e in entries if e.category == "icon"]
    cols, rows = (5, 4) if wide else (4, 5)
    cw, ch = W / cols, H / rows
    for n in range(0, len(icons), cols * rows):
        chunk, cells = icons[n:n + cols * rows], {}
        for k, e in enumerate(chunk):
            r, c = divmod(k, cols)
            cells[e.resource_id] = [round(c * cw), round(r * ch), round((c + 1) * cw), round((r + 1) * ch)]

        def mk_icons(t0, chunk=chunk, cells=cells):
            return [{"type": "icon", "resource_id": e.resource_id, "resource_sha256": e.integrity.sha256,
                     "pos": [(cells[e.resource_id][0] + cells[e.resource_id][2]) // 2, (cells[e.resource_id][1] + cells[e.resource_id][3]) // 2],
                     "size": 160, "color": "#ffffff", "enter": {"at": t0, "anim": "pop", "dur": 0.3}, "z": 5} for e in chunk]
        add("icons", f"icons_{n // (cols * rows) + 1}", mk_icons, cells)
    for e in (x for x in entries if x.category == "font"):
        size, x0, gap = (84, 120, 150) if wide else (56, 60, 210)
        y0 = 80 if wide else 120
        bands, spec = {}, []
        for k, key in enumerate(TEXTS):
            for j, own in enumerate((True, False)):
                y = y0 + (k * 2 + j) * gap
                spec.append((key, own, y))
                bands[f"{key}_{'font' if own else 'default'}"] = [0, y - 10, W, y + gap - 20]

        def mk_font(t0, e=e, spec=spec, size=size, x0=x0):
            out = []
            for key, own, y in spec:
                l = {"type": "motion_text", "text": TEXTS[key], "style": "headline", "preset": "cinematic-fade", "at": t0, "pos": [x0, y], "size": size, "z": 5}
                if own:
                    l.update({"fontId": e.resource_id, "fontSha": e.integrity.sha256})
                out.append(l)
            return out
        add("font", e.resource_id, mk_font, {e.resource_id: [0, 0, W, H]}, {"bands": bands})
    for e in (x for x in entries if x.category == "background"):
        s = dict(e.data["sample"])
        add("background", e.resource_id, lambda t0, s=s: [{**s, "z": 0}], {e.resource_id: [0, 0, W, H]})
    for e in (x for x in entries if x.category == "chart"):
        s = dict(e.data["sample"])
        add("chart", e.resource_id, lambda t0, s=s: [{**s, "at": t0, "z": 5}], {e.resource_id: [0, 0, W, H]})
    for e in (x for x in entries if x.category in ("diagram", "effect", "react_component")):
        s = dict(e.data["sample"])
        b = s["box"]
        add("gfx", e.resource_id, lambda t0, s=s: [{**s, "at": t0, "color": "#ffffff", "z": 5}], {e.resource_id: [round(b[0] * W), round(b[1] * H), round((b[0] + b[2]) * W), round((b[1] + b[3]) * H)]})
    comp = {"meta": {"fps": FPS, "width": W, "height": H, "audio": SILENCE, "duration": len(scenes) * SCENE, "subtitles": False, "palette": PALETTE}, "scenes": scenes}
    return comp, plan


# ---------------------------------------------------------------- measuring (pure: tests feed it synthetic images)
def gray(path: Path) -> np.ndarray:
    with Image.open(path) as im:
        return np.asarray(im.convert("L"), dtype=np.int16)


def changed(img: np.ndarray, base: np.ndarray, box: list[int], scale: float = SCALE) -> dict:
    """How much of `box` (full-size px) differs from the empty-background baseline: the share of changed pixels, the mean difference and the bbox of the change."""
    x0, y0, x1, y1 = (round(v * scale) for v in box)
    d = np.abs(img[y0:y1, x0:x1] - base[y0:y1, x0:x1])
    m = d > 25
    ys, xs = np.nonzero(m)
    return {"ratio": float(m.mean()) if m.size else 0.0, "mean": float(d.mean()) if d.size else 0.0,
            "bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if xs.size else None}


def evaluate(entry: rl.Entry, item: dict, img: np.ndarray, base: np.ndarray) -> dict:
    """Pass/fail of one resource in one aspect, with the numbers."""
    cat, box = entry.category, item["cells"][entry.resource_id]
    c = changed(img, base, box)
    if cat == "icon":
        return {"ok": c["ratio"] >= THRESH["icon"], "changed_ratio": round(c["ratio"], 4)}
    if cat == "background":
        return {"ok": c["mean"] >= THRESH["background_mean"], "mean_diff": round(c["mean"], 2)}
    if cat == "chart":
        return {"ok": c["ratio"] >= THRESH["chart"], "changed_ratio": round(c["ratio"], 4)}
    if cat == "font":
        w = {}
        for name, b in item["bands"].items():
            cb = changed(img, base, b)["bbox"]
            w[name] = (cb[2] - cb[0] + 1, cb[3] - cb[1] + 1) if cb else (0, 0)
        ink = all(w[f"{k}_font"][0] >= 20 and w[f"{k}_font"][1] >= 10 for k in TEXTS)
        ratios = {k: round(w[f"{k}_font"][0] / w[f"{k}_default"][0], 2) if w[f"{k}_default"][0] else None for k in TEXTS}
        return {"ok": ink, "ink_in_every_row": ink, "width_vs_default_font": ratios, "bands_px": w}
    return {"ok": c["ratio"] >= THRESH["gfx"], "changed_ratio": round(c["ratio"], 4)}


# ---------------------------------------------------------------- rendering
def _still(bundle: Path, props: Path, frame: int, dest: Path) -> None:
    from . import render
    cmd = f'npx remotion still "{bundle}" Main "{dest}" --frame={frame} --scale={SCALE} --props="{props}" --port={render._free_port()}'
    r = None
    for _ in range(3):                                           # the project's default font stack fetches web fonts: one slow fetch is retried, a real error fails every time
        r = subprocess.run(cmd, cwd=config.REMOTION_DIR, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
        if r.returncode == 0 and dest.exists():
            return
    raise rl.ResourceError("render_failed", f"frame {frame} could not be rendered: {((r.stderr or r.stdout) if r else '')[-240:]}")


def _silence() -> None:
    p = config.REMOTION_DIR / "public" / SILENCE
    if not p.exists():
        with wave.open(str(p), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(8000)
            w.writeframes(b"\x00\x00" * 8000)


def _merge_manifest(path: Path, new: dict) -> dict:
    """A run on a few resources must not erase the cells of the sheets it did not render: keep the previous scenes by name, the new ones win."""
    try:
        old = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, json.JSONDecodeError):
        old = {}
    out = {**new, "aspects": {}}
    for a, scenes in new.get("aspects", {}).items():
        names = {x["name"] for x in scenes}
        out["aspects"][a] = [*scenes, *[x for x in old.get("aspects", {}).get(a, []) if x["name"] not in names and x["kind"] != "baseline"]]
    return out


def verify(ids: list[str] | None = None, progress=None) -> dict:
    """Render the gallery for the chosen resources (default: every imported / failed one) and update the registry. Returns the report (also written to reports/RESOURCE_MANAGER/verification/)."""
    from . import browser_profiles, jobs
    say = progress or (lambda m: None)
    reg = rl.load()
    todo = [e for e in reg if (ids is None and e.status in ("imported", "installed", "failed")) or (ids and e.resource_id in ids)]
    todo = [e for e in todo if rl.check_files(e)["ok"]]
    if not todo:
        return {"verified": [], "failed": [], "note": "nothing to verify"}
    start_sha = {e.resource_id: e.integrity.sha256 for e in todo}
    rl.build_bundle()
    rl.stage_fonts()
    _silence()
    tmp = Path(tempfile.mkdtemp(prefix="a2v_gal_"))
    manifest: dict = {"created_at": rl.now(), "aspects": {}}
    results: dict[str, dict] = {e.resource_id: {"aspects": {}, "deterministic": True} for e in todo}
    try:
        with jobs.RENDER_LOCK, browser_profiles.cleaned_after():
            say("bundling the renderer")
            r = subprocess.run(f'npx remotion bundle src/index.ts --out-dir="{tmp / "b"}" --quiet', cwd=config.REMOTION_DIR, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=400, creationflags=config.LOW_PRIORITY)
            if r.returncode != 0:
                raise rl.ResourceError("bundle_failed", f"the Remotion bundle could not be made: {(r.stderr or r.stdout)[-240:]}")
            for aspect in ASPECTS:
                comp, plan = build_gallery(aspect, todo)
                props = tmp / f"gallery_{aspect.replace(':', 'x')}.json"
                props.write_text(json.dumps(comp), encoding="utf-8")
                out = tmp / aspect.replace(":", "x")
                out.mkdir()
                shots: dict[int, Path] = {}
                for n, item in enumerate(plan):
                    say(f"{aspect}: rendering {item['name']} ({n + 1}/{len(plan)})")
                    dest = out / f"{item['scene']:02d}_{item['kind']}.png"
                    _still(tmp / "b", props, item["frame"], dest)
                    shots[item["scene"]] = dest
                    if aspect == "16:9" and item["kind"] != "baseline":
                        again = out / f"{item['scene']:02d}_repeat.png"
                        _still(tmp / "b", props, item["frame"], again)
                        same = hashlib.sha256(dest.read_bytes()).digest() == hashlib.sha256(again.read_bytes()).digest()
                        for rid in item["cells"]:
                            results[rid]["deterministic"] &= same
                base = gray(shots[plan[0]["scene"]])
                pdir = PREVIEWS / aspect.replace(":", "x")
                pdir.mkdir(parents=True, exist_ok=True)
                for item in plan[1:]:
                    img = gray(shots[item["scene"]])
                    jpg = pdir / f"{item['name']}.jpg"
                    Image.open(shots[item["scene"]]).convert("RGB").save(jpg, quality=82)
                    for e in todo:
                        if e.resource_id in item["cells"]:
                            results[e.resource_id]["aspects"][aspect] = {**evaluate(e, item, img, base), "preview": jpg.relative_to(config.PROJECT_ROOT).as_posix()}
                manifest["aspects"][aspect] = plan
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    # registry update: only a resource whose files did not change while the gallery rendered
    cur = {e.resource_id: e for e in rl.load()}
    ok_ids, bad_ids = [], []
    for rid, res in results.items():
        e = cur[rid]
        if not rl.check_files(e)["ok"] or e.integrity.sha256 != start_sha[rid]:
            continue
        passed = set(res["aspects"]) == set(ASPECTS) and all(a["ok"] for a in res["aspects"].values())
        checks = {"renders_in_16x9": bool(res["aspects"].get("16:9", {}).get("ok")), "renders_in_9x16": bool(res["aspects"].get("9:16", {}).get("ok")),
                  "same_frame_twice_identical": bool(res["deterministic"]), "resolves_from_local_files": True}
        if e.category == "font":
            cov = e.data.get("coverage") or {}
            checks["telugu_and_latin_glyphs_and_shaping_audited"] = not cov.get("telugu_missing") and not cov.get("latin_missing") and bool(cov.get("telugu_shaping"))
        ok = passed and all(checks.values())
        note = "pixel measurements against an empty-background baseline in a gallery fixture; not a human review, not a real project"
        if e.category == "font":
            note += "; width vs the default font: " + json.dumps({a: v.get("width_vs_default_font") for a, v in res["aspects"].items()}) + " (layout boxes are computed for the default font)"
        e.verification = rl.Verification(at=rl.now(), ok=ok, checks=checks, aspects=sorted(res["aspects"]), evidence=res["aspects"].get("16:9", {}).get("preview"), input_sha256=e.integrity.sha256, notes=note)
        e.compatibility.headless_render, e.compatibility.deterministic = ok, bool(res["deterministic"])
        e.compatibility.aspect_ratios = [a for a in ASPECTS if res["aspects"].get(a, {}).get("ok")]
        e.usage.preview_path = e.verification.evidence
        e.status = "verified" if ok else "failed"
        (ok_ids if ok else bad_ids).append(rid)
    rl.save(list(cur.values()))
    rl.build_bundle()
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    rl.atomic_write(PREVIEWS / "gallery_manifest.json", json.dumps(_merge_manifest(PREVIEWS / "gallery_manifest.json", manifest), indent=1) + "\n")
    report = {"at": rl.now(), "verified": ok_ids, "failed": bad_ids, "results": results}
    REPORTS.mkdir(parents=True, exist_ok=True)
    rl.atomic_write(REPORTS / (time.strftime("%Y%m%d-%H%M%S") + ".json"), json.dumps(report, indent=1) + "\n")
    return report
