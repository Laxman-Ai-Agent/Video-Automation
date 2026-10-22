"""Video QC: measures the rendered mp4 of one aspect (ffprobe / ffmpeg) and adds the findings of the pre-render check. Nothing is simulated: a check that
cannot be measured is reported as such, a missing video gives one failed check."""
import json
import re
import subprocess
from pathlib import Path

from . import audio_utils, review

SIZES = {"16:9": (1920, 1080), "9:16": (1080, 1920)}
LENGTH_TOLERANCE = 0.3          # seconds between the video and the audio
CLIP_DB = -0.1                  # loudest sample at or above this = clipped
BLACK_MIN = 0.5                 # seconds of black that count as a finding
FREEZE_MIN = 3.0                # seconds of an unchanging picture that count as a finding


def _tool(args: list[str], timeout: int = 600) -> str:
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(next((x.strip() for x in reversed(r.stderr.splitlines()) if x.strip()), "no details"))
    return r.stdout + r.stderr


def probe(path: Path) -> dict:
    out = _tool(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate:format=duration,size", "-of", "json", str(path)])
    return json.loads(out[out.find("{"):])


def _fps(text: str) -> float:
    a, _, b = text.partition("/")
    return float(a) / float(b or 1) if float(b or 1) else 0.0


def _check(cid: str, name: str, severity: str, result: str, detail: str, scene: int | None = None, at: float | None = None, until: float | None = None) -> dict:
    return {"id": cid, "check": name, "source": "measured on the video file", "severity": severity, "result": result, "detail": detail, "scene": scene, "at": at, "until": until}


def _scene_of(plan, t: float) -> int | None:
    return next((s.id for s in plan.scenes if s.start - 0.05 <= t < s.end), None) if plan else None


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _audio(pdir: Path) -> Path:
    from .render import project_audio
    return project_audio(pdir)


def check(pdir: Path, aspect: str, preview: bool) -> dict:
    sfx = "_9x16" if aspect == "9:16" else ""
    video = pdir / f"{'out_preview' if preview else 'out'}{sfx}.mp4"
    out = {"aspect": aspect, "preview": preview, "video": video.name, "checks": [], "result": "failed", "media": None}
    checks = out["checks"]
    if not video.exists():
        checks.append(_check("video_exists", "The rendered video exists", "error", "failed", f"{video.name} has not been rendered yet"))
        return out
    plan = review._plan(pdir)
    try:
        info = probe(video)
    except Exception as e:  # unreadable file: nothing else can be measured
        checks.append(_check("video_readable", "The video file can be read", "error", "failed", f"ffprobe could not read {video.name}: {e}"))
        return out
    checks.append(_check("video_exists", "The rendered video exists", "info", "passed", f"{video.name}, {video.stat().st_size} bytes"))
    streams = info.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), {})
    seconds = float(info.get("format", {}).get("duration") or 0)
    a = next((s for s in streams if s.get("codec_type") == "audio"), {})
    out["media"] = {"size_bytes": video.stat().st_size, "duration": seconds, "width": v.get("width"), "height": v.get("height"),
                    "fps": round(_fps(v.get("r_frame_rate", "0/1")), 3), "video_codec": v.get("codec_name"), "audio_codec": a.get("codec_name"),
                    "modified": video.stat().st_mtime}

    try:
        audio_len = audio_utils.duration(_audio(pdir))
        gap = seconds - audio_len
        ok = abs(gap) <= LENGTH_TOLERANCE
        checks.append(_check("length", "Video length matches the audio", "info" if ok else "error", "passed" if ok else "failed",
                             f"video {seconds:.2f} s, audio {audio_len:.2f} s ({gap:+.2f} s)"))
    except Exception as e:
        checks.append(_check("length", "Video length matches the audio", "warning", "warning", f"the audio length could not be read: {e}"))

    w, h = SIZES[aspect]
    want = (w // 2, h // 2) if preview else (w, h)
    got = (v.get("width"), v.get("height"))
    ok = got == want
    checks.append(_check("size", "Picture size matches the aspect ratio", "info" if ok else "error", "passed" if ok else "failed", f"{got[0]} x {got[1]}, expected {want[0]} x {want[1]} for {aspect}"))

    want_fps = (_load(pdir / f"composition{sfx}.json").get("meta") or {}).get("fps")
    if want_fps:
        fps = _fps(v.get("r_frame_rate", "0/1"))
        ok = abs(fps - want_fps) < 0.01
        checks.append(_check("fps", "Frame rate matches the composition", "info" if ok else "warning", "passed" if ok else "warning", f"{fps:g} fps, composition {want_fps} fps"))

    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    checks.append(_check("audio_stream", "The video has an audio track", "info" if has_audio else "error", "passed" if has_audio else "failed", "audio track found" if has_audio else "no audio track in the video"))
    if has_audio:
        loud = audio_utils.max_volume_db(video)
        if loud is None:
            checks.append(_check("clipping", "Audio level", "warning", "warning", "the loudness could not be measured"))
        elif loud < -50:
            checks.append(_check("clipping", "Audio level", "error", "failed", f"the audio is silent (peak {loud:.1f} dB)"))
        elif loud >= CLIP_DB:
            checks.append(_check("clipping", "Audio level", "warning", "warning", f"peak {loud:.1f} dB: the audio may be clipped"))
        else:
            checks.append(_check("clipping", "Audio level", "info", "passed", f"peak {loud:.1f} dB"))

    try:
        # one pass over the whole picture: it also proves the video decodes from the first frame to the last
        text = _tool(["ffmpeg", "-v", "info", "-i", str(video), "-an", "-vf", f"blackdetect=d={BLACK_MIN}:pix_th=0.10,freezedetect=n=0.001:d={FREEZE_MIN}", "-f", "null", "-"])
        checks.append(_check("decode", "The video decodes completely", "info", "passed", f"all {seconds:.2f} s of picture were decoded"))
        blacks = [(float(a), float(b)) for a, b in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", text)]
        if not blacks:
            checks.append(_check("black", "Black frames", "info", "passed", f"no black longer than {BLACK_MIN} s"))
        for a, b in blacks:
            checks.append(_check("black", "Black frames", "warning", "warning", f"black from {a:.2f} s to {b:.2f} s", _scene_of(plan, a), a, b))
        starts = [float(x) for x in re.findall(r"freeze_start: ([\d.]+)", text)]
        lasts = [float(x) for x in re.findall(r"freeze_duration: ([\d.]+)", text)]
        if not starts:
            checks.append(_check("freeze", "Frozen frames", "info", "passed", f"no picture stays unchanged for more than {FREEZE_MIN:g} s"))
        for i, a in enumerate(starts):
            b = a + lasts[i] if i < len(lasts) else seconds
            checks.append(_check("freeze", "Frozen frames", "warning", "warning", f"the picture does not change from {a:.2f} s to {b:.2f} s", _scene_of(plan, a), a, b))
    except Exception as e:
        checks.append(_check("decode", "The video decodes completely", "error", "failed", f"decoding stopped: {e}"))

    pre = review.timeline_state(pdir)[aspect]
    if pre["checked"]:
        bad = pre["errors"] + pre["warnings"]
        sev = "error" if pre["errors"] else "warning" if bad else "info"
        checks.append(_check("prerender", "Pre-render check of the composition", sev, {"error": "failed", "warning": "warning", "info": "passed"}[sev], f"{pre['errors']} errors, {pre['warnings']} warnings"))
        for f in pre["findings"]:
            checks.append(_check(f"prerender:{f['rule']}", f["rule"].replace("_", " ").capitalize(), f["severity"], "failed" if f["severity"] == "error" else "warning", f["message"], f["scene"]))
    out["result"] = "failed" if any(c["result"] == "failed" for c in checks) else "passed_with_warning" if any(c["result"] == "warning" for c in checks) else "passed"
    return out
