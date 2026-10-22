"""Unit and regression tests for LearningGate, KnowledgePromoter, RollbackManager,
StoreLock, and Operator Authorization / Anti-Spoofing.
"""
from __future__ import annotations

import concurrent.futures
import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from SYSTEM.agents.capability_finder.learning.authorization import (
    ELEVATED_SECURITY_ROLES,
    STANDARD_OPERATOR_ROLES,
    TRUSTED_OPERATOR_ROLES,
    AuthenticatedOperator,
    SecurityAuthError,
    authenticate_operator,
    verify_elevated_role,
)
from SYSTEM.agents.capability_finder.learning.case_collector import CaseCollector, LearningCase
from SYSTEM.agents.capability_finder.learning.knowledge_promoter import KnowledgePromoter
from SYSTEM.agents.capability_finder.learning.learning_gate import LearningGate
from SYSTEM.agents.capability_finder.learning.lesson_evaluator import LearningEvaluation
from SYSTEM.agents.capability_finder.learning.lesson_generator import LessonProposal
from SYSTEM.agents.capability_finder.learning.rollback_manager import RollbackManager
from SYSTEM.agents.capability_finder.learning.store_lock import StoreLock
from SYSTEM.approvals.approval_engine import approval_engine


@pytest.fixture(autouse=True)
def isolated_state(tmp_path: Path, monkeypatch, llm_review_says):
    """Each test gets its own approval queue and a fresh lock registry."""
    monkeypatch.setattr(approval_engine, "_queue_file", tmp_path / "approvals_queue.json")
    monkeypatch.setattr(approval_engine, "_audit_file", tmp_path / "approvals_audit.jsonl")
    StoreLock.reset_registry_for_tests()
    yield
    StoreLock.reset_registry_for_tests()


def approved_request(key: str, risk_level: str = "medium") -> str:
    """A Laxman approval request that a person approved in the UI."""
    req = approval_engine.submit_request(
        requester_agent_id="capability_finder",
        category="system_subagent",
        action_type="promote_lesson",
        risk_level=risk_level,
        action_summary=f"Approve {key}",
        idempotency_key=key,
        payload_for_fingerprint={"key": key},
    )
    approval_engine.llm_decide(req.request_id)
    return req.request_id


def lead_operator(operator_id: str = "lead_user") -> AuthenticatedOperator:
    return AuthenticatedOperator(
        operator_id=operator_id,
        role="lead_operator",
        auth_method="trusted_context",
        verified_at=datetime.now(timezone.utc).isoformat(),
    )


