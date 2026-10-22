"""Task Decomposer for Main Architecture Agent.

Translates high-level system, workflow, and user requests into structured,
dependency-ordered execution plans using the active Architecture Strategy.
"""
from __future__ import annotations

import copy
import logging
import uuid
from typing import Any

from ..learning.strategy_manager import strategy_manager

logger = logging.getLogger("main_architecture_agent.task_decomposer")


class TaskDecomposer:
    """Decomposes goals into structured subtask graphs based on strategy rules."""

    def __init__(self) -> None:
        pass

    def decompose(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
        strategy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Decomposes a goal into an ordered sequence of subtasks."""
        context = context or {}
        strat = strategy or strategy_manager.get_active_strategy()
        rules = strat.get("task_decomposition_rules", {})
        strat_ver = strat.get("version", "1.0.0")

        goal_lower = goal.lower()
        matched_family = "generic_task"
        best_match_score = 0
        matched_subtasks_def: list[dict[str, Any]] = []

        # Find best matching task decomposition rule
        for family_name, rule_def in rules.items():
            keywords = rule_def.get("keywords", [])
            score = sum(1 for kw in keywords if kw.lower() in goal_lower)
            if score > best_match_score:
                best_match_score = score
                matched_family = family_name
                matched_subtasks_def = rule_def.get("subtasks", [])

        # If no rule matched, construct safe fallback decomposition
        if not matched_subtasks_def:
            matched_family = "fallback_discovery"
            matched_subtasks_def = [
                {
                    "step": 1,
                    "title": f"Discover capabilities and plan execution for: {goal[:50]}",
                    "assigned_agent_id": "capability_finder",
                    "action": "inspect_all",
                    "dependencies": [],
                }
            ]

        # Build concrete subtask items
        task_id = f"task_{uuid.uuid4().hex[:10]}"
        subtasks: list[dict[str, Any]] = []

        for item in matched_subtasks_def:
            step_num = item.get("step", len(subtasks) + 1)
            subtasks.append({
                "step": step_num,
                "subtask_id": f"{task_id}_step{step_num}",
                "title": item.get("title", f"Subtask {step_num}"),
                "assigned_agent_id": item.get("assigned_agent_id", "capability_finder"),
                "action": item.get("action", "execute"),
                "dependencies": copy.deepcopy(item.get("dependencies", [])),
                "parameters": copy.deepcopy(context),
                "status": "ready" if not item.get("dependencies") else "pending",
            })

        return {
            "task_id": task_id,
            "goal": goal,
            "family": matched_family,
            "strategy_version": strat_ver,
            "subtasks": subtasks,
            "context": context,
        }


task_decomposer = TaskDecomposer()
