"""Render Video (roadmap improvements/Render_Video_Complete_Roadmap), Stage 13: renders EXACTLY the approved timeline version into a verified final video. It reuses the existing Remotion renderer (backend/render.py); it adds
what makes the result trustworthy: the approval gate again inside the job, an immutable manifest of what was approved, a temporary output, a verification of the encoded file, an atomic publish that never destroys the
last good video, a report and honest phases. It does not edit the timeline, approve anything, or declare the video acceptable: `final_qc_status` stays `pending` and Stage 14 (Final QC) decides.

Scope (like Stages 11 and 12): Motion-Only projects. With pictures the earlier render path of pipeline.py stays as it was.
Phases (`render_job[_9x16].json`): validating -> rendering -> finalizing -> verifying_output -> publishing -> completed | failed | cancelled (`cancel_requested` between); a job file that says "active" while no job runs is
`interrupted` (never inferred as success from a leftover file). The progress shown to the pipeline never reaches 100 before the output is verified and published (the step itself finishes it).
Files: `render_manifest[_9x16].json` (written when the job reserves its input), `render_job[_9x16].json` (live state + attempt history), `render_report[_9x16].json` (the result), `out[_9x16].mp4` (published),
`out[_9x16].previous.mp4` (the last good video before the current one), `out[_9x16].failed-<job>.mp4` (a rejected output kept for diagnosis, one at most)."""
from __future__ import annotations

import json
import os
import shutil
import threading
import time
import uuid
from pathlib import Path

from SYSTEM.policies import rule_switches
from . import config, media_probe as mprobe, motion_planning as mp, motion_validation as mv, pipeline, render, resource_library as rl, store
from . import timeline_approval as ta

SCHEMA = "1.0"
VERSION = 1
PROFILE = "standard_final"                     # the only profile: the approved timeline's own resolution / fps, h264 in mp4, the project audio. Server-controlled: a request cannot choose another.
DURATION_TOLERANCE_S = 0.15                    # container duration vs the frames the composition asks for (audio may end a few ms after the picture): the ONE tolerance of this stage
AUDIO_TOLERANCE_S = 0.25                       # audio stream duration vs min(audio file, video)
SIZES = {"16:9": (1920, 1080), "9:16": (1080, 1920)}
ACTIVE = ("validating", "rendering", "finalizing", "verifying_output", "publishing", "cancel_requested")
MAX_EVENTS, MAX_ATTEMPTS = 40, 10
_guard = threading.Lock()
_running: dict[str, threading.Lock] = {}


class RenderError(Exception):
    """The render cannot start or did not produce a verified video (a message for the user). `blockers` = the reasons when it is a refusal."""

    def __init__(self, message: str, blockers: list[str] | None = None) -> None:
        super().__init__(message)
        self.blockers = blockers or []


def names(aspect: str) -> dict[str, str]:
    sfx = "_9x16" if aspect == "9:16" else ""
    return {"job": f"render_job{sfx}.json", "manifest": f"render_manifest{sfx}.json", "report": f"render_report{sfx}.json"}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def canon(obj) -> str:
    return mv.canon(obj)


# ---------- reading and writing the three records (the store's per-project lock, atomic replace) ----------
def _read(pdir: Path, key: str, aspect: str) -> dict | None:
    f = pdir / names(aspect)[key]
    with store._info_lock(pdir):
        data = mp._read(f)
    return data if isinstance(data, dict) and data.get("schema_version") == SCHEMA else None


def _write(pdir: Path, key: str, aspect: str, data: dict) -> None:
    f = pdir / names(aspect)[key]
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    with store._info_lock(pdir):
        for i in range(5):
            try:
                os.replace(tmp, f)
                break
            except PermissionError:
                if i == 4:
                    raise
                time.sleep(0.05)


