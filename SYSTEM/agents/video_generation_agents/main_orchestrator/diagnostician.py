"""Intelligent Error Diagnosis and Recovery Reasoner for Main Orchestrator Agent.

Gathers evidence across error logs, stack traces, stage artifacts, and prior attempts;
determines root cause hypotheses; selects targeted recovery actions; and guarantees that
retry attempts differ meaningfully from prior unsuccessful executions.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from SYSTEM.core import resilience
from .model_selector import model_selector

logger = logging.getLogger("orchestrator.diagnostician")

RecoveryActionType = Literal[
    "RETRY_WITH_BACKOFF",
    "REPAIR_INTERMEDIATE_ARTIFACT",
    "ADJUST_PARAMETERS",
    "ALTERNATIVE_STRATEGY",
    "SAFE_STOP",
]


@dataclass
class DiagnosticReport:
    diagnosis_id: str
    project_id: str
    stage_id: str
    attempt: int
    error_category: str
    error_code: str
    raw_error_message: str
    root_cause_hypothesis: str
    recommended_action: RecoveryActionType
    is_retry_safe: bool
    differs_from_prior_attempt: bool
    parameter_adjustments: dict[str, Any] = field(default_factory=dict)
    repair_summary: str = ""
    decision_rationale: str = ""
    applicable_lesson_ids: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class OrchestratorDiagnostician:
    """Diagnoses stage execution failures using context evidence, past lessons, and LLM reasoning."""

    def __init__(self) -> None:
        pass

    def diagnose_and_prescribe(
        self,
        project_dir: Path,
        stage_id: str,
        error: Exception | str,
        attempt: int,
        max_retries: int,
        prior_actions: list[str] | None = None,
        available_lessons: list[dict[str, Any]] | None = None,
        aspect: str = "16:9",
    ) -> DiagnosticReport:
        """Gathers context, classifies failure, checks prior attempts, and prescribes recovery."""
        diagnosis_id = f"diag_{uuid.uuid4().hex[:8]}"
        project_id = project_dir.name
        prior_actions = prior_actions or []
        available_lessons = available_lessons or []

        # 1. Resilience error classification
        error_cat, error_code, retry_eligible = resilience.classify_error(error)
        clean_msg = resilience.sanitize_secrets(str(error))

        # 2. Check available verified lessons matching this stage and error
        matching_lesson_ids = []
        lesson_repair_hint = ""
        for l in available_lessons:
            target_stage = l.get("stage_id") or l.get("applicable_stage")
            target_cat = l.get("error_category")
            if (not target_stage or target_stage == stage_id) and (not target_cat or target_cat == error_cat.value):
                matching_lesson_ids.append(str(l.get("lesson_id", "")))
                if l.get("repair_recipe"):
                    lesson_repair_hint = str(l.get("repair_recipe"))

        # 3. Check for specific fixable artifact conditions
        is_fixable_artifact = False
        repair_action_summary = ""

        # Condition A: Malformed or truncated JSON in scene_plan or composition
        if stage_id in ("planning", "motion_plan", "motion_gen"):
            sp_file = project_dir / "scene_plan.json"
            if sp_file.exists():
                try:
                    json.loads(sp_file.read_text(encoding="utf-8"))
                except Exception as json_err:
                    is_fixable_artifact = True
                    repair_action_summary = f"Detected corrupted scene_plan.json: {json_err}. Rebuilding baseline schema."

        # Condition B: Stale temporary locks or tmp files
        stale_tmps = list(project_dir.glob("*.tmp")) + list(project_dir.glob(".*.lock"))
        if stale_tmps:
            is_fixable_artifact = True
            repair_action_summary += f" Found {len(stale_tmps)} stale temporary locks/files. Cleaning stale files."

        # 4. Strategy Selection Logic (Ensuring retry differs from previous attempts)
        recommended_action: RecoveryActionType = "SAFE_STOP"
        is_safe = False
        differs = True
        param_adjustments: dict[str, Any] = {}
        hypothesis = f"Execution failed in stage '{stage_id}' due to {error_cat.value} ({error_code})."

        if stage_id in ("approval", "qc", "timeline_approval", "final_qc") or "approval" in clean_msg.lower():
            recommended_action = "SAFE_STOP"
            is_safe = False
            differs = False
            hypothesis = f"Mandatory approval gate '{stage_id}' (decided by an LLM review) cannot be bypassed by automated retry."
            rationale = (
                f"Diagnosed stage '{stage_id}' failure (attempt {attempt}/{max_retries}). "
                f"Prescribed action: SAFE_STOP. Approval gates cannot be bypassed by automation."
            )
            return DiagnosticReport(
                diagnosis_id=diagnosis_id,
                project_id=project_id,
                stage_id=stage_id,
                attempt=attempt,
                error_category=error_cat.value,
                error_code=error_code,
                raw_error_message=clean_msg,
                root_cause_hypothesis=hypothesis,
                recommended_action=recommended_action,
                is_retry_safe=is_safe,
                differs_from_prior_attempt=differs,
                parameter_adjustments=param_adjustments,
                repair_summary=repair_action_summary,
                decision_rationale=rationale,
                applicable_lesson_ids=matching_lesson_ids,
            )

        if error_cat == resilience.ErrorCategory.SECURITY or not retry_eligible:
            recommended_action = "SAFE_STOP"
            is_safe = False
            differs = False
            hypothesis = f"Security or policy boundary reached in stage '{stage_id}': {clean_msg}. Automated recovery halted."

        elif is_fixable_artifact:
            recommended_action = "REPAIR_INTERMEDIATE_ARTIFACT"
            is_safe = True
            differs = "REPAIR_INTERMEDIATE_ARTIFACT" not in prior_actions
            hypothesis = f"Stage '{stage_id}' failed due to intermediate artifact inconsistency. {repair_action_summary}"

        elif attempt >= max_retries:
            recommended_action = "SAFE_STOP"
            is_safe = False
            differs = False
            hypothesis = f"Retry budget exhausted ({attempt}/{max_retries}) for stage '{stage_id}' without success."

        elif error_cat in (resilience.ErrorCategory.TRANSIENT, resilience.ErrorCategory.RESOURCE):
            # If plain retry was already attempted and failed again, adjust parameters
            if "RETRY_WITH_BACKOFF" in prior_actions:
                recommended_action = "ADJUST_PARAMETERS"
                is_safe = True
                differs = True
                param_adjustments = {
                    "backoff_multiplier": 2.0,
                    "timeout_seconds": 60.0 * (attempt + 1),
                    "force_cache_invalidation": True,
                }
                hypothesis = f"Repeated transient fault in stage '{stage_id}'. Shifting strategy to parameter adjustment and cache refresh."
            else:
                recommended_action = "RETRY_WITH_BACKOFF"
                is_safe = True
                differs = True
                hypothesis = f"Transient I/O or network contention in stage '{stage_id}'. Safe to retry with exponential backoff."

        elif error_cat == resilience.ErrorCategory.TIMEOUT:
            recommended_action = "ADJUST_PARAMETERS"
            is_safe = True
            differs = "timeout_boost" not in prior_actions
            param_adjustments = {"timeout_seconds": 120.0, "timeout_boost": True}
            hypothesis = f"Stage '{stage_id}' timed out. Boosting timeout deadline to 120s for next attempt."

        else:
            recommended_action = "SAFE_STOP"
            is_safe = False
            differs = False
            hypothesis = f"Unrecoverable or unclassified fault in stage '{stage_id}': {clean_msg}."

        rationale = (
            f"Diagnosed stage '{stage_id}' failure (attempt {attempt}/{max_retries}). "
            f"Prescribed action: {recommended_action}. "
            f"Differs from previous attempts: {differs}. Safe to proceed: {is_safe}."
        )

        # 5. Optional LLM reasoning enhancement (if reasoning profile is available)
        try:
            sys_prompt = (
                "You are the Intelligent Diagnostician for the LAXMAN-AUTONOMOUS video engine orchestrator. "
                "Analyze the stage error and provide a concise 1-sentence root-cause hypothesis and recovery rationale."
            )
            u_prompt = (
                f"Stage: {stage_id}\n"
                f"Attempt: {attempt}/{max_retries}\n"
                f"Error: {clean_msg}\n"
                f"Error Category: {error_cat.value}\n"
                f"Prior Actions: {prior_actions}\n"
                f"Selected Strategy: {recommended_action}\n"
                f"Lesson Hint: {lesson_repair_hint or 'None'}\n"
            )
            llm_res, _ = model_selector.execute_call(
                task_type="diagnose",
                system_instruction=sys_prompt,
                user_prompt=u_prompt,
                project_id=project_id,
            )
            if llm_res and isinstance(llm_res, dict) and llm_res.get("hypothesis"):
                hypothesis = str(llm_res["hypothesis"])
        except Exception:
            pass

        return DiagnosticReport(
            diagnosis_id=diagnosis_id,
            project_id=project_id,
            stage_id=stage_id,
            attempt=attempt,
            error_category=error_cat.value,
            error_code=error_code,
            raw_error_message=clean_msg,
            root_cause_hypothesis=hypothesis,
            recommended_action=recommended_action,
            is_retry_safe=is_safe,
            differs_from_prior_attempt=differs,
            parameter_adjustments=param_adjustments,
            repair_summary=repair_action_summary,
            decision_rationale=rationale,
            applicable_lesson_ids=matching_lesson_ids,
        )

    def apply_repair(self, project_dir: Path, stage_id: str, report: DiagnosticReport) -> bool:
        """Executes targeted, safe repair actions based on the diagnostic report."""
        if report.recommended_action != "REPAIR_INTERMEDIATE_ARTIFACT":
            return False

        repaired = False
        try:
            # Action 1: Remove stale locks or tmp files
            for p in list(project_dir.glob("*.tmp")) + list(project_dir.glob(".*.lock")):
                try:
                    p.unlink(missing_ok=True)
                    repaired = True
                except Exception:
                    pass

            # Action 2: Repair corrupted scene_plan.json
            sp_file = project_dir / "scene_plan.json"
            if sp_file.exists():
                try:
                    json.loads(sp_file.read_text(encoding="utf-8"))
                except Exception:
                    from VIDEO_ENGINE.pipeline.orchestrator import ensure_motion_planning_artifacts
                    ensure_motion_planning_artifacts(project_dir)
                    repaired = True

            logger.info(f"Successfully applied targeted repair for stage '{stage_id}': {report.repair_summary}")
            return repaired
        except Exception as e:
            logger.warning(f"Failed to apply repair for stage '{stage_id}': {e}")
            return False


orchestrator_diagnostician = OrchestratorDiagnostician()
