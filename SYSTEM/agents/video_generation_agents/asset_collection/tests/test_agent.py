"""Unit tests for AssetCollectionAgent (the stage logic itself is tested in tests/test_asset_collection.py)."""
import json

from SYSTEM.agents.shared.contracts import AgentMetadata, AgentRequest
from SYSTEM.agents.video_generation_agents.asset_collection.agent import AssetCollectionAdapter, AssetCollectionAgent
from VIDEO_ENGINE.stages import asset_collection


def test_agent_instantiation():
    agent = AssetCollectionAgent(AgentMetadata(agent_id="asset_collection", name="Asset Collection Agent", version="1.0.0", stage_id="assets"))
    assert agent.agent_id == "asset_collection" and agent.stage_id == "assets" and agent.memory is not None
    assert AssetCollectionAdapter is AssetCollectionAgent


def test_default_metadata_binds_the_assets_stage():
    agent = AssetCollectionAgent()
    assert agent.metadata.stage_id == "assets" and "rights-and-provenance-tracking" in agent.metadata.capabilities


def test_validate_requires_the_scene_plan(tmp_path):
    agent = AssetCollectionAgent()
    req = AgentRequest(project_id="p", agent_id="asset_collection", stage_id="assets")
    assert agent.validate(tmp_path, req) and "scene_plan.json" in agent.validate(tmp_path, req)[0]
    (tmp_path / "scene_plan.json").write_text(json.dumps({"scenes": []}), encoding="utf-8")
    assert agent.validate(tmp_path, req) == []


def test_a_failed_stage_reports_the_exact_cause(tmp_path, monkeypatch):
    def boom(pdir, aspect, force=False):
        raise asset_collection.AssetError("no acceptable real media for req_1_1 (no usable candidate)")
    monkeypatch.setattr(asset_collection, "run", boom)
    res = AssetCollectionAgent().execute(tmp_path, AgentRequest(project_id="p", agent_id="asset_collection", stage_id="assets", parameters={"aspect": "16:9"}))
    assert res.status == "failed" and "req_1_1" in res.error


def test_zero_requirements_complete_without_error(tmp_path, monkeypatch):
    empty = {"schema": "assets-manifest", "assets": [], "fallbacks": [], "requirement_count": 0}
    monkeypatch.setattr(asset_collection, "run", lambda pdir, aspect, force=False: empty)
    res = AssetCollectionAgent().execute(tmp_path, AgentRequest(project_id="p", agent_id="asset_collection", stage_id="assets", parameters={"aspect": "16:9"}))
    assert res.status == "succeeded" and res.summary == "no scene needs real media" and res.metadata["assets"] == 0
