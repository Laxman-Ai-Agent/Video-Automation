"""Acceptance Test Suite for Stage 8: Autonomous Failure Recovery, Resilience & System Hardening.

Covers:
- Group A: Error Classification & Bounded Retry Matrix
- Group B: Checkpoint Integrity & Path Confinement
- Group C: Process Crash Reconciliation & Concurrency Guards
- Group D: Stage Failure Isolation & Cleanup
- Group E: External Provider Circuit Breaker
- Group F: Telugu Activity Recovery Stream & Secret Redaction
"""
import json
import os
import shutil
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from SYSTEM.core.resilience import (
    ErrorCategory,
    FailureDiagnostic,
    classify_error,
    is_retry_permitted,
    calculate_backoff,
    CircuitBreaker,
    CircuitBreakerOpenError,
    validate_checkpoint_deep,
    verify_path_confinement,
    reconcile_interrupted_run,
    get_project_mutex,
    sanitize_secrets,
    record_recovery_experience,
)
from SYSTEM.agents.shared.telugu_activity_mapper import (
    MILESTONE_MESSAGES,
    telugu_activity_mapper,
    map_activity,
)
from SYSTEM.core import pipeline_state
from VIDEO_ENGINE.pipeline import orchestrator
from SYSTEM.core.llm_gateway import LlmGateway, LlmGatewayRequest, get_gateway


@pytest.fixture
def temp_project(tmp_path: Path):
    """Creates a mock project directory with pipeline_state.json and project.json."""
    pdir = tmp_path / "test_proj_stage8"
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "project.json").write_text(json.dumps({"id": pdir.name, "state": "created"}), encoding="utf-8")
    state = pipeline_state.load_pipeline_state(pdir)
    return pdir


# ==============================================================================
# GROUP A: Error Classification & Bounded Retry Matrix
# ==============================================================================

class TestGroupAErrorClassificationAndRetry:

    def test_transient_error_classification(self):
        """Transient network errors, 429, 503, and timeouts must be classified as retry-eligible."""
        for err in [
            ConnectionResetError("Connection reset by peer"),
            "HTTP 429: Too Many Requests",
            "503 Service Unavailable",
            TimeoutError("Operation timed out after 30s"),
            "rate limit exceeded",
        ]:
            cat, code, retry_eligible = classify_error(err)
            assert retry_eligible is True, f"Expected {err} to be retry eligible"
            assert cat in (ErrorCategory.TRANSIENT, ErrorCategory.TIMEOUT), f"Unexpected cat: {cat}"

    def test_deterministic_validation_error_classification(self):
        """Contract, schema, and validation errors must NOT be retry-eligible."""
        for err in [
            ValueError("Invalid schema: missing field 'resolution'"),
            "Contract violation: spec hash mismatch",
            TypeError("unhashable type: 'dict'"),
            "400 Bad Request: validation error",
        ]:
            cat, code, retry_eligible = classify_error(err)
            assert retry_eligible is False, f"Expected {err} to NOT be retry eligible"
            assert cat == ErrorCategory.VALIDATION

    def test_security_error_classification_and_denial(self):
        """Security violations, forbidden actions, and path traversal must be classified as SECURITY and never retried."""
        for err in [
            PermissionError("Security Policy Denied: execution forbidden"),
            "Path traversal attempt detected",
            "Forbidden access to protected file",
            "403 Forbidden",
            "unauthorized",
        ]:
            cat, code, retry_eligible = classify_error(err)
            assert retry_eligible is False
            assert cat == ErrorCategory.SECURITY
            permitted, reason = is_retry_permitted(cat, current_attempt=1)
            assert permitted is False
            assert "cannot be retried" in reason or "SECURITY" in reason

    def test_bounded_retry_budget_enforcement(self):
        """Transient errors may only be retried up to MAX_RETRY_LIMIT (3 attempts)."""
        cat = ErrorCategory.TRANSIENT

        # Attempt 1 -> permitted (attempt 2)
        permitted, _ = is_retry_permitted(cat, current_attempt=1, max_retries=3)
        assert permitted is True

        # Attempt 2 -> permitted (attempt 3)
        permitted, _ = is_retry_permitted(cat, current_attempt=2, max_retries=3)
        assert permitted is True

        # Attempt 3 -> budget exhausted, rejected!
        permitted, reason = is_retry_permitted(cat, current_attempt=3, max_retries=3)
        assert permitted is False
        assert "limit reached" in reason

    def test_jittered_backoff_bounds(self):
        """Backoff calculation must be bounded between 0.5 * delay and max delay with jitter."""
        for attempt in range(1, 5):
            delay = calculate_backoff(attempt, base_seconds=0.5, max_seconds=4.0, jitter=True)
            assert 0.1 <= delay <= 4.0, f"Delay {delay} out of bounds for attempt {attempt}"


