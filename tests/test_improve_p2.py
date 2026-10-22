"""Phase 2 of improvement/MASTER_PLAN.md: cues, confidence bands, cue agreement, locks, duplicates, match_detail.json (A2V_MATCH_DETAIL).
CLIP is replaced by a tiny deterministic scorer (word weights per image) so the decision logic is tested without the model."""
import json
import shutil
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from backend import config, cues, matcher, match_detail, plan_preview
from backend.assets import save_uploads
from backend.models import MatchItem, MatchReport

FIX = Path(__file__).parent / "fixtures"


# ---------- cues (no model) ----------
def _sample(tmp_path: Path) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    for f in ("transcript.json", "scene_plan.json", "prompts_map.json", "composition.json", "transcript_en.json"):
        shutil.copy(FIX / "plan_sample" / f, tmp_path / f)
    return tmp_path


def test_overlap_uses_word_stems():
    assert cues.overlap("Rows of server racks representing databases", "add custom logic, databases,") == 1
    assert cues.overlap("a glowing agent avatar", "build AI agents") == 1
    assert cues.overlap("Close-up of a dark monitor, soft light", "the weather is nice") == 0       # style words never count


def test_cues_real_sample_links_and_arrangements(tmp_path):
    out = cues.build(_sample(tmp_path))
    sc = out["scenes"]
    assert sc["1"]["arrangement"] == "single" and out["links"]["1"]
    assert sc["4"]["arrangement"] == "timed"                                            # three prompts, three different narration phrases
    assert len({out["links"][n] for n in ("5", "6", "7")}) == 3
    starts = [c["start"] for c in out["cues"] if c["scene"] == 4]
    assert starts == sorted(starts) and all(b - a >= config.MIN_SHOT_SEC for a, b in zip(starts, starts[1:]))
    assert sc["8"]["arrangement"] == "combined"                                         # two prompts share one phrase
    assert all(c["timing"] == "segment" for c in out["cues"])                             # honest precision: English text is not word-aligned
    for c in out["cues"]:
        assert c["start"] < c["end"] and c["id"].startswith(f"scene_{c['scene']:02d}_cue_")


def test_scene_without_overlap_falls_back_to_scene_level(tmp_path):
    out = cues.build(_sample(tmp_path / "a"))
    assert out["scenes"]["2"]["arrangement"] == "scene_level" and out["links"]["2"] is None and out["links"]["3"] is None
    pdir = _sample(tmp_path / "b")
    (pdir / "transcript_en.json").unlink()                                              # no translation at all: no crash, every prompt scene-level
    out = cues.build(pdir)
    assert out["cues"] == [] and all(v is None for v in out["links"].values())


def test_match_detail_file_has_bands_reasons_and_cue_links(tmp_path):
    pdir = _sample(tmp_path)
    shutil.copy(FIX / "golden" / "match_report.json", pdir / "match_report.json")
    rep = MatchReport.model_validate_json((pdir / "match_report.json").read_text(encoding="utf-8"))
    rows = json.loads(match_detail.write(pdir, rep).read_text(encoding="utf-8"))
    assert len(rows) == 14 and all(r["reason"]["rule"] for r in rows)
    by = {r["n"]: r for r in rows}
    assert by[1]["band"] == "high" and by[9]["locked"] is True and by[9]["band"] == "none"      # the hand-picked image is locked and has no score
    assert by[5]["reason"]["source_cue"] and by[6]["reason"]["source_cue"] != by[5]["reason"]["source_cue"]


def test_plan_preview_shows_cues_only_with_flag(tmp_path, monkeypatch):
    pdir = _sample(tmp_path)
    shutil.copy(FIX / "golden" / "match_report.json", pdir / "match_report.json")
    monkeypatch.delenv("A2V_MATCH_DETAIL", raising=False)
    assert "arrangement" not in plan_preview.build(pdir)["scenes"][3]
    monkeypatch.setenv("A2V_MATCH_DETAIL", "1")
    sc4 = plan_preview.build(pdir)["scenes"][3]
    assert sc4["arrangement"] == "timed" and len(sc4["cues"]) == 3


