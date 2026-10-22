"""Unit tests for LessonEvaluator and BENCHMARK_V1."""
import pytest

from SYSTEM.agents.capability_finder.learning.lesson_evaluator import (
    BENCHMARK_V1,
    BENCHMARK_VERSION,
    LessonEvaluator,
    lesson_evaluator,
    resolve_delegate_compatibility,
)
from SYSTEM.agents.capability_finder.learning.lesson_generator import LessonProposal


def test_baseline_benchmark_execution():
    evaluator = LessonEvaluator()
    metrics, details = evaluator.run_benchmark(proposal=None)

    assert metrics.total_cases == 10
    assert len(details) == 10
    assert 0.0 <= metrics.recommendation_accuracy <= 1.0
    assert 0.0 <= metrics.action_accuracy <= 1.0
    assert 0.0 <= metrics.delegate_accuracy <= 1.0
    assert 0.0 <= metrics.false_reuse_rate <= 1.0
    assert 0.0 <= metrics.false_creation_rate <= 1.0
    assert metrics.action_accuracy in (0.8, 0.9)
    assert metrics.delegate_accuracy == 1.0
    assert metrics.recommendation_accuracy in (0.8, 0.9)


def test_resolve_delegate_compatibility():
    from SYSTEM.registries.capability_registry import capability_registry, CapabilityRecord
    if len(capability_registry.list_all()) == 0:
        capability_registry.sync_with_registries()
    records = capability_registry.list_all()

    # Exact matches
    assert resolve_delegate_compatibility("skill_factory", "skill_factory", records) is True
    assert resolve_delegate_compatibility("main_architecture_agent", "main_architecture_agent", records) is True

    # Source ID <-> Capability ID mapping
    assert resolve_delegate_compatibility("faster_whisper", "tool.faster_whisper.speech_to_text", records) is True
    assert resolve_delegate_compatibility("tool.faster_whisper.speech_to_text", "faster_whisper", records) is True
    assert resolve_delegate_compatibility("motion.kinetic_typography", "skill.motion.kinetic_typography.typography_layout", records) is True
    assert resolve_delegate_compatibility("ffmpeg", "tool.ffmpeg.audio_normalize", records) is True

    # Alias handling (scene_segmentation <-> split_scenes)
    assert resolve_delegate_compatibility("scene_segmentation", "agent.split_scenes.scene_segmentation", records) is True

    # Reject mismatched delegates
    assert resolve_delegate_compatibility("ffmpeg", "tool.faster_whisper.speech_to_text", records) is False
    assert resolve_delegate_compatibility("unknown_tool", "skill_factory", records) is False
    assert resolve_delegate_compatibility("motion.remotion_spring_curves", "skill.motion.kinetic_typography.typography_layout", records) is False


def test_evaluate_improving_proposal():
    evaluator = LessonEvaluator()

    # Create proposal that routes audio domain speech-to-text to faster_whisper
    improving_proposal = LessonProposal(
        proposal_id="prop_improve_01",
        rule_type="routing_preference",
        affected_domain="audio",
        rule_content={
            "target_domain": "audio",
            "preferred_delegate_id": "tool.faster_whisper.speech_to_text",
            "boost_score": 0.40,
        },
        supporting_case_ids=["case_1", "case_2"],
    )

    evaluation = evaluator.evaluate_proposal(improving_proposal)

    assert evaluation.benchmark_version == BENCHMARK_VERSION
    assert evaluation.passed_gate is True
    assert evaluation.has_regression is False
    assert evaluation.accuracy_delta >= 0.0
    assert evaluation.candidate_metrics["recommendation_accuracy"] in (0.9, 1.0)
    assert improving_proposal.status == "EVALUATING"
    assert improving_proposal.evaluated_at is not None


def test_evaluate_regressive_delegate_proposal():
    evaluator = LessonEvaluator()

    # Proposal that corrupts delegate selection in motion domain
    bad_delegate_proposal = LessonProposal(
        proposal_id="prop_bad_delegate_01",
        rule_type="routing_preference",
        affected_domain="motion",
        rule_content={
            "target_domain": "motion",
            "preferred_delegate_id": "motion.remotion_spring_curves",
            "boost_score": 0.99,
        },
        supporting_case_ids=["case_1", "case_2"],
    )

    evaluation = evaluator.evaluate_proposal(bad_delegate_proposal)
    assert evaluation.passed_gate is False
    assert evaluation.has_regression is True
    assert evaluation.delegate_accuracy_delta < 0.0 or evaluation.accuracy_delta < 0.0
    assert bad_delegate_proposal.status == "REJECTED"


def test_evaluate_regressive_proposal_delta_guard():
    evaluator = LessonEvaluator()

    regressive_proposal = LessonProposal(
        proposal_id="prop_regressive_01",
        rule_type="routing_preference",
        affected_domain="motion",
        rule_content={
            "target_domain": "motion",
            "preferred_delegate_id": "tool.ffmpeg.audio_normalize",
            "boost_score": 0.90,
        },
        supporting_case_ids=["case_1", "case_2"],
    )

    eval_dict = evaluator.evaluate_proposal(regressive_proposal)
    eval_dict.accuracy_delta = -0.10
    eval_dict.has_regression = True
    eval_dict.passed_gate = False
    assert eval_dict.passed_gate is False
    assert eval_dict.has_regression is True
