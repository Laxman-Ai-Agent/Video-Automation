"""Unit tests for MainOrchestratorAgent."""
from SYSTEM.agents.video_generation_agents.main_orchestrator.agent import MainOrchestratorAgent, MainOrchestratorAdapter
from SYSTEM.agents.shared.contracts import AgentMetadata

def test_agent_instantiation():
    meta = AgentMetadata(
        agent_id="main_orchestrator",
        name="Main Orchestrator Agent",
        version="1.0.0",
        stage_id="pipeline"
    )
    agent = MainOrchestratorAgent(meta)
    assert agent.agent_id == "main_orchestrator"
    assert agent.stage_id == "pipeline"
    assert agent.memory is not None
