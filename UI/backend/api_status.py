"""GET /status: merges the running job, the pipeline's job.json and the files on disk into one answer."""
import json
from pathlib import Path

from . import jobs, store
from .api_models import Status
from .models import MatchReport, PromptsMap


def image_count(pdir: Path) -> int:
    for sub in ("inbox", "raw"):
        d = pdir / "assets" / sub
        if d.exists():
            n = sum(1 for f in d.iterdir() if f.is_file() and f.suffix.lower() in store.IMAGE_EXTS)
            if n:
                return n
    return 0


def required_count(pdir: Path) -> int:
    f = pdir / "prompts_map.json"
    return sum(1 for p in PromptsMap.model_validate_json(f.read_text(encoding="utf-8")).prompts if p.required) if f.exists() else 0


def waiting_for(pdir: Path) -> tuple[str | None, str | None]:
    """plan -> images -> review. Returns (waiting_for, exact command for Claude Code when it is the plan).
    Files can be mid-write while a job runs: an unreadable file means "nothing to report this time"."""
    try:
        return _waiting_for(pdir)
    except ValueError:                       # json / pydantic validation errors are ValueErrors
        return None, None


def _waiting_for(pdir: Path) -> tuple[str | None, str | None]:
    has = lambda name: (pdir / name).exists()
    if not store.uses_images(pdir):          # Motion-Only mode never waits for images
        return ("plan", f"/plan {pdir.name}") if has("transcript.json") and has("cuts.json") and not has("scene_plan.json") else (None, None)
    if has("transcript.json") and has("cuts.json") and not has("scene_plan.json"):
        return "plan", f"/plan {pdir.name}"
    if has("scene_plan.json") and has("prompts_map.json"):
        if image_count(pdir) == 0:
            return "images", None
        if has("match_report.json"):
            rep = MatchReport.model_validate_json((pdir / "match_report.json").read_text(encoding="utf-8"))
            req = {p.n: p.required for p in PromptsMap.model_validate_json((pdir / "prompts_map.json").read_text(encoding="utf-8")).prompts}
            if any((not m.file or m.status == "missing") and req.get(m.n, True) for m in rep.matches):
                return "images", None
    return None, None


def build_status(pid: str) -> Status:
    pdir = store.project_dir(pid)
    job, running = jobs.current(pid), jobs.is_running(pid)
    disk = {}
    try:                                     # pipeline.set_job rewrites this file in place: a read can catch it empty
        disk = json.loads((pdir / "job.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    error = (job.error if job else None) or (None if job else disk.get("error"))
    wait, command = (None, None) if running else waiting_for(pdir)
    if not running and job and job.state == "waiting":            # the run stopped for a person's decision (Final QC sign-off): a wait, not an error
        wait = "review"
    hint = None
    if error and error.startswith("review needed"):
        hint = "confirm images with POST /projects/{id}/match/fix, or submit again with force=true"
    return Status(step=(job.step if job and job.step else disk.get("step")), percent=disk.get("percent", 0) or 0,
                  message=(job.message if job else ""), error=error, hint=hint, waiting_for=wait, command=command,
                  running=running, state=store.read_info(pdir).get("state", ""))
