"""Two things of the motion plan that Stage 10 reported: (1) a positioned text (the quote_type pattern) now has a measured `drawn_box` (before: null, "collisions not verified"), and (2) the emphasis of a
marked word can be put on the spoken word it translates (`motion_planning.align_emphasis`, applied by `build_composition.ts --fixes`). The real builder (node) runs on the fixture plan.
Run: python -m pytest tests/test_emphasis_alignment.py -q"""
import importlib
import json
import shutil
import subprocess

import pytest

from backend import motion_planning as mpl

_mo = importlib.import_module("test_motion_only_mode")
FIXTURE, REMOTION = _mo.FIXTURE, _mo.REMOTION


def build(pdir, fixes=False, plan_only=True):
    cmd = f'npx tsx scripts/build_composition.ts "{pdir}" --motion --no-images' + (" --plan-only" if plan_only else "") + (" --fixes" if fixes else "")
    r = subprocess.run(cmd, cwd=REMOTION, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, (r.stderr or r.stdout)[-500:]


@pytest.fixture
def pdir(tmp_path):
    for f in ("scene_plan.json", "transcript.json"):
        shutil.copyfile(FIXTURE / f, tmp_path / f)
    build(tmp_path)
    return tmp_path


def plan(d):
    return json.loads((d / "motion_plan.json").read_text(encoding="utf-8"))


def pick(d):
    """A text with an emphasis and a spoken word of its scene that starts after the text has entered and early enough to be seen."""
    words = [w for s in json.loads((d / "transcript.json").read_text(encoding="utf-8"))["segments"] for w in s["words"]]
    for m in plan(d)["scenes"]:
        for t in m["texts"]:
            if not t.get("emphasis_at"):
                continue
            entered = (t["at"] if t.get("at") is not None else m["start"]) + (t.get("enter_s") or 0.5)
            end = mpl.reading_end(t, m["end"])
            for w in words:
                if m["start"] <= w["start"] and w["end"] <= m["end"] and entered + 0.05 <= w["start"] <= end - 0.5 and w["w"].strip(".,;:!?"):
                    return m, t, w
    pytest.skip("the fixture has no marked text with a spoken word after its entrance")


def test_a_positioned_text_has_a_drawn_box_where_the_renderer_puts_it(pdir):
    scene = next(m for m in plan(pdir)["scenes"] if m["pattern"] == "quote_type")
    comp_pos = {t["text"]: t for t in scene["texts"]}
    assert comp_pos and all(t["drawn_box"] for t in scene["texts"])                                           # before this: null (the planner did not measure a text with `pos`)
    build(pdir, plan_only=False)
    layers = [l for s in json.loads((pdir / "composition.json").read_text(encoding="utf-8"))["scenes"] if s["id"] == scene["id"] for l in s["layers"] if l["type"] == "motion_text" and l.get("pos")]
    assert layers
    for l in layers:
        b = comp_pos[l["text"]]["drawn_box"]
        assert abs(b[0] - l["pos"][0] / 1920) < 0.002 and abs(b[1] - l["pos"][1] / 1080) < 0.002             # its top-left corner IS the layer's pos (MotionTextLayer: left / top)
        assert b[2] > b[0] and b[3] > b[1] and b[2] <= 1 and b[3] <= 1


def test_an_emphasis_goes_on_the_start_of_the_spoken_word_and_the_rest_of_the_ledger_is_kept(pdir):
    m, t, w = pick(pdir)
    old = {"version": 1, "before": 3, "accepted": ["scene_02"], "scenes": {"1": {"textAt": {"0": 0.5}}}, "changes": [{"scene": "scene_01", "kind": "text_earlier", "text": "x", "from": 1, "to": 0.5, "why": "y"}]}
    (pdir / "motion_fixes.json").write_text(json.dumps(old), encoding="utf-8")
    done = mpl.align_emphasis(pdir, "16:9", [{"scene": m["id"], "text": t["text"], "word": w["w"].strip(".,;:!?")}])
    assert len(done) == 1 and done[0]["kind"] == "emphasis_aligned" and done[0]["from"] == t["emphasis_at"][0] and done[0]["to"] == round(w["start"], 2)
    fx = json.loads((pdir / "motion_fixes.json").read_text(encoding="utf-8"))
    assert fx["accepted"] == ["scene_02"] and fx["before"] == 3 and fx["scenes"]["1"]["textAt"] == {"0": 0.5}        # nothing else was touched
    assert fx["changes"][0] == old["changes"][0] and fx["changes"][-1]["kind"] == "emphasis_aligned" and fx["scenes"][str(m["id"])]["emphasisAt"]
    build(pdir, fixes=True)
    again = next(x for x in plan(pdir)["scenes"] if x["id"] == m["id"])
    assert next(x for x in again["texts"] if x["text"] == t["text"])["emphasis_at"] == [round(w["start"], 2)]       # the plan the builder writes has it
    build(pdir, fixes=True, plan_only=False)
    comp = json.loads((pdir / "composition.json").read_text(encoding="utf-8"))
    lay = next(l for s in comp["scenes"] if s["id"] == m["id"] for l in s["layers"] if l["type"] == "motion_text" and l["text"] == t["text"])
    assert lay["emphasisAt"] == [round(w["start"], 2)]                                                           # and so has the composition Motion Generation builds
    assert mpl.align_emphasis(pdir, "16:9", [{"scene": m["id"], "text": t["text"], "word": w["w"].strip(".,;:!?")}])[0]["to"] == round(w["start"], 2)       # a second decision is the same time


def test_a_decision_that_would_damage_the_animation_or_is_not_true_is_refused_and_writes_nothing(pdir):
    m, t, w = pick(pdir)
    word = w["w"].strip(".,;:!?")
    with pytest.raises(mpl.MotionError, match="not in the scene"):
        mpl.align_emphasis(pdir, "16:9", [{"scene": m["id"], "text": t["text"], "word": "no-such-word"}])
    with pytest.raises(mpl.MotionError, match="no text"):
        mpl.align_emphasis(pdir, "16:9", [{"scene": m["id"], "text": "not on the screen", "word": word}])
    with pytest.raises(mpl.MotionError, match="is not in the plan"):
        mpl.align_emphasis(pdir, "16:9", [{"scene": 999, "text": t["text"], "word": word}])
    words = [x for s in json.loads((pdir / "transcript.json").read_text(encoding="utf-8"))["segments"] for x in s["words"] if m["start"] <= x["start"] and x["end"] <= m["end"]]
    early = next(x for x in words if x["start"] < (t["at"] if t.get("at") is not None else m["start"]) + (t.get("enter_s") or 0.5) - 0.1)
    late = max(words, key=lambda x: x["start"])
    if early["w"].strip(".,;:!?"):
        with pytest.raises(mpl.MotionError, match="before .* has entered"):
            mpl.align_emphasis(pdir, "16:9", [{"scene": m["id"], "text": t["text"], "word": early["w"].strip(".,;:!?")}])
    if late["start"] + 0.4 > mpl.reading_end(t, m["end"]) and late["w"].strip(".,;:!?"):
        with pytest.raises(mpl.MotionError, match="too late"):
            mpl.align_emphasis(pdir, "16:9", [{"scene": m["id"], "text": t["text"], "word": late["w"].strip(".,;:!?")}])
    assert not (pdir / "motion_fixes.json").exists()                                                             # a refusal writes nothing


def test_auto_align_moves_an_emphasis_that_lies_inside_a_spoken_word_to_that_words_start_and_leaves_the_rest(pdir):
    m, t, w = pick(pdir)
    f = pdir / mpl._names("16:9")[0]
    mid = round((w["start"] + w["end"]) / 2, 3)
    assert w["start"] + 0.06 < mid < w["end"] - 0.06                                                     # the picked word is long enough to have an inside
    stored = json.loads(f.read_text(encoding="utf-8"))
    sc = next(x for x in stored["scenes"] if x["id"] == m["id"])
    next(x for x in sc["texts"] if x["text"] == t["text"])["emphasis_at"] = [mid]
    f.write_text(json.dumps(stored), encoding="utf-8")
    done = mpl.auto_align_emphasis(pdir, "16:9")
    assert [d["to"] for d in done["done"]] == [round(w["start"], 2)] and done["done"][0]["from"] == mid
    # the same time again, now on a word start: nothing inside a word, nothing to do
    stored = json.loads(f.read_text(encoding="utf-8"))
    next(x for x in next(s for s in stored["scenes"] if s["id"] == m["id"])["texts"] if x["text"] == t["text"])["emphasis_at"] = [round(w["start"], 2)]
    f.write_text(json.dumps(stored), encoding="utf-8")
    assert mpl.auto_align_emphasis(pdir, "16:9")["done"] == []
