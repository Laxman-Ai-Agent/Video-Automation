"""Centralized Resilience, Error Classification, Circuit Breaking & Recovery Engine.

Provides:
1. Strict Error Taxonomy:
   TRANSIENT, TIMEOUT, RESOURCE, VALIDATION, DEPENDENCY, PERMANENT, SECURITY, CANCELLED, UNKNOWN.
2. Structured Failure Diagnostics with safe error codes, timestamps, and retry telemetry.
3. Secret-safe redaction across user-facing messages, diagnostics, and logs.
4. Bounded exponential backoff with jitter to prevent retry storms (upper bound: 3 retries).
5. Provider Circuit Breaker:
   CLOSED -> OPEN (after threshold failures) -> HALF_OPEN (after cooldown) -> CLOSED.
6. Deep Checkpoint Integrity & Path Confinement Verification (guards against traversal and corruption).
7. Safe Crash Reconciliation & Concurrency Guards for idempotent execution.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import re
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("system.resilience")

# ==============================================================================
# 1. ERROR TAXONOMY
# ==============================================================================

class ErrorCategory(str, Enum):
    """Authoritative taxonomy of execution failure modes for governed recovery."""
    TRANSIENT = "TRANSIENT"         # Temporary network, provider 429/503, lock contention
    TIMEOUT = "TIMEOUT"             # Operation or subprocess exceeded configured deadline
    RESOURCE = "RESOURCE"           # Disk full, out of memory, file lock, OS process limitation
    VALIDATION = "VALIDATION"       # Input schema invalid, malformed payload, contract violation
    DEPENDENCY = "DEPENDENCY"       # Missing upstream artifact or prerequisite dependency
    PERMANENT = "PERMANENT"         # Irrecoverable fault that cannot succeed without code/data change
    SECURITY = "SECURITY"           # Policy denial, forbidden operation, path traversal, auth failure
    CANCELLED = "CANCELLED"         # User or controller cooperatively requested cancellation
    UNKNOWN = "UNKNOWN"             # Insufficient telemetry to categorize reliably


# The one secret redactor: (kind, pattern, replacement), most specific first.
# Every marker starts with "[REDACTED_"; a value that already is a marker is never redacted again.
_SECRET_KEYS = r"api_key|apikey|client_secret|password|passwd|pwd|secret|token|pin"
_COLON_KEYS = r"api_key|apikey|client_secret|password|passwd|pwd|secret"   # "token: x" is common in parser errors
_NOT_MARKER = r"(?!\[REDACTED_)"
SECRET_RULES: list[tuple[str, re.Pattern, str]] = [
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----(?:[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----)?"), "[REDACTED_PRIVATE_KEY]"),
    ("json_secret", re.compile(rf"""(["'](?:{_SECRET_KEYS})["']\s*:\s*)(?:"[^"]+"|'[^']+'|\d+)""", re.IGNORECASE), r'\1"[REDACTED_SECRET]"'),
    ("aws_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), "[REDACTED_AWS_KEY]"),
    ("google_key", re.compile(r"AIza[0-9A-Za-z\-_]{20,}"), "[REDACTED_GOOGLE_KEY]"),
    ("github_token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"), "[REDACTED_GITHUB_TOKEN]"),
    ("api_key", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}"), "[REDACTED_API_KEY]"),
    ("bearer_token", re.compile(rf"\b(Bearer|Token)\s+{_NOT_MARKER}[A-Za-z0-9_\-\.=]{{20,}}", re.IGNORECASE), r"\1 [REDACTED_TOKEN]"),
    ("key_value_secret", re.compile(rf"""\b({_SECRET_KEYS})\s*=\s*{_NOT_MARKER}['"]?[^\s&;'"]+['"]?""", re.IGNORECASE), r"\1=[REDACTED_SECRET]"),
    ("key_value_secret", re.compile(rf"""\b({_COLON_KEYS})\s*:\s*{_NOT_MARKER}['"]?[^\s,;'"}}]+['"]?""", re.IGNORECASE), r"\1: [REDACTED_SECRET]"),
]

# Kinds that are credentials by their shape alone, not by a key name (`const pin = 3` in code is not a secret).
CREDENTIAL_KINDS = frozenset({"private_key", "aws_key", "google_key", "github_token", "api_key"})


def redact_secrets(text: str) -> tuple[str, list[str]]:
    """Removes API keys, tokens, private keys and password/secret values from text.
    Returns (redacted_text, kinds_redacted) — the kinds are SECRET_RULES names, each once, in rule order."""
    if not text:
        return "", []
    result = str(text)
    kinds: list[str] = []
    for kind, rx, repl in SECRET_RULES:
        result, n = rx.subn(repl, result)
        if n and kind not in kinds:
            kinds.append(kind)
    return result, kinds


def sanitize_secrets(text: str) -> str:
    """redact_secrets() without the kinds."""
    return redact_secrets(text)[0]


# ==============================================================================
# 2. STRUCTURED FAILURE DIAGNOSTIC
# ==============================================================================

@dataclass
class FailureDiagnostic:
    """Structured diagnostic payload for failure isolation, reporting, and learning."""
    project_id: str
    task_id: str
    agent_id: str
    stage_id: str
    category: str
    code: str
    message: str
    timestamp: str = ""
    recovery_permitted: bool = False
    attempt: int = 1
    retry_limit: int = 3
    checkpoint_ref: str | None = None
    current_task_state: str = "failed"
    recovery_outcome: str | None = None
    blocker_reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        self.message = sanitize_secrets(self.message)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ==============================================================================
# 3. ERROR CLASSIFICATION ENGINE
# ==============================================================================

def classify_error(
    error: Exception | str,
    context: dict[str, Any] | None = None,
) -> tuple[ErrorCategory, str, bool]:
    """Classifies an error into an authoritative ErrorCategory, safe code, and retry eligibility.

    Returns:
        (category: ErrorCategory, code: str, is_retry_eligible: bool)
    """
    context = context or {}
    err_str = str(error)
    err_lower = err_str.lower()

    # 1. User Cancellation
    if isinstance(error, (KeyboardInterrupt, InterruptedError)) or "cancel" in err_lower:
        return ErrorCategory.CANCELLED, "user_cancelled", False

    # 2. Security Denials (NEVER retryable!)
    if isinstance(error, PermissionError) or any(t in err_lower for t in [
        "security policy denied",
        "forbidden",
        "unauthorized",
        "permission denied",
        "frozen file protection",
        "path traversal",
        "security_policy",
        "human approval",
        "approval required",
        "approval sign-off",
        "approval gate",
        "401",
        "403",
    ]):
        return ErrorCategory.SECURITY, "security_policy_denied", False

    # 3. Timeouts (Retryable within budget if transient)
    if isinstance(error, TimeoutError) or any(t in err_lower for t in [
        "timed out",
        "timeout",
        "deadline exceeded",
        "execution timed out",
    ]):
        return ErrorCategory.TIMEOUT, "operation_timeout", True

    # 4. Resource Limitations (Retryable with backoff if temporary)
    if isinstance(error, (MemoryError, BlockingIOError)) or any(t in err_lower for t in [
        "no space left on device",
        "disk full",
        "resource temporarily unavailable",
        "lock acquisition failed",
        "lock busy",
        "too many open files",
        "out of memory",
    ]):
        return ErrorCategory.RESOURCE, "resource_exhausted", True

    # 5. Validation & Contract Violations (Deterministic, NOT retryable without input change)
    if isinstance(error, (ValueError, TypeError)) or any(t in err_lower for t in [
        "schema",
        "validation",
        "contract error",
        "contract violation",
        "schema validation failed",
        "validation error",
        "invalid request",
        "invalid argument",
        "spec hash mismatch",
        "bad request",
        "valueerror",
        "typeerror",
        "400",
        "422",
    ]):
        return ErrorCategory.VALIDATION, "contract_validation_error", False

    # 6. Missing Dependencies & Upstream Artifacts
    if isinstance(error, FileNotFoundError) or any(t in err_lower for t in [
        "file not found",
        "missing prerequisite",
        "dependency unavailable",
        "upstream stage",
        "artifact missing",
        "404",
    ]):
        return ErrorCategory.DEPENDENCY, "dependency_missing", False

    # 7. Transient Errors (Network, provider rate-limit 429/503)
    if isinstance(error, (ConnectionError, ConnectionResetError)) or any(t in err_lower for t in [
        "connection reset",
        "connectionreset",
        "connection refused",
        "rate limit",
        "too many requests",
        "429",
        "503",
        "service unavailable",
        "bad gateway",
        "502",
        "temporary failure",
        "transient",
    ]):
        return ErrorCategory.TRANSIENT, "transient_service_error", True

    # 8. Permanent Failures
    if any(t in err_lower for t in [
        "permanent",
        "corrupted state",
        "fatal error",
        "irreversible",
    ]):
        return ErrorCategory.PERMANENT, "permanent_failure", False

    # Fallback to UNKNOWN (treated conservatively)
    return ErrorCategory.UNKNOWN, "unclassified_error", True


# ==============================================================================
# 4. BOUNDED RETRY & BACKOFF WITH JITTER
# ==============================================================================

MAX_RETRY_LIMIT: int = 3


def calculate_backoff(
    attempt: int,
    base_seconds: float = 0.5,
    max_seconds: float = 4.0,
    jitter: bool = True,
) -> float:
    """Computes bounded exponential backoff with full jitter to avoid retry storms.

    Formula: min(max_seconds, base_seconds * 2^(attempt - 1)) * (0.5 + 0.5 * random)
    """
    attempt_clamped = max(1, attempt)
    raw_delay = min(max_seconds, base_seconds * (2 ** (attempt_clamped - 1)))
    if jitter:
        # Full jitter: random uniform between 0.5 * raw and 1.0 * raw
        return round(random.uniform(raw_delay * 0.5, raw_delay), 3)
    return round(raw_delay, 3)


def is_retry_permitted(
    category: ErrorCategory,
    current_attempt: int,
    max_retries: int = MAX_RETRY_LIMIT,
    is_cancelled: bool = False,
) -> tuple[bool, str]:
    """Strictly evaluates whether a retry is authorized under governance rules."""
    if is_cancelled:
        return False, "Task execution was cancelled by user; retry forbidden."
    if category in (ErrorCategory.SECURITY, ErrorCategory.CANCELLED):
        return False, f"Errors of category {category.value} cannot be retried."
    if category in (ErrorCategory.VALIDATION, ErrorCategory.PERMANENT):
        return False, f"Deterministic {category.value} error cannot succeed by retrying without input changes."
    if current_attempt >= max_retries:
        return False, f"Retry attempt limit reached ({current_attempt}/{max_retries})."
    return True, f"Eligible for bounded retry (attempt {current_attempt + 1}/{max_retries})."


# ==============================================================================
# 5. PROVIDER CIRCUIT BREAKER
# ==============================================================================

class CircuitBreakerOpenError(RuntimeError):
    """Raised when an external provider request is rejected because the circuit is open."""


class CircuitBreaker:
    """Bounded, thread-safe circuit breaker protecting external LLM/API providers.

    States:
    - CLOSED: Normal operation. Successes reset failure count.
    - OPEN: Tripped after failure_threshold consecutive failures. Rejects calls fast.
    - HALF_OPEN: Entered after cooldown_seconds. Permits a single probe call.
    """

    def __init__(self, failure_threshold: int = 3, cooldown_seconds: float = 20.0) -> None:
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._lock = threading.Lock()
        self._consecutive_failures: dict[str, int] = {}
        self._tripped_at: dict[str, float] = {}
        self._half_open: dict[str, bool] = {}

    def _key(self, provider: str, model: str | None = None) -> str:
        prov = str(provider).strip().lower()
        return f"{prov}:{model}" if model else prov

    def can_execute(self, provider: str, model: str | None = None) -> tuple[bool, str]:
        """Checks if a request is permitted to execute or blocked by open circuit."""
        key = self._key(provider, model)
        now = time.time()
        with self._lock:
            failures = self._consecutive_failures.get(key, 0)
            if failures >= self.failure_threshold:
                tripped = self._tripped_at.get(key, 0.0)
                elapsed = now - tripped
                if elapsed < self.cooldown_seconds:
                    remaining = round(self.cooldown_seconds - elapsed, 1)
                    return False, f"Circuit for '{key}' is OPEN ({failures} consecutive failures). Cooldown: {remaining}s remaining."
                # Cooldown expired -> enter HALF_OPEN
                self._half_open[key] = True
                return True, f"Circuit for '{key}' is HALF_OPEN (probing single request)."
            return True, f"Circuit for '{key}' is CLOSED (healthy)."

    def record_success(self, provider: str, model: str | None = None) -> None:
        """Records a successful request, resetting failures and closing circuit."""
        key = self._key(provider, model)
        with self._lock:
            self._consecutive_failures[key] = 0
            self._tripped_at.pop(key, None)
            self._half_open.pop(key, None)

    def record_failure(self, provider: str, model: str | None = None, error: str = "") -> None:
        """Records a request failure. If threshold reached, trips circuit to OPEN."""
        key = self._key(provider, model)
        now = time.time()
        with self._lock:
            count = self._consecutive_failures.get(key, 0) + 1
            self._consecutive_failures[key] = count
            if count >= self.failure_threshold:
                self._tripped_at[key] = now
                self._half_open.pop(key, None)
                logger.warning(
                    f"Circuit breaker TRIPPED to OPEN for provider '{key}' after {count} consecutive failures. "
                    f"Cooldown: {self.cooldown_seconds}s. Error: {sanitize_secrets(error)}"
                )

    def reset(self, provider: str | None = None) -> None:
        """Manually resets circuit breaker state for testing or operational recovery."""
        with self._lock:
            if provider:
                key = str(provider).strip().lower()
                self._consecutive_failures.pop(key, None)
                self._tripped_at.pop(key, None)
                self._half_open.pop(key, None)
            else:
                self._consecutive_failures.clear()
                self._tripped_at.clear()
                self._half_open.clear()

    def get_status(self, provider: str, model: str | None = None) -> dict[str, Any]:
        """Returns the current state and health metrics of the circuit breaker."""
        key = self._key(provider, model)
        now = time.time()
        with self._lock:
            failures = self._consecutive_failures.get(key, 0)
            tripped = self._tripped_at.get(key, 0.0)
            is_open = failures >= self.failure_threshold and (now - tripped < self.cooldown_seconds)
            is_half_open = self._half_open.get(key, False)
            return {
                "key": key,
                "state": "OPEN" if is_open else ("HALF_OPEN" if is_half_open else "CLOSED"),
                "consecutive_failures": failures,
                "tripped_at": tripped if is_open else None,
                "cooldown_remaining": max(0.0, round(self.cooldown_seconds - (now - tripped), 1)) if is_open else 0.0,
            }


# Global singleton instance
circuit_breaker = CircuitBreaker()


# ==============================================================================
# 6. DEEP CHECKPOINT INTEGRITY & PATH CONFINEMENT VALIDATION
# ==============================================================================

def verify_path_confinement(base_dir: Path, target_path: Path) -> None:
    """Guarantees that target_path strictly resolves within base_dir (guards against traversal)."""
    base_resolved = base_dir.resolve()
    target_resolved = target_path.resolve()
    try:
        target_resolved.relative_to(base_resolved)
    except ValueError:
        raise PermissionError(
            f"Security Violation: Path traversal attempt. Target '{target_resolved}' is outside permitted base '{base_resolved}'."
        )


def validate_checkpoint_deep(
    pdir: Path,
    stage_id: str,
    aspect: str = "16:9",
) -> tuple[bool, list[str], dict[str, Any]]:
    """Deeply validates checkpoint integrity, artifact existence, readability, and path confinement.

    Returns:
        (is_valid: bool, issues: list[str], metadata: dict[str, Any])
    """
    issues: list[str] = []
    metadata: dict[str, Any] = {}

    state_file = pdir / "pipeline_state.json"
    if not state_file.exists():
        return False, ["pipeline_state.json does not exist"], metadata

    try:
        raw_text = state_file.read_text(encoding="utf-8")
        if not raw_text.strip():
            return False, ["pipeline_state.json is empty (0 bytes)"], metadata
        state_data = json.loads(raw_text)
    except Exception as e:
        return False, [f"pipeline_state.json is corrupted: {e}"], metadata

    # 1. Project Identity Check
    stored_project = state_data.get("project_id")
    if stored_project and stored_project != pdir.name:
        issues.append(f"Project ID mismatch: stored '{stored_project}' != directory '{pdir.name}'")

    # 2. Stage Record Check
    stage_rec = state_data.get("stages", {}).get(stage_id)
    if not stage_rec:
        issues.append(f"No stage record found for '{stage_id}'")
        return False, issues, metadata

    status = stage_rec.get("status")
    metadata["status"] = status
    metadata["checkpoint_id"] = stage_rec.get("checkpoint_id")
    metadata["attempt"] = stage_rec.get("attempt", 0)

    # 3. Artifact Confinement & Existence
    artifacts = stage_rec.get("metadata", {}).get("artifacts", [])
    for art in artifacts:
        rel_path = art.get("path")
        if rel_path:
            art_file = pdir / rel_path
            try:
                verify_path_confinement(pdir, art_file)
            except PermissionError as pe:
                issues.append(str(pe))
                continue

            if not art_file.exists():
                issues.append(f"Referenced artifact missing on disk: {rel_path}")
            elif not os.access(art_file, os.R_OK):
                issues.append(f"Referenced artifact not readable: {rel_path}")
            else:
                # Verify non-empty
                if art_file.stat().st_size == 0:
                    issues.append(f"Referenced artifact is empty (0 bytes): {rel_path}")

    is_valid = len(issues) == 0
    return is_valid, issues, metadata


# ==============================================================================
# 7. CRASH RECONCILIATION & CONCURRENCY GUARDS
# ==============================================================================

_PROJECT_MUTEXES: dict[str, threading.Lock] = {}
_MUTEX_LOCK = threading.Lock()


def get_project_mutex(project_id: str) -> threading.Lock:
    """Returns a process-wide mutex serializing operations on a specific project."""
    with _MUTEX_LOCK:
        if project_id not in _PROJECT_MUTEXES:
            _PROJECT_MUTEXES[project_id] = threading.Lock()
        return _PROJECT_MUTEXES[project_id]


def get_project_store_lock(project_id: str, pdir: Path | None = None) -> Any:
    """Provides a durable cross-process file lock for multi-process environments."""
    try:
        from SYSTEM.agents.capability_finder.learning.store_lock import StoreLock
        from SYSTEM.core import config
        base = pdir or (config.PROJECTS_DIR / project_id)
        base.mkdir(parents=True, exist_ok=True)
        lock_file = base / ".project.lock"
        return StoreLock.get(lock_file)
    except Exception as e:
        logger.debug(f"Cross-process lock fallback to in-memory mutex: {e}")
        return get_project_mutex(project_id)


def reconcile_interrupted_run(
    pdir: Path,
    project_id: str,
    aspect: str = "16:9",
) -> dict[str, Any]:
    """Reconciles tasks left in an active/running state after unexpected process termination.

    Safely moves interrupted running stages to 'failed' with diagnostic evidence,
    while preserving approved gates and reusable completed checkpoints.
    """
    from SYSTEM.core import integrations
    pipeline_state = integrations.get("pipeline_state")
    if pipeline_state is None:          # no domain project keeps stage state here, so no stage can have been interrupted
        return {"project_id": project_id, "reconciled_stages": [], "can_resume": False, "earliest_invalid_stage": None, "reusable_count": 0}

    reconciled_stages: list[str] = []
    state = pipeline_state.load_pipeline_state(pdir)
    changed = False

    for sid, srec in state.stages.items():
        if srec.status == "running":
            # Running stage detected on startup -> was interrupted by crash
            srec.status = "failed"
            diag = FailureDiagnostic(
                project_id=project_id,
                task_id=f"crash_reconcile_{sid}",
                agent_id="main_orchestrator",
                stage_id=sid,
                category=ErrorCategory.RESOURCE.value,
                code="interrupted_by_crash",
                message=f"Stage '{sid}' execution was interrupted by process termination or server restart.",
                recovery_permitted=True,
                attempt=srec.attempt,
                retry_limit=3,
                current_task_state="failed",
            )
            srec.last_error = diag.to_dict()
            srec.completed_at = time.time()
            reconciled_stages.append(sid)
            changed = True

    if changed:
        state.revision += 1
        pipeline_state.save_pipeline_state(pdir, state)

    resume_plan = pipeline_state.resolve_resume_plan(pdir, aspect)

    return {
        "project_id": project_id,
        "reconciled_stages": reconciled_stages,
        "can_resume": resume_plan.get("can_resume", False),
        "earliest_invalid_stage": resume_plan.get("earliest_invalid_stage"),
        "reusable_count": resume_plan.get("reusable_count", 0),
    }


def record_recovery_experience(
    agent_id: str,
    stage_id: str,
    project_id: str,
    task_id: str,
    outcome: str,
    error_category: str | None = None,
    attempt: int = 1,
    details: dict[str, Any] | None = None,
) -> bool:
    """Safely logs a recovery experience to the agent's private memory partition.
    Fail-safe: never raises, never degrades pipeline if memory is unavailable.
    """
    try:
        from SYSTEM.memory.per_agent_store import PerAgentMemoryStore
        store = PerAgentMemoryStore()
        store.record_experience(
            agent_id=agent_id,
            task_type=f"recovery_{stage_id}",
            outcome=outcome,
            error_category=error_category,
            task_id=task_id,
            project_id=project_id,
            context={"stage_id": stage_id, "attempt": attempt, "details": details or {}},
            metrics={"attempt": attempt},
            reflection=f"Recovery execution for {stage_id} resulted in {outcome} on attempt {attempt}.",
        )
        return True
    except Exception as e:
        logger.debug(f"Recovery experience logging suppressed fail-safe: {e}")
        return False

