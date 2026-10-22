"""Tests for the new Agent Registry and Communication FastAPI routes."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_get_agents_lists_15_agents():
    res = client.get("/agents")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) == 15
    ids = {a["agent_id"] for a in data}
    assert "main_orchestrator" in ids
    assert "audio_analyzer" in ids
    assert "final_video_delivery" in ids

    # Assert categories are present
    categories = {a["agent_id"]: a.get("category") for a in data}
    assert categories["main_orchestrator"] == "orchestrator"
    assert categories["audio_analyzer"] == "video_engine_agent"
    assert categories["final_video_delivery"] == "video_engine_agent"


def test_get_agent_detail_and_404():
    res = client.get("/agents/audio_analyzer")
    assert res.status_code == 200
    data = res.json()
    assert data["agent_id"] == "audio_analyzer"
    assert data["is_frozen"] is False                                   # the FROZEN markers were removed (2026-10-20)
    assert data["status"] == "implemented"

    res_404 = client.get("/agents/unknown_agent_xyz")
    assert res_404.status_code == 404


def test_post_and_get_project_communications(tmp_path, monkeypatch):
    pid = "route-test-proj"
    pdir = tmp_path / pid
    pdir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("backend.store.project_dir", lambda p: tmp_path / p)

    # 1. Post a communication message
    payload = {
        "stage_id": "motion_plan",
        "sender_agent_id": "visual_planning",
        "recipient_agent_ids": ["motion_planning"],
        "message_type": "handoff",
        "content": "Visual plan completed with 4 scenes; handoff to motion planning",
        "artifact_refs": [{"path": f"projects/{pid}/visual_planning.json", "description": "Visual Plan"}],
    }
    res_post = client.post(f"/projects/{pid}/agent-communications", json=payload)
    assert res_post.status_code == 201
    posted = res_post.json()
    assert posted["project_id"] == pid
    assert posted["sender_agent_id"] == "visual_planning"
    assert posted["sequence"] == 1

    # 2. Query communications
    res_get = client.get(f"/projects/{pid}/agent-communications")
    assert res_get.status_code == 200
    result = res_get.json()
    assert result["project_id"] == pid
    assert result["count"] == 1
    assert result["messages"][0]["content"] == payload["content"]

    # 3. Post with unknown sender rejected
    res_bad = client.post(
        f"/projects/{pid}/agent-communications",
        json={"stage_id": "test", "sender_agent_id": "fake_agent_xyz", "content": "Fake message"},
    )
    assert res_bad.status_code == 400
