"""GET /projects/{pid}/timeline-build/stills: the preview stills the Timeline page draws in its tiles and its viewport. Run: python -m pytest tests/test_timeline_stills_api.py -q"""
import importlib

from backend import motion_gen_report, motion_validation_preview as pv

_m7 = importlib.import_module("test_m7")
client, create = _m7.client, _m7.create

SAMPLES = [{"scene_id": "scene_01", "kind": "entry", "frame": 41, "time_s": 1.367, "file": "scene_01_entry_00041.png"},
           {"scene_id": "scene_01", "kind": "mid", "frame": 170, "time_s": 5.667, "file": "scene_01_mid_00170.png"}]


def test_stills_are_listed_only_while_they_belong_to_the_current_composition(client, monkeypatch):
    pid = create(client).json()["id"]
    assert client.get(f"/projects/{pid}/timeline-build/stills").json() == {"current": False, "exists": False, "samples": []}      # nothing made yet: nothing invented
    monkeypatch.setattr(pv, "load", lambda pdir, aspect: {"samples": SAMPLES})
    monkeypatch.setattr(motion_gen_report, "load", lambda pdir, aspect: {"output": {"composition_sha": "abc"}})
    monkeypatch.setattr(pv, "is_current", lambda man, sha: False)
    got = client.get(f"/projects/{pid}/timeline-build/stills").json()
    assert got == {"current": False, "exists": True, "samples": []}                                                                    # older composition: no frames that do not belong to this timeline
    monkeypatch.setattr(pv, "is_current", lambda man, sha: sha == "abc")
    got = client.get(f"/projects/{pid}/timeline-build/stills").json()
    assert got["current"] and [s["frame"] for s in got["samples"]] == [41, 170]
    assert got["samples"][0]["url"] == f"/projects/{pid}/motion-timeline-validation/preview/scene_01_entry_00041.png"
