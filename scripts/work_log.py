"""Add one line to the Work Log shown on the Work Log page: python scripts/work_log.py <doing|done|problem|fixed> "<title>" "<detail>" """
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

LOG_FILE = Path(__file__).resolve().parents[1] / "work_log.jsonl"
STATUSES = ("doing", "done", "problem", "fixed")


def add(status: str, title: str, detail: str = "") -> dict:
    if status not in STATUSES:
        raise SystemExit(f"status must be one of {STATUSES}")
    try:
        n = sum(1 for _ in LOG_FILE.open(encoding="utf-8"))
    except OSError:
        n = 0
    entry = {"id": n + 1, "time": datetime.now().isoformat(timespec="seconds"), "status": status, "title": title, "detail": detail}
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    add(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
