"""An LLM check of every step a stage recorded in its report.

The stage's steps are deterministic checks (motion_generation.json "stages", ...). Here each recorded step is shown to the LLM on its own, with the
stage report as evidence, and the LLM says whether the recorded result holds: confirms / questions / rejects, with a note. One gateway call per
step, in a background thread so no page waits. Results are stored per step with the hash of what was checked, so a step is checked again only
when its recorded result changes. Nothing is invented: a failed or unavailable LLM call is stored as verdict "error" with the reason.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path

STEP_REPORTS = {                                                                    # stage -> the report whose "stages" list the stage itself writes ({sfx} = the 9:16 suffix)
    "analyzer": "audio_analysis.json", "segmentation": "scene_segmentation.json", "planning": "visual_planning.json",
    "motion_plan": "motion_planning{sfx}.json", "motion_gen": "motion_generation{sfx}.json",
    "motion_validation": "motion_timeline_validation{sfx}.json", "timeline": "timeline_build_report{sfx}.json", "qc": "final_qc_report.json",
}
EVIDENCE_CHARS = 30_000                                                            # the part of the report the LLM sees besides the step (a full report can be very large)
CHECK_VERSION = "2.1"                                                              # cache version: bump to invalidate stale checks across all projects
_running: set[tuple[str, str]] = set()
_lock = threading.Lock()


def _sfx(aspect: str) -> str:
    return "_9x16" if aspect == "9:16" else ""


def report_file(pdir: Path, stage_id: str, aspect: str) -> Path | None:
    name = STEP_REPORTS.get(stage_id)
    return pdir / name.format(sfx=_sfx(aspect)) if name else None


def steps(pdir: Path, stage_id: str, aspect: str) -> tuple[list[dict], dict | None, Path | None]:
    """The recorded steps of the stage, the whole report and its file (empty when the stage keeps no step report)."""
    f = report_file(pdir, stage_id, aspect)
    if f is None or not f.exists():
        return [], None, None
    try:
        rep = json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        return [], None, f
    out = [{"n": s.get("n"), "name": s.get("name") or s.get("label"), "status": s.get("status"), "detail": s.get("detail"),
            "checks_passed": s.get("checks_passed"), "checks_total": s.get("checks_total")}
           for s in (rep.get("stages") or []) if isinstance(s, dict) and "status" in s]
    return out, rep, f


def _checks_file(pdir: Path, stage_id: str, aspect: str) -> Path:
    return pdir / f"llm_step_checks_{stage_id}{_sfx(aspect)}.json"


def _hash(step: dict, report: dict | None = None) -> str:
    fp = (report or {}).get("source_fingerprint") or ""
    payload = {"v": CHECK_VERSION, "step": step, "fp": fp}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def load(pdir: Path, stage_id: str, aspect: str) -> dict:
    """The stored checks, each marked current (it checked exactly the step now recorded) or not."""
    f = _checks_file(pdir, stage_id, aspect)
    try:
        data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except ValueError:
        data = {}
    st_list, rep, _ = steps(pdir, stage_id, aspect)
    current = {str(s["n"]): _hash(s, rep) for s in st_list}
    out = {}
    for n, c in (data.get("steps") or {}).items():
        out[n] = {**c, "current": current.get(n) == c.get("hash")}
    return {"steps": out, "running": (pdir.name, stage_id) in _running, "updated_at": data.get("updated_at")}


def _done(check: dict) -> bool:
    """A step is checked only by a real verdict on its current result: an `error` (LLM unavailable, session limit, open circuit) is retried, never counted as a check."""
    return bool(check.get("current")) and check.get("verdict") != "error"


def pending(pdir: Path, stage_id: str, aspect: str) -> int:
    """How many recorded steps have no LLM check of their current result."""
    checks = load(pdir, stage_id, aspect)["steps"]
    return sum(1 for s in steps(pdir, stage_id, aspect)[0] if not _done(checks.get(str(s["n"]), {})))


def build_step_evidence(stage_id: str, step: dict, report: dict) -> dict:
    """Builds focused, authoritative evidence for verifying a deterministic stage step.
    Ensures critical source metrics, sentences/clause splits, and validation fields are preserved
    without being pushed out by uncompressed scene dumps."""
    if not isinstance(report, dict):
        return {}

    evidence = {
        "schema_version": report.get("schema_version"),
        "timing_rules": report.get("timing_rules"),
        "source_fingerprint": report.get("source_fingerprint"),
        "source_transcript": report.get("source_transcript"),
        "source_audio_analysis": report.get("source_audio_analysis"),
        "language": report.get("language"),
        "audio_duration_seconds": report.get("audio_duration_seconds"),
        "segmentation_method": report.get("segmentation_method"),
        "semantic_confidence": report.get("semantic_confidence"),
        "needs_review": report.get("needs_review"),
    }

    # Authoritative source data metrics
    source_data = report.get("source_data")
    if source_data:
        evidence["source_data"] = source_data
    else:
        evidence["source_data"] = {
            "source_transcript_file": report.get("source_transcript"),
            "source_audio_analysis": report.get("source_audio_analysis"),
            "transcript_segment_count": report.get("source_segments"),
            "word_count": report.get("source_words"),
            "measured_pause_count": report.get("source_pauses"),
            "audio_duration_seconds": report.get("audio_duration_seconds"),
            "scene_count": len(report.get("scenes", [])) if isinstance(report.get("scenes"), list) else None,
        }

    # Sentence & clause detection data
    if "sentence_and_clause_detection" in report:
        evidence["sentence_and_clause_detection"] = report["sentence_and_clause_detection"]

    if "validation" in report:
        evidence["validation"] = report["validation"]
    if "llm" in report:
        evidence["llm"] = report["llm"]
    if "config" in report:
        evidence["config"] = report["config"]

    # Compact scene summary to guarantee every scene is visible within character limits
    scenes = report.get("scenes")
    if isinstance(scenes, list):
        evidence["scene_count"] = len(scenes)
        evidence["scenes_summary"] = [
            {
                "scene_id": s.get("scene_id") or f"scene_{s.get('scene_index', idx + 1):03d}",
                "scene_index": s.get("scene_index", idx + 1),
                "start_time": s.get("start_time"),
                "end_time": s.get("end_time"),
                "source_segment_ids": s.get("source_segment_ids"),
                "source_sentence_ids": s.get("source_sentence_ids"),
                "word_range": s.get("word_range"),
                "transcript": (s.get("transcript") or "")[:80],
                "timing_source": s.get("timing_source"),
                "boundary_after": s.get("boundary_after"),
                "boundary_before": s.get("boundary_before"),
                "pause_after_seconds": s.get("pause_after_seconds"),
            }
            for idx, s in enumerate(scenes)
        ]

    # Include other stage-specific top-level keys
    for k, v in report.items():
        if k not in ("stages", "scenes", "source_data", "sentence_and_clause_detection", "validation", "llm", "config"):
            if k not in evidence:
                evidence[k] = v

    return evidence


def _step_guidance(stage_id: str, step: dict) -> str:
    n = step.get("n")
    if stage_id == "segmentation":
        if n == 1:
            return (
                "Step Guidance (Analysis Data Reader):\n"
                "Verify the source transcript segments count, word count, measured pause count, and audio duration against 'source_data'.\n"
                "Note: 'transcript segments' are the input speech units from transcription; 'scenes' are the output units produced by segmentation. "
                "Measured pauses are acoustic pauses from the source audio analysis, not inter-scene pauses."
            )
        if n == 2:
            return (
                "Step Guidance (Sentence & Clause Detection):\n"
                "The recorded detail reports: '<units> units (<clause_splits> clause splits), <cuts> places where a scene may end'.\n"
                "Verify the 3 primary metrics against 'sentence_and_clause_detection':\n"
                "1. 'units' must match 'unit_count' (count of syntactic units in 'sentences').\n"
                "2. 'clause splits' must match 'clause_split_count' (the count of sentences split into multiple units due to long duration; 0 if no sentence was split).\n"
                "3. 'places where a scene may end' must match 'potential_cut_count' (the count of candidate cut points in 'allowed_cuts').\n"
                "Note: A 'clause split' refers strictly to splitting a long sentence into multiple units (clause_split_count: 0 here). "
                "Do NOT confuse 'clause splits' with candidate cut points at clause punctuation marks (clause_punctuation in candidate_cut_points_by_type), which allow scene boundaries at commas without splitting the underlying sentence unit."
            )
        if n == 3:
            return "Step Guidance (Semantic Understanding):\nVerify semantic grouping LLM status and reuse/call status against the 'llm' object."
        if n == 4:
            return "Step Guidance (Topic & Idea Change Detection):\nVerify topic and idea boundary decisions in boundary_before/boundary_after across scenes."
        if n == 5:
            return "Step Guidance (Scene Boundary & Grouping):\nVerify the count of generated scenes and source segments in scenes_summary."
        if n == 6:
            return "Step Guidance (Duration & Timing Assignment):\nVerify start and end timestamps and timing_source across scenes_summary."
        if n == 7:
            return "Step Guidance (Scene Validation & Continuity):\nVerify validation status, transcript coverage, chronological order, and errors/warnings against 'validation'."
    return "Verify whether the recorded status and detail are supported by and consistent with the provided evidence."


def _ask(pdir: Path, stage_id: str, step: dict, report: dict, aspect: str) -> dict:
    from SYSTEM.core import llm_gateway
    evidence = build_step_evidence(stage_id, step, report)
    ev_text = json.dumps(evidence, ensure_ascii=False)
    if len(ev_text) > EVIDENCE_CHARS:
        ev_text = ev_text[:EVIDENCE_CHARS]
    guidance = _step_guidance(stage_id, step)
    req = llm_gateway.LlmGatewayRequest(
        project_id=pdir.name,
        stage_id=stage_id,
        agent_id="step_llm_check",
        purpose="review",
        model_profile="fast_structured",
        system_prompt=("You verify one deterministic step of a video generation pipeline stage. "
                       "The step recorded a status and a detail string. "
                       "Using only the verified evidence provided, determine if the recorded result holds.\n"
                       "- 'confirms': The status and detail are consistent with and supported by the evidence.\n"
                       "- 'questions': The evidence is insufficient, ambiguous, or shows minor discrepancies.\n"
                       "- 'rejects': The evidence directly contradicts the recorded result.\n"
                       "Important: Do not confuse different metric types (e.g. source transcript segments are input speech chunks, while scenes are segmented output units; measured pauses are physical acoustic pauses from audio analysis, not scene gaps). Answer in JSON."),
        user_prompt=(f"Stage: {stage_id}\nStep {step.get('n')}: {step.get('name')}\nRecorded status: {step.get('status')}\n"
                     f"Recorded detail: {step.get('detail')}\nChecks: {step.get('checks_passed')}/{step.get('checks_total')}\n\n"
                     f"{guidance}\n\n"
                     f"Evidence (the stage report without its step list, may be cut at {EVIDENCE_CHARS} characters):\n{ev_text}\n\n"
                     'Return ONLY this JSON object: {"verdict": "confirms" | "questions" | "rejects", "note": "one or two sentences: why"}'),
        structured_schema={"verdict": "confirms | questions | rejects", "note": "one or two sentences: why"},
        timeout=120,
        metadata={"aspect": aspect, "step": step.get("n")},
    )
    t0 = time.time()
    try:
        resp = llm_gateway.get_gateway().execute(req)
    except Exception as e:                                                          # the call itself broke: stored as an error, never as a pass
        return {"verdict": "error", "note": f"LLM call failed: {e}", "model": None, "latency_ms": int((time.time() - t0) * 1000)}
    data = resp.structured_data or {}
    verdict = str(data.get("verdict", "")).strip().lower()
    if resp.error or verdict not in ("confirms", "questions", "rejects"):
        return {"verdict": "error", "note": resp.error or f"unusable LLM answer: {(resp.raw_text or '')[:200]}", "model": resp.model, "latency_ms": resp.latency_ms,
                "blocked": resp.status in ("blocked", "failed")}
    note = data.get("note") or data.get("reason") or data.get("rationale") or data.get("explanation") or ""
    return {"verdict": verdict, "note": str(note)[:600], "model": resp.model, "latency_ms": resp.latency_ms}


def _run(pdir: Path, stage_id: str, aspect: str) -> None:
    try:
        f = _checks_file(pdir, stage_id, aspect)
        for step in steps(pdir, stage_id, aspect)[0]:                               # re-read every time: the report may change while the checks run
            recorded, report, _ = steps(pdir, stage_id, aspect)
            step = next((s for s in recorded if s["n"] == step["n"]), None)
            if step is None or report is None:
                continue
            h = _hash(step, report)
            try:
                data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
            except ValueError:
                data = {}
            prev = (data.get("steps") or {}).get(str(step["n"]), {})
            if prev.get("hash") == h and prev.get("verdict") != "error":
                continue                                                            # this exact result was already checked (an earlier error is asked again)
            res = _ask(pdir, stage_id, step, report, aspect)
            data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
            data.setdefault("steps", {})[str(step["n"])] = {**res, "hash": h, "at": time.time()}
            data.update({"stage_id": stage_id, "report": report_file(pdir, stage_id, aspect).name, "updated_at": time.time()})
            f.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
            if res.get("verdict") == "error" and res.get("blocked"):
                break                                                               # the LLM is unavailable (session limit / open circuit): the remaining steps are asked on the next start, not failed one by one
    finally:
        with _lock:
            _running.discard((pdir.name, stage_id))


def start(pdir: Path, stage_id: str, aspect: str) -> bool:
    """Start checking the steps that have no check of their current result. False when nothing is pending or a check of this stage already runs."""
    key = (pdir.name, stage_id)
    with _lock:
        if key in _running or pending(pdir, stage_id, aspect) == 0:
            return False
        _running.add(key)
    threading.Thread(target=_run, args=(pdir, stage_id, aspect), daemon=True, name=f"step-llm-check-{stage_id}").start()
    return True
