"""Unit tests for MotionPlanningAgent."""
from SYSTEM.agents.video_generation_agents.motion_planning.agent import MotionPlanningAgent, MotionPlanningAdapter
from SYSTEM.agents.shared.contracts import AgentMetadata


def test_agent_instantiation():
    agent = MotionPlanningAgent()
    assert agent.agent_id == "motion_planning"
    assert agent.stage_id == "motion_plan"
    assert agent.metadata.version == "2.0.0"
    assert agent.memory is not None
    assert "cinematic-camera-choreography" in agent.metadata.capabilities
    assert "audio-reactive-intelligence" in agent.metadata.capabilities
    assert "collision-resolution" in agent.metadata.capabilities


def test_adapter_alias():
    adapter = MotionPlanningAdapter()
    assert isinstance(adapter, MotionPlanningAgent)
