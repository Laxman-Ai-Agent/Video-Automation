"""Offline Benchmark Evaluator for Capability Finder Lessons.

Evaluates candidate LessonProposals against a fixed 10-scenario benchmark suite (BENCHMARK_V1).
Computes recommendation accuracy, false-reuse rate, and false-creation rate.
Enforces non-regression gates before candidate lessons can be promoted.
"""
from __future__ import annotations

import copy
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from SYSTEM.registries.capability_registry import CapabilityRecord, capability_registry
from ..discovery.gap_analyzer import GapAnalyzer, GapAnalysisReport, gap_analyzer
from ..discovery.matcher import CapabilityMatch, CapabilityMatcher, capability_matcher
from ..discovery.requirement_parser import ParsedRequirement, RequirementParser, requirement_parser
from .lesson_generator import LessonProposal

BENCHMARK_VERSION = "v1.0.0"

BENCHMARK_V1: list[dict[str, Any]] = [
    {
        "scenario_id": "bench_01_speech_to_text",
        "description": "Speech to text transcription with word-level timestamps",
        "query": "Transcribe speech to text with timestamps",
        "extra_params": {"domain": "audio", "primary_capability": "speech_to_text"},
        "expected_action": "REUSE",
        "expected_delegate_id": "tool.faster_whisper.speech_to_text",
    },
    {
        "scenario_id": "bench_02_kinetic_typography",
        "description": "Kinetic typography layout and text animations",
        "query": "Kinetic typography layout and text animations",
        "extra_params": {"domain": "motion", "primary_capability": "kinetic_typography"},
        "expected_action": "REUSE",
        "expected_delegate_id": "skill.motion.kinetic_typography.typography_layout",
    },
    {
        "scenario_id": "bench_03_loudness_normalize",
        "description": "Media audio loudness normalization to EBU standards",
        "query": "Audio normalize loudness and volume",
        "extra_params": {"domain": "media", "primary_capability": "audio_normalize"},
        "expected_action": "REUSE",
        "expected_delegate_id": "tool.ffmpeg.audio_normalize",
    },
    {
        "scenario_id": "bench_04_spring_physics",
        "description": "Remotion spring physics and curve math interpolation",
        "query": "Remotion spring physics and curve math",
        "extra_params": {"domain": "motion", "primary_capability": "spring_physics"},
        "expected_action": "REUSE",
        "expected_delegate_id": "skill.motion.remotion_spring_curves.spring_physics",
    },
    {
        "scenario_id": "bench_05_safe_zone_validation",
        "description": "Layout safe zones and collision boundary detection",
        "query": "Layout safe zones and collision detection",
        "extra_params": {"domain": "validation", "primary_capability": "safe_zone_validation"},
        "expected_action": "REUSE",
        "expected_delegate_id": "skill.validation.layout_safe_zones.safe_zone_validation",
    },
    {
        "scenario_id": "bench_06_scene_segmentation",
        "description": "Video scene cut detection and segmentation",
        "query": "Split scenes and detect scene segmentation cuts",
        "extra_params": {"domain": "visual", "primary_capability": "scene_segmentation"},
        "expected_action": "REUSE",
        "expected_delegate_id": "agent.split_scenes.scene_segmentation",
    },
    {
        "scenario_id": "bench_07_custom_particle_glsl",
        "description": "Custom GLSL particle emitter shader (new skill)",
        "query": "Synthesize custom GLSL particle emitter shader",
        "extra_params": {"domain": "motion", "primary_capability": "particle_glsl_shader"},
        "expected_action": "CREATE_SKILL",
        "expected_delegate_id": "skill_factory",
    },
    {
        "scenario_id": "bench_08_3d_avatar_agent",
        "description": "Full 3D autonomous talking avatar system (new agent)",
        "query": "Create autonomous 3D talking avatar agent",
        "extra_params": {"domain": "avatar", "primary_capability": "avatar_agent_synthesis"},
        "expected_action": "CREATE_AGENT",
        "expected_delegate_id": "main_architecture_agent",
    },
    {
        "scenario_id": "bench_09_watermark_inpaint_skill",
        "description": "Video watermark removal inpainting filter (new skill)",
        "query": "Video watermark removal inpainting filter",
        "extra_params": {"domain": "visual", "primary_capability": "watermark_inpaint"},
        "expected_action": "CREATE_SKILL",
        "expected_delegate_id": "skill_factory",
    },
    {
        "scenario_id": "bench_10_neural_voice_agent",
        "description": "End-to-end neural voice cloning model (new agent)",
        "query": "Train full neural voice cloning pipeline",
        "extra_params": {"domain": "orchestrator", "primary_capability": "neural_voice_cloning"},
        "expected_action": "CREATE_AGENT",
        "expected_delegate_id": "main_architecture_agent",
    },
]


