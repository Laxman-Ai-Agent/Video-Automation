"""FastAPI app. Thin on purpose: routers in UI/backend/routes/, logic in VIDEO_ENGINE & SYSTEM.
Run (local only): uvicorn UI.backend.main:app --reload --host 127.0.0.1 --port 8000"""
from __future__ import annotations

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import SYSTEM.core.errors as errors
from .routes import (
    agents,
    approvals,
    assets,
    evaluation,
    llm,
    memory,
    orchestrator,
    pipeline,
    projects,
    resources,
    results,
    review,
    run,
    skills,
    uploads,
    visual,
    work_log,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Leftover Chrome profiles of earlier killed renders (older than an hour, no process using them) are removed in the background."""
    try:
        from VIDEO_ENGINE.pipeline import browser_profiles
        threading.Thread(target=browser_profiles.sweep, daemon=True).start()
    except Exception:
        pass
    try:
        from .routes.llm import trigger_llm_health_probe
        threading.Thread(target=trigger_llm_health_probe, daemon=True).start()
    except Exception:
        pass
    yield


app = FastAPI(title="Audio-to-Video", version="0.7", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_methods=["*"],
    allow_headers=["*"],
)
errors.install(app)
for module in (
    projects,
    uploads,
    run,
    results,
    review,
    assets,
    visual,
    pipeline,
    resources,
    llm,
    agents,
    skills,
    memory,
    orchestrator,
    evaluation,
    approvals,
    work_log,
):
    app.include_router(module.router)


@app.get("/health")
async def health():
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "UI.backend.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_dirs=["UI/backend"],
    )