def test_learning_gate_checks(tmp_path: Path):
    collector = CaseCollector(storage_file=tmp_path / "cases.jsonl")
    c1 = collector.record_case(LearningCase(task_id="t1"))
    c2 = collector.record_case(LearningCase(task_id="t2"))

    gate = LearningGate(collector=collector)

    valid_proposal = LessonProposal(
        proposal_id="prop_abcdef123456",
        schema_version=1,
        version="1.1.0",
        title="Routing for Audio Speech",
        description="Routes audio domain to faster_whisper",
        observed_pattern="Multiple requests for transcription",
        affected_domain="audio",
        rule_type="routing_preference",
        rule_content={"target_domain": "audio", "preferred_delegate_id": "faster_whisper"},
        supporting_case_ids=[c1, c2],
        counterexample_case_ids=[],
        status="CANDIDATE",
    )

    valid_eval = LearningEvaluation(
        proposal_id="prop_abcdef123456",
        baseline_metrics={"recommendation_accuracy": 0.8, "false_reuse_rate": 0.0, "false_creation_rate": 0.0},
        candidate_metrics={"recommendation_accuracy": 0.9, "false_reuse_rate": 0.0, "false_creation_rate": 0.0},
        accuracy_delta=0.1,
        has_regression=False,
        passed_gate=True,
    )

    # 1. Gate passes with an approved Laxman request
    passed, reasons = gate.check_promotion_gates(
        proposal=valid_proposal,
        evaluation=valid_eval,
        approval_request_id=approved_request("gate_valid"),
        check_case_existence=True,
    )
    assert passed is True
    assert len(reasons) == 0

    # 2. Gate rejects without authorization / credentials
    passed_no_auth, reasons_no_auth = gate.check_promotion_gates(
        proposal=valid_proposal,
        evaluation=valid_eval,
        authorized_by="",
    )
    assert passed_no_auth is False
    assert any("credentials" in r.lower() or "authorization" in r.lower() for r in reasons_no_auth)

    # 3. Gate rejects caller-supplied role string without credentials (role-spoofing prevention)
    passed_spoof, reasons_spoof = gate.check_promotion_gates(
        proposal=valid_proposal,
        evaluation=valid_eval,
        authorized_by="system_admin",  # No credentials supplied
    )
    assert passed_spoof is False
    assert any("role spoofing" in r.lower() or "credentials" in r.lower() for r in reasons_spoof)

    # 4. Gate rejects insufficient evidence (< 2)
    prop_low_ev = LessonProposal(
        proposal_id="prop_112233445566",
        title="Low Evidence",
        description="desc",
        observed_pattern="pat",
        affected_domain="audio",
        rule_type="routing_preference",
        rule_content={},
        supporting_case_ids=[c1],  # Only 1
    )
    passed_low, reasons_low = gate.check_promotion_gates(
        proposal=prop_low_ev,
        evaluation=valid_eval,
        operator=lead_operator(),
    )
    assert passed_low is False
    assert any("Insufficient evidence" in r for r in reasons_low)

    # 5. Gate rejects evaluation with regression
    bad_eval = LearningEvaluation(
        proposal_id="prop_abcdef123456",
        baseline_metrics={"recommendation_accuracy": 0.8, "false_reuse_rate": 0.0, "false_creation_rate": 0.0},
        candidate_metrics={"recommendation_accuracy": 0.7, "false_reuse_rate": 0.1, "false_creation_rate": 0.0},
        accuracy_delta=-0.1,
        has_regression=True,
        passed_gate=False,
    )
    passed_reg, reasons_reg = gate.check_promotion_gates(
        proposal=valid_proposal,
        evaluation=bad_eval,
        operator=lead_operator(),
    )
    assert passed_reg is False
    assert any("regression" in r.lower() for r in reasons_reg)


def test_role_spoofing_prevention_fail_closed(tmp_path: Path):
    """Passing a caller-supplied role string must NEVER grant authorization on its own."""
    active_file = tmp_path / "knowledge" / "active" / "active_knowledge.json"
    archive_dir = tmp_path / "knowledge" / "archive"
    promoter = KnowledgePromoter(active_file=active_file, archive_dir=archive_dir)
    rollback_mgr = RollbackManager(active_file=active_file, archive_dir=archive_dir, promoter=promoter)

    prop = LessonProposal(
        proposal_id="prop_000000000001",
        title="Spoof Proposal",
        description="desc",
        observed_pattern="pattern",
        affected_domain="audio",
        rule_type="routing_preference",
        rule_content={"target_domain": "audio"},
        supporting_case_ids=["c1", "c2"],
        author="system_admin",  # Untrusted proposal payload author field
    )
    eval_rep = LearningEvaluation(
        proposal_id="prop_000000000001",
        baseline_metrics={"recommendation_accuracy": 0.8, "false_reuse_rate": 0.0, "false_creation_rate": 0.0},
        candidate_metrics={"recommendation_accuracy": 0.9, "false_reuse_rate": 0.0, "false_creation_rate": 0.0},
        accuracy_delta=0.1,
        has_regression=False,
        passed_gate=True,
    )

    # 1. Attempting promote with spoofed role string alone must fail closed
    for claimed_role in ["system_admin", "security_officer", "laxman_admin", "operator"]:
        with pytest.raises(ValueError) as excinfo:
            promoter.promote_proposal(
                proposal=prop,
                evaluation=eval_rep,
                authorized_by=claimed_role,  # No credentials
                check_case_existence=False,
            )
        err_msg = str(excinfo.value).lower()
        assert "role spoofing" in err_msg or "credentials" in err_msg

    # 2. Attempting rollback with spoofed role string alone must fail closed
    with pytest.raises(ValueError) as excinfo_rb:
        rollback_mgr.rollback(authorized_by="system_admin")  # No credentials
    assert "role spoofing" in str(excinfo_rb.value).lower() or "credentials" in str(excinfo_rb.value).lower()


