"""The live step report of a stage: which of its steps runs, how many items of it are done, written to a file at every change so the Subtasks page and the stage card show a run as it goes
(never an estimate: a step shows only the counts it really reached). One implementation for every stage that reports its steps while it runs (Asset Collection, Motion Validation ...)."""
from __future__ import annotations

import json
import time
from pathlib import Path


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


DONE = ("completed", "warning", "blocked", "skipped_due_to_dependency")


class LiveSteps:
    """`names`: the steps of the stage in order. `live`: the rows are marked `live`, so nothing asks the LLM about a step before the stage's own final report exists."""

    def __init__(self, path: Path, names: tuple[str, ...] | list[str], live: bool = False) -> None:
        self.path, self.live = path, live
        self.rows = [{"n": i, "name": nm, "status": "pending", "detail": "waiting", "checks_passed": 0, "checks_total": 0, "progress_percent": 0} for i, nm in enumerate(names, 1)]
        self.status, self.started = "running", time.time()
        self.write()

    def write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")                          # atomic: readers never see a half-written file
        tmp.write_text(json.dumps({"schema_version": "1.0", "status": self.status, "started_at": self.started, "stages": self.rows, "updated_at": _now()}, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def step(self, n: int, status: str, detail: str, done: int = 0, total: int = 0, evidence: dict | None = None) -> None:
        """`evidence`: the facts the recorded detail stands on (what the LLM check of the step is shown: a step that claims something without facts cannot be confirmed)."""
        pct = 100 if status in DONE else min(99, max(1, round(100 * done / total))) if total and done else 0
        row = self.rows[n - 1]
        row.update(status=status, detail=detail, checks_passed=done, checks_total=total, progress_percent=pct)
        if self.live:
            row["live"] = True
        if evidence is not None:
            row["evidence"] = evidence
        self.write()

    def fail(self, why: str) -> None:
        row = next((r for r in self.rows if r["status"] == "running"), self.rows[-1])
        self.step(row["n"], "failed", why[:300], row["checks_passed"], row["checks_total"])
        self.status = "failed"
        self.write()

    def finish(self) -> None:
        self.status = "completed"
        self.write()


def progress(path: Path) -> dict | None:
    """How far a running stage is, from its live report (None when the report is not of a run in progress): the step that runs, the percent of all steps, the run's start."""
    try:
        rep = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if rep.get("status") != "running":
        return None
    rows = rep.get("stages") or []
    now = next((r for r in rows if r["status"] == "running"), None)
    return {"detail": f"{now['name']}: {now['detail']}" if now else "starting", "started_at": rep.get("started_at"),
            "percent": round(sum(100 if r["status"] in DONE else r.get("progress_percent", 0) for r in rows) / max(1, len(rows)), 1)}
