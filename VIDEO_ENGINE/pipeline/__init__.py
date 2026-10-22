"""VIDEO_ENGINE Pipeline Package.

Exposes the single canonical video execution engine: PipelineOrchestrator,
along with job and execution adapters.
"""
from __future__ import annotations

from .orchestrator import (
    ACTIVE_STAGES,
    STAGE_DEPENDENCIES,
    STAGE_TO_AGENT,
    PipelineOrchestrator,
    RunRecord,
    check_system_capabilities,
    classify_error,
    compute_idempotency_key,
    current_run,
    evaluate_stage_eligibility,
    find_browser_executable,
    get_monitoring_status,
    is_running,
    list_project_runs,
    load_run_record,
    sanitize_message,
    save_run_record,
)
from .jobs_adapter import (
    Job,
    cancel as cancel_job,
    current as current_job,
    is_running as is_job_running,
    start as start_job,
)
