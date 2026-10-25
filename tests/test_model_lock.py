"""Comprehensive regression tests for Active Coding Session Model Lock.

Verifies:
1. Strict locking to the explicitly configured AI provider and model.
2. Complete elimination of silent fallbacks (no switching to claude_cli, gemini, or other providers).
3. Complete elimination of silent model swapping on 429 / quota exhaustion.
4. Gateways fail fast and report exact reasons on unavailable models or quota limits.
5. Exact model preservation across logical profiles (fast_structured, reasoning_review, etc.).
6. Telemetry and public configuration never expose secrets.
7. Explicit configuration persistence across reloads.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend import llm_client, llm_gateway
from backend.llm_gateway import LlmGateway, LlmGatewayRequest

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_llm_config(tmp_path, monkeypatch):
    """Ensure tests run in isolated config directory and do not mutate disk config."""
    monkeypatch.setattr(llm_client, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(llm_client, "CONFIG_FILE", tmp_path / "llm_settings.json")
    monkeypatch.setattr(llm_client, "STATUS_FILE", tmp_path / "llm_status.json")


def test_model_lock_centralized_configuration_structure():
    """Verify Active Model Configuration exposes authoritative fields."""
    llm_client.save_settings({
        "provider": "gemini",
        "model": "gemini-3.5-flash",
        "api_key": "AIzaSyTestKey1234567890",
    })
    cfg = llm_client.get_active_model_config()

    assert cfg["model_locked"] is True
    assert cfg["active_provider"] == "gemini"
    assert cfg["active_provider_name"] == "Google Gemini"
    assert cfg["active_model"] == "gemini-3.5-flash"
    assert cfg["auth_method"] == "api_key"
    assert cfg["auth_method_name"] == "API Key"
    assert cfg["has_credentials"] is True
    assert cfg["has_api_key"] is True
    assert cfg["api_key_masked"] == "AIza••••7890"
    assert "AIzaSyTestKey1234567890" not in json.dumps(cfg)


def test_model_lock_prohibits_silent_fallback_when_api_key_missing(monkeypatch):
    """When an API provider is configured without a key, it must NOT silently fall back to claude_cli or gemini."""
    monkeypatch.setattr(llm_client.shutil, "which", lambda t: "/usr/local/bin/claude" if t == "claude" else None)
    for k in ("LLM_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY"):
        monkeypatch.delenv(k, raising=False)

    # Save OpenAI with no key
    llm_client.save_settings({"provider": "openai", "model": "gpt-4o-mini", "api_key": ""})

    prov, model, key, _ = llm_client.resolve_provider_config()
    assert prov == "openai"
    assert model == "gpt-4o-mini"
    assert key == ""

    # Test connection must report offline and missing key for OpenAI, NOT switch to claude_cli
    t_res = llm_client.test_connection()
    assert t_res["ok"] is False
    assert t_res["provider"] == "openai"
    assert "API key is missing" in t_res["message"]
    assert "Silent fallback disabled" in t_res["message"]


def test_model_lock_profile_routing_preserves_locked_model():
    """When a model is explicitly locked, gateway profile routing must NOT substitute it with another model."""
    gw = LlmGateway()

    # User explicitly configured gemini-3.5-flash
    configured = "gemini-3.5-flash"
    assert gw.resolve_model_for_profile("gemini", "fast_structured", configured_model=configured) == "gemini-3.5-flash"
    assert gw.resolve_model_for_profile("gemini", "reasoning_review", configured_model=configured) == "gemini-3.5-flash"
    assert gw.resolve_model_for_profile("gemini", "code_generation", configured_model=configured) == "gemini-3.5-flash"

    # User explicitly configured gpt-4o
    configured_openai = "gpt-4o"
    assert gw.resolve_model_for_profile("openai", "fast_structured", configured_model=configured_openai) == "gpt-4o"
    assert gw.resolve_model_for_profile("openai", "reasoning_review", configured_model=configured_openai) == "gpt-4o"


def test_model_lock_fails_fast_on_quota_exhaustion_without_silent_switching():
    """When 429 quota limit is encountered, gateway stops immediately and does NOT silently switch models or providers."""
    mock_client = MagicMock()
    mock_client.resolve_provider_config.return_value = ("groq", "llama-3.3-70b-versatile", "gsk_test_key", "")
    mock_client.generate_text.side_effect = llm_client.LlmError("429 Too Many Requests: Rate limit reached. Exceeded your current quota.")

    gw = LlmGateway(client_module=mock_client)
    req = LlmGatewayRequest(
        project_id="test_lock_proj",
        stage_id="planning",
        agent_id="visual_planning",
        purpose="decision",
        user_prompt="Generate plan",
        max_retries=3,
    )

    resp = gw.execute(req)
    assert resp.status == "blocked"
    assert "quota" in (resp.error or "").lower()
    # Fast failed on attempt 1 because quota exhaustion is non-retryable
    assert resp.attempt_count == 1
    # Model remained strictly the locked model
    assert resp.provider == "groq"
    assert resp.model == "llama-3.3-70b-versatile"


def test_model_lock_claude_cli_subscription_isolation():
    """Verify Claude Code local CLI uses cli_subscription auth method and respects locked model."""
    llm_client.save_settings({
        "provider": "claude_cli",
        "model": "claude-3-5-sonnet-20241022",
    })
    cfg = llm_client.get_active_model_config()
    assert cfg["active_provider"] == "claude_cli"
    assert cfg["active_model"] == "claude-3-5-sonnet-20241022"
    assert cfg["auth_method"] == "cli_subscription"
    assert cfg["auth_method_name"] == "CLI Subscription"


def test_model_lock_api_key_redaction_in_gateway_errors():
    """Verify that even on provider failure, API keys in errors are sanitized."""
    mock_client = MagicMock()
    secret = "sk-live-998877665544332211"
    mock_client.resolve_provider_config.return_value = ("openai", "gpt-4o-mini", secret, "")
    mock_client.generate_text.side_effect = RuntimeError(f"Connection failed to endpoint with key={secret}")

    gw = LlmGateway(client_module=mock_client)
    req = LlmGatewayRequest(
        project_id="redact_proj",
        stage_id="review",
        agent_id="qc",
        purpose="review",
        user_prompt="Review text",
        max_retries=1,
    )

    resp = gw.execute(req)
    assert resp.status == "blocked"
    assert secret not in (resp.error or "")
    assert "[REDACTED" in (resp.error or "")
