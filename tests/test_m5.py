"""M5 tests: 6 simple shape images renamed randomly -> all matched; swapped content detected as review.
Run: python -m pytest tests/test_m5.py -q  (with the project .venv)"""
import json
import random
from pathlib import Path

from PIL import Image, ImageDraw

from backend.assets import save_uploads
from backend.matcher import apply_fix, match, run
from backend.models import MatchItem, MatchReport

SHAPES = [  # (prompt text, draw function)
    ("a red circle on a white background", lambda d: d.ellipse((300, 150, 700, 550), fill="red")),
    ("a blue square on a white background", lambda d: d.rectangle((300, 150, 700, 550), fill="blue")),
    ("a green triangle on a white background", lambda d: d.polygon([(500, 120), (260, 560), (740, 560)], fill="green")),
    ("a yellow five pointed star on a white background", lambda d: d.polygon(
        [(500, 100), (570, 300), (780, 300), (610, 420), (670, 620), (500, 500), (330, 620), (390, 420), (220, 300), (430, 300)], fill="gold")),
    ("a black cross on a white background", lambda d: (d.rectangle((440, 100, 560, 600), fill="black"), d.rectangle((250, 280, 750, 420), fill="black"))),
    ("an orange horizontal striped pattern", lambda d: [d.rectangle((0, y, 1000, y + 50), fill="orange") for y in range(0, 700, 100)]),
]


def make_project(tmp: Path, names: list[str]) -> Path:
    pdir = tmp / "proj"
    pdir.mkdir()
    prompts = [{"n": i + 1, "scene": 1, "slot": f"s01_{i}", "role": "supporting", "ratio": "4:3", "required": True,
                "bg": "full", "text": t} for i, (t, _) in enumerate(SHAPES)]
    (pdir / "prompts_map.json").write_text(json.dumps({"prompts": prompts}), encoding="utf-8")
    src = tmp / "uploads"
    src.mkdir()
    for (t, draw), name in zip(SHAPES, names):
        im = Image.new("RGB", (1000, 750), "white")
        draw(ImageDraw.Draw(im))
        im.save(src / name)
    save_uploads(pdir, [src])
    return pdir


def test_shuffled_names_all_matched(tmp_path):
    names = [f"IMG_{random.Random(7).randint(1000, 9999) + i}.png" for i in range(6)]   # no numbers: CLIP must decide
    random.Random(1).shuffle(names)
    pdir = make_project(tmp_path, names)
    rep = match(pdir)
    got = {m.n: m.file for m in rep.matches}
    assert all(m.method == "clip" for m in rep.matches)
    assert got == {i + 1: names[i] for i in range(6)}, rep.model_dump()
    assert all(m.status == "ok" for m in rep.matches)


def test_swapped_content_flagged_review(tmp_path):
    names = [f"{i + 1:02d}.png" for i in range(6)]
    names[0], names[1] = names[1], names[0]   # image 1 (red circle) is saved as 02.png and vice versa
    pdir = make_project(tmp_path, names)
    rep = match(pdir)
    st = {m.n: m.status for m in rep.matches}
    assert st[1] == "review" and st[2] == "review"
    assert all(st[n] == "ok" for n in (3, 4, 5, 6))


def test_missing_unused_and_manual_fix(tmp_path):
    names = [f"{i + 1:02d}.png" for i in range(6)]
    pdir = make_project(tmp_path, names)
    (pdir / "assets" / "raw" / "04.png").rename(pdir / "assets" / "raw" / "extra_star.png")
    (pdir / "assets" / "work" / "04.png").rename(pdir / "assets" / "work" / "extra_star.png")
    rep = run(pdir)
    assert next(m for m in rep.matches if m.n == 4).status in ("ok", "review")   # CLIP may recover it, never silently wrong
    rep2 = apply_fix(pdir, {"file": "extra_star.png", "n": 4})
    m4 = next(m for m in rep2.matches if m.n == 4)
    assert m4.file == "extra_star.png" and m4.method == "manual" and m4.status == "ok"
    assert MatchReport.model_validate_json((pdir / "match_report.json").read_text()).matches[3].file == "extra_star.png"


def _manual_project(tmp: Path, roles: list[str], ratio: str = "16:9") -> Path:
    pdir = tmp / "proj2"
    pdir.mkdir()
    prompts = [{"n": i + 1, "scene": i + 1, "slot": f"s{i + 1:02d}_0", "role": r, "ratio": ratio, "required": True,
                "bg": "full", "text": f"prompt {i + 1}"} for i, r in enumerate(roles)]
    (pdir / "prompts_map.json").write_text(json.dumps({"prompts": prompts}), encoding="utf-8")
    return pdir


def test_near_identical_images_are_reported_as_duplicates_without_crashing(tmp_path, monkeypatch):
    """Regression: duplicates() returns work-copy names ("a.png") while raw is keyed by stem; a .jpg upload used to
    raise KeyError and kill the whole match step."""
    import numpy as np
    from backend import matcher
    pdir = _manual_project(tmp_path, ["main", "main", "main"])
    up = tmp_path / "up_dup"
    up.mkdir()
    base = np.random.default_rng(3).integers(0, 255, (180, 320, 3), dtype=np.uint8)
    Image.fromarray(base).save(up / "a.jpg", quality=95)
    Image.fromarray(base).save(up / "b.jpg", quality=90)                       # same picture, different file
    Image.fromarray(np.random.default_rng(9).integers(0, 255, (180, 320, 3), dtype=np.uint8)).save(up / "c.jpg")
    save_uploads(pdir, [up])
    monkeypatch.setattr(matcher, "_clip_scores", lambda images, texts: np.zeros((len(images), len(texts))))
    rep = match(pdir)
    assert rep.duplicates == [["a.jpg", "b.jpg"]]                              # raw names, with their real extension
    assert "c.jpg" not in sum(rep.duplicates, [])


def test_apply_fix_recomputes_image_checks(tmp_path):
    """Regression: after apply_fix the warnings belong to the NEW image, never the previous one."""
    import numpy as np
    pdir = _manual_project(tmp_path, ["main"])
    up = tmp_path / "up2"
    up.mkdir()
    Image.new("RGB", (1000, 750), "gray").save(up / "small.png")   # 4:3, 1000 px: low_res + bad_ratio (+ blurry, flat)
    noise = (np.random.default_rng(0).random((1152, 2048, 3)) * 255).astype("uint8")
    Image.fromarray(noise).save(up / "good.png")                  # 2048x1152, 16:9, sharp: no warnings
    save_uploads(pdir, [up])
    rep = MatchReport(matches=[MatchItem(n=1, file="small.png", method="clip", status="review", score=0.1, margin=0.0)],
                      warnings=[{"file": "small.png", "n": 1, "type": "low_res"}, {"file": "small.png", "n": 1, "type": "bad_ratio"}])
    (pdir / "match_report.json").write_text(rep.model_dump_json())
    after = apply_fix(pdir, {"file": "good.png", "n": 1})        # good image replaces the bad one
    assert [w for w in after.warnings if w["n"] == 1] == []
    after = apply_fix(pdir, {"file": "small.png", "n": 1})       # bad image comes back: its own checks appear
    kinds = {w["type"] for w in after.warnings if w["n"] == 1}
    assert {"low_res", "bad_ratio"} <= kinds and all(w["file"] == "small.png" for w in after.warnings)
    assert "good.png" in after.unused
    saved = MatchReport.model_validate_json((pdir / "match_report.json").read_text())
    assert {w["type"] for w in saved.warnings} == {w["type"] for w in after.warnings}
