"""Execution Planning Engine for Main Orchestrator Agent.

Analyzes project requirements, audio characteristics, aspect ratios, checkpoint
integrity, and registered agent capabilities to formulate structured, evidence-based
execution plans with clear decision rationale.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from SYSTEM.core import pipeline_state, resilience
from SYSTEM.memory import store
from .model_selector import model_selector

logger = logging.getLogger("orchestrator.planner")


@dataclass
class PlannedStage:
    stage_id: str
    agent_id: str
    action: str  # "execute" | "reuse_checkpoint" | "await_approval"
    estimated_duration_s: float
    dependencies: list[str]
    input_artifacts: list[str]
    output_artifacts: list[str]
    is_gate: bool = False
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionPlan:
    plan_id: str
    project_id: str
    aspect: str
    created_at: float = field(default_factory=time.time)
    stages_to_run: list[str] = field(default_factory=list)
    stages_to_reuse: list[str] = field(default_factory=list)
    planned_stages: list[PlannedStage] = field(default_factory=list)
    approval_gates: list[str] = field(default_factory=list)
    risk_assessment: list[str] = field(default_factory=list)
    decision_rationale: str = ""
    estimated_total_duration_s: float = 0.0
    prerequisites_met: bool = True
    unmet_prerequisites: list[str] = field(default_factory=list)
    lessons_applied: list[str] = field(default_factory=list)
    parallelizable_subtasks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["planned_stages"] = [s.to_dict() if isinstance(s, PlannedStage) else s for s in self.planned_stages]
        return d


class OrchestratorPlanner:
    """Constructs evidence-based execution plans combining deterministic state audits with LLM reasoning."""

    def __init__(self) -> None:
        pass

    def create_plan(
        self,
        project_dir: Path,
        aspect: str = "16:9",
        from_stage: str | None = None,
        to_stage: str | None = None,
        resume: bool = True,
        user_instructions: str = "",
        applicable_lessons: list[dict[str, Any]] | None = None,
    ) -> ExecutionPlan:
        """Evaluates project state, checkpoints, audio metadata, and generates an ExecutionPlan."""
        plan_id = f"plan_{uuid.uuid4().hex[:8]}"
        project_id = project_dir.name
        applicable_lessons = applicable_lessons or []

        # 1. Inspect Audio metadata
        audio_duration = 10.0
        audio_file = ""
        info_file = project_dir / "info.json"
        if info_file.exists():
            try:
                info_data = json.loads(info_file.read_text(encoding="utf-8"))
                audio_meta = info_data.get("audio", {})
                audio_duration = float(audio_meta.get("duration", 10.0))
                audio_file = audio_meta.get("file", "")
            except Exception:
                pass

        # 2. Check System Prerequisites
        from VIDEO_ENGINE.pipeline import orchestrator
        caps = orchestrator.check_system_capabilities()
        unmet_prereqs = []
        if not caps.get("tools", {}).get("node", {}).get("available"):
            unmet_prereqs.append("Node.js runtime not found on system PATH")
        if not caps.get("tools", {}).get("ffmpeg", {}).get("available"):
            unmet_prereqs.append("FFmpeg binary not found on system PATH")
        if not caps.get("browser", {}).get("browser_ready"):
            unmet_prereqs.append(caps.get("browser", {}).get("unresolved_limitation", "Headless browser not ready"))

        # 3. Determine Reusable Checkpoints vs. Stages to Run
        stages_to_run: list[str] = []
        stages_to_reuse: list[str] = []
        active_stages = orchestrator.ACTIVE_STAGES

        if resume and not from_stage:
            resume_plan = pipeline_state.resolve_resume_plan(project_dir, aspect)
            reused_ids = {rc["stage_id"] for rc in resume_plan.get("reusable_checkpoints", [])}

            for sid in active_stages:
                if sid in reused_ids:
                    is_valid, _, _ = resilience.validate_checkpoint_deep(project_dir, sid, aspect)
                    if is_valid:
                        stages_to_reuse.append(sid)
                    else:
                        stages_to_run.append(sid)
                else:
                    stages_to_run.append(sid)
        else:
            start_idx = active_stages.index(from_stage) if from_stage in active_stages else 0
            stages_to_reuse = list(active_stages[:start_idx])
            stages_to_run = list(active_stages[start_idx:])

        if to_stage and to_stage in active_stages:
            end_idx = active_stages.index(to_stage) + 1
            stages_to_run = [s for s in stages_to_run if active_stages.index(s) < end_idx]

        # 4. Map Planned Stages with durations and artifacts
        planned_stages: list[PlannedStage] = []
        approval_gates = ["approval", "qc"]
        total_duration = 0.0

        for sid in active_stages:
            agent_id = orchestrator.STAGE_TO_AGENT.get(sid, "main_orchestrator")
            is_gate = sid in approval_gates
            weight = orchestrator.STAGE_WEIGHTS.get(sid, 0.08)
            est_dur = round(max(2.0, audio_duration * weight * 1.5), 1)

            if sid in stages_to_reuse:
                action = "reuse_checkpoint"
                est_dur = 0.1
            elif is_gate:
                action = "await_approval"
                est_dur = 1.0
            else:
                action = "execute"
                total_duration += est_dur

            planned_stages.append(
                PlannedStage(
                    stage_id=sid,
                    agent_id=agent_id,
                    action=action,
                    estimated_duration_s=est_dur,
                    dependencies=list(orchestrator.STAGE_DEPENDENCIES.get(sid, ())),
                    input_artifacts=[f"{sid}_in"],
                    output_artifacts=[f"{sid}_out"],
                    is_gate=is_gate,
                    notes=f"Weight: {weight:.2f}",
                )
            )

        # 5. Risk Assessment
        risks: list[str] = []
        if audio_duration > 180.0:
            risks.append(f"Extended audio duration ({audio_duration:.1f}s) may increase Remotion render memory pressure.")
        if unmet_prereqs:
            risks.append(f"Unmet system prerequisites: {'; '.join(unmet_prereqs)}.")
        if not (project_dir / "audio.wav").exists() and not (project_dir / audio_file).exists():
            risks.append("Audio source file missing or not yet uploaded.")

        # 6. Parallelizable Independent Subtasks
        parallel_tasks = [
            "Prerequisite environmental check (FFmpeg, Node, Browser)",
            "Resource library font and asset readiness audit",
            "Deep integrity check across reusable prior checkpoints",
        ]

        # 7. Formulate Decision Rationale (via LLM or deterministic fallback)
        lessons_applied = [str(l.get("lesson_id", "")) for l in applicable_lessons if l.get("lesson_id")]
        rationale = (
            f"Execution plan formulated for project '{project_id}' in {aspect} format. "
            f"Evaluated {len(stages_to_reuse)} reusable checkpoints and scheduled {len(stages_to_run)} stages. "
            f"Mandatory LLM-decided approval gates enforced at Stage 8 (Timeline Approval) and Stage 10 (Final QC). "
            f"Audio duration is {audio_duration:.1f}s. Estimated execution duration: {total_duration:.1f}s."
        )
        if user_instructions:
            rationale += f" User instructions: '{user_instructions}'."

        # Attempt structured LLM enhancement for rationale and risk synthesis
        system_prompt = (
            "You are the Main Orchestrator Agent for the LAXMAN-AUTONOMOUS video generation system. "
            "Analyze the project execution context and provide a concise, professional 2-sentence rationale "
            "explaining the planned execution sequence, reuse strategy, and risk mitigation."
        )
        user_prompt = (
            f"Project: {project_id}\n"
            f"Aspect: {aspect}\n"
            f"Audio Duration: {audio_duration:.1f}s\n"
            f"Stages to Reuse: {stages_to_reuse}\n"
            f"Stages to Run: {stages_to_run}\n"
            f"Risks: {risks}\n"
            f"User Instructions: {user_instructions or 'Standard autonomous run'}\n"
            f"Applicable Lessons: {lessons_applied}\n"
        )
        llm_data, _ = model_selector.execute_call(
            task_type="plan",
            system_instruction=system_prompt,
            user_prompt=user_prompt,
            project_id=project_id,
        )
        if llm_data and isinstance(llm_data, dict) and llm_data.get("rationale"):
            rationale = str(llm_data["rationale"])

        plan = ExecutionPlan(
            plan_id=plan_id,
            project_id=project_id,
            aspect=aspect,
            stages_to_run=stages_to_run,
            stages_to_reuse=stages_to_reuse,
            planned_stages=planned_stages,
            approval_gates=approval_gates,
            risk_assessment=risks,
            decision_rationale=rationale,
            estimated_total_duration_s=round(total_duration, 1),
            prerequisites_met=len(unmet_prereqs) == 0,
            unmet_prerequisites=unmet_prereqs,
            lessons_applied=lessons_applied,
            parallelizable_subtasks=parallel_tasks,
        )

        return plan


orchestrator_planner = OrchestratorPlanner()
