"""Phase 3 of improvement/MASTER_PLAN.md: shot planning (A2V_SHOTS). Short scenes stay whole, long scenes with several pictures on different narration
phrases get timed shots on real pauses, one picture means a subtle move, no blank gaps, valid transitions, safe crops."""
import json
import shutil
from pathlib import Path

from PIL import Image

from backend import config, shots
from backend.assets import work_dir
from backend.models import MatchReport

FIX = Path(__file__).parent / "fixtures"


def _sample(tmp_path: Path, with_report=True) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    for f in ("transcript.json", "scene_plan.json", "prompts_map.json", "composition.json", "transcript_en.json", "cuts.json"):
        shutil.copy(FIX / "plan_sample" / f, tmp_path / f)
    if with_report:
        shutil.copy(FIX / "golden" / "match_report.json", tmp_path / "match_report.json")
    return tmp_path


def _scene(out, sid):
    return next(s for s in out["scenes"] if s["id"] == sid)


def test_real_sample_long_scene_becomes_timed_shots_on_real_pauses(tmp_path):
    pdir = _sample(tmp_path)
    out = shots.plan(pdir)
    sc = _scene(out, 4)
    assert [s["kind"] for s in sc["shots"]] == ["shot_change"] * 3
    assert not shots.validate(sc["start"], sc["end"], sc["shots"])                  # contiguous, no gap, no overlap
    assert all(s["end"] - s["start"] >= config.MIN_SHOT_SEC for s in sc["shots"])
    cuts = {c["t"] for c in json.loads((pdir / "cuts.json").read_text(encoding="utf-8"))["cuts"]}
    words = {w["start"] for s in json.loads((pdir / "transcript.json").read_text(encoding="utf-8"))["segments"] for w in s["words"]}
    for s in sc["shots"][1:]:                                                       # every change falls on a cut or a spoken word start, never on a timer
        assert any(abs(s["start"] - t) < 0.01 for t in cuts | words), s
        assert s["reason"]["rule"] == "narration_cue" and s["reason"]["source_cue"]
    assert sc["shots"][0]["transition"] is None and sc["shots"][1]["transition"] != sc["shots"][2]["transition"]    # no repeated transition
    assert [s["camera"] for s in sc["shots"]] == ["ken-burns", "hold", "ken-burns"]                                  # neighbouring shots never repeat the same move


def test_short_scenes_are_never_split(tmp_path):
    out = shots.plan(_sample(tmp_path))
    for s in out["scenes"]:
        if s["end"] - s["start"] < config.LONG_SCENE_SEC:
            assert len(s["shots"]) == 1 and s["shots"][0]["kind"] == "whole_scene" and s["shots"][0]["reason"]["rule"] == "short_scene"


def test_combined_scene_and_scene_without_assets_stay_whole(tmp_path):
    out = shots.plan(_sample(tmp_path))
    s8, s5 = _scene(out, 8), _scene(out, 5)
    assert len(s8["shots"]) == 1 and s8["shots"][0]["reason"]["rule"] == "combined_layout" and len(s8["shots"][0]["slots"]) == 4      # shown together
    assert len(s5["shots"]) == 1 and s5["shots"][0]["reason"]["rule"] == "no_asset" and s5["shots"][0]["slots"] == []                # nothing invented


def test_one_asset_in_a_long_scene_is_a_subtle_move_not_a_cut(tmp_path):
    pdir = _sample(tmp_path)
    plan = json.loads((pdir / "scene_plan.json").read_text(encoding="utf-8"))
    for s in plan["scenes"]:                                                         # make scene 6 (one picture) 12 s long
        if s["id"] == 6:
            s["end"] = s["start"] + 12
    (pdir / "scene_plan.json").write_text(json.dumps(plan), encoding="utf-8")
    sh = _scene(shots.plan(pdir), 6)["shots"]
    assert len(sh) == 1 and sh[0]["kind"] == "whole_scene" and sh[0]["reason"]["rule"] == "one_asset_fallback"


def test_unaccepted_picture_gets_no_shot_and_is_reported(tmp_path):
    pdir = _sample(tmp_path)
    rep = MatchReport.model_validate_json((pdir / "match_report.json").read_text(encoding="utf-8"))
    for m in rep.matches:
        if m.n == 6:
            m.status = "review"                                                      # needs a decision: not usable yet
    (pdir / "match_report.json").write_text(rep.model_dump_json(), encoding="utf-8")
    out = shots.plan(pdir)
    sc = _scene(out, 4)
    assert sc["shots"][0]["kind"] == "shot_change" and all("s04_1" not in s["slots"] for s in sc["shots"])
    assert any(i["rule"] == "shot_asset_missing" and "prompt 6" in i["issue"] for i in out["issues"])
    for m in rep.matches:
        if m.n in (6, 7):
            m.file, m.status = None, "missing"                                       # two of three gone: one picture left -> subtle move
    (pdir / "match_report.json").write_text(rep.model_dump_json(), encoding="utf-8")
    assert _scene(shots.plan(pdir), 4)["shots"][0]["reason"]["rule"] == "one_asset_fallback"


