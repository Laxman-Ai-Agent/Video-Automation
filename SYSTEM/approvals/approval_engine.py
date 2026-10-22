"""Central Approval Engine (decided by an LLM review; no person).

Owns:
1. Approval request data model, lifecycle states, and transition rules.
2. Cryptographic action fingerprint binding (exact input SHA-256).
3. Thread-safe persistence in config/approvals_queue.json.
4. Append-only audit logging in config/approvals_audit.jsonl.
5. The decision itself: llm_decide asks the LLM reviewer (llm_reviewer.ask_reviewer) and records its verdict; nothing else approves.
6. Guard boundaries for single-use consumption and stale invalidation.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

from SYSTEM.core import config

logger = logging.getLogger("laxman_approval.engine")

ApprovalStatus = Literal[
    "pending",
    "approved",
    "rejected",
    "changes_requested",
    "stale",
    "expired",
    "consumed",
]

ApprovalRiskLevel = Literal["low", "medium", "high", "critical"]
ApprovalCategory = Literal["video_engine_agent", "system_subagent", "orchestrator"]

QUEUE_FILE = config.PROJECT_ROOT / "config" / "approvals_queue.json"
AUDIT_FILE = config.PROJECT_ROOT / "config" / "approvals_audit.jsonl"


class ApprovalEngineError(Exception):
    """Base exception for approval engine errors."""
    def __init__(self, message: str, code: str = "approval_error", status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class ApprovalNotFoundError(ApprovalEngineError):
    """Raised when an approval request ID does not exist."""
    def __init__(self, request_id: str) -> None:
        super().__init__(f"Approval request '{request_id}' not found", code="request_not_found", status_code=404)


class ApprovalGuardError(ApprovalEngineError):
    """Raised when a protected action cannot be consumed or executed."""
    def __init__(self, message: str, code: str = "approval_required", status_code: int = 409) -> None:
        super().__init__(message, code=code, status_code=status_code)


def canonical_json(data: Any) -> str:
    """Produces deterministic canonical JSON for hashing."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_action_fingerprint(action_type: str, target_id: str | None, payload: dict[str, Any]) -> str:
    """Computes a SHA-256 fingerprint binding the exact action, target, and payload."""
    content = {
        "action_type": action_type,
        "target_id": target_id or "",
        "payload": payload,
    }
    return hashlib.sha256(canonical_json(content).encode("utf-8")).hexdigest()


@dataclass
class ApprovalRequest:
    request_id: str
    idempotency_key: str
    created_at: str
    requester_agent_id: str
    category: ApprovalCategory
    action_type: str
    risk_level: ApprovalRiskLevel
    action_summary: str
    affected_files: list[str] = field(default_factory=list)
    action_fingerprint: str = ""
    upstream_evidence: dict[str, Any] = field(default_factory=dict)
    expected_outcomes: list[str] = field(default_factory=list)
    reversibility: Literal["reversible", "rerunnable", "irreversible"] = "rerunnable"
    rollback_plan: str = ""
    project_id: Optional[str] = None
    status: ApprovalStatus = "pending"
    decision: Optional[Literal["approved", "rejected", "changes_requested"]] = None
    reviewer: Optional[str] = None
    decision_reason: Optional[str] = None
    decision_at: Optional[str] = None
    expires_at: Optional[str] = None
    consumed_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ApprovalRequest:
        valid_keys = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)


