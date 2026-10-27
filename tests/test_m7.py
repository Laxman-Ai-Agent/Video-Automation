"""M7 API tests (FastAPI TestClient). Whisper, CLIP and Remotion are replaced by fast fakes; everything else
(routes, store, jobs, pipeline executor, fill_slots) is real.
Run: python -m pytest tests/test_m7.py -q"""
import io
import importlib
import json
import shutil
import time
import wave
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend import config, jobs, pipeline, store
from backend.main import app

FIXTURE = Path(__file__).parent / "fixtures" / "plan_sample"


def wav_bytes(seconds: float = 1.0) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * int(16000 * seconds))
    return buf.getvalue()


def png_bytes(color=(200, 50, 50), size=(320, 180)) -> bytes:
    """Seeded noise per colour: every image is visually distinct (flat images would trigger the duplicate check,
    which currently crashes in matcher.py:113 - reported separately, M5 is frozen)."""
    arr = np.random.default_rng(sum(color) * 7 + color[0]).integers(0, 255, (size[1], size[0], 3), dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def client(tmp_path, monkeypatch, llm_review_pass):
    root = tmp_path / "repo"
    (root / "projects").mkdir(parents=True)
    (root / "VIDEO_ENGINE" / "remotion" / "src").mkdir(parents=True)
    (root / "VIDEO_ENGINE" / "remotion" / "public" / "geo").mkdir(parents=True)
    (root / "VIDEO_ENGINE" / "remotion" / "src" / "Main.tsx").write_text("x")
    monkeypatch.setattr(config, "PROJECT_ROOT", root)
    monkeypatch.setattr(config, "PROJECTS_DIR", root / "projects")
    monkeypatch.setattr(pipeline.shutil, "which", lambda t: "/fake/" + t)

    from backend.transcribe import Transcript

    def fake_transcribe(pdir, progress=None):
        if progress:
            progress(50)
        (pdir / "transcript.json").write_text(json.dumps({"language": "te", "duration": 1.0, "segments": []}))
        return Transcript(language="te", duration=1.0, segments=[])

    monkeypatch.setattr("backend.transcribe.transcribe", fake_transcribe)
    monkeypatch.setattr("backend.cuts.make_cuts", lambda pdir: [{"t": 0.5, "reason": "silence", "silence": 0.3}])

    def fake_render(pdir, preview, on_progress=None, aspect="16:9", out=None):
        """Stands in for Remotion. A final render hands Stage 13 a real encoded video of the composition's size and length (it verifies the file for real); a preview is 10 kB of bytes."""
        from backend.render import output_path, stage_audio
        stage_audio(pdir)
        if on_progress:
            on_progress(60, 5)
        out = out or output_path(pdir, preview, aspect)
        if preview:
            out.write_bytes(b"0123456789" * 1000)
        else:
            shutil.copyfile(importlib.import_module("test_motion_only_mode").real_video(pdir, aspect), out)
        return out
    monkeypatch.setattr("backend.render.render", fake_render)
    jobs._jobs.clear()
    return TestClient(app)


def wait_job(c: TestClient, pid: str, timeout: float = 20):
    end = time.time() + timeout
    while time.time() < end:
        s = c.get(f"/projects/{pid}/status").json()
        if not s["running"]:
            return s
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def create(c: TestClient, name="My Demo", audio=None, fname="talk.wav"):
    return c.post("/projects", data={"name": name}, files={"audio": (fname, audio or wav_bytes(), "audio/wav")})


def install_plan(pid: str):
    """Stand-in for /plan: copy the known-good M4 sample outputs into the project."""
    pdir = config.PROJECTS_DIR / pid
    for f in ("scene_plan.json", "prompts_map.json", "composition.json", "translation.json"):
        shutil.copyfile(FIXTURE / f, pdir / f)
    return pdir


def n_prompts(pdir: Path) -> int:
    return len(json.loads((pdir / "prompts_map.json").read_text())["prompts"])


# ---------- happy path: create -> transcribe -> waits for the plan ----------
def test_full_flow(client):
    r = create(client)
    assert r.status_code == 201
    info = r.json()
    pid = info["id"]
    assert info["name"] == "My Demo" and pid.startswith("my-demo-") and info["state"] == "created"
    assert (config.PROJECTS_DIR / pid / "audio.wav").exists() and (config.PROJECTS_DIR / pid / "project.json").exists()
    assert pid in [p["id"] for p in client.get("/projects").json()]

    assert client.post(f"/projects/{pid}/transcribe").status_code == 202
    s = wait_job(client, pid)
    assert s["error"] is None and s["waiting_for"] == "plan" and s["command"] == f"/plan {pid}"
    assert client.get(f"/projects/{pid}").json()["state"] == "done"                # the orchestrator's run (Audio Input -> Audio Analysis) finished
    assert client.get(f"/projects/{pid}/status").json()["waiting_for"] == "plan"
    assert client.get(f"/projects/{pid}/result").status_code == 404           # nothing rendered


def test_status_has_all_documented_fields(client):
    pid = create(client).json()["id"]
    s = client.get(f"/projects/{pid}/status").json()
    assert {"step", "percent", "message", "error", "waiting_for"} <= set(s)


# ---------- uploads ----------
def test_upload_rejections(client, monkeypatch):
    monkeypatch.setattr(store, "MAX_AUDIO_BYTES", 100)
    assert create(client, name="Big", audio=wav_bytes(2)).status_code == 413
    assert create(client, fname="clip.exe").status_code == 415
    assert all(p["name"] != "Big" for p in client.get("/projects").json())          # failed creates leave nothing behind


# ---------- submit rules, review, fix ----------


# ---------- jobs ----------
def test_one_active_job_per_project_and_cancel(client, monkeypatch):
    pid = create(client).json()["id"]
    gate = {"go": False}

    def slow_transcribe(pdir, progress=None):
        end = time.time() + 10
        while not gate["go"] and time.time() < end:
            time.sleep(0.02)
        (pdir / "transcript.json").write_text("{}")
        from backend.transcribe import Transcript
        return Transcript(language="te", duration=1, segments=[])
    monkeypatch.setattr("backend.transcribe.transcribe", slow_transcribe)
    assert client.post(f"/projects/{pid}/transcribe").status_code == 202
    again = client.post(f"/projects/{pid}/transcribe")
    assert again.status_code == 409 and again.json()["error"]["code"] == "job_running"
    assert client.get(f"/projects/{pid}/status").json()["running"] is True
    assert client.post(f"/projects/{pid}/cancel").status_code == 200
    gate["go"] = True
    wait_job(client, pid)
    assert jobs.current(pid).state == "cancelled"                               # stopped before the next step (cuts)
    assert not (config.PROJECTS_DIR / pid / "cuts.json").exists()
    assert client.post(f"/projects/{pid}/cancel").json()["error"]["code"] == "no_job"


def test_failed_step_reports_error_without_the_repo_path(client, monkeypatch):
    pid = create(client).json()["id"]

    def boom(pdir, progress=None):
        raise pipeline.StepError(f"cannot read {pdir / 'audio.wav'}")
    monkeypatch.setattr("backend.transcribe.transcribe", boom)
    client.post(f"/projects/{pid}/transcribe")
    s = wait_job(client, pid)
    assert s["error"] and str(config.PROJECT_ROOT) not in s["error"] and "audio.wav" in s["error"]
    assert client.get(f"/projects/{pid}").json()["state"] == "failed"


# ---------- errors, security, projects ----------
def test_error_format_and_no_path_leaks(client):
    r = client.get("/projects/does-not-exist")
    assert r.status_code == 404 and set(r.json()["error"]) == {"code", "message", "hint"}
    assert client.get("/projects/%2E%2E").status_code == 404
    assert client.get("/projects/..%2F..%2Fetc").status_code in (404, 422)
    assert client.get("/nope").json()["error"]["code"] == "not_found"
    assert client.post("/projects", data={"name": "x"}).json()["error"]["code"] == "invalid_request"        # audio missing
    assert str(config.PROJECT_ROOT) not in json.dumps(r.json())


def test_delete_needs_confirmation(client):
    pid = create(client).json()["id"]
    r = client.delete(f"/projects/{pid}")
    assert r.status_code == 400 and r.json()["error"]["code"] == "confirmation_required"
    assert (config.PROJECTS_DIR / pid).exists()
    assert client.delete(f"/projects/{pid}", params={"confirm": True}).json() == {"deleted": pid}
    assert not (config.PROJECTS_DIR / pid).exists()


def test_cli_projects_are_listed_and_hidden_folders_are_not(client):
    (config.PROJECTS_DIR / "demo").mkdir()
    (config.PROJECTS_DIR / "_scratch").mkdir()
    ids = [p["id"] for p in client.get("/projects").json()]
    assert "demo" in ids and "_scratch" not in ids
    assert client.get("/projects/demo").json()["state"] == "legacy"
    assert client.get("/projects/_scratch").status_code == 404


def test_openapi_lists_every_endpoint(client):
    paths = client.get("/openapi.json").json()["paths"]
    for p in ("/projects", "/projects/{pid}", "/projects/{pid}/transcribe", "/projects/{pid}/status",
              "/projects/{pid}/pipeline", "/projects/{pid}/motion", "/projects/{pid}/render", "/projects/{pid}/final-qc",
              "/projects/{pid}/result", "/projects/{pid}/cancel"):
        assert p in paths, p
    for gone in ("/projects/{pid}/prompts", "/projects/{pid}/review", "/projects/{pid}/crops/{n}", "/projects/{pid}/qc", "/projects/{pid}/visual", "/projects/{pid}/run"):      # the old prompt / crop / scene-table / video-QC workflow
        assert gone not in paths, gone
    assert "/projects/{pid}/video" in paths                                                                       # the rendered video is still served


def test_rename_changes_only_the_display_name(client):
    a, b = create(client).json()["id"], create(client).json()["id"]
    before = json.loads((config.PROJECTS_DIR / a / "project.json").read_text(encoding="utf-8"))
    other = (config.PROJECTS_DIR / b / "project.json").read_text(encoding="utf-8")
    r = client.patch(f"/projects/{a}", json={"name": "  New   name  "})
    assert r.status_code == 200 and r.json()["name"] == "New name" and r.json()["id"] == a
    after = json.loads((config.PROJECTS_DIR / a / "project.json").read_text(encoding="utf-8"))
    assert {k: v for k, v in after.items() if k != "name"} == {k: v for k, v in before.items() if k != "name"}
    assert (config.PROJECTS_DIR / b / "project.json").read_text(encoding="utf-8") == other
    assert client.patch(f"/projects/{a}", json={"name": "   "}).status_code == 422
    assert client.patch(f"/projects/{a}", json={"name": "x" * 121}).status_code == 422
    assert client.patch("/projects/nope-123", json={"name": "x"}).status_code == 404


def test_delete_removes_only_the_chosen_project(client):
    a, b = create(client).json()["id"], create(client).json()["id"]
    files = sorted(p.name for p in (config.PROJECTS_DIR / b).iterdir())
    assert client.delete(f"/projects/{a}", params={"confirm": True}).status_code == 200
    assert not (config.PROJECTS_DIR / a).exists() and sorted(p.name for p in (config.PROJECTS_DIR / b).iterdir()) == files
    assert client.delete(f"/projects/{a}", params={"confirm": True}).status_code == 404
