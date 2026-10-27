"""Final QC (roadmap improvements/Final_QC_Complete_Roadmap), Stage 14: judges the ACTUAL rendered video file, not the timeline JSON and not the render job's exit status. It is read-only: it never renders, edits,
repairs or deletes the candidate or any upstream artifact and never approves a timeline. The decision about the file is the Final QC LLM review's (llm_decide); nobody watches the video.

What it does (14 internal stages; checks of one module, shown as a compact row on the page): 1 run initialization, 2 artifact and manifest resolution, 3 provenance and approval gate, 4 file integrity, 5 stream and metadata
probe, 6 video decode, 7 duration and frame accounting, 8 audio integrity, 9 audio/video synchronization, 10 frame quality, 11 scene boundaries and transitions, 12 upstream reconciliation, 13 LLM review, 14 report and
delivery gate. The candidate is the verified output of Stage 13 (`render_video.candidate`): a video without a render report is never QC'd as current.
Honesty rules: every check is passed / warning / failed / not_run / not_applicable / requires_review, and what was NOT measured is said (`not_run`, with the reason), never passed. Nobody watches the playback: the status can
only become `passed` after the Final QC LLM review approved this exact file (its hash) from the report and its measurements, and what was not measured stays listed. Upstream limitations (stand-ins, elements not drawn, the audio tail) are
carried in and stay visible; "accepted" is a resolution status, not proof the visual is right. Status: blocked > failed > needs_review > passed_with_warnings > passed; one blocker is never outweighed by passes.
Evidence of the media checks is cached per candidate hash + rules version + profile + tool versions: the same file is not decoded twice, a changed file invalidates everything media-dependent.
Files: `final_qc_report[_9x16].json`, `final_qc_review[_9x16].json` (append-only LLM decisions), `final_qc_frames[_9x16]/` (sampled frames)."""
from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
import uuid
from pathlib import Path

from SYSTEM.policies import rule_switches
from . import asset_collection, media_probe as mprobe, motion_planning as mp, motion_validation as mv, render, render_video as rv, resource_library as rl, store
from . import timeline_approval as ta
from . import timeline_build as tb

SCHEMA = "1.0"
VERSION = 1
RULES_VERSION = "2"                                  # the meaning of the rules: part of every cache key
PROFILES = {                                          # named profiles with recorded parameters (roadmap 10); only `standard` is implemented, and it says so
    "standard": {"decode": "full", "black_min_s": 0.5, "black_pix_th": 0.10, "freeze_min_s": 3.0, "freeze_noise": 0.001, "clip_db": -0.1, "silent_db": -50.0, "silence_min_s": 2.0, "sample_fractions": (0.12, 0.5, 0.9),
                 "frame_width": 480, "blank_std": 2.0, "empty_detail_pct": 0.5, "static_diff": 0.5, "static_scene_min_s": 3.0, "av_offset_warn_s": 0.04, "av_offset_error_s": 0.25, "audio_tail_warn_s": 0.5},
}
STAGES = (
    ("run_initialization", "Run Initialization"), ("artifact_resolution", "Artifact & Manifest"), ("provenance_gate", "Provenance & Approval"), ("file_integrity", "File Integrity"),
    ("stream_metadata", "Stream & Metadata"), ("video_decode", "Video Decode"), ("duration_frames", "Duration & Frames"), ("audio_integrity", "Audio Integrity"), ("av_sync", "A/V Sync"),
    ("frame_quality", "Frame Quality"), ("scene_boundaries", "Scenes & Transitions"), ("upstream_reconciliation", "Upstream Reconciliation"), ("llm_review", "LLM Review"), ("report_gate", "Report & Delivery Gate"),
)
MEDIA_STAGES = ("file_integrity", "stream_metadata", "video_decode", "duration_frames", "audio_integrity", "av_sync", "frame_quality", "scene_boundaries")
OK_STATUS = ("passed", "passed_with_warnings")
DECISIONS = ("approved", "approved_with_accepted_risks", "changes_required", "cannot_determine")
_guard = threading.Lock()
_locks: dict[str, threading.Lock] = {}
_cancel: set[str] = set()


class QcError(Exception):
    """The QC could not run reliably, or a request is refused (a message for the user). `code` = the API error code."""

    def __init__(self, message: str, code: str = "qc_refused") -> None:
        super().__init__(message)
        self.code = code


class Cancelled(Exception):
    pass


def names(aspect: str) -> dict[str, str]:
    sfx = "_9x16" if aspect == "9:16" else ""
    return {"report": f"final_qc_report{sfx}.json", "review": f"final_qc_review{sfx}.json", "frames": f"final_qc_frames{sfx}"}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


canon, sha = mv.canon, mv.sha


def _rw_read(pdir: Path, key: str, aspect: str):
    with store._info_lock(pdir):
        return mp._read(pdir / names(aspect)[key])


def _rw_write(pdir: Path, key: str, aspect: str, data) -> None:
    f = pdir / names(aspect)[key]
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    with store._info_lock(pdir):
        os.replace(tmp, f)


def cancel(pdir: Path) -> None:
    """Cooperative: the run stops before its next stage and writes no report (an earlier valid report is kept)."""
    _cancel.add(pdir.name)


def _check_cancel(pdir: Path) -> None:
    if pdir.name in _cancel:
        raise Cancelled()


# ---------- the checks ----------
class Q:
    """Checks per stage. A check that is not `passed` is a finding (stable id: rule + scene + target)."""

    def __init__(self) -> None:
        self.checks: list[dict] = []
        self.stage = ""

    def add(self, rule: str, status: str, severity: str, message: str, scene: str | None = None, target: str | None = None, evidence: dict | None = None, action: str = "", resolution: str = "unresolved") -> dict:
        fid = re.sub(r"[^A-Za-z0-9._:-]+", "-", f"{rule}:{scene or 'video'}:{target or '-'}")
        if status not in ("passed", "not_applicable") and rule_switches.is_off("qc", rule):        # a rule the user switched off is never evaluated: said, never counted as a pass
            status, severity, message = "not_applicable", "info", f"switched off by the user: {rule}"
        c = {"finding_id": fid, "rule_id": rule, "stage_id": self.stage, "status": status, "severity": severity, "message": message, "scene_id": scene, "target": target, "evidence": evidence or {},
             "recommended_action": action, "resolution": "none" if status in ("passed", "not_applicable") else resolution}
        self.checks.append(c)
        return c

    def ok(self, rule: str, message: str, **kw) -> dict:
        return self.add(rule, "passed", "info", message, **kw)


def _assets_provenance(q: Q, pdir: Path) -> None:
    """Real photos/clips Asset Collection put into the video: their source, licence and files must be intact (blocker otherwise); assets whose rights are not established are judged by the Final QC LLM review."""
    if not (assets := asset_collection.load_manifest(pdir).get("assets")):
        return
    found = asset_collection.check_assets(pdir)
    errs, review = [f for f in found if f["severity"] == "error"], [f for f in found if f["severity"] == "review"]
    q.add("QC_ASSETS_PROVENANCE", "failed" if errs else "passed", "blocker" if errs else "info",
          "; ".join(f["message"] for f in errs[:3]) if errs else f"{len(assets)} real asset(s): source, licence and files are unchanged since collection",
          evidence={"assets": [a["asset_id"] for a in assets]}, action="run Asset Collection again" if errs else "")
    if review:
        q.add("QC_ASSET_RIGHTS_REVIEW", "requires_review", "review", "; ".join(f["message"] for f in review),
              evidence={"assets": [f["asset_id"] for f in review]}, action="confirm that these assets may be used in this video, or replace them")


def _run(cmd: list[str], timeout: int = 900) -> tuple[int, str]:
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def _excerpt(text: str, n: int = 300) -> str:
    return " | ".join(x.strip() for x in text.strip().splitlines()[-4:])[:n]


