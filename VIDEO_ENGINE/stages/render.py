"""Remotion render wrapper. composition.json is the single source of truth and is passed to Remotion as is.
The only derived input is a staged COPY of the audio at VIDEO_ENGINE/remotion/public/<meta.audio> (Remotion serves
audio through staticFile()): the sound-design mix projects/<id>/audio_mix.wav (stages/sound_design.py: narration + transition whooshes + an optional licensed music bed, -14 LUFS),
or the bare projects/<id>/audio.* when no mix exists; the narration file itself is never edited.
Renders must therefore run one at a time (the staged name is shared).
The picture is rendered scene by scene (stages/render_cache.py, cache in projects/<id>/render_cache/<final|preview>/): only a scene that changed (and the one after it) is rendered again.
preview = 960x540 at the project fps (--scale 0.5), final = 1920x1080 at the project fps.
The optional 9:16 variant renders composition_9x16.json (1080x1920; preview 540x960) to out_9x16.mp4 / out_preview_9x16.mp4;
16:9 stays the default and its files and command are unchanged."""
import json
import os
import re
import shutil
import statistics
import subprocess
import time
from pathlib import Path

from PIL import Image

from . import asset_collection, config, render_cache, sound_design
from .diagnose import UserProblem, check_disk, explain_text

CONCURRENCY = 3
HEAVY_RATIO = 1.5      # a scene is "heavy" when it costs this many times the median seconds per frame
SLOW_X_VIDEO = 3.0     # docs/m9.md: tell the user when a render takes more than ~3x the video length
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac"}


def project_audio(pdir: Path) -> Path | None:
    return next((f for f in sorted(pdir.glob("audio.*")) if f.suffix.lower() in AUDIO_EXTS), None)


ASPECTS = ("16:9", "9:16")


def suffix(aspect: str) -> str:
    if aspect not in ASPECTS:
        raise ValueError(f"unknown aspect {aspect!r} (use 16:9 or 9:16)")
    return "_9x16" if aspect == "9:16" else ""


def comp_path(pdir: Path, aspect: str = "16:9") -> Path:
    return pdir / f"composition{suffix(aspect)}.json"


def output_path(pdir: Path, preview: bool, aspect: str = "16:9") -> Path:
    return pdir / f"{'out_preview' if preview else 'out'}{suffix(aspect)}.mp4"


def stage_audio(pdir: Path, aspect: str = "16:9") -> Path:
    """Copy the project audio to VIDEO_ENGINE/remotion/public/<meta.audio> so staticFile(meta.audio) resolves."""
    audio = project_audio(pdir)
    if audio is None:
        raise FileNotFoundError("no audio.* in the project folder")
    name = json.loads(comp_path(pdir, aspect).read_text(encoding="utf-8"))["meta"]["audio"]
    remotion_dir = config.REMOTION_DIR
    dst = remotion_dir / "public" / name
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(sound_design.audio_for_render(pdir, audio), dst)          # the sound-design mix (narration + transition whooshes + music bed, -14 LUFS) when it was built, else the narration itself
    return dst


def stage_motion(pdir: Path) -> None:
    """Stage generated motion scenes from projects/<id>/generated_motion/ into VIDEO_ENGINE/remotion/src/generated/."""
    gen_dir = pdir / "generated_motion"
    if not gen_dir.is_dir():
        return
    from .motion_animation import stage_scenes               # the one implementation: it also removes a scene another project left in the shared folder
    stage_scenes(sorted(gen_dir.glob("scene_*.tsx")), config.REMOTION_DIR / "src" / "generated")
    asset_collection.stage_assets(pdir)                       # the real photos/clips the scenes draw (staticFile("projects/<id>/assets/..."))


def render_flags(preview: bool) -> list[str]:
    """Mode-specific Remotion flags. Preview is cheaper by SPATIAL scaling only (--scale=0.5): the frame rate
    must stay the project fps. --every-nth-frame is forbidden: it makes Remotion play the audio at 2x speed."""
    return [f"--concurrency={CONCURRENCY}"] + (["--scale=0.5"] if preview else [])