def test_trusted_operator_and_approval_engine_authorization(tmp_path: Path):
    """Verifies trusted-context operators and ApprovalEngine request verification."""
    active_file = tmp_path / "knowledge" / "active" / "active_knowledge.json"
    archive_dir = tmp_path / "archive"
    promoter = KnowledgePromoter(active_file=active_file, archive_dir=archive_dir)

    prop = LessonProposal(
        proposal_id="prop_000000000003",
        title="Auth Flow Proposal",
        description="desc",
        observed_pattern="pattern",
        affected_domain="audio",
        rule_type="routing_preference",
        rule_content={"target_domain": "audio", "preferred_delegate_id": "faster_whisper"},
        supporting_case_ids=["c1", "c2"],
    )
    eval_rep = LearningEvaluation(
        proposal_id="prop_000000000003",
        baseline_metrics={"recommendation_accuracy": 0.8, "false_reuse_rate": 0.0, "false_creation_rate": 0.0},
        candidate_metrics={"recommendation_accuracy": 0.9, "false_reuse_rate": 0.0, "false_creation_rate": 0.0},
        accuracy_delta=0.1,
        has_regression=False,
        passed_gate=True,
    )

    # 1. Success with a trusted-context standard operator
    res_op = promoter.promote_proposal(
        proposal=prop,
        evaluation=eval_rep,
        operator=lead_operator("operator_alice"),
        check_case_existence=False,
    )
    assert res_op["promoted"] is True
    assert res_op["authorized_by"] == "operator_alice (lead_operator)"
    assert res_op["operator"]["auth_method"] == "trusted_context"

    # 2. Success via ApprovalEngine integration
    prop2 = LessonProposal(
        proposal_id="prop_000000000004",
        title="Approval Flow Proposal",
        description="desc",
        observed_pattern="pattern",
        affected_domain="audio",
        rule_type="routing_preference",
        rule_content={"target_domain": "audio", "preferred_delegate_id": "whisper_large"},
        supporting_case_ids=["c1", "c2"],
    )
    eval_rep2 = LearningEvaluation(
        proposal_id="prop_000000000004",
        baseline_metrics={"recommendation_accuracy": 0.8, "false_reuse_rate": 0.0, "false_creation_rate": 0.0},
        candidate_metrics={"recommendation_accuracy": 0.9, "false_reuse_rate": 0.0, "false_creation_rate": 0.0},
        accuracy_delta=0.1,
        has_regression=False,
        passed_gate=True,
    )

    # Submit request to ApprovalEngine
    appr_req = approval_engine.submit_request(
        requester_agent_id="capability_finder",
        category="system_subagent",
        action_type="promote_lesson",
        risk_level="medium",
        action_summary="Approve lesson promotion prop_000000000004",
        idempotency_key="key_auth_flow_004",
        payload_for_fingerprint={"proposal_id": "prop_000000000004"},
    )
    assert appr_req.status == "pending"

    # Unapproved request should be rejected
    with pytest.raises(ValueError) as exc_appr:
        promoter.promote_proposal(
            proposal=prop2,
            evaluation=eval_rep2,
            approval_request_id=appr_req.request_id,
            check_case_existence=False,
        )
    assert "not approved" in str(exc_appr.value).lower()

    # The LLM reviewer approves the request
    approval_engine.llm_decide(appr_req.request_id)

    # Now promotion succeeds and single-use consumes the approval
    res_appr = promoter.promote_proposal(
        proposal=prop2,
        evaluation=eval_rep2,
        approval_request_id=appr_req.request_id,
        check_case_existence=False,
    )
    assert res_appr["promoted"] is True
    assert res_appr["operator"]["auth_method"] == "approval_engine"
    assert res_appr["operator"]["role"] == "laxman_admin"

    # Re-using already consumed approval must fail
    with pytest.raises(ValueError):
        promoter.promote_proposal(
            proposal=prop2,
            evaluation=eval_rep2,
            approval_request_id=appr_req.request_id,
            check_case_existence=False,
        )


