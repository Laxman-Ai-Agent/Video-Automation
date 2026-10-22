"""The attempt counter of the automatic Solve-warnings loop of Motion Planning (POST /motion-planning/fix-warnings?auto=true).

At most MAX_AUTO_FIXES automatic attempts per scene plan: the count lives in `motion_autofix.json` (not an input of any stage), keyed by the hash of scene_plan.json, so page refreshes and repeated
requests cannot add attempts and a NEW scene plan starts again. Each attempt keeps what `motion_planning.solve` decided. The manual Solve warnings button is not counted and not limited."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

MAX_AUTO_FIXES = 5
FILE = "motion_autofix.json"


class Exhausted(Exception):
    pass


def _file(name: str) -> str:
    return FILE if name == "plan" else f"motion_autofix_{name}.json"


def _key(pdir: Path) -> str:
    f = pdir / "scene_plan.json"
    return hashlib.sha256(f.read_bytes()).hexdigest()[:16] if f.exists() else "none"


def state(pdir: Path, name: str = "plan") -> dict:
    try:
        d = json.loads((pdir / _file(name)).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    return d if d.get("scene_plan") == _key(pdir) else {"scene_plan": _key(pdir), "attempts": []}


def count(pdir: Path, done: dict, name: str = "plan") -> dict:
    """Record one automatic attempt (what solve decided); raises Exhausted when the limit is already used up."""
    d = state(pdir)
    if len(d["attempts"]) >= MAX_AUTO_FIXES:
        raise Exhausted(f"{MAX_AUTO_FIXES} automatic attempts were used for this scene plan; warnings that remain were not solved")
    d["attempts"].append({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "moved": done.get("moved", 0), "earlier": done.get("earlier", 0), "accepted": done.get("accepted", 0), "aligned": done.get("aligned", 0), "kept": done.get("kept", [])})
    tmp = (pdir / FILE).with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(pdir / FILE)
    return d
