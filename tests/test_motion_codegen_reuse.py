"""Generated scene code is reused only while the inputs it was written from are unchanged: a new picture, text, length or palette writes it again (it used to be reused whenever the file existed)."""
import json

from VIDEO_ENGINE.stages import motion_animation as ma


def _fp(**kw):
    base = dict(duration=11.3, headline="Business owners", subtext="", texts=["Business owners"], palette=["#0f172a"], aspect="16:9",
                elements=[{"element_id": "s1_hero", "type": "image", "real_media": {"file": "projects/p/assets/old.jpg"}}])
    return ma.scene_input_fingerprint(**{**base, **kw})


def test_the_fingerprint_changes_with_every_input_the_code_is_written_from():
    same = _fp()
    assert _fp() == same
    assert _fp(elements=[{"element_id": "s1_hero", "type": "image", "real_media": {"file": "projects/p/assets/NEW.png"}}]) != same     # the user uploaded another picture
    assert _fp(headline="Other") != same and _fp(duration=12.0) != same and _fp(palette=["#000"]) != same and _fp(aspect="9:16") != same


def test_a_manifest_without_fingerprints_gives_none_so_its_code_is_written_again(tmp_path):
    assert ma.previous_fingerprints(tmp_path, "") == {}                                                   # no manifest
    (tmp_path / "motion_animation.json").write_text(json.dumps({"scenes": [{"scene_id": 1, "source_sha256": "x"}, {"scene_id": 2, "input_fingerprint": "abc"}]}), encoding="utf-8")
    got = ma.previous_fingerprints(tmp_path, "")
    assert got[1] is None and got[2] == "abc"
    (tmp_path / "motion_animation_9x16.json").write_text("not json", encoding="utf-8")
    assert ma.previous_fingerprints(tmp_path, "_9x16") == {}
