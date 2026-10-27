"""The project's small state store and two read-only questions about the plan and the timeline. Nothing here replaces a stage and nobody approves anything through it.
  review.json   the generation record of the planning jobs ("generation": state, progress, error; see promptgen.py), written under one lock
  plan_blockers  why the scene plan cannot be used yet (it does not exist, or the plan checks found errors)
  timeline_state per aspect: has the pre-render check run on the current composition, and did it pass."""
import hashlib
import json
import threading
import time
from pathlib import Path

from .models import ScenePlan

ASPECTS = ("16:9", "9:16")

LOCK = threading.RLock()                 # the planning jobs (promptgen.py) and the request threads read-modify-write the same file


class ReviewError(ValueError):
    """A request the current project state does not allow (the API turns it into a 409/422 with this message)."""

    def __init__(self, message: str, blockers: list[str] | None = None):
        super().__init__(message)
        self.blockers = blockers or []


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def h(*parts) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:16]


def _retry(fn):
    """Windows refuses to read or replace a file for a moment while another thread replaces it (a planning job runs beside the requests)."""
    for i in range(20):
        try:
            return fn()
        except PermissionError:
            if i == 19:
                raise
            time.sleep(0.05)


def _read(path: Path) -> str:
    return _retry(lambda: path.read_text(encoding="utf-8"))


def _load(path: Path, default):
    try:
        return json.loads(_read(path)) if path.exists() else default
    except (OSError, ValueError):
        return default


def _save(path: Path, data) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    _retry(lambda: tmp.replace(path))


def state_of(pdir: Path) -> dict:
    return _load(pdir / "review.json", {})


def _plan(pdir: Path) -> ScenePlan | None:
    f = pdir / "scene_plan.json"
    return ScenePlan.model_validate_json(_read(f)) if f.exists() else None


def plan_blockers(pdir: Path) -> list[str]:
    """Why the scene plan cannot be used yet: it does not exist, or its checks found errors (empty = it can)."""
    if _plan(pdir) is None:
        return ["The plan does not exist yet: run Visual Planning"]
    try:
        from . import plan_checks
        errors, _ = plan_checks.check(pdir)
    except Exception:                                  # the plan files are still being written, or the composition is not built yet
        errors = []
    return [f"plan error: {e}" for e in errors]


def timeline_state(pdir: Path) -> dict:
    """Per aspect: has the pre-render check run on the current composition, and did it pass. A passed check on fresh files = a verified timeline."""
    out = {}
    for aspect in ASPECTS:
        sfx = "_9x16" if aspect == "9:16" else ""
        comp, report = pdir / f"composition{sfx}.json", pdir / f"prerender_report{sfx}.json"
        data = _load(report, None)
        inputs = [f for f in (comp, pdir / "match_report.json", pdir / "prompts_map.json", pdir / "crops.json") if f.exists()]
        fresh = bool(data and comp.exists() and report.stat().st_mtime >= max(f.stat().st_mtime for f in inputs))
        summary = (data or {}).get("summary", {})
        out[aspect] = {
            "composition": comp.exists(), "checked": data is not None, "fresh": fresh, "ok": bool(data and data.get("ok")),
            "errors": summary.get("error", 0), "warnings": summary.get("warning", 0), "ready": bool(fresh and data and data.get("ok")),
            "preview_video": (pdir / f"out_preview{sfx}.mp4").exists(), "final_video": (pdir / f"out{sfx}.mp4").exists(),
            "findings": [f for f in (data or {}).get("findings", []) if f["severity"] != "info"][:60],
        }
    return out
