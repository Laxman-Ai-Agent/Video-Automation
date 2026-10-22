"""The UI's per-prompt upload relies on existing backend behaviour (no API change): a numbered file in the inbox is ingested next to the
images already in assets/raw and claims its prompt by file name, so the other assignments stay. Run: python -m pytest tests/test_m9_ui_inbox.py -q"""
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from backend import api_status, config, matcher, theme  # noqa: F401  (theme.json is read when backend.theme is first imported: before the fixtures move the project root)
from backend.assets import raw_dir, save_uploads
from backend.models import MatchReport

PROMPTS = [{"n": n, "scene": n, "slot": f"s{n:02d}_0", "role": "main", "ratio": "16:9", "text": f"prompt {n}"} for n in (1, 2, 3)]
# which prompt each image looks like to the (fake) CLIP: a -> 1, b -> 2, 03_c -> 3
LOOKS_LIKE = {"a": 0, "b": 1, "03_c": 2}


@pytest.fixture
def pdir(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    p = root / "projects" / "p1"
    p.mkdir(parents=True)
    monkeypatch.setattr(config, "PROJECT_ROOT", root)
    monkeypatch.setattr(config, "PROJECTS_DIR", root / "projects")
    (p / "prompts_map.json").write_text(json.dumps({"prompts": PROMPTS}), encoding="utf-8")
    (p / "scene_plan.json").write_text("{}", encoding="utf-8")

    def fake_scores(images, texts):
        s = np.full((len(images), len(texts)), 0.05)
        for i, path in enumerate(images):
            s[i, LOOKS_LIKE.get(Path(path).stem, 2)] = 0.9
        return s

    monkeypatch.setattr(matcher, "_clip_scores", fake_scores)
    return p


def make_image(path: Path, shade: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(shade)
    Image.fromarray(rng.integers(0, 255, (180, 320, 3), dtype=np.uint8)).save(path)


def assignment(pdir: Path) -> dict[int, tuple[str | None, str, str]]:
    rep = MatchReport.model_validate_json((pdir / "match_report.json").read_text(encoding="utf-8"))
    return {m.n: (m.file, m.method, m.status) for m in rep.matches}


def build(pdir: Path) -> None:
    """The ingest step, then the match step."""
    save_uploads(pdir, [pdir / "assets" / "inbox"])
    matcher.save_report(pdir, matcher.match(pdir))


def first_build(pdir: Path) -> Path:
    inbox = pdir / "assets" / "inbox"
    make_image(inbox / "a.png", 1)
    make_image(inbox / "b.png", 2)
    build(pdir)
    return inbox


def test_a_numbered_upload_takes_its_prompt_and_leaves_the_other_assignments_alone(pdir):
    inbox = first_build(pdir)
    before = assignment(pdir)
    assert before == {1: ("a.png", "clip", "ok"), 2: ("b.png", "clip", "ok"), 3: (None, "none", "missing")}

    make_image(inbox / "03_c.png", 3)                       # what the UI sends for "Upload Image" on the card of prompt 3
    build(pdir)
    after = assignment(pdir)

    assert after[3] == ("03_c.png", "filename", "ok")        # deterministic: by file number, not by content
    assert after[1] == before[1] and after[2] == before[2]   # nothing else moved
    assert sorted(f.name for f in raw_dir(pdir).iterdir()) == ["03_c.png", "a.png", "b.png"]   # nothing deleted


def test_a_unnumbered_extra_never_overrides_a_numbered_file_and_is_reported_as_unused(pdir):
    inbox = first_build(pdir)
    make_image(inbox / "03_c.png", 3)
    build(pdir)
    make_image(inbox / "extra.png", 4)                       # unnumbered, and it also looks like prompt 3
    build(pdir)
    rep = MatchReport.model_validate_json((pdir / "match_report.json").read_text(encoding="utf-8"))
    assert assignment(pdir)[3] == ("03_c.png", "filename", "ok")
    assert "extra.png" in rep.unused                         # left over, shown to the user, never forced into a prompt


def test_two_files_claiming_one_number_wait_for_a_decision(pdir):
    inbox = first_build(pdir)
    make_image(inbox / "03_c.png", 3)
    make_image(inbox / "03_d.png", 5)
    build(pdir)
    f, method, status = assignment(pdir)[3]
    assert (f, status) == (None, "review")                   # not guessed: the user chooses in the match check
    rep = MatchReport.model_validate_json((pdir / "match_report.json").read_text(encoding="utf-8"))
    assert "03_c.png" in next(m.note for m in rep.matches if m.n == 3) and "03_d.png" in next(m.note for m in rep.matches if m.n == 3)


def test_the_api_counts_the_inbox_only_so_apply_must_send_force(pdir):
    """image_count() reads assets/inbox when it holds files: after a per-prompt upload the API sees fewer images than prompts."""
    inbox = first_build(pdir)
    make_image(inbox / "03_c.png", 3)
    build(pdir)
    assert api_status.image_count(pdir) == 3 and api_status.required_count(pdir) == 3     # all uploaded through the UI: complete
    for f in (inbox / "a.png", inbox / "b.png"):             # images that came from the command line live in assets/raw only
        f.rename(pdir / "assets" / f.name)
    assert api_status.image_count(pdir) == 1 < api_status.required_count(pdir)             # submit without force=true would answer images_missing
