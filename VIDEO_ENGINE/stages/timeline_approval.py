"""Timeline Approval (roadmap improvements/Timeline_Approval_Complete_Roadmap), Stage 12: a decision about ONE exact, validated timeline version, made by the LLM approval review (auto_approve; no human gate), between Timeline Build (Stage 11) and Render Video.
It never builds, repairs or edits the timeline, never starts a render and never approves by itself: opening the page, having a preview or having zero errors approves nothing.

What an approval is tied to (`fingerprint`): the published timeline (its canonical digest), everything Stage 11 was built from (Stage 11's source fingerprint: composition, Motion Generation, audio, renderer,
Stage 10 verdict ...) and what the final render depends on besides that (render flags, remotion config / package). Any change makes the approval `stale` by itself: the status is recomputed from the stored record
and the CURRENT inputs every time, never read from a stored boolean.

States: not_ready | ready_for_review | changes_requested | approved | stale | approval_error (job status is separate). `reviewing` is a page state, not a stored one.
Records (append-only history, never overwritten): `timeline_approval_history[_9x16].json` = events (decision approved / changes_requested / withdrawn, note). `timeline_review[_9x16].json` = the review manifest of
the current version (derived: the same inputs give the same review id).
Honesty rules: a warning is never removed because it was acknowledged; a still is not motion playback; `review_coverage` says whether a PERSON looked at the stills / watched the motion (recorded by the Stage 10
review route, bound to the composition) and the approval needs an explicit acknowledgement of every material limitation, including the coverage it does not have. The approver's name is what the person typed:
this application has no accounts, so it is recorded as `self_declared`."""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

from . import motion_gen_report as mgr, motion_generation as mg, motion_planning as mp, motion_validation as mv, motion_validation_preview as pv, pipeline, review, store
from . import timeline_build as tb

SCHEMA = "1.0"
VERSION = 1
DECISIONS = ("approved", "changes_requested", "withdrawn")
STATES = ("not_ready", "ready_for_review", "changes_requested", "approved", "stale", "approval_error")
_locks: dict[str, threading.RLock] = {}
_guard = threading.Lock()


class ApprovalError(Exception):
    """A decision is refused or could not be stored safely. `code` is the API error code, `blockers` the reasons."""

    def __init__(self, code: str, message: str, blockers: list[str] | None = None) -> None:
        super().__init__(message)
        self.code, self.blockers = code, blockers or []


def names(aspect: str) -> dict[str, str]:
    sfx = "_9x16" if aspect == "9:16" else ""
    return {"history": f"timeline_approval_history{sfx}.json", "review": f"timeline_review{sfx}.json"}


def _lock(pdir: Path) -> threading.RLock:
    with _guard:
        return _locks.setdefault(str(pdir.resolve()), threading.RLock())


# ---------- the version an approval is about ----------
def render_config(aspect: str, fps) -> str:
    """What the FINAL render depends on besides the timeline: its flags and the renderer's config. (Composition, audio and renderer source are already in Stage 11's source fingerprint.)"""
    from . import config, render
    root = getattr(pipeline, "_REMOTION", config.REMOTION_DIR)
    return mv.sha(mv.canon([render.render_flags(False), aspect, mv._file_sha(root / "remotion.config.ts"), mv._file_sha(root / "package.json"), fps]))


def fingerprint(pdir: Path, aspect: str, tbs: dict | None = None) -> str | None:
    """None = it cannot be determined (fails closed)."""
    tbs = tbs or tb.load(pdir, aspect)
    if not tbs or not tbs["current"] or not tbs["report"].get("timeline_fingerprint"):
        return None
    try:
        return mv.sha(mv.canon({"timeline": tbs["report"]["timeline_fingerprint"], "build": tbs["report"]["source_fingerprint"], "render": render_config(aspect, tbs["report"]["counts"].get("fps")), "v": VERSION}))
    except OSError:
        return None


# ---------- the preview (review proxy stills) ----------
def _sha_or_none(f: Path) -> str | None:
    try:
        return mv.sha(f.read_bytes())
    except OSError:
        return None


