"""Learning Scheduler for Main Architecture Agent.

Coordinates the continuous self-learning loop:
- Post-task triggers and threshold monitoring
- Feedback-driven and failure-driven early triggers
- Reflection, proposal generation, benchmark verification
- Autonomous activation for low-risk improvements
- Mandatory approval (decided by the LLM approval review) for consequential/high-risk improvements
"""
from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from .experience_collector import ExperienceCollector, ExperienceRecord, experience_collector
from .improvement_proposals import ImprovementProposal, ImprovementProposalEngine, proposal_engine
from .reflection_engine import ReflectionEngine, ReflectionReport, reflection_engine
from .strategy_manager import StrategyManager, strategy_manager

logger = logging.getLogger("main_architecture_agent.scheduler")
_SCHEDULER_LOCK = threading.Lock()


class LearningScheduler:
    """Coordinates lifecycle triggers and autonomous learning loops."""

    def __init__(
        self,
        collector: ExperienceCollector | None = None,
        reflection: ReflectionEngine | None = None,
        proposals: ImprovementProposalEngine | None = None,
        strategies: StrategyManager | None = None,
        evaluator: Any | None = None,
    ) -> None:
        self.collector = collector or experience_collector
        self.reflection = reflection or reflection_engine
        if collector and getattr(self.reflection, "_collector", None) is None:
            self.reflection._collector = self.collector
        self.proposals = proposals or proposal_engine
        self.strategies = strategies or strategy_manager
        self._evaluator = evaluator
        self._lock = _SCHEDULER_LOCK

    @property
    def evaluator(self) -> Any:
        if self._evaluator is None:
            from ..evaluations.evaluation_runner import evaluation_runner
            self._evaluator = evaluation_runner
        return self._evaluator

    def trigger_post_task(self, experience: ExperienceRecord) -> dict[str, Any] | None:
        """Evaluates whether recent task experience warrants triggering a learning cycle."""
        policy = self.proposals.load_policy()
        if not policy.get("learning_enabled", True):
            return None

        unreflected = self.collector.get_unreflected_experiences()
        min_exp = policy.get("min_experiences_before_reflection", 2)

        if len(unreflected) >= min_exp:
            logger.info(f"Unreflected experiences count ({len(unreflected)}) >= threshold ({min_exp}); initiating learning cycle.")
            return self.run_learning_cycle()
        return None

    def trigger_on_feedback(self, experience: ExperienceRecord) -> dict[str, Any]:
        """Triggers an immediate learning cycle when explicit user feedback is recorded."""
        logger.info(f"User feedback recorded for task {experience.task_id}; running immediate learning cycle.")
        return self.run_learning_cycle(force=True, authorized_by="user_feedback_trigger")

    def trigger_on_failure(self, experience: ExperienceRecord) -> dict[str, Any]:
        """Triggers an immediate learning cycle on task failure."""
        logger.info(f"Task failure detected for task {experience.task_id}; running failure-driven learning cycle.")
        return self.run_learning_cycle(force=True, authorized_by="failure_trigger")

    def run_learning_cycle(
        self,
        force: bool = False,
        authorized_by: str = "autonomous_scheduler",
    ) -> dict[str, Any]:
        """Executes a full, bounded self-learning cycle."""
        with self._lock:
            cycle_id = f"cycle_{uuid.uuid4().hex[:8]}"
            policy = self.proposals.load_policy()
            if not policy.get("learning_enabled", True):
                return {
                    "cycle_id": cycle_id,
                    "status": "disabled",
                    "reason": "Self-learning disabled in policy.",
                }

            unreflected = self.collector.get_unreflected_experiences()
            min_exp = policy.get("min_experiences_before_reflection", 2)

            if len(unreflected) < min_exp and not force:
                return {
                    "cycle_id": cycle_id,
                    "status": "skipped",
                    "reason": f"Only {len(unreflected)} unreflected experiences, minimum required is {min_exp}.",
                }

            # Phase 1: Reflection
            reflection_report: ReflectionReport = self.reflection.reflect_on_experiences(
                experiences=unreflected,
                mark_processed=True,
            )

            if not reflection_report.lessons:
                return {
                    "cycle_id": cycle_id,
                    "status": "completed",
                    "experiences_reflected": len(unreflected),
                    "lessons_derived": 0,
                    "proposals_generated": 0,
                    "summary": "Reflection yielded no new validated lessons.",
                }

            # Phase 2: Improvement Proposals
            active_strat = self.strategies.get_active_strategy()
            proposals = self.proposals.generate_proposals(
                lessons=reflection_report.lessons,
                active_strategy=active_strat,
            )

            promoted_proposals = []
            staged_proposals = []
            rejected_proposals = []

            # Phase 3: Benchmark Evaluation & Safe Activation
            for prop in proposals:
                eval_res = self.evaluator.compare_and_evaluate_candidate(
                    candidate_strategy=prop.candidate_strategy,
                    baseline_strategy=active_strat,
                    tolerance=policy.get("evaluation_tolerance", 0.05),
                )

                if eval_res.get("is_promotable", False):
                    # High-risk proposals need an approval request, decided by the LLM approval review
                    if prop.approval_required or prop.risk_level == "high":
                        # Stage candidate file
                        cand_path = self.strategies.save_candidate(prop.candidate_strategy, candidate_id=prop.proposal_id)
                        self.proposals.update_proposal_status(prop.proposal_id, "benchmarked")

                        approval = self._request_approval(prop, eval_res)
                        decision = approval.status if approval else "unavailable"
                        if decision == "approved":
                            new_strat = self.strategies.activate_strategy(
                                candidate_input=prop.candidate_strategy,
                                authorized_by=f"approval:{approval.request_id}",
                                reason=f"Self-improvement {prop.proposal_id}: {prop.target_mutation_field} (approved by {approval.reviewer})",
                            )
                            self.proposals.update_proposal_status(prop.proposal_id, "promoted")
                            active_strat = new_strat
                            promoted_proposals.append({
                                "proposal_id": prop.proposal_id,
                                "new_version": new_strat.get("version"),
                                "target_field": prop.target_mutation_field,
                                "score_delta": eval_res.get("score_delta"),
                                "approval_request_id": approval.request_id,
                            })
                        elif decision == "rejected":
                            self.proposals.update_proposal_status(prop.proposal_id, "rejected", reason=f"approval rejected: {approval.decision_reason}")
                            rejected_proposals.append({
                                "proposal_id": prop.proposal_id,
                                "candidate_version": prop.proposed_version,
                                "reason": f"approval rejected by {approval.reviewer}: {approval.decision_reason}",
                            })
                        else:                                          # changes requested, or no approval could be made: the candidate stays staged and nothing is activated
                            staged_proposals.append({
                                "proposal_id": prop.proposal_id,
                                "candidate_version": prop.proposed_version,
                                "target_field": prop.target_mutation_field,
                                "risk_level": prop.risk_level,
                                "candidate_file": str(cand_path),
                                "approval_request_id": approval.request_id if approval else None,
                                "approval_status": decision,
                                "score_delta": eval_res.get("score_delta"),
                            })
                    else:
                        # Autonomous safe activation for low/medium-risk proposals
                        new_strat = self.strategies.activate_strategy(
                            candidate_input=prop.candidate_strategy,
                            authorized_by=authorized_by,
                            reason=f"Self-improvement {prop.proposal_id}: {prop.target_mutation_field}",
                        )
                        self.proposals.update_proposal_status(prop.proposal_id, "promoted")
                        active_strat = new_strat  # Update active reference for subsequent proposals
                        promoted_proposals.append({
                            "proposal_id": prop.proposal_id,
                            "new_version": new_strat.get("version"),
                            "target_field": prop.target_mutation_field,
                            "score_delta": eval_res.get("score_delta"),
                        })
                else:
                    rejection_reason = (
                        f"Failed benchmark evaluation. Candidate score: {eval_res.get('candidate_score')}, "
                        f"Baseline score: {eval_res.get('baseline_score')}, Hard gates: {eval_res.get('hard_gate_passed')}"
                    )
                    self.proposals.update_proposal_status(prop.proposal_id, "rejected", reason=rejection_reason)
                    rejected_proposals.append({
                        "proposal_id": prop.proposal_id,
                        "candidate_version": prop.proposed_version,
                        "reason": rejection_reason,
                    })

            cycle_result = {
                "cycle_id": cycle_id,
                "status": "completed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "experiences_reflected": len(unreflected),
                "lessons_derived": len(reflection_report.lessons),
                "proposals_generated": len(proposals),
                "promoted": promoted_proposals,
                "staged_for_approval": staged_proposals,
                "rejected": rejected_proposals,
                "active_strategy_version": self.strategies.get_active_strategy().get("version"),
            }

            logger.info(f"Learning cycle {cycle_id} finished: {len(promoted_proposals)} promoted, {len(staged_proposals)} staged, {len(rejected_proposals)} rejected.")
            return cycle_result

    def _request_approval(self, prop: ImprovementProposal, eval_res: dict[str, Any]):
        """Submits an approval request and returns it decided by the LLM approval review (None when the approval engine failed: nothing is activated)."""
        try:
            from SYSTEM.approvals.adapters.eval_adapter import submit_candidate_promotion_request
            req = submit_candidate_promotion_request(
                candidate_id=prop.proposal_id,
                candidate_type="architecture_strategy",
                target_id="active_strategy",
                title=f"Architecture Strategy v{prop.proposed_version} ({prop.target_mutation_field})",
                description=f"Automated improvement proposing mutation to {prop.target_mutation_field}. Score delta: {eval_res.get('score_delta')}",
                risk_level=prop.risk_level,
                evidence=[{
                    "proposal_id": prop.proposal_id,
                    "target_mutation_field": prop.target_mutation_field,
                    "diff": prop.diff,
                    "eval_res": {
                        "candidate_score": eval_res.get("candidate_score"),
                        "baseline_score": eval_res.get("baseline_score"),
                    },
                }],
                proposed_content=prop.diff,
            )
            return req
        except Exception as e:
            logger.warning(f"Could not request approval for {prop.proposal_id}: {e}")
            return None


learning_scheduler = LearningScheduler()
