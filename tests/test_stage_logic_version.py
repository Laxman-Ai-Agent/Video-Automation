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


def test_the_fingerprint_is_stable_while_nothing_changes(tmp_path):
    pdir = tmp_path / "p"
    pdir.mkdir()
    assert llm_review.compute_stage_input_fingerprint(pdir, "planning") == llm_review.compute_stage_input_fingerprint(pdir, "planning")
