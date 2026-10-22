"""Failure classification, bounded retry governance, and infinite loop prevention.

Implements:
1. Taxonomy-based failure classification (transient, defect, prerequisite missing, approval required, security denied, permanent).
2. Per-step attempt limits (default 3) and task-wide retry budgets (default 6).
3. Loop detection via failure fingerprinting to halt repeated identical failures.
4. Backoff timing calculations for transient errors.
5. Fail-closed security and approval protection (never retry security denials or bypass approvals).
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
from typing import Any

from .contracts import FailureCategory, StepExecutionRecord, TaskCheckpoint

logger = logging.getLogger("autonomous_execution.recovery_manager")


class RecoveryManager:
    """Manages failure classification, retry eligibility, and loop prevention."""

    def __init__(self, default_step_max_attempts: int = 3, default_task_max_retries: int = 6) -> None:
        self.default_step_max_attempts = default_step_max_attempts
        self.default_task_max_retries = default_task_max_retries
        self._fingerprint_history: dict[str, list[str]] = {}

    def classify_failure(self, error: str | Exception, context: dict[str, Any] | None = None) -> FailureCategory:
        """Classifies an error string or exception into an authoritative FailureCategory."""
        context = context or {}
        err_msg = str(error).lower()

        # Check explicit classification hints in context first
        if "category" in context:
            hint = str(context["category"]).lower()
            for cat in FailureCategory:
                if cat.value == hint:
                    return cat

        # 1. Security Denials
        if any(term in err_msg for term in [
            "security policy denied",
            "forbidden",
            "unauthorized",
            "access denied",
            "permission denied",
            "violates security boundary",
            "frozen file protection",
        ]):
            return FailureCategory.SECURITY_DENIED

        # 2. Approval Required
        if any(term in err_msg for term in [
            "approval required",
            "waiting for approval",
            "human approval needed",
            "approval gate pending",
            "approval_required",
        ]):
            return FailureCategory.APPROVAL_REQUIRED

        # 3. Timeout & Interrupted Execution
        if any(term in err_msg for term in [
            "timed out",
            "timeout",
            "execution deadline exceeded",
            "interrupted",
        ]):
            return FailureCategory.TIMEOUT

        # 4. Transient System / Resource Errors
        if any(term in err_msg for term in [
            "transient",
            "temporary failure",
            "connection reset",
            "rate limit",
            "resource temporarily unavailable",
            "resource locked",
            "lock acquisition failed",
            "busy",
            "service unavailable",
            "status code 503",
            "status code 429",
        ]):
            return FailureCategory.TRANSIENT

        # 5. Missing Prerequisites / Dependencies
        if any(term in err_msg for term in [
            "not found in registry",
            "missing prerequisite",
            "dependency not met",
            "file not found",
            "no such file or directory",
            "missing input",
            "artifact missing",
        ]):
            return FailureCategory.PREREQUISITE_MISSING

        # 6. Defect (Logic, Type, Syntax, Contract validation failure)
        if any(term in err_msg for term in [
            "syntaxerror",
            "typeerror",
            "valueerror",
            "assertionerror",
            "keyerror",
            "contract violation",
            "invalid schema",
            "unsupported action",
        ]):
            return FailureCategory.DEFECT

        # 7. Explicit Permanent
        if any(term in err_msg for term in [
            "permanent",
            "fatal",
            "unrecoverable",
            "irreversible conflict",
            "corrupted state",
        ]):
            return FailureCategory.PERMANENT

        # Default fallback for unclassified errors is DEFECT (treated carefully with bounded attempts)
        return FailureCategory.DEFECT

    def compute_fingerprint(self, step_id: str, category: FailureCategory, error_msg: str) -> str:
        """Computes a normalized SHA-256 fingerprint of the step failure.

        Strips variable IDs, timestamps, and memory addresses to recognize repeated identical errors.
        """
        # Normalize error message by stripping numbers, memory addresses, timestamps
        norm = re.sub(r"0x[0-9a-fA-F]+", "HEX", error_msg.strip().lower())
        norm = re.sub(r"\d{4}-\d{2}-\d{2}t\d{2}:\d{2}:\d{2}", "TIMESTAMP", norm)
        norm = re.sub(r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}", "UUID", norm)
        raw = f"{step_id}:{category.value}:{norm}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def is_retry_eligible(
        self,
        step: StepExecutionRecord,
        category: FailureCategory,
        checkpoint: TaskCheckpoint,
        error_msg: str = "",
    ) -> tuple[bool, str]:
        """Evaluates whether the failed step is eligible for retry under governance rules."""
        # Irreversible actions must never be re-executed blindly
        if step.is_irreversible:
            return False, f"Step '{step.step_id}' is marked irreversible; retrying could cause unintended duplicate side-effects."

        # Security denials and approval gates must NEVER be retried as transient failures
        if category == FailureCategory.SECURITY_DENIED:
            return False, f"Step '{step.step_id}' failed due to Security Policy Denial; retry forbidden."
        if category == FailureCategory.APPROVAL_REQUIRED:
            return False, f"Step '{step.step_id}' requires an approval; execution suspended in waiting_approval."
        if category == FailureCategory.PERMANENT:
            return False, f"Step '{step.step_id}' experienced a permanent failure; retry rejected."

        # Per-step attempt limit
        max_step_attempts = step.max_attempts or self.default_step_max_attempts
        if step.attempts >= max_step_attempts:
            return False, f"Step '{step.step_id}' exhausted retry attempt limit ({step.attempts}/{max_step_attempts})."

        # Task-wide retry budget
        max_task_retries = checkpoint.max_task_retries or self.default_task_max_retries
        if checkpoint.task_retry_count >= max_task_retries:
            return False, f"Task-wide retry budget exhausted ({checkpoint.task_retry_count}/{max_task_retries})."

        # Infinite Loop Detection: check if identical failure occurred twice consecutively
        fingerprint = self.compute_fingerprint(step.step_id, category, error_msg)
        history = self._fingerprint_history.setdefault(step.step_id, [])
        if len(history) >= 2 and history[-1] == fingerprint and history[-2] == fingerprint:
            return False, f"Loop prevention triggered for step '{step.step_id}': identical failure repeated {len(history)} times without state progress."

        history.append(fingerprint)
        return True, f"Eligible for bounded retry (attempt {step.attempts + 1}/{max_step_attempts})."

    def record_attempt(
        self,
        step: StepExecutionRecord,
        checkpoint: TaskCheckpoint,
        category: FailureCategory,
        error_msg: str,
    ) -> None:
        """Records a failed attempt into step history and increments attempt counters."""
        step.attempts += 1
        checkpoint.task_retry_count += 1
        record = {
            "attempt": step.attempts,
            "category": category.value,
            "error": error_msg,
            "timestamp": time.time(),
        }
        step.failure_history.append(record)
        step.error = error_msg
        step.failure_category = category.value

    def calculate_backoff(self, attempt: int, policy: dict[str, Any] | None = None) -> float:
        """Calculates bounded exponential backoff duration in seconds."""
        policy = policy or {}
        base = float(policy.get("backoff_base_seconds", 0.05))
        ceiling = float(policy.get("max_backoff_seconds", 1.0))
        # Bounded exponential backoff: base * 2^(attempt - 1)
        factor = 2 ** max(0, attempt - 1)
        delay = min(ceiling, base * factor)
        return delay

    def reset_loop_history(self, step_id: str | None = None) -> None:
        """Resets loop fingerprint history for a step or entire task."""
        if step_id:
            self._fingerprint_history.pop(step_id, None)
        else:
            self._fingerprint_history.clear()
