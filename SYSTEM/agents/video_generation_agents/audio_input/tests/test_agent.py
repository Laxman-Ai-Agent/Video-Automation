"""Unit tests for AudioInputAgent."""
from SYSTEM.agents.video_generation_agents.audio_input.agent import AudioInputAgent, AudioInputAdapter
from SYSTEM.agents.shared.contracts import AgentMetadata

def test_agent_instantiation():
    meta = AgentMetadata(
        agent_id="audio_input",
        name="Audio Input Agent",
        version="1.0.0",
        stage_id="audio"
    )
    agent = AudioInputAgent(meta)
    assert agent.agent_id == "audio_input"
    assert agent.stage_id == "audio"
    assert agent.memory is not None