# ==============================================================================
# GROUP B: Checkpoint Integrity & Path Confinement
# ==============================================================================

class TestGroupBCheckpointIntegrityAndPathConfinement:

    def test_path_confinement_guards_against_traversal(self, temp_project: Path):
        """Target files resolving outside project root must raise PermissionError."""
        safe_path = temp_project / "artifacts" / "audio.json"
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        safe_path.write_text("{}", encoding="utf-8")

        # Confinement within base succeeds
        verify_path_confinement(temp_project, safe_path)

        # Path traversal outside base fails
        traversal_path = temp_project / ".." / "system32" / "cmd.exe"
        with pytest.raises(PermissionError) as exc_info:
            verify_path_confinement(temp_project, traversal_path)
        assert "Path traversal attempt" in str(exc_info.value)

    def test_validate_checkpoint_deep_validates_artifacts(self, temp_project: Path):
        """validate_checkpoint_deep must verify state existence, stage record, and artifact health."""
        # Setup valid state and valid artifact
        state = pipeline_state.load_pipeline_state(temp_project)
        art_rel = "artifacts/audio/audio_meta.json"
        art_file = temp_project / art_rel
        art_file.parent.mkdir(parents=True, exist_ok=True)
        art_file.write_text(json.dumps({"duration": 12.5}), encoding="utf-8")

        state.stages["audio"].status = "completed"
        state.stages["audio"].metadata["artifacts"] = [{"path": art_rel}]
        pipeline_state.save_pipeline_state(temp_project, state)

        # Validate healthy checkpoint
        is_valid, issues, meta = validate_checkpoint_deep(temp_project, "audio")
        assert is_valid is True
        assert len(issues) == 0
        assert meta["status"] == "completed"

    def test_validate_checkpoint_deep_flags_corrupt_or_empty_artifact(self, temp_project: Path):
        """Zero-byte or missing referenced artifacts must invalidate checkpoint."""
        state = pipeline_state.load_pipeline_state(temp_project)
        art_rel = "artifacts/analyzer/analysis.json"
        art_file = temp_project / art_rel
        art_file.parent.mkdir(parents=True, exist_ok=True)
        art_file.write_text("", encoding="utf-8")  # 0 bytes

        state.stages["analyzer"].status = "completed"
        state.stages["analyzer"].metadata["artifacts"] = [{"path": art_rel}]
        pipeline_state.save_pipeline_state(temp_project, state)

        is_valid, issues, _ = validate_checkpoint_deep(temp_project, "analyzer")
        assert is_valid is False
        assert any("empty" in issue for issue in issues)


# ==============================================================================
# GROUP C: Process Crash Reconciliation & Concurrency Guards
# ==============================================================================

class TestGroupCCrashReconciliationAndConcurrency:

    def test_reconcile_interrupted_run_resets_running_stages(self, temp_project: Path):
        """Stages left in 'running' state after server restart must be safely marked 'failed'."""
        state = pipeline_state.load_pipeline_state(temp_project)
        # Stage 'audio' completed
        state.stages["audio"].status = "completed"
        # Stage 'analyzer' was running when process terminated
        state.stages["analyzer"].status = "running"
        pipeline_state.save_pipeline_state(temp_project, state)

        reconcile_info = reconcile_interrupted_run(temp_project, temp_project.name)

        assert "analyzer" in reconcile_info["reconciled_stages"]
        updated_state = pipeline_state.load_pipeline_state(temp_project)
        assert updated_state.stages["analyzer"].status == "failed"
        assert updated_state.stages["analyzer"].last_error["code"] == "interrupted_by_crash"
        # Completed stage 'audio' preserved
        assert updated_state.stages["audio"].status == "completed"

    def test_get_project_mutex_serializes_same_project(self):
        """Multiple calls to get_project_mutex for the same project must return identical mutex."""
        m1 = get_project_mutex("proj_abc")
        m2 = get_project_mutex("proj_abc")
        assert m1 is m2
        m3 = get_project_mutex("proj_xyz")
        assert m1 is not m3


