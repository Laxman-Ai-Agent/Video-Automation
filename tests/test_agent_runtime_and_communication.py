"""Focused tests for Phase 1: Common Agent Runtime, Registry, and Communication Protocol."""
from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest
from SYSTEM.core.resilience import redact_secrets
from backend.agents import (
    AgentCategory,
    AgentMessage,
    AgentMetadata,
    AgentRegistry,
    AgentRequest,
    AgentResult,
    AgentStatus,
    ArtifactRef,
    BaseAgent,
    MessageType,
    append_message,
    get_communications_file,
    publish_handoff,
    publish_lifecycle_event,
    publish_message,
    publish_review_feedback,
    query_messages,
    registry,
)


def test_registry_contains_all_15_logical_agents():
    """Verify that the authoritative registry contains exactly the 15 logical agents with valid metadata: the orchestrator and one agent per stage (13 stages, plus the deprecated template selection)."""
    issues = registry.validate_registry()
    assert issues == [], f"Registry validation issues: {issues}"

    agents = registry.list_agents()
    assert len(agents) == 15

    expected_ids = [
        "main_orchestrator",
        "audio_input",
        "audio_analyzer",
        "scene_segmentation",
        "visual_planning",
        "asset_collection",
        "motion_planning",
        "motion_template_selection",
        "motion_animation",
        "motion_timeline_validation",
        "timeline_build",
        "timeline_approval",
        "render_video",
        "final_qc",
        "final_video_delivery",
    ]

    for aid in expected_ids:
        meta = registry.get(aid)
        assert meta.status in (AgentStatus.IMPLEMENTED, AgentStatus.DEPRECATED)
        assert meta.purpose, f"Agent {aid} has empty purpose"
        assert meta.capabilities, f"Agent {aid} has no capabilities"
        adapter = registry.get_agent(aid)
        assert isinstance(adapter, BaseAgent), f"Agent {aid} adapter is not a BaseAgent"

    # Category verification
    assert registry.get("main_orchestrator").category == AgentCategory.ORCHESTRATOR
    assert registry.get("audio_analyzer").category == AgentCategory.VIDEO_ENGINE_AGENT
    assert registry.get("motion_template_selection").category == AgentCategory.VIDEO_ENGINE_AGENT

    # Frozen stage verification
    assert registry.get("audio_analyzer").is_frozen is False                    # the FROZEN markers were removed (2026-10-20); the stage files stay protected by the sandbox rules
    assert registry.get("scene_segmentation").is_frozen is False


def test_registry_rejects_empty_id_or_invalid_adapter():
    """Verify registry enforces validation on registration."""
    r = AgentRegistry()
    with pytest.raises(ValueError, match="Agent ID cannot be empty"):
        r.register(
            AgentMetadata(agent_id="", name="Invalid", purpose="Test"),
            BaseAgent,  # type: ignore[arg-type]
        )

    class NotAnAgent:
        pass

    with pytest.raises(TypeError, match="must inherit from BaseAgent"):
        r.register(
            AgentMetadata(agent_id="test_invalid", name="Invalid", purpose="Test"),
            NotAnAgent,  # type: ignore[arg-type]
        )


def test_runtime_base_agent_lifecycle(tmp_path: Path, monkeypatch):
    """Verify BaseAgent standard lifecycle: validate -> execute -> review -> lifecycle events."""
    pdir = tmp_path / "test-proj-lifecycle"
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "project.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr("backend.store.project_dir", lambda pid: tmp_path / pid)

    meta = AgentMetadata(
        agent_id="mock_agent",
        name="Mock Agent",
        purpose="Testing lifecycle",
        stage_id="mock_stage",
    )

    class MockAgent(BaseAgent):
        def validate(self, project_dir: Path, request: AgentRequest) -> list[str]:
            if not (project_dir / "input.txt").exists():
                return ["Missing input.txt"]
            return []

        def execute(self, project_dir: Path, request: AgentRequest) -> AgentResult:
            out_file = project_dir / "output.txt"
            out_file.write_text("Processed", encoding="utf-8")
            return AgentResult(
                agent_id=self.agent_id,
                stage_id="mock_stage",
                project_id=project_dir.name,
                status="succeeded",
                output_refs=[ArtifactRef(path=str(out_file), description="Output")],
                summary="Mock execution succeeded",
            )

    agent = MockAgent(meta)

    # 1. Validation failure test
    req = AgentRequest(project_id="test-proj-lifecycle", agent_id="mock_agent", stage_id="mock_stage")
    res_blocked = agent.invoke(pdir, req)
    assert res_blocked.status == "blocked"
    assert "Missing input.txt" in res_blocked.error

    # 2. Successful execution test
    (pdir / "input.txt").write_text("Input data", encoding="utf-8")
    res_success = agent.invoke(pdir, req)
    assert res_success.status == "succeeded"
    assert len(res_success.output_refs) == 1
    assert "output.txt" in res_success.output_refs[0].path


