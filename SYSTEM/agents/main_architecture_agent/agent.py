"""Authoritative Main Architecture Agent (System Coordinator).

Responsible for:
1. Understanding high-level system user goals and architectural requirements.
2. Decomposing complex requests into executable subtasks with dependencies via TaskDecomposer.
3. Capability-driven and experience-informed subtask routing via AgentRouter.
4. Pre-execution plan validation and dependency cycle checking via PlanEvaluator.
5. Delegating work to appropriate system subagents or video-generation agents.
6. Recording task execution experiences and redacting secrets via ExperienceCollector.
7. Continuous self-reflection, pattern derivation, and confidence scoring via ReflectionEngine.
8. Generating governed, declarative strategy proposals via ImprovementProposalEngine.
9. Deterministic planning and routing benchmark validation via EvaluationRunner.
10. Atomic strategy lifecycle management, promotion, and rollback via StrategyManager.
11. Enforcing security, permissions, execution limits, and Laxman Approval gates.

BOUNDARY NOTE:
The Main Architecture Agent is the system-level coordinator. It does NOT compete with
or replace VIDEO_ENGINE.pipeline.orchestrator.PipelineOrchestrator, which remains the sole
canonical engine for video pipeline execution, stage sequencing, checkpoints, and rendering.
"""
from __future__ import annotations

import copy
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from SYSTEM.agents.shared.base_agent import BaseAgent
from SYSTEM.agents.shared.contracts import (
    AgentCategory,
    AgentMetadata,
    AgentRequest,
    AgentResult,
    AgentStatus,
)
from SYSTEM.history.decision_history import DecisionRecord
from SYSTEM.history.history_service import history_service
from SYSTEM.registries.skill_registry import registry as skill_registry
from SYSTEM.registries.tool_registry import tool_registry

from .evaluations.evaluation_runner import evaluation_runner
from .learning.experience_collector import ExperienceRecord, experience_collector
from .learning.improvement_proposals import proposal_engine
from .learning.learning_scheduler import learning_scheduler
from .learning.reflection_engine import reflection_engine
from .learning.strategy_manager import strategy_manager
from .planning.agent_router import agent_router
from .planning.plan_evaluator import plan_evaluator
from .planning.task_decomposer import task_decomposer

logger = logging.getLogger("main_architecture_agent")