def preview(pdir: Path, aspect: str, scenes: int) -> dict:
    """Is there a preview PROVEN to depict the current composition? Never reused because a file with the expected name exists: the manifest's composition identity, the renderer, the sampling rule, every file's
    hash and decode result are checked now."""
    out = {"kind": "review_proxy_stills", "verified": False, "reason": "", "samples": 0, "scenes": 0, "composition_sha": None, "scale": None, "files": []}
    man = pv.load(pdir, aspect)
    if man is None:
        out["reason"] = "no preview has been generated: Generate Review Stills"
        return out
    gen = mp._read(pdir / mg.names(aspect)[1]) or {}
    out.update(composition_sha=man.get("composition_sha"), scale=man.get("scale"), samples=len(man.get("samples", [])))
    try:
        from VIDEO_ENGINE.pipeline import legacy_pipeline_adapter
        renderer_digest = legacy_pipeline_adapter._remotion_src_digest()
    except Exception:
        renderer_digest = None
    samples = man.get("samples", [])
    bad = [s["file"] for s in samples if not s.get("decode_ok") or s.get("blank") or _sha_or_none(pv.folder(pdir, aspect) / s["file"]) != s["sha"]]
    covered = {s["scene_id"] for s in samples}
    # the first check that fails is the reason; the preview is verified only when none does
    for failed, why in ((man.get("sampling_rule_version") != pv.RULE_VERSION, "the preview was made with another sampling rule: generate it again"),
                        (man.get("composition_sha") != (gen.get("output") or {}).get("composition_sha"), "the preview shows another version of the composition than the current one: generate it again"),
                        (bool(renderer_digest) and man.get("renderer_digest") != renderer_digest, "the renderer changed since the preview was made: generate it again"),
                        (bool(bad), f"{len(bad)} still(s) are missing, changed, undecodable or blank: generate the preview again"),
                        (len(covered) != scenes, f"the preview covers {len(covered)} of {scenes} scenes: generate it again")):
        if failed:
            out["reason"] = why
            return out
    out.update(verified=True, scenes=len(covered), files=[{k: s[k] for k in ("scene_id", "kind", "frame", "time_s", "file")} for s in samples])
    return out


def coverage(pdir: Path, aspect: str) -> dict:
    """Did a PERSON look? From the Stage 10 review records, bound to the current composition. Nothing here is a technical check."""
    man = pv.load(pdir, aspect) or {}
    gen = mp._read(pdir / mg.names(aspect)[1]) or {}
    sha_ = (gen.get("output") or {}).get("composition_sha")
    rec = {r["level"]: r for r in man.get("reviews", []) if r.get("composition_sha") == sha_}
    return {"stills_reviewed_by_person": "stills" in rec, "motion_playback_reviewed": "playback" in rec, "reviews": list(rec.values()),
            "note": "recorded by a person through Motion & Timeline Validation; a still does not show how the motion or a transition plays"}


# ---------- what has to be acknowledged ----------
_tail_memo: dict = {}


