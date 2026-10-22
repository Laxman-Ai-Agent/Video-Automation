"""Unit tests for MotionAnimationAgent."""
from SYSTEM.agents.video_generation_agents.motion_animation.agent import MotionAnimationAgent, MotionAnimationAdapter
from SYSTEM.agents.shared.contracts import AgentMetadata

def test_agent_instantiation():
    meta = AgentMetadata(
        agent_id="motion_animation",
        name="Motion Animation Agent",
        version="1.0.0",
        stage_id="motion_gen"
    )
    agent = MotionAnimationAgent(meta)
    assert agent.agent_id == "motion_animation"
    assert agent.stage_id == "motion_gen"
    assert agent.memory is not None
