"""Improvement Proposal Engine for Main Architecture Agent.

Generates governed, schema-validated Strategy Mutation proposals based on
validated lessons derived from real task execution experience.
"""
from __future__ import annotations

import copy
import json
import logging
import re
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from .reflection_engine import LessonItem

logger = logging.getLogger("main_architecture_agent.proposals")

PROPOSALS_FILE = Path(__file__).resolve().parent.parent / "history" / "proposals.jsonl"
POLICY_FILE = Path(__file__).resolve().parent.parent / "config" / "learning_policy.json"
_PROPOSAL_LOCK = threading.Lock()


@dataclass
class ImprovementProposal:
    proposal_id: str = field(default_factory=lambda: f"prop_{uuid.uuid4().hex[:10]}")
    current_version: str = "1.0.0"
    proposed_version: str = "1.1.0"
    target_mutation_field: str = ""
    diff: dict[str, Any] = field(default_factory=dict)
    candidate_strategy: dict[str, Any] = field(default_factory=dict)
    supporting_lessons: list[str] = field(default_factory=list)
    risk_level: Literal["low", "medium", "high"] = "low"
    approval_required: bool = False
    status: Literal["proposed", "benchmarked", "promoted", "rejected"] = "proposed"
    rejection_reason: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImprovementProposal:
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


