"""The pipeline is autonomous: a stage starts only when the one before it completed with nothing unresolved, the LLM reviews that matter must PASS (nothing is waved through), and no person
approves or accepts anything. Run: python -m pytest tests/test_autonomous_pipeline.py -q"""
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from SYSTEM.policies import llm_review, llm_reviewer, rule_switches
from VIDEO_ENGINE.pipeline import orchestrator, stage_gate

_m7 = importlib.import_module("test_m7")
client, create = _m7.client, _m7.create


def _review(pdir: Path, stage: str, status: str, findings=None, score=0.9) -> None:
    """Store a review for the stage's CURRENT inputs and outputs."""
    rev = {"schema": llm_review.SCHEMA, "version": llm_review.VERSION, "stage": stage, "aspect": "16:9", "status": status, "score": score, "summary": "s", "findings": findings or [],
           "input_fingerprint": llm_review.compute_stage_input_fingerprint(pdir, stage, "16:9"), "output_fingerprint": llm_review.compute_stage_output_fingerprint(pdir, stage, "16:9")}
    llm_review.review_path(pdir, stage, "16:9").write_text(json.dumps(rev), encoding="utf-8")


@pytest.fixture
def pdir(tmp_path):
    p = tmp_path / "proj_auto"
    p.mkdir()
    return p


def test_only_a_passed_review_approves_whatever_the_mode(pdir):
    _review(pdir, "segmentation", "passed")
    assert llm_review.is_stage_review_passed(pdir, "segmentation", "16:9")[0] is True
    _review(pdir, "segmentation", "needs_review")                                      # warnings only: it still wants something looked at, so it is not a pass
    assert llm_review.is_stage_review_passed(pdir, "segmentation", "16:9")[:2] == (False, "llm_review_needs_review")
    _review(pdir, "segmentation", "passed", findings=[{"severity": "error", "message": "x"}])
    assert llm_review.is_stage_review_passed(pdir, "segmentation", "16:9")[1] == "llm_review_has_blockers"
    assert "auto_pilot" not in llm_review.is_stage_review_passed.__code__.co_varnames and "auto_pilot" not in llm_reviewer.ask_reviewer.__code__.co_varnames


def test_the_stages_with_an_llm_review_are_exactly_the_chosen_ones_and_two_cannot_be_switched_off(monkeypatch):
    assert llm_review.LLM_STAGES == ("analyzer", "segmentation", "planning", "motion_gen", "approval", "qc")
    for stage in ("audio", "assets", "motion_plan", "motion_validation", "timeline", "render", "final"):
        assert llm_review.review_required(stage) is False                              # decided by their own deterministic checks
    monkeypatch.setattr(rule_switches, "is_off", lambda stage, rule: rule == "llm_review")
    assert [s for s in llm_review.LLM_STAGES if llm_review.review_required(s)] == ["approval", "qc"]      # Approval and Final QC ARE an LLM decision: nobody else could decide them


def test_a_stage_whose_llm_review_did_not_pass_keeps_the_next_stage_from_starting(pdir, monkeypatch):
    monkeypatch.setattr(orchestrator.pipeline_state, "load_pipeline_state", lambda _p: SimpleNamespace(stages={"motion_gen": SimpleNamespace(status="completed", reusable=False)}))
    monkeypatch.setattr(llm_review, "is_stage_review_passed", lambda *a, **k: (False, "llm_review_needs_review", {"summary": "scene 4 is empty"}))
    blocked = orchestrator.evaluate_stage_eligibility(pdir, "motion_validation", "16:9")
    assert blocked["eligible"] is False and any("LLM review" in b and "scene 4 is empty" in b for b in blocked["blockers"])
    monkeypatch.setattr(llm_review, "is_stage_review_passed", lambda *a, **k: (True, "passed", {}))
    assert orchestrator.evaluate_stage_eligibility(pdir, "motion_validation", "16:9")["eligible"] is True


def test_earlier_finished_stages_are_reviewed_again_only_when_their_review_is_not_current(pdir, monkeypatch):
    done = {s: SimpleNamespace(status="completed", reusable=False) for s in ("analyzer", "segmentation", "planning", "assets", "motion_plan", "motion_gen", "approval", "qc")}
    monkeypatch.setattr(orchestrator.pipeline_state, "load_pipeline_state", lambda _p: SimpleNamespace(stages=done))
    current = {"segmentation", "planning"}
    monkeypatch.setattr(llm_review, "review_is_current", lambda p, stage, aspect="16:9": stage in current)
    asked = []
    monkeypatch.setattr(llm_review, "run_stage_llm_review", lambda p, stage, aspect="16:9", **k: asked.append(stage))
    o = orchestrator.PipelineOrchestrator.__new__(orchestrator.PipelineOrchestrator)
    o.pdir, o.aspect, o.project_id = pdir, "16:9", "proj_auto"
    o._ensure_reviews("render")
    assert asked == ["analyzer", "motion_gen"]                                         # not the current ones, not Approval / Final QC (they decide themselves), not stages without an LLM review


def test_a_stage_without_an_llm_review_is_not_reviewed_after_it_ran(pdir, monkeypatch):
    asked = []
    monkeypatch.setattr(llm_review, "run_stage_llm_review", lambda p, stage, aspect="16:9", **k: asked.append(stage))
    o = orchestrator.PipelineOrchestrator.__new__(orchestrator.PipelineOrchestrator)
    o.pdir, o.aspect = pdir, "16:9"
    for stage in ("audio", "assets", "motion_plan", "timeline", "render"):
        o._review(stage)
    o._review("motion_gen")
    assert asked == ["motion_gen"]


