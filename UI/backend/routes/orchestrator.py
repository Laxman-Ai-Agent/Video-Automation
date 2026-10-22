"""FastAPI routes for Pipeline Orchestrator and Operational Monitoring."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .. import orchestrator, pipeline_state, store
from ..errors import ApiError

router = APIRouter(prefix="/projects/{pid}/orchestrator", tags=["orchestrator"])


class RunRequestBody(BaseModel):
    from_stage: str | None = None
    resume: bool = True
    aspect: str = "16:9"
    max_retries: int = Field(default=3, ge=0, le=10)
    idempotency_key: str | None = None
    synchronous: bool = False
    auto_pilot: bool = True


class CancelRequestBody(BaseModel):
    run_id: str | None = None


@router.post("/run", status_code=202)
def start_orchestrator_run(pid: str, body: RunRequestBody | None = None) -> dict[str, Any]:
    """Starts or resumes a pipeline run coordinated by the canonical Orchestrator."""
    body = body or RunRequestBody()
    if body.aspect not in ("16:9", "9:16"):
        raise HTTPException(status_code=422, detail="Aspect ratio must be '16:9' or '9:16'")

    try:
        orch = orchestrator.PipelineOrchestrator(pid, body.aspect, auto_pilot_mode=body.auto_pilot)
        run = orch.start_run(
            from_stage=body.from_stage,
            resume=body.resume,
            idempotency_key=body.idempotency_key,
            max_retries=body.max_retries,
            synchronous=body.synchronous,
            auto_pilot_mode=body.auto_pilot,
        )
        return run.to_dict()
    except ApiError as e:
        raise HTTPException(status_code=e.status, detail={"code": e.code, "message": e.message, "hint": e.hint})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cancel")
def cancel_orchestrator_run(pid: str, body: CancelRequestBody | None = None) -> dict[str, Any]:
    """Cooperatively cancels an active orchestrator run for the project."""
    run_id = body.run_id if body else None
    try:
        orch = orchestrator.PipelineOrchestrator(pid)
        run = orch.cancel_run(run_id=run_id)
        return run.to_dict()
    except ApiError as e:
        raise HTTPException(status_code=e.status, detail={"code": e.code, "message": e.message, "hint": e.hint})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
def get_monitoring_status(pid: str, aspect: str = Query(default="16:9")) -> dict[str, Any]:
    """Retrieves authoritative monitoring, stage states, blockers, approval requirements, and capabilities."""
    if aspect not in ("16:9", "9:16"):
        raise HTTPException(status_code=422, detail="Aspect ratio must be '16:9' or '9:16'")
    try:
        return orchestrator.get_monitoring_status(pid, aspect)
    except ApiError as e:
        raise HTTPException(status_code=e.status, detail={"code": e.code, "message": e.message, "hint": e.hint})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runs")
def list_runs(pid: str, limit: int = Query(default=50, ge=1, le=200)) -> dict[str, Any]:
    """Lists persistent historical orchestrator runs for the project."""
    runs = orchestrator.list_project_runs(pid, limit=limit)
    return {"project_id": pid, "count": len(runs), "runs": runs}


@router.get("/runs/{run_id}")
def get_run(pid: str, run_id: str) -> dict[str, Any]:
    """Fetches details of a specific orchestrator run record."""
    try:
        pdir = store.project_dir(pid)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Project '{pid}' not found")
    run = orchestrator.load_run_record(pdir, run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found for project '{pid}'")
    return run.to_dict()


@router.get("/gates")
def get_gates_status(pid: str, aspect: str = Query(default="16:9")) -> dict[str, Any]:
    """The approval gates (Timeline Approval and Final QC, both decided by an LLM review) for the project."""
    status_data = orchestrator.get_monitoring_status(pid, aspect)
    return {
        "project_id": pid,
        "aspect": aspect,
        "approval_gates": status_data["approval_gates"],
        "overall_status": status_data["overall_status"],
    }


@router.get("/capabilities")
def get_capabilities() -> dict[str, Any]:
    """Reports system tools, remotion installation, and headless Chromium prerequisite status."""
    return orchestrator.check_system_capabilities()


@router.post("/reconcile")
def reconcile_orphans(pid: str) -> dict[str, Any]:
    """Detects and reconciles orphaned stage states after server restart or interruption."""
    try:
        pdir = store.project_dir(pid)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Project '{pid}' not found")
    reconciled = pipeline_state.reconcile_orphaned_jobs(pdir)
    return {"project_id": pid, "reconciled_stages": reconciled, "count": len(reconciled)}
