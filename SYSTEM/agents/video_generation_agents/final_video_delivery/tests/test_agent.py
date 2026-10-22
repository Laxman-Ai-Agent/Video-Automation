"""Unit tests for FinalVideoDeliveryAgent."""
from SYSTEM.agents.video_generation_agents.final_video_delivery.agent import FinalVideoDeliveryAgent, FinalVideoDeliveryAdapter
from SYSTEM.agents.shared.contracts import AgentMetadata

def test_agent_instantiation():
    meta = AgentMetadata(
        agent_id="final_video_delivery",
        name="Final Video Delivery Agent",
        version="1.0.0",
        stage_id="final"
    )
    agent = FinalVideoDeliveryAgent(meta)
    assert agent.agent_id == "final_video_delivery"
    assert agent.stage_id == "final"
    assert agent.memory is not None
