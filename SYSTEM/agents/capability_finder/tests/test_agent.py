"""Unit tests for canonical CapabilityFinderAgent."""
from pathlib import Path
from SYSTEM.agents.capability_finder.agent import CapabilityFinderAgent
from SYSTEM.agents.shared.contracts import AgentRequest


def test_capability_finder_execution_backward_compat(tmp_path: Path):
    agent = CapabilityFinderAgent()
    req = AgentRequest(agent_id=agent.agent_id, parameters={"query": "audio"})
    res = agent.execute(tmp_path, req)
    assert res.status == "succeeded"
    assert "matching_agents" in res.metadata
    assert "matching_skills" in res.metadata
    assert "available_tools" in res.metadata
    assert "prerequisites" in res.metadata


def test_capability_finder_natural_language_discovery(tmp_path: Path):
    agent = CapabilityFinderAgent()
    query = "Create an animated stacked bar chart for a 9:16 video with Telugu labels, smooth transitions, and deterministic rendering."
    req = AgentRequest(agent_id=agent.agent_id, parameters={"query": query})
    res = agent.execute(tmp_path, req)

    assert res.status == "succeeded"
    # Phase 2 upgraded metadata
    assert "parsed_requirement" in res.metadata
    parsed = res.metadata["parsed_requirement"]
    assert parsed["primary_capability"] == "data_visualization"
    assert parsed["constraints"]["aspect_ratio"] == "9:16"
    assert parsed["constraints"]["language"] == "telugu"

    assert "gap_analysis" in res.metadata
    gap = res.metadata["gap_analysis"]
    assert gap["overall_status"] in ("satisfied", "partial", "missing")
    assert "recommended_action" in res.metadata
    assert res.metadata["recommended_action"] in ("REUSE", "ADAPT", "CREATE_SKILL", "CREATE_AGENT")


def test_capability_finder_sync_registry_action(tmp_path: Path):
    agent = CapabilityFinderAgent()
    req = AgentRequest(agent_id=agent.agent_id, parameters={"action": "sync_registry"})
    res = agent.execute(tmp_path, req)

    assert res.status == "succeeded"
    assert "sync_report" in res.metadata
    assert res.metadata["sync_report"]["total_records"] > 0


def test_capability_finder_ast_scan_action(tmp_path: Path):
    agent = CapabilityFinderAgent()
    req = AgentRequest(agent_id=agent.agent_id, parameters={"action": "ast_scan", "target_path": str(tmp_path)})
    (tmp_path / "mock.py").write_text("class MockAgent:\n    capabilities = ['test']\n", encoding="utf-8")
    res = agent.execute(tmp_path, req)

    assert res.status == "succeeded"
    assert "discovered_symbols" in res.metadata
    assert len(res.metadata["discovered_symbols"]) >= 1


def test_capability_finder_metadata():
    agent = CapabilityFinderAgent()
    assert agent.agent_id == "capability_finder"
    assert agent.metadata.category.value == "system_subagent"
    assert "capability-query" in agent.metadata.capabilities
    assert "requirement-parsing" in agent.metadata.capabilities
    assert "ast-discovery" in agent.metadata.capabilities
    assert "gap-analysis" in agent.metadata.capabilities
