"""Input stage (POST /projects): the project name, the audio file and the aspect ratio are validated, stored in the project folder and saved in project.json
(aspect and the audio reference); a failed creation leaves no half project; projects made before these fields existed read as before.
Run: python -m pytest tests/test_m9_input.py -q"""
import importlib
import json

import pytest

from backend import config, store

_m7 = importlib.import_module("test_m7")
client, wav_bytes = _m7.client, _m7.wav_bytes


def post(c, name="My Demo", aspect=None, fname="talk.wav", data=None, ctype="audio/wav"):
    form = {"name": name}
    if aspect is not None:
        form["aspect"] = aspect
    return c.post("/projects", data=form, files={"audio": (fname, wav_bytes() if data is None else data, ctype)})


def folders():
    return sorted(p.name for p in config.PROJECTS_DIR.iterdir())


def test_a_valid_project_stores_the_audio_and_saves_the_aspect_and_the_audio_reference(client):
    r = post(client, "My Demo", "9:16", "Narration take 2.WAV")
    assert r.status_code == 201, r.text
    info = r.json()
    assert info["aspect"] == "9:16" and info["state"] == "created" and info["name"] == "My Demo" and info["id"].startswith("my-demo-")
    seconds = info["audio"].pop("duration")                # read by ffprobe; None only when it is not installed
    assert seconds is None or seconds > 0
    assert info["audio"] == {"file": "audio.wav", "original_name": "Narration take 2.WAV", "size_bytes": len(wav_bytes()), "format": "WAV"}
    info["audio"]["duration"] = seconds
    pdir = config.PROJECTS_DIR / info["id"]
    assert (pdir / "audio.wav").read_bytes() == wav_bytes()                          # in the project folder
    assert json.loads((pdir / "project.json").read_text(encoding="utf-8")) == info   # and referenced in the project metadata
    assert client.get(f"/projects/{info['id']}").json() == info
    assert [p["id"] for p in client.get("/projects").json()] == [info["id"]]


@pytest.mark.parametrize("aspect", ["9:16", "16:9"])
def test_both_aspect_ratios_are_saved(client, aspect):
    assert post(client, aspect=aspect).json()["aspect"] == aspect


def test_every_project_gets_its_own_id_even_with_the_same_name(client):
    ids = {post(client).json()["id"] for _ in range(3)}
    assert len(ids) == 3 and len(folders()) == 3


def test_the_aspect_is_optional_so_older_callers_still_work(client):
    r = post(client)
    assert r.status_code == 201 and r.json()["aspect"] is None
    assert "aspect" not in json.loads((config.PROJECTS_DIR / r.json()["id"] / "project.json").read_text(encoding="utf-8"))


def test_missing_or_invalid_fields_are_refused_and_nothing_is_created(client):
    assert post(client, aspect="4:3").json()["error"]["code"] == "invalid_aspect"
    assert post(client, name="   ").json()["error"]["code"] == "invalid_name"
    assert client.post("/projects", data={"name": "x"}).status_code == 422                   # no audio at all
    assert client.post("/projects", files={"audio": ("a.wav", wav_bytes(), "audio/wav")}).status_code == 422   # no name
    assert folders() == []


@pytest.mark.parametrize("fname", ["notes.txt", "clip.mp4", "talk", "talk.exe"])
def test_an_unsupported_file_type_is_refused_before_a_project_exists(client, fname):
    r = post(client, fname=fname, ctype="application/octet-stream")
    assert r.status_code == 415 and r.json()["error"]["code"] == "unsupported_media"
    assert folders() == []


@pytest.mark.parametrize("fname", ["a.mp3", "a.wav", "a.m4a"])
def test_the_three_formats_of_the_input_page_are_accepted(client, fname):
    r = post(client, fname=fname)
    assert r.status_code == 201 and r.json()["audio"]["format"] == fname[-3:].upper()


def test_a_file_over_the_size_limit_leaves_no_half_project(client, monkeypatch):
    monkeypatch.setattr(store, "MAX_AUDIO_BYTES", 1000)
    r = post(client, data=b"0" * 5000)
    assert r.status_code == 413 and r.json()["error"]["code"] == "file_too_large"
    assert folders() == []


def test_a_failure_while_saving_the_file_leaves_no_half_project(client, monkeypatch):
    from backend.routes import projects

    async def broken(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(projects, "receive", broken)
    with pytest.raises(OSError):
        post(client)
    assert folders() == []


def test_projects_made_before_aspect_and_audio_existed_read_unchanged(client):
    pdir = config.PROJECTS_DIR / "old-one"
    pdir.mkdir()
    old = {"id": "old-one", "name": "Old", "created": "2026-01-01T00:00:00", "state": "done"}
    (pdir / "project.json").write_text(json.dumps(old), encoding="utf-8")
    got = client.get("/projects/old-one").json()
    assert got == {**old, "aspect": None, "audio": None, "use_images": True, "motion_branch": False, "reusable_motion_templates": True, "media": None, "motion_kit": False}      # a project made before the Use Images setting keeps the image workflow; one made before the media mix has none (defaults apply)
    assert json.loads((pdir / "project.json").read_text(encoding="utf-8")) == old        # the file itself is never rewritten by a read
    assert post(client).status_code == 201
    assert json.loads((pdir / "project.json").read_text(encoding="utf-8")) == old        # creating another project leaves it alone


def test_the_new_project_starts_the_analysis_through_the_real_job_endpoint(client):
    pid = post(client, "Flow", "16:9").json()["id"]
    r = client.post(f"/projects/{pid}/transcribe")
    assert r.status_code == 202 and r.json()["label"] == "transcribe"
    assert _m7.wait_job(client, pid)["error"] is None
    assert client.get(f"/projects/{pid}").json()["aspect"] == "16:9"
