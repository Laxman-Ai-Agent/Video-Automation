"""Final QC sees an empty frame at a cut even when the background is a gradient: the test project's render showed only its vignetted
background at 4 of 7 cuts (std 7-12, so the old flat test passed it) and Final QC approved it with 0 warnings."""
import numpy as np
from PIL import Image, ImageDraw

from VIDEO_ENGINE.stages import final_qc as fq

PROF = fq.PROFILES["standard"]


def _gradient(path):
    y, x = np.mgrid[0:270, 0:480]
    g = 20 + 60 * np.exp(-(((x - 240) / 260) ** 2 + ((y - 230) / 120) ** 2))            # a dark vignette, no drawn edge
    Image.fromarray(g.astype("uint8")).convert("RGB").save(path)
    return path


def _content(path):
    im = Image.open(_gradient(path))
    d = ImageDraw.Draw(im)
    for i in range(3):
        d.rounded_rectangle([40 + i * 140, 70, 160 + i * 140, 170], radius=12, outline=(200, 220, 255), width=3)
    d.text((180, 30), "Fast & Professional", fill=(255, 255, 255))
    im.save(path)
    return path


def _sample(frame, path):
    return {"frame": frame, **{k: v for k, v in fq.measure(path).items() if k != "_small"}}


def test_detail_separates_a_gradient_from_drawn_content(tmp_path):
    assert fq.measure(_gradient(tmp_path / "g.png"))["detail"] < PROF["empty_detail_pct"]
    assert fq.measure(_content(tmp_path / "c.png"))["detail"] > PROF["empty_detail_pct"]


def _run(tmp_path, blank_after_cut):
    t = {"transition_id": "t1", "from_scene": "scene_001", "to_scene": "scene_002", "type": "fade", "start_frame": 100, "end_frame": 113, "applied_frames": 13}
    frames = {98: "c", 100: "c", 106: "c", 112: "c", 101: "g" if blank_after_cut else "c"}
    samples = [_sample(f, (_gradient if k == "g" else _content)(tmp_path / f"{f}.png")) for f, k in frames.items()]
    q = fq.Q()
    fq._boundaries(q, [], [t], {"frame_quality": {"samples": samples}}, PROF)
    return [c for c in q.checks if c["rule_id"] == "QC_TRANSITION_NOT_BLANK"][0]


def test_an_empty_frame_at_the_cut_is_a_warning(tmp_path):
    c = _run(tmp_path, blank_after_cut=True)
    assert c["status"] == "warning" and c["evidence"]["frames"] == [101]


def test_a_cut_with_content_on_both_sides_passes(tmp_path):
    assert _run(tmp_path, blank_after_cut=False)["status"] == "passed"
