"""Motion Generation (backend/motion_generation.py, motion_gen_rules.py, motion_gen_report.py): the `motion-build` step builds the composition from the checked plan, checks it with the 13
stages and writes motion_generation.json. Real planner + real composition builder (node) on a fixture project; tampered compositions go straight to `build`."""
import importlib
import json

import pytest

pytestmark = pytest.mark.usefixtures("llm_codegen_stub_module")

from backend import motion_gen_report as mgr
from backend import motion_generation as mg
from backend import motion_planning as mpl
from backend import pipeline

_p = importlib.import_module("test_motion_planning")
_m7 = importlib.import_module("test_m7")
make, client, create = _p.make, _m7.client, _m7.create


@pytest.fixture(scope="module")
def built(tmp_path_factory, llm_codegen_stub_module):
    """A motion-only fixture project planned and generated once by the real steps."""
    d, *_ = make(tmp_path_factory.mktemp("gen"))
    (d / "motion_plan.json").unlink()
    assert pipeline.execute(d, "motion-plan", pipeline.Ctx())["status"] == "ran"
    r = pipeline.execute(d, "motion-build", pipeline.Ctx())
    assert r["status"] == "ran", r
    return d


def test_the_step_writes_the_composition_and_a_report_with_the_13_stages_and_no_errors(built):
    rep = mgr.load(built, "16:9")
    assert [s["n"] for s in rep["stages"]] == list(range(1, 14))
    assert [s["name"] for s in rep["stages"]] == ["Plan Reader", "Element Resolver", "Preset Registry", "Effect Reuse", "Animation Builder", "Engine Adapter", "Composition Builder", "Audio Sync",
                                                  "Layout Validation", "Code Validation", "Motion Testing", "Error Repair", "Remotion Adapter"]
    assert rep["validation"]["errors"] == [] and rep["stale"] is False and mgr.blockers(built, "16:9") is None
    assert rep["output"]["persisted"] is True and rep["output"]["pictures"] == 0 and rep["project"]["mode"] == "motion_only"
    assert rep["tests"]["determinism"]["identical"] is True and rep["tests"]["renderer"]["zod"] is True and rep["tests"]["renderer"]["wallclock_files"] == []
    assert rep["input"]["file"] == "motion_planning.json" and rep["input"]["plan_fingerprint"] == mpl.load(built, "16:9")["source_fingerprint"]


def test_an_unchanged_step_is_fresh_and_a_composition_changed_behind_the_report_makes_it_stale(built):
    assert pipeline.execute(built, "motion-build", pipeline.Ctx())["status"] == "fresh"
    f = built / "composition.json"
    keep = f.read_text(encoding="utf-8")
    try:
        f.write_text(keep.replace('"duration":', '"duration": ', 1), encoding="utf-8")
        assert mgr.load(built, "16:9")["stale"] is True and "out of date" in mgr.blockers(built, "16:9")
    finally:
        f.write_text(keep, encoding="utf-8")
    assert mgr.load(built, "16:9")["stale"] is False


def test_the_same_plan_gives_the_same_composition_and_each_aspect_has_its_own_files(built):
    pipeline._run_build_script(built, "16:9", False)
    a = (built / "composition.json").read_bytes()
    pipeline._run_build_script(built, "16:9", False)
    assert (built / "composition.json").read_bytes() == a
    assert mg.names("9:16") == ("composition_9x16.json", "motion_generation_9x16.json", "motion_plan_9x16.json") and mg.names("16:9")[1] == "motion_generation.json"
    assert pipeline.execute(built, "motion-build", pipeline.Ctx())["status"] in ("ran", "fresh")        # leave the fixture as the step writes it


def test_a_project_without_a_report_is_not_blocked_and_the_api_refuses_a_missing_one(client, tmp_path):
    assert mgr.load(tmp_path, "16:9") is None and mgr.blockers(tmp_path, "16:9") is None
    pid = create(client).json()["id"]
    r = client.get(f"/projects/{pid}/motion-generation")
    assert r.status_code == 409 and r.json()["error"]["code"] == "motion_generation_missing"
    r = client.post(f"/projects/{pid}/motion-generation/run")
    assert r.status_code == 409 and r.json()["error"]["code"] == "motion_plan_missing"