# ==============================================================================
# GROUP D: Stage Failure Isolation & Cleanup
# ==============================================================================

class TestGroupDStageFailureIsolation:

    def test_stage_failure_preserves_upstream_state(self, temp_project: Path):
        """When an adapter fails permanently, it must record FailureDiagnostic and not corrupt earlier stages."""
        # Mark audio completed
        state = pipeline_state.load_pipeline_state(temp_project)
        state.stages["audio"].status = "completed"
        pipeline_state.save_pipeline_state(temp_project, state)

        # Mock adapter for analyzer to raise non-retryable validation error
        mock_adapter = MagicMock()
        mock_adapter.validate.return_value = ["Contract violation: bad audio channels"]

        with patch("SYSTEM.memory.store.project_dir", return_value=temp_project), \
             patch("VIDEO_ENGINE.pipeline.orchestrator.store.project_dir", return_value=temp_project), \
             patch("SYSTEM.registries.agent_registry.registry.get_adapter", return_value=mock_adapter):
            orch = orchestrator.PipelineOrchestrator(temp_project.name)
            run = orch.start_run(from_stage="analyzer", synchronous=True, max_retries=1)

        assert run.status == "failed"
        assert "analyzer" in run.stages_failed
        # Audio remains completed in state
        final_state = pipeline_state.load_pipeline_state(temp_project)
        assert final_state.stages["audio"].status == "completed"
        assert final_state.stages["analyzer"].status == "failed"


# ==============================================================================
# GROUP E: External Provider Circuit Breaker
# ==============================================================================

class TestGroupECircuitBreaker:

    def test_circuit_breaker_trips_to_open_after_threshold(self):
        """Circuit breaker must trip to OPEN after 3 consecutive failures."""
        cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=10.0)
        provider = "test_llm_provider"

        # Initial state CLOSED
        can_exec, status = cb.can_execute(provider)
        assert can_exec is True
        assert "CLOSED" in status

        # 1st failure
        cb.record_failure(provider, error="503 Service Unavailable")
        assert cb.get_status(provider)["state"] == "CLOSED"

        # 2nd failure
        cb.record_failure(provider, error="503 Service Unavailable")
        assert cb.get_status(provider)["state"] == "CLOSED"

        # 3rd failure -> trips to OPEN
        cb.record_failure(provider, error="503 Service Unavailable")
        assert cb.get_status(provider)["state"] == "OPEN"

        # Next call must be blocked fast
        can_exec, status = cb.can_execute(provider)
        assert can_exec is False
        assert "OPEN" in status
        assert "Cooldown" in status

    def test_circuit_breaker_half_open_and_recovery(self):
        """After cooldown, breaker enters HALF_OPEN and resets to CLOSED on success."""
        cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=0.1)
        provider = "test_llm_fast_cooldown"

        cb.record_failure(provider, error="Timeout")
        cb.record_failure(provider, error="Timeout")
        assert cb.get_status(provider)["state"] == "OPEN"

        # Wait for cooldown to expire
        time.sleep(0.15)

        # First call probes HALF_OPEN
        can_exec, status = cb.can_execute(provider)
        assert can_exec is True
        assert "HALF_OPEN" in status

        # Success resets to CLOSED
        cb.record_success(provider)
        assert cb.get_status(provider)["state"] == "CLOSED"
        assert cb.get_status(provider)["consecutive_failures"] == 0

    def test_llm_gateway_integration_with_circuit_breaker(self):
        """LlmGateway must fast-reject requests when provider circuit is OPEN."""
        from SYSTEM.core.resilience import circuit_breaker
        circuit_breaker.reset()

        gw = LlmGateway()
        # Mock client to fail 3 times
        mock_client = MagicMock()
        mock_client.resolve_provider_config.return_value = ("test_prov", "model_x", "k", "http://localhost")
        mock_client.generate_text.side_effect = RuntimeError("503 Gateway Down")
        gw.client = mock_client

        req = LlmGatewayRequest(
            project_id="p1",
            stage_id="planning",
            agent_id="visual_planning",
            purpose="generation",
            user_prompt="Hello",
            max_retries=0,
        )

        # Trigger failures to trip circuit
        for _ in range(3):
            res = gw.execute(req)
            assert res.status == "blocked"

        # Circuit should now be OPEN
        status = circuit_breaker.get_status("test_prov", "model_x")
        assert status["state"] == "OPEN"

        # Subsequent call must fast-fail without calling generate_text
        mock_client.generate_text.reset_mock()
        fast_res = gw.execute(req)
        assert fast_res.status == "blocked"
        assert "OPEN" in str(fast_res.error)
        mock_client.generate_text.assert_not_called()

        # Clean up
        circuit_breaker.reset()


