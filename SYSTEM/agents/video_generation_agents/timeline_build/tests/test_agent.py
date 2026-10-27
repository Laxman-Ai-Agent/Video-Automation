"""Unit tests for TimelineBuildAgent."""
from SYSTEM.agents.video_generation_agents.timeline_build.agent import TimelineBuildAgent, TimelineBuildAdapter
from SYSTEM.agents.shared.contracts import AgentMetadata

def test_agent_instantiation():
    meta = AgentMetadata(
        agent_id="timeline_build",
        name="Timeline Build Agent",
        version="1.0.0",
        stage_id="timeline"
    )
    agent = TimelineBuildAgent(meta)
    assert agent.agent_id == "timeline_build"
    assert agent.stage_id == "timeline"
    assert agent.memory is not None


def test_a_stale_completed_report_is_rebuilt_not_accepted(tmp_path, monkeypatch):
    """Regression: a published report whose inputs changed (status 'completed' on old inputs) used to be taken as the result, so the approval then found the timeline stale."""
    import json
    from types import SimpleNamespace
    from VIDEO_ENGINE.pipeline import legacy_pipeline_adapter
    from VIDEO_ENGINE.stages import timeline_build
    (tmp_path / "timeline.json").write_text("{}")
    (tmp_path / "timeline_build_report.json").write_text(json.dumps({"status": "completed"}))
    ran = []
    monkeypatch.setattr(legacy_pipeline_adapter, "execute", lambda *a, **k: None)
    monkeypatch.setattr(timeline_build, "load", lambda *a: {"current": False, "status": "stale", "report": {"status": "completed"}})
    monkeypatch.setattr(timeline_build, "run", lambda *a, **k: ran.append(1) or {"status": "blocked", "findings": []})
    agent = TimelineBuildAgent(AgentMetadata(agent_id="timeline_build", name="t", version="1", stage_id="timeline"))
    agent.execute(tmp_path, SimpleNamespace(parameters={"aspect": "16:9"}, metadata={}))
    assert ran == [1]
