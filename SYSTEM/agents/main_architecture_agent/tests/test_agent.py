"""Unit tests for MainArchitectureAgent."""
from pathlib import Path
from SYSTEM.agents.main_architecture_agent.agent import MainArchitectureAgent
from SYSTEM.agents.shared.contracts import AgentRequest

def test_main_architecture_agent_discovery(tmp_path):
    agent = MainArchitectureAgent()
    req = AgentRequest(agent_id=agent.agent_id, parameters={"action": "discover"})
    res = agent.execute(tmp_path, req)
    assert res.status == "succeeded"
    assert "agents" in res.metadata
    assert "skills" in res.metadata
    assert "tools" in res.metadata
    assert len(res.metadata["agents"]) >= 14

def test_main_architecture_agent_planning(tmp_path):
    agent = MainArchitectureAgent()
    req = AgentRequest(agent_id=agent.agent_id, parameters={"action": "plan", "goal": "Generate video from audio"})
    res = agent.execute(tmp_path, req)
    assert res.status == "succeeded"
    assert "tasks" in res.metadata
    assert len(res.metadata["tasks"]) >= 2
