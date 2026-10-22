"""Unit tests for MotionValidationAgent."""
from SYSTEM.agents.video_generation_agents.motion_timeline_validation.agent import MotionValidationAgent, MotionValidationAdapter
from SYSTEM.agents.shared.contracts import AgentMetadata

def test_agent_instantiation():
    meta = AgentMetadata(
        agent_id="motion_timeline_validation",
        name="Motion Validation Agent",
        version="1.0.0",
        stage_id="motion_validation"
    )
    agent = MotionValidationAgent(meta)
    assert agent.agent_id == "motion_timeline_validation"
    assert agent.stage_id == "motion_validation"
    assert agent.memory is not None