class ApprovalEngine:
    """Authoritative state machine and persistence for Laxman Approvals."""

    def __init__(self, queue_file: Path = QUEUE_FILE, audit_file: Path = AUDIT_FILE) -> None:
        self._queue_file = queue_file
        self._audit_file = audit_file
        self._lock = threading.RLock()

    def _load_queue_unlocked(self) -> dict[str, ApprovalRequest]:
        if not self._queue_file.exists():
            return {}
        try:
            raw = json.loads(self._queue_file.read_text(encoding="utf-8"))
            return {item["request_id"]: ApprovalRequest.from_dict(item) for item in raw.get("requests", [])}
        except Exception as e:
            logger.error("Failed to read approvals queue: %s", e)
            return {}

    def _save_queue_unlocked(self, requests: dict[str, ApprovalRequest]) -> None:
        self._queue_file.parent.mkdir(parents=True, exist_ok=True)
        items = [r.to_dict() for r in requests.values()]
        payload = {
            "schema_version": "1.0",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(items),
            "requests": items,
        }
        tmp = self._queue_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self._queue_file)

    def _append_audit_event_unlocked(self, event_type: str, details: dict[str, Any]) -> None:
        """Appends an event to the append-only audit log with secret redaction."""
        self._audit_file.parent.mkdir(parents=True, exist_ok=True)
        sanitized = {}
        for k, v in details.items():
            if "pin" in k.lower() or "secret" in k.lower() or "salt" in k.lower():
                sanitized[k] = "***REDACTED***"
            else:
                sanitized[k] = v

        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            **sanitized,
        }
        try:
            with open(self._audit_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
        except Exception as e:
            logger.error("Failed to write approvals audit log: %s", e)
            raise ApprovalEngineError(
                "Critical: Failed to append approval audit record",
                code="audit_failure",
                status_code=500,
            ) from e

    def submit_request(
        self,
        requester_agent_id: str,
        category: ApprovalCategory,
        action_type: str,
        risk_level: ApprovalRiskLevel,
        action_summary: str,
        idempotency_key: str,
        payload_for_fingerprint: dict[str, Any],
        affected_files: list[str] | None = None,
        upstream_evidence: dict[str, Any] | None = None,
        expected_outcomes: list[str] | None = None,
        reversibility: Literal["reversible", "rerunnable", "irreversible"] = "rerunnable",
        rollback_plan: str = "",
        project_id: str | None = None,
        expires_in_hours: int = 24,
    ) -> ApprovalRequest:
        """Creates or returns an idempotent pending approval request."""
        fingerprint = compute_action_fingerprint(action_type, project_id, payload_for_fingerprint)

        with self._lock:
            queue = self._load_queue_unlocked()

            # Check idempotency
            for existing in queue.values():
                if existing.idempotency_key == idempotency_key:
                    if existing.status in ("pending", "approved"):
                        # If fingerprint changed, invalidate existing
                        if existing.action_fingerprint != fingerprint:
                            existing.status = "stale"
                            existing.decision_reason = "Upstream inputs changed"
                            self._append_audit_event_unlocked(
                                "approval_marked_stale",
                                {"request_id": existing.request_id, "reason": "Fingerprint change on idempotent submit"},
                            )
                        else:
                            return existing

            now = datetime.now(timezone.utc)
            request_id = f"appr_{now.strftime('%Y%m%d%H%M%S')}_{hashlib.sha256(idempotency_key.encode()).hexdigest()[:8]}"
            expires_at = datetime.fromtimestamp(now.timestamp() + (expires_in_hours * 3600), tz=timezone.utc).isoformat()

            req = ApprovalRequest(
                request_id=request_id,
                idempotency_key=idempotency_key,
                created_at=now.isoformat(),
                requester_agent_id=requester_agent_id,
                category=category,
                action_type=action_type,
                risk_level=risk_level,
                action_summary=action_summary,
                affected_files=affected_files or [],
                action_fingerprint=fingerprint,
                upstream_evidence=upstream_evidence or {},
                expected_outcomes=expected_outcomes or [],
                reversibility=reversibility,
                rollback_plan=rollback_plan,
                project_id=project_id,
                status="pending",
                expires_at=expires_at,
            )

            queue[request_id] = req
            self._save_queue_unlocked(queue)
            self._append_audit_event_unlocked(
                "approval_requested",
                {
                    "request_id": request_id,
                    "action_type": action_type,
                    "requester_agent_id": requester_agent_id,
                    "risk_level": risk_level,
                    "fingerprint": fingerprint,
                    "project_id": project_id,
                },
            )
            return req

    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """Retrieves a single request by ID."""
        with self._lock:
            queue = self._load_queue_unlocked()
            return queue.get(request_id)

    def list_requests(
        self,
        status: Optional[str] = None,
        category: Optional[str] = None,
        project_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[ApprovalRequest]:
        """Lists requests with pending items prioritized first, sorted by created_at desc."""
        with self._lock:
            queue = self._load_queue_unlocked()
            items = list(queue.values())

            if status:
                items = [r for r in items if r.status == status]
            if category:
                items = [r for r in items if r.category == category]
            if project_id:
                items = [r for r in items if r.project_id == project_id]

            # Priority sort: pending first, then newest first
            def sort_key(r: ApprovalRequest) -> tuple[int, str]:
                is_pending = 0 if r.status == "pending" else 1
                return is_pending, r.created_at

            items.sort(key=sort_key, reverse=False)
            return items[:limit]

    def decide(
        self,
        request_id: str,
        decision: Literal["approved", "rejected", "changes_requested"],
        reason: str | None = None,
        reviewer: str = "llm",
    ) -> ApprovalRequest:
        """Records a decision (`reviewer` says who made it; llm_decide is the only caller outside tests)."""
        with self._lock:
            queue = self._load_queue_unlocked()
            req = queue.get(request_id)
            if not req:
                raise ApprovalNotFoundError(request_id)

            if req.status not in ("pending", "changes_requested"):
                raise ApprovalEngineError(
                    f"Request is in terminal or non-decidable status: '{req.status}'",
                    code="invalid_request_state",
                    status_code=409,
                )

            now_iso = datetime.now(timezone.utc).isoformat()

            if decision == "approved":
                req.status = "approved"
                req.decision = "approved"
                req.reviewer = reviewer
                req.decision_reason = reason or f"Approved by {reviewer}"
                req.decision_at = now_iso

                self._save_queue_unlocked(queue)
                self._append_audit_event_unlocked(
                    "approval_granted",
                    {
                        "request_id": request_id,
                        "action_type": req.action_type,
                        "reviewer": reviewer,
                        "fingerprint": req.action_fingerprint,
                        "project_id": req.project_id,
                    },
                )
                return req

            elif decision == "rejected":
                if not reason or not reason.strip():
                    raise ApprovalEngineError("Rejection requires a non-empty reason", code="reason_required", status_code=422)

                req.status = "rejected"
                req.decision = "rejected"
                req.reviewer = reviewer
                req.decision_reason = reason.strip()
                req.decision_at = now_iso

                self._save_queue_unlocked(queue)
                self._append_audit_event_unlocked(
                    "approval_rejected",
                    {
                        "request_id": request_id,
                        "action_type": req.action_type,
                        "reviewer": reviewer,
                        "reason": req.decision_reason,
                        "project_id": req.project_id,
                    },
                )
                return req

            elif decision == "changes_requested":
                if not reason or not reason.strip():
                    raise ApprovalEngineError("Requesting changes requires structured feedback", code="reason_required", status_code=422)

                req.status = "changes_requested"
                req.decision = "changes_requested"
                req.reviewer = reviewer
                req.decision_reason = reason.strip()
                req.decision_at = now_iso

                self._save_queue_unlocked(queue)
                self._append_audit_event_unlocked(
                    "approval_changes_requested",
                    {
                        "request_id": request_id,
                        "action_type": req.action_type,
                        "reviewer": reviewer,
                        "feedback": req.decision_reason,
                        "project_id": req.project_id,
                    },
                )
                return req

            else:
                raise ApprovalEngineError(f"Unsupported decision: '{decision}'", code="invalid_decision", status_code=422)

    def llm_decide(self, request_id: str, timeout: int = 60) -> ApprovalRequest:
        """The LLM reviewer decides a pending request from what the request itself says (action, risk, evidence, files, outcomes, rollback).
        Only `passed` with score >= 0.80 and no blocker/error approves; `blocked` or `failed` rejects; anything else (needs_review, unavailable LLM) asks for changes.
        The verdict is recorded through decide() with the reviewer `llm:<provider>/<model>`."""
        from SYSTEM.policies import llm_reviewer
        req = self.get_request(request_id)
        if req is None:
            raise ApprovalNotFoundError(request_id)
        facts = {k: v for k, v in req.to_dict().items() if k in (
            "requester_agent_id", "category", "action_type", "risk_level", "action_summary", "affected_files", "upstream_evidence",
            "expected_outcomes", "reversibility", "rollback_plan", "project_id")}
        verdict = llm_reviewer.ask_reviewer(
            project_id=req.project_id or "system",
            stage_id="approval",
            agent_id=req.requester_agent_id,
            system_prompt=(
                "You are the approval reviewer of the Dark World Video Generation Agent. You decide, from the request alone, whether ONE consequential action may run. "
                "Nobody reviews after you. Judge ONLY from the facts given; never assume evidence that is not in them. Approve only when the evidence supports the action, its risk is "
                "proportionate to its reversibility and rollback plan, and nothing in it is missing, contradictory or unverifiable. "
                "Respond with ONLY a JSON object: {\"status\": \"passed\"|\"needs_review\"|\"blocked\", \"score\": 0.0-1.0, \"summary\": \"...\", "
                "\"findings\": [{\"severity\": \"blocker\"|\"error\"|\"warning\"|\"info\", \"category\": \"...\", \"message\": \"...\"}]}. "
                "status='passed' with score >= 0.85 approves; 'blocked' (with a blocker finding) rejects; 'needs_review' asks for changes and says what is missing."),
            user_prompt="### APPROVAL REQUEST\n" + json.dumps(facts, indent=2, ensure_ascii=False, default=str)[:12000],
            timeout=timeout,
            input_fingerprint=req.action_fingerprint,
        )
        reviewer = f"llm:{verdict.get('provider')}/{verdict.get('model')}"
        blockers = [f for f in verdict.get("findings", []) if f.get("severity") in ("blocker", "error")]
        why = (verdict.get("summary") or "no summary")[:400] + "".join(f"; {f.get('severity')}: {f.get('message')}" for f in blockers[:5])
        if verdict["status"] == "passed" and float(verdict.get("score") or 0) >= 0.80 and not blockers:
            return self.decide(request_id, "approved", why, reviewer=reviewer)
        if verdict["status"] in ("blocked", "failed") or blockers:
            return self.decide(request_id, "rejected", why, reviewer=reviewer)
        return self.decide(request_id, "changes_requested", why, reviewer=reviewer)

    def mark_stale(self, request_id: str, reason: str) -> ApprovalRequest:
        """Marks an approval request stale when upstream assets or preconditions change."""
        with self._lock:
            queue = self._load_queue_unlocked()
            req = queue.get(request_id)
            if not req:
                raise ApprovalNotFoundError(request_id)

            req.status = "stale"
            req.decision_reason = f"Invalidated: {reason}"
            self._save_queue_unlocked(queue)
            self._append_audit_event_unlocked(
                "approval_marked_stale",
                {"request_id": request_id, "reason": reason, "project_id": req.project_id},
            )
            return req

    def consume_approval(self, request_id: str, expected_fingerprint: str) -> ApprovalRequest:
        """Enforces single-use consumption of an approved request at backend action execution time."""
        with self._lock:
            queue = self._load_queue_unlocked()
            req = queue.get(request_id)
            if not req:
                raise ApprovalNotFoundError(request_id)

            if req.status != "approved":
                raise ApprovalGuardError(
                    f"Action execution blocked: Request '{request_id}' has status '{req.status}' (must be 'approved')",
                    code="approval_not_approved",
                )

            if req.action_fingerprint != expected_fingerprint:
                # Upstream assets changed since approval was granted
                req.status = "stale"
                req.decision_reason = "Fingerprint mismatch during execution"
                self._save_queue_unlocked(queue)
                self._append_audit_event_unlocked(
                    "approval_consumption_rejected_stale",
                    {
                        "request_id": request_id,
                        "expected_fingerprint": expected_fingerprint,
                        "approved_fingerprint": req.action_fingerprint,
                    },
                )
                raise ApprovalGuardError(
                    "Action execution blocked: Upstream artifact fingerprint changed after approval was granted",
                    code="approval_stale",
                )

            now_iso = datetime.now(timezone.utc).isoformat()
            req.status = "consumed"
            req.consumed_at = now_iso

            self._save_queue_unlocked(queue)
            self._append_audit_event_unlocked(
                "approval_consumed",
                {
                    "request_id": request_id,
                    "action_type": req.action_type,
                    "fingerprint": req.action_fingerprint,
                    "project_id": req.project_id,
                },
            )
            return req

    def get_audit_trail(self, limit: int = 100) -> list[dict[str, Any]]:
        """Reads recent events from the append-only audit trail."""
        with self._lock:
            if not self._audit_file.exists():
                return []
            try:
                lines = self._audit_file.read_text(encoding="utf-8").strip().splitlines()
                events = [json.loads(line) for line in reversed(lines[-limit:]) if line.strip()]
                return events
            except Exception as e:
                logger.error("Failed to read audit events: %s", e)
                return []


# Canonical singleton engine
approval_engine = ApprovalEngine()
