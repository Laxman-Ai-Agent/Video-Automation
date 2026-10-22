"""Comprehensive verification test suite for Main Architecture Agent self-learning.

Covers:
1. Experience Collection & Secret Redaction
2. Reflection Engine & Pattern Derivation
3. Improvement Proposal Generation & Loop Prevention
4. Strategy Manager Atomic Promotion & Rollback
5. Planning Decomposition, Routing, and Cycle Detection
6. Benchmark Evaluation Suite & Hard Gate Enforcement
7. End-to-End Autonomous Learning Cycle
8. Agent Coordination & Feedback Triggers
"""
from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path
import pytest
from SYSTEM.core.resilience import sanitize_secrets

from SYSTEM.agents.main_architecture_agent.agent import MainArchitectureAgent
from SYSTEM.agents.main_architecture_agent.evaluations.evaluation_runner import (
    EvaluationRunner,
    evaluation_runner,
)
from SYSTEM.agents.main_architecture_agent.learning.experience_collector import (
    ExperienceCollector,
    ExperienceRecord,
)
from SYSTEM.agents.main_architecture_agent.learning.improvement_proposals import (
    ImprovementProposal,
    ImprovementProposalEngine,
)
from SYSTEM.agents.main_architecture_agent.learning.learning_scheduler import (
    LearningScheduler,
)
from SYSTEM.agents.main_architecture_agent.learning.reflection_engine import (
    LessonItem,
    ReflectionEngine,
)
from SYSTEM.agents.main_architecture_agent.learning.strategy_manager import (
    SAFE_BASELINE_STRATEGY,
    StrategyManager,
    calculate_strategy_hash,
)
from SYSTEM.agents.main_architecture_agent.planning.agent_router import AgentRouter
from SYSTEM.agents.main_architecture_agent.planning.plan_evaluator import PlanEvaluator
from SYSTEM.agents.main_architecture_agent.planning.task_decomposer import TaskDecomposer
from SYSTEM.agents.shared.contracts import AgentRequest


# ----------------------------------------------------------------------
# 1. Experience Collector & Secret Redaction Tests
# ----------------------------------------------------------------------

def test_secret_redaction():
    text_with_keys = (
        "Got sk-1234567890abcdef1234567890 and token AIzaSyD35charLongGoogleSecretKey123456789 "
        "and ghp_123456789012345678901234567890123456 Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6 "
        'and {"api_key": "super_secret_val", "pin": "8888"}'
    )
    redacted = sanitize_secrets(text_with_keys)
    assert "sk-" not in redacted
    assert "AIzaSy" not in redacted
    assert "ghp_" not in redacted
    assert "super_secret_val" not in redacted
    assert "[REDACTED" in redacted


def test_experience_collector_deduplication_and_query(tmp_path: Path):
    storage = tmp_path / "exp.jsonl"
    collector = ExperienceCollector(storage_path=storage)

    exp1 = ExperienceRecord(task_id="t1", goal="Goal 1 with sk-secretkey1234567890123456", status="succeeded")
    collector.record_task_experience(exp1)

    # Second record with same task_id should be ignored (deduplicated)
    exp1_dup = ExperienceRecord(task_id="t1", goal="Duplicate Goal", status="failed")
    collector.record_task_experience(exp1_dup)

    all_exps = collector.query_experiences()
    assert len(all_exps) == 1
    assert all_exps[0].task_id == "t1"
    assert "sk-secretkey" not in all_exps[0].goal  # Secret was redacted

    # Add second unique experience
    exp2 = ExperienceRecord(task_id="t2", goal="Goal 2", status="failed", selected_agents=["motion_planning"])
    collector.record_task_experience(exp2)

    assert len(collector.query_experiences()) == 2
    failed_only = collector.query_experiences(status="failed")
    assert len(failed_only) == 1
    assert failed_only[0].task_id == "t2"


