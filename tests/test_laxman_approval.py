"""Approval engine: requests are decided by the LLM reviewer (llm_decide); no person approves."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.approvals.adapters.eval_adapter import submit_candidate_promotion_request
from backend.approvals.approval_engine import (
    ApprovalEngine,
    ApprovalGuardError,
    ApprovalNotFoundError,
    approval_engine,
    compute_action_fingerprint,
)
from backend.approvals.guard import require_approved_action
from backend.main import app


@pytest.fixture
def temp_engine(tmp_path: Path):
    queue_file = tmp_path / "approvals_queue.json"
    audit_file = tmp_path / "approvals_audit.jsonl"
    return ApprovalEngine(queue_file=queue_file, audit_file=audit_file)


# ==============================================================================
# 1. Approval Engine Lifecycle, LLM decisions & Cryptographic Binding Tests
# ==============================================================================

def test_submit_and_retrieve_request(temp_engine):
    req = temp_engine.submit_request(
        requester_agent_id="test_agent",
        category="video_engine_agent",
        action_type="timeline_render",
        risk_level="medium",
        action_summary="Test render action",
        idempotency_key="idem_test_01",
        payload_for_fingerprint={"comp_sha": "abc123"},
        project_id="p1",
    )
    assert req.status == "pending"
    assert req.action_fingerprint != ""
    assert req.requester_agent_id == "test_agent"

    fetched = temp_engine.get_request(req.request_id)
    assert fetched is not None
    assert fetched.request_id == req.request_id
    assert fetched.idempotency_key == "idem_test_01"


def test_idempotent_submission(temp_engine):
    req1 = temp_engine.submit_request(
        requester_agent_id="test_agent",
        category="video_engine_agent",
        action_type="timeline_render",
        risk_level="medium",
        action_summary="Render",
        idempotency_key="idem_same",
        payload_for_fingerprint={"sha": "123"},
    )
    req2 = temp_engine.submit_request(
        requester_agent_id="test_agent",
        category="video_engine_agent",
        action_type="timeline_render",
        risk_level="medium",
        action_summary="Render",
        idempotency_key="idem_same",
        payload_for_fingerprint={"sha": "123"},
    )
    assert req1.request_id == req2.request_id


def _request(engine, key, **over):
    return engine.submit_request(**{
        "requester_agent_id": "render_video", "category": "video_engine_agent", "action_type": "timeline_render", "risk_level": "medium",
        "action_summary": "Render video", "idempotency_key": key, "payload_for_fingerprint": {"video": key}, **over})


def test_the_llm_approves_and_the_decision_is_recorded_with_its_reviewer(temp_engine, llm_review_says):
    req = _request(temp_engine, "idem_render")
    decided = temp_engine.llm_decide(req.request_id)
    assert decided.status == "approved" and decided.decision == "approved"
    assert decided.reviewer == "llm:stub/stub" and "stub review" in decided.decision_reason and decided.decision_at is not None


def test_the_llm_rejects_on_a_blocker_and_asks_for_changes_when_it_cannot_approve(temp_engine, llm_review_says):
    llm_review_says("blocked", 0.2, [{"severity": "blocker", "category": "evidence", "message": "no test evidence"}])
    rejected = temp_engine.llm_decide(_request(temp_engine, "idem_reject", action_type="skill_promotion", risk_level="high").request_id)
    assert rejected.status == "rejected" and "no test evidence" in rejected.decision_reason and rejected.reviewer == "llm:stub/stub"
    llm_review_says("needs_review", 0.6, [{"severity": "warning", "category": "evidence", "message": "rollback plan is thin"}])
    changes = temp_engine.llm_decide(_request(temp_engine, "idem_changes", action_type="skill_promotion").request_id)
    assert changes.status == "changes_requested" and "stub review" in changes.decision_reason
    llm_review_says("passed", 0.7)                                                                               # passed, but below the 0.80 bar
    assert temp_engine.llm_decide(_request(temp_engine, "idem_low").request_id).status == "changes_requested"
    llm_review_says("passed", 0.95, [{"severity": "error", "category": "evidence", "message": "contradiction"}])  # an error is never approved
    assert temp_engine.llm_decide(_request(temp_engine, "idem_err").request_id).status == "rejected"


def test_an_unavailable_llm_never_approves(temp_engine, llm_review_says, monkeypatch):
    from SYSTEM.core import llm_gateway

    def offline(req):
        raise RuntimeError("offline")
    monkeypatch.setattr(llm_gateway.gateway, "execute", offline)
    out = temp_engine.llm_decide(_request(temp_engine, "idem_offline").request_id)
    assert out.status == "rejected" and "LLM review unavailable" in out.decision_reason


def test_a_decided_request_is_not_decided_again(temp_engine, llm_review_says):
    req = _request(temp_engine, "idem_twice")
    temp_engine.llm_decide(req.request_id)
    with pytest.raises(Exception, match="non-decidable"):
        temp_engine.llm_decide(req.request_id)


def test_consume_approval_and_replay_protection(temp_engine, llm_review_says):
    payload = {"scene_count": 3}
    expected_fp = compute_action_fingerprint("timeline_render", "p_replay", payload)

    req = temp_engine.submit_request(
        requester_agent_id="timeline_build",
        category="video_engine_agent",
        action_type="timeline_render",
        risk_level="medium",
        action_summary="Render",
        idempotency_key="idem_consume",
        payload_for_fingerprint=payload,
        project_id="p_replay",
    )
    temp_engine.llm_decide(req.request_id)

    # First consumption succeeds
    consumed = temp_engine.consume_approval(req.request_id, expected_fp)
    assert consumed.status == "consumed"
    assert consumed.consumed_at is not None

    # Replay consumption fails
    with pytest.raises(ApprovalGuardError, match="must be 'approved'"):
        temp_engine.consume_approval(req.request_id, expected_fp)


def test_fingerprint_mismatch_marks_stale_and_blocks(temp_engine, llm_review_says):
    payload = {"scene_count": 3}
    req = temp_engine.submit_request(
        requester_agent_id="timeline_build",
        category="video_engine_agent",
        action_type="timeline_render",
        risk_level="medium",
        action_summary="Render",
        idempotency_key="idem_stale",
        payload_for_fingerprint=payload,
        project_id="p_stale",
    )
    temp_engine.llm_decide(req.request_id)

    # Consuming with a different fingerprint triggers staleness
    with pytest.raises(ApprovalGuardError, match="fingerprint changed"):
        temp_engine.consume_approval(req.request_id, "different_sha256_hash")

    # Verify request is now marked stale
    stale_req = temp_engine.get_request(req.request_id)
    assert stale_req.status == "stale"


def test_audit_trail_logging_and_redaction(temp_engine, llm_review_says):
    req = temp_engine.submit_request(
        requester_agent_id="agent_audit",
        category="orchestrator",
        action_type="system_change",
        risk_level="low",
        action_summary="Audit test",
        idempotency_key="idem_audit",
        payload_for_fingerprint={"k": "v"},
    )
    temp_engine.llm_decide(req.request_id)

    events = temp_engine.get_audit_trail()
    assert len(events) >= 2
    types = [e["event_type"] for e in events]
    assert "approval_requested" in types
    assert "approval_granted" in types


# ==============================================================================
# 2. FastAPI Route Integration Tests
# ==============================================================================

@pytest.fixture
def client():
    return TestClient(app)


def test_api_status_endpoint(client):
    res = client.get("/approvals/status")
    assert res.status_code == 200
    data = res.json()
    assert set(data) == {"pending_count"}


def test_api_request_lifecycle(client, monkeypatch, tmp_path, llm_review_says):
    monkeypatch.setattr(approval_engine, "_queue_file", tmp_path / "queue.json")
    monkeypatch.setattr(approval_engine, "_audit_file", tmp_path / "audit.jsonl")

    # Create request
    payload = {
        "requester_agent_id": "api_test",
        "category": "video_engine_agent",
        "action_type": "timeline_render",
        "risk_level": "medium",
        "action_summary": "API Test Action",
        "idempotency_key": "idem_api_01",
        "payload_for_fingerprint": {"test": True},
        "affected_files": ["file1.txt"],
        "project_id": "proj_api",
    }
    create_res = client.post("/approvals", json=payload)
    assert create_res.status_code == 201
    req = create_res.json()
    req_id = req["request_id"]
    assert req["status"] == "pending"

    # Fetch detail
    detail_res = client.get(f"/approvals/{req_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["action_summary"] == "API Test Action"

    # The LLM decides (no person) -> 200
    good_res = client.post(f"/approvals/{req_id}/llm-decide")
    assert good_res.status_code == 200
    assert good_res.json()["status"] == "approved"
    assert good_res.json()["reviewer"] == "llm:stub/stub"
    assert client.post(f"/approvals/{req_id}/decide", json={"decision": "approved"}).status_code in (404, 405)    # no person-decision route exists
    assert client.post(f"/approvals/{req_id}/llm-decide").status_code == 409                                      # decided once
    assert client.post("/approvals/appr_nope/llm-decide").status_code == 404

    # Audit trail contains decisions
    audit_res = client.get("/approvals/audit")
    assert audit_res.status_code == 200
    events = audit_res.json()
    assert any(e["event_type"] == "approval_granted" for e in events)

    # A blocking verdict rejects through the API
    rej_id = client.post("/approvals", json={**payload, "idempotency_key": "idem_api_reject_01", "action_summary": "API Reject Test"}).json()["request_id"]
    llm_review_says("blocked", 0.1, [{"severity": "blocker", "category": "evidence", "message": "No good"}])
    good_rej = client.post(f"/approvals/{rej_id}/llm-decide")
    assert good_rej.status_code == 200 and good_rej.json()["status"] == "rejected" and "No good" in good_rej.json()["decision_reason"]


# ==============================================================================
# 3. Integration Adapters Unit Tests
# ==============================================================================

def test_eval_adapter_submission_is_decided_by_the_llm(tmp_path, monkeypatch, llm_review_says):
    monkeypatch.setattr(approval_engine, "_queue_file", tmp_path / "queue.json")
    monkeypatch.setattr(approval_engine, "_audit_file", tmp_path / "audit.jsonl")
    req = submit_candidate_promotion_request(
        candidate_id="cand_123",
        candidate_type="skill",
        target_id="skill_camera_shake",
        title="Camera Shake Motion Skill",
        description="High quality camera shake",
        risk_level="high",
    )
    assert req.action_type == "skill_promotion"
    assert req.category == "system_subagent"
    assert req.status == "approved" and req.reviewer == "llm:stub/stub"                                           # submitted and decided in one call
