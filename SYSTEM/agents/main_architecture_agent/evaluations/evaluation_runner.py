"""Evaluation Runner for Main Architecture Agent.

Runs deterministic planning and routing benchmark test cases against candidate
and active architecture strategies to prevent regressions and verify improvements.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ..planning.agent_router import AgentRouter
from ..planning.plan_evaluator import PlanEvaluator
from ..planning.task_decomposer import TaskDecomposer
from ..learning.strategy_manager import strategy_manager

logger = logging.getLogger("main_architecture_agent.evaluation_runner")

BASE_DIR = Path(__file__).resolve().parent
PLANNING_BENCHMARK_FILE = BASE_DIR / "planning_cases" / "planning_benchmark.json"
ROUTING_BENCHMARK_FILE = BASE_DIR / "routing_cases" / "routing_benchmark.json"


class EvaluationRunner:
    """Executes deterministic test suites against architecture strategies."""

    def __init__(
        self,
        planning_benchmark_file: Path | None = None,
        routing_benchmark_file: Path | None = None,
    ) -> None:
        self.planning_file = planning_benchmark_file or PLANNING_BENCHMARK_FILE
        self.routing_file = routing_benchmark_file or ROUTING_BENCHMARK_FILE
        self.decomposer = TaskDecomposer()
        self.router = AgentRouter()
        self.evaluator = PlanEvaluator()

    def _load_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading benchmark file {path}: {e}")
            return {}

    def evaluate_strategy(self, strategy: dict[str, Any]) -> dict[str, Any]:
        """Evaluates a strategy against planning and routing benchmark suites."""
        plan_bench = self._load_json(self.planning_file)
        route_bench = self._load_json(self.routing_file)

        plan_cases = plan_bench.get("cases", [])
        route_cases = route_bench.get("cases", [])

        # 1. Evaluate Planning Cases
        plan_passed = 0
        plan_details = []
        for case in plan_cases:
            goal = case.get("goal", "")
            exp_family = case.get("expected_family")
            min_subs = case.get("min_subtasks", 1)
            exp_agents = case.get("expected_agents", [])

            plan = self.decomposer.decompose(goal=goal, strategy=strategy)
            val = self.evaluator.evaluate_plan(plan, strategy=strategy)

            family_match = plan.get("family") == exp_family
            subs_count = len(plan.get("subtasks", [])) >= min_subs
            agent_ids = [st.get("assigned_agent_id") for st in plan.get("subtasks", [])]
            agents_match = all(ea in agent_ids for ea in exp_agents)
            valid_graph = val.get("is_valid", False)

            passed = family_match and subs_count and agents_match and valid_graph
            if passed:
                plan_passed += 1

            plan_details.append({
                "case_id": case.get("case_id"),
                "passed": passed,
                "family_match": family_match,
                "agents_match": agents_match,
                "valid_graph": valid_graph,
                "errors": val.get("errors", []),
            })

        plan_score = (plan_passed / len(plan_cases)) if plan_cases else 1.0

        # 2. Evaluate Routing Cases
        route_passed = 0
        route_details = []
        for case in route_cases:
            subtask = case.get("subtask", {})
            exp_agent = case.get("expected_agent")

            res = self.router.route_subtask(subtask, strategy=strategy)
            actual_agent = res.get("chosen_agent_id")
            passed = actual_agent == exp_agent

            if passed:
                route_passed += 1

            route_details.append({
                "case_id": case.get("case_id"),
                "passed": passed,
                "expected": exp_agent,
                "actual": actual_agent,
                "reason": res.get("routing_reason"),
            })

        route_score = (route_passed / len(route_cases)) if route_cases else 1.0

        composite_score = round(0.5 * plan_score + 0.5 * route_score, 4)
        hard_gate_passed = all(d["valid_graph"] for d in plan_details)

        return {
            "strategy_version": strategy.get("version", "unknown"),
            "composite_score": composite_score,
            "planning_score": round(plan_score, 4),
            "routing_score": round(route_score, 4),
            "planning_passed": plan_passed,
            "planning_total": len(plan_cases),
            "routing_passed": route_passed,
            "routing_total": len(route_cases),
            "hard_gate_passed": hard_gate_passed,
            "details": {
                "planning": plan_details,
                "routing": route_details,
            },
        }

    def compare_and_evaluate_candidate(
        self,
        candidate_strategy: dict[str, Any],
        baseline_strategy: dict[str, Any] | None = None,
        tolerance: float = 0.05,
    ) -> dict[str, Any]:
        """Compares a candidate strategy against the baseline or active strategy."""
        baseline = baseline_strategy or strategy_manager.get_active_strategy()
        base_eval = self.evaluate_strategy(baseline)
        cand_eval = self.evaluate_strategy(candidate_strategy)

        cand_score = cand_eval["composite_score"]
        base_score = base_eval["composite_score"]
        score_delta = round(cand_score - base_score, 4)

        hard_gates = cand_eval["hard_gate_passed"]
        no_regression = cand_score >= (base_score - tolerance)
        is_promotable = hard_gates and no_regression

        recommendation = "reject"
        if is_promotable:
            if score_delta >= 0.0:
                recommendation = "promote"
            else:
                recommendation = "stage_for_human_review"

        return {
            "is_promotable": is_promotable,
            "recommendation": recommendation,
            "candidate_score": cand_score,
            "baseline_score": base_score,
            "score_delta": score_delta,
            "tolerance": tolerance,
            "hard_gate_passed": hard_gates,
            "candidate_eval": cand_eval,
            "baseline_eval": base_eval,
        }


evaluation_runner = EvaluationRunner()