def resolve_delegate_compatibility(
    actual_delegate: str | None,
    expected_delegate: str | None,
    records: list[CapabilityRecord] | None = None,
) -> bool:
    """Authoritative registry-grounded delegate compatibility resolver.

    Resolves exact matches, direct alias mappings, or authoritative relationships
    between capability_id and source_id in CapabilityRegistry.
    """
    if not expected_delegate:
        return True
    if not actual_delegate:
        return False

    act_l = actual_delegate.strip().lower()
    exp_l = expected_delegate.strip().lower()

    if act_l == exp_l:
        return True

    # Check known canonical aliases (e.g., scene_segmentation vs split_scenes)
    known_aliases = {
        "split_scenes": "scene_segmentation",
        "scene_segmentation": "split_scenes",
    }
    if known_aliases.get(act_l) == exp_l or known_aliases.get(exp_l) == act_l:
        return True

    if records:
        for r in records:
            cap_id = r.capability_id.lower()
            src_id = r.source_id.lower()
            if (exp_l == cap_id and act_l == src_id) or (act_l == cap_id and exp_l == src_id):
                return True
            if act_l == src_id and (
                ("split_scenes" in exp_l or "scene_segmentation" in exp_l)
                and ("split_scenes" in src_id or "scene_segmentation" in src_id)
            ):
                return True

    return False


@dataclass
class EvaluationMetrics:
    recommendation_accuracy: float
    action_accuracy: float
    delegate_accuracy: float
    false_reuse_rate: float
    false_creation_rate: float
    total_cases: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommendation_accuracy": round(self.recommendation_accuracy, 4),
            "action_accuracy": round(self.action_accuracy, 4),
            "delegate_accuracy": round(self.delegate_accuracy, 4),
            "false_reuse_rate": round(self.false_reuse_rate, 4),
            "false_creation_rate": round(self.false_creation_rate, 4),
            "total_cases": self.total_cases,
        }


@dataclass
class LearningEvaluation:
    evaluation_id: str = field(default_factory=lambda: f"eval_{uuid.uuid4().hex[:12]}")
    proposal_id: str = ""
    benchmark_version: str = BENCHMARK_VERSION
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    baseline_metrics: dict[str, Any] = field(default_factory=dict)
    candidate_metrics: dict[str, Any] = field(default_factory=dict)
    passed_gate: bool = False
    accuracy_delta: float = 0.0
    action_accuracy_delta: float = 0.0
    delegate_accuracy_delta: float = 0.0
    has_regression: bool = False
    rejection_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id,
            "proposal_id": self.proposal_id,
            "benchmark_version": self.benchmark_version,
            "timestamp": self.timestamp,
            "baseline_metrics": self.baseline_metrics,
            "candidate_metrics": self.candidate_metrics,
            "accuracy_delta": round(self.accuracy_delta, 4),
            "action_accuracy_delta": round(self.action_accuracy_delta, 4),
            "delegate_accuracy_delta": round(self.delegate_accuracy_delta, 4),
            "has_regression": self.has_regression,
            "passed_gate": self.passed_gate,
            "rejection_reason": self.rejection_reason,
        }


