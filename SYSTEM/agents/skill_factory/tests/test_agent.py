"""Unit tests for canonical SkillFactoryAgent."""
from pathlib import Path
from SYSTEM.agents.skill_factory.agent import SkillFactoryAgent
from SYSTEM.agents.shared.contracts import AgentRequest


def test_skill_factory_audit_safe(tmp_path: Path):
    agent = SkillFactoryAgent()
    safe_content = "---\nname: test_skill\nversion: 1.0.0\n---\n# Safe skill\nInstructions here."
    req = AgentRequest(agent_id=agent.agent_id, parameters={"action": "audit", "content": safe_content})
    res = agent.execute(tmp_path, req)
    assert res.status == "succeeded"
    assert res.metadata.get("is_safe") is True


def test_skill_factory_rejects_dangerous_shell(tmp_path: Path):
    agent = SkillFactoryAgent()
    unsafe_content = "---\nname: bad_skill\n---\n```bash\nrm -rf / --no-preserve-root\n```"
    req = AgentRequest(agent_id=agent.agent_id, parameters={"action": "audit", "content": unsafe_content})
    res = agent.execute(tmp_path, req)
    assert res.status == "blocked"
    assert res.metadata.get("is_safe") is False


def test_skill_factory_metadata():
    agent = SkillFactoryAgent()
    assert agent.agent_id == "skill_factory"
    assert agent.metadata.category.value == "system_subagent"
    assert "skill-authoring" in agent.metadata.capabilities