def test_elevated_role_enforcement_for_high_risk(tmp_path: Path):
    """High-risk proposals strictly require elevated operator roles."""
    collector = CaseCollector(storage_file=tmp_path / "cases.jsonl")
    c1 = collector.record_case(LearningCase(task_id="t1"))
    c2 = collector.record_case(LearningCase(task_id="t2"))
    gate = LearningGate(collector=collector)

    prop_high = LessonProposal(
        proposal_id="prop_000000000005",
        title="High Risk Override",
        description="desc",
        observed_pattern="pattern",
        affected_domain="audio",
        rule_type="routing_preference",
        rule_content={"target_domain": "audio"},
        supporting_case_ids=[c1, c2],
        risk_level="high",
    )
    eval_rep = LearningEvaluation(
        proposal_id="prop_000000000005",
        baseline_metrics={"recommendation_accuracy": 0.8, "false_reuse_rate": 0.0, "false_creation_rate": 0.0},
        candidate_metrics={"recommendation_accuracy": 0.9, "false_reuse_rate": 0.0, "false_creation_rate": 0.0},
        accuracy_delta=0.1,
        has_regression=False,
        passed_gate=True,
    )

    # 1. A standard operator fails for a high-risk proposal
    passed, reasons = gate.check_promotion_gates(
        prop_high,
        eval_rep,
        operator=lead_operator(),
        check_case_existence=False,
    )
    assert passed is False
    assert any("High-risk proposals require elevated authorization" in r for r in reasons)

    # 2. Elevated role via ApprovalEngine succeeds for high-risk proposal
    appr_high = approval_engine.submit_request(
        requester_agent_id="capability_finder",
        category="system_subagent",
        action_type="promote_lesson",
        risk_level="high",
        action_summary="Approve high risk lesson",
        idempotency_key=f"key_high_risk_appr_005_{uuid.uuid4().hex[:8]}",
        payload_for_fingerprint={"proposal_id": "prop_000000000005"},
    )
    approval_engine.llm_decide(appr_high.request_id)

    passed_appr, reasons_appr = gate.check_promotion_gates(
        prop_high,
        eval_rep,
        approval_request_id=appr_high.request_id,
        check_case_existence=False,
    )
    assert passed_appr is True
    assert len(reasons_appr) == 0

    # 3. Elevated role via server trusted_context succeeds for high-risk proposal
    op_admin = AuthenticatedOperator(
        operator_id="admin_sec",
        role="security_officer",
        auth_method="trusted_context",
        verified_at=datetime.now(timezone.utc).isoformat(),
    )
    passed_ctx, reasons_ctx = gate.check_promotion_gates(
        prop_high,
        eval_rep,
        operator=op_admin,
        check_case_existence=False,
    )
    assert passed_ctx is True
    assert len(reasons_ctx) == 0


