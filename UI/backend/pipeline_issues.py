"""The real problems of a project: failed and stuck stages and the ones waiting for an LLM review.

Everything here is read from data the pipeline already wrote: the agent communications log (stage_failed / recovery_detected / stage_started
events with their diagnostics), the stage list of pipeline_view.build() and the job error. Nothing is invented: no log line, no issue.
An issue disappears by itself once the stage completes (or the log shows a newer start or completion).
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

LOG_TAIL_BYTES = 600_000                                                           # the newest events are enough: only the last event of each stage matters
DEFAULT_STUCK_S = 600                                                              # a stage that started and reported nothing for this long is stuck
STUCK_AFTER_S = {"analyzer": 1500, "render": 2400, "qc": 900, "motion_gen": 1200}      # expected upper bounds of the slow stages, in seconds

_FAILURE = ("stage_failed", "recovery_detected")
_DONE = ("stage_completed",)
_START = ("stage_started",)


def _events(pdir: Path) -> list[dict]:
    f = pdir / "agent-communications" / "communications.jsonl"
    if not f.exists():
        return []
    with f.open("rb") as fh:
        fh.seek(0, 2)
        size = fh.tell()
        fh.seek(max(0, size - LOG_TAIL_BYTES))
        raw = fh.read().decode("utf-8", errors="replace")
    lines = raw.splitlines()
    rows = []
    for line in lines[1:] if size > LOG_TAIL_BYTES else lines:                      # the first line of a tail may be cut in half
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def _epoch(iso: str | None) -> float | None:
    try:
        return datetime.fromisoformat(iso).timestamp() if iso else None
    except ValueError:
        return None


def build(pdir: Path, stages: list[dict], job_error: str | None = None, now: float | None = None) -> list[dict]:
    now = time.time() if now is None else now
    by_id = {s["id"]: s for s in stages}
    last: dict[str, dict] = {}                                                      # the newest lifecycle event of each stage
    last_failure: dict[str, dict] = {}                                              # and the newest failure of it
    last_diag: dict[str, dict] = {}
    for ev in _events(pdir):
        kind = (ev.get("metadata") or {}).get("event")
        sid = ev.get("stage_id")
        if not sid or kind not in _FAILURE + _DONE + _START:
            continue
        last[sid] = ev
        if kind in _DONE:
            last_failure.pop(sid, None)                                             # completed after failing: resolved
            last_diag.pop(sid, None)
        if kind in _FAILURE:
            last_failure[sid] = ev
            if (ev.get("metadata") or {}).get("diagnostic"):
                last_diag[sid] = ev["metadata"]["diagnostic"]                       # stage_failed carries only text; recovery_detected carries the diagnosis

    issues: list[dict] = []
    for sid, ev in last.items():
        stage = by_id.get(sid)
        if stage is None or stage["status"] == "completed":                         # the stage finished: whatever happened before is resolved
            continue
        kind = (ev.get("metadata") or {}).get("event")
        at = _epoch(ev.get("timestamp"))
        fail = last_failure.get(sid)
        if fail is not None:                                                        # failed and not completed since (a newer start is a retry of the failure)
            diag = (fail.get("metadata") or {}).get("diagnostic") or last_diag.get(sid) or {}
            issues.append({
                "id": f"{sid}:failed", "severity": "error", "stage_id": sid, "stage_label": stage["label"], "source": "agent log",
                "component": diag.get("agent_id") or fail.get("sender_agent_id") or sid,
                "message": diag.get("message") or fail.get("content") or "stage failed", "code": diag.get("code"),
                "attempts": diag.get("attempt"), "retry_limit": diag.get("retry_limit"), "at": _epoch(fail.get("timestamp")),
            })
        limit = STUCK_AFTER_S.get(sid, DEFAULT_STUCK_S)
        # stuck = a stage that IS running (or retrying) and reports no progress: a stage waiting for an LLM review, queued or blocked is not stuck, whatever its last lifecycle event was
        if kind in _START and at is not None and now - at > limit and stage["status"] in ("running", "retrying"):
            issues.append({
                "id": f"{sid}:stuck", "severity": "stuck", "stage_id": sid, "stage_label": stage["label"], "source": "pipeline monitor",
                "component": ev.get("sender_agent_id") or sid,
                "message": f"started {int((now - at) // 60)} min ago and reported no progress since (expected within {limit // 60} min)",
                "at": at,
            })

    seen = {i["id"] for i in issues}
    for s in stages:                                                                # stage statuses that need attention, straight from the pipeline view
        if s["status"] == "failed" and f"{s['id']}:failed" not in seen:
            issues.append({"id": f"{s['id']}:failed", "severity": "error", "stage_id": s["id"], "stage_label": s["label"], "source": "pipeline status",
                           "component": s["id"], "message": s.get("detail") or "stage failed", "at": None})
        elif s["status"] == "waiting_for_approval":
            issues.append({"id": f"{s['id']}:approval", "severity": "warning", "stage_id": s["id"], "stage_label": s["label"], "source": "pipeline status",
                           "component": s["id"], "message": s.get("detail") or "waiting for your decision", "at": None})
    if job_error:
        issues.append({"id": "job:error", "severity": "error", "stage_id": None, "stage_label": "Pipeline job", "source": "job",
                       "component": "job", "message": str(job_error), "at": None})

    issues += _subtask_issues(pdir, stages)
    for i in issues:                                                                # where and in what state: the subtask (None = the stage itself) and the stage's current status
        i.setdefault("subtask", None)
        i["stage_status"] = by_id.get(i["stage_id"] or "", {}).get("status")
    return issues


def _subtask_issues(pdir: Path, stages: list[dict]) -> list[dict]:
    """The steps a stage recorded as warning / failed / blocked in its own report, and the LLM step checks that reject a recorded result.
    Only for a stage that is completed, failed or waiting for a decision: a queued or running stage's report belongs to an older run."""
    from . import step_llm_check, store
    aspect = store.read_info(pdir).get("aspect") or "9:16"
    out: list[dict] = []
    for s in stages:
        if s["status"] not in ("completed", "failed", "waiting_for_approval"):
            continue
        steps, _report, f = step_llm_check.steps(pdir, s["id"], aspect)
        if not steps:
            continue
        written = f.stat().st_mtime if f is not None and f.exists() else None
        checks = step_llm_check.load(pdir, s["id"], aspect)["steps"]
        for st in steps:
            state = (st.get("status") or "").lower()
            sev = "error" if state in ("failed", "blocked", "error") else ("warning" if state == "warning" else None)
            if sev:
                out.append({"id": f"{s['id']}:step:{st['n']}", "severity": sev, "stage_id": s["id"], "stage_label": s["label"],
                            "source": f"step report ({f.name})", "component": st.get("name"), "subtask": st.get("name"),
                            "message": st.get("detail") or f"step {state}", "at": written})
            c = checks.get(str(st["n"]))
            if c and c.get("current") and c.get("verdict") == "rejects":
                out.append({"id": f"{s['id']}:llm:{st['n']}", "severity": "warning", "stage_id": s["id"], "stage_label": s["label"],
                            "source": "LLM step check", "component": c.get("model") or "llm", "subtask": st.get("name"),
                            "message": f"The LLM rejects the recorded result ({st.get('detail')}): {c.get('note')}", "at": c.get("at")})
    return out