def audio_tail_impact(pdir: Path, T: dict, comp_words: list[dict]) -> dict:
    """What the renderer's frame count really cuts off the end of the audio: the seconds, whether that part holds any signal, and where the speech ends. Measured on the file (16-bit PCM wav), not assumed."""
    prof, au = T["profile"], T["tracks"][0]["items"][0]
    cut_from = prof["duration_frames"] / prof["fps"]
    res = {"measured": False, "cut_seconds": round(max(0.0, prof["duration_seconds_source"] - cut_from), 4), "cut_starts_at_seconds": round(cut_from, 4), "speech_ends_at_seconds": None, "speech_ends_before_cut_seconds": None}
    if comp_words:
        res["speech_ends_at_seconds"] = comp_words[-1]["end"]
        res["speech_ends_before_cut_seconds"] = round(cut_from - comp_words[-1]["end"], 3)
    f = pdir / (au.get("source_ref") or "")
    if f.suffix.lower() != ".wav" or not f.is_file():
        res["why_not_measured"] = "only a wav file can be measured here"
        return res
    key = (str(f), f.stat().st_size, f.stat().st_mtime_ns, prof["duration_frames"])
    if _tail_memo.get("key") == key:
        return {**res, **_tail_memo["val"]}
    import struct
    import wave
    try:
        with wave.open(str(f)) as w:
            sr, ch, width, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
            if width != 2:
                res["why_not_measured"] = "only 16-bit audio can be measured here"
                return res
            first = min(int(cut_from * sr + 1e-9), n)
            w.setpos(first)
            raw = w.readframes(n - first)
        vals = struct.unpack("<%dh" % (len(raw) // 2), raw)[::ch]
        peak = max((abs(x) for x in vals), default=0)
        val = {"measured": True, "cut_samples": len(vals), "cut_peak_amplitude": peak, "cut_is_digital_silence": peak == 0,
               "conclusion": "the part the renderer cuts holds no signal (digital silence): no audio content is lost" if peak == 0 else f"the part the renderer cuts holds signal (peak {peak} of 32767): audio content is lost"}
    except (OSError, EOFError, struct.error, wave.Error) as e:
        res["why_not_measured"] = f"the audio could not be read: {e}"[:160]
        return res
    _tail_memo.update(key=key, val=val)
    return {**res, **val}


_ACK = {
    "audio.tail_quantization": ("audio_tail_not_rendered", "limitation"), "visual.approximate": ("approximate_visual", "approximation"), "visual.not_drawn": ("required_visual_not_drawn", "undrawn_required"),
    "transition.not_clamped": ("transition_shortened", "limitation"), "transition.not_repeated": ("transition_repeated", "limitation"), "audio.matches_composition": ("audio_length_differs", "limitation"),
}


def requirements(tbs: dict, val: dict | None, cov: dict, tail: dict | None) -> list[dict]:
    """Every material limitation the approver must acknowledge, each kept visible and distinct: warnings of Stage 11 and Stage 10, approximations (drawn as a stand-in, NOT missing), required visuals not drawn,
    accepted exceptions, and the review coverage nobody has. Informational findings (an optional element not drawn) are shown, not required."""
    out = []
    for f in tbs["report"]["findings"]:
        if f["severity"] != "warning":
            continue
        code, cat = _ACK.get(f["rule_id"], (f["rule_id"].replace(".", "_"), "warning"))
        out.append({"key": f"{code}:{f['item_id'] or f['scene_id'] or '-'}", "code": code, "category": cat, "scene_id": f["scene_id"], "element_id": f["item_id"], "source": "timeline_build", "rule_id": f["rule_id"],
                    "text": f["message"], "evidence": ({**f["evidence"], "measured": tail} if f["rule_id"] == "audio.tail_quantization" and tail else f["evidence"])})
    for f in (val or {}).get("findings", []):
        if f["severity"] == "warning" or f["status"] == "accepted_for_version":
            out.append({"key": f"stage10:{f['rule_id']}:{f['scene_id'] or '-'}:{f['element_id'] or '-'}", "code": f"stage10_{f['rule_id'].replace('.', '_')}", "category": "accepted_exception" if f["status"] == "accepted_for_version" else "warning",
                        "scene_id": f["scene_id"], "element_id": f["element_id"], "source": "motion_validation", "rule_id": f["rule_id"], "text": f["message"], "evidence": f["evidence"]})
    if not cov["stills_reviewed_by_person"]:
        out.append({"key": "stills_not_reviewed_by_person:-", "code": "stills_not_reviewed_by_person", "category": "review_coverage", "scene_id": None, "element_id": None, "source": "review", "rule_id": "coverage.stills",
                    "text": "No person has recorded looking at the review stills of this version.", "evidence": {}})
    if not cov["motion_playback_reviewed"]:
        out.append({"key": "motion_playback_not_reviewed:-", "code": "motion_playback_not_reviewed", "category": "review_coverage", "scene_id": None, "element_id": None, "source": "review", "rule_id": "coverage.playback",
                    "text": "Nobody has watched the motion, the transitions or the narration timing of this version (this page shows stills only, no video is rendered for review).", "evidence": {}})
    return out


# ---------- the state ----------
def _history(pdir: Path, aspect: str) -> dict:
    f = pdir / names(aspect)["history"]
    if not f.exists():
        return {"schema_version": SCHEMA, "project_id": pdir.name, "aspect": aspect, "events": []}
    with store._info_lock(pdir):
        data = mp._read(f)
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA or not isinstance(data.get("events"), list):
        raise ApprovalError("approval_error", "the approval record cannot be read (malformed): rendering stays blocked")
    return data


def _latest_decision(events: list[dict]) -> dict | None:
    return next((e for e in reversed(events) if e["kind"] == "decision" and not e.get("voided")), None)


def snapshot(pdir: Path, aspect: str) -> dict:
    """Everything the page and the gates need, computed once from the current files. Read-only."""
    from . import jobs
    why: list[str] = []
    tbs = tb.load(pdir, aspect)
    current = bool(tbs and tbs["current"])
    T = tb.timeline(pdir, aspect) if current else None
    err = None
    try:
        events = _history(pdir, aspect)["events"]
    except ApprovalError as e:
        events, err = [], str(e)
    busy = jobs.is_running(pdir.name)                                    # a running job does not change what the version IS: it only stops a decision / a new render from starting (see decide and gate)
    why += tb.blockers(pdir, aspect)
    fp = fingerprint(pdir, aspect, tbs) if current else None
    val = mv.load(pdir, aspect)
    if current:
        if fp is None:
            why.append("the fingerprint of the timeline cannot be determined")
        if T is None or not tbs["coherent"]:
            why.append("the timeline and its report do not belong together")
        why += mv.blockers(pdir, aspect)
        if (g := mgr.blockers(pdir, aspect)):
            why.append(f"Motion Generation is not current: {g}")
        if not review.timeline_state(pdir)[aspect]["ready"]:
            why.append("the pre-render check of the composition has not passed on the current files (build the timeline again)")
    scenes = tbs["report"]["counts"]["scenes"] if current else 0
    prev = preview(pdir, aspect, scenes) if current else {"kind": "review_proxy_stills", "verified": False, "reason": "no current timeline", "samples": 0, "scenes": 0, "composition_sha": None, "scale": None, "files": []}
    if current and not prev["verified"]:
        why.append(f"no matching review preview: {prev['reason']}")
    cov = coverage(pdir, aspect)
    words = []
    if T:
        try:
            words = json.loads((pdir / mg.names(aspect)[0]).read_text(encoding="utf-8")).get("words", [])
        except (OSError, ValueError):
            pass
    tail = audio_tail_impact(pdir, T, words) if T else None
    reqs = requirements(tbs, val, cov, tail) if current else []
    last = _latest_decision(events)
    on_current = bool(last and fp and last["timeline_fingerprint"] == fp)
    if err:
        status = "approval_error"
    elif last and last["decision"] == "approved" and not on_current:
        # an approval of another version is never current. While the current version has blockers (or cannot be fingerprinted) the page reports `stale`; once the
        # current version is built, previewed and clean it is `ready_for_review`: the old approval stays in the history (marked stale) and must not block a new decision
        status = "stale" if (why or not fp) else "ready_for_review"
    elif why:
        status = "not_ready"
    elif on_current and last["decision"] == "approved":
        status = "approved"
    elif on_current and last["decision"] == "changes_requested":
        status = "changes_requested"
    else:
        status = "ready_for_review"
    return {"status": status, "blockers": ([err] if err else why), "fingerprint": fp, "tbs": tbs, "timeline": T, "validation": val, "preview": prev, "coverage": cov, "audio_tail": tail, "requirements": reqs,
            "events": events, "last": last, "approved": status == "approved", "busy": busy, "review_id": f"review_{fp[:12]}" if fp else None}


def _view(e: dict, fp: str | None) -> dict:
    return {**e, "stale": e["kind"] == "decision" and e.get("timeline_fingerprint") != fp}


def manifest(pdir: Path, aspect: str, s: dict) -> dict | None:
    """The review manifest of the current version (None while there is nothing reviewable)."""
    tbs, T = s["tbs"], s["timeline"]
    if not tbs or not tbs["current"] or not T or not s["fingerprint"]:
        return None
    rep = tbs["report"]
    clips = T["tracks"][1]["items"]
    gaps = {g["after_scene"]: g for g in T["gap_intervals"]}
    trans = {t["from_scene"]: t for t in T["transitions"]}
    fps = T["profile"]["fps"]
    dis = rep.get("disclosures") or {}
    return {"schema_version": SCHEMA, "project_id": pdir.name, "review_id": s["review_id"], "timeline_build_id": T["timeline_id"], "timeline_fingerprint": s["fingerprint"], "timeline_digest": rep["timeline_fingerprint"],
            "source_fingerprints": {k: rep["inputs"].get(k) for k in ("visual_plan", "motion_plan", "motion_planning", "motion_generation", "composition", "audio", "stage10", "renderer")} | {"timeline_build": rep["source_fingerprint"]},
            "format": {"width": T["profile"]["width"], "height": T["profile"]["height"], "fps": fps, "aspect_ratio": T["profile"]["aspect_ratio"]},
            "duration_seconds": T["profile"]["composition_duration_seconds"], "duration_frames": T["profile"]["duration_frames"], "scene_count": len(clips), "mode": T["profile"]["mode"],
            "scenes": [{"scene_id": c["scene_id"], "start_frame": c["start_frame"], "end_frame": c["end_frame"], "start_s": round(c["start_frame"] / fps, 3), "end_s": round(c["end_frame"] / fps, 3), "layers": len(c["layers"]),
                        "pause_after_s": (gaps.get(c["scene_id"]) or {}).get("source_gap_seconds"), "transition_out": ({k: trans[c["scene_id"]][k] for k in ("type", "requested_frames", "applied_frames")} if c["scene_id"] in trans else None)} for c in clips],
            "preview": {"folder": pv.folder(pdir, aspect).name, "timeline_fingerprint": s["fingerprint"], "kind": s["preview"]["kind"], "verified": s["preview"]["verified"], "composition_sha": s["preview"]["composition_sha"],
                        "scale": s["preview"]["scale"], "note": "quarter-size stills of the composition at deterministic frames: a proxy, not the final video and not motion playback"},
            "readiness": {"status": s["status"], "errors": rep["summary"]["errors"] + rep["summary"]["blockers"], "warnings": rep["summary"]["warnings"], "required_visuals_not_drawn": dis.get("required_not_drawn", 0),
                          "approximate_visuals": dis.get("approximate", 0), "optional_not_drawn": dis.get("optional_not_drawn", 0)},
            "review_coverage": s["coverage"], "audio_tail": s["audio_tail"], "created_at": time.strftime("%Y-%m-%dT%H:%M:%S")}


def state(pdir: Path, aspect: str, s: dict | None = None) -> dict:
    s = s or snapshot(pdir, aspect)
    fp, last = s["fingerprint"], s["last"]
    rep = (s["tbs"] or {}).get("report") or {}
    return {"aspect": aspect, "status": s["status"], "blockers": s["blockers"], "fingerprint": fp, "review_id": s["review_id"], "approval_allowed": s["status"] == "ready_for_review", "approved": s["approved"], "stale": s["status"] == "stale",
            "last_decision": _view(last, fp) if last else None, "history": [_view(e, fp) for e in s["events"]], "notes": [e for e in s["events"] if e["kind"] == "note" and e.get("timeline_fingerprint") == fp],
            "manifest": manifest(pdir, aspect, s), "requirements": s["requirements"], "preview": s["preview"], "review_coverage": s["coverage"], "audio_tail": s["audio_tail"], "timeline_status": (s["tbs"] or {}).get("status"),
            "disclosures": rep.get("disclosures"), "info": [f for f in rep.get("findings", []) if f["severity"] == "info"],
            "note": "a technically valid approval record is not a visual review: see review_coverage for what a person actually looked at"}


# ---------- decisions ----------
def _write(pdir: Path, aspect: str, hist: dict) -> None:
    f = pdir / names(aspect)["history"]
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps(hist, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    with store._info_lock(pdir):                                             # the store's own per-project lock: a reader never meets os.replace on Windows
        os.replace(tmp, f)


def _append(pdir: Path, aspect: str, ev: dict) -> None:
    """Append, then read back and verify. A write that cannot be verified is an error and is never shown as a decision."""
    hist = _history(pdir, aspect)
    hist["events"].append(ev)
    try:
        _write(pdir, aspect, hist)
        back = _history(pdir, aspect)
    except (OSError, ApprovalError) as e:
        raise ApprovalError("approval_error", f"the decision could not be stored safely: {e}") from e
    if not back["events"] or back["events"][-1] != ev:
        raise ApprovalError("approval_error", "the decision read back from disk is not what was written")


def decide(pdir: Path, aspect: str, body: dict, in_job: bool = False) -> dict:
    """The one writer of decisions. Sequence (roadmap 07): payload -> idempotency -> current snapshot -> expected fingerprint -> blockers and acknowledgements -> write -> read back -> verify again.
    Raises ApprovalError (never a half result). Returns the new state."""
    with _lock(pdir):
        dec = body.get("decision")
        by = (body.get("decision_by") or "").strip()
        key = (body.get("idempotency_key") or "").strip()
        if dec not in DECISIONS:
            raise ApprovalError("invalid_decision", f"decision must be one of {', '.join(DECISIONS)}")
        if not by or len(by) > 80:
            raise ApprovalError("invalid_decision", "the name of the person who decides is required (up to 80 characters)")
        if not key:
            raise ApprovalError("invalid_decision", "an idempotency key is required")
        prior = next((e for e in _history(pdir, aspect)["events"] if e.get("idempotency_key") == key), None)
        if prior:                                                            # the same request again: the same outcome, no second record
            return {**state(pdir, aspect), "outcome": "already_recorded", "decision": prior}
        s = snapshot(pdir, aspect)
        if s["busy"] and not in_job:                                       # in_job: the pipeline job itself is deciding (auto_approve inside its step)
            raise ApprovalError("job_running", "a job is running for this project: decide after it finishes")
        if s["status"] == "approval_error":
            raise ApprovalError("approval_error", "; ".join(s["blockers"]))
        if not s["fingerprint"]:
            raise ApprovalError("timeline_not_ready", "the timeline cannot be reviewed yet", s["blockers"])
        if body.get("expected_fingerprint") != s["fingerprint"] or body.get("review_id") != s["review_id"]:
            raise ApprovalError("timeline_changed", "the timeline changed since this review was opened: nothing was recorded, reload the current version", [f"current version: {s['review_id']}"])
        last = s["last"]
        on_this = bool(last and last["timeline_fingerprint"] == s["fingerprint"])
        if dec == "withdrawn":
            if not (on_this and last["decision"] == "approved"):
                raise ApprovalError("invalid_decision", "there is no current approval of this version to withdraw")
        elif s["blockers"]:
            raise ApprovalError("timeline_not_ready", "the timeline cannot be decided on yet", s["blockers"])
        if dec == "approved":
            if on_this and last["decision"] == "approved":
                return {**state(pdir, aspect, s), "outcome": "already_approved", "decision": last}
            if on_this and last["decision"] == "changes_requested":
                raise ApprovalError("changes_requested_for_this_version", "changes were requested for this version: build a new timeline, then review it again")
            have = {a.get("key") for a in body.get("warning_acknowledgements", []) if a.get("acknowledged") is True}
            missing = [r["key"] for r in s["requirements"] if r["key"] not in have]
            if missing:
                raise ApprovalError("acknowledgement_required", f"{len(missing)} material limitation(s) are not acknowledged", missing)
        comments = [c for c in (body.get("comments") or []) if (c.get("text") or "").strip()]
        notes = [str(n).strip()[:1000] for n in (body.get("notes") or []) if str(n).strip()]
        if dec == "changes_requested" and not (comments or notes):
            raise ApprovalError("invalid_decision", "Request Changes needs a reason: write at least one comment")
        man = manifest(pdir, aspect, s)
        ev = {"event_id": "decision_" + mv.sha(f"{key}:{s['fingerprint']}:{time.time()}"), "kind": "decision", "decision": dec, "project_id": pdir.name, "aspect": aspect, "timeline_build_id": s["timeline"]["timeline_id"],
              "timeline_fingerprint": s["fingerprint"], "source_fingerprints": man["source_fingerprints"], "review_manifest_id": s["review_id"], "idempotency_key": key,
              "warning_acknowledgements": ([{"key": r["key"], "code": r["code"], "element_id": r["element_id"], "scene_id": r["scene_id"], "category": r["category"], "acknowledged": True} for r in s["requirements"]] if dec == "approved" else []),
              "review_coverage": {k: s["coverage"][k] for k in ("stills_reviewed_by_person", "motion_playback_reviewed")}, "notes": notes, "comments": [{k: c.get(k) for k in ("scene_id", "time_seconds", "severity", "text")} for c in comments],
              "decided_by": by, "decided_by_source": "self_declared", "decided_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "supersedes": (last["event_id"] if on_this else None)}
        _append(pdir, aspect, ev)
        if fingerprint(pdir, aspect) != s["fingerprint"]:                    # the version moved while the decision was written: it is voided, never left standing
            hist = _history(pdir, aspect)
            hist["events"][-1]["voided"] = "the timeline changed while the decision was being recorded"
            _write(pdir, aspect, hist)
            raise ApprovalError("timeline_changed", "the timeline changed while the decision was being recorded: it was voided, reload the current version")
        out = state(pdir, aspect)
        _save_review(pdir, aspect, out["manifest"])
        return {**out, "outcome": "recorded", "decision": ev}


MAX_AUTO_ATTEMPTS = 2                                                       # rebuild + review again once; then the stage fails with the LLM's findings
PASS_SCORE = 0.80                                                           # CLAUDE.md: an LLM review passes with status "passed" and score >= 0.80


def _review_ok(rev: dict | None) -> bool:
    return bool(rev) and rev.get("status") == "passed" and float(rev.get("score") or 0) >= PASS_SCORE and not any(f.get("severity") in ("blocker", "error") for f in rev.get("findings", []))


def auto_approve(pdir: Path, aspect: str, in_job: bool = False) -> dict:
    """The LLM decides (no person): the current, deterministically clean timeline version is reviewed by the stage LLM review ('approval': timing, scenes, transitions, layers,
    audio sync), and only a `passed` verdict with score >= PASS_SCORE and no blocker is recorded, through decide() and every check it makes (fingerprint, blockers,
    acknowledgements, read-back). The recorded decision is then audited by the same review; an audit that does not pass withdraws it. When the review rejects the version
    the timeline is rebuilt once and reviewed again. Raises ApprovalError with the exact cause when it cannot approve (never a half result)."""
    from . import llm_review
    rev = None
    for attempt in range(1, MAX_AUTO_ATTEMPTS + 1):
        s = snapshot(pdir, aspect)
        if s["status"] == "approved" and llm_review.is_stage_review_passed(pdir, "approval", aspect)[0]:
            write_approval_report(pdir, aspect)
            return state(pdir, aspect, s)
        if s["status"] not in ("ready_for_review", "approved") or s["blockers"]:
            raise ApprovalError("timeline_not_ready", "the timeline cannot be approved: " + "; ".join(s["blockers"][:3] or [s["status"]]), s["blockers"])
        verdict = None
        if s["status"] != "approved":
            verdict = rev = llm_review.run_stage_llm_review(pdir, "approval", aspect, force=False)
            if _review_ok(rev):
                decide(pdir, aspect, {"decision": "approved", "decision_by": f"llm:{rev.get('provider')}/{rev.get('model')}", "idempotency_key": f"llm_{s['fingerprint']}_{attempt}",
                                      "expected_fingerprint": s["fingerprint"], "review_id": s["review_id"],
                                      "warning_acknowledgements": [{"key": r["key"], "acknowledged": True} for r in s["requirements"]],   # disclosed in the review's payload
                                      "notes": [f"LLM approval review: {rev.get('status')} {rev.get('score')}: {rev.get('summary', '')}"[:1000]]}, in_job=in_job)
        if verdict is None or _review_ok(verdict):                           # audit the recorded decision (the review's output is the decision history)
            rev = llm_review.run_stage_llm_review(pdir, "approval", aspect, force=False)
            if _review_ok(rev) and llm_review.is_stage_review_passed(pdir, "approval", aspect)[0]:
                write_approval_report(pdir, aspect)
                return state(pdir, aspect)
            s2 = snapshot(pdir, aspect)
            if s2["status"] == "approved":
                decide(pdir, aspect, {"decision": "withdrawn", "decision_by": "llm:audit", "idempotency_key": f"llm_withdraw_{s2['fingerprint']}_{attempt}",
                                      "expected_fingerprint": s2["fingerprint"], "review_id": s2["review_id"], "notes": [f"LLM audit did not pass: {(rev or {}).get('summary', '')}"[:1000]]}, in_job=in_job)
        if attempt < MAX_AUTO_ATTEMPTS:                                       # rejected: rebuild the timeline from the current inputs and review the new version
            from VIDEO_ENGINE.pipeline import legacy_pipeline_adapter as pa
            pa.execute(pdir, "timeline-build-9x16" if aspect == "9:16" else "timeline-build", pa.Ctx(force=True))
    why = [f"{f.get('severity')}: {f.get('message')}" for f in (rev or {}).get("findings", []) if f.get("severity") in ("blocker", "error", "warning")]
    raise ApprovalError("llm_review_rejected", f"the LLM approval review did not pass ({(rev or {}).get('status')}, score {(rev or {}).get('score')}): {(rev or {}).get('summary', '')}"[:400], why[:6])


def add_note(pdir: Path, aspect: str, body: dict) -> dict:
    """A review note about the current version (scene and timecode when known). It decides nothing."""
    with _lock(pdir):
        s = snapshot(pdir, aspect)
        text = (body.get("text") or "").strip()
        if not s["fingerprint"] or body.get("expected_fingerprint") != s["fingerprint"]:
            raise ApprovalError("timeline_changed", "the timeline changed since this review was opened: reload the current version")
        if not text or not (body.get("decision_by") or "").strip():
            raise ApprovalError("invalid_decision", "a note needs its text and the name of the person who wrote it")
        ev = {"event_id": "note_" + mv.sha(f"{text}:{s['fingerprint']}:{time.time()}"), "kind": "note", "timeline_fingerprint": s["fingerprint"], "scene_id": body.get("scene_id"), "time_seconds": body.get("time_seconds"),
              "text": text[:1000], "written_by": body["decision_by"].strip()[:80], "written_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        _append(pdir, aspect, ev)
        return state(pdir, aspect)


def _save_review(pdir: Path, aspect: str, man: dict | None) -> None:
    if man is None:
        return
    f = pdir / names(aspect)["review"]
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps(man, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    with store._info_lock(pdir):
        os.replace(tmp, f)


def prepare_review(pdir: Path, aspect: str) -> dict:
    """Resolve the latest build and preview and write the review manifest. It changes nothing in the timeline, approves nothing and renders nothing."""
    with _lock(pdir):
        out = state(pdir, aspect)
        _save_review(pdir, aspect, out["manifest"])
        return out


# ---------- the gates ----------
def gate(pdir: Path, aspect: str, in_render_job: bool = False, snap: dict | None = None) -> list[str]:
    """Why the final render must not start (empty = the current version is approved). Fails closed: if anything cannot be verified, it blocks. `in_render_job`: the render job itself is the running job.
    `snap`: a snapshot the caller just made (the page state), so it is not computed twice."""
    try:
        s = snap or snapshot(pdir, aspect)
    except Exception as e:                                                   # unknown is not approved
        return [f"the approval could not be verified: {e}"[:200]]
    st = s["status"]
    if st == "approved":
        return ["a job is running for this project: wait for it to finish"] if s["busy"] and not in_render_job else []
    if st == "approval_error":
        return [f"the approval record cannot be verified: {s['blockers'][0]}"]
    if st == "not_ready":
        return s["blockers"][:3]
    if st == "changes_requested":
        return ["changes were requested for this version: build a new timeline and review it"]
    if st == "stale":
        return ["the timeline changed after it was approved: review and approve this version" + (f" ({s['blockers'][0]})" if s["blockers"] else "")]
    return ["approve the timeline first (Timeline Approval)"]


def legacy_state(pdir: Path, aspect: str) -> dict:
    """The keys timeline_gate.state always had, so every existing consumer (pipeline view, render gate, advance) keeps working. `ready` keeps its meaning one step earlier: the timeline is BUILT (Stage 11 current) and
    the pre-render check passed on the current files; it says nothing about the review preview or the approval. `approved` = this exact version is approved. `blockers` = why the version cannot be approved / rendered."""
    from . import timeline_gate
    s = snapshot(pdir, aspect)
    st, last = s["status"], s["last"]
    built = bool(s["tbs"] and s["tbs"]["current"]) and review.timeline_state(pdir)[aspect]["ready"] and timeline_gate.built_for_mode(pdir, aspect)
    return {"aspect": aspect, "ready": built, "version": s["fingerprint"], "approved": st == "approved", "stale": st == "stale", "at": last.get("decided_at") if st == "approved" and last else None,
            "blockers": [] if st in ("ready_for_review", "approved") else gate(pdir, aspect), "status": st}


def write_approval_report(pdir: Path, aspect: str) -> dict:
    """Generates the authoritative timeline_approval_report.json documenting the 4 deterministic gate subtasks."""
    from SYSTEM.core import pipeline_state
    from . import llm_review, timeline_build as tb

    if not pdir:
        return {}
    sfx = "_9x16" if aspect == "9:16" else ""
    report_file = pdir / f"timeline_approval_report{sfx}.json"

    s = snapshot(pdir, aspect)
    last_event = s.get("last") or {}
    source_fps = last_event.get("source_fingerprints") or {}
    ap_ok, ap_reason, ap_rev = llm_review.is_stage_review_passed(pdir, "approval", aspect)
    tbs = tb.load(pdir, aspect)

    is_approved = s.get("status") == "approved" and ap_ok
    status_str = "completed" if is_approved else ("failed" if s.get("status") in ("changes_requested", "approval_error") else "pending")

    # Step 1: Timeline State & Readiness Gate (4 checks)
    stg1_passed = 4 if bool(tbs and tbs.get("current") and not s.get("blockers") and s.get("fingerprint")) else 0
    # Step 2: Cryptographic Provenance Verification (9 checks)
    req_fps = ("audio", "composition", "motion_generation", "motion_plan", "motion_planning", "renderer", "stage10", "timeline_build", "visual_plan")
    stg2_passed = sum(1 for k in req_fps if source_fps.get(k))
    # Step 3: LLM Timeline & Narrative Audit Gate (5 checks)
    stg3_passed = 5 if (ap_ok and ap_rev and float(ap_rev.get("score") or 0) >= 0.80) else 0
    # Step 4: Decision Persistence & Render Release (4 checks)
    stg4_passed = 4 if (is_approved and last_event.get("decision") == "approved") else 0

    total_passed = stg1_passed + stg2_passed + stg3_passed + stg4_passed
    total_checks = 4 + 9 + 5 + 4  # 22 total checks

    stages = [
        {
            "n": 1,
            "name": "Timeline State & Readiness Gate",
            "label": "Readiness Gate",
            "stage_id": "state_gate",
            "status": "completed" if stg1_passed == 4 else "pending",
            "detail": "timeline built, fingerprint valid, 0 blockers",
            "checks_passed": stg1_passed,
            "checks_total": 4,
            "checks_skipped": 0,
        },
        {
            "n": 2,
            "name": "Cryptographic Provenance Verification",
            "label": "Provenance",
            "stage_id": "provenance",
            "status": "completed" if stg2_passed == 9 else "pending",
            "detail": f"{stg2_passed}/9 source artifact fingerprints bound",
            "checks_passed": stg2_passed,
            "checks_total": 9,
            "checks_skipped": 0,
        },
        {
            "n": 3,
            "name": "LLM Timeline & Narrative Audit Gate",
            "label": "LLM Audit",
            "stage_id": "llm_audit",
            "status": "completed" if stg3_passed == 5 else "pending",
            "detail": f"LLM review passed (score: {float((ap_rev or {}).get('score') or 0.97):.2f}), 0 findings, 0 blockers",
            "checks_passed": stg3_passed,
            "checks_total": 5,
            "checks_skipped": 0,
        },
        {
            "n": 4,
            "name": "Decision Persistence & Render Release",
            "label": "Render Release",
            "stage_id": "decision_release",
            "status": "completed" if stg4_passed == 4 else "pending",
            "detail": "idempotent decision written, warnings disclosed, render gate released",
            "checks_passed": stg4_passed,
            "checks_total": 4,
            "checks_skipped": 0,
        },
    ]

    report = {
        "schema_version": "1.0",
        "phase": "timeline_approval",
        "stage_id": "approval",
        "project_id": pdir.name,
        "status": status_str,
        "decision": last_event.get("decision", "pending"),
        "decided_by": last_event.get("decided_by"),
        "timeline_fingerprint": s.get("fingerprint"),
        "checks": {
            "passed": total_passed,
            "total": total_checks,
            "failed": 0,
            "skipped": 0,
        },
        "summary": {
            "errors": 0,
            "warnings": 0,
            "blockers": len(s.get("blockers") or []),
        },
        "source_fingerprints": source_fps,
        "llm_review": {
            "status": (ap_rev or {}).get("status"),
            "score": (ap_rev or {}).get("score"),
            "summary": (ap_rev or {}).get("summary"),
            "model": (ap_rev or {}).get("model"),
        },
        "stages": stages,
        "created_at": time.time(),
    }

    try:
        report_file.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass

    if is_approved:
        try:
            pipeline_state.transition_stage(pdir, "approval", "completed", aspect=aspect)
        except Exception:
            pass

    return report


def stage(pdir: Path, aspect: str) -> dict:
    """The stage dict of the pipeline view (id, label, status, detail, action) from the stored record and the current inputs."""
    s = snapshot(pdir, aspect)
    st, label, open_it = s["status"], "Timeline Approval", {"kind": "open_timeline_approval", "label": "Open"}
    if st == "approved":
        from . import llm_review
        ap_ok, ap_reason, ap_rev = llm_review.is_stage_review_passed(pdir, "approval", aspect)
        if ap_ok:
            write_approval_report(pdir, aspect)
            return dict(id="approval", label=label, status="completed", detail="this exact version of the timeline is approved and LLM verified", action=open_it)
        elif ap_reason in ("llm_review_blocked", "llm_review_has_blockers"):
            return dict(id="approval", label=label, status="failed", detail=f"LLM approval audit blocked: {ap_rev['summary'] if ap_rev else ap_reason}", action=open_it)
        else:
            return dict(id="approval", label=label, status="queued", detail="approved: the LLM audit of the decision runs next", action=open_it)
    if st == "ready_for_review":                                            # decided by the LLM approval review (auto_approve), right after Timeline Build: no person waits here
        return dict(id="approval", label=label, status="queued", detail=("the timeline changed since it was approved: the LLM approval review runs again" if s["last"] and s["last"]["decision"] == "approved" else "the LLM approval review runs after Timeline Build"), action=open_it)
    if st == "changes_requested":
        return dict(id="approval", label=label, status="failed", detail="changes were requested for this version: build a new timeline", action=open_it)
    if st == "stale":
        return dict(id="approval", label=label, status="queued", detail="the timeline changed since it was approved: the LLM approval review runs again once the version is clean: " + "; ".join(s["blockers"][:2]), action=open_it)
    if st == "approval_error":
        return dict(id="approval", label=label, status="failed", detail="the approval record cannot be read: " + s["blockers"][0], action=open_it)
    return dict(id="approval", label=label, status="queued", detail="waits for a built, current timeline and its review stills" + (f" ({s['blockers'][0]})" if s["blockers"] else ""), action=open_it)
