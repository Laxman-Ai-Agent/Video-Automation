"""Jobs of the Resource Manager (discover, audit, import, verify, refresh). They are not project jobs (backend/jobs.py is one active job per PROJECT), so this is the same idea in the same
thread pool: one active resource job at a time (they all write the one registry), progress messages while it runs, and every state change written to
reports/RESOURCE_MANAGER/jobs/<id>.json so a failure can be reproduced from the file."""
from __future__ import annotations

import json
import secrets
import threading
import time

from . import config, jobs, resource_library as rl
from .errors import ApiError

DIR = config.PROJECT_ROOT / "reports" / "RESOURCE_MANAGER" / "jobs"
_lock = threading.Lock()
_jobs: dict[str, dict] = {}


def _save(j: dict) -> None:
    rl.atomic_write(DIR / f"{j['id']}.json", json.dumps(j, indent=1, ensure_ascii=False) + "\n")


def running() -> dict | None:
    return next((j for j in _jobs.values() if j["state"] == "running"), None)


def get(job_id: str) -> dict:
    j = _jobs.get(job_id)
    if j is None:
        p = DIR / f"{job_id}.json"
        if job_id.replace("-", "").isalnum() and p.is_file():
            j = json.loads(p.read_text(encoding="utf-8"))
            if j["state"] == "running":                                  # a file that says running while nothing runs: the server restarted
                j["state"], j["error"] = "interrupted", {"code": "interrupted", "message": "the server stopped while this job was running"}
    if j is None:
        raise ApiError(404, "job_missing", "no such resource job")
    return j


def start(kind: str, fn, *args) -> dict:
    """Run fn(*args, progress=callable) in the pool. fn returns a JSON-able result or raises an error that has `.code` and `.message` (AuditError, ResourceError)."""
    with _lock:
        cur = running()
        if cur:
            raise ApiError(409, "job_running", f"a resource job is already running ({cur['kind']})", "wait for it to finish")
        j = {"id": time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(2), "kind": kind, "state": "running", "started_at": rl.now(), "finished_at": None, "progress": [], "result": None, "error": None}
        _jobs[j["id"]] = j
        _save(j)

    def say(msg: str) -> None:
        j["progress"] = [*j["progress"][-40:], f"{time.strftime('%H:%M:%S')} {msg}"]
        _save(j)

    def run() -> None:
        try:
            j["result"], j["state"] = fn(*args, progress=say), "done"
        except Exception as e:                                           # the message is shown to the user: codes and messages of our own errors only
            code = getattr(e, "code", None)
            j["state"], j["error"] = "failed", {"code": code or "unexpected", "message": getattr(e, "message", None) or "unexpected error (details in the job file)"}
            if not code:
                j["error"]["detail"] = repr(e)[:300]
        finally:
            j["finished_at"] = rl.now()
            _save(j)

    jobs._pool.submit(run)
    return j