# ---------- matcher decisions with a fake CLIP ----------
def _img(path: Path, seed: int):
    rng = np.random.default_rng(seed)
    Image.fromarray(rng.integers(40, 200, (450, 800, 3), dtype=np.uint8)).save(path)


def _project(tmp: Path, prompts: list[tuple[str, str]], files: list[str], same_content=()) -> Path:
    """prompts: [(text, role)] numbered 1..n in scene 1; files: upload names. same_content: pairs of file names that get identical pixels."""
    pdir = tmp / "proj"
    pdir.mkdir()
    items = [{"n": i + 1, "scene": 1, "slot": f"s01_{i}", "role": role, "ratio": "16:9", "required": True, "bg": "full", "text": t} for i, (t, role) in enumerate(prompts)]
    (pdir / "prompts_map.json").write_text(json.dumps({"prompts": items}), encoding="utf-8")
    src = tmp / "up"
    src.mkdir()
    for k, f in enumerate(files):
        _img(src / f, 100 + k)
    for a, b in same_content:
        shutil.copyfile(src / a, src / b)
    save_uploads(pdir, [src])
    return pdir


def _fake(weights: dict[str, dict[str, float]]):
    """score(image, text) = 0.2 + the weights of the words found in the text; weights[image stem][word]."""
    def scores(images, texts):
        out = np.full((len(images), len(texts)), 0.2)
        for i, p in enumerate(images):
            for j, t in enumerate(texts):
                out[i, j] += sum(w for word, w in weights.get(p.stem, {}).items() if word in t.lower())
        return out
    return scores


def test_medium_confidence_is_review_only_with_flag(tmp_path, monkeypatch):
    # image a: score 0.40 margin 0.2 (high); image b: score 0.26 margin 0.06 -> margin >= 0.06 but score < 0.30 (medium)
    pdir = _project(tmp_path, [("alpha scene", "main"), ("beta scene", "main")], ["a.png", "b.png"])
    monkeypatch.setattr(matcher, "_clip_scores", _fake({"a": {"alpha": 0.2}, "b": {"beta": 0.06}}))
    monkeypatch.delenv("A2V_MATCH_DETAIL", raising=False)
    off = {m.n: m for m in matcher.match(pdir).matches}
    assert off[1].status == "ok" and off[2].status == "ok"                               # flag off: old behavior
    monkeypatch.setenv("A2V_MATCH_DETAIL", "1")
    on = {m.n: m for m in matcher.match(pdir).matches}
    assert on[1].status == "ok" and on[2].status == "review" and "medium" in on[2].note
    assert [(m.file, m.score, m.margin) for m in off.values()] == [(m.file, m.score, m.margin) for m in on.values()]      # same scores, only the state differs


def test_low_confidence_stays_review_and_missing_stays_missing(tmp_path, monkeypatch):
    pdir = _project(tmp_path, [("alpha scene", "main"), ("beta scene", "main"), ("gamma scene", "main")], ["a.png", "b.png"])
    monkeypatch.setattr(matcher, "_clip_scores", _fake({"a": {"alpha": 0.2}, "b": {"beta": 0.0}}))
    monkeypatch.setenv("A2V_MATCH_DETAIL", "1")
    st = {m.n: m for m in matcher.match(pdir).matches}
    assert st[2].status == "review" and st[3].status == "missing" and st[3].file is None


