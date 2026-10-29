"""Phase 5, QC that sees: the Final QC LLM review is shown contact sheets of the frames Final QC sampled plus per-scene measurements, only when the active LLM can look,
and a verdict made without the pictures says so. Run: python -m pytest tests/test_qc_sight.py -q"""
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from SYSTEM.core import llm_client
from SYSTEM.policies import llm_review
from VIDEO_ENGINE.stages import contact_grid, qc_sight

SHA = "ab" * 32


def _frame(path: Path, drawn: bool, size=(480, 270)):
    img = Image.new("RGB", size, (20, 30, 50))
    if drawn:
        d = ImageDraw.Draw(img)
        d.rectangle((60, 40, 420, 230), fill=(240, 240, 240))
        d.rectangle((100, 80, 380, 190), fill=(30, 60, 200))
    img.save(path, "JPEG", quality=95)


def _project(tmp_path, monkeypatch, size=(480, 270)):
    """Two scenes of 5 s at 30 fps, a transition between them, every sampled frame a file; scene 2's frames are empty."""
    frames = tmp_path / "final_qc_frames"
    frames.mkdir()
    clips = [{"scene_id": "scene_001", "start_frame": 0, "end_frame": 150}, {"scene_id": "scene_002", "start_frame": 150, "end_frame": 300}]
    samples = []

    def add(frame, scene, kind, drawn):
        name = f"{scene}_{kind}_{frame}.jpg"
        _frame(frames / name, drawn, size)
        samples.append({"frame": frame, "scene_id": scene, "kind": kind, "time_s": round((frame + 0.5) / 30, 3), "file": name, "decode_ok": True})
    for c, drawn in zip(clips, (True, False)):
        a = c["start_frame"]
        for kind, off in (("entry", 20), ("mid", 70), ("pre_exit", 130)):
            add(a + off, c["scene_id"], kind, drawn)
    add(148, "scene_001", "before_cut", True)
    add(151, None, "after_cut", False)
    add(155, "scene_002", "transition_mid", False)
    report = {"candidate": {"sha256": SHA}, "evidence": {"frame_quality": {"data": {"samples": samples}}}}
    cand = {"path": tmp_path / "out.mp4", "sha256": SHA, "report": {"observed": {"duration_seconds": 10}}}
    transitions = [{"from_scene": "scene_001", "to_scene": "scene_002", "start_frame": 150, "end_frame": 160}]
    monkeypatch.setattr(qc_sight.rv, "candidate", lambda pdir, aspect: cand)
    monkeypatch.setattr(qc_sight.fq, "_rw_read", lambda pdir, key, aspect: report)
    monkeypatch.setattr(qc_sight.fq, "scenes_of", lambda pdir, aspect: (clips, transitions, 30))
    tiles = [np.full((18, 32), 100.0 * (i % 2)) for i in range(5)] + [np.full((18, 32), 50.0) for _ in range(5)]    # scene 1's picture flips every second, scene 2's never changes
    monkeypatch.setattr(qc_sight, "_seconds", lambda pdir, c: (tiles, 1))
    return tmp_path


def test_a_grid_stamps_every_cell_with_its_label_and_says_what_is_missing():
    red = Image.new("RGB", (640, 360), (220, 20, 20))
    sheet = contact_grid.grid([red, None], ["s1 mid 2.5s", "s2 mid"], (320, 180), 3, empty="no frame")
    assert sheet.size == (960, 180)
    px = lambda x, y: sheet.getpixel((x, y))
    assert px(160, 120)[0] > 180 and px(160, 120)[1] < 60                                  # the picture is in cell 0
    assert px(150, 20)[0] > 200 and px(150, 20)[2] < 80                                     # a long label has a wider yellow tag than a single digit
    assert px(320 + 300, 150) == contact_grid.BACKGROUND                                    # cell 1 has no picture: only the background and its words


def test_the_sheets_have_one_row_per_scene_and_per_cut_and_the_metrics_name_the_flat_scene(tmp_path, monkeypatch):
    pdir = _project(tmp_path, monkeypatch)
    out = qc_sight.build(pdir, "16:9")
    assert [p.name.split("_", 1)[1] for p in out["sheets"]] == ["scenes_1.jpg", "cuts_1.jpg"]
    assert Image.open(out["sheets"][0]).size == (3 * 320, 2 * 180)                          # 2 scenes x (entry, mid, exit)
    assert Image.open(out["sheets"][1]).size == (3 * 320, 1 * 180)                          # 1 cut x (before, mid, after)
    one, two = out["metrics"]["scenes"]
    assert one["frame_usage_pct"] > 15 and two["frame_usage_pct"] == 0.0                    # scene 2 draws nothing
    assert one["big_changes_per_10s"] == 10.0 and one["motion_energy"] == 100.0             # a new picture every second
    assert two["big_changes_per_10s"] == 0.0 and two["motion_energy"] == 0.0


