"""Plan Evaluator for Main Architecture Agent.

Validates plans before execution:
- Circular dependency detection via topological sort
- Agent existence check against AgentRegistry
- Prerequisite tool readiness check
- Compliance with strategy acceptance criteria
"""
from __future__ import annotations

import collections
import logging
import shutil
from typing import Any

from ..learning.strategy_manager import strategy_manager

logger = logging.getLogger("main_architecture_agent.plan_evaluator")


class PlanEvaluator:
    """Pre-flight validator for decomposed task plans."""

    def __init__(self) -> None:
        pass

    def _get_registry(self) -> Any:
        try:
            from SYSTEM.registries.agent_registry import AgentRegistry
            return AgentRegistry()
        except Exception:
            return None

    def evaluate_plan(
        self,
        plan: dict[str, Any],
        strategy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Performs comprehensive pre-execution validation on a plan."""
        strat = strategy or strategy_manager.get_active_strategy()
        criteria = strat.get("acceptance_criteria", {})
        subtasks = plan.get("subtasks", [])

        errors: list[str] = []
        warnings: list[str] = []
        execution_order: list[int] = []

        if not subtasks:
            errors.append("Plan contains no subtasks to execute.")
            return {
                "is_valid": False,
                "errors": errors,
                "warnings": warnings,
                "execution_order": [],
            }

        # 1. Dependency Graph & Cycle Detection
        adj: dict[int, list[int]] = collections.defaultdict(list)
        in_degree: dict[int, int] = collections.defaultdict(int)
        all_steps = set()

        for st in subtasks:
            step = st.get("step")
            if step is None:
                errors.append(f"Subtask {st.get('subtask_id', 'unknown')} is missing 'step' number.")
                continue
            all_steps.add(step)
            deps = st.get("dependencies", [])
            for dep in deps:
                adj[dep].append(step)
                in_degree[step] += 1

        # Check unknown dependencies
        for st in subtasks:
            for dep in st.get("dependencies", []):
                if dep not in all_steps:
                    errors.append(f"Subtask step {st.get('step')} depends on non-existent step {dep}.")

        # Topological sort (Kahn's algorithm)
        queue = collections.deque([s for s in all_steps if in_degree[s] == 0])
        sorted_steps: list[int] = []

        while queue:
            node = queue.popleft()
            sorted_steps.append(node)
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(sorted_steps) != len(all_steps):
            errors.append("Circular dependency detected in subtask execution plan.")
        else:
            execution_order = sorted_steps

        # 2. Agent Existence & Capability Verification
        registry = self._get_registry()
        for st in subtasks:
            agent_id = st.get("assigned_agent_id")
            if not agent_id:
                errors.append(f"Step {st.get('step')} has no assigned agent ID.")
            elif registry and not registry.get(agent_id):
                warnings.append(f"Assigned agent '{agent_id}' for step {st.get('step')} is not currently registered in AgentRegistry.")

        # 3. Prerequisite Readiness
        if criteria.get("check_prerequisites_prior_to_delegation", True):
            for st in subtasks:
                action = st.get("action", "").lower()
                agent_id = (st.get("assigned_agent_id") or "").lower()
                if "render" in action or "render" in agent_id or "audio" in action or "audio" in agent_id:
                    # Check for ffmpeg/ffprobe binary availability
                    has_ffmpeg = shutil.which("ffmpeg") is not None
                    has_ffprobe = shutil.which("ffprobe") is not None
                    if not has_ffmpeg or not has_ffprobe:
                        warnings.append("System media tools (ffmpeg/ffprobe) not discovered in PATH for media subtasks.")

        is_valid = len(errors) == 0

        return {
            "is_valid": is_valid,
            "errors": errors,
            "warnings": warnings,
            "execution_order": execution_order,
            "acceptance_criteria_checked": criteria,
        }


plan_evaluator = PlanEvaluator()