def test_no_route_lets_a_person_approve_or_accept_anything():
    from UI.backend.main import app
    paths = set(app.openapi()["paths"])
    for gone in ("/projects/{pid}/stages/{stage_id}/accept-warnings", "/projects/{pid}/approve", "/projects/{pid}/timeline-approval/decision", "/projects/{pid}/timeline-approval/notes",
                 "/projects/{pid}/motion-timeline-validation/preview/review", "/projects/{pid}/motion-timeline-validation/findings/{finding_id}/exception"):
        assert gone not in paths, gone
    assert not hasattr(stage_gate, "accept_warnings")


def test_the_run_route_uses_the_projects_own_aspect_and_has_no_mode(client, monkeypatch):
    pid = create(client).json()["id"]
    seen = {}

    class FakeOrch:
        def __init__(self, project_id, aspect="16:9"):
            seen["aspect"] = aspect

        def start_run(self, **kw):
            seen["kw"] = kw
            return SimpleNamespace(to_dict=lambda: {"run_id": "r1"})

    monkeypatch.setattr(orchestrator, "PipelineOrchestrator", FakeOrch)
    r = client.post(f"/projects/{pid}/orchestrator/run", json={"from_stage": "motion_gen"})
    assert r.status_code == 202 and seen["aspect"] in ("16:9", "9:16") and "auto_pilot_mode" not in seen["kw"] and seen["kw"]["from_stage"] == "motion_gen"


def test_the_view_says_llm_verified_only_for_a_passed_review_and_null_where_there_is_none(client, monkeypatch):
    pid = create(client).json()["id"]
    monkeypatch.setattr(llm_review, "is_stage_review_passed", lambda *a, **k: (False, "llm_review_needs_review", {"status": "needs_review", "score": 0.9}))      # a high score is not a pass
    stages = {s["id"]: s for s in client.get(f"/projects/{pid}/pipeline").json()["stages"]}
    assert stages["segmentation"]["llm_verified"] is False and stages["motion_gen"]["llm_verified"] is False
    assert stages["assets"]["llm_verified"] is None and stages["render"]["llm_verified"] is None


def test_a_retry_waits_out_the_llm_circuit_breakers_cooldown():
    """Three slow answers opened the breaker for 20 s; the stage retried after about a second, three times inside the cooldown, and stopped."""
    msg = "the planner could not be asked: LLM Gateway call failed: Circuit for 'claude_cli:claude-sonnet-5-5' is OPEN (3 consecutive failures). Cooldown: 18.5s remaining."
    assert orchestrator._circuit_wait(msg) == 19.5
    assert orchestrator._circuit_wait("The Claude CLI did not answer within 60 s") == 0.0 and orchestrator._circuit_wait(None) == 0.0


def test_the_visual_planning_agent_gives_the_gateway_the_planners_timeout(tmp_path, monkeypatch):
    """The agent's ask() dropped the planner's 900 s and the gateway used its default of 60 s: a planner answer takes minutes, so Visual Planning failed after three 'did not answer within 60 s'."""
    from SYSTEM.agents.video_generation_agents.visual_planning.agent import VisualPlanningAgent
    from SYSTEM.core import llm_gateway
    seen = {}

    def fake(req):
        seen["timeout"] = req.timeout
        return SimpleNamespace(status="passed", raw_output="{}", error_message=None)
    monkeypatch.setattr(llm_gateway, "execute_llm_gateway_call", fake)
    monkeypatch.setattr(VisualPlanningAgent, "agent_id", "visual_planning")                           # a property of the agent: no instance setup is needed for this
    agent = VisualPlanningAgent.__new__(VisualPlanningAgent)
    ask = agent._gateway_ask(tmp_path, SimpleNamespace(correlation_id="c"))
    ask("p", system="s", timeout=900)
    assert seen["timeout"] == 900
    ask("p")
    assert seen["timeout"] == 900


def test_the_gateway_keeps_the_callers_timeout():
    """execute_llm_gateway_call turned a GatewayRequest into the gateway's own request and dropped the timeout: every such call was cut off after 60 s, whatever the caller asked for."""
    from SYSTEM.core import llm_gateway
    seen = {}
    fake_gw = SimpleNamespace(execute=lambda r: seen.setdefault("req", r) and SimpleNamespace(status="passed", raw_text="x", provider="p", model="m", model_profile="fast", purpose="generation", stage_id="planning",
                                                                                               error=None, structured_data=None, token_usage={}))
    import pytest as _pt
    with _pt.MonkeyPatch.context() as m:
        m.setattr(llm_gateway, "get_gateway", lambda: fake_gw)
        llm_gateway.execute_llm_gateway_call(llm_gateway.GatewayRequest(prompt="p", timeout=900))
        assert seen["req"].timeout == 900
        seen.clear()
        llm_gateway.execute_llm_gateway_call(llm_gateway.GatewayRequest(prompt="p"))
        assert seen["req"].timeout == 0                                                   # 0 = the timeout of the model profile (PROFILE_TIMEOUT), not a fixed 60 s


def test_a_later_successful_visual_planning_replaces_an_old_failure_on_the_page(tmp_path):
    """The autonomous run planned successfully at 12:00 but the page kept the 'failed' record of the 11:11 attempt (network blip): only the background job wrote the record."""
    from VIDEO_ENGINE.stages import promptgen, visual_planning
    visual_planning.record_outcome(tmp_path, "Visual Planning: can't reach the API server")
    g = promptgen.state(tmp_path)
    assert g["state"] == "failed" and "reach the API" in g["error"]
    visual_planning.record_outcome(tmp_path)
    g = promptgen.state(tmp_path)
    assert g["state"] == "done" and g["error"] is None and g["kind"] == "plan"
