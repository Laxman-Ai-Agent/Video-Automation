"""Canonical Job Execution Adapter over PipelineOrchestrator.

Provides a 100% backward-compatible Job API for existing routes, pipeline views,
and test harnesses while ensuring all pipeline execution is driven by the single
canonical engine: VIDEO_ENGINE.pipeline.orchestrator.PipelineOrchestrator.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from SYSTEM.memory import store
from SYSTEM.core.errors import ApiError, clean
from VIDEO_ENGINE.pipeline import procs

try:
    from SYSTEM.core import config
except ImportError:
    try:
        from backend import config
    except ImportError:
        import config

try:
    from VIDEO_ENGINE.pipeline import orchestrator
except ImportError:
    from backend import orchestrator

logger = logging.getLogger("jobs")

RENDER_LOCK = threading.Lock()
_jobs: dict[str, "Job"] = {}
_lock = threading.RLock()


@dataclass
class Job:
    project: str
    label: str
    names: tuple = ()
    ctx: Any = None
    state: str = "running"  # running | done | failed | cancelled
    step: str | None = None
    message: str = ""
    error: str | None = None
    cancel: threading.Event = field(default_factory=threading.Event)
    future: object = None
    run_id: str | None = None


def _map_label_to_stages(label: str, names: Any = ()) -> tuple[str | None, str | None]:
    """Maps legacy chain/step labels to canonical orchestrator (from_stage, to_stage)."""
    l = label.lower()
    names_str = " ".join(str(n).lower() for n in names) if names else ""
    # Timeline Build -> Timeline Approval (decided by the LLM approval review) -> Render Video -> Final QC, with no human pause before render; checked before
    # "render-final" (which these chains end with) so the approval stage is never skipped
    if "approval" in l:
        return "approval", "qc"
    if "timeline" in l:                                                 # a chain that starts with Motion Planning (Motion-Only "build the timeline from the plan") runs the motion stages first
        return ("motion_plan" if names and str(names[0]).lower().startswith("motion-plan") else "timeline"), "qc"
    if "render" in l or l in ("build", "build-9x16") or "render-final" in names_str:
        return "render", "final"
    if "motion-val" in l:
        return "motion_validation", "motion_validation"
    if "motion-gen" in l or "motion-build" in l:
        return "motion_gen", "motion_gen"
    if "motion-plan" in l:
        return "motion_plan", "motion_plan"
    if "motion" in l:
        return "motion_plan", "motion_validation"
    if "qc" in l:
        return "qc", "final"
    if "segment" in l:
        return "segmentation", "segmentation"
    if "transcribe" in l:
        return "audio", "analyzer"
    return None, None


def _finish_from_record(pid: str, j: Job) -> None:
    """The run has ended: the job takes the run's real outcome and error from its saved record (a failed or blocked run never reads as done)."""
    run = orchestrator.load_run_record(store.project_dir(pid), j.run_id) if j.run_id else None
    if run is None:
        j.state = "done"
        return
    _apply_outcome(j, run)


def _apply_outcome(j: Job, run) -> None:
    """The job's state from the run: a run that stopped for a person's decision (a stage answered needs_review, e.g. the Final QC playback sign-off) is WAITING, not
    failed: its reason is the message, not an error. Every other stop keeps the run's real error."""
    if run.status == "blocked" and (run.error or {}).get("code") == "stage_needs_review":
        j.state, j.error, j.message = "waiting", None, run.error.get("message") or j.message
        return
    j.state = {"running": "running", "completed": "done", "cancelled": "cancelled"}.get(run.status, "failed")
    if run.error:
        j.error = run.error.get("message") or j.error


def is_running(pid: str) -> bool:
    """Checks whether any execution is currently active for this project."""
    if orchestrator.is_running(pid):
        return True
    with _lock:
        j = _jobs.get(pid)
        if j and j.state == "running" and not orchestrator.is_running(pid):
            _finish_from_record(pid, j)
            return False
        return bool(j and j.state == "running")


def current(pid: str) -> Job | None:
    """Retrieves current job representation, synced with canonical PipelineOrchestrator."""
    run = orchestrator.current_run(pid)
    if run:
        with _lock:
            j = _jobs.get(pid)
            names_tuple = tuple(run.stages_completed + ([run.current_stage] if run.current_stage else []))
            if not j or j.run_id != run.run_id:
                j = Job(
                    project=pid,
                    label=run.current_stage or "pipeline",
                    names=names_tuple or ("pipeline",),
                    ctx=None,
                    state="running",
                    step=run.current_stage,
                    message=f"Executing stage {run.current_stage}" if run.current_stage else "Running",
                    run_id=run.run_id,
                )
                _jobs[pid] = j
            j.step = run.current_stage                                  # a new Job too: a run that already ended must not read as running without its error
            j.names = names_tuple or j.names
            j.message = f"Executing stage {run.current_stage}" if run.current_stage else ""
            _apply_outcome(j, run)
            return j

    with _lock:
        return _jobs.get(pid)


def start(pid: str, label: str, names: Any = (), ctx: Any = None) -> Job:
    """Starts execution via the canonical PipelineOrchestrator."""
    with _lock:
        if is_running(pid):
            raise ApiError(
                409,
                "job_running",
                "a job is already running for this project",
                "wait for it to finish, or POST /projects/{id}/cancel",
            )

        pdir = store.project_dir(pid)
        try:
            try:
                from UI.backend import pipeline_view
            except ImportError:
                from backend import pipeline_view
            aspect = pipeline_view.aspect_of(pdir) if hasattr(pipeline_view, "aspect_of") else "16:9"
        except Exception:
            aspect = "16:9"

        from_stage, to_stage = _map_label_to_stages(label, names)
        force = bool(getattr(ctx, "force", False))

        orch = orchestrator.PipelineOrchestrator(pid, aspect)
        run = orch.start_run(from_stage=from_stage, to_stage=to_stage, resume=not force)

        job = Job(
            project=pid,
            label=label,
            names=tuple(names) if names else ((from_stage,) if from_stage else ("pipeline",)),
            ctx=ctx,
            state="running",
            step=from_stage,
            message=f"Started {label}",
            run_id=run.run_id,
        )
        _jobs[pid] = job
        return job


def cancel(pid: str) -> None:
    """Cooperatively cancels active orchestrator execution and terminates any child process."""
    if not is_running(pid):
        raise ApiError(409, "no_job", "no job is running for this project")

    with _lock:
        j = _jobs.get(pid)
        if j:
            j.cancel.set()
            j.state = "cancelled"

    try:
        orch = orchestrator.PipelineOrchestrator(pid)
        orch.cancel_run()
    except Exception as e:
        logger.debug(f"Orchestrator cancel notice for {pid}: {e}")

    procs.kill(pid)


def _cancelled(job: Job, pdir: Path) -> None:
    """Compatibility helper for step cancellation recording."""
    job.state, job.message = "cancelled", f"cancelled while running {job.step}"
    try:
        try:
            from VIDEO_ENGINE.pipeline import legacy_pipeline_adapter as pipeline
        except ImportError:
            from backend import pipeline
        pipeline.set_job(pdir, job.step or "", error="cancelled by you")
    except Exception:
        pass
