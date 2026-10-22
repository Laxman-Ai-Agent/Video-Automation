"""Comprehensive Acceptance Test Suite for Stage 4:
Structured Agent Communication & Natural Telugu Activity Updates.

Verifies:
1. Telugu Activity Mapper:
   - All 21 canonical registered agents are mapped to friendly Telugu names.
   - Canonical pipeline milestones produce natural Telugu activity updates.
   - Unicode compliance: Telugu codepoints in the range U+0C00 to U+0C7F.
   - Sensitive technical data (API keys, tokens, paths) is sanitized.
   - Graceful fallback for unknown agents/stages without fabricating progress.
2. Structured Agent Communication Contract:
   - Backward-compatible AgentMessage deserialization for legacy records.
   - Stage 4 fields: task_id, telugu_activity, progress_percent, details,
     source_agent_id, target_agent_id.
   - Alias properties: agent_id, technical_message, event_id, event_type.
   - Bidirectional serialization and dictionary parsing.
3. Truthful Progress Calculation:
   - Intermediate stages are strictly bounded and NEVER report 100%.
   - Terminal stage completion reaches 100.0%.
   - Blocked or failed operations retain stage lower bounds.
4. Event Bus & SSE Streaming:
   - append_message auto-populates telugu_activity and progress_percent.
   - query_messages filters by task_id.
   - subscribe_events yields SSE formatted payloads with Telugu updates.
   - Lifecycle and handoff events carry source/target and Telugu descriptions.
5. FastAPI Endpoints:
   - /api/stream/events and /projects/{pid}/agent-communications/stream stream SSE.
   - POST /projects/{pid}/agent-communications accepts task_id and telugu_activity.
6. Non-blocking & Performance:
   - Mapping executes in < 1ms per event.
   - Fail-safe handling on malformed inputs.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest
from SYSTEM.core.resilience import sanitize_secrets
from fastapi.testclient import TestClient

from backend.main import app
from SYSTEM.agents.shared.contracts import (
    AgentCategory,
    AgentMessage,
    AgentMetadata,
    AgentRequest,
    AgentResult,
    AgentStatus,
    MessageType,
)
from SYSTEM.agents.shared.base_agent import BaseAgent
from SYSTEM.agents.shared.communication import (
    append_message,
    publish_handoff,
    publish_lifecycle_event,
    publish_message,
    publish_review_feedback,
    query_messages,
    subscribe_events,
)
from SYSTEM.agents.shared.telugu_activity_mapper import (
    AGENT_ACTIVITIES,
    AGENT_TELUGU_NAMES,
    MILESTONE_MESSAGES,
    STAGE_WEIGHTS,
    TeluguActivityMapper,
    calculate_progress,
    map_activity,
    map_handoff,
    map_review_feedback,
    telugu_activity_mapper,
)

# 21 Canonical Agents as registered in the master architecture
CANONICAL_21_AGENTS = [
    "main_architecture_agent",
    "capability_finder",
    "skill_factory",
    "audio_input",
    "audio_analyzer",
    "scene_segmentation",
    "visual_planning",
    "image_generator",
    "motion_planning",
    "motion_animation",
    "motion_timeline_validation",
    "timeline_build",
    "timeline_approval",
    "render_video",
    "final_qc",
    "final_video_delivery",
    "verification_and_test",
    "security_policy",
    "autonomous_execution",
    "video_pipeline_orchestrator",
    "resource_manager",
]


def _has_telugu_characters(text: str) -> bool:
    """Returns True if the string contains at least one character in the Telugu Unicode block."""
    return any(0x0C00 <= ord(char) <= 0x0C7F for char in text)


# ============================================================================
# Test Group A: Telugu Activity Mapper & Unicode Compliance
# ============================================================================

class TestTeluguActivityMapper:
    """Verifies natural Telugu mappings, milestones, Unicode compliance, and secret redaction."""

    def test_all_21_canonical_agents_mapped_to_telugu(self):
        """All 21 canonical agents must have a user-friendly Telugu name containing Telugu characters."""
        for agent_id in CANONICAL_21_AGENTS:
            assert agent_id in AGENT_TELUGU_NAMES, f"Agent {agent_id} missing from AGENT_TELUGU_NAMES"
            name = AGENT_TELUGU_NAMES[agent_id]
            assert isinstance(name, str) and len(name.strip()) > 0
            assert _has_telugu_characters(name), f"Agent {agent_id} name '{name}' lacks Telugu characters"

    def test_milestone_messages_contain_valid_telugu(self):
        """All canonical pipeline milestones must contain natural, valid Telugu."""
        expected_milestones = [
            "audio_accepted",
            "audio_analysis",
            "transcript_processing",
            "scene_segmentation",
            "skill_lookup",
            "github_discovery",
            "skill_validation",
            "visual_planning",
            "motion_planning",
            "timeline_building",
            "rendering",
            "technical_qc",
            "recovery",
            "waiting_for_approval",
            "task_blocked",
            "desktop_delivery",
            "completion",
        ]
        for milestone in expected_milestones:
            assert milestone in MILESTONE_MESSAGES, f"Milestone {milestone} missing"
            text = MILESTONE_MESSAGES[milestone]
            assert isinstance(text, str) and len(text.strip()) > 0
            assert _has_telugu_characters(text), f"Milestone {milestone} lacks Telugu characters"

    def test_map_lifecycle_events_for_agents(self):
        """Lifecycle operations (started, completed) for canonical agents map to distinct Telugu messages."""
        for agent_id in ["audio_input", "audio_analyzer", "scene_segmentation", "visual_planning", "render_video", "final_qc"]:
            # Started
            msg_start = map_activity(agent_id=agent_id, status="started")
            assert _has_telugu_characters(msg_start)

            # Completed
            msg_done = map_activity(agent_id=agent_id, status="completed")
            assert _has_telugu_characters(msg_done)
            assert msg_start != msg_done, f"Started and completed messages should differ for {agent_id}"

    def test_map_handoff_formatting(self):
        """Handoffs format clear Telugu delegating responsibility between agents."""
        text = map_handoff("audio_input", "audio_analyzer", "ఆడియో సరిచూడబడింది")
        assert _has_telugu_characters(text)
        # Should reference the agents' Telugu names or IDs
        assert "నుండి" in text and ("కు" in text or "కి" in text)

        # Multi-recipient handoff
        text_multi = map_handoff("visual_planning", ["motion_planning", "image_generator"], "దృశ్యాలు సిద్ధమయ్యాయి")
        assert _has_telugu_characters(text_multi)
        assert "నుండి" in text_multi

    def test_map_review_feedback_formatting(self):
        """Review feedback creates truthful Telugu messages containing verdict and score."""
        text_approved = map_review_feedback("approved", 96.5, "అన్ని దృశ్యాలు బాగున్నాయి")
        assert _has_telugu_characters(text_approved)
        assert "ఆమోదించబడింది" in text_approved or "విజయవంతం" in text_approved
        assert "96.5%" in text_approved

        text_changes = map_review_feedback("changes_requested", 70.0, "టైమింగ్ మార్చాలి")
        assert _has_telugu_characters(text_changes)
        assert "మార్పులు" in text_changes

    def test_secret_sanitization(self):
        """Secrets (API keys, tokens, AWS keys, passwords) are sanitized and never exposed in Telugu updates."""
        secret_text = "API error: sk-ant-api03-abcdef123456789012345678 and token ghp_ABCDEFGHIJKLMNOPQRSTUVWX with key AKIAIOSFODNN7EXAMPLE"
        sanitized = sanitize_secrets(secret_text)
        assert "sk-ant-api03" not in sanitized
        assert "ghp_" not in sanitized
        assert "AKIAIOSFODNN7EXAMPLE" not in sanitized
        assert "[REDACTED_AWS_KEY]" in sanitized

        # Check in map_activity with secret in content
        telugu_result = map_activity(
            agent_id="audio_analyzer",
            status="failed",
            content=f"Error using secret {secret_text}",
        )
        assert _has_telugu_characters(telugu_result)
        assert "sk-" not in telugu_result
        assert "AKIA" not in telugu_result

    def test_truthful_fallback_unknown_agent_and_stage(self):
        """Unknown agent or stage returns safe Telugu fallback without error."""
        text = map_activity(agent_id="totally_unknown_agent", status="running", content="doing unknown things")
        assert _has_telugu_characters(text)
        assert text in ("పని కొనసాగుతోంది.", "పని పురోగతిలో ఉంది.", "పని విజయవంతంగా పూర్తయింది.")

        text_done = map_activity(agent_id="unknown_x", status="completed")
        assert _has_telugu_characters(text_done)
        assert "పూర్తయింది" in text_done

    def test_failure_and_recovery_messaging(self):
        """Failure and retry events generate appropriate supportive Telugu activity."""
        fail_text = map_activity(agent_id="render_video", status="failed", content="FFmpeg segmentation fault")
        assert _has_telugu_characters(fail_text)
        assert "లోపం" in fail_text or "సమస్య" in fail_text

        retry_text = map_activity(agent_id="render_video", status="running", content="recovering from failure, retrying scene 2")
        assert _has_telugu_characters(retry_text)
        assert "పరిష్కరించి" in retry_text or "ప్రయత్నిస్తున్నాను" in retry_text


# ============================================================================
# Test Group B: Structured Agent Communication Contract
# ============================================================================

class TestStructuredAgentContracts:
    """Verifies backward compatibility, Stage 4 fields, and alias properties."""

    def test_agent_message_backward_compatibility(self):
        """Legacy JSON dictionaries without Stage 4 fields deserialize seamlessly."""
        legacy_dict = {
            "message_id": "msg-legacy-001",
            "project_id": "proj-legacy",
            "stage_id": "audio",
            "sender_agent_id": "audio_input",
            "recipient_agent_ids": ["audio_analyzer"],
            "message_type": "handoff",
            "status": "sent",
            "sequence": 1,
            "created_at": "2026-10-17T12:00:00",
            "content": "Legacy handoff without stage 4 fields",
            "artifact_refs": [],
            "metadata": {},
        }
        msg = AgentMessage.from_dict(legacy_dict)
        assert msg.message_id == "msg-legacy-001"
        assert msg.content == "Legacy handoff without stage 4 fields"
        assert msg.task_id is None
        assert msg.telugu_activity is None
        assert msg.progress_percent is None

    def test_stage4_extended_fields(self):
        """AgentMessage preserves and round-trips task_id, telugu_activity, progress_percent, and details."""
        msg = AgentMessage(
            message_id="msg-stage4-100",
            project_id="proj-4",
            stage_id="planning",
            sender_agent_id="visual_planning",
            recipient_agent_ids=["motion_planning"],
            content="Visual scenes generated",
            task_id="task-run-444",
            telugu_activity="విజువల్ ప్లానింగ్ పూర్తయింది.",
            progress_percent=38.5,
            details={"scenes_count": 5, "duration": 42.0},
            source_agent_id="visual_planning",
            target_agent_id="motion_planning",
        )
        msg_dict = msg.to_dict()
        assert msg_dict["task_id"] == "task-run-444"
        assert msg_dict["telugu_activity"] == "విజువల్ ప్లానింగ్ పూర్తయింది."
        assert msg_dict["progress_percent"] == 38.5
        assert msg_dict["details"]["scenes_count"] == 5
        assert msg_dict["source_agent_id"] == "visual_planning"
        assert msg_dict["target_agent_id"] == "motion_planning"

        reconstructed = AgentMessage.from_dict(msg_dict)
        assert reconstructed.task_id == "task-run-444"
        assert reconstructed.telugu_activity == "విజువల్ ప్లానింగ్ పూర్తయింది."
        assert reconstructed.progress_percent == 38.5
        assert reconstructed.source_agent_id == "visual_planning"
        assert reconstructed.target_agent_id == "motion_planning"

    def test_alias_properties(self):
        """Alias properties provide seamless access across communication formats."""
        msg = AgentMessage(
            message_id="msg-alias-1",
            content="Audio normalization done",
            sender_agent_id="audio_input",
            message_type=MessageType.LIFECYCLE_EVENT,
        )
        # Check alias getters
        assert msg.agent_id == "audio_input"
        assert msg.technical_message == "Audio normalization done"
        assert msg.event_id == "msg-alias-1"
        assert msg.event_type == "lifecycle_event"

        # Check alias setters
        msg.agent_id = "audio_analyzer"
        assert msg.sender_agent_id == "audio_analyzer"

        msg.technical_message = "Updated technical text"
        assert msg.content == "Updated technical text"

    def test_to_dict_includes_canonical_and_alias_keys(self):
        """to_dict() emits both canonical and alias keys for maximum client compatibility."""
        msg = AgentMessage(
            message_id="msg-dual-01",
            sender_agent_id="scene_segmentation",
            content="Segmentation ready",
            message_type=MessageType.HANDOFF,
        )
        d = msg.to_dict()
        assert d["message_id"] == "msg-dual-01"
        assert d["event_id"] == "msg-dual-01"
        assert d["sender_agent_id"] == "scene_segmentation"
        assert d["agent_id"] == "scene_segmentation"
        assert d["content"] == "Segmentation ready"
        assert d["technical_message"] == "Segmentation ready"
        assert d["message_type"] == "handoff"
        assert d["event_type"] == "handoff"

    def test_from_dict_with_alias_keys_only(self):
        """Deserializing from a dict containing only alias keys creates a valid AgentMessage."""
        alias_dict = {
            "event_id": "evt-alias-99",
            "agent_id": "skill_factory",
            "technical_message": "Synthesized new skill",
            "event_type": "lifecycle_event",
        }
        msg = AgentMessage.from_dict(alias_dict)
        assert msg.message_id == "evt-alias-99"
        assert msg.sender_agent_id == "skill_factory"
        assert msg.content == "Synthesized new skill"
        assert msg.message_type == MessageType.LIFECYCLE_EVENT.value


# ============================================================================
# Test Group C: Truthful Progress Calculation
# ============================================================================

class TestProgressCalculationIntegrity:
    """Verifies that progress calculations are truthful, bounded, and never prematurely 100%."""

    def test_stage_weights_exist_and_monotonic(self):
        """All pipeline stages must have valid (start, end) weights in ascending progression."""
        prev_end = 0.0
        for stage_id, (start, end) in STAGE_WEIGHTS.items():
            assert 0.0 <= start <= end <= 100.0, f"Stage {stage_id} invalid bounds: ({start}, {end})"
            assert start >= prev_end - 0.01, f"Stage {stage_id} start {start} precedes prev_end {prev_end}"
            prev_end = end
        assert prev_end == 100.0, "Final stage must reach 100.0"

    def test_intermediate_stages_never_reach_100(self):
        """Intermediate stages with succeeded/completed status NEVER report 100.0%."""
        intermediate_stages = ["audio", "analyzer", "segmentation", "planning", "motion_plan", "motion_gen", "timeline", "render", "qc"]
        for stage in intermediate_stages:
            prog = calculate_progress(stage_id=stage, status="succeeded")
            assert prog < 100.0, f"Stage {stage} prematurely reported 100%!"
            _, expected_max = STAGE_WEIGHTS[stage]
            assert prog == expected_max, f"Stage {stage} should reach its stage cap {expected_max}, got {prog}"

    def test_terminal_final_reaches_100(self):
        """Only final/delivery stage with status succeeded/completed reaches 100.0%."""
        prog = calculate_progress(stage_id="final", status="succeeded")
        assert prog == 100.0

    def test_failed_and_blocked_retain_lower_bound(self):
        """Blocked or failed stages retain their start_percent and do not claim progress."""
        for stage in ["audio", "planning", "render"]:
            start_pct, _ = STAGE_WEIGHTS[stage]
            prog_blocked = calculate_progress(stage_id=stage, status="blocked")
            assert prog_blocked == start_pct

            prog_failed = calculate_progress(stage_id=stage, status="failed")
            assert prog_failed == start_pct

    def test_explicit_progress_clamped_within_stage(self):
        """Explicit progress values passed to calculate_progress are clamped to stage boundaries."""
        # Visual planning is 25.0 - 40.0
        clamped_low = calculate_progress(stage_id="planning", status="running", explicit_progress=5.0)
        assert clamped_low >= 25.0

        clamped_high = calculate_progress(stage_id="planning", status="running", explicit_progress=99.0)
        assert clamped_high <= 40.0


# ============================================================================
# Test Group D: Communication & Event Stream Integration
# ============================================================================

class TestCommunicationAndEventStream:
    """Verifies message storage, auto-population of Telugu activity, querying, and SSE streams."""

    def test_append_message_auto_populates_telugu_and_progress(self, tmp_path, monkeypatch):
        """append_message automatically infers telugu_activity and progress_percent if omitted."""
        monkeypatch.setattr("backend.store.project_dir", lambda p: tmp_path / p)
        pid = "test-proj-telugu-auto"

        msg = AgentMessage(
            project_id=pid,
            stage_id="audio",
            sender_agent_id="audio_input",
            content="Audio ingested successfully",
            status="completed",
        )
        saved = append_message(pid, msg)
        assert saved.telugu_activity is not None
        assert _has_telugu_characters(saved.telugu_activity)
        assert saved.progress_percent == 5.0

    def test_query_messages_task_id_filtering(self, tmp_path, monkeypatch):
        """query_messages correctly filters messages by task_id."""
        monkeypatch.setattr("backend.store.project_dir", lambda p: tmp_path / p)
        pid = "test-proj-query-filter"

        msg1 = AgentMessage(project_id=pid, stage_id="audio", sender_agent_id="audio_input", content="M1", task_id="task-ALPHA")
        msg2 = AgentMessage(project_id=pid, stage_id="analyzer", sender_agent_id="audio_analyzer", content="M2", task_id="task-BETA")
        msg3 = AgentMessage(project_id=pid, stage_id="planning", sender_agent_id="visual_planning", content="M3", task_id="task-ALPHA")

        append_message(pid, msg1)
        append_message(pid, msg2)
        append_message(pid, msg3)

        alpha_messages = query_messages(pid, task_id="task-ALPHA")
        assert len(alpha_messages) == 2
        assert all(m.task_id == "task-ALPHA" for m in alpha_messages)

        beta_messages = query_messages(pid, task_id="task-BETA")
        assert len(beta_messages) == 1
        assert beta_messages[0].task_id == "task-BETA"

    def test_publish_handoff_with_source_target_telugu(self, tmp_path, monkeypatch):
        """publish_handoff populates source_agent_id, target_agent_id, and Telugu handoff text."""
        monkeypatch.setattr("backend.store.project_dir", lambda p: tmp_path / p)
        pid = "test-proj-handoff"

        msg = publish_handoff(
            project_id=pid,
            stage_id="segmentation",
            from_agent="audio_analyzer",
            to_agents=["scene_segmentation"],
            reason="Audio analyzed, handed off to segmentation",
            task_id="task-seg-99",
        )
        assert msg.source_agent_id == "audio_analyzer"
        assert msg.target_agent_id == "scene_segmentation"
        assert msg.task_id == "task-seg-99"
        assert _has_telugu_characters(msg.telugu_activity)
        assert "నుండి" in msg.telugu_activity

    def test_publish_review_feedback_telugu(self, tmp_path, monkeypatch):
        """publish_review_feedback produces truthful Telugu activity with review verdict."""
        monkeypatch.setattr("backend.store.project_dir", lambda p: tmp_path / p)
        pid = "test-proj-review"

        msg = publish_review_feedback(
            project_id=pid,
            stage_id="qc",
            reviewer_agent_id="final_qc",
            target_agent_ids=["video_pipeline_orchestrator"],
            verdict="approved",
            score=98.0,
            summary="Audio/video sync and motion quality confirmed",
        )
        assert _has_telugu_characters(msg.telugu_activity)
        assert "ఆమోదించబడింది" in msg.telugu_activity or "విజయవంతం" in msg.telugu_activity
        assert "98.0%" in msg.telugu_activity

    @pytest.mark.anyio
    async def test_subscribe_events_yields_sse_stream(self, tmp_path, monkeypatch):
        """subscribe_events yields valid SSE strings containing telugu_activity and content."""
        monkeypatch.setattr("backend.store.project_dir", lambda p: tmp_path / p)
        pid = "test-proj-sse"

        # Pre-seed one message
        msg = AgentMessage(
            project_id=pid,
            stage_id="planning",
            sender_agent_id="visual_planning",
            content="Planning scenes",
            telugu_activity="విజువల్ ప్లానింగ్ ప్రారంభమైంది.",
            progress_percent=28.0,
        )
        append_message(pid, msg)

        # Call subscribe_events with catch_up=True
        gen = subscribe_events(project_id=pid, poll_interval=0.05, catch_up=True)
        # First chunk is connected
        first_chunk = await anext(gen)
        assert first_chunk["event"] == "connected"

        # Second chunk is the pre-seeded message
        second_chunk = await anext(gen)
        assert second_chunk["event"] == "message"
        data = json.loads(second_chunk["data"])
        assert data["telugu_activity"] == "విజువల్ ప్లానింగ్ ప్రారంభమైంది."
        assert data["progress_percent"] == 28.0
        assert data["content"] == "Planning scenes"


# ============================================================================
# Test Group E: BaseAgent Lifecycle Integration
# ============================================================================

class TestBaseAgentLifecycleIntegration:
    """Verifies that BaseAgent executions publish lifecycle events with Telugu activity and task_id."""

    class MockAudioAgent(BaseAgent):
        def validate(self, project_dir: Path, request: AgentRequest) -> list[str]:
            return []

        def execute(self, project_dir: Path, request: AgentRequest) -> AgentResult:
            return AgentResult(
                agent_id="audio_input",
                stage_id="audio",
                project_id=request.project_id,
                status="succeeded",
                output_refs=[],
                metadata={"audio_duration": 12.5},
            )

        def review(self, project_dir: Path, request: AgentRequest, result: AgentResult) -> AgentResult:
            return result

    def test_base_agent_invoke_publishes_telugu_lifecycle(self, tmp_path, monkeypatch):
        """Invoking a BaseAgent publishes started and completed lifecycle events with Telugu messages."""
        monkeypatch.setattr("backend.store.project_dir", lambda p: tmp_path / p)
        pid = "test-proj-base-agent"

        meta = AgentMetadata(
            agent_id="audio_input",
            name="Audio Input Agent",
            category=AgentCategory.VIDEO_ENGINE_AGENT,
            status=AgentStatus.IMPLEMENTED,
            purpose="Ingest audio",
        )
        agent = self.MockAudioAgent(meta)

        req = AgentRequest(
            project_id=pid,
            stage_id="audio",
            task_id="task-audio-001",
            run_id="run-001",
        )
        pdir = tmp_path / pid
        pdir.mkdir(parents=True, exist_ok=True)
        result = agent.invoke(pdir, req)
        assert result.success is True

        messages = query_messages(pid, task_id="task-audio-001")
        assert len(messages) >= 2  # Started and completed

        started_msg = next((m for m in messages if m.metadata.get("event") == "started"), None)
        assert started_msg is not None
        assert _has_telugu_characters(started_msg.telugu_activity)

        completed_msg = next((m for m in messages if m.metadata.get("event") == "completed"), None)
        assert completed_msg is not None
        assert _has_telugu_characters(completed_msg.telugu_activity)
        assert completed_msg.progress_percent == 5.0


# ============================================================================
# Test Group F: FastAPI SSE Endpoints
# ============================================================================

class TestFastApiSseEndpoints:
    """Verifies the FastAPI SSE streaming endpoints and Telugu communication routes."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_post_message_with_telugu_and_task_id(self, client, tmp_path, monkeypatch):
        """POST /projects/{pid}/agent-communications accepts and returns task_id and telugu_activity."""
        pid = "api-test-stage4-proj"
        monkeypatch.setattr("backend.store.project_dir", lambda p: tmp_path / p)

        payload = {
            "stage_id": "analyzer",
            "sender_agent_id": "audio_analyzer",
            "recipient_agent_ids": ["scene_segmentation"],
            "message_type": "handoff",
            "content": "Transcription completed for 3 scenes",
            "task_id": "task-api-99",
            "telugu_activity": "ఆడియో విశ్లేషణ పూర్తయింది.",
            "progress_percent": 15.0,
        }
        res = client.post(f"/projects/{pid}/agent-communications", json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data["task_id"] == "task-api-99"
        assert data["telugu_activity"] == "ఆడియో విశ్లేషణ పూర్తయింది."
        assert data["progress_percent"] == 15.0

        # Query messages with task_id filter
        res_get = client.get(f"/projects/{pid}/agent-communications?task_id=task-api-99")
        assert res_get.status_code == 200
        get_data = res_get.json()
        assert get_data["count"] == 1
        assert get_data["messages"][0]["task_id"] == "task-api-99"
        assert get_data["messages"][0]["telugu_activity"] == "ఆడియో విశ్లేషణ పూర్తయింది."

    @pytest.mark.anyio
    async def test_sse_endpoint_headers(self, tmp_path, monkeypatch):
        """SSE streaming endpoint returns Content-Type text/event-stream."""
        from UI.backend.routes.agents import stream_project_communications
        pid = "api-sse-test-proj"
        monkeypatch.setattr("backend.store.project_dir", lambda p: tmp_path / p)

        res = await stream_project_communications(pid)
        assert res.media_type == "text/event-stream"
        assert res.headers["Cache-Control"] == "no-cache"

        # Verify initial connected event is yielded
        iterator = res.body_iterator
        first_chunk = await anext(iterator)
        assert "event: connected" in first_chunk

    @pytest.mark.anyio
    async def test_canonical_stream_events_route(self, tmp_path, monkeypatch):
        """Canonical /api/stream/events route exists and provides text/event-stream."""
        from UI.backend.routes.agents import stream_events_global
        pid = "api-stream-events-proj"
        monkeypatch.setattr("backend.store.project_dir", lambda p: tmp_path / p)

        res = await stream_events_global(project_id=pid)
        assert res.media_type == "text/event-stream"
        assert res.headers["Cache-Control"] == "no-cache"

        iterator = res.body_iterator
        first_chunk = await anext(iterator)
        assert "event: connected" in first_chunk


# ============================================================================
# Test Group G: Non-blocking Safety & Performance
# ============================================================================

class TestPerformanceAndSafety:
    """Verifies that Telugu activity mapping is ultra-fast (< 1ms) and safe against corrupted inputs."""

    def test_mapper_execution_speed(self):
        """1000 activity mapping evaluations must complete in < 0.5s (< 0.5ms per event)."""
        start = time.perf_counter()
        for i in range(1000):
            agent = CANONICAL_21_AGENTS[i % len(CANONICAL_21_AGENTS)]
            status = "completed" if i % 2 == 0 else "started"
            _ = map_activity(stage_id="planning", agent_id=agent, status=status, content=f"Event {i}")
        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / 1000) * 1000
        assert elapsed < 0.5, f"1000 mappings took {elapsed:.4f}s (avg {avg_ms:.3f}ms), exceeding 0.5s limit"

    def test_non_blocking_error_handling(self):
        """Passing None or unexpected types to mapper functions does not raise uncaught exceptions."""
        mapper = TeluguActivityMapper()
        # Should not raise exception
        result_none = mapper.map_event(stage_id="", agent_id="", content="")
        assert isinstance(result_none, str) and len(result_none) > 0

        # Pass None or invalid inputs
        result_safe = mapper.sanitize_text("")
        assert result_safe == ""

        prog = mapper.calculate_progress("invalid_stage_xyz", "running")
        assert isinstance(prog, float)