def test_experience_feedback_recording(tmp_path: Path):
    storage = tmp_path / "exp.jsonl"
    collector = ExperienceCollector(storage_path=storage)

    collector.record_task_experience(ExperienceRecord(task_id="task_fb_1", goal="Render video", status="succeeded"))
    success = collector.record_user_feedback("task_fb_1", {"rating": 5, "comment": "Great pacing"})
    assert success is True

    record = collector.query_experiences(limit=1)[0]
    assert record.user_feedback is not None
    assert record.user_feedback["rating"] == 5


# ----------------------------------------------------------------------
# 2. Reflection Engine Tests
# ----------------------------------------------------------------------

def test_reflection_engine_routing_failures():
    engine = ReflectionEngine(min_sample_for_validation=2)

    # Simulate 2 failures for an agent with a known fallback
    exps = [
        ExperienceRecord(
            task_id=f"f_{i}",
            goal="Select motion template",
            status="failed",
            selected_agents=["motion_template_selection"],
            error_detail="Template not found",
        )
        for i in range(2)
    ]

    report = engine.reflect_on_experiences(experiences=exps, mark_processed=False)
    assert report.analyzed_experience_count == 2
    assert len(report.lessons) >= 1

    routing_lesson = next((l for l in report.lessons if l.lesson_type == "routing_failure"), None)
    assert routing_lesson is not None
    assert routing_lesson.status == "validated"
    assert routing_lesson.confidence >= 0.8
    assert routing_lesson.target_mutation_field in ("fallback_routes", "agent_routing_preferences")
    assert "motion_template_selection" in routing_lesson.suggested_mutation


def test_reflection_engine_confidence_threshold():
    # If sample count < min_sample_for_validation, status remains 'hypothesis'
    engine = ReflectionEngine(min_sample_for_validation=3)
    exps = [
        ExperienceRecord(
            task_id="single_fail",
            goal="Single failure",
            status="failed",
            selected_agents=["audio_analyzer"],
        )
    ]
    report = engine.reflect_on_experiences(experiences=exps, mark_processed=False)
    lesson = report.lessons[0]
    assert lesson.status == "hypothesis"
    assert lesson.confidence < 0.75


# ----------------------------------------------------------------------
# 3. Improvement Proposal Engine Tests
# ----------------------------------------------------------------------

def test_improvement_proposal_generation(tmp_path: Path):
    prop_file = tmp_path / "proposals.jsonl"
    engine = ImprovementProposalEngine(proposals_file=prop_file)

    lesson = LessonItem(
        lesson_type="routing_failure",
        description="Reroute motion_template_selection to motion_planning",
        confidence=0.85,
        status="validated",
        target_mutation_field="fallback_routes",
        suggested_mutation={"motion_template_selection": "motion_planning"},
    )

    base_strategy = copy.deepcopy(SAFE_BASELINE_STRATEGY)
    proposals = engine.generate_proposals([lesson], base_strategy)

    assert len(proposals) == 1
    p = proposals[0]
    assert p.target_mutation_field == "fallback_routes"
    assert p.candidate_strategy["fallback_routes"]["motion_template_selection"] == "motion_planning"
    assert p.proposed_version == "1.0.1"
    assert p.status == "proposed"


def test_improvement_proposal_loop_prevention(tmp_path: Path):
    prop_file = tmp_path / "proposals.jsonl"
    engine = ImprovementProposalEngine(proposals_file=prop_file)

    lesson = LessonItem(
        lesson_type="routing_failure",
        description="Repeated rejected mutation",
        confidence=0.9,
        status="validated",
        target_mutation_field="fallback_routes",
        suggested_mutation={"bad_action": "bad_agent"},
    )

    # Pre-populate history with 2 rejections
    for i in range(2):
        rejected_prop = ImprovementProposal(
            target_mutation_field="fallback_routes",
            diff={"bad_action": "bad_agent"},
            status="rejected",
            rejection_reason="Benchmark regression",
        )
        engine.save_proposal(rejected_prop)

    base_strategy = copy.deepcopy(SAFE_BASELINE_STRATEGY)
    proposals = engine.generate_proposals([lesson], base_strategy)
    # Loop prevention should prevent regenerating this proposal
    assert len(proposals) == 0


# ----------------------------------------------------------------------
# 4. Strategy Manager Tests
# ----------------------------------------------------------------------

