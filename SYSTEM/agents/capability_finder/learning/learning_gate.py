"""Learning Promotion Gate for Capability Finder.

Enforces strict verification and promotion policies before candidate lessons can become
active knowledge:
1. Strict JSON schema compliance.
2. Minimum evidence thresholds (>= 2 independent supporting cases, bounded counterexamples).
3. Non-regression offline benchmark evaluation verification.
4. Prompt injection and security policy checks.
5. Case provenance verification.
6. Explicit human/system authorization.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .case_collector import CaseCollector, case_collector
from .authorization import (
    ELEVATED_SECURITY_ROLES,
    TRUSTED_OPERATOR_ROLES,
    AuthenticatedOperator,
    SecurityAuthError,
    authenticate_operator,
)
from .feedback_processor import FeedbackProcessor
from .lesson_evaluator import LearningEvaluation
from .lesson_generator import LessonProposal

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"


class LearningGate:
    """Enforces multi-stage verification gates for lesson promotion."""

    def __init__(self, collector: CaseCollector | None = None) -> None:
        self.collector = collector or case_collector
        self._proposal_schema = self._load_schema("lesson_proposal.schema.json")
        self._evaluation_schema = self._load_schema("learning_evaluation.schema.json")

    def _load_schema(self, schema_name: str) -> dict[str, Any] | None:
        p = SCHEMA_DIR / schema_name
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def validate_schema(self, data: dict[str, Any], schema_type: str = "proposal") -> list[str]:
        """Validates dict against JSON schema if jsonschema is available, plus standard rules."""
        errors: list[str] = []
        schema = self._proposal_schema if schema_type == "proposal" else self._evaluation_schema

        try:
            import jsonschema
            if schema:
                validator = jsonschema.Draft202012Validator(schema)
                for err in validator.iter_errors(data):
                    errors.append(f"Schema violation at {err.json_path}: {err.message}")
                return errors
        except ImportError:
            pass

        # Fallback structural validation
        if schema_type == "proposal":
            required = [
                "proposal_id", "schema_version", "version", "title", "description",
                "observed_pattern", "affected_domain", "rule_type", "rule_content",
                "supporting_case_ids", "status"
            ]
            for field_name in required:
                if field_name not in data or data[field_name] is None:
                    errors.append(f"Missing required field: {field_name}")
            if not isinstance(data.get("supporting_case_ids"), list) or len(data.get("supporting_case_ids", [])) < 1:
                errors.append("supporting_case_ids must be a non-empty list")
        elif schema_type == "evaluation":
            required = [
                "evaluation_id", "proposal_id", "benchmark_version", "timestamp",
                "baseline_metrics", "candidate_metrics", "passed_gate"
            ]
            for field_name in required:
                if field_name not in data or data[field_name] is None:
                    errors.append(f"Missing required field: {field_name}")

        return errors

    def check_promotion_gates(
        self,
        proposal: LessonProposal,
        evaluation: LearningEvaluation | None,
        authorized_by: str | None = None,
        operator: AuthenticatedOperator | None = None,
        operator_id: str | None = None,
        role: str | None = None,
        approval_request_id: str | None = None,
        check_case_existence: bool = True,
        min_evidence: int = 2,
    ) -> tuple[bool, list[str]]:
        """Evaluates all gates required to promote a candidate proposal into active knowledge."""
        rejection_reasons: list[str] = []

        # Gate 1: Explicit authorization check and trusted operator verification (anti-spoofing)
        auth_op: AuthenticatedOperator | None = None
        try:
            auth_op = authenticate_operator(
                operator=operator,
                authorized_by=authorized_by,
                operator_id=operator_id,
                role=role,
                approval_request_id=approval_request_id,
                consume_approval=False,
            )
        except SecurityAuthError as e:
            rejection_reasons.append(str(e))
        except Exception as e:
            rejection_reasons.append(f"Authorization verification failed: {e}")

        # Gate 2: Schema validation
        schema_errs = self.validate_schema(proposal.to_dict(), schema_type="proposal")
        if schema_errs:
            rejection_reasons.extend(schema_errs)

        # Gate 3: Evidence threshold
        supports = proposal.supporting_case_ids or []
        counters = proposal.counterexample_case_ids or []
        if len(supports) < min_evidence:
            rejection_reasons.append(
                f"Insufficient evidence: proposal has {len(supports)} supporting cases; "
                f"minimum required is {min_evidence}."
            )
        if len(counters) > len(supports) // 2:
            rejection_reasons.append(
                f"Excessive counterexamples: {len(counters)} counterexamples exceeds "
                f"allowed threshold ({len(supports) // 2})."
            )

        # Gate 4: Security and safety checks
        text_to_check = f"{proposal.title} {proposal.description} {proposal.observed_pattern} {json.dumps(proposal.rule_content)}"
        for pattern in FeedbackProcessor.UNTRUSTED_INJECTION_PATTERNS:
            if pattern.search(text_to_check):
                rejection_reasons.append(f"Security policy violation: suspicious pattern detected ({pattern.pattern}).")

        if proposal.risk_level == "high":
            if auth_op is None or auth_op.role not in ELEVATED_SECURITY_ROLES:
                current_role = auth_op.role if auth_op else "unauthenticated"
                rejection_reasons.append(
                    f"High-risk proposals require elevated authorization ({', '.join(sorted(ELEVATED_SECURITY_ROLES))}); "
                    f"operator role is '{current_role}'."
                )

        # Gate 5: Provenance verification
        if check_case_existence:
            known_ids = {c.case_id for c in self.collector.list_cases()}
            missing_cases = [cid for cid in supports if cid not in known_ids]
            if missing_cases:
                rejection_reasons.append(
                    f"Provenance failure: supporting case IDs not found in experience memory: {missing_cases}."
                )

        # Gate 6: Offline benchmark evaluation verification
        if evaluation is None:
            rejection_reasons.append("Offline benchmark evaluation report is required before promotion.")
        else:
            eval_schema_errs = self.validate_schema(evaluation.to_dict(), schema_type="evaluation")
            if eval_schema_errs:
                rejection_reasons.extend(eval_schema_errs)

            if not evaluation.passed_gate:
                rejection_reasons.append(
                    f"Benchmark gate failed: {evaluation.rejection_reason or 'candidate failed evaluation'}"
                )
            if evaluation.has_regression:
                rejection_reasons.append("Benchmark regression detected: candidate proposal cannot be promoted.")
            if evaluation.accuracy_delta < 0.0:
                rejection_reasons.append(f"Negative accuracy delta ({evaluation.accuracy_delta:.4f}) detected.")

        passed = len(rejection_reasons) == 0
        return passed, rejection_reasons


learning_gate = LearningGate()
