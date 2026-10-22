"""FastAPI routes for Evaluation Engine, Regression Testing & Verified Self-Learning Governance."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from SYSTEM.observability import evaluation
from SYSTEM.core.errors import ApiError

router = APIRouter(prefix="/evaluations", tags=["evaluation"])


class RunEvaluationRequest(BaseModel):
    suite_id: str
    case_id: str
    observed_output: dict[str, Any]
    llm_mock_response: dict[str, Any] | None = None
    save_as_baseline_key: str | None = None


class CompareRequest(BaseModel):
    baseline_key: str
    candidate_result: dict[str, Any]
    tolerance: float = 0.05


class ProposeCandidateRequest(BaseModel):
    candidate_type: Literal["skill", "memory", "prompt_proposal", "configuration"]
    target_id: str
    version: str = "1.1.0"
    title: str
    description: str
    rationale: str
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    proposed_content: Any
    diff: str = ""
    risk_level: Literal["low", "medium", "high", "critical"] = "low"
    rollback_plan: str = ""


class CandidateDecisionRequest(BaseModel):
    reviewer: str
    decision: Literal["approved", "rejected", "request_changes"]
    reason: str


class CandidatePromoteRequest(BaseModel):
    reviewer: str


class CandidateRollbackRequest(BaseModel):
    reviewer: str
    reason: str


@router.get("/suites")
def list_suites() -> list[dict[str, Any]]:
    """Lists all registered, versioned evaluation suites and benchmark cases."""
    reg = evaluation.get_evaluation_registry()
    return reg.list_suites()


@router.get("/suites/{suite_id}")
def get_suite(suite_id: str) -> dict[str, Any]:
    """Retrieves details of a specific evaluation suite."""
    reg = evaluation.get_evaluation_registry()
    suite = reg.get_suite(suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail=f"Evaluation suite '{suite_id}' not found")
    return suite.to_dict()


@router.post("/run", status_code=200)
def run_evaluation(body: RunEvaluationRequest) -> dict[str, Any]:
    """Runs isolated deterministic hard checks and optional LLM judge for an evaluation case."""
    reg = evaluation.get_evaluation_registry()
    case = reg.get_case(body.suite_id, body.case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{body.case_id}' in suite '{body.suite_id}' not found")

    result = evaluation.evaluate_case(
        case=case,
        observed_output=body.observed_output,
        llm_mock_response=body.llm_mock_response,
    )

    if body.save_as_baseline_key:
        reg.store_baseline(body.save_as_baseline_key, result)

    return result.to_dict()


@router.post("/compare", status_code=200)
def compare_evaluation(body: CompareRequest) -> dict[str, Any]:
    """Compares a candidate evaluation against an approved baseline standard."""
    reg = evaluation.get_evaluation_registry()
    baseline = reg.get_baseline(body.baseline_key)
    
    # Parse candidate result
    c_data = body.candidate_result
    cand_checks = [evaluation.DeterministicCheckResult(**c) for c in c_data.get("deterministic_checks", [])]
    cand_llm = evaluation.LlmJudgmentResult(**c_data["llm_judgment"]) if c_data.get("llm_judgment") else None
    
    candidate = evaluation.EvaluationResult(
        schema_version=c_data.get("schema_version", 1),
        evaluation_id=c_data.get("evaluation_id", "eval_cand"),
        suite_id=c_data.get("suite_id", ""),
        suite_version=c_data.get("suite_version", 1),
        case_id=c_data.get("case_id", ""),
        case_version=c_data.get("case_version", 1),
        stage_id=c_data.get("stage_id", ""),
        overall_status=c_data.get("overall_status", "passed"),
        hard_gates_passed=c_data.get("hard_gates_passed", True),
        deterministic_checks=cand_checks,
        llm_judgment=cand_llm,
        composite_score=c_data.get("composite_score", 1.0),
        findings=c_data.get("findings", []),
    )

    report = evaluation.compare_evaluations(baseline, candidate, tolerance=body.tolerance)
    return report.to_dict()


@router.get("/candidates")
def list_candidates() -> list[dict[str, Any]]:
    """Lists improvement candidates proposed for skills, memories, or configurations."""
    reg = evaluation.get_evaluation_registry()
    return reg.list_candidates()


@router.post("/candidates", status_code=201)
def propose_candidate(body: ProposeCandidateRequest) -> dict[str, Any]:
    """Registers an unverified improvement candidate proposal based on reproducible evidence."""
    reg = evaluation.get_evaluation_registry()
    cand = evaluation.CandidateProposal(
        candidate_type=body.candidate_type,
        target_id=body.target_id,
        version=body.version,
        title=body.title,
        description=body.description,
        rationale=body.rationale,
        evidence_refs=body.evidence_refs,
        proposed_content=body.proposed_content,
        diff=body.diff,
        risk_level=body.risk_level,
        rollback_plan=body.rollback_plan,
        status="proposed",
    )
    saved = reg.register_candidate(cand)
    return saved.to_dict()


@router.get("/candidates/{candidate_id}")
def get_candidate(candidate_id: str) -> dict[str, Any]:
    """Retrieves candidate diff, evidence links, and governance decision history."""
    reg = evaluation.get_evaluation_registry()
    cand = reg.get_candidate(candidate_id)
    if not cand:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found")
    return cand.to_dict()


@router.post("/candidates/{candidate_id}/decision")
def record_candidate_decision(candidate_id: str, body: CandidateDecisionRequest) -> dict[str, Any]:
    """Enforces human reviewer sign-off before any candidate can be approved."""
    reg = evaluation.get_evaluation_registry()
    try:
        updated = reg.record_decision(
            candidate_id=candidate_id,
            reviewer=body.reviewer,
            decision=body.decision,
            reason=body.reason,
        )
        return updated.to_dict()
    except ApiError as e:
        raise HTTPException(status_code=e.status, detail={"code": e.code, "message": e.message, "hint": e.hint})
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found")


@router.post("/candidates/{candidate_id}/promote")
def promote_candidate(candidate_id: str, body: CandidatePromoteRequest) -> dict[str, Any]:
    """Atomically promotes an approved candidate into production active version pointer."""
    reg = evaluation.get_evaluation_registry()
    try:
        return reg.promote_candidate(candidate_id=candidate_id, reviewer=body.reviewer)
    except ApiError as e:
        raise HTTPException(status_code=e.status, detail={"code": e.code, "message": e.message, "hint": e.hint})
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found")


@router.post("/candidates/{candidate_id}/rollback")
def rollback_candidate(candidate_id: str, body: CandidateRollbackRequest) -> dict[str, Any]:
    """Rolls back an approved candidate, restoring prior active pointer without deleting history."""
    reg = evaluation.get_evaluation_registry()
    try:
        return reg.rollback_candidate(candidate_id=candidate_id, reviewer=body.reviewer, reason=body.reason)
    except ApiError as e:
        raise HTTPException(status_code=e.status, detail={"code": e.code, "message": e.message, "hint": e.hint})
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found")