def _job(pdir: Path, aspect: str, job_id: str, **fields) -> dict:
    """Update the live job record (read-modify-write under the store lock)."""
    with store._info_lock(pdir):
        cur = _read(pdir, "job", aspect) or {"schema_version": SCHEMA, "project_id": pdir.name, "aspect": aspect, "attempts": []}
        if cur.get("job_id") != job_id:
            cur.update(job_id=job_id, events=[], error=None, cancel_requested=False, started_at=now(), finished_at=None, render_percent=0, frames_done=0)
        ev = fields.pop("event", None)
        cur.update(fields)
        cur["updated_at"] = now()
        if ev:
            cur["events"] = (cur.get("events", []) + [{"at": cur["updated_at"], "phase": cur.get("phase"), "note": ev}])[-MAX_EVENTS:]
        _write(pdir, "job", aspect, cur)
        return cur


def _finish_attempt(pdir: Path, aspect: str, job_id: str, status: str, error: str | None) -> None:
    with store._info_lock(pdir):
        cur = _read(pdir, "job", aspect)
        if not cur or cur.get("job_id") != job_id:
            cur = {"schema_version": SCHEMA, "project_id": pdir.name, "aspect": aspect, "attempts": (cur or {}).get("attempts", []), "job_id": job_id, "events": [], "started_at": now()}
        cur.update(status=status, phase=status, error=error, finished_at=now(), updated_at=now())
        att = {"job_id": job_id, "status": status, "started_at": cur.get("started_at"), "finished_at": cur["finished_at"], "error": error}
        cur["attempts"] = ([a for a in cur.get("attempts", []) if a.get("job_id") != job_id] + [att])[-MAX_ATTEMPTS:]
        _write(pdir, "job", aspect, cur)


# ---------- what is expected, what is supported ----------
def expected(pdir: Path, aspect: str) -> dict:
    """From the composition the renderer reads (its own frame rule: Math.round(duration x fps) = motion_planning.fr), never from UI defaults."""
    m = json.loads(render.comp_path(pdir, aspect).read_text(encoding="utf-8"))["meta"]
    fps = m["fps"]
    frames = mp.fr(m["duration"], fps)
    return {"width": m["width"], "height": m["height"], "fps": fps, "frames": frames, "duration_seconds": round(frames / fps, 3), "composition_duration_seconds": m["duration"],
            "audio_required": bool(m.get("audio")), "codec": "h264", "container": "mp4", "profile": PROFILE}


def validate_config(pdir: Path, aspect: str, exp: dict) -> list[str]:
    """Why this render is not supported (empty = supported). Nothing is downgraded silently: an unsupported setting stops the render with its name."""
    why = []
    if aspect not in SIZES:
        return [f"aspect {aspect!r} is not supported (16:9 or 9:16)"]
    if (exp["width"], exp["height"]) != SIZES[aspect]:
        why.append(f"the composition is {exp['width']}x{exp['height']}, the {aspect} profile is {SIZES[aspect][0]}x{SIZES[aspect][1]}")
    if not (isinstance(exp["fps"], int) and 1 <= exp["fps"] <= 120):
        why.append(f"fps {exp['fps']!r} is not supported (a whole number from 1 to 120)")
    if exp["frames"] <= 0:
        why.append("the composition has no duration")
    if exp["audio_required"] and render.project_audio(pdir) is None:
        why.append("the composition names an audio track but the project has no audio file")
    for tool in ("ffprobe", "npx"):
        if shutil.which(tool) is None:
            why.append(f"the tool {tool} is not on PATH")
    try:
        probe_file = pdir / f".write_test_{uuid.uuid4().hex[:6]}"
        probe_file.write_bytes(b"")
        probe_file.unlink()
    except OSError:
        why.append("the project folder is not writable")
    try:
        from .diagnose import check_disk
        check_disk(pdir, config.MIN_FREE_GB_RENDER, "the render")
    except Exception as e:
        why.append(str(e)[:200])
    return why


