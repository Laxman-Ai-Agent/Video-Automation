"""Dedicated implementation module for Main Orchestrator Agent.
Agent ID: main_orchestrator
Stage ID: pipeline
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from SYSTEM.agents.shared.base_agent import BaseAgent
from SYSTEM.agents.shared.contracts import AgentCategory, AgentMetadata, AgentRequest, AgentResult, AgentStatus, ArtifactRef
from SYSTEM.memory import store
from .diagnostician import orchestrator_diagnostician
from .learning_engine import learning_engine
from .model_selector import model_selector
from .planner import orchestrator_planner

logger = logging.getLogger("main_orchestrator.agent")


class MainOrchestratorAgent(BaseAgent):
    """A01: Main Orchestrator Agent. Coordinates stage progression, safe-stops,
    intelligent execution planning, failure diagnosis, targeted recovery, and persistent self-learning.
    """

    def __init__(self, metadata: AgentMetadata | None = None) -> None:
        if metadata is None:
            metadata = AgentMetadata(
                agent_id="main_orchestrator",
                name="Main Orchestrator Agent",
                version="2.0.0",
                category=AgentCategory.ORCHESTRATOR,
                status=AgentStatus.IMPLEMENTED,
                purpose="Coordinates stage progression, safe-stops, execution planning, failure diagnosis, and persistent self-learning.",
                capabilities=["orchestration", "auto-advance", "planning", "diagnosis", "self-learning"],
                stage_id="pipeline",
                allowed_tools=["job_queue", "step_graph", "pipeline_view", "llm_gateway"],
                owner="agent-system",
            )
        super().__init__(metadata)

    def validate(self, project_dir: Path, request: AgentRequest) -> list[str]:
        from SYSTEM.core.artifact_contracts import verify_path_confinement
        try:
            verify_path_confinement(project_dir, project_dir)
        except Exception as e:
            return [f"Path traversal detected: {e}"]
        if not project_dir.exists():
            return [f"Project directory {project_dir} does not exist"]
        return []

    def execute(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        from VIDEO_ENGINE.pipeline import orchestrator
        try:
            from UI.backend import pipeline_view
        except ImportError:
            from backend import pipeline_view

        action = request.parameters.get("action", "status")
        aspect = request.parameters.get("aspect", "16:9")

        # ----------------------------------------------------------------------
        # ACTION: plan (LLM-Driven Execution Planning with Decision Rationale)
        # ----------------------------------------------------------------------
        if action == "plan":
            applicable_lessons = [
                l.to_dict() for l in learning_engine.retrieve_lessons(tier="verified")
            ]
            plan = orchestrator_planner.create_plan(
                project_dir=project_dir,
                aspect=aspect,
                from_stage=request.parameters.get("from_stage"),
                to_stage=request.parameters.get("to_stage"),
                resume=bool(request.parameters.get("resume", True)),
                user_instructions=str(request.parameters.get("user_instructions", "")),
                applicable_lessons=applicable_lessons,
            )
            return AgentResult(
                agent_id=self.agent_id,
                stage_id=request.stage_id or "pipeline",
                project_id=project_dir.name,
                status="succeeded",
                summary=f"Orchestrator created execution plan '{plan.plan_id}' ({len(plan.stages_to_run)} stages to run, {len(plan.stages_to_reuse)} to reuse)",
                metadata={"plan": plan.to_dict()},
            )

        # ----------------------------------------------------------------------
        # ACTION: diagnose (Intelligent Error Diagnosis and Root-Cause Analysis)
        # ----------------------------------------------------------------------
        elif action == "diagnose":
            stage_id = str(request.parameters.get("target_stage", "planning"))
            error_msg = str(request.parameters.get("error_message", "Unknown error"))
            attempt = int(request.parameters.get("attempt", 1))
            max_retries = int(request.parameters.get("max_retries", 3))
            prior_actions = list(request.parameters.get("prior_actions", []))
            available_lessons = [
                l.to_dict() for l in learning_engine.retrieve_lessons(stage_id=stage_id)
            ]

            diag = orchestrator_diagnostician.diagnose_and_prescribe(
                project_dir=project_dir,
                stage_id=stage_id,
                error=error_msg,
                attempt=attempt,
                max_retries=max_retries,
                prior_actions=prior_actions,
                available_lessons=available_lessons,
                aspect=aspect,
            )
            return AgentResult(
                agent_id=self.agent_id,
                stage_id=request.stage_id or "pipeline",
                project_id=project_dir.name,
                status="succeeded",
                summary=f"Orchestrator diagnosed stage '{stage_id}': {diag.recommended_action} (differs={diag.differs_from_prior_attempt})",
                metadata={"diagnostic": diag.to_dict()},
            )

        # ----------------------------------------------------------------------
        # ACTION: recover (Targeted Artifact Repair Execution)
        # ----------------------------------------------------------------------
        elif action == "recover":
            stage_id = str(request.parameters.get("target_stage", "planning"))
            diag_dict = request.parameters.get("diagnostic")
            if diag_dict and isinstance(diag_dict, dict):
                from .diagnostician import DiagnosticReport
                report = DiagnosticReport(**diag_dict)
            else:
                diag_dict = request.parameters.get("diagnostic", {})
                report = orchestrator_diagnostician.diagnose_and_prescribe(
                    project_dir=project_dir,
                    stage_id=stage_id,
                    error=request.parameters.get("error_message", "Recovery needed"),
                    attempt=int(request.parameters.get("attempt", 1)),
                    max_retries=int(request.parameters.get("max_retries", 3)),
                    aspect=aspect,
                )

            repaired = orchestrator_diagnostician.apply_repair(project_dir, stage_id, report)
            return AgentResult(
                agent_id=self.agent_id,
                stage_id=request.stage_id or "pipeline",
                project_id=project_dir.name,
                status="succeeded" if repaired else "failed",
                summary=f"Orchestrator applied targeted repair for stage '{stage_id}' (success={repaired})",
                metadata={"repaired": repaired, "diagnostic": report.to_dict()},
            )

        # ----------------------------------------------------------------------
        # ACTION: lessons (Persistent Self-Learning Lesson Retrieval)
        # ----------------------------------------------------------------------
        elif action == "lessons":
            tier_filter = request.parameters.get("tier")
            stage_filter = request.parameters.get("target_stage")
            lessons = learning_engine.retrieve_lessons(
                stage_id=stage_filter,
                tier=tier_filter,
            )
            summary = learning_engine.get_summary()
            return AgentResult(
                agent_id=self.agent_id,
                stage_id=request.stage_id or "pipeline",
                project_id=project_dir.name,
                status="succeeded",
                summary=f"Orchestrator retrieved {len(lessons)} lessons ({summary['verified_count']} verified, {summary['candidate_count']} candidate)",
                metadata={"lessons": [l.to_dict() for l in lessons], "summary": summary},
            )

        # ----------------------------------------------------------------------
        # ACTION: model_budget (Model Selector Cost & Token Spend Metrics)
        # ----------------------------------------------------------------------
        elif action == "model_budget":
            spend = model_selector.get_total_spend()
            return AgentResult(
                agent_id=self.agent_id,
                stage_id=request.stage_id or "pipeline",
                project_id=project_dir.name,
                status="succeeded",
                summary=f"Orchestrator LLM spend: {spend['calls_count']} calls, {spend['total_tokens']} tokens, ${spend['total_cost_usd']} USD",
                metadata={"spend": spend},
            )

        # ----------------------------------------------------------------------
        # ACTION: run (Start or Resume Autonomous Video Pipeline Run)
        # ----------------------------------------------------------------------
        elif action == "run":
            orch = orchestrator.PipelineOrchestrator(project_dir.name, aspect)
            run = orch.start_run(
                from_stage=request.parameters.get("from_stage"),
                to_stage=request.parameters.get("to_stage"),
                resume=bool(request.parameters.get("resume", True)),
                max_retries=int(request.parameters.get("max_retries", 3)),
                synchronous=bool(request.parameters.get("synchronous", False)),
            )
            return AgentResult(
                agent_id=self.agent_id,
                stage_id=request.stage_id or "pipeline",
                project_id=project_dir.name,
                status="succeeded",
                summary=f"Orchestrator started run '{run.run_id}' (status={run.status}, aspect={aspect})",
                metadata={"run": run.to_dict()},
            )

        # ----------------------------------------------------------------------
        # ACTION: cancel (Cancel Active Pipeline Run)
        # ----------------------------------------------------------------------
        elif action == "cancel":
            orch = orchestrator.PipelineOrchestrator(project_dir.name, aspect)
            run = orch.cancel_run(run_id=request.parameters.get("run_id"))
            return AgentResult(
                agent_id=self.agent_id,
                stage_id=request.stage_id or "pipeline",
                project_id=project_dir.name,
                status="succeeded",
                summary=f"Orchestrator cancelled run '{run.run_id}' (status={run.status})",
                metadata={"run": run.to_dict()},
            )

        # ----------------------------------------------------------------------
        # ACTION: capabilities (Check System Prerequisites & Capabilities)
        # ----------------------------------------------------------------------
        elif action == "capabilities":
            caps = orchestrator.check_system_capabilities()
            return AgentResult(
                agent_id=self.agent_id,
                stage_id=request.stage_id or "pipeline",
                project_id=project_dir.name,
                status="succeeded",
                summary="Orchestrator evaluated system capabilities and environment prerequisites",
                metadata={"capabilities": caps},
            )

        # ----------------------------------------------------------------------
        # DEFAULT ACTION: status (Pipeline State & Monitoring Telemetry)
        # ----------------------------------------------------------------------
        else:
            status_data = orchestrator.get_monitoring_status(project_dir.name, aspect)
            view = pipeline_view.build(project_dir.name)
            return AgentResult(
                agent_id=self.agent_id,
                stage_id=request.stage_id or "pipeline",
                project_id=project_dir.name,
                status="succeeded",
                summary=f"Orchestrator evaluated pipeline. Active stages: {len(view.get('stages', []))}, Overall status: {status_data['overall_status']}",
                metadata={"pipeline_view": view, "monitoring_status": status_data},
            )


# Backward-compatibility alias
MainOrchestratorAdapter = MainOrchestratorAgent
