"""Long-running actions: transcribe, cancel. All run as background jobs."""
from fastapi import APIRouter

from .. import jobs, store
from ..api_models import JobStarted
from ..errors import ApiError
from ..pipeline import CHAINS, Ctx

router = APIRouter(prefix="/projects/{pid}", tags=["jobs"])


@router.post("/transcribe", response_model=JobStarted, status_code=202)
def transcribe(pid: str):
    pdir = store.project_dir(pid)
    if not any(pdir.glob("audio.*")):
        raise ApiError(409, "audio_missing", "this project has no audio file", "create the project with an audio upload")
    job = jobs.start(pid, "transcribe", CHAINS["transcribe"], Ctx())
    return JobStarted(project=pid, label=job.label, steps=list(job.names))


@router.post("/cancel")
def cancel(pid: str):
    store.project_dir(pid)
    jobs.cancel(pid)
    try:
        from .. import orchestrator
        orch = orchestrator.PipelineOrchestrator(pid)
        orch.cancel_run()
    except Exception:
        pass
    return {"cancelling": True}
