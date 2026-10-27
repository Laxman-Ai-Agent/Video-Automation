"""The rule switches: the catalog lists every rule of the stages once, a rule switched OFF is never evaluated by its stage (it cannot block or warn), nothing else changes."""
import importlib

import pytest

from SYSTEM.policies import rule_catalog, rule_switches
from VIDEO_ENGINE.stages import asset_collection as ac
from VIDEO_ENGINE.stages import final_qc, motion_planning as mp, motion_validation as mv, timeline_build as tb

_m7 = importlib.import_module("test_m7")
client = _m7.client


@pytest.fixture(autouse=True)
def switches(tmp_path, monkeypatch):
    monkeypatch.setattr(rule_switches, "FILE", tmp_path / "rule_switches.json")


def test_the_catalog_lists_every_rule_of_every_stage_once():
    cat = rule_catalog.catalog()
    ids = [(r["stage"], r["rule"]) for r in cat]
    assert len(ids) == len(set(ids)) and len(ids) > 300
    stages = {r["stage"] for r in cat}
    assert stages == {"analyzer", "segmentation", "planning", "motion_plan", "motion_gen", "motion_validation", "timeline", "render", "qc", "assets"}        # analyzer / segmentation only have their LLM review switch
    assert ("planning", "hierarchy") in ids and ("motion_validation", "animation.no_untrusted_execution") in ids and ("assets", "asset_provenance") in ids and ("qc", "QC_ASSETS_PROVENANCE") in ids
    assert all(r["says"] for r in cat)
    assert {r["stage"] for r in cat if r["rule"] == "llm_review"} == {"analyzer", "segmentation", "planning", "motion_gen"}      # the four reviews that can be switched off; Approval and Final QC cannot


def test_a_rule_that_is_off_is_never_evaluated_by_its_stage(tmp_path):
    def finding(run):
        run.rule("text_count", 9, "scene_01", True, "warning", "layout_density", "too many texts")
        return [i["code"] for i in run.items]
    assert finding(mp.Run()) == ["layout_density"]
    rule_switches.set_many([("motion_plan", "text_count")], False, "not needed for my videos")
    assert finding(mp.Run()) == [] and finding(mp.Run("motion_gen")) == ["layout_density"]       # the switch is per stage: motion_gen has its own
    v = mv.V()
    stage = mv.STAGES[0][0]
    assert v.check(stage, "layout.text_graphic_collision", False, "warning", "x") is False and len(v.findings) == 1
    rule_switches.set_many([("motion_validation", "layout.text_graphic_collision")], False)
    v = mv.V()
    assert v.check(stage, "layout.text_graphic_collision", False, "warning", "x") is True and not v.findings and v.counts[stage]["passed"] == 1
    r = tb.Rec()
    rule_switches.set_many([("timeline", "some_rule")], False)
    assert r.check(tb.STAGES[0][0], "some_rule", False, "error", "x") is True and not r.findings
    q = final_qc.Q()
    assert q.add("QC_X", "failed", "blocker", "bad")["status"] == "failed"
    rule_switches.set_many([("qc", "QC_X")], False)
    off = q.add("QC_X", "failed", "blocker", "bad")
    assert off["status"] == "not_applicable" and off["severity"] == "info" and "switched off by the user" in off["message"]       # said, never counted as a pass
    asset = {"asset_id": "a", "file": "x.png", "authenticity": "real", "license": {"name": "L"}, "rights_class": "A"}
    assert "asset_provenance" in [f["code"] for f in ac.check_assets(tmp_path, {"assets": [asset]}) if f["code"] != "asset_file"]
    rule_switches.set_many([("assets", "asset_provenance")], False)
    assert "asset_provenance" not in [f["code"] for f in ac.check_assets(tmp_path, {"assets": [asset]})]
    assert rule_switches.off_in("qc") == ["QC_X"] and rule_switches.off_in("planning") == []


def test_the_api_lists_the_rules_and_switches_one_a_stage_or_all(client):
    got = client.get("/rules").json()
    assert got["total"] == len(rule_catalog.catalog()) and got["off"] == 0 and {s["stage"] for s in got["stages"]} >= {"planning", "qc"}
    one = client.post("/rules/switch", json={"on": False, "stage": "planning", "rule": "hierarchy", "note": "fine for my videos"}).json()
    plan = next(s for s in one["stages"] if s["stage"] == "planning")
    h = next(r for r in plan["rules"] if r["rule"] == "hierarchy")
    assert one["off"] == 1 and plan["off"] == 1 and h["on"] is False and h["off_note"] == "fine for my videos" and rule_switches.is_off("planning", "hierarchy")
    whole = client.post("/rules/switch", json={"on": False, "stage": "assets"}).json()
    assert whole["off"] == 1 + 5
    assert client.post("/rules/switch", json={"on": True}).json()["off"] == 0                      # everything back on
    assert client.post("/rules/switch", json={"on": False, "stage": "planning", "rule": "nope"}).status_code == 404
    assert client.post("/rules/switch", json={"on": False, "rule": "hierarchy"}).status_code == 422