# ---------- the scenes (from the built timeline: the approved one) ----------
def scenes_of(pdir: Path, aspect: str) -> tuple[list[dict], list[dict], int]:
    T = tb.timeline(pdir, aspect) or {}
    tracks = T.get("tracks") or []
    clips = tracks[1].get("items", []) if len(tracks) > 1 else []
    return clips, T.get("transitions", []), (T.get("profile") or {}).get("fps") or 30


def sample_plan(clips: list[dict], transitions: list[dict], total_frames: int, prof: dict) -> list[dict]:
    """Which frames: first and last, every scene at fractions of its interval, a frame just before and just after every scene boundary and the start / middle / end of every transition window. Chosen by frame arithmetic only;
    short scenes are deduplicated (a frame is sampled once)."""
    out: dict[int, dict] = {}

    def add(frame: int, scene: str | None, kind: str):
        f = max(0, min(total_frames - 1, frame))
        out.setdefault(f, {"frame": f, "scene_id": scene, "kind": kind})

    add(0, clips[0]["scene_id"] if clips else None, "first")
    add(total_frames - 1, clips[-1]["scene_id"] if clips else None, "last")
    for c in clips:
        a, b = c["start_frame"], c["end_frame"]
        for k, frac in zip(("entry", "mid", "pre_exit"), prof["sample_fractions"]):
            add(a + int((b - a) * frac), c["scene_id"], k)
        add(b - 2, c["scene_id"], "before_cut")
        add(b + 1, None, "after_cut")
    for t in transitions:
        a, b = t["start_frame"], t["end_frame"]
        for k, f in (("transition_start", a), ("transition_mid", (a + b) // 2), ("transition_end", b - 1)):
            add(f, t["to_scene"], k)
    return sorted(out.values(), key=lambda s: s["frame"])


def grab(video: Path, t: float, dest: Path, width: int) -> bool:
    rc, _ = _run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "4", "-y", str(dest)], 120)
    return rc == 0 and dest.is_file() and dest.stat().st_size > 0


def measure(path: Path) -> dict:
    import numpy as np
    from PIL import Image
    try:
        with Image.open(path) as im:
            g = np.asarray(im.convert("L"), dtype="float32")
            small = np.asarray(im.convert("L").resize((64, 36)), dtype="float32")
            # detail: % of pixels on an edge. A gradient or vignette background has a high std but almost no edges (0-0.3 %); any drawn content has 1.5 % or more.
            edge = np.maximum(np.abs(np.diff(g, axis=1))[:-1, :], np.abs(np.diff(g, axis=0))[:, :-1])
            return {"decode_ok": True, "width": im.width, "height": im.height, "mean": round(float(g.mean()), 1), "std": round(float(g.std()), 1),
                    "detail": round(float((edge > 12).mean() * 100), 2), "_small": small}
    except Exception as e:
        return {"decode_ok": False, "width": None, "height": None, "mean": None, "std": None, "detail": None, "error": str(e)[:100], "_small": None}


# ---------- run ----------
def run(pdir: Path, aspect: str, progress=None, profile: str = "standard") -> dict:
    """Run (or reuse the evidence of) Final QC of the current candidate and write the report. One run per project at a time; a changed candidate or rules version recomputes the media checks."""
    say = progress or (lambda p, eta=None: None)
    if profile not in PROFILES:
        raise QcError(f"profile {profile!r} is not implemented (only: {', '.join(PROFILES)})", "invalid_request")
    key = str(pdir.resolve())
    with _guard:
        lock = _locks.setdefault(key, threading.Lock())
    if not lock.acquire(blocking=False):
        raise QcError("a Final QC run is already active for this project", "qc_running")
    _cancel.discard(pdir.name)
    try:
        rep = _run_locked(pdir, aspect, say, profile)
        from . import llm_review
        llm_review.run_stage_llm_review(pdir, "qc", aspect)
        return rep
    except Cancelled as e:
        raise QcError("Final QC was cancelled before it finished: no report was written, an earlier valid report is unchanged", "cancelled") from e
    finally:
        _cancel.discard(pdir.name)
        lock.release()


