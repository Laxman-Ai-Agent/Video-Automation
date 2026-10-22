"""Unit tests for FinalQcAgent."""
from SYSTEM.agents.video_generation_agents.final_qc.agent import FinalQcAgent, FinalQcAdapter
from SYSTEM.agents.shared.contracts import AgentMetadata

def test_agent_instantiation():
    meta = AgentMetadata(
        agent_id="final_qc",
        name="Final QC Agent",
        version="1.0.0",
        stage_id="qc"
    )
    agent = FinalQcAgent(meta)
    assert agent.agent_id == "final_qc"
    assert agent.stage_id == "qc"
    assert agent.memory is not None
