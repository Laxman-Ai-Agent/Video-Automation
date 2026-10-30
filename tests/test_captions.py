"""Phase 6: captions (stages/captions.py, the `captions` project option, the composition). Run: python -m pytest tests/test_captions.py -q (with the project .venv)"""
import importlib
import json

from SYSTEM.core import config
from VIDEO_ENGINE.stages import captions as cap
from VIDEO_ENGINE.stages import motion_animation as ma
from VIDEO_ENGINE.stages import store

_m7 = importlib.import_module("test_m7")
client, create = _m7.client, _m7.create


def words(*items):
    """words('hello', 0.0, 0.4, 'world', 0.4, 0.8) -> [{w, start, end}]"""
    return [{"w": items[i], "start": items[i + 1], "end": items[i + 2]} for i in range(0, len(items), 3)]


def test_a_caption_ends_at_a_sentence_a_pause_or_the_width():
    spoken = words("This", 0.0, 0.3, "is", 0.3, 0.5, "one.", 0.5, 0.9,                       # a sentence end
                   "Then", 0.95, 1.2, "a", 1.2, 1.3, "pause", 1.3, 1.7,
                   "later", 2.3, 2.7)                                                      # a pause of 0.6 s
    got = cap.build(spoken, "16:9", [])
    assert [[w["w"] for w in c["words"]] for c in got] == [["This", "is", "one."], ["Then", "a", "pause"], ["later"]]
    long = words(*[x for i in range(14) for x in (f"word{i}", i * 0.3, i * 0.3 + 0.28)])       # 14 words of 5-6 characters do not fit one caption
    parts = cap.build(long, "16:9", [])
    assert len(parts) > 1 and all(sum(len(w["w"]) + 1 for w in c["words"]) <= cap.MAX_GRAPHEMES["16:9"] + 1 for c in parts)
    assert len(cap.build(long, "9:16", [])) > len(parts)                                      # a portrait caption is narrower


def test_a_telugu_syllable_counts_as_one_grapheme_not_as_its_code_points():
    word = "తెలుగులో"                                                                       # 8 code points, 5 grapheme clusters
    one = cap.build(words(*[x for i in range(6) for x in (word, i * 0.3, i * 0.3 + 0.28)]), "16:9", [])
    assert len(one) == 1                                                                     # 6 x (5 + 1) = 35 <= 38: it would be split if code points were counted


def test_the_first_caption_is_the_hook_only_when_it_starts_in_the_first_seconds():
    assert [c["hook"] for c in cap.build(words("Hello.", 0.5, 0.9, "Next", 1.0, 1.4), "16:9", [])] == [True, False]
    assert [c["hook"] for c in cap.build(words("Late.", 5.0, 5.4), "16:9", [])] == [False]


def test_a_number_and_a_word_the_scene_shows_are_key_terms_but_only_in_that_scene():
    scenes = [{"id": 1, "start": 0, "end": 4}, {"id": 2, "start": 4, "end": 8}]
    terms = cap.scene_terms(scenes, {1: [{"text": "Virtual Assistant"}], 2: []})
    got = cap.build(words("A", 0.0, 0.2, "virtual", 0.2, 0.6, "assistant,", 0.6, 1.0, "costs", 1.0, 1.3, "5", 1.3, 1.5, "virtual", 4.5, 4.9), "16:9", terms)
    keys = {w["w"] + str(w["start"]): w["key"] for c in got for w in c["words"]}
    assert keys == {"A0.0": False, "virtual0.2": True, "assistant,0.6": True, "costs1.0": False, "51.3": True, "virtual4.5": False}


def test_a_blank_word_is_not_drawn():
    got = cap.build(words("a", 0.0, 0.2, " ", 0.2, 0.3, "b", 0.3, 0.5), "16:9", [])
    assert [w["w"] for c in got for w in c["words"]] == ["a", "b"]


def test_a_project_stores_the_captions_choice_at_creation_and_old_projects_have_it_off(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path)
    assert store.captions(store.create("New", "16:9")) is True                              # on by default
    off = store.create("Quiet", "16:9", captions=False)
    assert store.captions(off) is False
    info = json.loads((off / "project.json").read_text(encoding="utf-8"))
    info.pop("captions")                                                                     # a project made before the option existed keeps rendering as it did
    (off / "project.json").write_text(json.dumps(info), encoding="utf-8")
    assert store.captions(off) is False


def test_the_api_takes_the_choice_at_upload_and_nothing_changes_it_afterwards(client):
    assert create(client).json()["captions"] is True
    off = client.post("/projects", data={"name": "K", "captions": "false"}, files={"audio": ("a.wav", _m7.wav_bytes(), "audio/wav")})
    assert off.status_code == 201 and off.json()["captions"] is False
    client.patch(f"/projects/{off.json()['id']}", json={"captions": True})
    assert client.get(f"/projects/{off.json()['id']}").json()["captions"] is False


def composition(tmp_path, monkeypatch, on):
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path)
    pdir = store.create("Cap", "16:9", captions=on)
    seg = {"id": 0, "start": 0.0, "end": 4.0, "text": "x", "words": words("Hello", 0.0, 0.5, "5", 0.5, 1.0, "world.", 1.0, 1.6, "Bye", 5.0, 5.4)}
    (pdir / "transcript_corrected.json").write_text(json.dumps({"language": "te", "duration": 6.0, "segments": [seg]}), encoding="utf-8")
    return ma.custom_composition(pdir, "16:9", [{"id": 1, "start": 0, "end": 3}, {"id": 2, "start": 3, "end": 6}], ["#111111", "#ffffff"])


def test_the_composition_carries_the_captions_only_when_the_project_wants_them(tmp_path, monkeypatch):
    on = composition(tmp_path / "a", monkeypatch, True)
    assert on["meta"]["subtitles"] is True and [[w["w"] for w in c["words"]] for c in on["captions"]] == [["Hello", "5", "world."], ["Bye"]]
    assert on["captions"][0]["hook"] is True and on["captions"][0]["words"][1]["key"] is True
    off = composition(tmp_path / "b", monkeypatch, False)
    assert off["meta"]["subtitles"] is False and "captions" not in off
    assert len(on["words"]) == len(off["words"]) == 4                                      # the spoken words stay in the composition for every reader