def _run_locked(pdir: Path, aspect: str, say, profile: str) -> dict:
    prof = PROFILES[profile]
    t0 = time.time()
    q = Q()
    prev = _rw_read(pdir, "report", aspect) or {}
    ev_prev = prev.get("evidence", {}) if prev.get("rules_version") == RULES_VERSION and prev.get("profile") == profile else {}
    evidence: dict = {}
    records: list[dict] = []

    def stage(sid: str) -> int:
        q.stage = sid
        return len(q.checks)

    def close(sid: str, start: int, cache: dict | None = None, skipped: str | None = None) -> None:
        mine = [c for c in q.checks[start:] if c["stage_id"] == sid]
        bad = [c for c in mine if c["status"] == "failed" and c["severity"] in ("blocker", "error")]
        warn = [c for c in mine if c["status"] in ("warning", "requires_review", "not_run")]
        status = "skipped" if skipped else "failed" if bad else "warning" if warn else "completed"
        # name / detail / checks_passed / checks_total are what the Subtasks tab, the stage gate and the LLM step check read: a warning step must say WHAT it warns about
        open_ = [c for c in mine if c["status"] != "passed"]
        detail = skipped or ("; ".join(f"{c['rule_id']}: {c['message']}"[:240] for c in open_[:3]) + (f" (+{len(open_) - 3} more)" if len(open_) > 3 else "") if open_ else f"{len(mine)} check(s) passed")
        records.append({"n": [s[0] for s in STAGES].index(sid) + 1, "stage_id": sid, "label": dict(STAGES)[sid], "name": dict(STAGES)[sid], "status": status, "checks": len(mine), "checks_total": len(mine),
                        "checks_passed": sum(c["status"] == "passed" for c in mine), "findings": [c["finding_id"] for c in open_], "detail": detail, "cache": cache or {"hit": False}})

    say(3)
    s = stage("run_initialization")
    qc_run_id = "qc_" + uuid.uuid4().hex[:10]
    q.ok("QC_RUN_STARTED", f"profile {profile}, rules version {RULES_VERSION}", evidence={"profile": {k: (list(v) if isinstance(v, tuple) else v) for k, v in prof.items()}})
    close("run_initialization", s)

    # 2 artifact and manifest resolution
    s = stage("artifact_resolution")
    cand = rv.candidate(pdir, aspect)
    manifest = rv._read(pdir, "manifest", aspect)
    rrep = rv._read(pdir, "report", aspect)
    final = render.output_path(pdir, False, aspect)
    if cand is None:
        why = ("the final video exists but has no verified render report (it was not made by Stage 13, or its bytes changed since): QC does not treat it as current" if final.is_file() and not rrep
               else "there is no rendered final video yet: run Render Video")
        q.add("QC_CANDIDATE_RESOLVED", "failed", "blocker", why, action="run Render Video from its page after the timeline is approved")
    else:
        q.ok("QC_CANDIDATE_RESOLVED", f"{final.name}, {cand['size_bytes']} bytes", evidence={"sha256": cand["sha256"]})
    if cand is not None and manifest is None:
        q.add("QC_MANIFEST_PRESENT", "failed", "blocker", "the render manifest is missing: the expected settings are unknown and are not guessed", action="render again")
    elif manifest is not None:
        q.ok("QC_MANIFEST_PRESENT", "the render manifest is present", evidence={"manifest_fingerprint": manifest.get("manifest_fingerprint")})
    close("artifact_resolution", s)

    # 3 provenance and approval
    s = stage("provenance_gate")
    snap = None
    if cand is not None and manifest is not None and rrep is not None:
        _check_cancel(pdir)
        snap = ta.snapshot(pdir, aspect)
        same = manifest.get("manifest_fingerprint") == rv.manifest_fingerprint(manifest) == rrep.get("input_fingerprints", {}).get("manifest")
        q.add("QC_MANIFEST_MATCHES_RENDER", "passed" if same else "failed", "info" if same else "blocker", "the render manifest is the one the render report names" if same else "the render manifest and the render report do not belong together")
        approved = snap["status"] == "approved" and snap["fingerprint"] == rrep["input_fingerprints"]["approved_version"]
        q.add("QC_APPROVAL_CURRENT", "passed" if approved else "failed", "info" if approved else "blocker",
              "the render was made from the timeline version that is approved now" if approved else "the approved timeline changed (or its approval was withdrawn) after this video was rendered: the video is stale",
              evidence={"approved_now": snap["fingerprint"], "rendered_from": rrep["input_fingerprints"]["approved_version"], "approval_status": snap["status"]}, action="" if approved else "return to Timeline Approval, then render again")
        a0 = (cand["path"].stat().st_size, cand["path"].stat().st_mtime_ns)
        time.sleep(0.2)
        writing = (rv._read(pdir, "job", aspect) or {}).get("status") in rv.ACTIVE
        stable = a0 == (cand["path"].stat().st_size, cand["path"].stat().st_mtime_ns) and not writing
        q.add("QC_CANDIDATE_STABLE", "passed" if stable else "failed", "info" if stable else "blocker", "the file did not change between reads and no render is writing" if stable else "the file is still being written: wait for the render to finish")
    _assets_provenance(q, pdir)
    close("provenance_gate", s)
    if any(c["status"] == "failed" and c["severity"] == "blocker" for c in q.checks):
        q.stage = ""
        for sid, _ in STAGES[3:12]:
            q.stage = sid
            close(sid, len(q.checks), skipped="an earlier stage found a blocker: nothing is measured on a video that is missing, stale or still being written")
        return _finish(pdir, aspect, q, records, evidence, qc_run_id, profile, cand, manifest, rrep, snap, t0, blocked=True)

    # 4-11 media checks (cached by candidate hash)
    video, exp, cfg = cand["path"], manifest["expected"], manifest["render_config"]
    tools = {"ffprobe": mprobe.tool_version("ffprobe"), "ffmpeg": mprobe.tool_version("ffmpeg")}
    clips, transitions, fps = scenes_of(pdir, aspect)
    base_key = [cand["sha256"], RULES_VERSION, profile, {k: (list(v) if isinstance(v, tuple) else v) for k, v in prof.items()}, tools, manifest["manifest_fingerprint"],
                [(c["scene_id"], c["start_frame"], c["end_frame"]) for c in clips], [(t["start_frame"], t["end_frame"]) for t in transitions]]
    data: dict = {}
    folder = pdir / names(aspect)["frames"]
    for i, sid in enumerate(MEDIA_STAGES):
        key = sha(canon([sid, base_key]))
        hit = ev_prev.get(sid)
        s = stage(sid)
        say(8 + 70 * i / len(MEDIA_STAGES))
        _check_cancel(pdir)
        usable = bool(hit and hit.get("key") == key)
        if usable and sid == "frame_quality":
            usable = all((folder / x["file"]).is_file() for x in hit.get("data", {}).get("samples", []) if x.get("file"))
        if usable:
            q.checks.extend(hit["checks"])
            data[sid] = hit.get("data", {})
            evidence[sid] = hit
            close(sid, s, cache={"hit": True, "reason": "the same file, rules, profile and tools: evidence reused"})
            continue
        before = len(q.checks)
        data[sid] = _media_stage(sid, q, pdir, aspect, video, cand, exp, cfg, clips, transitions, fps, prof, data, rrep) or {}
        evidence[sid] = {"key": key, "checks": q.checks[before:], "data": data[sid]}
        close(sid, s, cache={"hit": False, "reason": "first run" if not hit else "an input of this stage changed"})

    # 12 upstream reconciliation (always recomputed: it reads the CURRENT upstream reports)
    s = stage("upstream_reconciliation")
    say(82)
    _reconcile(q, pdir, aspect, manifest, snap, data.get("frame_quality", {}).get("samples", []))
    close("upstream_reconciliation", s)
    return _finish(pdir, aspect, q, records, evidence, qc_run_id, profile, cand, manifest, rrep, snap, t0, blocked=False, media=data.get("stream_metadata", {}).get("observed"), tools=tools, say=say)


