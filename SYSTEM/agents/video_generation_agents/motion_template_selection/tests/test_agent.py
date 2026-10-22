"""Unit tests for MotionTemplateSelectionAgent."""
from SYSTEM.agents.video_generation_agents.motion_template_selection.agent import MotionTemplateSelectionAgent, MotionTemplateSelectionAdapter
from SYSTEM.agents.shared.contracts import AgentMetadata

def test_agent_instantiation():
    meta = AgentMetadata(
        agent_id="motion_template_selection",
        name="Motion Template Selection Agent (Internal Helper)",
        version="1.0.0",
        stage_id="motion_template"
    )
    agent = MotionTemplateSelectionAgent(meta)
    assert agent.agent_id == "motion_template_selection"
    assert agent.stage_id == "motion_template"
    assert agent.memory is not None