def build_command(pdir: Path, preview: bool, aspect: str = "16:9", out: Path | None = None, entry: str = "src/index.ts",
                  frames: tuple[int, int] | None = None) -> list[str]:
    """`out`: another target than the project's output slot (Stage 13 renders a final video to a temporary file first and publishes it only after it was verified).
    `entry` + `frames`: one scene's chunk (first and last frame, inclusive) of an already bundled project; a chunk is muted, the audio is muxed once after the join."""
    cmd = ["npx", "remotion", "render", entry, "Main", str(out or output_path(pdir, preview, aspect)),
           f"--props={comp_path(pdir, aspect)}", *render_flags(preview), *([f"--frames={frames[0]}-{frames[1]}", "--muted"] if frames else [])]
    try:
        from .orchestrator import find_browser_executable
        b_path, _ = find_browser_executable()
        if b_path:
            cmd.append(f"--browser-executable={b_path}")
    except Exception:
        pass
    return cmd


def preflight(pdir: Path, aspect: str = "16:9") -> None:
    """Fail early, by name, instead of deep inside Remotion: enough disk, and every file the video uses exists
    and (for images) decodes. Slots without a file are fine: they render empty."""
    check_disk(pdir, config.MIN_FREE_GB_RENDER, "the render")
    remotion_dir = config.REMOTION_DIR
    public = remotion_dir / "public"
    missing, unreadable = set(), set()
    for scene in json.loads(comp_path(pdir, aspect).read_text(encoding="utf-8"))["scenes"]:
        for layer in scene["layers"]:
            if layer.get("enabled") is False:
                continue                                       # switched off in the timeline: it is not rendered, so its file is not needed
            name = layer.get("file")
            if not name:
                continue
            path = public / name
            if not path.exists():
                missing.add(name)
            elif layer.get("type") == "image":
                try:
                    with Image.open(path) as im:
                        im.verify()
                except Exception:
                    unreadable.add(name)
    problems = []
    if bad_assets := [f["message"] for f in asset_collection.check_assets(pdir) if f["severity"] == "error"]:
        problems.append(f"collected assets are not usable: {'; '.join(bad_assets[:3])} (run Asset Collection again)")
    if missing:
        problems.append(f"missing files: {', '.join(sorted(missing))} (run the build again so the images are copied)")
    if unreadable:
        problems.append(f"unreadable images: {', '.join(sorted(unreadable))} (re-export them and upload again)")
    if problems:
        raise UserProblem("The video cannot be rendered - " + "; ".join(problems) + ".")


def scene_profile(comp: dict, marks: list[tuple[int, float]]) -> list[dict]:
    """Seconds spent per scene, from (frames_done, elapsed_s) samples taken while ONE render ran, so measuring
    costs nothing extra. Frames done are interpolated between samples (approximate: workers render in chunks)."""
    fps = comp["meta"]["fps"]
    pts = [(0, 0.0), *sorted(marks)]

    def at(frame: int) -> float:
        for (f0, t0), (f1, t1) in zip(pts, pts[1:]):
            if frame <= f1:
                return t0 + (t1 - t0) * ((frame - f0) / (f1 - f0) if f1 > f0 else 1)
        return pts[-1][1]

    rows = []
    for sc in comp["scenes"]:
        a, b = round(sc["start"] * fps), round(sc["end"] * fps)
        secs = at(b) - at(a)
        rows.append({"id": sc["id"], "pattern": sc.get("pattern"), "frames": b - a, "seconds": round(secs, 1),
                     "s_per_frame": round(secs / max(b - a, 1), 3)})
    return rows


def heavy_scenes(rows: list[dict]) -> list[int]:
    """Scenes that cost HEAVY_RATIO x more per frame than the median scene (needs 3+ scenes to compare)."""
    if len(rows) < 3:
        return []
    median = statistics.median(r["s_per_frame"] for r in rows)
    return [r["id"] for r in rows if median > 0 and r["s_per_frame"] > HEAVY_RATIO * median]


