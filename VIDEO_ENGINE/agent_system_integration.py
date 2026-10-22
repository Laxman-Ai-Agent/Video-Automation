"""The video project's side of the Agent System's optional-integration interface (SYSTEM/core/integrations.py).

The Agent System never imports VIDEO_ENGINE; this module tells it what the video project can provide.
Registered when VIDEO_ENGINE is imported. Every provider is built on first use, so importing VIDEO_ENGINE stays cheap
(the orchestrator pulls in the whole pipeline).
"""
from __future__ import annotations

from SYSTEM.core import integrations


def _stage_dependencies():
    from VIDEO_ENGINE.pipeline.orchestrator import STAGE_DEPENDENCIES
    return STAGE_DEPENDENCIES


def _pipeline_orchestrator():
    from VIDEO_ENGINE.pipeline.orchestrator import PipelineOrchestrator
    return PipelineOrchestrator


def _system_capabilities():
    from VIDEO_ENGINE.pipeline import orchestrator
    return orchestrator.check_system_capabilities


def _jobs():
    from VIDEO_ENGINE.pipeline import jobs_adapter
    return jobs_adapter


def _agent_entries():
    from SYSTEM.agents.video_generation_agents.registry_entries import video_agent_entries
    return video_agent_entries()


def register() -> None:
    integrations.register("agent_entries", factory=_agent_entries)
    integrations.register("stage_dependencies", factory=_stage_dependencies)
    integrations.register("pipeline_orchestrator", factory=_pipeline_orchestrator)
    integrations.register("system_capabilities", factory=_system_capabilities)
    integrations.register("jobs", factory=_jobs)
