"""Canonical Pipeline Stage-State, Checkpoint, and Resume Manager.

Manages:
1. Canonical stage lifecycle (pending, running, completed, blocked, failed, needs_review, cancelled, skipped).
2. Validated state transitions with fail-closed completion rules.
3. Checkpoint identity and fingerprint provenance.
4. Deterministic resume graph calculation (earliest invalid stage, reusable checkpoints, downstream invalidation).
5. Safe process restart recovery, concurrency serialization, and audit logging.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from SYSTEM.core import artifact_contracts
from SYSTEM.policies import llm_review
from SYSTEM.memory import store
from SYSTEM.core.errors import ApiError
from SYSTEM.agents.shared import communication

StageStatus = Literal[
    "pending",
    "running",
    "completed",
    "blocked",
    "failed",
    "needs_review",
    "cancelled",
    "skipped",
]

ACTIVE_STAGES: tuple[str, ...] = (
    "audio",
    "analyzer",
    "segmentation",
    "planning",
    "assets",
    "motion_plan",
    "motion_gen",
    "motion_validation",
    "timeline",
    "approval",
    "render",
    "qc",
    "final",
)

STAGE_TO_AGENT_MAP: dict[str, str] = {
    "audio": "audio_input",
    "analyzer": "audio_analyzer",
    "segmentation": "scene_segmentation",
    "planning": "visual_planning",
    "assets": "asset_collection",
    "motion_plan": "motion_planning",
    "motion_gen": "motion_animation",
    "motion_validation": "motion_timeline_validation",
    "timeline": "timeline_build",
    "approval": "timeline_approval",
    "render": "render_video",
    "qc": "final_qc",
    "final": "final_video_delivery",
}

# Legal lifecycle state transitions
LEGAL_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"running", "skipped", "pending"},
    "running": {"completed", "blocked", "failed", "needs_review", "cancelled", "running"},
    "blocked": {"running", "pending", "blocked"},
    "failed": {"running", "pending", "failed"},
    "needs_review": {"completed", "blocked", "running", "needs_review", "pending"},
    "cancelled": {"pending", "running", "cancelled"},
    "skipped": {"pending", "running", "skipped"},
    "completed": {"running", "pending", "completed"},  # recompute / invalidation triggers running/pending
}


class InvalidStateTransitionError(Exception):
    """Raised when an illegal lifecycle transition is attempted."""


@dataclass
class StageStateRecord:
    stage_id: str
    status: StageStatus = "pending"
    attempt: int = 0
    input_fingerprint: str = ""
    output_fingerprint: str = ""
    contract_version: int = 1
    checkpoint_id: str = ""
    started_at: float | None = None
    completed_at: float | None = None
    last_error: dict[str, Any] | None = None
    review_ref: str | None = None
    reusable: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PipelineState:
    schema: str = "pipeline-state"
    schema_version: int = 1
    project_id: str = ""
    revision: int = 0
    updated_at: str = ""
    pipeline_mode: str = "motion_only"
    stages: dict[str, StageStateRecord] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "revision": self.revision,
            "updated_at": self.updated_at,
            "pipeline_mode": self.pipeline_mode,
            "stages": {sid: s.to_dict() for sid, s in self.stages.items()},
        }


def _state_file(pdir: Path) -> Path:
    return pdir / "pipeline_state.json"


def compute_checkpoint_id(
    project_id: str,
    stage_id: str,
    in_fp: str,
    out_fp: str,
    contract_version: int,
    review_fp: str = "",
) -> str:
    """Computes a deterministic checkpoint hash from validated provenance."""
    raw = f"{project_id}:{stage_id}:{in_fp}:{out_fp}:v{contract_version}:{review_fp}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def init_default_state(pdir: Path) -> PipelineState:
    """Creates a blank default pipeline state for a project."""
    ts = datetime.now(timezone.utc).isoformat()
    state = PipelineState(
        project_id=pdir.name,
        revision=1,
        updated_at=ts,
        pipeline_mode="motion_only",
        stages={sid: StageStateRecord(stage_id=sid, status="pending") for sid in ACTIVE_STAGES},
    )
    return state


def load_pipeline_state(pdir: Path) -> PipelineState:
    """Loads authoritative pipeline state from disk with concurrency locking and atomic defaults."""
    f = _state_file(pdir)
    with store._info_lock(pdir):
        if not f.exists():
            state = init_default_state(pdir)
            save_pipeline_state(pdir, state)
            return state

        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("schema") != "pipeline-state":
                state = init_default_state(pdir)
                save_pipeline_state(pdir, state)
                return state

            stages = {}
            for sid in ACTIVE_STAGES:
                s_raw = data.get("stages", {}).get(sid, {})
                stages[sid] = StageStateRecord(
                    stage_id=sid,
                    status=s_raw.get("status", "pending"),
                    attempt=s_raw.get("attempt", 0),
                    input_fingerprint=s_raw.get("input_fingerprint", ""),
                    output_fingerprint=s_raw.get("output_fingerprint", ""),
                    contract_version=s_raw.get("contract_version", 1),
                    checkpoint_id=s_raw.get("checkpoint_id", ""),
                    started_at=s_raw.get("started_at"),
                    completed_at=s_raw.get("completed_at"),
                    last_error=s_raw.get("last_error"),
                    review_ref=s_raw.get("review_ref"),
                    reusable=s_raw.get("reusable", False),
                    metadata=s_raw.get("metadata", {}),
                )
            # A stage added to the pipeline after this project ran (no record in its stored state) while a LATER stage already completed was never part of this run: it is skipped, not pending,
            # so it neither blocks its dependants nor asks to be run for a video that is already built without it.
            stored = data.get("stages", {})
            for i, sid in enumerate(ACTIVE_STAGES):
                if sid not in stored and any(stored.get(later, {}).get("status") == "completed" for later in ACTIVE_STAGES[i + 1:]):
                    stages[sid].status = "skipped"
                    stages[sid].metadata = {"skipped_reason": "the stage was added after this project ran"}

            return PipelineState(
                schema=data.get("schema", "pipeline-state"),
                schema_version=data.get("schema_version", 1),
                project_id=data.get("project_id", pdir.name),
                revision=data.get("revision", 1),
                updated_at=data.get("updated_at", ""),
                pipeline_mode=data.get("pipeline_mode", "motion_only"),
                stages=stages,
            )
        except Exception:
            state = init_default_state(pdir)
            save_pipeline_state(pdir, state)
            return state


def save_pipeline_state(pdir: Path, state: PipelineState) -> None:
    """Atomically persists pipeline state using a temporary file and per-project lock."""
    f = _state_file(pdir)
    tmp = f.with_suffix(".tmp")
    state.updated_at = datetime.now(timezone.utc).isoformat()
    with store._info_lock(pdir):
        tmp.write_text(json.dumps(state.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, f)


def update_pipeline_state(pdir: Path, updater: Callable[[PipelineState], None]) -> PipelineState:
    """Thread-safe atomic read-modify-write helper holding per-project lock across entire operation."""
    with store._info_lock(pdir):
        state = load_pipeline_state(pdir)
        updater(state)
        state.revision += 1
        save_pipeline_state(pdir, state)
        return state


def reconcile_orphaned_jobs(pdir: Path) -> list[str]:
    """Detects stages marked 'running' whose background execution died or was interrupted."""
    from SYSTEM.core import integrations
    jobs = integrations.get("jobs")
    if jobs is None:                       # no domain project runs background jobs here, so none can have been orphaned
        return []
    reconciled = []
    is_job_active = jobs.is_running(pdir.name)
    current_job = jobs.current(pdir.name)

    state = load_pipeline_state(pdir)
    changed = False

    for sid, srec in state.stages.items():
        if srec.status == "running":
            if not is_job_active or (current_job and current_job.step != sid):
                srec.status = "failed"
                srec.last_error = {
                    "code": "interrupted_by_process_restart",
                    "message": f"Stage {sid} execution was interrupted by process restart or server reload.",
                }
                reconciled.append(sid)
                changed = True

    if changed:
        state.revision += 1
        save_pipeline_state(pdir, state)

    return reconciled


def transition_stage(
    pdir: Path,
    stage_id: str,
    target_status: StageStatus,
    aspect: str = "16:9",
    error_code: str | None = None,
    error_message: str | None = None,
    details: dict[str, Any] | None = None,
) -> StageStateRecord:
    """Validates and applies a stage lifecycle transition with fail-closed completion gates."""
    if stage_id not in ACTIVE_STAGES:
        raise InvalidStateTransitionError(f"Unknown pipeline stage '{stage_id}'")

    with store._info_lock(pdir):
        state = load_pipeline_state(pdir)
        srec = state.stages.get(stage_id)
        if not srec:
            srec = StageStateRecord(stage_id=stage_id, status="pending")
            state.stages[stage_id] = srec

        current = srec.status

        # Validate legal transition
        allowed = LEGAL_TRANSITIONS.get(current, set())
        if target_status not in allowed:
            raise InvalidStateTransitionError(
                f"Illegal transition for stage '{stage_id}': cannot move from '{current}' to '{target_status}'"
            )

        # Handle Running
        if target_status == "running":
            srec.attempt += 1
            srec.started_at = time.time()
            srec.status = "running"
            srec.last_error = None
            srec.reusable = False

        # Handle Blocked or Failed
        elif target_status in ("blocked", "failed"):
            srec.status = target_status
            srec.completed_at = time.time()
            srec.reusable = False
            srec.last_error = {
                "code": error_code or target_status,
                "message": error_message or f"Stage {stage_id} entered {target_status} status",
                "details": details or {},
            }

        # Handle Cancelled
        elif target_status == "cancelled":
            srec.status = "cancelled"
            srec.completed_at = time.time()
            srec.reusable = False
            srec.last_error = {
                "code": "user_cancelled",
                "message": error_message or f"Stage {stage_id} was cancelled by user",
            }

        # Handle Needs Review / Awaiting Approval
        elif target_status == "needs_review":
            srec.status = "needs_review"
            srec.reusable = False

        # Handle Completed (STRICT FAIL-CLOSED COMPLETION GATE)
        elif target_status == "completed":
            # 1. Validate artifact schema and integrity
            try:
                manifest_records = artifact_contracts.validate_stage_artifacts(pdir, stage_id, aspect)
            except artifact_contracts.ContractError as e:
                srec.status = "blocked"
                srec.last_error = {
                    "code": "contract_validation_failed",
                    "message": str(e),
                }
                state.revision += 1
                save_pipeline_state(pdir, state)
                raise InvalidStateTransitionError(f"Cannot complete stage '{stage_id}': contract check failed: {e}")

            # 2. Compute fingerprints
            in_fp = llm_review.compute_stage_input_fingerprint(pdir, stage_id, aspect)
            out_fp = llm_review.compute_stage_output_fingerprint(pdir, stage_id, aspect)

            # 3. Verify Phase 2 mandatory LLM review gate
            passed, reason, rev = llm_review.is_stage_review_passed(pdir, stage_id, aspect, auto_pilot=True)
            if not passed:
                srec.status = "blocked"
                srec.last_error = {
                    "code": f"llm_review_gate_{reason}",
                    "message": f"Mandatory LLM review gate not satisfied: {reason}",
                }
                state.revision += 1
                save_pipeline_state(pdir, state)
                raise InvalidStateTransitionError(
                    f"Cannot complete stage '{stage_id}': Phase 2 review gate failed ({reason})"
                )

            # 4. Success: persist checkpoint provenance
            srec.status = "completed"
            srec.completed_at = time.time()
            srec.input_fingerprint = in_fp
            srec.output_fingerprint = out_fp
            srec.contract_version = artifact_contracts.CURRENT_CONTRACT_VERSION
            srec.review_ref = llm_review.review_path(pdir, stage_id, aspect).name
            srec.checkpoint_id = compute_checkpoint_id(
                project_id=pdir.name,
                stage_id=stage_id,
                in_fp=in_fp,
                out_fp=out_fp,
                contract_version=srec.contract_version,
                review_fp=rev.get("output_fingerprint", "") if rev else "",
            )
            srec.reusable = True
            srec.last_error = None
            srec.metadata["artifacts"] = [m.to_dict() for m in manifest_records]

        else:
            srec.status = target_status

        # Increment monotonic state revision
        state.revision += 1
        save_pipeline_state(pdir, state)

        # Publish state transition audit event
        try:
            agent_id = STAGE_TO_AGENT_MAP.get(stage_id, "main_orchestrator")
            communication.publish_lifecycle_event(
                project_id=pdir.name,
                stage_id=stage_id,
                sender_agent_id=agent_id,
                event=f"state_transition_{target_status}",
                detail=f"Stage '{stage_id}' transitioned to '{target_status}' (attempt {srec.attempt}, rev {state.revision})",
                metadata={"checkpoint_id": srec.checkpoint_id, "error": srec.last_error},
            )
        except Exception:
            pass

        return srec


def resolve_resume_plan(pdir: Path, aspect: str = "16:9") -> dict[str, Any]:
    """Calculates resume graph: earliest invalid stage, reusable checkpoints, and invalidated stages."""
    state = load_pipeline_state(pdir)
    reusable_stages: list[dict[str, Any]] = []
    invalidated_stages: list[str] = []
    earliest_invalid_stage: str | None = None
    invalidation_reason: str = "all_stages_completed"

    for sid in ACTIVE_STAGES:
        srec = state.stages.get(sid)

        # Check if this stage has already been invalidated by an upstream failure
        if earliest_invalid_stage is not None:
            invalidated_stages.append(sid)
            continue

        # If not marked completed, this is the earliest invalid stage
        if not srec or srec.status != "completed":
            earliest_invalid_stage = sid
            invalidation_reason = f"stage_not_completed:{srec.status if srec else 'missing'}"
            invalidated_stages.append(sid)
            continue

        # 1. Verify artifacts exist and validate against contracts
        try:
            manifest = artifact_contracts.validate_stage_artifacts(pdir, sid, aspect)
        except artifact_contracts.ContractError as e:
            earliest_invalid_stage = sid
            invalidation_reason = f"contract_invalid:{sid}:{e}"
            invalidated_stages.append(sid)
            continue

        # 2. Verify input and output fingerprints match current files on disk
        current_in_fp = llm_review.compute_stage_input_fingerprint(pdir, sid, aspect)
        current_out_fp = llm_review.compute_stage_output_fingerprint(pdir, sid, aspect)

        if srec.input_fingerprint != current_in_fp:
            earliest_invalid_stage = sid
            invalidation_reason = f"stale_inputs:{sid}"
            invalidated_stages.append(sid)
            continue

        if srec.output_fingerprint != current_out_fp:
            earliest_invalid_stage = sid
            invalidation_reason = f"stale_outputs:{sid}"
            invalidated_stages.append(sid)
            continue

        # 3. Verify Phase 2 LLM review gate is fresh and passed
        passed, reason, _ = llm_review.is_stage_review_passed(pdir, sid, aspect, auto_pilot=True)
        if not passed:
            earliest_invalid_stage = sid
            invalidation_reason = f"review_gate_failed:{sid}:{reason}"
            invalidated_stages.append(sid)
            continue

        # Stage is 100% verified and can be safely reused without rerun
        reusable_stages.append({
            "stage_id": sid,
            "checkpoint_id": srec.checkpoint_id,
            "attempt": srec.attempt,
            "completed_at": srec.completed_at,
            "artifact_count": len(manifest),
        })

    return {
        "project_id": pdir.name,
        "aspect": aspect,
        "earliest_invalid_stage": earliest_invalid_stage,
        "reusable_checkpoints": reusable_stages,
        "reusable_count": len(reusable_stages),
        "invalidated_stages": invalidated_stages,
        "invalidated_count": len(invalidated_stages),
        "invalidation_reason": invalidation_reason,
        "can_resume": earliest_invalid_stage is not None,
    }
