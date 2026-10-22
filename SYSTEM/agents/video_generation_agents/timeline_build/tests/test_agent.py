"""Unit tests for TimelineBuildAgent."""
from SYSTEM.agents.video_generation_agents.timeline_build.agent import TimelineBuildAgent, TimelineBuildAdapter
from SYSTEM.agents.shared.contracts import AgentMetadata

def test_agent_instantiation():
    meta = AgentMetadata(
        agent_id="timeline_build",
        name="Timeline Build Agent",
        version="1.0.0",
        stage_id="timeline"
    )
    agent = TimelineBuildAgent(meta)
    assert agent.agent_id == "timeline_build"
    assert agent.stage_id == "timeline"
    assert agent.memory is not None
