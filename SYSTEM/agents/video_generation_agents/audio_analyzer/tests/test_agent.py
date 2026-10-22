"""Unit tests for AudioAnalyzerAgent."""
from SYSTEM.agents.video_generation_agents.audio_analyzer.agent import AudioAnalyzerAgent, AudioAnalyzerAdapter
from SYSTEM.agents.shared.contracts import AgentMetadata

def test_agent_instantiation():
    meta = AgentMetadata(
        agent_id="audio_analyzer",
        name="Audio Analyzer Agent",
        version="1.0.0",
        stage_id="analyzer"
    )
    agent = AudioAnalyzerAgent(meta)
    assert agent.agent_id == "audio_analyzer"
    assert agent.stage_id == "analyzer"
    assert agent.memory is not None
