"""Unit and integration tests for Development LLM Usage & Estimated Cost Monitor."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend import llm_usage


@pytest.fixture
def temp_metrics_file(tmp_path):
    """Create a temporary costs.jsonl with realistic Claude Code snapshots."""
    metrics_path = tmp_path / "costs.jsonl"
    records = [
        # Session 1 - snapshot 1
        {
            "timestamp": "2026-10-07T10:00:00Z",
            "session_id": "session_1",
            "transcript_path": "C:\\Users\\dev\\.claude\\projects\\E--audio-to-video\\session_1.jsonl",
            "model": "claude-sonnet-5-5",
            "input_tokens": 1000,
            "output_tokens": 5000,
            "cache_read_tokens": 20000,
            "cache_write_tokens": 1000,
            "estimated_cost_usd": 0.085,
        },
        # Session 1 - snapshot 2 (later timestamp, cumulative)
        {
            "timestamp": "2026-10-07T10:15:00Z",
            "session_id": "session_1",
            "transcript_path": "C:\\Users\\dev\\.claude\\projects\\E--audio-to-video\\session_1.jsonl",
            "model": "claude-sonnet-5-5",
            "input_tokens": 1500,
            "output_tokens": 8000,
            "cache_read_tokens": 30000,
            "cache_write_tokens": 2000,
            "estimated_cost_usd": 0.135,
        },
        # Session 2 - another model in the same repo
        {
            "timestamp": "2026-10-08T09:00:00Z",
            "session_id": "session_2",
            "transcript_path": "C:\\Users\\dev\\.claude\\projects\\Video_Generation_Agent\\session_2.jsonl",
            "model": "claude-haiku-4-5-20251001",
            "input_tokens": 500,
            "output_tokens": 2000,
            "cache_read_tokens": 10000,
            "cache_write_tokens": 500,
            "estimated_cost_usd": 0.012,
        },
        # Session 3 - unrelated repo (should be filtered out!)
        {
            "timestamp": "2026-10-08T11:00:00Z",
            "session_id": "unrelated_session",
            "transcript_path": "C:\\Users\\dev\\.claude\\projects\\Unrelated-Ecommerce\\session_x.jsonl",
            "model": "claude-sonnet-5-5",
            "input_tokens": 50000,
            "output_tokens": 100000,
            "estimated_cost_usd": 15.0,
        },
    ]

    with open(metrics_path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    return metrics_path


def test_model_pricing_lookup():
    """Verify exact and fuzzy model pricing lookups."""
    pricing_sonnet = llm_usage.get_model_pricing("claude-sonnet-5-5")
    assert pricing_sonnet["input"] == 3.0
    assert pricing_sonnet["output"] == 15.0

    pricing_flash = llm_usage.get_model_pricing("gemini-2.0-flash")
    assert pricing_flash["input"] == 0.10
    assert pricing_flash["output"] == 0.40

    pricing_unknown = llm_usage.get_model_pricing("custom-experimental-model")
    assert pricing_unknown["input"] == llm_usage.DEFAULT_FALLBACK_PRICING["input"]


def test_estimate_cost_usd():
    """Verify cost calculations using token quantities and rates."""
    # 1M input of sonnet = $3.00, 1M output = $15.00
    cost = llm_usage.estimate_cost_usd("claude-sonnet-5-5", 1_000_000, 1_000_000)
    assert abs(cost - 18.0) < 0.001

    # Gemini 2.0 Flash: 100k input = $0.01, 100k output = $0.04
    cost_gemini = llm_usage.estimate_cost_usd("gemini-2.0-flash", 100_000, 100_000)
    assert abs(cost_gemini - 0.05) < 0.0001


def test_parse_claude_code_sessions_deduplication(temp_metrics_file, monkeypatch, tmp_path):
    """Verify deduplication by session_id and repository path filtering."""
    temp_storage = tmp_path / "llm_usage.json"
    monkeypatch.setattr(llm_usage, "USAGE_STORAGE_FILE", temp_storage)

    sessions = llm_usage.read_claude_code_sessions(metrics_file=temp_metrics_file)

    # Exactly 2 sessions should match (session_1 and session_2).
    # Unrelated repo should be ignored.
    assert len(sessions) == 2
    session_ids = {s["session_id"] for s in sessions}
    assert session_ids == {"session_1", "session_2"}

    # Session 1 should pick the latest snapshot (snapshot 2): input=1500, output=8000
    s1 = next(s for s in sessions if s["session_id"] == "session_1")
    assert s1["input_tokens"] == 1500
    assert s1["output_tokens"] == 8000
    assert s1["is_subscription"] is True
    assert s1["cost_usd"] == 0.135


def test_record_backend_usage_deduplication(tmp_path, monkeypatch):
    """Verify backend token tracking persists and avoids duplicates."""
    temp_storage = tmp_path / "llm_usage.json"
    monkeypatch.setattr(llm_usage, "USAGE_STORAGE_FILE", temp_storage)

    # First call records
    rec1 = llm_usage.record_backend_usage("gemini", "gemini-2.0-flash", 500, 1500, task="motion_plan")
    assert rec1 is not None
    assert rec1["input_tokens"] == 500
    assert rec1["output_tokens"] == 1500
    assert rec1["cost_usd"] > 0

    # Identical call within the same run is deduplicated
    rec2 = llm_usage.record_backend_usage("gemini", "gemini-2.0-flash", 500, 1500, task="motion_plan")
    assert rec2 is None

    # Different tokens or task records
    rec3 = llm_usage.record_backend_usage("openai", "gpt-4o-mini", 600, 2000, task="qc_review")
    assert rec3 is not None
    assert rec3["provider"] == "openai"


def test_usage_summary_aggregation(temp_metrics_file, tmp_path, monkeypatch):
    """Verify summary compiles INR, USD, tokens, and model breakdowns."""
    temp_storage = tmp_path / "llm_usage.json"
    monkeypatch.setattr(llm_usage, "USAGE_STORAGE_FILE", temp_storage)
    monkeypatch.setattr(llm_usage, "CLAUDE_METRICS_PATH", temp_metrics_file)

    # Record one backend API usage
    llm_usage.record_backend_usage("gemini", "gemini-2.0-flash", 1000, 2000, task="scene_planning")

    summary = llm_usage.get_usage_summary()

    # Total tokens = session_1 (9,500) + session_2 (2,500) + backend (3,000) = 15,000
    assert summary["total_tokens"] == 15000
    assert summary["total_input_tokens"] == 3000
    assert summary["total_output_tokens"] == 12000

    # Pricing & Currency
    assert summary["usd_to_inr_rate"] == 86.0
    assert summary["total_cost_usd"] > 0
    assert summary["total_cost_inr"] == round(summary["total_cost_usd"] * 86.0, 2)

    # By source
    assert "claude_code" in summary["by_source"]
    assert summary["by_source"]["claude_code"]["is_subscription"] is True
    assert "backend_api" in summary["by_source"]
    assert summary["by_source"]["backend_api"]["is_subscription"] is False

    # Models breakdown
    assert "claude-sonnet-5-5" in summary["by_model"]
    assert "claude-haiku-4-5-20251001" in summary["by_model"]
    assert "gemini-2.0-flash" in summary["by_model"]


def test_api_routes_usage_and_refresh(temp_metrics_file, tmp_path, monkeypatch):
    """Verify GET /llm/usage and POST /llm/usage/refresh endpoints via TestClient."""
    temp_storage = tmp_path / "llm_usage.json"
    monkeypatch.setattr(llm_usage, "USAGE_STORAGE_FILE", temp_storage)
    monkeypatch.setattr(llm_usage, "CLAUDE_METRICS_PATH", temp_metrics_file)

    client = TestClient(app)

    res = client.get("/llm/usage")
    assert res.status_code == 200
    data = res.json()
    assert "total_tokens" in data
    assert "total_cost_inr" in data
    assert "by_model" in data
    assert "subscription_disclaimer" in data

    # POST refresh
    res_refresh = client.post("/llm/usage/refresh")
    assert res_refresh.status_code == 200
    refreshed_data = res_refresh.json()
    assert refreshed_data["records_count"] == 2


def test_cache_token_pricing():
    """Verify cost calculation with cache read and cache write tokens."""
    # claude-sonnet-5-5: input: 3.0, output: 15.0, cache_read: 0.30, cache_write: 3.75
    # 100k input ($0.30) + 10k output ($0.15) + 500k cache read ($0.15) + 50k cache write ($0.1875) = $0.7875
    cost = llm_usage.estimate_cost_usd(
        model="claude-sonnet-5-5",
        input_tokens=100_000,
        output_tokens=10_000,
        cache_read_tokens=500_000,
        cache_write_tokens=50_000,
    )
    assert abs(cost - 0.7875) < 0.0001


def test_get_usage_history_filtering_and_pagination(temp_metrics_file, tmp_path, monkeypatch):
    """Verify get_usage_history with search, source filtering, and pagination."""
    temp_storage = tmp_path / "llm_usage.json"
    monkeypatch.setattr(llm_usage, "USAGE_STORAGE_FILE", temp_storage)
    monkeypatch.setattr(llm_usage, "CLAUDE_METRICS_PATH", temp_metrics_file)

    # Insert backend records
    llm_usage.record_backend_usage("gemini", "gemini-2.0-flash", 100, 200, task="visual_storyboard")
    llm_usage.record_backend_usage("openai", "gpt-4o-mini", 300, 400, task="qc_validation")

    # Total: 2 Claude Code sessions + 2 backend API records = 4 records
    all_history = llm_usage.get_usage_history(limit=10, offset=0)
    assert all_history["total_count"] == 4
    assert len(all_history["items"]) == 4

    # Pagination: limit=2, offset=0
    page1 = llm_usage.get_usage_history(limit=2, offset=0)
    assert len(page1["items"]) == 2
    assert page1["limit"] == 2
    assert page1["offset"] == 0

    # Source filter: claude_code
    claude_only = llm_usage.get_usage_history(source="claude_code")
    assert claude_only["total_count"] == 2
    assert all(r["source"] == "claude_code" for r in claude_only["items"])

    # Source filter: backend_api
    backend_only = llm_usage.get_usage_history(source="backend_api")
    assert backend_only["total_count"] == 2
    assert all(r["source"] == "backend_api" for r in backend_only["items"])

    # Search filter by task
    searched = llm_usage.get_usage_history(search="visual_storyboard")
    assert searched["total_count"] == 1
    assert searched["items"][0]["task"] == "visual_storyboard"

    # Search filter by session_id
    searched_sess = llm_usage.get_usage_history(search="session_1")
    assert searched_sess["total_count"] == 1
    assert searched_sess["items"][0]["session_id"] == "session_1"


def test_update_usage_settings(temp_metrics_file, tmp_path, monkeypatch):
    """Verify custom USD-to-INR rate updates and model pricing overrides."""
    temp_storage = tmp_path / "llm_usage.json"
    monkeypatch.setattr(llm_usage, "USAGE_STORAGE_FILE", temp_storage)
    monkeypatch.setattr(llm_usage, "CLAUDE_METRICS_PATH", temp_metrics_file)

    # Initial rate is 86.0
    summary_before = llm_usage.get_usage_summary()
    assert summary_before["usd_to_inr_rate"] == 86.0

    # Update to 90.0
    updated_summary = llm_usage.update_usage_settings(
        usd_to_inr=90.0,
        model_pricing_overrides={"custom-test-model": {"input": 5.0, "output": 20.0}},
    )
    assert updated_summary["usd_to_inr_rate"] == 90.0
    assert updated_summary["total_cost_inr"] == round(updated_summary["total_cost_usd"] * 90.0, 2)

    # Verify custom pricing is effective
    pricing = llm_usage.get_model_pricing("custom-test-model")
    assert pricing["input"] == 5.0
    assert pricing["output"] == 20.0


def test_api_routes_history_and_settings(temp_metrics_file, tmp_path, monkeypatch):
    """Verify GET /llm/usage/history and POST /llm/usage/settings API endpoints."""
    temp_storage = tmp_path / "llm_usage.json"
    monkeypatch.setattr(llm_usage, "USAGE_STORAGE_FILE", temp_storage)
    monkeypatch.setattr(llm_usage, "CLAUDE_METRICS_PATH", temp_metrics_file)

    client = TestClient(app)

    # Test GET /llm/usage/history
    res_hist = client.get("/llm/usage/history?source=claude_code&limit=10")
    assert res_hist.status_code == 200
    hist_data = res_hist.json()
    assert hist_data["total_count"] == 2
    assert len(hist_data["items"]) == 2

    # Test POST /llm/usage/settings
    res_settings = client.post("/llm/usage/settings", json={"usd_to_inr": 88.5})
    assert res_settings.status_code == 200
    settings_data = res_settings.json()
    assert settings_data["usd_to_inr_rate"] == 88.5

