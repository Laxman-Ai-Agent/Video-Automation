"""Unit tests for SceneSegmentationAgent."""
from SYSTEM.agents.video_generation_agents.scene_segmentation.agent import SceneSegmentationAgent, SceneSegmentationAdapter
from SYSTEM.agents.shared.contracts import AgentMetadata


def test_agent_instantiation():
    agent = SceneSegmentationAgent()
    assert agent.agent_id == "scene_segmentation"
    assert agent.stage_id == "segmentation"
    assert agent.metadata.version == "2.0.0"
    assert agent.memory is not None
    assert "topic-modeling" in agent.metadata.capabilities
    assert "adaptive-pacing" in agent.metadata.capabilities
    assert "vocabulary-standardization" in agent.metadata.capabilities


def test_adapter_alias():
    adapter = SceneSegmentationAdapter()
    assert isinstance(adapter, SceneSegmentationAgent)