def test_strategy_manager_lifecycle(tmp_path: Path):
    active_f = tmp_path / "active" / "active_strategy.json"
    cand_dir = tmp_path / "candidates"
    arch_dir = tmp_path / "archive"

    mgr = StrategyManager(active_file=active_f, candidates_dir=cand_dir, archive_dir=arch_dir)

    # 1. Active strategy exists and matches baseline
    active = mgr.get_active_strategy()
    assert active["version"] == "1.0.0"
    base_hash = mgr.get_active_strategy_hash()
    assert len(base_hash) == 64

    # 2. Stage candidate
    candidate = copy.deepcopy(active)
    candidate["version"] = "1.1.0"
    candidate["fallback_routes"]["test_key"] = "test_target"
    cand_path = mgr.save_candidate(candidate)
    assert cand_path.exists()

    # 3. Promote candidate
    promoted = mgr.activate_strategy(cand_path, authorized_by="operator_test", reason="Passed test benchmark")
    assert promoted["version"] == "1.1.0"
    assert mgr.get_active_strategy()["version"] == "1.1.0"

    # Archived previous active strategy should exist
    archived = mgr.list_archived_strategies()
    assert len(archived) >= 1
    assert any(a["version"] == "1.0.0" for a in archived)

    # 4. Rollback to 1.0.0
    restored = mgr.rollback(target_version="1.0.0", authorized_by="operator_test", reason="Test rollback")
    assert restored["version"] == "1.0.0"
    assert mgr.get_active_strategy()["version"] == "1.0.0"


# ----------------------------------------------------------------------
# 5. Planning, Routing, and Evaluation Tests
# ----------------------------------------------------------------------

def test_task_decomposer_and_plan_evaluator():
    decomposer = TaskDecomposer()
    evaluator = PlanEvaluator()

    # Video plan decomposition
    plan = decomposer.decompose("Render video from speech narrative")
    assert plan["family"] == "video_generation"
    assert len(plan["subtasks"]) >= 2

    # Validation
    val = evaluator.evaluate_plan(plan)
    assert val["is_valid"] is True
    assert len(val["execution_order"]) >= 2


def test_plan_evaluator_cycle_detection():
    evaluator = PlanEvaluator()

    # Circular plan: step 1 depends on 2, step 2 depends on 1
    cyclic_plan = {
        "subtasks": [
            {"step": 1, "subtask_id": "s1", "assigned_agent_id": "capability_finder", "dependencies": [2]},
            {"step": 2, "subtask_id": "s2", "assigned_agent_id": "main_orchestrator", "dependencies": [1]},
        ]
    }
    val = evaluator.evaluate_plan(cyclic_plan)
    assert val["is_valid"] is False
    assert any("Circular dependency" in err for err in val["errors"])


def test_agent_router_fallbacks():
    router = AgentRouter()

    # Known fallback route: motion_template_selection -> motion_planning
    res = router.route_subtask({
        "action": "motion_template_selection",
        "title": "Select motion template",
        "assigned_agent_id": "motion_template_selection",
    })
    assert res["chosen_agent_id"] == "motion_planning"
    assert res["fallback_used"] is True

    # Unknown fallback
    res_unreg = router.route_subtask({
        "action": "unknown_action_xyz",
        "title": "Unknown action",
        "assigned_agent_id": "completely_unregistered_agent",
    })
    assert res_unreg["chosen_agent_id"] == "capability_finder"
    assert res_unreg["fallback_used"] is True


# ----------------------------------------------------------------------
# 6. Benchmark Evaluation Suite Tests
# ----------------------------------------------------------------------

def test_benchmark_evaluation_active_strategy():
    runner = EvaluationRunner()
    strat = copy.deepcopy(SAFE_BASELINE_STRATEGY)

    eval_result = runner.evaluate_strategy(strat)
    assert eval_result["hard_gate_passed"] is True
    assert eval_result["composite_score"] >= 0.8
    assert eval_result["planning_passed"] == eval_result["planning_total"]


