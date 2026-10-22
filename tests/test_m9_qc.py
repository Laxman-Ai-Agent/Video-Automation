"""Video QC (GET /projects/{id}/qc): the checks are measured on the real mp4 with ffprobe / ffmpeg; a missing or wrong video is reported as failed.
Run: python -m pytest tests/test_m9_qc.py -q"""
import importlib
import subprocess

from backend import config

_m7 = importlib.import_module("test_m7")
client, wav_bytes = _m7.client, _m7.wav_bytes


def make_project(c):
    return c.post("/projects", data={"name": "Qc"}, files={"audio": ("a.wav", wav_bytes(2.0), "audio/wav")}).json()["id"]


def make_video(pid, size="960x540", seconds=2.0, audio=True, color="red", name="out_preview.mp4"):
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c={color}:s={size}:d={seconds}:r=30"]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}", "-af", "volume=0.3"]
    cmd += ["-pix_fmt", "yuv420p", str(config.PROJECTS_DIR / pid / name)]
    subprocess.run(cmd, check=True)


def qc(c, pid, aspect="16:9", preview=True):
    r = c.get(f"/projects/{pid}/qc", params={"aspect": aspect, "preview": preview})
    assert r.status_code == 200, r.text
    return r.json()


def by_id(rep):
    return {c["id"]: c for c in rep["checks"]}


def test_no_video_is_one_failed_check_not_a_success(client):
    rep = qc(client, make_project(client))
    assert rep["result"] == "failed" and [c["id"] for c in rep["checks"]] == ["video_exists"] and rep["checks"][0]["result"] == "failed"


def test_a_correct_video_passes_every_measured_check(client):
    pid = make_project(client)
    make_video(pid)
    rep = qc(client, pid)
    assert rep["result"] == "passed", rep
    assert {"video_exists", "length", "size", "audio_stream", "clipping", "black"} <= set(by_id(rep))


def test_the_picture_size_must_match_the_aspect_ratio(client):
    pid = make_project(client)
    make_video(pid, size="540x960")                                  # a portrait picture in the 16:9 file
    make_video(pid, size="540x960", name="out_preview_9x16.mp4")
    assert by_id(qc(client, pid, "16:9"))["size"]["result"] == "failed"
    assert by_id(qc(client, pid, "9:16"))["size"]["result"] == "passed"


def test_a_video_of_the_wrong_length_fails(client):
    pid = make_project(client)
    make_video(pid, seconds=1.0)
    c = by_id(qc(client, pid))["length"]
    assert c["result"] == "failed" and "audio 2.00 s" in c["detail"]


def test_a_video_without_sound_fails(client):
    pid = make_project(client)
    make_video(pid, audio=False)
    rep = qc(client, pid)
    assert by_id(rep)["audio_stream"]["result"] == "failed" and rep["result"] == "failed"


def test_black_frames_are_reported_as_a_warning(client):
    pid = make_project(client)
    make_video(pid, color="black")
    c = [x for x in qc(client, pid)["checks"] if x["id"] == "black"]
    assert c and c[0]["result"] == "warning" and "black from 0.00 s" in c[0]["detail"]


def test_an_invalid_aspect_is_refused(client):
    assert client.get(f"/projects/{make_project(client)}/qc", params={"aspect": "4:3"}).status_code == 422


def test_the_findings_have_a_place_in_the_video_and_media_details_are_measured(client):
    pid = make_project(client)
    make_video(pid)
    rep = qc(client, pid)
    m = rep["media"]
    assert m["video_codec"] == "h264" and m["audio_codec"] and (m["width"], m["height"]) == (960, 540) and m["fps"] == 30 and m["size_bytes"] > 0
    assert by_id(rep)["decode"]["result"] == "passed"                                                    # the whole picture was decoded
    assert by_id(rep)["freeze"]["result"] == "passed"                                                    # 2 s of one colour is shorter than the freeze limit


def test_a_long_unchanging_picture_is_a_warning_with_its_time(client):
    pid = make_project(client)
    make_video(pid, seconds=5.0)
    (config.PROJECTS_DIR / pid / "audio.wav").exists()
    rep = qc(client, pid)
    freeze = [c for c in rep["checks"] if c["id"] == "freeze" and c["result"] == "warning"]
    assert freeze and freeze[0]["at"] is not None and freeze[0]["until"] > freeze[0]["at"]

