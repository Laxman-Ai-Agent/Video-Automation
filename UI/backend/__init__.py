"""UI backend package.

Routes, schemas, and API presentation layer for Audio-to-Video.
Delegates canonically to SYSTEM shared services and VIDEO_ENGINE execution components.
"""
from __future__ import annotations

import importlib
import sys

_DELEGATIONS: dict[str, str] = {
    # Local UI backend schemas and views
    "models": "UI.backend.models",
    "api_models": "UI.backend.api_models",
    "api_status": "UI.backend.api_status",
    "pipeline_view": "UI.backend.pipeline_view",
    "errors": "SYSTEM.core.errors",

    # Canonical SYSTEM services
    "pipeline_state": "SYSTEM.core.pipeline_state",
    "artifact_contracts": "SYSTEM.core.artifact_contracts",
    "store": "SYSTEM.memory.store",
    "llm_review": "SYSTEM.policies.llm_review",
    "llm_client": "SYSTEM.core.llm_client",

    # Canonical VIDEO_ENGINE pipeline
    "orchestrator": "VIDEO_ENGINE.pipeline.orchestrator",
    "jobs": "VIDEO_ENGINE.pipeline.jobs_adapter",
    "pipeline": "VIDEO_ENGINE.pipeline.legacy_pipeline_adapter",
    "browser_profiles": "VIDEO_ENGINE.pipeline.browser_profiles",

    # Canonical VIDEO_ENGINE stages
    "audio_analysis": "VIDEO_ENGINE.stages.audio_analysis",
    "analysis_autofix": "VIDEO_ENGINE.stages.analysis_autofix",
    "audio_utils": "VIDEO_ENGINE.stages.audio_utils",
    "assets": "VIDEO_ENGINE.stages.assets",
    "autoplan": "VIDEO_ENGINE.stages.autoplan",
    "cuts": "VIDEO_ENGINE.stages.cuts",
    "final_qc": "VIDEO_ENGINE.stages.final_qc",
    "matcher": "VIDEO_ENGINE.stages.matcher",
    "motion_autofix": "VIDEO_ENGINE.stages.motion_autofix",
    "motion_branch": "VIDEO_ENGINE.stages.motion_branch",
    "motion_gen_report": "VIDEO_ENGINE.stages.motion_gen_report",
    "motion_generation": "VIDEO_ENGINE.stages.motion_generation",
    "motion_planning": "VIDEO_ENGINE.stages.motion_planning",
    "motion_template_selection": "VIDEO_ENGINE.stages.motion_template_selection",
    "motion_validation": "VIDEO_ENGINE.stages.motion_validation",
    "motion_validation_preview": "VIDEO_ENGINE.stages.motion_validation_preview",
    "promptgen": "VIDEO_ENGINE.stages.promptgen",
    "render_video": "VIDEO_ENGINE.stages.render_video",
    "resource_audit": "VIDEO_ENGINE.stages.resource_audit",
    "resource_jobs": "VIDEO_ENGINE.stages.resource_jobs",
    "resource_library": "VIDEO_ENGINE.stages.resource_library",
    "resource_local": "VIDEO_ENGINE.stages.resource_local",
    "resource_verify": "VIDEO_ENGINE.stages.resource_verify",
    "review": "VIDEO_ENGINE.stages.review",
    "scene_segmentation": "VIDEO_ENGINE.stages.scene_segmentation",
    "timeline_approval": "VIDEO_ENGINE.stages.timeline_approval",
    "timeline_build": "VIDEO_ENGINE.stages.timeline_build",
    "timeline_gate": "VIDEO_ENGINE.stages.timeline_gate",
    "timeline_media": "VIDEO_ENGINE.stages.timeline_media",
    "transcribe": "VIDEO_ENGINE.stages.transcribe",
    "transcript_review": "VIDEO_ENGINE.stages.transcript_review",
    "video_qc": "VIDEO_ENGINE.stages.video_qc",
    "visual_plan": "VIDEO_ENGINE.stages.visual_plan",
    "visual_planning": "VIDEO_ENGINE.stages.visual_planning",
}


def __getattr__(name: str):
    if name in _DELEGATIONS:
        mod = importlib.import_module(_DELEGATIONS[name])
        sys.modules[f"{__name__}.{name}"] = mod
        return mod
    if name == "agents":
        import types
        import SYSTEM.agents.shared.communication as communication
        _agents_pkg = types.ModuleType(f"{__name__}.agents")
        _agents_pkg.communication = communication
        sys.modules[f"{__name__}.agents"] = _agents_pkg
        sys.modules[f"{__name__}.agents.communication"] = communication
        return _agents_pkg
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