def test_no_match_report_plans_from_prompts(tmp_path):
    out = shots.plan(_sample(tmp_path, with_report=False))
    assert _scene(out, 4)["shots"][0]["kind"] == "shot_change"                       # preview before any image exists still shows the intended structure
    assert not [i for i in out["issues"] if i["rule"] == "shot_asset_missing"]


# ---------- validation of shot lists (pure) ----------
def _shot(i, a, b, tr=None, td=0.0):
    return {"id": f"scene_01_shot_{i:02d}", "scene": 1, "start": a, "end": b, "transition": tr, "transition_dur": td}


def test_validate_gap_overlap_short_and_transitions():
    ok = [_shot(1, 0, 4), _shot(2, 4, 8, "fade", 0.5), _shot(3, 8, 12, "wipe", 0.5)]
    assert shots.validate(0, 12, ok) == []
    rules = lambda sh: sorted(i.rule for i in shots.validate(0, 12, sh))
    assert rules([_shot(1, 0, 4), _shot(2, 5, 12)]) == ["shot_gap"]                       # blank second between shots
    assert rules([_shot(1, 0, 6), _shot(2, 5, 12)]) == ["shot_overlap"]
    assert rules([_shot(1, 1, 12)]) == ["shot_gap"]                                       # scene start not covered
    assert rules([_shot(1, 0, 11)]) == ["shot_gap"]                                       # scene end not covered
    assert "shot_too_short" in rules([_shot(1, 0, 11), _shot(2, 11, 12, "fade", 0.2)])
    assert "shot_transition" in rules([_shot(1, 0, 6), _shot(2, 6, 12, "fade", 5.0)])
    assert "shot_transition_repeat" in rules([_shot(1, 0, 4), _shot(2, 4, 8, "fade", 0.5), _shot(3, 8, 12, "fade", 0.5)])
    assert rules([]) == ["shots_missing"]


# ---------- crops ----------
def test_full_frame_shot_that_hides_most_of_the_picture_is_warned(tmp_path):
    pdir = _sample(tmp_path)
    rep = MatchReport.model_validate_json((pdir / "match_report.json").read_text(encoding="utf-8"))
    files = {m.n: m.file for m in rep.matches}
    work_dir(pdir).mkdir(parents=True, exist_ok=True)
    for n, size in ((5, (1920, 1080)), (6, (3600, 600)), (7, (1920, 1080))):        # prompt 6: a 6:1 panorama
        Image.new("RGB", size, "gray").save(work_dir(pdir) / (Path(files[n]).stem + ".png"))
    crops = [i for i in shots.plan(pdir)["issues"] if i["rule"] == "shot_crop"]
    wide = [i for i in crops if i["issue"].startswith("16:9")]
    assert len(wide) == 1 and "s04_1" in wide[0]["issue"] and wide[0]["action"]       # in 16:9 only the panorama hides most of its picture
    assert any(i["issue"].startswith("9:16") and "s04_1" in i["issue"] for i in crops)   # in 9:16 it is flagged too (16:9 pictures are flagged there as well: 32% visible)


# ---------- applying to the composition ----------
def _opacity(l, t):
    o = 1.0
    if l.get("enter"):
        e = l["enter"]
        o *= min(1.0, max(0.0, (t - e["at"]) / e["dur"])) if t >= e["at"] else 0.0
    if l.get("exit"):
        x = l["exit"]
        o *= 1.0 - min(1.0, max(0.0, (t - x["at"]) / x["dur"]))
    return o


def test_apply_shots_rewrites_layers_without_blank_frames(tmp_path):
    pdir = _sample(tmp_path)
    comp = json.loads((pdir / "composition.json").read_text(encoding="utf-8"))
    sc = next(s for s in comp["scenes"] if s["id"] == 4)
    for l in sc["layers"]:
        if l["type"] == "image":
            l["file"] = f"projects/x/{l['slot']}.png"
    assert shots.apply_shots(pdir, comp) == 1
    imgs = [l for l in sc["layers"] if l["type"] == "image"]
    assert [l["pos"] for l in imgs] == ["full"] * 3 and [l["z"] for l in imgs] == [1, 2, 3]
    assert "exit" not in imgs[-1] and "enter" not in imgs[0]                             # first shot is there from the start, last stays to the end
    assert sc["camera"]["move"] == "static" and len(sc["shots"]) == 3                     # no stacked zoom: each shot has its own simulated move
    t = sc["start"]
    while t < sc["end"]:                                                                 # at every moment some picture is fully visible: no blank gap
        assert max(_opacity(l, t) for l in imgs) > 0.99, t
        t += 0.05


def test_apply_shots_leaves_scene_alone_when_a_picture_is_missing_in_the_composition(tmp_path):
    pdir = _sample(tmp_path)
    comp = json.loads((pdir / "composition.json").read_text(encoding="utf-8"))          # image files are still null in this composition
    before = json.dumps(comp, sort_keys=True)
    assert shots.apply_shots(pdir, comp) == 0 and json.dumps(comp, sort_keys=True) == before