class ImprovementProposalEngine:
    """Evaluates validated lessons and synthesizes candidate strategy proposals."""

    def __init__(
        self,
        proposals_file: Path | None = None,
        policy_file: Path | None = None,
    ) -> None:
        self.proposals_file = proposals_file or PROPOSALS_FILE
        self.proposals_file.parent.mkdir(parents=True, exist_ok=True)
        self.policy_file = policy_file or POLICY_FILE
        self._lock = _PROPOSAL_LOCK

    def load_policy(self) -> dict[str, Any]:
        if self.policy_file.exists():
            try:
                with open(self.policy_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to read learning policy: {e}")
        return {
            "learning_enabled": True,
            "confidence_threshold_proposal": 0.75,
            "max_proposals_per_cycle": 3,
            "allowed_strategy_mutation_fields": [
                "agent_routing_preferences",
                "fallback_routes",
                "task_decomposition_rules",
                "retry_policies",
                "acceptance_criteria",
            ],
            "require_human_approval_for": [
                "governance",
                "security",
                "high_risk",
                "consequential_routing",
            ],
            "loop_prevention_max_identical_proposals": 2,
        }

    def _get_historical_proposals(self) -> list[ImprovementProposal]:
        with self._lock:
            if not self.proposals_file.exists():
                return []
            records = []
            with open(self.proposals_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        records.append(ImprovementProposal.from_dict(json.loads(line)))
                    except Exception:
                        continue
            return records

    def _bump_version(self, current_ver: str, level: str = "patch") -> str:
        parts = current_ver.split(".")
        if len(parts) != 3:
            return f"{current_ver}-cand"
        try:
            major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
            if level == "minor":
                return f"{major}.{minor + 1}.0"
            return f"{major}.{minor}.{patch + 1}"
        except ValueError:
            return f"{current_ver}.1"

    def generate_proposals(
        self,
        lessons: list[LessonItem],
        active_strategy: dict[str, Any],
    ) -> list[ImprovementProposal]:
        """Translates validated lessons into concrete strategy mutation proposals."""
        policy = self.load_policy()
        if not policy.get("learning_enabled", True):
            logger.info("Self-learning is disabled in policy.")
            return []

        min_conf = policy.get("confidence_threshold_proposal", 0.75)
        allowed_fields = set(policy.get("allowed_strategy_mutation_fields", []))
        max_proposals = policy.get("max_proposals_per_cycle", 3)
        loop_limit = policy.get("loop_prevention_max_identical_proposals", 2)

        history = self._get_historical_proposals()
        proposals: list[ImprovementProposal] = []

        # Filter lessons by confidence and validation status
        actionable_lessons = [
            l for l in lessons
            if l.status == "validated" and l.confidence >= min_conf and l.target_mutation_field in allowed_fields
        ]

        for lesson in actionable_lessons:
            if len(proposals) >= max_proposals:
                break

            mutation_field = lesson.target_mutation_field
            suggested = lesson.suggested_mutation
            if not suggested:
                continue

            # Loop prevention: check duplicate rejection count
            identical_rejections = [
                h for h in history
                if h.target_mutation_field == mutation_field
                and h.diff == suggested
                and h.status == "rejected"
            ]
            if len(identical_rejections) >= loop_limit:
                logger.info(
                    f"Skipping proposal for lesson {lesson.lesson_id}: "
                    f"Identical mutation was rejected {len(identical_rejections)} times."
                )
                continue

            # Clone active strategy and apply the declarative mutation
            candidate_strat = copy.deepcopy(active_strategy)
            current_ver = candidate_strat.get("version", "1.0.0")

            if mutation_field == "agent_routing_preferences":
                # Ensure the field is a dictionary
                prefs = candidate_strat.setdefault("agent_routing_preferences", {})
                for k, v in suggested.items():
                    if isinstance(v, list):
                        prefs[k] = v
                    elif isinstance(v, str):
                        prefs[k] = [v]
                risk = "medium"
                ver_bump = "patch"
                requires_approval = False

            elif mutation_field == "fallback_routes":
                fallbacks = candidate_strat.setdefault("fallback_routes", {})
                fallbacks.update(suggested)
                risk = "low"
                ver_bump = "patch"
                requires_approval = False

            elif mutation_field == "retry_policies":
                retry_p = candidate_strat.setdefault("retry_policies", {})
                retry_p.update(suggested)
                risk = "low"
                ver_bump = "patch"
                requires_approval = False

            elif mutation_field == "task_decomposition_rules":
                decomps = candidate_strat.setdefault("task_decomposition_rules", {})
                decomps.update(suggested)
                risk = "high"
                ver_bump = "minor"
                requires_approval = True

            elif mutation_field == "acceptance_criteria":
                crit = candidate_strat.setdefault("acceptance_criteria", {})
                crit.update(suggested)
                risk = "high"
                ver_bump = "minor"
                requires_approval = True
            else:
                continue

            proposed_ver = self._bump_version(current_ver, ver_bump)
            candidate_strat["version"] = proposed_ver
            candidate_strat["updated_at"] = datetime.now(timezone.utc).isoformat()
            candidate_strat["parent_version"] = current_ver

            proposal = ImprovementProposal(
                current_version=current_ver,
                proposed_version=proposed_ver,
                target_mutation_field=mutation_field,
                diff=suggested,
                candidate_strategy=candidate_strat,
                supporting_lessons=[lesson.lesson_id],
                risk_level=risk,
                approval_required=requires_approval,
                status="proposed",
                metadata={"lesson_description": lesson.description, "confidence": lesson.confidence},
            )

            self.save_proposal(proposal)
            proposals.append(proposal)

        return proposals

    def save_proposal(self, proposal: ImprovementProposal) -> None:
        """Appends a proposal record atomically to proposals.jsonl."""
        with self._lock:
            with open(self.proposals_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(proposal.to_dict()) + "\n")

    def get_proposals(self, status: str | None = None) -> list[ImprovementProposal]:
        """Returns proposals matching the requested status."""
        history = self._get_historical_proposals()
        if status:
            return [p for p in history if p.status == status]
        return history

    def update_proposal_status(
        self,
        proposal_id: str,
        new_status: Literal["proposed", "benchmarked", "promoted", "rejected"],
        reason: str | None = None,
    ) -> bool:
        """Updates proposal status in persistent storage."""
        with self._lock:
            if not self.proposals_file.exists():
                return False
            records = []
            updated = False
            with open(self.proposals_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        p_dict = json.loads(line)
                        if p_dict.get("proposal_id") == proposal_id:
                            p_dict["status"] = new_status
                            if reason:
                                p_dict["rejection_reason"] = reason
                            p_dict["updated_at"] = datetime.now(timezone.utc).isoformat()
                            updated = True
                        records.append(p_dict)
                    except Exception:
                        continue

            if updated:
                with open(self.proposals_file, "w", encoding="utf-8") as f:
                    for r in records:
                        f.write(json.dumps(r) + "\n")
            return updated


proposal_engine = ImprovementProposalEngine()
