"""A change of the planner's own version must make the Planning stage stale (and with it everything after it) although no input file changed: found on 2026-10-29, when
`visual_planning.VERSION` moved to 4 and the orchestrator still reused all 13 stages. Run: python -m pytest tests/test_stage_logic_version.py -q"""
from SYSTEM.policies import llm_review
from VIDEO_ENGINE.stages import visual_planning


def test_a_new_planner_version_changes_the_planning_stage_fingerprint_and_no_other_stage(tmp_path, monkeypatch):
    pdir = tmp_path / "p"
    pdir.mkdir()
    before = {s: llm_review.compute_stage_input_fingerprint(pdir, s) for s in ("planning", "assets", "segmentation")}
    monkeypatch.setattr(visual_planning, "VERSION", visual_planning.VERSION + 1)
    after = {s: llm_review.compute_stage_input_fingerprint(pdir, s) for s in ("planning", "assets", "segmentation")}
    assert after["planning"] != before["planning"]
    assert after["assets"] == before["assets"] and after["segmentation"] == before["segmentation"]      # their own logic did not change


def test_a_change_in_the_code_that_plans_or_writes_the_motion_makes_the_stage_stale_in_the_run_and_in_the_pipeline_view(tmp_path, monkeypatch):
    """Found 2026-10-29: motion_planning.py was edited after the plan was made; the step digest (pipeline view) said stale, the orchestrator's stage fingerprint (the run) said fresh and reused the old plan."""
    from SYSTEM.memory import store
    from VIDEO_ENGINE.pipeline import legacy_pipeline_adapter as pipe
    from VIDEO_ENGINE.stages import config
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path)
    pdir = store.create("Fresh", "16:9")
    stages = tmp_path / "stages"
    stages.mkdir()
    for n in ("motion_planning.py", "motion_scenes.py", "motion_generation.py", "motion_gen_rules.py", "motion_gen_report.py", "motion_animation.py"):
        (stages / n).write_text("v1", encoding="utf-8")
    monkeypatch.setattr(pipe, "_STAGES_DIR", stages)
    monkeypatch.setattr(pipe, "_remotion_src_digest", lambda: "remotion")

    def now():
        return {"run_plan": llm_review.compute_stage_input_fingerprint(pdir, "motion_plan"), "run_gen": llm_review.compute_stage_input_fingerprint(pdir, "motion_gen"),
                "view_plan": pipe.digest(*pipe._motion_inputs(pdir, "16:9")), "run_planning": llm_review.compute_stage_input_fingerprint(pdir, "planning")}
    before = now()
    (stages / "motion_planning.py").write_text("v2", encoding="utf-8")                         # the plan's own code
    plan_changed = now()
    assert all(plan_changed[k] != before[k] for k in ("run_plan", "run_gen", "view_plan")) and plan_changed["run_planning"] == before["run_planning"]
    (stages / "motion_animation.py").write_text("v2", encoding="utf-8")                        # the scene writer: only Motion Generation depends on it
    gen_changed = now()
    assert gen_changed["run_gen"] != plan_changed["run_gen"] and gen_changed["run_plan"] == plan_changed["run_plan"] and gen_changed["view_plan"] == plan_changed["view_plan"]


def test_the_fingerprint_is_stable_while_nothing_changes(tmp_path):
    pdir = tmp_path / "p"
    pdir.mkdir()
    assert llm_review.compute_stage_input_fingerprint(pdir, "planning") == llm_review.compute_stage_input_fingerprint(pdir, "planning")