# ==============================================================================
# GROUP F: Telugu Activity Recovery Stream & Secret Redaction
# ==============================================================================

class TestGroupFTeluguRecoveryAndSecretRedaction:

    def test_telugu_recovery_milestones_mapped_truthfully(self):
        """All canonical recovery lifecycle events must map directly to explicit Telugu phrases."""
        expected_mappings = {
            "recovery_detected": "సమస్యను గుర్తించాను. కారణాన్ని పరిశీలిస్తున్నాను.",
            "recovery_safe_to_retry": "మళ్లీ ప్రయత్నించడం సురక్షితమని నిర్ధారించాను.",
            "recovery_retrying": "మళ్లీ ప్రయత్నిస్తున్నాను.",
            "recovery_resume_checkpoint": "చివరిగా ధృవీకరించిన దశ నుంచి పనిని కొనసాగిస్తున్నాను.",
            "recovery_verified_previous": "మునుపటి పని విజయవంతంగా పూర్తైందని నిర్ధారించాను.",
            "recovery_unresolvable": "సమస్యను స్వయంగా పరిష్కరించలేకపోయాను. అదనపు పరిశీలన అవసరం.",
            "recovery_needs_review": "ఈ పనిని సురక్షితంగా కొనసాగించలేను. అదనపు పరిశీలన అవసరం.",
        }

        for event_name, telugu_phrase in expected_mappings.items():
            assert MILESTONE_MESSAGES[event_name] == telugu_phrase
            mapped_text = telugu_activity_mapper.map_event(
                stage_id="planning",
                agent_id="visual_planning",
                metadata={"event": event_name},
            )
            assert mapped_text == telugu_phrase, f"Mismatch for {event_name}: {mapped_text}"

    def test_secret_redaction_in_diagnostics_and_messages(self):
        """API keys, tokens, and passwords must be replaced with typed [REDACTED_*] markers in failure diagnostics."""
        raw_error = "Authorization failed for sk-abcdef1234567890abcdef1234567890 with Bearer tok_xyz123456789012345678"
        sanitized = sanitize_secrets(raw_error)
        assert "sk-abcdef" not in sanitized
        assert "tok_xyz" not in sanitized
        assert "Bearer [REDACTED_TOKEN]" in sanitized

        diag = FailureDiagnostic(
            project_id="p1",
            task_id="t1",
            agent_id="agent1",
            stage_id="planning",
            category=ErrorCategory.SECURITY.value,
            code="auth_error",
            message=raw_error,
        )
        assert "sk-abcdef" not in diag.message
        assert "[REDACTED_API_KEY]" in diag.message


# ==============================================================================
# ==============================================================================

class TestGroupGMultiStageRegressions:


    def test_record_recovery_experience_failsafe(self):
        """record_recovery_experience must never raise even if memory persistence is unavailable."""
        res = record_recovery_experience(
            agent_id="visual_planning",
            stage_id="planning",
            project_id="test_proj",
            task_id="run_123",
            outcome="succeeded",
            attempt=2,
            details={"notes": "recovered successfully"},
        )
        assert isinstance(res, bool)
