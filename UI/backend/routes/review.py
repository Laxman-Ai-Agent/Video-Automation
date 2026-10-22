"""Review workflow endpoints: scene table and state, crops, approval gates, running the timeline or a render for one aspect, the video and the pictures."""
from fastapi import APIRouter
from fastapi.responses import FileResponse

from .. import jobs, promptgen, review, store, timeline_gate, video_qc
from ..api_models import (ApproveRequest, CropRequest, CropResult, Gate, JobStarted, QcReport, ReviewState, RunRequest)
from ..errors import ApiError
from ..pipeline import Ctx, chain_for
from .uploads import safe_name

router = APIRouter(prefix="/projects/{pid}", tags=["review"])


def _pdir(pid: str):
    return store.project_dir(pid)


def _need_plan(pdir) -> None:
    if not (pdir / "scene_plan.json").exists() or not (pdir / "prompts_map.json").exists():
        raise ApiError(409, "plan_missing", "the plan does not exist yet", "run /plan in Claude Code")


def _busy(pid: str) -> None:
    if jobs.is_running(pid):
        raise ApiError(409, "job_running", "a job is running for this project", "change things after it finishes")


def _refused(e: review.ReviewError) -> ApiError:
    return ApiError(409, "not_allowed", str(e), "; ".join(e.blockers))


@router.get("/review", response_model=ReviewState)
def get_review(pid: str):
    pdir = _pdir(pid)
    return {**review.review(pdir, pid), "generation": promptgen.state(pdir)}


@router.put("/crops/{n}", response_model=CropResult)
def set_crop(pid: str, n: int, body: CropRequest):
    pdir = _pdir(pid)
    _need_plan(pdir)
    _busy(pid)
    try:
        if body.reset:
            review.reset_crop(pdir, n, body.aspect)
            return CropResult(n=n, aspect=body.aspect, crop=None)
        if body.x is None or body.y is None:
            raise review.ReviewError("send the crop centre (x, y) or reset=true")
        saved = review.save_crop(pdir, n, body.aspect, body.x, body.y, body.zoom)
    except review.ReviewError as e:
        raise ApiError(422, "invalid_crop", str(e)) from e
    return CropResult(n=n, aspect=body.aspect, crop={**saved, "stale": False})


@router.post("/approve", response_model=Gate)
def approve(pid: str, body: ApproveRequest):
    pdir = _pdir(pid)
    _busy(pid)
    try:
        gate = review.set_gate(pdir, body.gate, body.approved)
    except review.ReviewError as e:
        raise _refused(e) from e
    if body.gate == "analysis" and body.approved:      # approving the analysis is what starts the prompt writer; it never runs before
        try:
            promptgen.start(pdir)
        except review.ReviewError:
            pass                                       # already running: the approval stands, the state shows the running job
    return gate


@router.post("/run", response_model=JobStarted, status_code=202)
def run(pid: str, body: RunRequest):
    """timeline = the motion chain up to the built timeline (no render); preview / final = the build chain for the chosen aspect."""
    pdir = _pdir(pid)
    _need_plan(pdir)
    sfx = "-9x16" if body.aspect == "9:16" else ""
    if body.stage == "timeline":
        g = review.gates(pdir)
        waiting = [name for name in ("analysis",) if not g[name]["approved"]]      # Motion-Only mode has no prompt or image gate
        if waiting:
            raise ApiError(409, "approval_missing", f"approve first: {', '.join(waiting)}",
                           "; ".join(b for name in waiting for b in g[name]["blockers"]) or "approve the stages in order")
        label = f"timeline{sfx}"
        job = jobs.start(pid, label, chain_for(pdir, label), Ctx())
    else:
        if not review.timeline_state(pdir)[body.aspect]["ready"]:
            raise ApiError(409, "timeline_not_ready", "the timeline has not been verified for this format yet", "run Continue to Timeline first")
        if body.stage == "final":                   # a final render needs the approved version of the timeline (the preview is what the user checks before approving)
            timeline_gate.require_approved(pdir, body.aspect)
        label = ("build-preview" if body.stage == "preview" else "build") + sfx
        job = jobs.start(pid, label, chain_for(pdir, label), Ctx(preview=body.stage == "preview"))
    return JobStarted(project=pid, label=job.label, steps=list(job.names))


@router.get("/video")
def video(pid: str, aspect: str = "9:16", preview: bool = True):
    pdir = _pdir(pid)
    if aspect not in review.ASPECTS:
        raise ApiError(422, "invalid_request", "aspect must be 16:9 or 9:16")
    f = pdir / f"{'out_preview' if preview else 'out'}{'_9x16' if aspect == '9:16' else ''}.mp4"
    if not f.exists():
        raise ApiError(404, "result_missing", "the video has not been rendered yet", "run Preview or Render")
    return FileResponse(f, media_type="video/mp4")


@router.get("/assets/{name}")
def asset(pid: str, name: str):
    pdir = _pdir(pid)
    path = review.asset_path(pdir, safe_name(name))
    if path is None:
        raise ApiError(404, "file_not_found", f"{safe_name(name)} is not among this project's images")
    return FileResponse(path)


@router.get("/qc", response_model=QcReport)
def qc(pid: str, aspect: str = "9:16", preview: bool = True):
    """Quality checks measured on the rendered video of this aspect (a missing video is one failed check, not an error)."""
    pdir = _pdir(pid)
    if aspect not in review.ASPECTS:
        raise ApiError(422, "invalid_request", "aspect must be 16:9 or 9:16")
    return video_qc.check(pdir, aspect, preview)
