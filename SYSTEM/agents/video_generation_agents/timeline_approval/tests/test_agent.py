"""Unit tests for TimelineApprovalAgent."""
from SYSTEM.agents.video_generation_agents.timeline_approval.agent import TimelineApprovalAgent, TimelineApprovalAdapter
from SYSTEM.agents.shared.contracts import AgentMetadata

def test_agent_instantiation():
    meta = AgentMetadata(
        agent_id="timeline_approval",
        name="Timeline Approval Agent",
        version="1.0.0",
        stage_id="approval"
    )
    agent = TimelineApprovalAgent(meta)
    assert agent.agent_id == "timeline_approval"
    assert agent.stage_id == "approval"
    assert agent.memory is not None
