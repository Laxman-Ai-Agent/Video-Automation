"""Audio Analyzer subtasks as they really are: status, percent and LLM verification of every step of the analyzer chain.

Read-only. Everything comes from what the executor and the steps already write (job.json, timings.json, the step outputs and the LLM review files); nothing is estimated.
The steps are the ones of CHAINS["transcribe"] in the pipeline adapter plus the LLM approval of the final result, so a new analyzer step is added to SUBTASKS here once.
"""
from __future__ import annotations

import json
from pathlib import Path

from SYSTEM.policies import llm_review

# (step name, label, outputs that prove it finished)
SUBTASKS = (
    ("transcribe", "Speech-to-text (Whisper)", ("transcript.json",)),
    ("refine", "Transcript check and correction (LLM)", ("transcript_review.json",)),
    ("cuts", "Sentence and silence cuts, audio analysis", ("cuts.json", "audio_analysis.json")),
)
APPROVAL = ("approval", "Final transcript approval (LLM)")
LLM_OK = ("applied", "cached", "not_needed")        # transcript_review.json llm.status values that mean the LLM check is done
LLM_DOWN = ("unavailable", "failed")


def _json(f: Path) -> dict:
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):               # job.json is rewritten in place: a read can catch it empty
        return {}


def _row(sid: str, name: str, status: str, percent: float | None, llm: dict, message: str = "") -> dict:
    return {"id": sid, "name": name, "status": status, "percent": percent, "llm": llm, "message": message}


def _llm(status: str, detail: str = "") -> dict:
    return {"status": status, "detail": detail}      # status: none (the step has no LLM check) | pending | running | completed | failed


def _refine_llm(pdir: Path, step_status: str, percent: float) -> dict:
    info = _json(pdir / "transcript_review.json").get("llm") or {}
    s = info.get("status")
    if s in LLM_OK and step_status != "running":
        return _llm("completed", "no words to check" if s == "not_needed" else ("answered earlier (cached)" if s == "cached" else f"checked by {info.get('model') or 'the LLM'}"))
    if s in LLM_DOWN:
        return _llm("failed", info.get("error") or s)
    if step_status == "running" and 50 <= percent < 75:      # refine() reports 50 before it asks the LLM and 75 when the answer is in
        return _llm("running", "the LLM is checking every word")
    return _llm("pending")


def _approval(pdir: Path, running: bool, cuts_done: bool) -> dict:
    rev = _json(llm_review.review_path(pdir, "analyzer"))
    st = rev.get("status")
    if st == "passed":
        return _row(APPROVAL[0], APPROVAL[1], "completed", 100, _llm("completed", f"passed, score {rev.get('score')}"), rev.get("summary") or "")
    if st:                                                     # needs_review / blocked / cannot_determine: never an approval
        return _row(APPROVAL[0], APPROVAL[1], "failed", 0, _llm("failed", f"{st}, score {rev.get('score')}"), rev.get("summary") or rev.get("error") or "")
    if running and cuts_done:
        return _row(APPROVAL[0], APPROVAL[1], "running", None, _llm("running", "the LLM is judging the final transcript"))
    return _row(APPROVAL[0], APPROVAL[1], "pending", 0, _llm("pending"))


def subtasks(pdir: Path, running: bool) -> dict:
    """{running, percent, subtasks: [{id, name, status: pending|running|completed|failed, percent|None, llm: {status, detail}, message}]}."""
    job = _json(pdir / "job.json")
    timings = (_json(pdir / "timings.json").get("steps") or {})
    rows, cuts_done = [], False
    for name, label, outputs in SUBTASKS:
        done = all((pdir / o).exists() for o in outputs)
        here = job.get("step") == name
        pct = job.get("percent") or 0
        if running and here and not job.get("error"):
            status, percent, msg = "running", pct, ""
        elif not running and here and job.get("error"):
            status, percent, msg = "failed", pct, job["error"]
        elif done and timings.get(name, {}).get("status") not in ("failed", "stopped"):
            status, percent, msg = "completed", 100, ""
        else:
            status, percent, msg = "pending", 0, ""
        if name == "cuts":
            cuts_done = status == "completed" or (status == "running" and (pdir / "audio_analysis.json").exists())
        llm = _refine_llm(pdir, status, pct) if name == "refine" else _llm("none")
        rows.append(_row(name, label, status, percent, llm, msg))
    rows.append(_approval(pdir, running, cuts_done))
    known = [r["percent"] if r["percent"] is not None else 0 for r in rows]
    return {"running": running, "percent": round(sum(known) / len(known)), "subtasks": rows}