def test_candidate_regression_rejection():
    runner = EvaluationRunner()
    baseline = copy.deepcopy(SAFE_BASELINE_STRATEGY)

    # Intentionally broken candidate strategy with emptied rules
    broken_candidate = copy.deepcopy(SAFE_BASELINE_STRATEGY)
    broken_candidate["version"] = "0.0.1"
    broken_candidate["task_decomposition_rules"] = {}  # Destroys planning
    broken_candidate["agent_routing_preferences"] = {}

    comp = runner.compare_and_evaluate_candidate(broken_candidate, baseline_strategy=baseline, tolerance=0.05)
    assert comp["is_promotable"] is False
    assert comp["recommendation"] == "reject"
    assert comp["score_delta"] < 0.0


# ----------------------------------------------------------------------
# 7. End-to-End Self-Learning Loop via LearningScheduler
# ----------------------------------------------------------------------

def test_end_to_end_learning_cycle(tmp_path: Path):
    storage = tmp_path / "exp.jsonl"
    collector = ExperienceCollector(storage_path=storage)
    reflection = ReflectionEngine(min_sample_for_validation=2)

    prop_file = tmp_path / "proposals.jsonl"
    proposals = ImprovementProposalEngine(proposals_file=prop_file)

    active_f = tmp_path / "active" / "active_strategy.json"
    cand_d = tmp_path / "candidates"
    arch_d = tmp_path / "archive"
    strategies = StrategyManager(active_file=active_f, candidates_dir=cand_d, archive_dir=arch_d)

    evaluator = EvaluationRunner()

    scheduler = LearningScheduler(
        collector=collector,
        reflection=reflection,
        proposals=proposals,
        strategies=strategies,
        evaluator=evaluator,
    )

    # Seed 2 experiences that fail on motion_template_selection
    for i in range(2):
        collector.record_task_experience(
            ExperienceRecord(
                task_id=f"seed_fail_{i}",
                goal="Template selection task",
                status="failed",
                selected_agents=["motion_template_selection"],
                error_detail="Template selection unsupported",
            )
        )

    # Run cycle
    cycle_res = scheduler.run_learning_cycle(force=True, authorized_by="test_harness")

    assert cycle_res["status"] == "completed"
    assert cycle_res["experiences_reflected"] == 2
    assert cycle_res["lessons_derived"] >= 1
    assert cycle_res["proposals_generated"] >= 1

    # Check that unreflected experiences are now reflected
    assert len(collector.get_unreflected_experiences()) == 0


# ----------------------------------------------------------------------
# 8. MainArchitectureAgent Execution Integration
# ----------------------------------------------------------------------

def test_main_architecture_agent_extended_actions(tmp_path: Path):
    agent = MainArchitectureAgent()

    # 1. Plan Action
    plan_req = AgentRequest(agent_id=agent.agent_id, parameters={"action": "plan", "goal": "Render full motion video"})
    res_plan = agent.execute(tmp_path, plan_req)
    assert res_plan.status == "succeeded"
    assert "plan" in res_plan.metadata
    assert "plan_evaluation" in res_plan.metadata
    assert res_plan.metadata["plan_evaluation"]["is_valid"] is True

    # 2. Strategy Action
    strat_req = AgentRequest(agent_id=agent.agent_id, parameters={"action": "strategy", "sub_action": "get_active"})
    res_strat = agent.execute(tmp_path, strat_req)
    assert res_strat.status == "succeeded"
    assert "strategy_hash" in res_strat.metadata

    # 3. Evaluate Strategy Action
    eval_req = AgentRequest(agent_id=agent.agent_id, parameters={"action": "evaluate_strategy"})
    res_eval = agent.execute(tmp_path, eval_req)
    assert res_eval.status == "succeeded"
    assert res_eval.metadata["composite_score"] >= 0.8

    # 4. Reflect Action
    ref_req = AgentRequest(agent_id=agent.agent_id, parameters={"action": "reflect"})
    res_ref = agent.execute(tmp_path, ref_req)
    assert res_ref.status == "succeeded"

    # 5. Proposals Action
    prop_req = AgentRequest(agent_id=agent.agent_id, parameters={"action": "proposals"})
    res_prop = agent.execute(tmp_path, prop_req)
    assert res_prop.status == "succeeded"
