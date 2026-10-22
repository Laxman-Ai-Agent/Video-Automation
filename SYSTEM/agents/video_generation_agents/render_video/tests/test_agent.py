"""Unit tests for RenderVideoAgent."""
from SYSTEM.agents.video_generation_agents.render_video.agent import RenderVideoAgent, RenderVideoAdapter
from SYSTEM.agents.shared.contracts import AgentMetadata

def test_agent_instantiation():
    meta = AgentMetadata(
        agent_id="render_video",
        name="Render Video Agent",
        version="1.0.0",
        stage_id="render"
    )
    agent = RenderVideoAgent(meta)
    assert agent.agent_id == "render_video"
    assert agent.stage_id == "render"
    assert agent.memory is not None