def test_cue_agreement_flags_image_that_fits_another_narration(tmp_path, monkeypatch):
    pdir = _project(tmp_path, [("a red apple on a table", "main"), ("a yellow banana bunch", "main")], ["a.png", "b.png"])
    (pdir / "scene_plan.json").write_text(json.dumps({"style": {"suffix": "x", "palette": ["#000000", "#ffffff"]}, "scenes": [
        {"id": 1, "start": 0, "end": 10, "meaning": "m", "concept": "c", "mood": "m", "mode": "image-composite", "pattern": "split_two", "keywords": [], "params": {}}]}), encoding="utf-8")
    (pdir / "transcript_en.json").write_text(json.dumps({"duration": 10, "segments": [
        {"id": 0, "start": 0, "end": 4, "te": "x", "en": "Apples are red fruits."}, {"id": 1, "start": 5, "end": 9, "te": "x", "en": "Bananas are yellow."}]}), encoding="utf-8")
    monkeypatch.setenv("A2V_MATCH_DETAIL", "1")
    # both images match their own prompt text well, and each fits its own narration
    good = {"a": {"apple": 0.2}, "b": {"banana": 0.2}}
    monkeypatch.setattr(matcher, "_clip_scores", _fake(good))
    ok = {m.n: m.status for m in matcher.match(pdir).matches}
    assert ok == {1: "ok", 2: "ok"}                                                       # consistent: nothing flagged
    # image a still fits its own prompt text (apple), but the word "bananas" only occurs in the BANANA narration and image a fits it far better than the apple narration
    bad = {"a": {"apple": 0.2, "bananas": 0.5}, "b": {"banana": 0.2}}
    monkeypatch.setattr(matcher, "_clip_scores", _fake(bad))
    res = {m.n: m for m in matcher.match(pdir).matches}
    assert res[1].status == "review" and "narration of prompt 2" in res[1].note


def test_locked_image_keeps_its_prompt_and_is_not_reused(tmp_path, monkeypatch):
    pdir = _project(tmp_path, [("alpha scene", "main"), ("beta scene", "main")], ["x.png", "y.png"])
    monkeypatch.setenv("A2V_MATCH_DETAIL", "1")
    # the user locked prompt 2 -> x.png although CLIP thinks x.png is prompt 1
    (pdir / "match_report.json").write_text(MatchReport(matches=[
        MatchItem(n=1, file=None, method="none", status="missing"), MatchItem(n=2, file="x.png", method="clip", score=0.2, margin=0.0, status="review")]).model_dump_json(), encoding="utf-8")
    (pdir / "locks.json").write_text("[2]", encoding="utf-8")
    monkeypatch.setattr(matcher, "_clip_scores", _fake({"x": {"alpha": 0.3}, "y": {"beta": 0.3}}))
    got = {m.n: m for m in matcher.match(pdir).matches}
    assert got[2].file == "x.png" and got[2].status == "review" and got[2].score == 0.2        # exactly the saved item, untouched
    assert got[1].file == "y.png"                                                           # the locked image is not taken by prompt 1
    monkeypatch.delenv("A2V_MATCH_DETAIL")
    assert {m.n: m.file for m in matcher.match(pdir).matches}[1] == "x.png"                 # flag off: the old behavior (no locks)


def test_same_picture_twice_is_flagged_not_hidden(tmp_path, monkeypatch):
    pdir = _project(tmp_path, [("alpha scene", "main"), ("beta scene", "main")], ["a.png", "b.png"], same_content=[("a.png", "b.png")])
    monkeypatch.setattr(matcher, "_clip_scores", _fake({"a": {"alpha": 0.3}, "b": {"beta": 0.3}}))
    monkeypatch.setenv("A2V_MATCH_DETAIL", "1")
    rep = matcher.match(pdir)
    assert rep.duplicates and {m.n: m.status for m in rep.matches} == {1: "ok", 2: "review"}
    assert "same as the image of prompt 1" in rep.matches[1].note
    monkeypatch.delenv("A2V_MATCH_DETAIL")
    assert {m.n: m.status for m in matcher.match(pdir).matches} == {1: "ok", 2: "ok"}       # flag off unchanged (duplicates only listed)


def test_save_report_writes_detail_only_with_flag(tmp_path, monkeypatch):
    pdir = _sample(tmp_path)
    shutil.copy(FIX / "golden" / "match_report.json", pdir / "match_report.json")
    rep = MatchReport.model_validate_json((pdir / "match_report.json").read_text(encoding="utf-8"))
    monkeypatch.delenv("A2V_MATCH_DETAIL", raising=False)
    matcher.save_report(pdir, rep)
    assert not (pdir / "match_detail.json").exists()
    monkeypatch.setenv("A2V_MATCH_DETAIL", "1")
    matcher.save_report(pdir, rep)
    assert (pdir / "match_detail.json").exists()
