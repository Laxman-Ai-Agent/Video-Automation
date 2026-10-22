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
EVIDENCE_CHARS = 12_000                                                            # the part of the report the LLM sees besides the step (a full report can be very large)
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


def _hash(step: dict) -> str:
    return hashlib.sha256(json.dumps(step, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def load(pdir: Path, stage_id: str, aspect: str) -> dict:
    """The stored checks, each marked current (it checked exactly the step now recorded) or not."""
    f = _checks_file(pdir, stage_id, aspect)
    try:
        data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except ValueError:
        data = {}
    current = {str(s["n"]): _hash(s) for s in steps(pdir, stage_id, aspect)[0]}
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


def _ask(pdir: Path, stage_id: str, step: dict, report: dict, aspect: str) -> dict:
    from SYSTEM.core import llm_gateway
    evidence = {k: v for k, v in report.items() if k != "stages"}
    ev_text = json.dumps(evidence, ensure_ascii=False)[:EVIDENCE_CHARS]
    req = llm_gateway.LlmGatewayRequest(
        project_id=pdir.name,
        stage_id=stage_id,
        agent_id="step_llm_check",
        purpose="review",
        model_profile="fast_structured",
        system_prompt=("You verify one step of a video pipeline stage. The step is a deterministic check; it recorded a status and a detail. "
                       "Using only the evidence given, say whether the recorded result holds. 'confirms' = the status and detail are consistent with the evidence; "
                       "'questions' = the evidence is insufficient or something looks off; 'rejects' = the evidence contradicts the recorded result. "
                       "Do not invent facts. Answer in JSON."),
        user_prompt=(f"Stage: {stage_id}\nStep {step.get('n')}: {step.get('name')}\nRecorded status: {step.get('status')}\n"
                     f"Recorded detail: {step.get('detail')}\nChecks: {step.get('checks_passed')}/{step.get('checks_total')}\n\n"
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
            h = _hash(step)
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