@dataclass
class SubTask:
    task_id: str = field(default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}")
    title: str = ""
    assigned_agent_id: str = ""
    action: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    status: Literal["pending", "running", "succeeded", "failed", "blocked"] = "pending"
    result: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MainArchitectureAgent(BaseAgent):
    """System-level architectural coordinator and self-learning delegation supervisor."""

    def __init__(self, metadata: AgentMetadata | None = None) -> None:
        if metadata is None:
            metadata = AgentMetadata(
                agent_id="main_architecture_agent",
                name="Main Architecture Agent",
                version="1.0.0",
                category=AgentCategory.ORCHESTRATOR,
                status=AgentStatus.IMPLEMENTED,
                purpose="System-level Master Agent that decomposes requirements, routes tasks, supervises subagents, and continuously improves through experience.",
                capabilities=[
                    "task-decomposition",
                    "agent-delegation",
                    "capability-discovery",
                    "policy-enforcement",
                    "self-learning",
                    "experience-reflection",
                    "strategy-management",
                ],
                allowed_tools=[
                    "agent_registry",
                    "skill_registry",
                    "tool_registry",
                    "memory_service",
                    "history_service",
                    "strategy_manager",
                    "experience_collector",
                    "evaluation_runner",
                ],
                owner="system-core",
            )
        super().__init__(metadata)

    def validate(self, project_dir: Path, request: AgentRequest) -> list[str]:
        """Validates that a coordination request has an action or objective."""
        action = request.parameters.get("action", "plan")
        allowed_actions = {
            "plan",
            "delegate",
            "discover",
            "status",
            "execute_plan",
            "execute_autonomous_task",
            "resume_autonomous_task",
            "learn",
            "reflect",
            "proposals",
            "strategy",
            "record_feedback",
            "evaluate_strategy",
            "validate_architecture",
            "verify_and_test",
            "evaluate_security_policy",
            "enforce_security_policy",
        }
        if action not in allowed_actions:
            return [f"Unknown coordination action '{action}'. Allowed: {', '.join(sorted(allowed_actions))}"]
        return []

    def execute(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        """Executes system coordination, planning, delegation, or self-learning."""
        action = request.parameters.get("action", "plan")
        goal = request.parameters.get("goal", "")

        if action == "discover":
            return self._handle_discover(request)
        elif action == "plan":
            return self._handle_plan(goal, request)
        elif action == "delegate":
            return self._handle_delegate(project_dir, request)
        elif action in ("execute_plan", "execute_autonomous_task"):
            return self._handle_execute_autonomous_task(project_dir, request)
        elif action == "resume_autonomous_task":
            return self._handle_resume_autonomous_task(project_dir, request)
        elif action == "validate_architecture":
            return self._handle_validate_architecture(project_dir, request)
        elif action == "verify_and_test":
            return self._handle_verify_and_test(project_dir, request)
        elif action in ("evaluate_security_policy", "enforce_security_policy"):
            return self._handle_security_policy(project_dir, request)
        elif action == "learn":
            return self._handle_learn(request)
        elif action == "reflect":
            return self._handle_reflect(request)
        elif action == "proposals":
            return self._handle_proposals(request)
        elif action == "strategy":
            return self._handle_strategy(request)
        elif action == "record_feedback":
            return self._handle_record_feedback(request)
        elif action == "evaluate_strategy":
            return self._handle_evaluate_strategy(request)
        else:
            return self._handle_status(request)

    @property
    def _registry(self):
        from SYSTEM.registries.agent_registry import registry
        return registry

    def _handle_discover(self, request: AgentRequest) -> AgentResult:
        """Discovers all available agents, skills, and tools across the system."""
        agents = [a.to_dict() for a in self._registry.list_all_agents()]
        skills = [s.to_dict() for s in skill_registry.list_skills()]
        tools = [t.to_dict() for t in tool_registry.list_tools()]

        summary = f"Discovered {len(agents)} agents, {len(skills)} approved skills, and {len(tools)} tools."
        return AgentResult(
            agent_id=self.agent_id,
            status="succeeded",
            summary=summary,
            metadata={"agents": agents, "skills": skills, "tools": tools},
        )

    def _handle_plan(self, goal: str, request: AgentRequest) -> AgentResult:
        """Decomposes a user goal into structured subtasks with assigned agents using active Strategy."""
        # 1. Active Strategy Decompose
        active_strat = strategy_manager.get_active_strategy()
        raw_plan = task_decomposer.decompose(goal=goal, context=request.parameters, strategy=active_strat)

        # 2. Capability & Preference Routing
        routed_plan = agent_router.route_plan(raw_plan, strategy=active_strat)

        # 3. Pre-execution Plan Evaluation (Cycles, Agents, Prerequisites)
        eval_report = plan_evaluator.evaluate_plan(routed_plan, strategy=active_strat)

        # Construct legacy-compatible task list
        tasks: list[dict[str, Any]] = []
        for st in routed_plan.get("subtasks", []):
            task_dict = {
                "task_id": st.get("subtask_id"),
                "title": st.get("title"),
                "assigned_agent_id": st.get("assigned_agent_id"),
                "action": st.get("action"),
                "parameters": st.get("parameters", {}),
                "dependencies": [f"step_{d}" for d in st.get("dependencies", [])],
                "status": st.get("status", "pending"),
            }
            tasks.append(task_dict)

        # 4. Record coordination decision
        rec = DecisionRecord(
            agent_id=self.agent_id,
            decision_type="plan_decomposition",
            rationale=f"Decomposed goal '{goal}' into {len(tasks)} tasks via strategy v{active_strat.get('version')}.",
            chosen_option=f"{len(tasks)}_step_plan",
            project_id=request.project_id,
            task_id=request.correlation_id or routed_plan.get("task_id", "task_plan"),
            parameters={"tasks": [t["title"] for t in tasks], "strategy_version": active_strat.get("version")},
        )
        history_service.record_decision(rec)

        summary = f"Planned {len(tasks)} subtasks for goal: {goal}"
        if not eval_report.get("is_valid"):
            summary += f" (Warnings: {'; '.join(eval_report.get('errors', []))})"

        return AgentResult(
            agent_id=self.agent_id,
            stage_id=request.stage_id or "system",
            project_id=request.project_id or "system",
            status="succeeded" if eval_report.get("is_valid") else "failed",
            summary=summary,
            error="; ".join(eval_report.get("errors", [])) if not eval_report.get("is_valid") else None,
            metadata={
                "tasks": tasks,
                "plan": routed_plan,
                "plan_evaluation": eval_report,
                "strategy_version": active_strat.get("version"),
            },
        )

    def _handle_delegate(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        """Delegates an individual task to an assigned agent with lifecycle supervision and experience collection."""
        start_time = time.time()
        target_agent_id = request.parameters.get("target_agent_id") or request.parameters.get("target_agent")
        if not target_agent_id:
            return AgentResult(
                agent_id=self.agent_id,
                stage_id=request.stage_id or "system",
                project_id=request.project_id or "system",
                status="failed",
                error="Missing target_agent_id for delegation",
            )

        agent_meta = self._registry.get(target_agent_id)
        if not agent_meta:
            return AgentResult(
                agent_id=self.agent_id,
                stage_id=request.stage_id or "system",
                project_id=request.project_id or "system",
                status="failed",
                error=f"Target agent '{target_agent_id}' not found in registry",
            )

        # Record decision
        rec = DecisionRecord(
            agent_id=self.agent_id,
            decision_type="agent_delegation",
            rationale=f"Delegating task to {target_agent_id}",
            chosen_option=target_agent_id,
            project_id=request.project_id or (project_dir.name if project_dir else None),
            task_id=request.correlation_id or "task_delegate",
        )
        history_service.record_decision(rec)

        # Security Policy Enforcement Gate
        sec_agent = self._registry.get_agent("security_policy")
        if sec_agent:
            sub_params = request.parameters.get("sub_parameters", {})
            sec_req = AgentRequest(
                agent_id="security_policy",
                parameters={
                    "action": "enforce",
                    "target_agent_id": target_agent_id,
                    "operation": sub_params.get("action") or request.parameters.get("action", "delegate"),
                    "resource": sub_params.get("resource") or sub_params.get("path") or sub_params.get("target") or "",
                    "parameters": sub_params,
                    "payload": request.parameters.get("payload") or sub_params.get("payload", {}),
                    "approval_request_id": request.parameters.get("approval_request_id") or sub_params.get("approval_request_id"),
                    "role": request.parameters.get("role") or sub_params.get("role"),
                },
            )
            sec_res = sec_agent.invoke(project_dir, sec_req)
            if sec_res.status != "succeeded":
                return AgentResult(
                    agent_id=self.agent_id,
                    stage_id=request.stage_id or "system",
                    project_id=request.project_id or "system",
                    status="failed",
                    error=f"Security Policy Denied Delegation: {sec_res.error or sec_res.summary}",
                    metadata={"security_violation": sec_res.to_dict()},
                )

        # Execute via adapter or agent instance
        sub_request = AgentRequest(
            agent_id=target_agent_id,
            stage_id=agent_meta.stage_id,
            project_id=request.project_id or (project_dir.name if project_dir else "system"),
            parameters=request.parameters.get("sub_parameters", {}),
        )

        agent_instance = self._registry.get_agent(target_agent_id)
        if not agent_instance:
            return AgentResult(
                agent_id=self.agent_id,
                status="failed",
                error=f"No executable adapter found for agent '{target_agent_id}'",
            )

        res = agent_instance.invoke(project_dir, sub_request)
        duration_ms = (time.time() - start_time) * 1000.0

        # Record Experience
        active_strat = strategy_manager.get_active_strategy()
        exp = ExperienceRecord(
            task_id=request.correlation_id or f"task_{uuid.uuid4().hex[:8]}",
            correlation_id=request.correlation_id or "",
            project_id=request.project_id or (project_dir.name if project_dir else "system"),
            goal=request.parameters.get("goal") or f"Delegated action to {target_agent_id}",
            strategy_version=active_strat.get("version", "1.0.0"),
            selected_agents=[target_agent_id],
            status="succeeded" if res.status == "succeeded" else "failed",
            duration_ms=duration_ms,
            error_detail=res.error if res.status != "succeeded" else None,
            metadata={"delegated_action": request.parameters.get("action")},
        )
        experience_collector.record_task_experience(exp)

        # Autonomous Trigger Check
        if res.status != "succeeded":
            learning_scheduler.trigger_on_failure(exp)
        else:
            learning_scheduler.trigger_post_task(exp)

        return AgentResult(
            agent_id=self.agent_id,
            status=res.status,
            summary=f"Delegated task completed by {target_agent_id}: {res.summary}",
            output_refs=res.output_refs,
            error=res.error,
            metadata={"delegated_result": res.to_dict(), "experience_id": exp.experience_id},
        )

    def _handle_validate_architecture(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        """Delegates architecture validation to the canonical ArchitectureValidatorAgent."""
        validator_id = "architecture_validator"
        target_agent = self._registry.get_agent(validator_id)
        if not target_agent:
            return AgentResult(
                agent_id=self.agent_id,
                stage_id=request.stage_id or "system",
                project_id=request.project_id or "system",
                status="failed",
                error=f"Canonical validator '{validator_id}' not found in AgentRegistry",
            )

        sub_params = request.parameters.get("sub_parameters") or {
            k: v for k, v in request.parameters.items() if k != "action"
        }
        sub_action = request.parameters.get("audit_action") or request.parameters.get("mode") or "full_architecture_audit"
        sub_params["action"] = sub_action

        sub_req = AgentRequest(
            agent_id=validator_id,
            stage_id=request.stage_id or "system",
            project_id=request.project_id or (project_dir.name if project_dir else "system"),
            parameters=sub_params,
        )

        res = target_agent.invoke(project_dir, sub_req)
        return AgentResult(
            agent_id=self.agent_id,
            stage_id=request.stage_id or "system",
            project_id=request.project_id or "system",
            status=res.status,
            summary=f"Architecture validation coordinated: {res.summary}",
            error=res.error,
            metadata={
                "delegated_to": validator_id,
                "validator_result": res.to_dict(),
            },
        )

    def _handle_verify_and_test(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        """Delegates verification and test execution to the canonical VerificationAndTestAgent."""
        verif_id = "verification_and_test"
        target_agent = self._registry.get_agent(verif_id)
        if not target_agent:
            return AgentResult(
                agent_id=self.agent_id,
                stage_id=request.stage_id or "system",
                project_id=request.project_id or "system",
                status="failed",
                error=f"Canonical verification agent '{verif_id}' not found in AgentRegistry",
            )

        sub_params = request.parameters.get("sub_parameters") or {
            k: v for k, v in request.parameters.items() if k != "action"
        }
        sub_action = request.parameters.get("verification_action") or request.parameters.get("mode") or "verify"
        sub_params["action"] = sub_action

        sub_req = AgentRequest(
            agent_id=verif_id,
            stage_id=request.stage_id or "system",
            project_id=request.project_id or (project_dir.name if project_dir else "system"),
            parameters=sub_params,
        )

        res = target_agent.invoke(project_dir, sub_req)
        return AgentResult(
            agent_id=self.agent_id,
            stage_id=request.stage_id or "system",
            project_id=request.project_id or "system",
            status=res.status,
            summary=f"Verification coordinated: {res.summary}",
            error=res.error,
            metadata={
                "delegated_to": verif_id,
                "verification_result": res.to_dict(),
            },
        )

    def _handle_security_policy(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        """Delegates security policy evaluation or enforcement to the canonical SecurityPolicyAgent."""
        sec_id = "security_policy"
        target_agent = self._registry.get_agent(sec_id)
        if not target_agent:
            return AgentResult(
                agent_id=self.agent_id,
                stage_id=request.stage_id or "system",
                project_id=request.project_id or "system",
                status="failed",
                error=f"Canonical security policy agent '{sec_id}' not found in AgentRegistry",
            )

        sub_params = request.parameters.get("sub_parameters") or {
            k: v for k, v in request.parameters.items() if k != "action"
        }
        sub_action = request.parameters.get("security_action") or request.parameters.get("mode") or (
            "enforce" if request.parameters.get("action") == "enforce_security_policy" else "evaluate"
        )
        sub_params["action"] = sub_action

        sub_req = AgentRequest(
            agent_id=sec_id,
            stage_id=request.stage_id or "security",
            project_id=request.project_id or (project_dir.name if project_dir else "system"),
            parameters=sub_params,
        )

        res = target_agent.invoke(project_dir, sub_req)
        return AgentResult(
            agent_id=self.agent_id,
            stage_id=request.stage_id or "system",
            project_id=request.project_id or "system",
            status=res.status,
            summary=f"Security policy coordinated: {res.summary}",
            error=res.error,
            metadata={
                "delegated_to": sec_id,
                "security_result": res.to_dict(),
            },
        )

    def _handle_execute_autonomous_task(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        """Delegates autonomous task execution, bounded recovery, and durable checkpointing to AutonomousExecutionAgent."""
        auto_agent_id = "autonomous_execution"
        target_agent = self._registry.get_agent(auto_agent_id)
        if not target_agent:
            return AgentResult(
                agent_id=self.agent_id,
                stage_id=request.stage_id or "system",
                project_id=request.project_id or "system",
                status="failed",
                error=f"Canonical autonomous execution agent '{auto_agent_id}' not found in AgentRegistry",
            )

        # Record coordination decision
        rec = DecisionRecord(
            agent_id=self.agent_id,
            decision_type="autonomous_task_execution",
            rationale=f"Delegating autonomous task execution to {auto_agent_id}",
            chosen_option=auto_agent_id,
            project_id=request.project_id or (project_dir.name if project_dir else None),
            task_id=request.correlation_id or "task_auto_exec",
        )
        history_service.record_decision(rec)

        sub_params = request.parameters.get("sub_parameters") or {
            k: v for k, v in request.parameters.items() if k != "action"
        }
        sub_params["action"] = "execute_task"

        sub_req = AgentRequest(
            agent_id=auto_agent_id,
            stage_id=request.stage_id or "system",
            project_id=request.project_id or (project_dir.name if project_dir else "system"),
            parameters=sub_params,
        )

        res = target_agent.invoke(project_dir, sub_req)
        return AgentResult(
            agent_id=self.agent_id,
            stage_id=request.stage_id or "system",
            project_id=request.project_id or "system",
            status=res.status,
            summary=f"Autonomous task execution coordinated: {res.summary}",
            error=res.error,
            metadata={
                "delegated_to": auto_agent_id,
                "execution_result": res.to_dict(),
            },
        )

    def _handle_resume_autonomous_task(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        """Delegates task resumption from a checkpoint to AutonomousExecutionAgent."""
        auto_agent_id = "autonomous_execution"
        target_agent = self._registry.get_agent(auto_agent_id)
        if not target_agent:
            return AgentResult(
                agent_id=self.agent_id,
                stage_id=request.stage_id or "system",
                project_id=request.project_id or "system",
                status="failed",
                error=f"Canonical autonomous execution agent '{auto_agent_id}' not found in AgentRegistry",
            )

        sub_params = request.parameters.get("sub_parameters") or {
            k: v for k, v in request.parameters.items() if k != "action"
        }
        sub_params["action"] = "resume_task"

        sub_req = AgentRequest(
            agent_id=auto_agent_id,
            stage_id=request.stage_id or "system",
            project_id=request.project_id or (project_dir.name if project_dir else "system"),
            parameters=sub_params,
        )

        res = target_agent.invoke(project_dir, sub_req)
        return AgentResult(
            agent_id=self.agent_id,
            stage_id=request.stage_id or "system",
            project_id=request.project_id or "system",
            status=res.status,
            summary=f"Autonomous task resume coordinated: {res.summary}",
            error=res.error,
            metadata={
                "delegated_to": auto_agent_id,
                "resume_result": res.to_dict(),
            },
        )

    def _handle_learn(self, request: AgentRequest) -> AgentResult:
        """Triggers an explicit or scheduled self-learning cycle."""
        force = request.parameters.get("force", True)
        res = learning_scheduler.run_learning_cycle(force=force, authorized_by="manual_agent_request")
        return AgentResult(
            agent_id=self.agent_id,
            status="succeeded",
            summary=f"Learning cycle {res.get('cycle_id', 'unknown')} finished with status: {res.get('status')}.",
            metadata=res,
        )

    def _handle_reflect(self, request: AgentRequest) -> AgentResult:
        """Analyzes unreflected experiences and returns synthesized lessons."""
        rep = reflection_engine.reflect_on_experiences()
        return AgentResult(
            agent_id=self.agent_id,
            status="succeeded",
            summary=f"Reflection completed. Derived {len(rep.lessons)} lessons from {rep.analyzed_experience_count} experiences.",
            metadata=rep.to_dict(),
        )

    def _handle_proposals(self, request: AgentRequest) -> AgentResult:
        """Lists or inspects generated strategy improvement proposals."""
        status_filter = request.parameters.get("status")
        proposals = proposal_engine.get_proposals(status=status_filter)
        return AgentResult(
            agent_id=self.agent_id,
            status="succeeded",
            summary=f"Found {len(proposals)} improvement proposals (filter: {status_filter or 'all'}).",
            metadata={"proposals": [p.to_dict() for p in proposals]},
        )

    def _handle_strategy(self, request: AgentRequest) -> AgentResult:
        """Manages architecture strategy: retrieve active, list archived, promote, or rollback."""
        sub_action = request.parameters.get("sub_action", "get_active")

        if sub_action == "rollback":
            target_ver = request.parameters.get("target_version")
            reason = request.parameters.get("reason", "Operator requested rollback")
            restored = strategy_manager.rollback(target_version=target_ver, authorized_by="operator", reason=reason)
            return AgentResult(
                agent_id=self.agent_id,
                status="succeeded",
                summary=f"Rolled back active strategy to v{restored.get('version')}.",
                metadata={"active_strategy": restored},
            )
        elif sub_action == "activate":
            candidate_id = request.parameters.get("candidate_id")
            if not candidate_id:
                return AgentResult(agent_id=self.agent_id, status="failed", error="Missing candidate_id to activate.")
            activated = strategy_manager.activate_strategy(
                candidate_input=candidate_id,
                authorized_by=request.parameters.get("authorized_by", "operator"),
                reason=request.parameters.get("reason", "Manual activation"),
            )
            return AgentResult(
                agent_id=self.agent_id,
                status="succeeded",
                summary=f"Activated strategy v{activated.get('version')}.",
                metadata={"active_strategy": activated},
            )
        elif sub_action == "list_archive":
            archived = strategy_manager.list_archived_strategies()
            return AgentResult(
                agent_id=self.agent_id,
                status="succeeded",
                summary=f"Retrieved {len(archived)} archived strategy versions.",
                metadata={"archived_strategies": archived},
            )
        else:
            strat = strategy_manager.get_active_strategy()
            strat_hash = strategy_manager.get_active_strategy_hash()
            return AgentResult(
                agent_id=self.agent_id,
                status="succeeded",
                summary=f"Active strategy: {strat.get('name')} (v{strat.get('version')}, SHA256: {strat_hash[:8]}).",
                metadata={"active_strategy": strat, "strategy_hash": strat_hash},
            )

    def _handle_record_feedback(self, request: AgentRequest) -> AgentResult:
        """Records explicit user correction or feedback and triggers feedback learning."""
        task_id = request.parameters.get("task_id")
        feedback = request.parameters.get("feedback", {})
        if not task_id:
            return AgentResult(agent_id=self.agent_id, status="failed", error="Missing task_id for user feedback.")

        updated = experience_collector.record_user_feedback(task_id, feedback)
        if updated:
            # Trigger immediate learning cycle
            recent = experience_collector.get_experiences(limit=10)
            target_exp = next((e for e in recent if e.task_id == task_id), None)
            if target_exp:
                learning_scheduler.trigger_on_feedback(target_exp)

            return AgentResult(
                agent_id=self.agent_id,
                status="succeeded",
                summary=f"User feedback recorded and processed for task {task_id}.",
                metadata={"task_id": task_id, "feedback": feedback},
            )
        else:
            return AgentResult(
                agent_id=self.agent_id,
                status="failed",
                error=f"Task {task_id} not found in experience collector.",
            )

    def _handle_evaluate_strategy(self, request: AgentRequest) -> AgentResult:
        """Runs planning and routing benchmarks against active strategy."""
        strat = strategy_manager.get_active_strategy()
        res = evaluation_runner.evaluate_strategy(strat)
        return AgentResult(
            agent_id=self.agent_id,
            status="succeeded",
            summary=f"Strategy v{strat.get('version')} benchmark composite score: {res.get('composite_score')} (Planning: {res.get('planning_score')}, Routing: {res.get('routing_score')}).",
            metadata=res,
        )

    def _handle_status(self, request: AgentRequest) -> AgentResult:
        """Queries recent coordination, execution, and learning status."""
        recent_execs = history_service.query_executions(limit=10)
        recent_decs = history_service.query_decisions(agent_id=self.agent_id, limit=10)
        active_strat = strategy_manager.get_active_strategy()
        unreflected_count = len(experience_collector.get_unreflected_experiences())

        return AgentResult(
            agent_id=self.agent_id,
            status="succeeded",
            summary=f"Retrieved {len(recent_execs)} executions, {len(recent_decs)} decisions. Strategy: v{active_strat.get('version')}. Unreflected experiences: {unreflected_count}.",
            metadata={
                "recent_executions": recent_execs,
                "recent_decisions": recent_decs,
                "active_strategy_version": active_strat.get("version"),
                "unreflected_experiences": unreflected_count,
            },
        )