def test_rejected_operations_leave_state_unchanged(tmp_path: Path):
    """When a promotion or rollback is rejected, the active store and archives remain 100% untouched."""
    active_file = tmp_path / "knowledge" / "active" / "active_knowledge.json"
    archive_dir = tmp_path / "knowledge" / "archive"

    promoter = KnowledgePromoter(active_file=active_file, archive_dir=archive_dir)
    rollback_mgr = RollbackManager(active_file=active_file, archive_dir=archive_dir, promoter=promoter)

    initial_knowledge = promoter.load_active_knowledge()
    initial_version = initial_knowledge["version"]
    assert initial_version == "1.0.0"

    prop_bad = LessonProposal(
        proposal_id="prop_000000000006",
        title="Bad Proposal",
        description="desc",
        observed_pattern="pat",
        affected_domain="audio",
        rule_type="routing_preference",
        rule_content={"target_domain": "audio"},
        supporting_case_ids=["c1", "c2"],
    )
    eval_bad = LearningEvaluation(
        proposal_id="prop_000000000006",
        baseline_metrics={"recommendation_accuracy": 0.8, "false_reuse_rate": 0.0, "false_creation_rate": 0.0},
        candidate_metrics={"recommendation_accuracy": 0.9, "false_reuse_rate": 0.0, "false_creation_rate": 0.0},
        accuracy_delta=0.1,
        has_regression=False,
        passed_gate=True,
    )

    # 1. Rejected promotion: unauthenticated spoofing attempt
    with pytest.raises(ValueError):
        promoter.promote_proposal(prop_bad, eval_bad, authorized_by="system_admin", check_case_existence=False)

    after_spoof = promoter.load_active_knowledge()
    assert after_spoof["version"] == initial_version
    assert len(list(archive_dir.glob("*.json"))) == 0

    # 2. Rejected rollback: unauthenticated attempt
    with pytest.raises(ValueError):
        rollback_mgr.rollback(authorized_by="system_admin")

    after_rb = promoter.load_active_knowledge()
    assert after_rb["version"] == initial_version
    assert len(list(archive_dir.glob("*.json"))) == 0


def test_knowledge_promotion_and_rollback(tmp_path: Path):
    active_file = tmp_path / "knowledge" / "active" / "active_knowledge.json"
    archive_dir = tmp_path / "knowledge" / "archive"

    promoter = KnowledgePromoter(active_file=active_file, archive_dir=archive_dir)
    rollback_mgr = RollbackManager(active_file=active_file, archive_dir=archive_dir, promoter=promoter)

    initial_knowledge = promoter.load_active_knowledge()
    assert initial_knowledge["version"] == "1.0.0"

    prop = LessonProposal(
        proposal_id="prop_aabbccddeeff",
        title="Promote Audio Routing",
        description="desc",
        observed_pattern="pattern",
        affected_domain="audio",
        rule_type="routing_preference",
        rule_content={"target_domain": "audio", "preferred_delegate_id": "faster_whisper", "boost_score": 0.3},
        supporting_case_ids=["case_1", "case_2"],
    )
    eval_rep = LearningEvaluation(
        proposal_id="prop_aabbccddeeff",
        baseline_metrics={"recommendation_accuracy": 0.8, "false_reuse_rate": 0.0, "false_creation_rate": 0.0},
        candidate_metrics={"recommendation_accuracy": 0.9, "false_reuse_rate": 0.0, "false_creation_rate": 0.0},
        accuracy_delta=0.1,
        has_regression=False,
        passed_gate=True,
    )

    # Promote proposal as a trusted standard operator
    prom_report = promoter.promote_proposal(
        proposal=prop,
        evaluation=eval_rep,
        operator=lead_operator(),
        check_case_existence=False,
    )

    assert prom_report["promoted"] is True
    assert prom_report["new_version"] == "1.1.0"
    assert prom_report["authorized_by"] == "lead_user (lead_operator)"

    # Check active knowledge file was updated
    updated = promoter.load_active_knowledge()
    assert updated["version"] == "1.1.0"
    assert "audio" in updated["routing_preferences"]
    assert len(updated["promoted_lessons"]) == 1
    assert updated["last_promoted_by"] == "lead_user (lead_operator)"

    # Check archive file was created
    archives = rollback_mgr.list_archive_versions()
    assert len(archives) >= 1
    assert archives[0]["version"] == "1.0.0"

    # Rollback to initial archive, approved by Laxman in the UI
    rb_report = rollback_mgr.rollback(approval_request_id=approved_request("rollback_initial"))
    assert rb_report["rolled_back"] is True
    assert rb_report["restored_version"] == "1.0.0"

    # Active knowledge should be restored to 1.0.0
    restored = promoter.load_active_knowledge()
    assert restored["version"] == "1.0.0"
    assert "audio" not in restored["routing_preferences"]
