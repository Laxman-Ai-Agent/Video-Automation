"""The Work Log: what the assistant is doing right now, one line per step, read by the Work Log page (GET /work-log).

Entries are written with `python scripts/work_log.py <status> "<title>" "<detail>"` (append-only work_log.jsonl in the project root): {id, time, status, title, detail}.
status: doing | done | problem | fixed."""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter

from SYSTEM.core import config

router = APIRouter(prefix="/work-log", tags=["work-log"])

LOG_FILE = config.PROJECT_ROOT / "work_log.jsonl"
LIMIT = 300


def read_entries(limit: int = LIMIT) -> list[dict[str, Any]]:
    """The last `limit` entries, oldest first; a missing file or a half-written line is skipped."""
    try:
        lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


@router.get("")
def work_log() -> dict[str, Any]:
    return {"entries": read_entries()}