def test_a_tall_video_is_split_in_sheets_that_stay_small_enough_to_keep_the_phone_size(tmp_path, monkeypatch):
    pdir = _project(tmp_path, monkeypatch, size=(270, 480))                                 # 9:16 frames
    cells = [(f"s{i} entry", 0) for i in range(15)]                                         # 5 scenes' worth of rows
    files = {0: tmp_path / "final_qc_frames" / "scene_001_entry_20.jpg"}
    (tmp_path / "x").mkdir()
    made = qc_sight._sheets(tmp_path / "x", files, SHA, "scenes", cells)
    assert len(made) == 2                                                                   # 320 px high cells: 4 rows (12 cells) per sheet at most
    assert max(Image.open(tmp_path / "x" / n).height for n in made) <= qc_sight.SHEET_MAX_PX


def test_the_same_video_and_frames_are_not_drawn_again(tmp_path, monkeypatch):
    pdir = _project(tmp_path, monkeypatch)
    first = qc_sight.build(pdir, "16:9")
    monkeypatch.setattr(qc_sight, "_sheets", lambda *a, **k: pytest.fail("the sheets exist: nothing may be drawn again"))
    again = qc_sight.build(pdir, "16:9")
    assert again["sheets"] == first["sheets"] and again["metrics"] == first["metrics"]


def test_no_report_or_another_video_gives_nothing_to_look_at(tmp_path, monkeypatch):
    pdir = _project(tmp_path, monkeypatch)
    monkeypatch.setattr(qc_sight.fq, "_rw_read", lambda *a: {"candidate": {"sha256": "other"}, "evidence": {"frame_quality": {"data": {"samples": [{"frame": 1, "file": "x.jpg"}]}}}})
    assert qc_sight.build(pdir, "16:9") == {"sheets": [], "metrics": None}


# ---------- the review ----------
def _sheet_files(tmp_path):
    names = []
    for n in ("a_scenes_1.jpg", "a_cuts_1.jpg"):
        Image.new("RGB", (8, 8)).save(tmp_path / n)
        names.append(tmp_path / n)
    return names


def _review(tmp_path, monkeypatch, stage, can_look, sheets):
    seen = {}

    def fake_ask(**kw):
        seen.update(kw)
        return {"status": "passed", "score": 0.9, "summary": "ok", "findings": [], "provider": "p", "model": "m", "latency_ms": 1, "error": None}
    monkeypatch.setattr(llm_review, "ask_reviewer", fake_ask)
    monkeypatch.setattr(llm_client, "can_look", lambda provider=None: can_look)
    monkeypatch.setattr(qc_sight, "build", lambda pdir, aspect: {"sheets": sheets, "metrics": {"scenes": [{"scene_id": "scene_001", "frame_usage_pct": 3.0}]} if sheets else None})
    result = llm_review.run_stage_llm_review(tmp_path, stage, force=True)
    return seen, result


def test_the_qc_review_is_shown_the_sheets_and_the_metrics_and_given_time_to_look(tmp_path, monkeypatch):
    sheets = _sheet_files(tmp_path)
    seen, result = _review(tmp_path, monkeypatch, "qc", True, sheets)
    assert seen["images"] == [str(p) for p in sheets] and seen["timeout"] == llm_client.VISION_TIMEOUT_S
    assert "visual_metrics" in seen["user_prompt"] and "LOOK at the attached pictures" in seen["user_prompt"] and "regenerate scene N" in seen["user_prompt"]
    assert "you ARE shown still frames" in seen["system_prompt"]
    assert not any(f["category"] == "pixels_not_seen" for f in result["findings"])


def test_an_llm_that_cannot_look_reviews_without_the_pictures_and_the_verdict_says_so(tmp_path, monkeypatch):
    seen, result = _review(tmp_path, monkeypatch, "qc", False, _sheet_files(tmp_path))
    assert seen["images"] == [] and "LOOK at the attached pictures" not in seen["user_prompt"] and "ARE shown" not in seen["system_prompt"]
    warn = [f for f in result["findings"] if f["category"] == "pixels_not_seen"]
    assert len(warn) == 1 and warn[0]["severity"] == "warning" and "cannot look at pictures" in warn[0]["message"]


def test_no_other_stage_gets_pictures(tmp_path, monkeypatch):
    seen, result = _review(tmp_path, monkeypatch, "approval", True, _sheet_files(tmp_path))
    assert seen["images"] == [] and not result["findings"] and "pictures" not in seen["user_prompt"]


def test_what_the_qc_reviewer_is_shown_is_part_of_its_stage_fingerprint(tmp_path, monkeypatch):
    before = {s: llm_review.compute_stage_input_fingerprint(tmp_path, s) for s in ("qc", "final", "render")}
    monkeypatch.setattr(qc_sight, "VERSION", qc_sight.VERSION + 1)
    after = {s: llm_review.compute_stage_input_fingerprint(tmp_path, s) for s in ("qc", "final", "render")}
    assert after["qc"] != before["qc"] and after["final"] == before["final"] and after["render"] == before["render"]


def test_only_claude_code_can_look_at_pictures():
    assert llm_client.can_look("claude_cli") and not llm_client.can_look("gemini") and not llm_client.can_look("antigravity")
    with pytest.raises(llm_client.LlmError):
        llm_client.generate_text("x", provider="gemini", images=["a.jpg"])
