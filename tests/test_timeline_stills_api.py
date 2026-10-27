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


def test_thumbnail_sheet_is_made_once_per_video(tmp_path, monkeypatch):
    import shutil
    import subprocess

    import pytest

    from VIDEO_ENGINE.stages import timeline_media as tm
    exe = shutil.which("ffmpeg")
    if not exe:
        pytest.skip("ffmpeg is not installed")
    video = tmp_path / "v.mp4"
    subprocess.run([exe, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=10:duration=3", "-pix_fmt", "yuv420p", str(video)], check=True)
    meta = tm.thumbnails(tmp_path, video, "k1", 3.0)
    assert meta["count"] == 3 and meta["interval_s"] == 1 and meta["cols"] == 10 and meta["rows"] == 1 and (meta["tile_w"], meta["tile_h"]) == (320, 180) and (tmp_path / tm.THUMBS).is_file()
    with monkeypatch.context() as m:
        m.setattr(subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("ffmpeg ran again for the same video")))
        assert tm.thumbnails(tmp_path, video, "k1", 3.0) == meta                          # same video: the cached sheet
    assert tm.thumbnails(tmp_path, video, "k2", 3.0)["key"] == "k2"                       # a new render: a new sheet


def test_thumbnails_route_only_for_the_render_of_the_current_approved_timeline(client, monkeypatch):
    from VIDEO_ENGINE.stages import timeline_media as tm
    from backend import render_video as rv
    pid = create(client).json()["id"]
    assert client.get(f"/projects/{pid}/timeline-build/thumbnails").json()["available"] is False      # no render of the approved timeline: nothing invented
    monkeypatch.setattr(rv, "current_candidate", lambda pdir, aspect: {"path": "v.mp4", "sha256": "k3abcdefabcdef", "report": {"observed": {"duration_seconds": 3.0}}})
    monkeypatch.setattr(tm, "thumbnails", lambda pdir, video, key, dur: {"key": key, "interval_s": 1, "cols": 10, "rows": 1, "count": 3, "tile_w": 320, "tile_h": 180})
    got = client.get(f"/projects/{pid}/timeline-build/thumbnails").json()
    assert got["available"] and got["count"] == 3 and got["url"] == f"/projects/{pid}/timeline-build/thumbnails/sheet.jpg?v=k3abcdefabcd"
    assert client.get(f"/projects/{pid}/timeline-build/thumbnails/sheet.jpg").status_code == 404      # no sheet file made in this test
