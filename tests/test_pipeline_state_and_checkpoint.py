"""Focused tests for Phase 3: Canonical State, Versioned Contracts, Checkpoint & Recovery."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend import artifact_contracts, llm_review, pipeline_state
from backend.agents import AgentRegistry, AgentRequest, AgentResult, registry
from backend.artifact_contracts import (
    ContractCompatibilityError,
    ContractValidationError,
    validate_stage_artifacts,
    verify_path_confinement,
)
from backend.main import app
from backend.pipeline_state import (
    ACTIVE_STAGES,
    InvalidStateTransitionError,
    PipelineState,
    StageStateRecord,
    compute_checkpoint_id,
    load_pipeline_state,
    reconcile_orphaned_jobs,
    resolve_resume_plan,
    save_pipeline_state,
    transition_stage,
)

client = TestClient(app)


def test_illegal_state_transition_rejected(tmp_path: Path):
    """Verify state transition invariants: illegal direct transitions are rejected."""
    pdir = tmp_path / "trans_proj"
    pdir.mkdir(parents=True, exist_ok=True)

    state = pipeline_state.init_default_state(pdir)
    save_pipeline_state(pdir, state)

    # Cannot transition directly from 'pending' to 'completed' without running
    with pytest.raises(InvalidStateTransitionError, match="cannot move from 'pending' to 'completed'"):
        transition_stage(pdir, "planning", "completed")

    # Can transition from 'pending' to 'running'
    srec = transition_stage(pdir, "planning", "running")
    assert srec.status == "running"
    assert srec.attempt == 1

    # Cannot transition from 'running' to 'pending' directly
    with pytest.raises(InvalidStateTransitionError, match="cannot move from 'running' to 'pending'"):
        transition_stage(pdir, "planning", "pending")


def test_completed_transition_blocks_when_artifacts_missing(tmp_path: Path):
    """Verify that transitioning to completed is strictly blocked if required output artifacts are absent."""
    pdir = tmp_path / "missing_art_proj"
    pdir.mkdir(parents=True, exist_ok=True)

    transition_stage(pdir, "planning", "running")

    # No visual_planning.json or scene_plan.json exists on disk
    with pytest.raises(InvalidStateTransitionError, match="contract check failed"):
        transition_stage(pdir, "planning", "completed")

    # Stage state must fail-closed to blocked
    st = load_pipeline_state(pdir)
    assert st.stages["planning"].status == "blocked"
    assert st.stages["planning"].last_error["code"] == "contract_validation_failed"


def test_completed_transition_blocks_when_llm_review_missing_or_stale(tmp_path: Path, monkeypatch):
    """Verify that completing a stage fails closed if Phase 2 LLM review is absent or stale."""
    pdir = tmp_path / "no_rev_proj"
    pdir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("backend.store.project_dir", lambda p: tmp_path / p)

    # Create dummy valid artifacts
    (pdir / "visual_planning.json").write_text(json.dumps({"scenes": [{"id": 1}]}), encoding="utf-8")
    (pdir / "scene_plan.json").write_text(json.dumps({"scenes": [{"id": 1}]}), encoding="utf-8")
    (pdir / "scene_segmentation.json").write_text(json.dumps({"scenes": [{"id": 1}]}), encoding="utf-8")
    (pdir / "transcript.json").write_text(json.dumps({"text": "Hello world"}), encoding="utf-8")

    transition_stage(pdir, "planning", "running")

    # LLM review has not been run
    with pytest.raises(InvalidStateTransitionError, match="Phase 2 review gate failed"):
        transition_stage(pdir, "planning", "completed")

    st = load_pipeline_state(pdir)
    assert st.stages["planning"].status == "blocked"
    assert "llm_review_gate" in st.stages["planning"].last_error["code"]


def test_completed_transition_succeeds_with_valid_artifacts_and_review(tmp_path: Path, monkeypatch):
    """Verify successful transition to completed records deterministic checkpoint and manifest."""
    pdir = tmp_path / "valid_comp_proj"
    pdir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("backend.store.project_dir", lambda p: tmp_path / p)

    (pdir / "visual_planning.json").write_text(json.dumps({"scenes": [{"id": 1}]}), encoding="utf-8")
    (pdir / "scene_plan.json").write_text(json.dumps({"scenes": [{"id": 1}]}), encoding="utf-8")
    (pdir / "scene_segmentation.json").write_text(json.dumps({"scenes": [{"id": 1}]}), encoding="utf-8")
    (pdir / "transcript.json").write_text(json.dumps({"text": "Hello world"}), encoding="utf-8")

    # Mock gateway execution to pass review
    mock_client = MagicMock()
    mock_client.resolve_provider_config.return_value = ("anthropic", "claude-3-5-sonnet-20241022", "dummy_key", "")
    mock_client.generate_text.return_value = json.dumps({
        "status": "passed",
        "score": 0.92,
        "summary": "Visual planning approved",
        "findings": [],
    })

    with patch("SYSTEM.core.llm_gateway.llm_client", mock_client), patch("backend.llm_gateway.llm_client", mock_client):
        llm_review.run_stage_llm_review(pdir, "planning")

    transition_stage(pdir, "planning", "running")
    srec = transition_stage(pdir, "planning", "completed")

    assert srec.status == "completed"
    assert srec.checkpoint_id != ""
    assert srec.reusable is True
    assert srec.contract_version == 1
    assert len(srec.metadata.get("artifacts", [])) >= 2


def test_path_confinement_rejects_directory_traversal(tmp_path: Path):
    """Verify security check: path traversal attempts outside project directory are rejected."""
    pdir = tmp_path / "safe_proj"
    pdir.mkdir(parents=True, exist_ok=True)

    escaped_target = pdir / ".." / "outside.json"
    with pytest.raises(ContractValidationError, match="Path traversal detected"):
        verify_path_confinement(pdir, escaped_target)


def test_state_persistence_and_monotonic_revision(tmp_path: Path):
    """Verify atomic state persistence and monotonic revision counter increments."""
    pdir = tmp_path / "rev_proj"
    pdir.mkdir(parents=True, exist_ok=True)

    st1 = load_pipeline_state(pdir)
    rev1 = st1.revision

    transition_stage(pdir, "audio", "running")
    st2 = load_pipeline_state(pdir)
    assert st2.revision == rev1 + 1

    transition_stage(pdir, "audio", "failed", error_code="err_test", error_message="Test failure")
    st3 = load_pipeline_state(pdir)
    assert st3.revision == rev1 + 2
    assert st3.stages["audio"].status == "failed"
    assert st3.stages["audio"].last_error["code"] == "err_test"


def test_resume_plan_identifies_earliest_invalid_stage_and_reusable_checkpoints(tmp_path: Path, monkeypatch):
    """Verify resume graph correctly identifies reusable stages, earliest invalid stage, and invalidated downstream closure."""
    pdir = tmp_path / "resume_proj"
    pdir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("backend.store.project_dir", lambda p: tmp_path / p)

    # Setup valid Audio stage
    (pdir / "audio.mp3").write_bytes(b"dummy mp3 audio content bytes for testing")
    mock_client = MagicMock()
    mock_client.resolve_provider_config.return_value = ("anthropic", "claude-3-5-sonnet-20241022", "dummy_key", "")
    mock_client.generate_text.return_value = json.dumps({"status": "passed", "score": 0.95, "findings": []})

    with patch("SYSTEM.core.llm_gateway.llm_client", mock_client), patch("backend.llm_gateway.llm_client", mock_client):
        llm_review.run_stage_llm_review(pdir, "audio")

    transition_stage(pdir, "audio", "running")
    transition_stage(pdir, "audio", "completed")

    # Analyzer stage is not yet completed (pending)
    plan = resolve_resume_plan(pdir, aspect="16:9")

    assert plan["earliest_invalid_stage"] == "analyzer"
    assert plan["reusable_count"] == 1
    assert plan["reusable_checkpoints"][0]["stage_id"] == "audio"
    assert "analyzer" in plan["invalidated_stages"]
    assert "segmentation" in plan["invalidated_stages"]
    assert "final" in plan["invalidated_stages"]
    assert plan["can_resume"] is True


def test_stale_fingerprint_invalidates_checkpoint_in_resume_plan(tmp_path: Path, monkeypatch):
    """Verify that modifying an input or output file invalidates the checkpoint during resume evaluation."""
    pdir = tmp_path / "stale_plan_proj"
    pdir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("backend.store.project_dir", lambda p: tmp_path / p)

    # Complete audio stage
    audio_file = pdir / "audio.mp3"
    audio_file.write_bytes(b"initial audio content")

    mock_client = MagicMock()
    mock_client.resolve_provider_config.return_value = ("anthropic", "claude-3-5-sonnet-20241022", "dummy_key", "")
    mock_client.generate_text.return_value = json.dumps({"status": "passed", "score": 0.95, "findings": []})

    with patch("SYSTEM.core.llm_gateway.llm_client", mock_client), patch("backend.llm_gateway.llm_client", mock_client):
        llm_review.run_stage_llm_review(pdir, "audio")

    transition_stage(pdir, "audio", "running")
    transition_stage(pdir, "audio", "completed")

    # Verify initially reusable
    plan1 = resolve_resume_plan(pdir, aspect="16:9")
    assert plan1["reusable_count"] == 1
    assert plan1["reusable_checkpoints"][0]["stage_id"] == "audio"

    # Modify audio file -> causes stale input/output fingerprint
    audio_file.write_bytes(b"modified audio content with new bytes")

    plan2 = resolve_resume_plan(pdir, aspect="16:9")
    # Audio is now invalidated and becomes earliest invalid stage!
    assert plan2["earliest_invalid_stage"] == "audio"
    assert plan2["reusable_count"] == 0
    assert "stale" in plan2["invalidation_reason"]


def test_reconcile_orphaned_jobs_recovers_process_restart(tmp_path: Path, monkeypatch):
    """Verify that process restarts recover orphan running stages without false completion."""
    pdir = tmp_path / "orphan_proj"
    pdir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("backend.store.project_dir", lambda p: tmp_path / p)

    # Manually simulate a stage left in running state before restart
    transition_stage(pdir, "motion_plan", "running")
    st = load_pipeline_state(pdir)
    assert st.stages["motion_plan"].status == "running"

    # In a fresh server process, no background thread owns this job
    reconciled = reconcile_orphaned_jobs(pdir)
    assert "motion_plan" in reconciled

    st_after = load_pipeline_state(pdir)
    assert st_after.stages["motion_plan"].status == "failed"
    assert st_after.stages["motion_plan"].last_error["code"] == "interrupted_by_process_restart"


def test_concurrency_serialization_on_project_state(tmp_path: Path):
    """Verify multi-threaded transitions serialize properly and preserve state integrity."""
    pdir = tmp_path / "concurrent_proj"
    pdir.mkdir(parents=True, exist_ok=True)

    num_threads = 6
    iterations_per_thread = 10

    def worker(idx: int):
        for _ in range(iterations_per_thread):
            pipeline_state.update_pipeline_state(pdir, lambda st: None)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    final_state = load_pipeline_state(pdir)
    assert final_state.revision >= num_threads * iterations_per_thread


def test_pipeline_state_routes(tmp_path: Path, monkeypatch):
    """Verify FastAPI routes /projects/{pid}/state and /projects/{pid}/resume-plan."""
    pid = "route-state-proj"
    pdir = tmp_path / pid
    pdir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("backend.store.project_dir", lambda p: tmp_path / p)

    # GET /state
    res_state = client.get(f"/projects/{pid}/state")
    assert res_state.status_code == 200
    data = res_state.json()
    assert data["schema"] == "pipeline-state"
    assert data["project_id"] == pid
    assert "stages" in data
    assert "planning" in data["stages"]

    # GET /resume-plan
    res_plan = client.get(f"/projects/{pid}/resume-plan")
    assert res_plan.status_code == 200
    plan = res_plan.json()
    assert plan["project_id"] == pid
    assert plan["earliest_invalid_stage"] == "audio"
    assert plan["reusable_count"] == 0