def test_communication_jsonl_append_and_query(tmp_path: Path, monkeypatch):
    """Verify durable JSONL append, independent parsing per line, and query filtering."""
    proj_dir = tmp_path / "test-comm-proj"
    proj_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("backend.store.project_dir", lambda pid: tmp_path / pid)

    pid = "test-comm-proj"

    # Publish real messages of different types
    msg1 = publish_lifecycle_event(pid, "audio", "audio_input", "started", "Audio ingest started")
    msg2 = publish_handoff(pid, "analyzer", "audio_input", "audio_analyzer", "Audio downsampled; ready for ASR")
    msg3 = publish_review_feedback(
        pid,
        "analyzer",
        "main_orchestrator",
        "audio_analyzer",
        status="passed",
        score=0.92,
        summary="Transcript accurate",
        findings=[],
    )

    cfile = get_communications_file(pid)
    assert cfile.exists()

    # Verify canonical JSONL format: each line independently parses as valid JSON
    lines = cfile.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3

    for i, line in enumerate(lines, start=1):
        parsed = json.loads(line)
        assert parsed["sequence"] == i
        assert parsed["project_id"] == pid
        assert parsed["schema_version"] == 1
        assert parsed["timestamp"]

    # Query with filters
    all_msgs = query_messages(pid, reverse=False)
    assert len(all_msgs) == 3
    assert [m.sequence for m in all_msgs] == [1, 2, 3]

    # Filter by message type
    handoffs = query_messages(pid, message_type=MessageType.HANDOFF)
    assert len(handoffs) == 1
    assert handoffs[0].sender_agent_id == "audio_input"
    assert handoffs[0].recipient_agent_ids == ["audio_analyzer"]

    # Filter by stage
    analyzer_msgs = query_messages(pid, stage_id="analyzer")
    assert len(analyzer_msgs) == 2

    # Test limit and cursor pagination
    page1 = query_messages(pid, limit=2, reverse=False)
    assert len(page1) == 2
    cursor_seq = page1[-1].sequence
    page2 = query_messages(pid, cursor=cursor_seq, limit=2, reverse=False)
    assert len(page2) == 1
    assert page2[0].sequence == 3


def test_communication_concurrency_safety(tmp_path: Path, monkeypatch):
    """Verify that multiple concurrent threads appending to communications.jsonl do not corrupt lines."""
    pid = "concurrent-comm-proj"
    pdir = tmp_path / pid
    pdir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("backend.store.project_dir", lambda p: tmp_path / p)

    num_threads = 8
    msgs_per_thread = 25

    def worker(thread_idx: int):
        for i in range(msgs_per_thread):
            publish_message(
                project_id=pid,
                stage_id="planning",
                sender_agent_id="visual_planning",
                content=f"Thread {thread_idx} message {i}",
                message_type=MessageType.AGENT_MESSAGE,
            )

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    cfile = get_communications_file(pid)
    lines = cfile.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == num_threads * msgs_per_thread

    # Every single line must parse cleanly
    sequences = set()
    for line in lines:
        data = json.loads(line)
        sequences.add(data["sequence"])

    assert len(sequences) == len(lines), "Duplicate or missing sequence detected"


def test_communication_project_isolation(tmp_path: Path, monkeypatch):
    """Verify strict project isolation: Project A communications are never returned for Project B."""
    p_a = tmp_path / "proj-alpha"
    p_b = tmp_path / "proj-beta"
    p_a.mkdir(parents=True, exist_ok=True)
    p_b.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("backend.store.project_dir", lambda p: tmp_path / p)

    publish_message("proj-alpha", "audio", "audio_input", "Message for Alpha")
    publish_message("proj-beta", "motion_plan", "motion_planning", "Message for Beta")

    msgs_a = query_messages("proj-alpha")
    msgs_b = query_messages("proj-beta")

    assert len(msgs_a) == 1
    assert msgs_a[0].project_id == "proj-alpha"
    assert "Alpha" in msgs_a[0].content

    assert len(msgs_b) == 1
    assert msgs_b[0].project_id == "proj-beta"
    assert "Beta" in msgs_b[0].content


def test_secret_redaction():
    """Verify that sensitive keys, passwords, and tokens are redacted from messages and metadata."""
    raw_content = "Calling service with api_key=sk-ant-api03-abcdef1234567890abcdef and Bearer eyJhbGciOiJIUzI1NiJ9.testsecret"
    redacted_content, applied = redact_secrets(raw_content)

    assert "sk-ant" not in redacted_content
    assert "api_key=[REDACTED_API_KEY]" in redacted_content
    assert "Bearer [REDACTED_TOKEN]" in redacted_content
    assert applied == ["api_key", "bearer_token"]


def test_distinguish_real_messages_vs_lifecycle_events():
    """Verify that runtime lifecycle events are distinguished from agent messages/handoffs."""
    msg = AgentMessage(
        project_id="test-p",
        stage_id="render",
        sender_agent_id="render_video",
        message_type=MessageType.LIFECYCLE_EVENT.value,
        content="Lifecycle: step_started - Render step started",
    )
    assert msg.message_type == "lifecycle_event"

    handoff = AgentMessage(
        project_id="test-p",
        stage_id="timeline",
        sender_agent_id="motion_timeline_validation",
        recipient_agent_ids=["timeline_build"],
        message_type=MessageType.HANDOFF.value,
        content="Handoff: validation report clean; proceed to timeline assembly",
    )
    assert handoff.message_type == "handoff"
    assert handoff.recipient_agent_ids == ["timeline_build"]
