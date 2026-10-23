"""Phase 9: Evaluation & Verified Self-Learning Governance Tests.

Validates:
1. Evaluation suites and cases schema, versions, and deterministic fixtures.
2. Deterministic hard checks (orthography, frame arithmetic, static security) execute first.
3. Strict invariant: Deterministic hard failure ALWAYS beats any LLM judge score.
4. Optional LLM judge scoring through canonical gateway structure with mock responses.
5. Baseline comparison and regression detection (hard gate regressions trigger immediate rejection).
6. Inconclusive comparison when baseline is absent or incomparable.
7. Candidate proposal lifecycle: proposed (unverified) -> under_evaluation -> approved/rejected.
8. Mandatory human reviewer identity required for candidate approval; agent self-approval is rejected.
9. Versioned atomic promotion updates active version pointer in skill registry / shared memory.
10. Auditable rollback restores previous version pointer without erasing history.
11. Unverified memory candidates and quarantined skills are excluded from production retrieval.
12. Truthful capability reporting: headless Chromium prerequisite remains explicitly unverified.
13. API endpoints for evaluation run, compare, candidate propose, decision, promote, and rollback.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend import evaluation, shared_memory, skill_registry
from backend.errors import ApiError
from backend.main import app

client = TestClient(app)


@pytest.fixture
def mock_no_asr():
    """Ensure that any accidental call to ASR or transcribe fails immediately."""
    with patch("backend.transcribe.transcribe", side_effect=RuntimeError("PROHIBITED: ASR transcribe was invoked!")), \
         patch("backend.scene_segmentation.run", side_effect=RuntimeError("PROHIBITED: Scene segmentation re-run was invoked!")):
        yield


@pytest.fixture
def isolated_eval_env(tmp_path: Path):
    """Provides an isolated clean environment for evaluation registry, suites, and baselines."""
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    results_dir = config_dir / "eval_results"
    results_dir.mkdir(parents=True, exist_ok=True)

    with patch("backend.evaluation.CONFIG_DIR", config_dir), \
         patch("backend.evaluation.EVAL_SUITES_FILE", config_dir / "eval_suites.json"), \
         patch("backend.evaluation.EVAL_BASELINES_FILE", config_dir / "eval_baselines.json"), \
         patch("backend.evaluation.EVAL_CANDIDATES_FILE", config_dir / "eval_candidates.json"), \
         patch("backend.evaluation.EVAL_RESULTS_DIR", results_dir):

        reg = evaluation.EvaluationRegistry()
        reg.initialize()
        with patch("backend.evaluation.get_evaluation_registry", return_value=reg):
            yield reg


def test_evaluation_registry_and_seed_suites(isolated_eval_env: evaluation.EvaluationRegistry, mock_no_asr):
    """Verify canonical evaluation suites are initialized with approved deterministic test cases."""
    suites = isolated_eval_env.list_suites()
    assert len(suites) >= 3

    suite_ids = {s["suite_id"] for s in suites}
    assert "suite-telugu-orthography" in suite_ids
    assert "suite-timeline-arithmetic" in suite_ids
    assert "suite-security-gates" in suite_ids

    telugu_suite = isolated_eval_env.get_suite("suite-telugu-orthography")
    assert telugu_suite is not None
    assert len(telugu_suite.cases) >= 2

    # Case inspection
    pos_case = isolated_eval_env.get_case("suite-telugu-orthography", "eval-telugu-01-positive")
    assert pos_case is not None
    assert pos_case.status == "approved"
    assert "require_telugu_script" in pos_case.expected_invariants


def test_deterministic_hard_check_evaluation(isolated_eval_env: evaluation.EvaluationRegistry, mock_no_asr):
    """Verify deterministic evaluator verifies Telugu script preservation and rejects corruption."""
    case_pos = isolated_eval_env.get_case("suite-telugu-orthography", "eval-telugu-01-positive")
    assert case_pos is not None

    # 1. Valid bilingual narration
    valid_output = {
        "transcript": "ఈ రోజు మనము AI మరియు Machine Learning గురించి నేర్చుకుందాము.",
    }
    res_valid = evaluation.evaluate_case(case_pos, valid_output)
    assert res_valid.overall_status == "passed"
    assert res_valid.hard_gates_passed is True
    assert all(c.status == "passed" for c in res_valid.deterministic_checks)

    # 2. Corrupted Latin phonetics without native Telugu script
    invalid_output = {
        "transcript": "Ee roju manamu AI gurinchi nerchukundamu.",
    }
    res_invalid = evaluation.evaluate_case(case_pos, invalid_output)
    assert res_invalid.overall_status == "failed"
    assert res_invalid.hard_gates_passed is False
    failed_check = next(c for c in res_invalid.deterministic_checks if c.check_id == "check_telugu_native_script")
    assert failed_check.status == "failed"
    assert failed_check.severity == "blocker"


def test_deterministic_failure_beats_llm_judge(isolated_eval_env: evaluation.EvaluationRegistry, mock_no_asr):
    """Verify STRICT INVARIANT: A deterministic hard-gate failure ALWAYS overrides an LLM pass with score 1.0."""
    sec_case = isolated_eval_env.get_case("suite-security-gates", "eval-sec-02-negative-dangerous-import")
    assert sec_case is not None

    # Observed output with prohibited child_process import
    dangerous_output = {
        "code": 'import { exec } from "child_process";\nexport const Scene = () => <div>Exploit</div>;',
    }

    # Simulate an LLM judge that mistakenly rates the code 1.0/1.0
    misleading_llm = {
        "provider": "mock_judge",
        "model": "gpt-4o",
        "passed": True,
        "composite_score": 1.0,
        "scores": {"quality": 1.0, "safety": 1.0},
        "summary": "Mistakenly claimed safe",
    }

    res = evaluation.evaluate_case(sec_case, dangerous_output, llm_mock_response=misleading_llm)

    # Deterministic failure MUST dominate
    assert res.overall_status == "failed"
    assert res.hard_gates_passed is False
    assert res.composite_score == 0.0  # Reset to 0 due to hard failure
    assert any("Dangerous shell/node module imports" in f for f in res.findings)


def test_timeline_frame_arithmetic_invariants(isolated_eval_env: evaluation.EvaluationRegistry, mock_no_asr):
    """Verify 30 fps frame arithmetic check: sequential contiguous frames pass; gaps fail."""
    tl_case = isolated_eval_env.get_case("suite-timeline-arithmetic", "eval-timeline-01-exact-30fps")
    assert tl_case is not None

    # 1. Contiguous 30fps scenes
    valid_timeline = {
        "fps": 30,
        "scenes": [
            {"id": "scene_1", "start_frame": 0, "end_frame": 90},
            {"id": "scene_2", "start_frame": 90, "end_frame": 180},
        ],
        "total_frames": 180,
    }
    res_valid = evaluation.evaluate_case(tl_case, valid_timeline)
    assert res_valid.overall_status == "passed"
    assert res_valid.hard_gates_passed is True

    # 2. Frame gap between scene 1 and 2
    gapped_timeline = {
        "fps": 30,
        "scenes": [
            {"id": "scene_1", "start_frame": 0, "end_frame": 90},
            {"id": "scene_2", "start_frame": 95, "end_frame": 180},
        ],
        "total_frames": 180,
    }
    res_gapped = evaluation.evaluate_case(tl_case, gapped_timeline)
    assert res_gapped.overall_status == "failed"
    assert res_gapped.hard_gates_passed is False
    assert any("gap/overlap" in c.reason for c in res_gapped.deterministic_checks if c.status == "failed")


def test_baseline_storage_and_regression_rejection(isolated_eval_env: evaluation.EvaluationRegistry, mock_no_asr):
    """Verify regression comparison rejects candidates that regress on hard gates or degrade quality."""
    case = isolated_eval_env.get_case("suite-telugu-orthography", "eval-telugu-01-positive")
    assert case is not None

    # 1. Store valid baseline
    baseline_output = {"transcript": "ఈ రోజు మనము AI మరియు Machine Learning గురించి నేర్చుకుందాము."}
    baseline_res = evaluation.evaluate_case(case, baseline_output)
    assert baseline_res.overall_status == "passed"
    isolated_eval_env.store_baseline("base-telugu-01", baseline_res)

    # 2. Candidate with hard-gate regression (missing Telugu script)
    candidate_output = {"transcript": "Today we will learn about AI."}
    cand_res = evaluation.evaluate_case(case, candidate_output)
    assert cand_res.overall_status == "failed"

    # Compare
    report = evaluation.compare_evaluations(baseline_res, cand_res)
    assert report.decision == "rejected"
    assert report.hard_gate_regression is True
    assert "check_telugu_native_script" in report.regressed_checks

    # 3. Missing baseline returns inconclusive
    inconclusive_rep = evaluation.compare_evaluations(None, cand_res)
    assert inconclusive_rep.decision == "inconclusive"


def test_candidate_proposal_lifecycle_and_human_approval(isolated_eval_env: evaluation.EvaluationRegistry, mock_no_asr):
    """Verify proposal governance: unverified candidate requires human review; self-approval prohibited."""
    cand = evaluation.CandidateProposal(
        candidate_type="skill",
        target_id="motion.typography_speed",
        version="1.2.0",
        title="Dynamic Pace Adjustment Rule",
        description="Increases typography velocity for fast narration beats.",
        rationale="Evidence from run_4821 shows 20% reading overflow on 180 wpm narration.",
        evidence_refs=[{"run_id": "run_4821", "finding": "text_overflow_risk"}],
        proposed_content={"speed_multiplier": 1.25},
        status="proposed",
    )
    saved = isolated_eval_env.register_candidate(cand)
    assert saved.status == "proposed"

    # Invariant: automated agent self-approval must be rejected with 403
    with pytest.raises(ApiError) as exc_info:
        isolated_eval_env.record_decision(
            candidate_id=saved.candidate_id,
            reviewer="system",
            decision="approved",
            reason="Auto approving my own proposal",
        )
    assert exc_info.value.status == 403
    assert exc_info.value.code == "self_approval_prohibited"

    # Authorized human review decision succeeds
    approved_cand = isolated_eval_env.record_decision(
        candidate_id=saved.candidate_id,
        reviewer="senior_engineer_human",
        decision="approved",
        reason="Verified against benchmark typography suite with zero clipping.",
    )
    assert approved_cand.status == "approved"
    assert approved_cand.reviewer_decision["reviewer"] == "senior_engineer_human"


def test_atomic_version_promotion_and_rollback(isolated_eval_env: evaluation.EvaluationRegistry, mock_no_asr):
    """Verify versioned atomic promotion activates pointer and rollback restores prior state cleanly."""
    # 1. Register and approve a candidate
    cand = evaluation.CandidateProposal(
        candidate_type="skill",
        target_id="audio.bilingual_preservation",
        version="1.0.1",
        title="Phonetic Vocabulary Enrichment",
        description="Preserves specific technical acronyms.",
        rationale="Benchmark evidence shows AI technical noun integrity.",
        proposed_content="Preserve technical words.",
        status="approved",
    )
    saved = isolated_eval_env.register_candidate(cand)

    # 2. Unapproved candidate cannot be promoted
    unapproved_cand = evaluation.CandidateProposal(
        candidate_type="skill",
        target_id="test_skill",
        version="1.0.0",
        status="proposed",
    )
    unapp_saved = isolated_eval_env.register_candidate(unapproved_cand)
    with pytest.raises(ApiError) as exc_info:
        isolated_eval_env.promote_candidate(unapp_saved.candidate_id, reviewer="lead_human")
    assert exc_info.value.status == 409
    assert exc_info.value.code == "candidate_not_approved"

    # 3. Promote approved candidate
    with patch("backend.skill_registry.SkillRegistry.transition_status") as mock_trans:
        mock_record = MagicMock()
        mock_record.version = "1.0.1"
        mock_trans.return_value = mock_record

        promo = isolated_eval_env.promote_candidate(saved.candidate_id, reviewer="lead_human")
        assert promo["status"] == "promoted"
        assert promo["active_version"] == "1.0.1"

    # 4. Rollback restores previous state and records audit history
    rb = isolated_eval_env.rollback_candidate(saved.candidate_id, reviewer="lead_human", reason="Edge-case regression observed in Telugu accents")
    assert rb["status"] == "rolled_back"
    assert rb["rolled_back_by"] == "lead_human"

    # Verify candidate record retains rollback metadata
    reloaded = isolated_eval_env.get_candidate(saved.candidate_id)
    assert reloaded is not None
    assert reloaded.status == "rolled_back"
    assert "rollback" in reloaded.metadata


def test_unverified_memory_candidate_quarantined_from_retrieval(mock_no_asr):
    """Verify unverified proposed memory candidates cannot be returned in verified retrieval."""
    mem = shared_memory.get_shared_memory()

    # Submit an unverified candidate
    cand = mem.submit_candidate(
        title="Unverified Fast Pace Fact",
        content="Pacing should always run at 2.0x without pause.",
        kind="heuristic",
        owner="experimental_agent",
        scope="global",
        evidence=[{"ref": "exp_run_1"}],
    )
    assert cand.status == "proposed"

    # Querying verified memories must NOT include the unverified candidate
    verified_items = mem.get_verified_memories(scope="global")
    verified_ids = {m.memory_id for m in verified_items}
    assert cand.memory_id not in verified_ids


def test_evaluation_truthful_capability_reporting(isolated_eval_env: evaluation.EvaluationRegistry, mock_no_asr):
    """Verify evaluation results report browser capability accurately without claiming live render is verified."""
    case = isolated_eval_env.get_case("suite-security-gates", "eval-sec-01-safe-react")
    assert case is not None

    res = evaluation.evaluate_case(case, {"code": "export const Scene = () => null;"})
    assert "capabilities" in res.to_dict()
    assert "browser" in res.capabilities
    # When headless Chromium is not preconfigured, browser_ready must be False and limitation disclosed
    if not res.capabilities["browser"]["browser_ready"]:
        assert res.capabilities["browser"]["unresolved_limitation"] is not None


def test_evaluation_api_routes(isolated_eval_env: evaluation.EvaluationRegistry, mock_no_asr):
    """Verify REST API endpoints: /evaluations/suites, /run, /compare, /candidates, /decision, /promote, /rollback."""
    # 1. GET /evaluations/suites
    res = client.get("/evaluations/suites")
    assert res.status_code == 200
    suites = res.json()
    assert len(suites) >= 3

    # 2. POST /evaluations/run
    run_req = {
        "suite_id": "suite-telugu-orthography",
        "case_id": "eval-telugu-01-positive",
        "observed_output": {"transcript": "ఈ రోజు మనము AI మరియు Machine Learning గురించి నేర్చుకుందాము."},
        "save_as_baseline_key": "api_test_baseline",
    }
    res_run = client.post("/evaluations/run", json=run_req)
    assert res_run.status_code == 200
    run_data = res_run.json()
    assert run_data["overall_status"] == "passed"
    assert run_data["hard_gates_passed"] is True

    # 3. POST /evaluations/compare
    comp_req = {
        "baseline_key": "api_test_baseline",
        "candidate_result": run_data,
        "tolerance": 0.05,
    }
    res_comp = client.post("/evaluations/compare", json=comp_req)
    assert res_comp.status_code == 200
    comp_data = res_comp.json()
    assert comp_data["decision"] == "accepted"
    assert comp_data["hard_gate_regression"] is False

    # 4. POST /evaluations/candidates (Propose candidate)
    cand_req = {
        "candidate_type": "skill",
        "target_id": "audio.bilingual_preservation",
        "version": "1.1.0",
        "title": "API Test Candidate",
        "description": "Proposed via REST API",
        "rationale": "Evidence from benchmark evaluation",
        "proposed_content": "Updated rule",
    }
    res_cand = client.post("/evaluations/candidates", json=cand_req)
    assert res_cand.status_code == 201
    cand_id = res_cand.json()["candidate_id"]

    # 5. POST /evaluations/candidates/{id}/decision (Human decision)
    dec_req = {
        "reviewer": "human_reviewer_42",
        "decision": "approved",
        "reason": "Passed all deterministic checks in test suite",
    }
    res_dec = client.post(f"/evaluations/candidates/{cand_id}/decision", json=dec_req)
    assert res_dec.status_code == 200
    assert res_dec.json()["status"] == "approved"

    # 6. POST /evaluations/candidates/{id}/promote
    with patch("backend.skill_registry.SkillRegistry.transition_status") as mock_t:
        rec = MagicMock()
        rec.version = "1.1.0"
        mock_t.return_value = rec

        res_promo = client.post(f"/evaluations/candidates/{cand_id}/promote", json={"reviewer": "human_reviewer_42"})
        assert res_promo.status_code == 200
        assert res_promo.json()["status"] == "promoted"

    # 7. POST /evaluations/candidates/{id}/rollback
    res_rb = client.post(f"/evaluations/candidates/{cand_id}/rollback", json={"reviewer": "human_reviewer_42", "reason": "Test rollback"})
    assert res_rb.status_code == 200
    assert res_rb.json()["status"] == "rolled_back"
