"""Focused tests for Phase 2: LLM Gateway & Mandatory Review Consolidation."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend import llm_gateway, llm_review, llm_usage
from backend.agents import AgentRegistry, AgentRequest, AgentResult, registry
from backend.agents.adapters.stage_adapters import VisualPlanningAdapter
from backend.llm_gateway import (
    PROFILE_ROUTING,
    LlmGateway,
    LlmGatewayRequest,
    LlmGatewayResponse,
    get_gateway,
)


def test_gateway_request_and_response_dataclasses():
    """Verify LlmGatewayRequest and LlmGatewayResponse initialization, correlation IDs, and serialization."""
    req = LlmGatewayRequest(
        project_id="p-123",
        stage_id="planning",
        agent_id="visual_planning",
        purpose="decision",
        user_prompt="Generate 3 visual concepts",
        system_prompt="You are an art director",
        model_profile="fast_structured",
        structured_schema={"type": "object"},
    )
    assert req.project_id == "p-123"
    assert req.stage_id == "planning"
    assert req.correlation_id.startswith("corr_")
    assert req.request_id.startswith("req_")
    assert req.timeout == 60
    assert req.max_retries == 2

    resp = LlmGatewayResponse(
        request_id=req.request_id,
        correlation_id=req.correlation_id,
        project_id=req.project_id,
        stage_id=req.stage_id,
        agent_id=req.agent_id,
        purpose=req.purpose,
        status="passed",
        raw_text='{"concepts": ["a", "b"]}',
        structured_data={"concepts": ["a", "b"]},
        model_profile="fast_structured",
        provider="anthropic",
        model="claude-3-5-haiku-20241022",
        latency_ms=120,
        attempt_count=1,
    )
    d = resp.to_dict()
    assert d["request_id"] == req.request_id
    assert d["status"] == "passed"
    assert d["structured_data"] == {"concepts": ["a", "b"]}
    assert d["token_usage"] == {"input": 0, "output": 0, "total": 0}


def test_logical_model_profile_routing():
    """Verify logical profile routing per provider table."""
    gw = LlmGateway()

    # Gemini profiles
    assert gw.resolve_model_for_profile("gemini", "fast_structured") == "gemini-3.1-flash-lite"
    assert gw.resolve_model_for_profile("gemini", "reasoning_review") == "gemini-3.5-flash"
    assert gw.resolve_model_for_profile("gemini", "code_generation") == "gemini-3.5-flash"

    # Anthropic profiles
    assert gw.resolve_model_for_profile("anthropic", "fast_structured") == "claude-3-5-haiku-20241022"
    assert gw.resolve_model_for_profile("anthropic", "reasoning_review") == "claude-3-5-sonnet-20241022"
    assert gw.resolve_model_for_profile("anthropic", "code_generation") == "claude-3-5-sonnet-20241022"

    # Configured model override for 'default' profile
    assert gw.resolve_model_for_profile("anthropic", "default", configured_model="custom-model") == "custom-model"


def test_gateway_execute_success_and_json_parsing():
    """Verify gateway execution parses structured JSON and calculates latency & tokens."""
    mock_client = MagicMock()
    mock_client.resolve_provider_config.return_value = ("anthropic", "claude-3-5-sonnet-20241022", "dummy_key", "")
    mock_client.generate_text.return_value = '```json\n{"status": "passed", "score": 0.95, "summary": "Great quality"}\n```'

    gw = LlmGateway(client_module=mock_client)
    req = LlmGatewayRequest(
        project_id="test_proj",
        stage_id="planning",
        agent_id="visual_planning",
        purpose="review",
        user_prompt="Review scene plan",
        structured_schema={"status": "string", "score": "number"},
    )

    resp = gw.execute(req)
    assert resp.status == "passed"
    assert resp.structured_data is not None
    assert resp.structured_data["score"] == 0.95
    assert resp.attempt_count == 1
    assert resp.error is None
    assert resp.token_usage["input"] > 0
    assert resp.token_usage["output"] > 0


def test_gateway_bounded_retry_on_malformed_json():
    """Verify bounded JSON repair retry when model initially returns invalid JSON."""
    mock_client = MagicMock()
    mock_client.resolve_provider_config.return_value = ("anthropic", "claude-3-5-sonnet-20241022", "dummy_key", "")

    # First call returns non-JSON text; second call returns repaired JSON
    mock_client.generate_text.side_effect = [
        "I think the plan looks good overall.",
        '{"status": "passed", "score": 0.88, "summary": "Repaired valid JSON"}',
    ]

    gw = LlmGateway(client_module=mock_client)
    req = LlmGatewayRequest(
        project_id="test_proj",
        stage_id="motion_plan",
        agent_id="motion_planning",
        purpose="review",
        user_prompt="Review motion typography",
        structured_schema={"status": "string"},
        max_retries=2,
    )

    resp = gw.execute(req)
    assert resp.status == "passed"
    assert resp.attempt_count == 2
    assert resp.structured_data is not None
    assert resp.structured_data["summary"] == "Repaired valid JSON"


def test_gateway_fail_fast_on_auth_errors():
    """Verify non-retryable 401/403/invalid key errors fail immediately without retry loops."""
    mock_client = MagicMock()
    mock_client.resolve_provider_config.return_value = ("anthropic", "claude-3-5-sonnet-20241022", "bad_key", "")
    mock_client.generate_text.side_effect = RuntimeError("401 Unauthorized: Invalid API key")

    gw = LlmGateway(client_module=mock_client)
    req = LlmGatewayRequest(
        project_id="test_proj",
        stage_id="audio",
        agent_id="audio_input",
        purpose="review",
        user_prompt="Review audio",
        max_retries=3,
    )

    resp = gw.execute(req)
    assert resp.status == "blocked"
    assert "401 Unauthorized" in (resp.error or "")
    assert resp.attempt_count == 1  # Fast-failed without retrying


def test_review_evidence_persisted_with_fingerprints(tmp_path: Path, monkeypatch):
    """Verify run_stage_llm_review persists evidence with current input/output fingerprints."""
    pdir = tmp_path / "fingerprint_proj"
    pdir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("backend.store.project_dir", lambda p: tmp_path / p)

    # Setup dummy project files for visual planning stage
    seg_file = pdir / "scene_segmentation.json"
    seg_file.write_text(json.dumps({"scenes": [{"id": 1, "narration": "Hello world"}]}), encoding="utf-8")
    tr_file = pdir / "transcript.json"
    tr_file.write_text(json.dumps({"text": "Hello world"}), encoding="utf-8")
    vp_file = pdir / "visual_planning.json"
    vp_file.write_text(json.dumps({"scenes": [{"id": 1, "prompt": "Cosmic visual"}]}), encoding="utf-8")
    sp_file = pdir / "scene_plan.json"
    sp_file.write_text(json.dumps({"scenes": [{"id": 1}]}), encoding="utf-8")
    pm_file = pdir / "prompts_map.json"
    pm_file.write_text(json.dumps({}), encoding="utf-8")

    mock_client = MagicMock()
    mock_client.resolve_provider_config.return_value = ("anthropic", "claude-3-5-sonnet-20241022", "dummy_key", "")
    mock_client.generate_text.return_value = json.dumps({
        "status": "passed",
        "score": 0.9,
        "summary": "Visual planning cohesive",
        "findings": [],
    })

    with patch("backend.llm_gateway.llm_client", mock_client):
        res = llm_review.run_stage_llm_review(pdir, "planning")

    assert res["status"] == "passed"
    assert res["stage"] == "planning"
    assert res["input_fingerprint"]
    assert res["output_fingerprint"]
    assert res["findings"] == []

    # Verify review file is saved
    rfile = pdir / "llm_review_planning.json"
    assert rfile.exists()
    disk_data = json.loads(rfile.read_text(encoding="utf-8"))
    assert disk_data["input_fingerprint"] == res["input_fingerprint"]
    assert disk_data["output_fingerprint"] == res["output_fingerprint"]


def test_stale_fingerprint_invalidates_review(tmp_path: Path, monkeypatch):
    """Verify changing input or output files causes is_stage_review_passed to report stale fingerprints."""
    pdir = tmp_path / "stale_proj"
    pdir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("backend.store.project_dir", lambda p: tmp_path / p)

    seg_file = pdir / "scene_segmentation.json"
    seg_file.write_text(json.dumps({"scenes": [{"id": 1}]}), encoding="utf-8")
    tr_file = pdir / "transcript.json"
    tr_file.write_text(json.dumps({"text": "Hello world"}), encoding="utf-8")
    vp_file = pdir / "visual_planning.json"
    vp_file.write_text(json.dumps({"scenes": []}), encoding="utf-8")
    sp_file = pdir / "scene_plan.json"
    sp_file.write_text(json.dumps({}), encoding="utf-8")
    pm_file = pdir / "prompts_map.json"
    pm_file.write_text(json.dumps({}), encoding="utf-8")

    mock_client = MagicMock()
    mock_client.resolve_provider_config.return_value = ("anthropic", "claude-3-5-sonnet-20241022", "dummy_key", "")
    mock_client.generate_text.return_value = json.dumps({
        "status": "passed",
        "score": 0.9,
        "summary": "Passed",
        "findings": [],
    })

    with patch("backend.llm_gateway.llm_client", mock_client):
        llm_review.run_stage_llm_review(pdir, "planning")

    ok, reason, _ = llm_review.is_stage_review_passed(pdir, "planning")
    assert ok is True
    assert reason == "passed"

    # Modify output file -> stale output fingerprint
    vp_file.write_text(json.dumps({"scenes": [{"modified": True}]}), encoding="utf-8")
    ok, reason, _ = llm_review.is_stage_review_passed(pdir, "planning")
    assert ok is False
    assert reason == "llm_review_stale_outputs"

    # Modify input file -> stale input fingerprint
    seg_file.write_text(json.dumps({"scenes": [{"id": 2, "changed": True}]}), encoding="utf-8")
    ok, reason, _ = llm_review.is_stage_review_passed(pdir, "planning")
    assert ok is False
    assert reason == "llm_review_stale_inputs"


def test_blocker_findings_fail_closed_even_if_status_passed(tmp_path: Path, monkeypatch):
    """Verify that if LLM returns status='passed' but findings contain a blocker, gate fails closed."""
    pdir = tmp_path / "blocker_proj"
    pdir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("backend.store.project_dir", lambda p: tmp_path / p)

    seg_file = pdir / "scene_segmentation.json"
    seg_file.write_text(json.dumps({"scenes": []}), encoding="utf-8")
    tr_file = pdir / "transcript.json"
    tr_file.write_text(json.dumps({"text": "Hello"}), encoding="utf-8")
    vp_file = pdir / "visual_planning.json"
    vp_file.write_text(json.dumps({}), encoding="utf-8")
    sp_file = pdir / "scene_plan.json"
    sp_file.write_text(json.dumps({}), encoding="utf-8")
    pm_file = pdir / "prompts_map.json"
    pm_file.write_text(json.dumps({}), encoding="utf-8")

    mock_client = MagicMock()
    mock_client.resolve_provider_config.return_value = ("anthropic", "claude-3-5-sonnet-20241022", "dummy_key", "")
    mock_client.generate_text.return_value = json.dumps({
        "status": "passed",  # Model claims passed
        "score": 0.85,
        "summary": "Looks good but has severe issue",
        "findings": [
            {
                "severity": "blocker",
                "category": "safety",
                "message": "Critical prompt safety blocker",
            }
        ],
    })

    with patch("backend.llm_gateway.llm_client", mock_client):
        res = llm_review.run_stage_llm_review(pdir, "planning")

    # Normalized to blocked due to blocker finding
    assert res["status"] == "blocked"
    ok, reason, _ = llm_review.is_stage_review_passed(pdir, "planning")
    assert ok is False
    assert reason in ("llm_review_blocked", "llm_review_has_blockers")


def test_base_agent_review_hook_enforces_gate(tmp_path: Path, monkeypatch):
    """Verify BaseAgent.review blocks agent progression if stage review is missing or failed."""
    pdir = tmp_path / "base_agent_proj"
    pdir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("backend.store.project_dir", lambda p: tmp_path / p)

    seg_file = pdir / "scene_segmentation.json"
    seg_file.write_text(json.dumps({"scenes": []}), encoding="utf-8")
    vp_file = pdir / "visual_planning.json"
    vp_file.write_text(json.dumps({}), encoding="utf-8")
    sp_file = pdir / "scene_plan.json"
    sp_file.write_text(json.dumps({}), encoding="utf-8")

    adapter = registry.get_agent("visual_planning")
    req = AgentRequest(project_id="base_agent_proj", agent_id="visual_planning", stage_id="planning")

    # Invocations without prior LLM review should execute but be blocked at the review gate
    res = adapter.invoke(pdir, req)
    assert res.status == "blocked"
    assert "Mandatory LLM review gate failed" in (res.error or "")


def test_cached_review_reused_without_duplicate_llm_call(tmp_path: Path, monkeypatch):
    """Verify that when review is fresh and force=False, no LLM call is made."""
    pdir = tmp_path / "cached_proj"
    pdir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("backend.store.project_dir", lambda p: tmp_path / p)

    seg_file = pdir / "scene_segmentation.json"
    seg_file.write_text(json.dumps({"scenes": []}), encoding="utf-8")
    tr_file = pdir / "transcript.json"
    tr_file.write_text(json.dumps({"text": "Hello"}), encoding="utf-8")
    vp_file = pdir / "visual_planning.json"
    vp_file.write_text(json.dumps({}), encoding="utf-8")
    sp_file = pdir / "scene_plan.json"
    sp_file.write_text(json.dumps({}), encoding="utf-8")
    pm_file = pdir / "prompts_map.json"
    pm_file.write_text(json.dumps({}), encoding="utf-8")

    mock_client = MagicMock()
    mock_client.resolve_provider_config.return_value = ("anthropic", "claude-3-5-sonnet-20241022", "dummy_key", "")
    mock_client.generate_text.return_value = json.dumps({
        "status": "passed",
        "score": 0.9,
        "summary": "First run",
        "findings": [],
    })

    with patch("backend.llm_gateway.llm_client", mock_client):
        res1 = llm_review.run_stage_llm_review(pdir, "planning")
        assert mock_client.generate_text.call_count == 1

        # Second call with force=False should reuse cache
        res2 = llm_review.run_stage_llm_review(pdir, "planning", force=False)
        assert mock_client.generate_text.call_count == 1
        assert res1["reviewed_at"] == res2["reviewed_at"]


def test_no_secrets_in_telemetry(tmp_path: Path, monkeypatch):
    """Verify that telemetry records do not contain secrets or API keys."""
    pdir = tmp_path / "secret_proj"
    pdir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("backend.store.project_dir", lambda p: tmp_path / p)

    mock_client = MagicMock()
    mock_client.resolve_provider_config.return_value = ("anthropic", "claude-3-5-sonnet-20241022", "sk-ant-api03-secret1234567890", "")
    mock_client.generate_text.return_value = '{"status": "passed", "score": 0.9, "summary": "Passed", "findings": []}'

    gw = LlmGateway(client_module=mock_client)
    req = LlmGatewayRequest(
        project_id="secret_proj",
        stage_id="planning",
        agent_id="visual_planning",
        purpose="review",
        user_prompt="Review prompt with api_key=sk-ant-api03-secret1234567890 in body",
        structured_schema={"status": "string"},
    )
    resp = gw.execute(req)
    assert resp.status == "passed"

    from backend.agents import get_communications_file
    cfile = get_communications_file("secret_proj")
    if cfile.exists():
        content = cfile.read_text(encoding="utf-8")
        assert "sk-ant-api03-secret1234567890" not in content
