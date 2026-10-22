"""Preview evidence of Motion & Timeline Validation (stage 11; roadmap 08_PREVIEW_AND_VISUAL_QA.md): low-resolution STILLS of the current composition at deterministic frames, never a render of
the video. A validation run makes them itself when they are missing or not current (the pipeline is fully automatic: the stage LLM review judges the motion from them); `Generate Preview`
still makes them again on request. Level 1 evidence only: a still proves the frame is not blank and shows the layers, not that the motion or a transition plays well. Whether a person looked
at them is recorded separately (`review`), per level and bound to the exact composition."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from . import config, motion_generation as mg, motion_planning as mp
from .motion_validation import ValidationError, fingerprint, names, sha

RULE_VERSION = "1"                              # the sampling rule: bump it and every old preview is out of date
SCALE = 0.25                                    # a quarter of the frame: cheap, enough to see layers and blankness
BLANK_STD = 2.0                                 # a frame whose grey values hardly vary is blank
FRACTIONS = (("entry", 0.12), ("mid", 0.5), ("pre_exit", 0.9))        # of every scene, by frame
LEVELS = ("stills", "playback")
ATTEMPTS = 5                                    # tries per still


def folder(pdir: Path, aspect: str) -> Path:
    return pdir / names(aspect)["preview"]


def load(pdir: Path, aspect: str) -> dict | None:
    m = mp._read(folder(pdir, aspect) / "manifest.json")
    return m if isinstance(m, dict) and m.get("sampling_rule_version") else None


def sample_plan(comp: dict) -> list[dict]:
    """Which frames: entry / mid / pre-exit of every scene, plus the middle of the outgoing transition. Chosen by frame arithmetic only, so the same composition gives the same frames."""
    fps, out = int(comp["meta"].get("fps") or mp.FPS), []
    for s in comp["scenes"]:
        sid, a, b = f"scene_{s['id']:02d}", s["start"], s["end"]
        for kind, f in FRACTIONS:
            out.append({"scene_id": sid, "kind": kind, "frame": mp.fr(a + f * (b - a), fps)})
        t = s.get("transition_out")
        if t:
            out.append({"scene_id": sid, "kind": "transition", "frame": mp.fr(b - 0.5 * t["dur"], fps)})
    return out


def is_current(man: dict | None, gen_sha: str | None) -> bool:
    """The preview shows the current composition, drawn by the current renderer with the current sampling rule."""
    from . import pipeline
    return bool(man) and man.get("composition_sha") == gen_sha and man.get("renderer_digest") == pipeline._remotion_src_digest() and man.get("sampling_rule_version") == RULE_VERSION


def _bundle(dest: Path) -> None:
    r = subprocess.run(f'npx remotion bundle src/index.ts --out-dir="{dest}" --quiet', cwd=config.REMOTION_DIR, shell=True, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300)
    if r.returncode != 0:
        raise ValidationError(f"the Remotion bundle could not be made: {(r.stderr or r.stdout)[-240:]}")


def _still(bundle: Path, comp_file: Path, frame: int, dest: Path, attempts: int = ATTEMPTS) -> None:
    from . import render
    b_posix = bundle.resolve().as_posix()
    d_posix = dest.resolve().as_posix()
    c_posix = comp_file.resolve().as_posix()
    cmd = [
        "npx", "remotion", "still",
        b_posix, "Main", d_posix,
        f"--frame={frame}", f"--scale={SCALE}",
        f"--props={c_posix}", f"--port={render._free_port()}"
    ]
    for attempt in range(attempts):                                              # the page fetches its web fonts: one slow or failed fetch is tried again, a real error fails every time
        r = subprocess.run(cmd, cwd=config.REMOTION_DIR, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        if r.returncode == 0 and dest.exists():
            return
        time.sleep(3 * (attempt + 1))                                            # back off: a network blip lasts longer than three immediate retries
    raise ValidationError(f"the still at frame {frame} could not be rendered after {attempts} tries: {(r.stderr or r.stdout)[-240:]}")


def _measure(path: Path) -> dict:
    from PIL import Image, ImageStat
    try:
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            std = float(ImageStat.Stat(im.convert("L")).stddev[0])
            return {"decode_ok": True, "width": im.width, "height": im.height, "std": round(std, 1), "blank": std < BLANK_STD}
    except Exception as e:                                                       # Pillow raises many kinds for a broken file
        return {"decode_ok": False, "width": None, "height": None, "std": None, "blank": True, "error": str(e)[:120]}


def _pipeline_modules():
    try:
        from VIDEO_ENGINE.pipeline import browser_profiles, jobs, pipeline
    except ImportError:
        try:
            from backend import browser_profiles, jobs, pipeline
        except ImportError:
            from . import browser_profiles, jobs, pipeline
    return browser_profiles, jobs, pipeline


def smoke(pdir: Path, aspect: str, comp: dict) -> dict[str, list[str]]:
    """The runtime errors of a composition's scenes, by scene id: what the type check cannot see (an `interpolate` input range of [1, 1], a value that is undefined). ONE still at the middle of
    every scene and one try each (a real error fails every time). Nothing is kept: this is a check made by Motion Generation, not the preview evidence of `generate`."""
    from . import asset_collection, render
    browser_profiles, jobs, _ = _pipeline_modules()
    fps, errors = int(comp["meta"].get("fps") or mp.FPS), {}
    tmp = Path(tempfile.mkdtemp(prefix="a2v_smoke_"))
    try:
        comp_file = tmp / "composition.json"
        comp_file.write_text(json.dumps(comp, ensure_ascii=False), encoding="utf-8")
        with jobs.RENDER_LOCK, browser_profiles.cleaned_after():
            render.stage_audio(pdir, aspect)
            asset_collection.stage_assets(pdir)
            _bundle(tmp / "b")
            for s in comp["scenes"]:
                frame = mp.fr((s["start"] + s["end"]) / 2, fps)
                try:
                    _still(tmp / "b", comp_file, frame, tmp / f"scene_{s['id']}.png", attempts=1)
                except ValidationError as e:
                    errors.setdefault(str(s["id"]), []).append(f"runtime error while the scene was drawn at frame {frame}: {str(e).split('tries: ', 1)[-1].strip()}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return errors


def generate(pdir: Path, aspect: str, progress=None) -> dict:
    browser_profiles, jobs, pipeline = _pipeline_modules()
    from . import asset_collection, motion_gen_report, render
    say = progress or (lambda p, eta=None: None)
    gen = motion_gen_report.load(pdir, aspect)
    if gen is None or gen["stale"] or gen["validation"]["errors"]:
        raise ValidationError("Motion Generation must be current and without errors before a preview is made")
    comp_file = pdir / mg.names(aspect)[0]
    comp = json.loads(comp_file.read_text(encoding="utf-8"))
    fps = int(comp["meta"].get("fps") or mp.FPS)
    plan = sample_plan(comp)
    out = folder(pdir, aspect)
    out.mkdir(exist_ok=True)
    tmp_bundle = Path(tempfile.mkdtemp(prefix="a2v_bundle_"))
    samples: list[dict] = []
    try:
        with jobs.RENDER_LOCK, browser_profiles.cleaned_after():                  # the staged audio copy in VIDEO_ENGINE/remotion/public is shared with the renders: one at a time
            render.stage_audio(pdir, aspect)
            asset_collection.stage_assets(pdir)                          # scenes that draw collected photos/clips need them in VIDEO_ENGINE/remotion/public
            _bundle(tmp_bundle / "b")
            for i, smp in enumerate(plan):
                say(5 + 90 * i / len(plan))
                name = f"{smp['scene_id']}_{smp['kind']}_{smp['frame']:05d}.png"
                dest = out / name
                _still(tmp_bundle / "b", comp_file, smp["frame"], dest)
                samples.append({**smp, "file": name, "time_s": round(smp["frame"] / fps, 3), "sha": sha(dest.read_bytes()), **_measure(dest)})
    finally:
        shutil.rmtree(tmp_bundle, ignore_errors=True)
    old = load(pdir, aspect) or {}
    man = {"sampling_rule_version": RULE_VERSION, "composition_sha": gen["output"]["composition_sha"], "renderer_digest": pipeline._remotion_src_digest(), "scale": SCALE, "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "level": "stills (level 1): a decoded, non-blank still is not proof that the motion or a transition plays well", "samples": samples, "reviews": old.get("reviews", [])}
    tmp = out / "manifest.tmp"
    tmp.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, out / "manifest.json")
    keep = {s["file"] for s in samples}
    for f in out.glob("*.png"):                                                   # frames of an older sampling are not evidence of this one
        if f.name not in keep:
            f.unlink()
    say(100)
    return man


def review(pdir: Path, aspect: str, level: str, by: str) -> dict:
    """A person says they looked: `stills` = at the generated stills, `playback` = at the moving video with its audio (made elsewhere). Bound to this composition and the current fingerprint; it is not a technical check."""
    man = load(pdir, aspect)
    gen = mp._read(pdir / mg.names(aspect)[1]) or {}
    if man is None or man.get("composition_sha") != (gen.get("output") or {}).get("composition_sha"):
        raise ValidationError("there is no preview of the current composition to review: generate it first")
    if level not in LEVELS or not (by or "").strip():
        raise ValidationError("a review needs a level (stills or playback) and the name of the person who looked")
    rec = {"level": level, "by": by.strip()[:80], "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "composition_sha": man["composition_sha"], "fingerprint": fingerprint(pdir, aspect)}
    man["reviews"] = [r for r in man.get("reviews", []) if not (r["level"] == level and r["composition_sha"] == man["composition_sha"])] + [rec]
    f = folder(pdir, aspect) / "manifest.json"
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, f)
    return rec