class LessonEvaluator:
    """Evaluates candidate proposals on fixed benchmark suite to measure improvement and prevent regression."""

    def __init__(
        self,
        matcher: CapabilityMatcher | None = None,
        analyzer: GapAnalyzer | None = None,
        parser: RequirementParser | None = None,
    ) -> None:
        self.matcher = matcher or capability_matcher
        self.analyzer = analyzer or gap_analyzer
        self.parser = parser or requirement_parser

    def run_benchmark(
        self,
        proposal: LessonProposal | None = None,
    ) -> tuple[EvaluationMetrics, list[dict[str, Any]]]:
        """Runs the 10-scenario benchmark suite, optionally applying a candidate proposal."""
        if len(capability_registry.list_all()) == 0:
            capability_registry.sync_with_registries()
        records = capability_registry.list_all()

        correct_action_count = 0
        correct_delegate_count = 0
        correct_recommendation_count = 0
        false_reuse_count = 0
        total_create_cases = 0
        false_creation_count = 0
        total_reuse_cases = 0

        detailed_results: list[dict[str, Any]] = []

        for scenario in BENCHMARK_V1:
            q = scenario["query"]
            extra = copy.deepcopy(scenario["extra_params"])
            exp_action = scenario["expected_action"]
            exp_delegate = scenario.get("expected_delegate_id")

            # Apply candidate proposal transformations if provided
            if proposal:
                if proposal.rule_type == "synonym_expansion":
                    synonyms = proposal.rule_content.get("synonyms", {})
                    for term, expanded in synonyms.items():
                        if term.lower() in q.lower():
                            q = f"{q} {expanded}"
                elif proposal.rule_type == "routing_preference":
                    target_dom = proposal.rule_content.get("target_domain")
                    if target_dom and target_dom.lower() == extra.get("domain", "").lower():
                        extra["preferred_delegate"] = proposal.rule_content.get("preferred_delegate_id")

            req = self.parser.parse(q, extra, use_llm=False)
            matches = self.matcher.match(req, records)

            # Apply proposal score adjustments to matches
            if proposal and proposal.rule_type == "routing_preference":
                pref_id = proposal.rule_content.get("preferred_delegate_id")
                boost = float(proposal.rule_content.get("boost_score", 0.25))
                if pref_id:
                    for m in matches:
                        if pref_id.lower() in m.source_id.lower() or pref_id.lower() in m.capability_id.lower():
                            m.score = min(1.0, round(max(m.score + boost, 0.85), 3))
                            m.match_type = "exact"
                            m.matched_by.append("proposal_boost")
                    matches.sort(key=lambda x: x.score, reverse=True)

            report = self.analyzer.analyze(req, matches)
            actual_action = report.recommended_action
            actual_delegate = report.suggested_delegate_id

            is_action_correct = (actual_action == exp_action)
            is_delegate_correct = resolve_delegate_compatibility(actual_delegate, exp_delegate, records)
            is_correct = is_action_correct and is_delegate_correct

            if is_action_correct:
                correct_action_count += 1
            if is_delegate_correct:
                correct_delegate_count += 1
            if is_correct:
                correct_recommendation_count += 1

            if exp_action in ("CREATE_SKILL", "CREATE_AGENT"):
                total_create_cases += 1
                if actual_action == "REUSE":
                    false_reuse_count += 1

            if exp_action == "REUSE":
                total_reuse_cases += 1
                if actual_action in ("CREATE_SKILL", "CREATE_AGENT"):
                    false_creation_count += 1

            detailed_results.append({
                "scenario_id": scenario["scenario_id"],
                "expected_action": exp_action,
                "expected_delegate": exp_delegate,
                "actual_action": actual_action,
                "suggested_delegate": actual_delegate,
                "is_action_correct": is_action_correct,
                "is_delegate_correct": is_delegate_correct,
                "is_correct": is_correct,
            })

        total = len(BENCHMARK_V1)
        action_acc = correct_action_count / total if total > 0 else 0.0
        delegate_acc = correct_delegate_count / total if total > 0 else 0.0
        recommendation_acc = correct_recommendation_count / total if total > 0 else 0.0
        false_reuse_rate = false_reuse_count / total_create_cases if total_create_cases > 0 else 0.0
        false_creation_rate = false_creation_count / total_reuse_cases if total_reuse_cases > 0 else 0.0

        metrics = EvaluationMetrics(
            recommendation_accuracy=recommendation_acc,
            action_accuracy=action_acc,
            delegate_accuracy=delegate_acc,
            false_reuse_rate=false_reuse_rate,
            false_creation_rate=false_creation_rate,
            total_cases=total,
        )
        return metrics, detailed_results

    def evaluate_proposal(self, proposal: LessonProposal) -> LearningEvaluation:
        """Evaluates a candidate proposal against baseline and returns an evaluation report."""
        baseline_metrics, _ = self.run_benchmark(proposal=None)
        candidate_metrics, _ = self.run_benchmark(proposal=proposal)

        acc_delta = candidate_metrics.recommendation_accuracy - baseline_metrics.recommendation_accuracy
        action_delta = candidate_metrics.action_accuracy - baseline_metrics.action_accuracy
        delegate_delta = candidate_metrics.delegate_accuracy - baseline_metrics.delegate_accuracy
        reuse_delta = candidate_metrics.false_reuse_rate - baseline_metrics.false_reuse_rate
        creation_delta = candidate_metrics.false_creation_rate - baseline_metrics.false_creation_rate

        has_regression = False
        rejection_reasons: list[str] = []

        if acc_delta < 0.0:
            has_regression = True
            rejection_reasons.append(f"Recommendation accuracy decreased by {abs(acc_delta):.4f}")
        if action_delta < 0.0:
            has_regression = True
            rejection_reasons.append(f"Action accuracy decreased by {abs(action_delta):.4f}")
        if delegate_delta < 0.0:
            has_regression = True
            rejection_reasons.append(f"Delegate accuracy decreased by {abs(delegate_delta):.4f}")
        if reuse_delta > 0.0:
            has_regression = True
            rejection_reasons.append(f"False reuse rate increased by {reuse_delta:.4f}")
        if creation_delta > 0.0:
            has_regression = True
            rejection_reasons.append(f"False creation rate increased by {creation_delta:.4f}")

        passed_gate = not has_regression and (acc_delta >= 0.0)
        rejection_str = "; ".join(rejection_reasons) if rejection_reasons else None

        evaluation = LearningEvaluation(
            proposal_id=proposal.proposal_id,
            benchmark_version=BENCHMARK_VERSION,
            baseline_metrics=baseline_metrics.to_dict(),
            candidate_metrics=candidate_metrics.to_dict(),
            accuracy_delta=acc_delta,
            action_accuracy_delta=action_delta,
            delegate_accuracy_delta=delegate_delta,
            has_regression=has_regression,
            passed_gate=passed_gate,
            rejection_reason=rejection_str,
        )

        # Update proposal state
        proposal.evaluated_at = evaluation.timestamp
        proposal.evaluation_summary = evaluation.to_dict()
        if not passed_gate:
            proposal.status = "REJECTED"
        else:
            proposal.status = "EVALUATING"

        return evaluation


lesson_evaluator = LessonEvaluator()