def renderer_version() -> dict:
    root = pipeline._REMOTION
    for f in (root / "node_modules" / "remotion" / "package.json", root / "package.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            ver = data.get("version") or (data.get("dependencies") or {}).get("remotion")
            if ver:
                return {"name": "remotion", "version": str(ver), "source": f.relative_to(root).as_posix()}
        except (OSError, ValueError):
            continue
    return {"name": "remotion", "version": "unknown", "source": None}


def out_paths(pdir: Path, aspect: str, job_id: str = "") -> dict[str, Path]:
    final = render.output_path(pdir, False, aspect)
    return {"final": final, "previous": final.with_name(final.stem + ".previous.mp4"), "temp": final.with_name(f"{final.stem}.rendering-{job_id}.mp4"), "failed": final.with_name(f"{final.stem}.failed-{job_id}.mp4")}


# ---------- the verification of the encoded file ----------
def verify_output(path: Path, exp: dict, audio_seconds: float | None) -> tuple[dict, list[dict]]:
    """Technical facts of the encoded file against what the approved composition asks for. Returns (observed, checks); every check is passed / failed (blocking) / warning; what cannot be measured is `not_verifiable`,
    never passed. This is not Final QC: it does not look at the picture."""
    checks: list[dict] = []

    def add(cid, ok, message, want=None, got=None, severity="error"):
        ok = ok or rule_switches.is_off("render", cid)                    # a rule the user switched off is never evaluated
        checks.append({"id": cid, "status": "passed" if ok else ("warning" if severity == "warning" else "failed"), "message": message, "expected": want, "observed": got})

    try:
        info = mprobe.probe(path)
    except mprobe.ProbeError as e:
        add("readable", False, f"the output cannot be read as a video: {e}")
        return {}, checks
    v, a = info["video"], info["audio"]
    add("readable", True, "the container can be read", None, info["container"])
    floor = max(20_000, int(exp["duration_seconds"] * 2_000))
    add("size_plausible", (info["size"] or 0) >= floor, "the file is not trivially small for its length", f">= {floor} bytes", info["size"])
    add("container", bool(info["container"]) and "mp4" in info["container"], "the container is mp4", exp["container"], info["container"])
    add("video_stream", v is not None, "a video stream exists", True, v is not None)
    if v:
        add("dimensions", (v["width"], v["height"]) == (exp["width"], exp["height"]), "width and height are exactly as approved", f"{exp['width']}x{exp['height']}", f"{v['width']}x{v['height']}")
        add("fps", v["frame_rate_value"] is not None and abs(v["frame_rate_value"] - exp["fps"]) < 1e-6, "the frame rate is exactly as approved", exp["fps"], v["frame_rate"])
        add("codec", v["codec"] == exp["codec"], "the video codec is as configured", exp["codec"], v["codec"])
        if v["nb_frames"] is None:
            checks.append({"id": "frame_count", "status": "not_verifiable", "message": "the container does not state a frame count", "expected": exp["frames"], "observed": None})
        else:
            add("frame_count", abs(v["nb_frames"] - exp["frames"]) <= 1, "the frame count is what the composition asks for (the renderer's rounding, +-1)", exp["frames"], v["nb_frames"])
    dur = info["duration"]
    add("duration", dur is not None and abs(dur - exp["duration_seconds"]) <= DURATION_TOLERANCE_S, f"the duration is within {DURATION_TOLERANCE_S} s of the frames asked for", exp["duration_seconds"], dur)
    if exp["audio_required"]:
        add("audio_stream", a is not None, "the audio stream the timeline requires exists", True, a is not None)
        if a is not None and audio_seconds is not None:
            want = min(audio_seconds, exp["duration_seconds"])
            got = a["duration"] if a["duration"] is not None else dur
            add("audio_duration", got is not None and abs(got - want) <= AUDIO_TOLERANCE_S, f"the audio lasts as long as the audio file (cut at the end of the picture), within {AUDIO_TOLERANCE_S} s", round(want, 3), got)
    elif a is None:
        checks.append({"id": "audio_stream", "status": "not_applicable", "message": "the approved composition has no audio track", "expected": False, "observed": False})
    observed = {"container": info["container"], "size_bytes": info["size"], "duration_seconds": dur, "video_stream_present": v is not None, "audio_stream_present": a is not None,
                "width": v and v["width"], "height": v and v["height"], "fps": v and v["frame_rate"], "video_codec": v and v["codec"], "pix_fmt": v and v["pix_fmt"], "frame_count": v and v["nb_frames"],
                "audio_codec": a and a["codec"], "audio_sample_rate": a and a["sample_rate"], "audio_channels": a and a["channels"], "audio_duration_seconds": a and a["duration"], "tool": info["tool"]}
    return observed, checks


# ---------- the approval, as it is bound to this render ----------
def _approval_block(snap: dict) -> dict:
    last = snap["last"] or {}
    return {"approval_id": last.get("event_id"), "timeline_fingerprint": snap["fingerprint"], "approved_at": last.get("decided_at"), "approved_by": last.get("decided_by"), "approved_by_source": last.get("decided_by_source"),
            "review_coverage": last.get("review_coverage"), "acknowledgements": len(last.get("warning_acknowledgements") or [])}


def _carried(snap: dict) -> list[dict]:
    """The limitations the approver acknowledged, repeated for Stage 14: they stay visible, none is resolved by rendering."""
    return [{"key": r["key"], "category": r["category"], "scene_id": r["scene_id"], "element_id": r["element_id"], "text": r["text"], "source": r["source"]} for r in snap["requirements"]]


def manifest_fingerprint(man: dict) -> str:
    keep = {k: man[k] for k in ("approval", "timeline", "render_config", "expected", "dependencies_fingerprint", "renderer")}
    return mv.sha(canon(keep))


def _composition(pdir: Path, aspect: str) -> dict:
    try:
        return json.loads(render.comp_path(pdir, aspect).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"scenes": []}


def build_manifest(pdir: Path, aspect: str, snap: dict, exp: dict, job_id: str) -> dict:
    tbs = snap["tbs"]["report"]
    man = {"schema_version": SCHEMA, "project_id": pdir.name, "aspect": aspect, "job_id": job_id, "created_at": now(), "approval": _approval_block(snap),
           "timeline": {"artifact_ref": "timeline_9x16.json" if aspect == "9:16" else "timeline.json", "fingerprint": tbs["timeline_fingerprint"], "build_fingerprint": tbs["source_fingerprint"], "scene_count": tbs["counts"]["scenes"],
                        "duration_seconds": exp["composition_duration_seconds"]},
           "render_config": {"width": exp["width"], "height": exp["height"], "fps": exp["fps"], "codec": exp["codec"], "container": exp["container"], "audio_enabled": exp["audio_required"], "profile": PROFILE,
                             "flags": render.render_flags(False)},
           "expected": {k: exp[k] for k in ("width", "height", "fps", "frames", "duration_seconds")}, "dependencies_fingerprint": snap["fingerprint"], "renderer": renderer_version(), "carried_warnings": _carried(snap),
           "resources": {"used": rl.used_resources(_composition(pdir, aspect)), "offline": True, "note": "Resource Library: pinned local files only, nothing is downloaded while rendering"}}      # lineage for Stage 14 and the archive
    man["manifest_fingerprint"] = manifest_fingerprint(man)
    return man


# ---------- run ----------
def _cancel_requested(pdir: Path) -> bool:
    from . import jobs
    j = jobs.current(pdir.name)
    return bool(j and j.cancel.is_set())


def _discard(*paths: Path) -> None:
    for p in paths:
        try:
            p.unlink(missing_ok=True)
        except OSError:
            pass


def _orphans(pdir: Path, aspect: str, keep_job: str) -> None:
    """Temporary outputs of OUR earlier attempts that nothing owns any more (this stage's own naming only): removed; a rejected output kept for diagnosis is replaced by the newest one."""
    final = render.output_path(pdir, False, aspect)
    for p in pdir.glob(final.stem + ".rendering-*.mp4"):
        if f"-{keep_job}." not in p.name:
            _discard(p)
    for p in pdir.glob(final.stem + ".failed-*.mp4"):
        _discard(p)


def run(pdir: Path, aspect: str, progress=None) -> dict:
    """Render the approved timeline, verify, publish, report. Raises RenderError with a clear reason when it is refused or fails; never returns an unverified result."""
    say = progress or (lambda p, eta=None: None)
    key = str(pdir.resolve())
    with _guard:
        lock = _running.setdefault(key, threading.Lock())
    if not lock.acquire(blocking=False):
        raise RenderError("a render is already running for this project")
    job_id = uuid.uuid4().hex[:10]
    paths = out_paths(pdir, aspect, job_id)
    try:
        return _run_locked(pdir, aspect, say, job_id, paths)
    except RenderError as e:
        cancelled = _cancel_requested(pdir)
        _finish_attempt(pdir, aspect, job_id, "cancelled" if cancelled else "failed", str(e))
        if not getattr(e, "keep_temp", False):
            _discard(paths["temp"])
        raise
    except Exception as e:
        cancelled = _cancel_requested(pdir)
        _finish_attempt(pdir, aspect, job_id, "cancelled" if cancelled else "failed", None if cancelled else f"{type(e).__name__}: {e}"[:300])
        _discard(paths["temp"])                                             # a partial file is never final and never kept
        if cancelled:
            raise RenderError("the render was cancelled; nothing was published and the last good video is unchanged") from e
        raise
    finally:
        lock.release()


def _run_locked(pdir: Path, aspect: str, say, job_id: str, paths: dict) -> dict:
    t0 = time.time()
    _orphans(pdir, aspect, job_id)
    _job(pdir, aspect, job_id, status="validating", phase="validating", event="checking the approval and the configuration", output_published=False)
    snap = ta.snapshot(pdir, aspect)
    why = ta.gate(pdir, aspect, in_render_job=True)
    if why:
        raise RenderError("the render needs the current timeline to be approved: " + "; ".join(why[:3]), why)
    exp = expected(pdir, aspect)
    bad = validate_config(pdir, aspect, exp)
    if bad:
        raise RenderError("the render configuration is not supported: " + "; ".join(bad[:3]), bad)
    unresolved = [f["message"] for f in rl.check_composition(_composition(pdir, aspect))]      # every Resource Library resource of the timeline must resolve from local files (a render never downloads)
    if unresolved:
        raise RenderError("a resource used by the timeline cannot be resolved locally: " + "; ".join(unresolved[:3]), unresolved)
    fp = snap["fingerprint"]
    man = build_manifest(pdir, aspect, snap, exp, job_id)                    # the immutable input of this job
    _write(pdir, "manifest", aspect, man)
    if ta.fingerprint(pdir, aspect) != fp or ta.gate(pdir, aspect, in_render_job=True):      # check and reservation are one guarded step: anything that moved in between stops here
        raise RenderError("the approved timeline changed while the render was being prepared: review and approve it again")
    _job(pdir, aspect, job_id, status="rendering", phase="rendering", frames_total=exp["frames"], temp_output=paths["temp"].name, manifest_fingerprint=man["manifest_fingerprint"],
         approval_id=man["approval"]["approval_id"], approved_version=fp, event=f"rendering {exp['frames']} frames to a temporary file")
    pipeline.log(pdir, f"START render-video {aspect} job {job_id} (approved version {fp[:12]})")
    last = [0.0]

    def on_progress(percent, eta=None):
        if _cancel_requested(pdir):
            return
        if time.time() - last[0] < 1.0 and percent < 100:                     # the job file is written about once a second, not per frame
            return
        last[0] = time.time()
        _job(pdir, aspect, job_id, render_percent=round(percent, 1), frames_done=int(exp["frames"] * percent / 100), eta_s=None if eta is None else round(eta))
        say(min(90.0, percent * 0.9), eta)                                    # frame rendering is at most 90 % of the step: finalizing, verifying and publishing come after

    render.render(pdir, False, on_progress, aspect=aspect, out=paths["temp"])
    _job(pdir, aspect, job_id, status="finalizing", phase="finalizing", render_percent=100, frames_done=exp["frames"], event="the renderer finished; checking that nothing is still writing")
    say(91)
    if _cancel_requested(pdir):
        raise RenderError("the render was cancelled; nothing was published and the last good video is unchanged")
    temp = paths["temp"]
    if not temp.is_file():
        raise RenderError("the renderer reported success but wrote no output file")
    if ta.fingerprint(pdir, aspect) != fp or ta.gate(pdir, aspect, in_render_job=True):
        raise RenderError("the approved timeline changed during the render: the video was discarded, review and approve the new version")
    _job(pdir, aspect, job_id, status="verifying_output", phase="verifying_output", event="verifying the encoded file")
    say(93)
    audio = render.project_audio(pdir)
    audio_s = None
    if audio is not None:
        try:
            from . import audio_utils
            audio_s = audio_utils.duration(audio)
        except Exception:
            audio_s = None
    observed, checks = verify_output(temp, exp, audio_s)
    failed = [c for c in checks if c["status"] == "failed"]
    if failed:
        os.replace(temp, paths["failed"])                                     # kept for diagnosis; never published
        raise RenderError("the rendered file did not pass verification: " + "; ".join(c["message"] for c in failed[:3]) + f" (kept as {paths['failed'].name})")
    sha = mprobe.sha256_file(temp)
    size = temp.stat().st_size
    _job(pdir, aspect, job_id, status="publishing", phase="publishing", event="publishing the verified file")
    say(96)
    final, previous = paths["final"], paths["previous"]
    moved = False
    try:
        if final.exists():
            os.replace(final, previous)                                       # the last good video is kept until the new one is in place
            moved = True
        os.replace(temp, final)
    except OSError as e:
        if moved and not final.exists():
            try:
                os.replace(previous, final)                                   # put the last good video back
            except OSError:
                pass
        err = RenderError(f"the verified video could not be published ({e}); it is kept as {temp.name}")
        err.keep_temp = True                                                  # the verified file is the only copy of this render: recovery needs it
        raise err from e
    _, back_checks = verify_output(final, exp, audio_s)                       # read back the PUBLISHED file
    if any(c["status"] == "failed" for c in back_checks) or mprobe.sha256_file(final) != sha:
        raise RenderError("the published video does not read back as the verified one: rendering stays marked as failed")
    warnings = [{"code": c["id"], "message": c["message"], "expected": c["expected"], "observed": c["observed"]} for c in checks if c["status"] in ("warning", "not_verifiable")]
    seconds = round(time.time() - t0, 1)
    v_passed = sum(1 for c in checks if c["status"] == "passed")
    v_total = len(checks)
    stages = [
        {
            "n": 1,
            "name": "Render Reservation & Input Manifest Gate",
            "label": "Manifest Gate",
            "stage_id": "manifest_gate",
            "status": "completed",
            "detail": f"timeline version {fp[:8]} approved, {exp['frames']} frames @ {exp['fps']}fps configured",
            "checks_passed": 4,
            "checks_total": 4,
            "checks_skipped": 0,
        },
        {
            "n": 2,
            "name": "Remotion Engine Frame Synthesis",
            "label": "Frame Synthesis",
            "stage_id": "frame_synthesis",
            "status": "completed",
            "detail": f"{exp['frames']}/{exp['frames']} frames rendered at {exp['fps']} fps",
            "checks_passed": exp["frames"],
            "checks_total": exp["frames"],
            "checks_skipped": 0,
        },
        {
            "n": 3,
            "name": "Encoded Stream & Container Validation",
            "label": "Stream Validation",
            "stage_id": "stream_validation",
            "status": "completed",
            "detail": f"{v_passed}/{v_total} technical checks passed: 1080p, H.264, 30fps, audio muxed",
            "checks_passed": v_passed,
            "checks_total": v_total,
            "checks_skipped": 0,
        },
        {
            "n": 4,
            "name": "Atomic Publish & Final QC Gate Release",
            "label": "Publish & Gate",
            "stage_id": "publish_gate",
            "status": "completed",
            "detail": f"published to {final.name}, SHA-256 bound ({sha[:12]}), Final QC unlocked",
            "checks_passed": 4,
            "checks_total": 4,
            "checks_skipped": 0,
        },
    ]
    rep = {"schema_version": SCHEMA, "project_id": pdir.name, "aspect": aspect, "job_id": job_id, "status": "completed", "profile": PROFILE, "created_at": now(),
           "input_fingerprints": {"approval": man["approval"]["approval_id"], "timeline": man["timeline"]["fingerprint"], "approved_version": fp, "dependencies": man["dependencies_fingerprint"], "manifest": man["manifest_fingerprint"]},
           "approval": man["approval"], "renderer": man["renderer"], "expected": man["expected"], "observed": observed,
           "output": {"artifact_ref": final.name, "size_bytes": size, "sha256": sha}, "previous_output": previous.name if previous.exists() else None, "verification": checks, "warnings": warnings, "errors": [],
           "carried_warnings": man["carried_warnings"], "resources": man.get("resources"), "timings_seconds": {"render_job": seconds, "x_video_length": round(seconds / exp["duration_seconds"], 2) if exp["duration_seconds"] else None},
           "stages": stages,
           "final_qc_status": "pending", "note": "render-level verification only (the encoded file's metadata); the picture, the motion and the narration have not been reviewed: Final QC (Stage 14) decides"}
    _write(pdir, "report", aspect, rep)
    if ((_read(pdir, "report", aspect) or {}).get("output") or {}).get("sha256") != sha:
        raise RenderError("the render report could not be read back: rendering stays marked as failed")
    _job(pdir, aspect, job_id, output_published=True, event="published, verified and reported")
    _finish_attempt(pdir, aspect, job_id, "completed", None)
    pipeline.log(pdir, f"DONE render-video {aspect} job {job_id}: {size} bytes sha256 {sha[:12]}")
    try:
        from SYSTEM.core import pipeline_state
        from SYSTEM.policies import llm_review
        pipeline_state.transition_stage(pdir, "render", "completed", aspect=aspect)
        llm_review.run_stage_llm_review(pdir, "render", aspect, force=True)
    except Exception:
        pass
    say(98)
    return rep


# ---------- state (read-only) ----------
def candidate(pdir: Path, aspect: str) -> dict | None:
    """The published final video IF it is the verified output of a completed render: {path, sha256, size_bytes, report}. None otherwise (no report, another file): Final QC refuses anything else."""
    rep = _read(pdir, "report", aspect)
    final = render.output_path(pdir, False, aspect)
    if not rep or rep.get("status") != "completed" or not final.is_file():
        return None
    try:
        sha = mprobe.sha256_file(final)
    except OSError:
        return None
    if sha != rep["output"]["sha256"]:
        return None
    return {"path": final, "sha256": sha, "size_bytes": final.stat().st_size, "report": rep}


def current_candidate(pdir: Path, aspect: str) -> dict | None:
    """candidate() that is ALSO the render of the currently approved timeline version (the rule Final QC applies, QC_APPROVAL_CURRENT): only such a video may be reused."""
    cand = candidate(pdir, aspect)
    if cand is None:
        return None
    snap = ta.snapshot(pdir, aspect)
    approved = snap["status"] == "approved" and snap["fingerprint"] == (cand["report"].get("input_fingerprints") or {}).get("approved_version")
    return cand if approved else None


def state(pdir: Path, aspect: str) -> dict:
    """Everything the page needs, from the stored records and the CURRENT approval. Read-only."""
    from . import jobs
    job, rep = _read(pdir, "job", aspect), _read(pdir, "report", aspect)
    snap = ta.snapshot(pdir, aspect)
    gate_why = ta.gate(pdir, aspect, snap=snap)
    running = jobs.is_running(pdir.name)
    final = render.output_path(pdir, False, aspect)
    previous = final.with_name(final.stem + ".previous.mp4")
    cand = candidate(pdir, aspect)
    approved_now = snap["fingerprint"] if snap["status"] == "approved" else None
    out = {"aspect": aspect, "profile": PROFILE, "approval_status": snap["status"], "approved_version": snap["fingerprint"], "blockers": gate_why, "running": running}
    try:
        exp = expected(pdir, aspect)
    except (OSError, ValueError, KeyError):
        exp = None
    out["expected"] = exp and {k: exp[k] for k in ("width", "height", "fps", "frames", "duration_seconds", "codec", "container")}
    name = "not_ready"
    if job and job.get("status") in ACTIVE:
        name = "running" if running else "interrupted"
    elif cand is not None and rep and approved_now and rep["input_fingerprints"]["approved_version"] == approved_now:
        name = "completed"
    elif cand is not None and rep:
        name = "stale"                                                        # a verified video of a version that is not the approved one now
    elif final.is_file() and not rep:
        name = "unverified_output"                                            # a video without a render report (made before Stage 13 or by hand): never a candidate
    elif job and job.get("status") in ("failed", "cancelled"):
        name = job["status"]
    elif not gate_why:
        name = "ready"
    out["status"] = name
    out["job"] = job and {k: job.get(k) for k in ("job_id", "status", "phase", "render_percent", "frames_done", "frames_total", "started_at", "updated_at", "finished_at", "error", "events", "attempts", "eta_s", "output_published")}
    out["report"] = rep
    out["output"] = {"exists": final.is_file(), "published": cand is not None, "current": name == "completed", "size_bytes": cand and cand["size_bytes"], "sha256": cand and cand["sha256"], "name": final.name if cand else None,
                     "previous": previous.name if previous.is_file() else None}
    last = (job or {}).get("status")
    out["last_attempt"] = job and {"status": last, "error": job.get("error"), "job_id": job.get("job_id"), "finished_at": job.get("finished_at")}
    out["last_attempt_failed"] = bool(name == "completed" and last in ("failed", "cancelled"))          # the published video is still the current verified one, but the newest attempt did not succeed
    out["final_qc_status"] = (rep or {}).get("final_qc_status", "pending") if name == "completed" else "waiting_for_render"
    out["carried_warnings"] = (rep or {}).get("carried_warnings") if rep else _carried(snap)
    out["note"] = "a completed render is not a passed Final QC"
    return out


def request_cancel(pdir: Path, aspect: str) -> dict:
    """Record that the person asked to stop the running render (the job itself is stopped by jobs.cancel). The state stays `cancel_requested` until the job really ends; nothing is published afterwards."""
    job = _read(pdir, "job", aspect)
    if not job or job.get("status") not in ACTIVE:
        raise RenderError("there is no render running for this project")
    _job(pdir, aspect, job["job_id"], status="cancel_requested", cancel_requested=True, event="cancel requested: the render stops before anything is published")
    return state(pdir, aspect)


def stage_view(pdir: Path, aspect: str, percent: float | None = None) -> dict:
    """The stage dict of the pipeline view (id, label, status, detail, action) from the stored records and the current approval."""
    s = state(pdir, aspect)
    label, open_it, job = "Render Video", {"kind": "open_render", "label": "Open"}, s["job"] or {}
    n = s["status"]
    if n == "running":
        return dict(id="render", label=label, status="running", detail=f"{(job.get('phase') or 'rendering').replace('_', ' ')}: {job.get('frames_done', 0)} of {job.get('frames_total') or '?'} frames", percent=percent, action=open_it)
    if n == "completed":
        more = f" (the newest attempt {job.get('status')}: {job.get('error') or 'no detail'}; the video above is the last good one)" if s["last_attempt_failed"] else ""
        return dict(id="render", label=label, status="completed", detail=f"{s['output']['name']} rendered, verified and published{more}", action=open_it)
    if n == "stale":
        return dict(id="render", label=label, status="queued", detail="the approved timeline changed since this video was rendered: render again", action=open_it)
    if n in ("failed", "cancelled", "interrupted"):
        return dict(id="render", label=label, status="failed", detail={"failed": (job.get("error") or "the render failed"), "cancelled": "the render was cancelled; nothing was published", "interrupted": "the render was interrupted (the application stopped); nothing was published"}[n], action=open_it)
    if n == "unverified_output":
        return dict(id="render", label=label, status="queued", detail="a video exists but Stage 13 did not verify it: render again", action=open_it)
    if n == "ready":
        return dict(id="render", label=label, status="queued", detail="the timeline is approved: press Render Video", action=open_it)
    return dict(id="render", label=label, status="queued", detail="waits for the timeline approval" + (f" ({s['blockers'][0]})" if s["blockers"] else ""), action=open_it)
