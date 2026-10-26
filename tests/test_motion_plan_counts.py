"""Motion Planning keeps ONE set of counts: a step's "x of y checks passed" is the sum of its own rules, and what the LLM check of the step is shown are those same numbers."""
from UI.backend import step_llm_check
from VIDEO_ENGINE.stages import motion_planning as mp


def test_a_steps_count_and_its_rules_counts_are_the_same_numbers():
    run = mp.Run()
    run.count("element_drawn", 2, True)
    run.count("element_drawn", 2, False)                                       # a recorded fallback: not drawn one by one
    run.rule("registry_id", 3, "scene_01", False, "error", "unknown_registry_id", "m")
    run.rule("transition_known", 3, "scene_01", True, "error", "unknown_registry_id", "m")
    assert run.by_stage[2] == [1, 2] == run.counts["element_drawn"] == run.stage_rules[2]["element_drawn"]
    assert run.by_stage[3] == [1, 2] and sum(v[0] for v in run.stage_rules[3].values()) == 1 and sum(v[1] for v in run.stage_rules[3].values()) == 2
    assert [i["code"] for i in run.items] == ["unknown_registry_id"] and run.counts["registry_id"] == [1, 1]


def test_the_stale_composition_is_a_told_fact_not_a_failed_check():
    run = mp.Run()
    run.note(13, "info", "composition_stale", None, "the composition on disk was built from an earlier plan")
    assert "composition_current" not in run.counts and 13 not in run.by_stage and run.of("info")[0]["code"] == "composition_stale"


def test_the_step_evidence_is_the_steps_own_rules_and_older_reports_fall_back_to_the_fixed_list():
    report = {"validation": {"checks": {"by_rule": {"element_drawn": {"passed": 31, "total": 35}, "registry_id": {"passed": 41, "total": 41}},
                                         "by_stage": {"2": {"element_drawn": {"passed": 31, "total": 35}}, "9": {"text_readable": {"passed": 7, "total": 7}, "extra_rule": {"passed": 2, "total": 2}}}}},
              "output": {"composition": "differs from the plan: Motion Generation has to build it again"}}
    assert step_llm_check._step_checks(report, 2, step_llm_check.MOTION_PLAN_STAGE_RULES) == {"element_drawn": {"passed": 31, "total": 35}}
    assert set(step_llm_check._step_checks(report, 9, step_llm_check.MOTION_PLAN_STAGE_RULES)) == {"text_readable", "extra_rule"}        # a rule the fixed list did not know is still counted
    old = {"validation": {"checks": {"by_rule": report["validation"]["checks"]["by_rule"]}}}
    assert step_llm_check._step_checks(old, 3, step_llm_check.MOTION_PLAN_STAGE_RULES) == {"registry_id": {"passed": 41, "total": 41}}
    ev = step_llm_check.build_step_evidence("motion_plan", {"n": 13, "name": "Remotion Output Adapter", "detail": "x"}, report)
    assert ev["composition"].startswith("differs")
