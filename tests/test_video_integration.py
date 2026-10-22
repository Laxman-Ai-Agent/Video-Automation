"""The video project's side of the Agent System interface: importing VIDEO_ENGINE connects it, and its 15 agents then join a registry that on its own holds only the Agent System's 7."""
from SYSTEM.core import integrations

CAPABILITIES = {"agent_entries", "skill_seeds", "stage_dependencies", "pipeline_orchestrator", "system_capabilities", "jobs",
                "pipeline_state", "stage_gate", "pipeline_validator"}


def _empty_registry(monkeypatch):
    """No domain project is connected: nothing is provided and nothing will be loaded from the environment."""
    monkeypatch.setattr(integrations, "_providers", {})
    monkeypatch.setattr(integrations, "_factories", {})
    monkeypatch.setattr(integrations, "_failures", {})
    monkeypatch.setattr(integrations, "_configured_loaded", True)


def test_importing_the_video_engine_registers_what_it_provides():
    import VIDEO_ENGINE  # noqa: F401  registers the integration
    assert CAPABILITIES <= set(integrations.available())


def test_the_providers_are_the_real_engine_objects():
    import VIDEO_ENGINE  # noqa: F401
    from VIDEO_ENGINE.pipeline import orchestrator
    assert integrations.get("pipeline_orchestrator") is orchestrator.PipelineOrchestrator
    assert integrations.get("stage_dependencies") is orchestrator.STAGE_DEPENDENCIES
    assert integrations.get("system_capabilities") is orchestrator.check_system_capabilities
    assert hasattr(integrations.get("jobs"), "is_running") and hasattr(integrations.get("jobs"), "current")
    assert integrations.failures() == {}


def test_the_registry_holds_the_video_agents_only_because_the_video_project_is_connected(monkeypatch):
    import VIDEO_ENGINE  # noqa: F401
    from SYSTEM.registries.agent_registry import AgentRegistry

    connected = AgentRegistry()
    assert len(connected.list_video_agents()) == 15 and len(connected.list_system_agents()) == 7

    _empty_registry(monkeypatch)
    alone = AgentRegistry()
    assert alone.list_video_agents() == [] and len(alone.list_system_agents()) == 7
    assert {m.agent_id for m in alone.list_all_agents()} >= {"main_architecture_agent", "skill_factory", "capability_finder"}


def _private_skill_catalog(monkeypatch, tmp_path):
    from SYSTEM.registries import skill_registry
    monkeypatch.setattr(skill_registry, "SKILLS_DIR", tmp_path / "skills")
    monkeypatch.setattr(skill_registry, "STAGING_DIR", tmp_path / "staging")
    monkeypatch.setattr(skill_registry, "CATALOG_FILE", tmp_path / "catalog.json")
    return skill_registry


def test_the_skill_registry_holds_the_video_seed_skills_only_because_the_video_project_is_connected(monkeypatch, tmp_path):
    import VIDEO_ENGINE  # noqa: F401
    skill_registry = _private_skill_catalog(monkeypatch, tmp_path)
    assert len(skill_registry.SkillRegistry().list_skills()) == 21

    (tmp_path / "catalog.json").unlink()
    _empty_registry(monkeypatch)
    assert skill_registry.SkillRegistry().list_skills() == []


def test_a_project_that_connects_later_adds_its_seed_skills_to_an_existing_registry(monkeypatch, tmp_path):
    import VIDEO_ENGINE  # noqa: F401
    from SYSTEM.skills.video_seed_skills import video_seed_skills
    skill_registry = _private_skill_catalog(monkeypatch, tmp_path)
    _empty_registry(monkeypatch)
    registry = skill_registry.SkillRegistry()
    assert registry.list_skills() == []

    integrations.register("skill_seeds", video_seed_skills())
    assert len(registry.list_skills()) == 21


def test_a_project_that_connects_later_adds_its_agents_to_an_existing_registry(monkeypatch):
    import VIDEO_ENGINE  # noqa: F401
    from SYSTEM.agents.video_generation_agents.registry_entries import video_agent_entries
    from SYSTEM.registries.agent_registry import AgentRegistry

    _empty_registry(monkeypatch)
    registry = AgentRegistry()
    assert registry.list_video_agents() == []

    integrations.register("agent_entries", video_agent_entries())            # the project connects after the registry exists
    assert len(registry.list_video_agents()) == 15