def _media_stage(sid, q, pdir, aspect, video, cand, exp, cfg, clips, transitions, fps, prof, data, rrep) -> dict | None:
    if sid == "file_integrity":
        sz = cand["size_bytes"]
        q.add("QC_FILE_NONEMPTY", "passed" if sz > 0 else "failed", "info" if sz else "blocker", f"{sz} bytes, sha256 {cand['sha256'][:16]}", evidence={"size_bytes": sz, "sha256": cand["sha256"]})
        same = cand["sha256"] == rrep["output"]["sha256"]
        q.add("QC_FILE_HASH_MATCHES_RENDER", "passed" if same else "failed", "info" if same else "blocker", "the bytes are exactly what Render Video verified and published" if same else "the file differs from the one Render Video verified")
        return {}
    if sid == "stream_metadata":
        try:
            info = mprobe.probe(video)
        except mprobe.ProbeError as e:
            q.add("QC_PROBE_READABLE", "failed", "blocker", f"the file cannot be probed: {e}", action="inspect the render log and render again")
            return {}
        v, a = info["video"], info["audio"]
        q.ok("QC_PROBE_READABLE", f"container {info['container']}, {info['stream_count']} stream(s)")
        if v is None:
            q.add("QC_VIDEO_STREAM", "failed", "blocker", "no video stream")
            return {"observed": {}}
        dim = (v["width"], v["height"]) == (exp["width"], exp["height"])
        q.add("QC_DIMENSIONS", "passed" if dim else "failed", "info" if dim else "error", f"{v['width']}x{v['height']} (expected {exp['width']}x{exp['height']}), aspect {round(v['width'] / v['height'], 4)}",
              evidence={"expected": [exp["width"], exp["height"]], "observed": [v["width"], v["height"]]})
        okfps = v["frame_rate_value"] is not None and abs(v["frame_rate_value"] - exp["fps"]) < 1e-6
        q.add("QC_FRAME_RATE", "passed" if okfps else "failed", "info" if okfps else "error", f"{v['frame_rate']} fps (expected {exp['fps']}/1)", evidence={"expected": exp["fps"], "observed": v["frame_rate"]})
        cfr = mprobe.rate(v["avg_frame_rate"]) == mprobe.rate(v["frame_rate"])
        q.add("QC_CONSTANT_FRAME_RATE", "passed" if cfr else "warning", "info" if cfr else "warning", "constant frame rate (r_frame_rate equals avg_frame_rate)" if cfr else f"the average frame rate {v['avg_frame_rate']} differs from {v['frame_rate']}: variable frame rate?",
              evidence={"r_frame_rate": v["frame_rate"], "avg_frame_rate": v["avg_frame_rate"]})
        q.add("QC_VIDEO_CODEC", "passed" if v["codec"] == cfg["codec"] else "failed", "info" if v["codec"] == cfg["codec"] else "error", f"{v['codec']} (configured {cfg['codec']}), pixel format {v['pix_fmt']}", evidence={"pix_fmt": v["pix_fmt"]})
        want_audio = cfg.get("audio_enabled", True)
        q.add("QC_AUDIO_STREAM", "passed" if (a is not None) == want_audio else "failed", "info" if (a is not None) == want_audio else "blocker",
              f"audio stream {'present' if a else 'absent'} ({'required' if want_audio else 'not required'} by the render manifest)", evidence={"audio": a})
        return {"observed": {"container": info["container"], "duration": info["duration"], "width": v["width"], "height": v["height"], "frame_rate": v["frame_rate"], "video_codec": v["codec"], "pix_fmt": v["pix_fmt"],
                             "nb_frames": v["nb_frames"], "audio_codec": a and a["codec"], "audio_sample_rate": a and a["sample_rate"], "audio_channels": a and a["channels"], "audio_present": a is not None,
                             "audio_duration": a and a["duration"], "audio_start": a and a["start_time"], "video_start": v["start_time"], "size_bytes": info["size"]}}
    if sid == "video_decode":
        rc, text = _run(["ffmpeg", "-v", "info", "-stats", "-i", str(video), "-an", "-vf", f"blackdetect=d={prof['black_min_s']}:pix_th={prof['black_pix_th']},freezedetect=n={prof['freeze_noise']}:d={prof['freeze_min_s']}", "-f", "null", "-"])
        frames = [int(x) for x in re.findall(r"frame=\s*(\d+)", text)]
        bad = [ln for ln in text.splitlines() if re.search(r"(error|invalid data|corrupt|truncat|moov atom|concealing)", ln, re.I) and "detect @" not in ln]
        good = rc == 0 and not bad
        q.add("QC_VIDEO_DECODES", "passed" if good else "failed", "info" if good else "blocker", "every frame decoded (full decode of the video stream)" if good else f"decode problems: {_excerpt(chr(10).join(bad) or text)}",
              evidence={"decoded_frames": frames[-1] if frames else None, "tool_exit_code": rc, "coverage": "full decode"}, action="inspect the render log; render again after fixing the cause")
        blacks = [[float(a), float(b)] for a, b in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", text)]
        starts = [float(x) for x in re.findall(r"freeze_start: ([\d.]+)", text)]
        lasts = [float(x) for x in re.findall(r"freeze_duration: ([\d.]+)", text)]
        end = (data.get("stream_metadata", {}).get("observed") or {}).get("duration") or exp["duration_seconds"]
        return {"decoded_frames": frames[-1] if frames else None, "black": blacks, "freeze": [[a, a + lasts[i] if i < len(lasts) else end] for i, a in enumerate(starts)]}      # a freeze that lasts to the end of the file gets no duration line: it ends with the video
    if sid == "duration_frames":
        dv, obs = data.get("video_decode", {}), data.get("stream_metadata", {}).get("observed") or {}
        dur = obs.get("duration")
        if dur is None:
            q.add("QC_DURATION", "not_run", "review", "the duration could not be read", action="inspect the file")
        else:
            ok = abs(dur - exp["duration_seconds"]) <= rv.DURATION_TOLERANCE_S
            q.add("QC_DURATION", "passed" if ok else "failed", "info" if ok else "error", f"{dur:.3f} s (expected {exp['duration_seconds']} s, tolerance {rv.DURATION_TOLERANCE_S} s)", evidence={"expected": exp["duration_seconds"], "observed": dur})
        for rule, val, label in (("QC_FRAME_COUNT_CONTAINER", obs.get("nb_frames"), "container frame count"), ("QC_FRAME_COUNT_DECODED", dv.get("decoded_frames"), "decoded frame count")):
            if val is None:
                q.add(rule, "not_run", "review", f"the {label} is not available")
            else:
                ok = abs(val - exp["frames"]) <= 1
                q.add(rule, "passed" if ok else "failed", "info" if ok else "error", f"{val} frames (expected {exp['frames']} from the approved timeline, +-1)", evidence={"expected": exp["frames"], "observed": val})
        return {}
    if sid == "audio_integrity":
        obs = data.get("stream_metadata", {}).get("observed") or {}
        if not obs.get("audio_present"):
            need = cfg.get("audio_enabled", True)
            q.add("QC_AUDIO_ANALYSIS", "failed" if need else "not_applicable", "blocker" if need else "info", "no audio stream to analyse")
            return {}
        rc, text = _run(["ffmpeg", "-v", "info", "-i", str(video), "-vn", "-af", f"volumedetect,silencedetect=noise={prof['silent_db']}dB:d={prof['silence_min_s']}", "-f", "null", "-"])
        bad = [ln for ln in text.splitlines() if re.search(r"(error|invalid data|corrupt|truncat)", ln, re.I) and "detect @" not in ln]
        good = rc == 0 and not bad
        q.add("QC_AUDIO_DECODES", "passed" if good else "failed", "info" if good else "blocker", "the whole audio track decoded" if good else f"audio decode problems: {_excerpt(chr(10).join(bad) or text)}")
        mx, mean = re.search(r"max_volume: (-?[\d.]+|-?inf) dB", text), re.search(r"mean_volume: (-?[\d.]+) dB", text)
        peak = float(mx.group(1)) if mx and "inf" not in mx.group(1) else None
        if peak is None:
            q.add("QC_AUDIO_LEVEL", "not_run", "review", "the loudness could not be measured")
        elif peak < prof["silent_db"]:
            q.add("QC_AUDIO_LEVEL", "failed", "error", f"the audio is silent (peak {peak} dB)", evidence={"peak_db": peak})
        elif peak >= prof["clip_db"]:
            q.add("QC_AUDIO_LEVEL", "warning", "warning", f"peak {peak} dB: the audio may be clipped", evidence={"peak_db": peak, "mean_db": mean and float(mean.group(1))})
        else:
            q.ok("QC_AUDIO_LEVEL", f"peak {peak} dB, mean {mean.group(1) if mean else '?'} dB (no clipping)", evidence={"peak_db": peak})
        ss = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", text)]
        se = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", text)]
        aud, vid = obs.get("audio_duration") or obs["duration"], exp["duration_seconds"]
        sil = [[a, se[i] if i < len(se) else aud] for i, a in enumerate(ss)]
        words = _words(pdir, aspect)
        speech_end = words[-1]["end"] if words else None
        for a, b in sil:
            if speech_end is not None and a >= speech_end - 0.05:
                q.add("QC_AUDIO_SILENCE", "passed", "info", f"silence {a:.2f}-{b:.2f} s is after the last spoken word ({speech_end:.2f} s)", target=f"{a:.2f}", evidence={"from": a, "to": b})
            else:
                q.add("QC_AUDIO_SILENCE", "warning", "warning", f"a silence of {b - a:.1f} s from {a:.2f} s inside the narration: intentional pause or missing audio?", target=f"{a:.2f}",
                      evidence={"from": a, "to": b, "speech_ends_at": speech_end}, action="listen to that part (Final QC LLM review)")
        if not sil:
            q.ok("QC_AUDIO_SILENCE", f"no silence of {prof['silence_min_s']:g} s or more")
        if speech_end is not None:
            cut = speech_end > min(aud, vid) + 0.02
            q.add("QC_SPEECH_NOT_CUT", "failed" if cut else "passed", "error" if cut else "info",
                  f"the last spoken word ends at {speech_end:.2f} s; the video lasts {vid:.2f} s, the audio {aud:.2f} s" + (": speech is cut off" if cut else f": {min(aud, vid) - speech_end:.2f} s of margin"), evidence={"speech_end": speech_end, "video": vid, "audio": aud})
        over = aud - vid
        long = over > prof["audio_tail_warn_s"]
        q.add("QC_AUDIO_NOT_BEYOND_VIDEO", "warning" if long else "passed", "warning" if long else "info", f"audio {aud:.3f} s, video {vid:.3f} s ({over:+.3f} s)", evidence={"audio": aud, "video": vid})
        return {"silences": sil, "peak_db": peak, "speech_end": speech_end}
    if sid == "av_sync":
        obs = data.get("stream_metadata", {}).get("observed") or {}
        if obs.get("audio_start") is not None and obs.get("video_start") is not None:
            off = abs(obs["audio_start"] - obs["video_start"])
            st, sev = ("failed", "error") if off > prof["av_offset_error_s"] else ("warning", "warning") if off > prof["av_offset_warn_s"] else ("passed", "info")
            q.add("QC_STREAM_START_OFFSET", st, sev, f"the audio stream starts {off * 1000:.1f} ms from the video stream (container timestamps)", evidence={"audio_start": obs["audio_start"], "video_start": obs["video_start"]})
        else:
            q.add("QC_STREAM_START_OFFSET", "not_run", "review", "the stream start times are not available")
        q.add("QC_AV_CONTENT_SYNC", "requires_review", "review", "whether the narration lands on its scene cannot be measured automatically (no reliable detector): the Final QC LLM review judges it from the evidence", action="judged by the Final QC LLM review")
        q.add("QC_EMPHASIS_ON_WORD", "not_run", "review", "the rendered emphasis moments were not measured against the spoken words (no pixel/audio detector); the planned emphasis times were aligned to words upstream", action="watch the emphasis moments (Final QC LLM review)")
        return {}
    if sid == "frame_quality":
        return _frames(q, pdir, aspect, video, exp, clips, transitions, fps, prof, data)
    if sid == "scene_boundaries":
        return _boundaries(q, clips, transitions, data, prof)
    return None


def _words(pdir: Path, aspect: str) -> list[dict]:
    try:
        return json.loads(render.comp_path(pdir, aspect).read_text(encoding="utf-8")).get("words", [])
    except (OSError, ValueError):
        return []


def _frames(q, pdir, aspect, video, exp, clips, transitions, fps, prof, data) -> dict:
    import numpy as np
    folder = pdir / names(aspect)["frames"]
    folder.mkdir(exist_ok=True)
    samples, keep = [], set()
    for smp in sample_plan(clips, transitions, exp["frames"], prof):
        name = f"{(smp['scene_id'] or 'cut').replace('scene_', 's')}_{smp['kind']}_{smp['frame']:05d}.jpg"
        got, used = False, smp["frame"]
        for back in (0, 1, 2, 3):                                              # a seek onto the very last frames can return nothing: take the nearest frame before it and say which one was used
            used = max(0, smp["frame"] - back)
            got = grab(video, (used + 0.5) / fps, folder / name, prof["frame_width"])
            if got:
                break
        m = measure(folder / name) if got else {"decode_ok": False, "width": None, "height": None, "mean": None, "std": None, "_small": None}
        keep.add(name)
        samples.append({**smp, "frame_used": used if got else None, "time_s": round((used + 0.5) / fps, 3), "file": name if got else None, **m})
    for f in folder.glob("*.jpg"):
        if f.name not in keep:
            f.unlink(missing_ok=True)
    undecoded = [s for s in samples if not s["decode_ok"]]
    q.add("QC_FRAMES_EXTRACTED", "passed" if not undecoded else "failed", "info" if not undecoded else "error", f"{len(samples) - len(undecoded)} of {len(samples)} sampled frames decoded (frame sampling, not playback)",
          evidence={"sampled": len(samples), "undecoded": [s["frame"] for s in undecoded][:10], "coverage": "sampled frames: first, last, every scene at 12 % / 50 % / 90 %, around every cut, every transition start / middle / end"})
    flat = lambda s: s["decode_ok"] and s["std"] is not None and s["std"] < prof["blank_std"]
    for c in clips:
        mine = [s for s in samples if s["scene_id"] == c["scene_id"] and s["kind"] in ("entry", "mid", "pre_exit")]
        stds = [s["std"] for s in mine if s["std"] is not None]
        if mine and all(flat(s) for s in mine):
            q.add("QC_SCENE_NOT_BLANK", "failed", "error", f"{c['scene_id']}: every sampled frame is flat (std < {prof['blank_std']}): the scene looks blank", scene=c["scene_id"], evidence={"frames": [s["frame"] for s in mine], "std": stds},
                  action="route to Motion Generation after looking at the frames")
        elif stds:
            q.ok("QC_SCENE_NOT_BLANK", f"{c['scene_id']}: sampled frames have content (std {min(stds)}-{max(stds)})", scene=c["scene_id"])
        dur = (c["end_frame"] - c["start_frame"]) / fps
        sm = [s["_small"] for s in mine if s["_small"] is not None]
        if len(sm) >= 2 and dur >= prof["static_scene_min_s"]:
            diff = float(np.abs(sm[0] - sm[-1]).mean())
            if diff < prof["static_diff"]:
                q.add("QC_SCENE_SHOWS_CHANGE", "requires_review", "review", f"{c['scene_id']}: the first and last sampled frames of this {dur:.1f} s scene are identical (difference {diff:.2f}): a static scene or a frozen animation?", scene=c["scene_id"],
                      evidence={"difference": round(diff, 2)}, action="watch this scene")
            else:
                q.ok("QC_SCENE_SHOWS_CHANGE", f"{c['scene_id']}: the picture changes within the scene (difference {diff:.1f})", scene=c["scene_id"])
    dec = data.get("video_decode", {})
    scene_at = lambda a: next((c["scene_id"] for c in clips if c["start_frame"] / fps - 0.05 <= a < c["end_frame"] / fps), None)
    for a, b in dec.get("black", []):
        q.add("QC_BLACK_RUN", "warning", "warning", f"black from {a:.2f} s to {b:.2f} s (at least {prof['black_min_s']} s)", scene=scene_at(a), target=f"{a:.2f}", evidence={"from": a, "to": b}, action="look at the frames; a dark scene is not an error")
    if not dec.get("black"):
        q.ok("QC_BLACK_RUN", f"no black longer than {prof['black_min_s']} s")
    for a, b in dec.get("freeze", []):
        q.add("QC_FROZEN_RUN", "warning", "warning", f"the picture does not change from {a:.2f} s to {b:.2f} s (at least {prof['freeze_min_s']:g} s)", scene=scene_at(a), target=f"{a:.2f}", evidence={"from": a, "to": b}, action="watch it: an intended hold is fine")
    if not dec.get("freeze"):
        q.ok("QC_FROZEN_RUN", f"no picture stays unchanged for {prof['freeze_min_s']:g} s or more")
    want = (prof["frame_width"], round(prof["frame_width"] * exp["height"] / exp["width"] / 2) * 2)
    wrong = [s for s in samples if s["decode_ok"] and (s["width"], s["height"]) != want]
    q.add("QC_FRAME_GEOMETRY", "passed" if not wrong else "warning", "info" if not wrong else "warning", "every sampled frame has the shape of the render" if not wrong else f"{len(wrong)} sampled frame(s) have another shape", evidence={"frames": [s["frame"] for s in wrong][:5]})
    return {"samples": [{k: v for k, v in s.items() if k != "_small"} for s in samples]}


def _boundaries(q, clips, transitions, data, prof) -> dict:
    by = {s["frame"]: s for s in data.get("frame_quality", {}).get("samples", [])}
    # A frame with no content: flat, or a background without any drawn edge (a gradient or vignette passes the std test but shows nothing).
    empty = lambda s: s and s["decode_ok"] and ((s["std"] is not None and s["std"] < prof["blank_std"]) or (s.get("detail") is not None and s["detail"] < prof["empty_detail_pct"]))
    for t in transitions:
        win = [by.get(t["start_frame"]), by.get((t["start_frame"] + t["end_frame"]) // 2), by.get(t["end_frame"] - 1)]
        have = [w for w in win if w and w["decode_ok"]]
        cut = [by.get(t["start_frame"] - 2)] + win + [by.get(t["start_frame"] + 1)]            # the frame before the cut, the transition window, the frame after the cut
        blank = sorted({s["frame"] for s in cut if empty(s)})
        if len(have) < 3:
            q.add("QC_TRANSITION_SAMPLED", "not_run", "review", f"{t['from_scene']} -> {t['to_scene']}: {3 - len(have)} of the 3 transition frames could not be sampled", scene=t["from_scene"], target=t["transition_id"], evidence={"window": [t["start_frame"], t["end_frame"]]})
        elif blank:
            q.add("QC_TRANSITION_NOT_BLANK", "warning", "warning", f"{t['from_scene']} -> {t['to_scene']} ({t['type']}): {len(blank)} frame(s) at the cut show no content (frames {blank}): the scenes fade out/in to an empty background",
                  scene=t["from_scene"], target=t["transition_id"], evidence={"frames": blank, "detail": {s["frame"]: s.get("detail") for s in cut if s}},
                  action="route to Motion Generation: the scenes must stay visible through the timeline transition (no whole-scene fade)")
        else:
            q.ok("QC_TRANSITION_NOT_BLANK", f"{t['from_scene']} -> {t['to_scene']} ({t['type']}, {t['applied_frames']} f): the window has content at start, middle and end", scene=t["from_scene"], target=t["transition_id"])
    first = by.get(0)
    good = bool(first and first["decode_ok"])
    q.add("QC_FIRST_FRAME", "passed" if good else "not_run", "info" if good else "review", "the first frame decodes" if good else "the first frame was not sampled")
    q.add("QC_SCENE_ORDER_AND_COVERAGE", "requires_review", "review", f"all {len(clips)} scenes were sampled in timeline order; that the right content is in the right scene is judged by the Final QC LLM review (frames below)", evidence={"scenes": [c["scene_id"] for c in clips]})
    q.add("QC_TRANSITION_SMOOTHNESS", "requires_review", "review", "how smooth each transition looks is subjective and cannot be established from stills", action="watch the transitions (Final QC LLM review)")
    return {}


def _resource_lineage(q: Q, manifest: dict) -> None:
    """The Resource Library resources the render used (recorded in the render manifest): each must still be in the registry, verified and at the pinned hash it was rendered with.
    A resource that changed since the render means the video was made from other files than the registry now holds; the notices of what was used are listed for the archive."""
    used = ((manifest or {}).get("resources") or {}).get("used")
    if used is None:
        q.add("QC_RESOURCE_LINEAGE", "not_run", "info", "this render predates the resource manifest: resource lineage cannot be checked", action="render again to record it")
        return
    if not used:
        q.ok("QC_RESOURCE_LINEAGE", "the video uses no Resource Library resource (nothing to trace)")
        return
    reg = {e.resource_id: e for e in rl.load()}
    bad = []
    for u in used:
        e = reg.get(u["resource_id"])
        if e is None:
            bad.append(f"{u['resource_id']}: no longer in the registry")
        elif rl.effective_status(e) != "verified":
            bad.append(f"{u['resource_id']}: now {rl.effective_status(e)}")
        elif e.integrity.sha256 != u["registry_sha256"]:
            bad.append(f"{u['resource_id']}: changed since the render (hash differs)")
    if bad:
        q.add("QC_RESOURCE_LINEAGE", "failed", "blocker", "a resource used by this video changed or is no longer verified since it was rendered: " + "; ".join(bad[:3]), evidence={"resources": bad}, action="render again from the current resources")
    else:
        q.ok("QC_RESOURCE_LINEAGE", f"{len(used)} Resource Library resource(s) used, all still verified at the pinned hash; licences: {', '.join(sorted({u['license_id'] or '?' for u in used}))}")


def _reconcile(q: Q, pdir: Path, aspect: str, manifest: dict, snap: dict | None, samples: list[dict]) -> None:
    """Upstream limitations carried into the current QC: each stays visible with its resolution status. Nothing is resolved because upstream marked it accepted; the pixels are not judged here."""
    val = mv.load(pdir, aspect)
    acked = {a["key"] for e in ((snap or {}).get("events") or []) if e.get("kind") == "decision" and e.get("decision") == "approved" and e.get("timeline_fingerprint") == (snap or {}).get("fingerprint")
             for a in e.get("warning_acknowledgements", [])}
    frames_of = lambda sid: [s["file"] for s in samples if s.get("scene_id") == sid and s.get("file")][:4]
    for w in manifest.get("carried_warnings", []):
        rule = {"approximation": "QC_UPSTREAM_STAND_IN", "undrawn_required": "QC_UPSTREAM_REQUIRED_NOT_DRAWN", "limitation": "QC_UPSTREAM_LIMITATION"}.get(w["category"], "QC_UPSTREAM_WARNING")
        req = w["category"] == "undrawn_required"
        q.add(rule, "failed" if req else "requires_review", "blocker" if req else "warning", w["text"], scene=w["scene_id"], target=w["element_id"],
              evidence={"source": w["source"], "acknowledged_at_approval": w["key"] in acked, "frames": frames_of(w["scene_id"]), "note": "carried from the approved timeline: not proof the visual is right"},
              resolution="accepted_with_reason" if w["key"] in acked else "unresolved", action="look at the frames of this scene (Final QC LLM review)")
    for row in (val or {}).get("elements", []):
        if row["state"] in ("drawn", "approximate"):
            continue
        if row["required"]:
            q.add("QC_UPSTREAM_REQUIRED_NOT_DRAWN", "failed", "blocker", f"{row['element_id']} is REQUIRED and was not drawn ({row['state']}): {row['why']}", scene=row["scene_id"], target=row["element_id"], resolution="not_drawn",
                  action="route to Motion Generation, or an explicit decision upstream")
        else:
            q.add("QC_UPSTREAM_OPTIONAL_NOT_DRAWN", "warning", "info", f"{row['element_id']} ({row['type']}) is optional and was not drawn: {row['why']}", scene=row["scene_id"], target=row["element_id"], resolution="not_drawn")
    _resource_lineage(q, manifest)
    elements = (val or {}).get("elements", [])
    q.ok("QC_UPSTREAM_ELEMENTS_COUNTED", f"{sum(1 for r in elements if r['state'] == 'drawn')} of {len(elements)} planned elements were drawn exactly as planned according to Motion Generation (a plan fact, not measured on this video)")
    emph = [c for c in (mp._read(pdir / mp.FIXES) or {}).get("changes", []) if c.get("kind") == "emphasis_aligned"]
    q.ok("QC_UPSTREAM_EMPHASIS", f"Stage 10 reports {((val or {}).get('summary') or {}).get('warnings', 0)} warning(s); {len(emph)} emphasis time(s) were aligned to spoken words by recorded decisions (not measured in the rendered video)")


# ---------- the Final QC LLM decision (append-only, bound to the candidate hash) ----------
def _reviews(pdir: Path, aspect: str) -> list[dict]:
    data = _rw_read(pdir, "review", aspect)
    return data.get("events", []) if isinstance(data, dict) else []


def current_review(pdir: Path, aspect: str, sha256: str | None) -> dict | None:
    return next((e for e in reversed(_reviews(pdir, aspect)) if sha256 and e["candidate_sha256"] == sha256 and not e.get("voided")), None)


def _append_review(pdir: Path, aspect: str, ev: dict) -> None:
    data = _rw_read(pdir, "review", aspect) or {"schema_version": SCHEMA, "project_id": pdir.name, "aspect": aspect, "events": []}
    data["events"].append(ev)
    _rw_write(pdir, "review", aspect, data)
    if (_reviews(pdir, aspect) or [{}])[-1] != ev:
        raise QcError("the decision could not be read back: it is not recorded", "persistence_failed")


def _void(pdir: Path, aspect: str, review_id: str, reason: str) -> None:
    """Mark a recorded decision as not valid; it stays in the history with the reason."""
    data = _rw_read(pdir, "review", aspect)
    ev = next((e for e in (data or {}).get("events", []) if e.get("review_id") == review_id), None)
    if ev is not None and not ev.get("voided"):
        ev["voided"], ev["voided_at"] = reason[:400], now()
        _rw_write(pdir, "review", aspect, data)
        _regate(pdir, aspect)


def llm_decide(pdir: Path, aspect: str) -> dict:
    """The Final QC decision about THIS file (its hash), made by the Final QC LLM review ("qc") from the report and its measurements; nobody watches the video.
    A failed or blocked QC is never approved. The decision is recorded append-only and read back, the report's status follows it, and the recorded approval is
    audited by the same review: an audit that does not pass voids it. An unavailable LLM records 'cannot_determine' (the QC stays needs_review)."""
    from . import llm_review
    rep = _rw_read(pdir, "report", aspect)
    cand = rv.candidate(pdir, aspect)
    if cand is None or not rep or rep["candidate"]["sha256"] != cand["sha256"]:
        raise QcError("the video changed (or there is no current QC report of it): run Final QC again before deciding", "candidate_changed")
    prior = current_review(pdir, aspect, cand["sha256"])
    if prior and prior["qc_run_id"] == rep["qc_run_id"] and prior["decision"] in ("approved", "approved_with_accepted_risks"):
        return {**state(pdir, aspect), "outcome": "already_recorded", "review": prior}
    if rep["status"] in ("failed", "blocked"):
        return {**state(pdir, aspect), "outcome": "not_approvable", "review": None}
    rev = llm_review.run_stage_llm_review(pdir, "qc", aspect, force=False)
    open_warn = [f["finding_id"] for f in rep["findings"] if f["severity"] == "warning"]
    if ta._review_ok(rev):
        dec = "approved_with_accepted_risks" if open_warn else "approved"
    else:
        dec = "cannot_determine" if any(f.get("category") == "llm_unavailable" for f in rev.get("findings", [])) else "changes_required"
    notes = [f"Final QC LLM review: {rev.get('status')} {rev.get('score')}: {rev.get('summary', '')}"[:1000]]
    notes += [f"{f.get('severity')}: {f.get('message')}"[:300] for f in rev.get("findings", []) if f.get("severity") in ("blocker", "error", "warning")][:10]
    ev = {"review_id": "qcr_" + uuid.uuid4().hex[:10], "decision": dec, "reviewer": f"llm:{rev.get('provider')}/{rev.get('model')}", "reviewer_source": "llm",
          "candidate_sha256": cand["sha256"], "qc_run_id": rep["qc_run_id"], "llm_review": {"status": rev.get("status"), "score": rev.get("score")},
          "coverage": {"report_reviewed": True, "playback_watched": False},
          "accepted_findings": open_warn if dec == "approved_with_accepted_risks" else [], "notes": notes, "decided_at": now()}
    _append_review(pdir, aspect, ev)
    _regate(pdir, aspect)                                                  # the report's status follows the decision; the media evidence is untouched
    if dec in ("approved", "approved_with_accepted_risks"):                  # the recorded decision is audited by the same review, asked again about the record (like the timeline approval): an audit that does not pass voids it
        audit = llm_review.run_stage_llm_review(pdir, "qc", aspect, force=False)
        if not ta._review_ok(audit):
            _void(pdir, aspect, ev["review_id"], f"the Final QC LLM audit did not pass: {audit.get('status')} {audit.get('summary', '')}")
        else:
            llm_review.run_stage_llm_review(pdir, "final", aspect)
    return {**state(pdir, aspect), "outcome": "recorded", "review": current_review(pdir, aspect, cand["sha256"])}


# ---------- status and the report ----------
def aggregate(checks: list[dict], rev: dict | None, blocked: bool) -> tuple[str, dict]:
    """blocked > failed > needs_review > passed_with_warnings > passed, from severities and the Final QC LLM decision, never from counts."""
    bad = [c for c in checks if c["status"] == "failed" and c["severity"] in ("blocker", "error")]
    warn = [c for c in checks if c["severity"] == "warning" and c["status"] != "passed"]
    summary = {"checks_total": len(checks), "checks_passed": sum(c["status"] == "passed" for c in checks), "checks_warned": sum(c["status"] == "warning" for c in checks), "checks_failed": sum(c["status"] == "failed" for c in checks),
               "checks_not_run": sum(c["status"] == "not_run" for c in checks), "checks_requires_review": sum(c["status"] == "requires_review" for c in checks), "blocking_findings": len(bad), "warnings": len(warn),
               "info": sum(1 for c in checks if c["severity"] == "info" and c["status"] != "passed"), "llm_review_required": True}
    if blocked:
        return "blocked", summary
    if bad or (rev and rev["decision"] == "changes_required"):
        return "failed", summary
    if not rev or rev["decision"] == "cannot_determine":
        return "needs_review", summary
    return ("passed_with_warnings" if warn else "passed"), summary


def _review_check(q_checks: list[dict], rev: dict | None, has_candidate: bool) -> dict | None:
    """Make the QC_LLM_REVIEW check say what the decision record says (used when the report is first written and again after a decision)."""
    for c in q_checks:
        if c["rule_id"] == "QC_LLM_REVIEW":
            if rev and rev["decision"] in ("approved", "approved_with_accepted_risks"):
                c.update(status="passed", severity="info", resolution="none", message=f"{rev['reviewer']} decided '{rev['decision']}' from the report (nobody watched the video)",
                         evidence={"review_id": rev["review_id"], "llm_review": rev.get("llm_review")})
            elif rev and rev["decision"] == "changes_required":
                c.update(status="failed", severity="error", resolution="unresolved", message=f"{rev['reviewer']} requested changes: {'; '.join(rev['notes'])[:200]}")
            elif rev:
                c.update(status="requires_review", severity="review", resolution="unresolved", message=f"{rev['reviewer']} could not decide: {'; '.join(rev['notes'])[:200]}")
            else:
                c.update(status="requires_review", severity="review", resolution="unresolved", message="the Final QC LLM review has not decided about this exact file yet" if has_candidate else "there is no candidate to review", evidence={})
            return c
    return None


def _resolve(checks: list[dict], rev: dict | None, status: str) -> None:
    """The LLM decision resolves the items nothing measured (marked reviewed_by_llm) and names the accepted risks; nothing is erased."""
    for c in checks:
        if c["status"] in ("passed", "not_applicable"):
            c["resolution"] = "none"
        elif c["resolution"] == "reviewed_by_llm":
            c["resolution"] = "unresolved"
    if rev and status in OK_STATUS:
        for c in checks:
            if c["status"] in ("requires_review", "not_run") and c["rule_id"] != "QC_LLM_REVIEW":
                c["resolution"] = "reviewed_by_llm"
            if c["finding_id"] in (rev.get("accepted_findings") or []):
                c["resolution"] = "accepted_with_reason"


def _finish(pdir, aspect, q, records, evidence, qc_run_id, profile, cand, manifest, rrep, snap, t0, blocked, media=None, tools=None, say=None) -> dict:
    sha_ = cand["sha256"] if cand else None
    q.stage = "llm_review"
    rev = current_review(pdir, aspect, sha_)
    q.add("QC_LLM_REVIEW", "requires_review", "review", "", action="run the Final QC LLM review")
    _review_check(q.checks, rev, cand is not None)
    status, summary = aggregate(q.checks, rev, blocked)
    _resolve(q.checks, rev, status)
    decided = bool(rev and rev["decision"] in ("approved", "approved_with_accepted_risks"))
    records.append({"n": 13, "stage_id": "llm_review", "label": "LLM Review", "name": "LLM Review", "status": "completed" if decided else "warning", "checks": 1, "checks_total": 1, "checks_passed": int(decided),
                    "findings": [] if decided else ["QC_LLM_REVIEW:video:-"], "detail": f"{rev['reviewer']} decided '{rev['decision']}'" if rev else "the Final QC LLM review has not decided about this exact file yet", "cache": {"hit": False}})
    records.append({"n": 14, "stage_id": "report_gate", "label": "Report & Delivery Gate", "name": "Report & Delivery Gate", "status": "completed", "checks": 0, "checks_total": 0, "checks_passed": 0, "findings": [],
                    "detail": f"report written with status '{status}'; the delivery gate opens only for passed / passed_with_warnings", "cache": {"hit": False}})
    rep = {"schema_version": SCHEMA, "qc_run_id": qc_run_id, "project_id": pdir.name, "aspect": aspect, "status": status, "created_at": now(), "rules_version": RULES_VERSION, "profile": profile,
           "profile_parameters": {k: (list(v) if isinstance(v, tuple) else v) for k, v in PROFILES[profile].items()},
           "candidate": {"relative_path": cand["path"].name if cand else None, "sha256": sha_, "size_bytes": cand["size_bytes"] if cand else None},
           "lineage": {"approved_timeline_id": (rrep or {}).get("approval", {}).get("approval_id"), "approved_timeline_fingerprint": (rrep or {}).get("input_fingerprints", {}).get("approved_version"),
                       "timeline_fingerprint": (rrep or {}).get("input_fingerprints", {}).get("timeline"), "render_manifest_fingerprint": (manifest or {}).get("manifest_fingerprint"), "render_job_id": (rrep or {}).get("job_id")},
           "media": media or {}, "summary": summary, "stages": records, "checks": q.checks, "findings": [c for c in q.checks if c["status"] != "passed"],
           "llm_review": {"status": "pending" if rev is None else rev["decision"], "reviewer": rev and rev["reviewer"], "decision": rev and rev["decision"], "review_id": rev and rev["review_id"],
                          "llm_review": rev and rev.get("llm_review"), "notes": (rev or {}).get("notes", [])},
           "evidence": {k: {"key": v["key"], "checks": v["checks"], "data": v.get("data") or {}} for k, v in evidence.items()},
           "tool_versions": tools or {}, "timings_seconds": {"qc": round(time.time() - t0, 1)}, "delivery_gate": {"open": status in OK_STATUS, "reason": "" if status in OK_STATUS else f"Final QC is {status.replace('_', ' ')}"},
           "limitations": ["nobody watched the video: the Final QC LLM review decided from this report and its measurements", "frames are sampled evidence, not motion playback", "audio/video content sync and emphasis moments are not measured automatically", "upstream stand-ins and undrawn elements are reported from the plan, not judged from pixels"],
           "next_action": {"passed": "the video may be delivered (a separate, explicit step)", "passed_with_warnings": "review the listed warnings; delivery is a separate, explicit step", "needs_review": "the Final QC LLM review has not approved this file (or could not decide): run Final QC again",
                           "failed": "fix the cause in the owning stage, render again", "blocked": "resolve the blocker named in the findings"}[status]}
    _rw_write(pdir, "report", aspect, rep)
    back = _rw_read(pdir, "report", aspect) or {}
    if back.get("qc_run_id") != qc_run_id or back.get("status") != status:
        raise QcError("the QC report could not be read back: no result is shown", "persistence_failed")
    if say:
        say(98)
    return rep


def _regate(pdir: Path, aspect: str) -> None:
    """After a decision: the stored report is recomputed from its own checks and the new decision (no media work)."""
    rep = _rw_read(pdir, "report", aspect)
    if not rep:
        return
    rev = current_review(pdir, aspect, rep["candidate"]["sha256"])
    _review_check(rep["checks"], rev, True)
    status, summary = aggregate(rep["checks"], rev, rep["status"] == "blocked")
    _resolve(rep["checks"], rev, status)
    decided = bool(rev and rev["decision"] in ("approved", "approved_with_accepted_risks"))
    for s in rep.get("stages", []):
        if s.get("stage_id") == "llm_review":
            s.update(
                status="completed" if decided else "warning",
                checks_passed=int(decided),
                findings=[] if decided else ["QC_LLM_REVIEW:video:-"],
                detail=f"{rev['reviewer']} decided '{rev['decision']}'" if rev else "the Final QC LLM review has not decided about this exact file yet"
            )
    rep.update(status=status, summary=summary, findings=[c for c in rep["checks"] if c["status"] != "passed"],
               llm_review={"status": "pending" if rev is None else rev["decision"], "reviewer": rev and rev["reviewer"], "decision": rev and rev["decision"], "review_id": rev and rev["review_id"],
                           "llm_review": rev and rev.get("llm_review"), "notes": (rev or {}).get("notes", [])},
               delivery_gate={"open": status in OK_STATUS, "reason": "" if status in OK_STATUS else f"Final QC is {status.replace('_', ' ')}"})
    rep["next_action"] = {"passed": "the video may be delivered (a separate, explicit step)", "passed_with_warnings": "review the listed warnings; delivery is a separate, explicit step", "needs_review": "the Final QC LLM review has not approved this file (or could not decide): run Final QC again",
                          "failed": "fix the cause in the owning stage, render again", "blocked": "resolve the blocker named in the findings"}[status]
    _rw_write(pdir, "report", aspect, rep)


def state(pdir: Path, aspect: str) -> dict:
    """Read-only: the stored report with `current` (its candidate hash is the published video's now, the approved version unchanged, the rules version the same), the candidate, the LLM decisions, the delivery gate."""
    from . import jobs
    rep = _rw_read(pdir, "report", aspect)
    cand = rv.candidate(pdir, aspect)
    rrep = rv._read(pdir, "report", aspect)
    why = []
    if cand is None:
        why.append("there is no verified rendered video: run Render Video first")
    else:
        snap = ta.snapshot(pdir, aspect)
        if not (snap["status"] == "approved" and rrep and snap["fingerprint"] == rrep["input_fingerprints"]["approved_version"]):
            why.append("the approved timeline changed after this video was rendered: approve and render again")
    current = bool(rep and cand and rep["candidate"]["sha256"] == cand["sha256"] and rep.get("rules_version") == RULES_VERSION and not why)
    status = "blocked" if cand is None else (("blocked" if why else "not_run") if rep is None else (rep["status"] if current else "stale"))     # no verified video = nothing to judge, whatever an old report says
    reasons = [] if current and rep["status"] in OK_STATUS else [f"Final QC is {status.replace('_', ' ')}"] + why
    return {"aspect": aspect, "status": status, "current": current, "stale": bool(rep) and not current, "blockers": why, "report": rep, "running": jobs.is_running(pdir.name),
            "candidate": cand and {"name": cand["path"].name, "sha256": cand["sha256"], "size_bytes": cand["size_bytes"]}, "reviews": _reviews(pdir, aspect),
            "delivery_gate": {"open": not reasons, "reasons": reasons}, "profiles": list(PROFILES), "note": "Final QC reads the video file; it never renders, edits or approves the timeline"}


def gate(pdir: Path, aspect: str) -> list[str]:
    """Why the finished video must not be released (empty = a current, acceptable Final QC of the current candidate). Fails closed."""
    try:
        return state(pdir, aspect)["delivery_gate"]["reasons"]
    except Exception as e:
        return [f"Final QC could not be verified: {e}"[:200]]


def stage_view(pdir: Path, aspect: str) -> dict:
    s = state(pdir, aspect)
    label, open_it, st = "Final QC", {"kind": "open_final_qc", "label": "Open"}, s["status"]
    if st in OK_STATUS:
        return dict(id="qc", label=label, status="completed", detail=f"{st.replace('_', ' ')}: {s['report']['summary']['warnings']} warning(s), approved by the Final QC LLM review", action=open_it)
    if st == "needs_review":
        return dict(id="qc", label=label, status="failed", detail="the Final QC LLM review has not approved this file (or could not decide): run Final QC again", action=open_it)
    if st == "failed":
        return dict(id="qc", label=label, status="failed", detail=f"{s['report']['summary']['blocking_findings']} blocking finding(s) or changes requested", action=open_it)
    if st == "stale":
        return dict(id="qc", label=label, status="queued", detail="the video or its approval changed since this QC: run Final QC again", action=open_it)
    if st == "blocked":
        return dict(id="qc", label=label, status="queued", detail="waits for a verified render: " + (s["blockers"][0] if s["blockers"] else "see the report"), action=open_it)
    return dict(id="qc", label=label, status="queued", detail="ready: run Final QC on the rendered video", action=open_it)
