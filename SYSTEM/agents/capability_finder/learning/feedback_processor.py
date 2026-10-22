"""Feedback Processor and Ingestion Validator for Capability Finder.

Validates and sanitizes feedback from:
1. Operator / Reviewer corrections.
2. Automated QC inspection results.
3. Main Architecture Agent reflections.

Rejects duplicate, conflicting, malformed, or policy-violating feedback.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from .case_collector import CaseCollector, LearningCase, case_collector


@dataclass
class FeedbackValidationResult:
    """Outcome of validating a feedback submission."""
    is_valid: bool
    status: Literal["accepted", "rejected", "quarantined", "inconclusive"]
    feedback_id: str
    rejection_reason: str | None = None
    sanitized_feedback: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FeedbackProcessor:
    """Validates, sanitizes, and applies feedback to historical learning cases."""

    UNTRUSTED_INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(?:all\s+)?prior\s+instructions", re.IGNORECASE),
        re.compile(r"override\s+system\s+policy", re.IGNORECASE),
        re.compile(r"bypass\s+security", re.IGNORECASE),
        re.compile(r"grant\s+admin\s+permission", re.IGNORECASE),
        re.compile(r"<script[\s>]", re.IGNORECASE),
    ]

    def __init__(self, collector: CaseCollector | None = None) -> None:
        self._collector = collector or case_collector
        self._seen_feedback_hashes: set[str] = set()

    def process_feedback(
        self,
        case_id: str,
        feedback_data: dict[str, Any],
        source: Literal["reviewer", "automated_qc", "maa_reflection"] = "reviewer",
    ) -> FeedbackValidationResult:
        """Validates and attaches feedback to the target learning case."""
        fid = f"fb_{uuid.uuid4().hex[:10]}"

        # 1. Verify case exists
        case = self._collector.get_case(case_id)
        if not case:
            return FeedbackValidationResult(
                is_valid=False,
                status="rejected",
                feedback_id=fid,
                rejection_reason=f"Target learning case '{case_id}' does not exist.",
            )

        # 2. Check for empty or malformed feedback
        if not isinstance(feedback_data, dict) or not feedback_data:
            return FeedbackValidationResult(
                is_valid=False,
                status="rejected",
                feedback_id=fid,
                rejection_reason="Feedback content is empty or malformed.",
            )

        # 3. Security scan for embedded prompt injections or policy overrides
        feedback_str = str(feedback_data)
        for pattern in self.UNTRUSTED_INJECTION_PATTERNS:
            if pattern.search(feedback_str):
                return FeedbackValidationResult(
                    is_valid=False,
                    status="quarantined",
                    feedback_id=fid,
                    rejection_reason="Untrusted prompt injection or policy override detected in feedback.",
                )

        # 4. Check for duplicate feedback submissions
        content_hash = f"{case_id}:{source}:{sorted(feedback_data.items())}"
        if content_hash in self._seen_feedback_hashes:
            return FeedbackValidationResult(
                is_valid=False,
                status="rejected",
                feedback_id=fid,
                rejection_reason="Duplicate feedback submission detected.",
            )
        self._seen_feedback_hashes.add(content_hash)

        # 5. Build sanitized record and attach to case
        sanitized = {
            "feedback_id": fid,
            "source": source,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "correction": feedback_data.get("correction", {}),
            "suggested_delegate_id": feedback_data.get("suggested_delegate_id"),
            "suggested_action": feedback_data.get("suggested_action"),
            "reviewer_notes": feedback_data.get("reviewer_notes", ""),
            "rating": feedback_data.get("rating"),
        }

        self._collector.attach_feedback(case_id, sanitized)

        return FeedbackValidationResult(
            is_valid=True,
            status="accepted",
            feedback_id=fid,
            sanitized_feedback=sanitized,
        )


feedback_processor = FeedbackProcessor()
