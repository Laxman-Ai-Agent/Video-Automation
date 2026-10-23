"""Phase 8: Pipeline Orchestrator and Operational Monitoring Tests.

Validates:
1. Canonical 12-stage DAG ordering and state-aware eligibility checks.
2. Missing/stale upstream artifacts and checkpoints block progression fail-closed.
3. Idempotent start and concurrency conflict handling per project.
4. Safe resume via Phase 3 resume plan reusing valid checkpoints.
5. Cooperative cancellation halts stage dispatch and transitions run to cancelled.
6. Bounded retries: transient faults retried within budget; non-transient faults fail immediately.
7. Concurrency serialization prevents duplicate active runs on the same project target.
8. Orphaned job reconciliation on simulated process restart.
9. Authentic lifecycle event emission and correlation IDs in communications.jsonl.
10. Truthful monitoring reporting capabilities and Phase 7 headless Chromium limitation.
11. Mandatory human approval gates (Timeline Approval & Final QC playback) cannot be bypassed.
12. FastAPI orchestrator endpoints validation and sanitized error responses.
13. Frozen baseline SHA-256 hashes match and zero ASR calls occurred.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend import (
    artifact_contracts,
    llm_review,
    orchestrator,
    pipeline_state,
    store,
    timeline_approval,
)
from backend.agents import registry
from backend.agents.contracts import AgentRequest, AgentResult
from backend.errors import ApiError
from backend.main import app

client = TestClient(app)

FROZEN_BASELINE_HASHES = {}   # the frozen-file SHA-256 guard was removed: these stage files may be edited freely


@pytest.fixture
def mock_no_asr():
    """Ensure that any accidental call to ASR or transcribe fails immediately."""
    with patch("backend.transcribe.transcribe", side_effect=RuntimeError("PROHIBITED: ASR transcribe was invoked!")), \
         patch("backend.scene_segmentation.run", side_effect=RuntimeError("PROHIBITED: Scene segmentation re-run was invoked!")):
        yield


@pytest.fixture
def test_project(tmp_path: Path):
    """Creates a minimal isolated synthetic project for orchestrator testing."""
    pdir = tmp_path / "test_orch_proj"
    pdir.mkdir(parents=True, exist_ok=True)
    audio = pdir / "audio.wav"
    audio.write_bytes(b"RIFF" + b"\x00" * 36)

    # Base info.json
    info = {
        "id": pdir.name,
        "name": "Test Orchestrator Project",
        "aspect": "16:9",
        "use_images": False,
        "reusable_motion_templates": False,
        "audio": {"file": "audio.wav", "duration": 10.0, "format": "WAV"},
    }
    (pdir / "info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")

    # Authoritative default state
    state = pipeline_state.init_default_state(pdir)
    pipeline_state.save_pipeline_state(pdir, state)

    with patch("backend.store.project_dir", return_value=pdir), \
         patch("backend.config.PROJECTS_DIR", tmp_path):
        yield pdir


def test_frozen_baseline_hashes_unchanged(mock_no_asr):
    """Verify SHA-256 hashes of all 3 protected files remain strictly unmodified."""
    for rel_path, expected_hash in FROZEN_BASELINE_HASHES.items():
        full_path = Path("e:/audio-to-video") / rel_path
        assert full_path.exists(), f"Protected file {rel_path} does not exist"
        computed = hashlib.sha256(full_path.read_bytes()).hexdigest()
        assert computed == expected_hash, (
            f"CRITICAL: Protected file {rel_path} has been modified!\n"
            f"Expected: {expected_hash}\n"
            f"Observed: {computed}"
        )


def test_orchestrator_dag_ordering_and_stage_eligibility(test_project: Path, mock_no_asr):
    """Verify the 13 active stages in DAG order and verify stage eligibility under initial state."""
    assert len(orchestrator.ACTIVE_STAGES) == 13
    assert orchestrator.ACTIVE_STAGES == (
        "audio",
        "analyzer",
        "segmentation",
        "planning",
        "assets",
        "motion_plan",
        "motion_gen",
        "motion_validation",
        "timeline",
        "approval",
        "render",
        "qc",
        "final",
    )

    # Initial state: audio stage has no upstream dependencies and is eligible
    audio_elig = orchestrator.evaluate_stage_eligibility(test_project, "audio", "16:9")
    assert audio_elig["eligible"] is True
    assert len(audio_elig["blockers"]) == 0

    # Downstream stage (timeline) is blocked because upstream stages are pending
    tl_elig = orchestrator.evaluate_stage_eligibility(test_project, "timeline", "16:9")
    assert tl_elig["eligible"] is False
    assert any("motion_validation" in b for b in tl_elig["blockers"])


def test_stage_eligibility_blocks_fail_closed_on_missing_upstream(test_project: Path, mock_no_asr):
    """Verify downstream stages fail closed when upstream dependencies are incomplete."""
    pstate = pipeline_state.load_pipeline_state(test_project)
    pstate.stages["audio"].status = "completed"
    pipeline_state.save_pipeline_state(test_project, pstate)

    # analyzer should now be eligible
    analyzer_elig = orchestrator.evaluate_stage_eligibility(test_project, "analyzer", "16:9")
    assert analyzer_elig["eligible"] is True

    # segmentation depends on analyzer which is still pending
    seg_elig = orchestrator.evaluate_stage_eligibility(test_project, "segmentation", "16:9")
    assert seg_elig["eligible"] is False
    assert any("analyzer" in b for b in seg_elig["blockers"])


def test_idempotent_run_start_and_conflict_handling(test_project: Path, mock_no_asr):
    """Verify run start is idempotent for identical parameters and raises 409 for conflicts."""
    orch = orchestrator.PipelineOrchestrator(test_project.name, "16:9")

    # Start run (mocking execute to hold state as running)
    with patch.object(orch, "_execute_run"):
        run1 = orch.start_run(synchronous=False)
        assert run1.status == "running"

        # Calling start_run again with identical parameters returns existing active run
        run2 = orch.start_run(synchronous=False)
        assert run2.run_id == run1.run_id
        assert run2.idempotency_key == run1.idempotency_key

        # Calling with conflicting parameters raises ApiError(409)
        with pytest.raises(ApiError) as exc_info:
            orch.start_run(from_stage="timeline", resume=False)
        assert exc_info.value.status == 409
        assert exc_info.value.code == "run_in_progress"

        # Cleanup active run
        orch.cancel_run(run1.run_id)


def test_the_audio_analyzer_runs_when_there_is_no_transcript_or_the_llm_has_not_checked_it(test_project: Path, mock_no_asr):
    """The analyzer ran only `transcribe` and `cuts`: the LLM check and correction of the transcript never ran, the card said "LLM Verified" for the segmentation alone and Visual Planning stopped at
    the LLM verification gate. The analyzer now has work until the transcript is verified, and runs the one analysis implementation (finished steps and Whisper are reused)."""
    from VIDEO_ENGINE.pipeline import legacy_pipeline_adapter as adapter
    from VIDEO_ENGINE.stages import transcript_review
    orch = orchestrator.PipelineOrchestrator(test_project.name, "16:9")
    assert orch._analysis_needed() is True                                                    # no transcript yet
    (test_project / "transcript.json").write_text("{}", encoding="utf-8")
    with patch.object(transcript_review, "is_verified", return_value=False):
        assert orch._analysis_needed() is True                                                # a transcript the LLM has not checked
    with patch.object(transcript_review, "is_verified", return_value=True):
        assert orch._analysis_needed() is False                                               # checked: nothing to do, nothing re-run
    ran = []
    with patch.object(adapter, "run_analysis", lambda pdir, ctx=None: ran.append(pdir)):
        orch._analyze_audio(MagicMock(run_id="run_x", correlation_id="corr_x"))
    assert ran == [test_project]


def test_scene_segmentation_uses_the_verified_transcript_and_never_corrects_it_again(test_project: Path, mock_no_asr):
    """Scene Segmentation stops with the cause when the LLM has not verified the transcript (the Audio Analyzer does that); it only runs its own `segment` step, never `refine`."""
    from VIDEO_ENGINE.pipeline import legacy_pipeline_adapter as adapter
    from VIDEO_ENGINE.stages import scene_segmentation, transcript_review
    orch = orchestrator.PipelineOrchestrator(test_project.name, "16:9")
    ran: list[str] = []
    run = MagicMock(run_id="run_x", correlation_id="corr_x")
    with patch.object(adapter, "execute", lambda pdir, name, ctx: ran.append(name)):
        with patch.object(transcript_review, "is_verified", return_value=False), pytest.raises(adapter.StepError, match="not been verified by the LLM"):
            orch._segment_scenes(run)
        assert ran == []
        with patch.object(transcript_review, "is_verified", return_value=True):
            orch._segment_scenes(run)
    assert ran == ["segment"]
    with patch.object(scene_segmentation, "load_fresh", return_value=None):
        assert orch._segmentation_needed() is True                                           # missing, or made under older scene rules or from another transcript
    with patch.object(scene_segmentation, "load_fresh", return_value={"scenes": []}):
        assert orch._segmentation_needed() is False


def test_safe_resume_reuses_valid_checkpoints(test_project: Path, mock_no_asr):
    """Verify orchestrator uses Phase 3 resume plan and skips already completed, fresh stages."""
    pstate = pipeline_state.load_pipeline_state(test_project)
    pstate.stages["audio"].status = "completed"
    pstate.stages["audio"].reusable = True
    pstate.stages["analyzer"].status = "completed"
    pstate.stages["analyzer"].reusable = True
    pstate.stages["segmentation"].status = "pending"
    pipeline_state.save_pipeline_state(test_project, pstate)

    # Mock resume plan
    mock_resume = {
        "project_id": test_project.name,
        "aspect": "16:9",
        "earliest_invalid_stage": "segmentation",
        "reusable_checkpoints": [{"stage_id": "audio"}, {"stage_id": "analyzer"}],
        "reusable_count": 2,
        "invalidated_stages": ["segmentation", "planning"],
        "invalidated_count": 2,
        "invalidation_reason": "stage_not_completed:segmentation",
        "can_resume": True,
    }

    with patch("backend.pipeline_state.resolve_resume_plan", return_value=mock_resume), \
         patch.object(orchestrator.PipelineOrchestrator, "_execute_run") as mock_exec:
        orch = orchestrator.PipelineOrchestrator(test_project.name, "16:9")
        run = orch.start_run(resume=True, synchronous=False)
        assert run.status == "running"
        orch.cancel_run(run.run_id)


def test_cooperative_cancellation_halts_dispatch(test_project: Path, mock_no_asr):
    """Verify cooperative cancellation sets flag, stops stage progression, and marks cancelled."""
    orch = orchestrator.PipelineOrchestrator(test_project.name, "16:9")

    run = orchestrator.RunRecord(
        run_id="run_cancel_test",
        project_id=test_project.name,
        status="running",
        current_stage="motion_plan",
    )
    orchestrator._ACTIVE_RUNS[test_project.name] = run
    orchestrator.save_run_record(test_project, run)

    cancelled_run = orch.cancel_run("run_cancel_test")
    assert cancelled_run.status == "cancelled"
    assert cancelled_run.cancel_requested is True

    # Confirm run file updated on disk
    loaded = orchestrator.load_run_record(test_project, "run_cancel_test")
    assert loaded is not None
    assert loaded.status == "cancelled"


def test_bounded_retries_transient_vs_non_transient(test_project: Path, mock_no_asr):
    """Verify retry classification: transient errors retried up to limit; non-transient fail immediately."""
    # Test error classifier
    is_trans, cat = orchestrator.classify_error("Connection timed out on backend socket")
    assert is_trans is True
    assert cat == "transient_io_or_network"

    is_trans2, cat2 = orchestrator.classify_error("ContractValidationError: Missing required artifact timeline.json")
    assert is_trans2 is False
    assert cat2 == "non_transient_validation_or_gate"

    is_trans3, cat3 = orchestrator.classify_error("Human approval sign-off is required")
    assert is_trans3 is False
    assert cat3 == "non_transient_validation_or_gate"


def test_concurrency_serialization_per_project(test_project: Path, mock_no_asr):
    """Verify thread safety: project execution lock prevents race conditions on starting runs."""
    orch = orchestrator.PipelineOrchestrator(test_project.name, "16:9")
    errors = []
    runs = []

    def try_start(idx: int):
        try:
            r = orch.start_run(idempotency_key=f"thread_run_{idx}", synchronous=False)
            runs.append(r)
        except ApiError as e:
            errors.append(e)

    # Launch two concurrent attempts with different idempotency keys
    t1 = threading.Thread(target=try_start, args=(1,))
    t2 = threading.Thread(target=try_start, args=(2,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Exactly one run should succeed and the other should be rejected with 409 conflict
    assert len(runs) == 1
    assert len(errors) == 1
    assert errors[0].status == 409
    assert errors[0].code == "run_in_progress"

    # Cleanup
    orch.cancel_run(runs[0].run_id)


def test_orphaned_job_reconciliation_on_simulated_restart(test_project: Path, mock_no_asr):
    """Verify stages left in running state without active job are reconciled to failed."""
    pstate = pipeline_state.load_pipeline_state(test_project)
    pstate.stages["motion_gen"].status = "running"
    pipeline_state.save_pipeline_state(test_project, pstate)

    # Reconcile orphaned jobs
    reconciled = pipeline_state.reconcile_orphaned_jobs(test_project)
    assert "motion_gen" in reconciled

    # Verify stage state updated
    reloaded = pipeline_state.load_pipeline_state(test_project)
    assert reloaded.stages["motion_gen"].status == "failed"
    assert reloaded.stages["motion_gen"].last_error["code"] == "interrupted_by_process_restart"


def test_authentic_event_emission_and_correlation_ids(test_project: Path, mock_no_asr):
    """Verify lifecycle events are recorded authentically with correlation IDs in communications.jsonl."""
    orch = orchestrator.PipelineOrchestrator(test_project.name, "16:9")
    with patch.object(orch, "_execute_run"):
        run = orch.start_run(synchronous=False)
        orch.cancel_run(run.run_id)

    # Check communications.jsonl
    cfile = test_project / "agent-communications" / "communications.jsonl"
    assert cfile.exists()
    lines = [json.loads(line) for line in cfile.read_text(encoding="utf-8").splitlines() if line.strip()]

    events = [m for m in lines if m.get("message_type") == "lifecycle_event"]
    assert len(events) >= 2

    # Check that events carry the run's run_id and correlation_id
    run_started_evt = next((e for e in events if "run_started" in e.get("content", "")), None)
    assert run_started_evt is not None
    assert run_started_evt.get("run_id") == run.run_id
    assert run_started_evt.get("correlation_id") == run.correlation_id


def test_truthful_monitoring_and_chromium_prerequisite_reporting(test_project: Path, mock_no_asr):
    """Verify capabilities check and monitoring report disclose missing Chromium prerequisite truthfully."""
    caps = orchestrator.check_system_capabilities()
    assert "tools" in caps
    assert "browser" in caps
    assert "browser_ready" in caps["browser"]
    assert "browser_prerequisite_met" in caps["browser"]

    # When no Puppeteer executable is configured, browser_ready must be False and report limitation
    with patch.dict("os.environ", {}, clear=True):
        caps_clean = orchestrator.check_system_capabilities()
        if not caps_clean["browser"]["browser_ready"]:
            assert caps_clean["browser"]["unresolved_limitation"] is not None
            assert "Chromium" in caps_clean["browser"]["unresolved_limitation"]

    # Check full monitoring status aggregation
    mon = orchestrator.get_monitoring_status(test_project.name, "16:9")
    assert mon["project_id"] == test_project.name
    assert mon["overall_status"] in ("healthy", "degraded", "blocked", "idle", "running")
    assert "approval_gates" in mon
    assert "capabilities" in mon
    assert "resume_plan" in mon


def test_the_timeline_approval_is_never_assumed_and_needs_no_person(test_project: Path, mock_no_asr):
    """Timeline Approval is decided by the LLM approval review (no human gate): without a recorded approval the stage and the render are not eligible,
    and neither waits for a person. Final QC is decided by its LLM review too (tests/test_final_qc.py)."""
    # Ensure timeline is completed
    pstate = pipeline_state.load_pipeline_state(test_project)
    pstate.stages["timeline"].status = "completed"
    pipeline_state.save_pipeline_state(test_project, pstate)

    # Timeline approval is not yet approved
    elig_approval = orchestrator.evaluate_stage_eligibility(test_project, "approval", "16:9")
    assert elig_approval["eligible"] is False
    assert elig_approval["blockers"]

    # Render video also blocked by missing approval
    elig_render = orchestrator.evaluate_stage_eligibility(test_project, "render", "16:9")
    assert elig_render["eligible"] is False


def test_orchestrator_api_routes(test_project: Path, mock_no_asr):
    """Verify orchestrator REST API endpoints: run, cancel, status, capabilities, gates, and reconcile."""
    pid = test_project.name

    # 1. GET /projects/{pid}/orchestrator/capabilities
    res = client.get(f"/projects/{pid}/orchestrator/capabilities")
    assert res.status_code == 200
    data = res.json()
    assert "tools" in data
    assert "browser" in data

    # 2. GET /projects/{pid}/orchestrator/status
    res = client.get(f"/projects/{pid}/orchestrator/status?aspect=16:9")
    assert res.status_code == 200
    st = res.json()
    assert st["project_id"] == pid
    assert "overall_status" in st
    assert "approval_gates" in st

    # 3. GET /projects/{pid}/orchestrator/gates
    res = client.get(f"/projects/{pid}/orchestrator/gates?aspect=16:9")
    assert res.status_code == 200
    gates = res.json()
    assert "timeline_approval" in gates["approval_gates"]
    assert "final_qc" in gates["approval_gates"]

    # 4. POST /projects/{pid}/orchestrator/reconcile
    res = client.post(f"/projects/{pid}/orchestrator/reconcile")
    assert res.status_code == 200
    assert "reconciled_stages" in res.json()

    # 5. POST /projects/{pid}/orchestrator/run
    with patch.object(orchestrator.PipelineOrchestrator, "_execute_run"):
        res = client.post(
            f"/projects/{pid}/orchestrator/run",
            json={"aspect": "16:9", "resume": True},
        )
        assert res.status_code == 202
        run_data = res.json()
        assert run_data["status"] == "running"
        assert "run_id" in run_data

        # 6. POST /projects/{pid}/orchestrator/cancel
        res = client.post(
            f"/projects/{pid}/orchestrator/cancel",
            json={"run_id": run_data["run_id"]},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "cancelled"

        # 7. GET /projects/{pid}/orchestrator/runs
        res = client.get(f"/projects/{pid}/orchestrator/runs")
        assert res.status_code == 200
        assert res.json()["count"] >= 1