def write_profile(pdir: Path, preview: bool, marks: list[tuple[int, float]], seconds: float, aspect: str = "16:9", cached_frames: int = 0) -> dict:
    """render_profile.json: total time vs video length and the cost of every scene (a scene taken from the render cache costs 0 s; `cached_frames` says how many frames that was). Not an input of any step."""
    comp = json.loads(comp_path(pdir, aspect).read_text(encoding="utf-8"))
    rows = scene_profile(comp, marks)
    video = comp["meta"]["duration"]
    data = {"mode": "preview" if preview else "final", "seconds": round(seconds, 1), "video_seconds": video,
            "x_video_length": round(seconds / video, 1) if video else None, "heavy": heavy_scenes(rows), "scenes": rows, "cached_frames": cached_frames}
    (pdir / f"render_profile{suffix(aspect)}.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
    return data


def _free_port() -> int:
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


_ANSI = re.compile(r"\x1b\[[0-9;]*m|\[\d{1,2}m")      # Remotion colours its messages; the colour codes are noise in an error shown to the user


def render(pdir: Path, preview: bool, on_progress=None, aspect: str = "16:9", out: Path | None = None) -> Path:
    try:
        from VIDEO_ENGINE.pipeline import browser_profiles
    except ImportError:
        try:
            from backend import browser_profiles
        except ImportError:
            from . import browser_profiles
    with browser_profiles.cleaned_after():
        return _render(pdir, preview, on_progress, aspect, out)


def _run(cmd: list[str], pdir: Path, label: str, on_line=None) -> None:
    """One Remotion command: its output is read line by line, it is registered so that a cancel can stop it, a failure is explained by name."""
    proc = subprocess.Popen(cmd, cwd=config.REMOTION_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace", shell=True, creationflags=config.LOW_PRIORITY)
    try:
        from VIDEO_ENGINE.pipeline import procs
    except ImportError:
        try:
            from backend import procs
        except ImportError:
            from . import procs
    procs.register(pdir.name, proc)
    tail = []
    for line in proc.stdout:
        line = _ANSI.sub("", line.strip())
        tail = (tail + [line])[-15:]
        if on_line:
            on_line(line)
    rc = proc.wait()
    procs.unregister(pdir.name, proc)
    if rc != 0:
        detail = " | ".join(tail[-5:])
        known = explain_text("\n".join(tail))
        if known:
            raise UserProblem(f"{known} (Remotion said: {detail[:300]})")
        raise RuntimeError(f"remotion {label} failed: " + detail)


def _render(pdir: Path, preview: bool, on_progress=None, aspect: str = "16:9", out: Path | None = None) -> Path:
    """Scene by scene (stages/render_cache.py): a scene whose chunk is cached is not rendered again, the chunks are joined and the audio is muxed once."""
    preflight(pdir, aspect)
    if (narration := project_audio(pdir)) is not None:
        sound_design.build(pdir, narration, aspect)                           # raises SoundDesignError with the cause: a render never plays a mix that was not measured
    audio = stage_audio(pdir, aspect)
    stage_motion(pdir)
    out = out or output_path(pdir, preview, aspect)
    comp = json.loads(comp_path(pdir, aspect).read_text(encoding="utf-8"))
    cache = pdir / f"render_cache{suffix(aspect)}" / ("preview" if preview else "final")
    cache.mkdir(parents=True, exist_ok=True)
    chunks = render_cache.plan(pdir, comp, preview, render_flags(preview), cache)
    total = chunks[-1]["to"]
    missing = [c for c in chunks if not c["path"].is_file()]
    cached = total - sum(c["to"] - c["from"] for c in missing)
    bundle = cache.parent / "_bundle"
    t0, marks, done = time.time(), [], 0

    def report(frames_done: int) -> None:
        if on_progress:
            rendered = frames_done - cached                                   # cached frames cost no time: the estimate counts only the frames that are really rendered
            on_progress(min(99.0, 100 * frames_done / total), (time.time() - t0) / max(rendered, 1) * (total - frames_done))      # the last frame is not the end: the join and the verification follow (the step says 100)

    try:
        if missing:
            shutil.rmtree(bundle, ignore_errors=True)
            _run(["npx", "remotion", "bundle", "src/index.ts", f"--out-dir={bundle}", "--quiet"], pdir, "bundle")      # once, after the staging above: the bundle carries the staged scenes, assets and audio
        for c in chunks:
            if c in missing:
                part = c["path"].with_suffix(".part.mp4")                    # a chunk is in the cache only when it is complete
                cmd = build_command(pdir, preview, aspect, part, entry=str(bundle), frames=(c["from"], c["to"] - 1)) + [f"--port={_free_port()}"]     # Remotion's own server must not land on a port another app already answers on ("Does this look like a foreign page?")

                def on_line(line: str, base: int = done) -> None:
                    m = re.search(r"Rendered (\d+)/(\d+)", line)
                    if m:
                        marks.append((base + int(m.group(1)), time.time() - t0))
                        report(base + int(m.group(1)))
                _run(cmd, pdir, "render", on_line)
                os.replace(part, c["path"])
            done += c["to"] - c["from"]
            marks.append((done, time.time() - t0))
            report(done)
    finally:
        shutil.rmtree(bundle, ignore_errors=True)
        for stray in cache.glob("*.part.mp4"):
            stray.unlink(missing_ok=True)
    render_cache.assemble(chunks, audio, comp["meta"]["fps"], out, cache.parent)
    render_cache.prune(cache, chunks)
    write_profile(pdir, preview, marks, time.time() - t0, aspect, cached)
    return out
