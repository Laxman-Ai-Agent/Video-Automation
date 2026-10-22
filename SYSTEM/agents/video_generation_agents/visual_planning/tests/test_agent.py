"""Unit tests for VisualPlanningAgent."""
from SYSTEM.agents.video_generation_agents.visual_planning.agent import VisualPlanningAgent, VisualPlanningAdapter
from SYSTEM.agents.shared.contracts import AgentMetadata

def test_agent_instantiation():
    meta = AgentMetadata(
        agent_id="visual_planning",
        name="Visual Planning Agent",
        version="1.0.0",
        stage_id="planning"
    )
    agent = VisualPlanningAgent(meta)
    assert agent.agent_id == "visual_planning"
    assert agent.stage_id == "planning"
    assert agent.memory is not None
