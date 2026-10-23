"""Render Video, Stage 13 (backend/render_video.py, the final-render step, the routes). The fixture project is made by the real planner and the real composition builder and approved through the real Stage 12 service;
the renderer is replaced by a function that writes a REAL mp4 (made by ffmpeg, cached in the temp folder) to the temporary output the stage asks for, so the verification, the publishing and the report are exercised on real
encoded files. No Remotion render runs here (test_motion_only_mode renders a fixture project for real through this same path). Run: python -m pytest tests/test_render_video.py -q"""
import importlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

import pytest

from backend import jobs, media_probe as mprobe, pipeline, render, render_video as rv, timeline_approval as ta
from backend import motion_branch, motion_gen_report as mgr, motion_planning as mp, motion_validation as mv, timeline_build as tb

_g = importlib.import_module("test_motion_generation")
_ta = importlib.import_module("test_timeline_approval")
_v = importlib.import_module("test_motion_validation")
_m7 = importlib.import_module("test_m7")
make, client = _g.make, _g.client
A = "16:9"


def encode(path: Path, w=1920, h=1080, frames=2104, fps=30, audio=True, src="testsrc2=size={w}x{h}:rate={fps}", a_src="sine=frequency=440:sample_rate=48000", extra=()) -> Path:
    """A real h264 / aac mp4 made by ffmpeg (moving test pattern and a tone by default). Cached by its parameters in the temp folder."""
    key = abs(hash((w, h, frames, fps, audio, src, a_src, tuple(extra))))
    cached = Path(tempfile.gettempdir()) / f"a2v_test_media_{key}.mp4"
    if not cached.exists():
        tmp = cached.with_name(cached.stem + ".part.mp4")
        cmd = ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", src.format(w=w, h=h, fps=fps)]
        if audio:
            cmd += ["-f", "lavfi", "-i", a_src]
        cmd += ["-frames:v", str(frames), "-t", f"{frames / fps:.4f}", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "38", "-pix_fmt", "yuv420p", *(["-c:a", "aac", "-b:a", "48k"] if audio else []), *extra, str(tmp)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-300:]
        os.replace(tmp, cached)
    shutil.copyfile(cached, path)
    return path


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    d, *_ = make(tmp_path_factory.mktemp("rv"))
    (d / "motion_plan.json").unlink()
    assert pipeline.execute(d, "motion-plan", pipeline.Ctx())["status"] == "ran"
    assert pipeline.execute(d, "motion-build", pipeline.Ctx())["status"] == "ran"
    wav = _m7.wav_bytes(70.13)                                            # an audio as long as the composition: the speech of the fixture lies inside it
    for name in {"audio.wav", json.loads((d / "composition.json").read_text(encoding="utf-8"))["meta"]["audio"]}:
        (d / name).write_bytes(wav)
    return d


@pytest.fixture
def pd(built, tmp_path, monkeypatch):
    d = tmp_path / "p"
    shutil.copytree(built, d)
    for f in ("motion_timeline_validation.json", "motion_validation_exceptions.json", *(tb.names(A)[k] for k in ("timeline", "report", "attempt")), *(ta.names(A)[k] for k in ("history", "review"))):
        (d / f).unlink(missing_ok=True)
    shutil.rmtree(d / "motion_validation_preview", ignore_errors=True)
    monkeypatch.setattr(mv, "blockers", lambda *a, **k: [])
    monkeypatch.setattr(mp, "blockers", lambda *a, **k: None)
    monkeypatch.setattr(mgr, "blockers", lambda *a, **k: None)
    monkeypatch.setattr(motion_branch, "blockers", lambda *a, **k: [])
    return d


def approved(d: Path) -> dict:
    """A project whose current timeline version is approved by the real Stage 12 service (a fixture approval: the real project's approval history is never touched)."""
    _ta.reviewable(d)
    s = ta.state(d, A)
    ta.decide(d, A, _ta.body(s))
    assert ta.state(d, A)["status"] == "approved"
    return ta.state(d, A)


def fake(video: Path, calls: list | None = None, before=None, after=None):
    def f(pdir, preview, cb=None, aspect="16:9", out=None):
        if calls is not None:
            calls.append(out)
        if before:
            before(pdir)
        shutil.copyfile(video, out)
        if cb:
            cb(50.0, 1)
            cb(100.0, 0)
        if after:
            after(pdir)
        return out
    return f


@pytest.fixture
def good(tmp_path):
    return encode(tmp_path / "good.mp4")


def report(d):
    return json.loads((d / "render_report.json").read_text(encoding="utf-8"))


# ---------- the happy path: temp -> verify -> publish -> report ----------
def test_an_approved_timeline_is_rendered_to_a_temp_file_verified_published_and_reported(pd, good, monkeypatch):
    st0 = approved(pd)
    calls, seen = [], []
    monkeypatch.setattr(render, "render", fake(good, calls))
    rep = rv.run(pd, A, progress=lambda p, eta=None: seen.append(p))
    final = pd / "out.mp4"
    assert calls and calls[0].name.startswith("out.rendering-") and calls[0] != final                           # rendered to a temporary file, never straight to the final slot
    assert final.is_file() and not list(pd.glob("out.rendering-*")) and rep["status"] == "completed"
    assert rep["output"]["sha256"] == mprobe.sha256_file(final) and rep["output"]["size_bytes"] == final.stat().st_size
    assert rep["input_fingerprints"]["approved_version"] == st0["fingerprint"] and rep["approval"]["approved_by"] == "Asha" and rep["approval"]["approved_by_source"] == "self_declared"
    assert rep["expected"]["frames"] == rep["observed"]["frame_count"] == 2104 and (rep["observed"]["width"], rep["observed"]["height"]) == (1920, 1080) and rep["observed"]["audio_stream_present"]
    assert all(c["status"] in ("passed", "not_applicable") for c in rep["verification"]) and rep["final_qc_status"] == "pending" and "not been reviewed" in rep["note"]
    assert {w["category"] for w in rep["carried_warnings"]} >= {"review_coverage"}                              # the limitations the approver acknowledged travel on to Final QC
    man = json.loads((pd / "render_manifest.json").read_text(encoding="utf-8"))
    assert man["manifest_fingerprint"] == rv.manifest_fingerprint(man) == rep["input_fingerprints"]["manifest"] and man["approval"]["timeline_fingerprint"] == st0["fingerprint"]
    assert seen and max(seen) < 100 and all(a <= b for a, b in zip(seen, seen[1:]))                              # never 100 % before verification and publishing; the step itself finishes it
    st = rv.state(pd, A)
    assert st["status"] == "completed" and st["output"]["current"] and st["final_qc_status"] == "pending" and st["job"]["status"] == "completed" and st["job"]["output_published"] is True
    assert not (pd / "timeline_approval.json").exists()                                                          # rendering approved nothing and changed no approval


def test_a_second_render_keeps_the_last_good_video_next_to_the_new_one(pd, good, tmp_path, monkeypatch):
    approved(pd)
    monkeypatch.setattr(render, "render", fake(good))
    first = rv.run(pd, A)
    other = encode(tmp_path / "other.mp4", extra=("-metadata", "title=second"))
    monkeypatch.setattr(render, "render", fake(other))
    second = rv.run(pd, A)
    assert second["output"]["sha256"] != first["output"]["sha256"] and mprobe.sha256_file(pd / "out.previous.mp4") == first["output"]["sha256"] and second["previous_output"] == "out.previous.mp4"
    assert len(rv._read(pd, "job", A)["attempts"]) == 2


# ---------- the gate: nothing renders without a current approval ----------
def test_without_a_current_approval_nothing_renders_and_the_renderer_is_never_called(pd, good, monkeypatch):
    _ta.reviewable(pd)                                                                                           # built and reviewable, NOT approved
    calls = []
    monkeypatch.setattr(render, "render", fake(good, calls))
    with pytest.raises(rv.RenderError) as e:
        rv.run(pd, A)
    assert "approved" in str(e.value) and e.value.blockers and calls == [] and not (pd / "out.mp4").exists() and not (pd / "render_report.json").exists()
    assert rv.state(pd, A)["status"] == "failed" and rv.state(pd, A)["blockers"]


def test_an_approval_that_goes_stale_during_the_render_never_publishes_the_video(pd, good, monkeypatch):
    approved(pd)
    monkeypatch.setattr(render, "render", fake(good, after=_ta.touch))                                          # an input changes while the renderer works
    with pytest.raises(rv.RenderError, match="changed"):
        rv.run(pd, A)
    assert not (pd / "out.mp4").exists() and not list(pd.glob("out.rendering-*")) and rv.state(pd, A)["status"] == "failed"


def test_a_stale_approval_blocks_the_start(pd, good, monkeypatch):
    approved(pd)
    _ta.touch(pd)
    monkeypatch.setattr(render, "render", fake(good))
    with pytest.raises(rv.RenderError):
        rv.run(pd, A)
    assert not (pd / "out.mp4").exists()


# ---------- verification: an exit code is not a result ----------
def test_a_renderer_that_reports_success_but_writes_nothing_is_a_failure(pd, monkeypatch):
    approved(pd)
    monkeypatch.setattr(render, "render", lambda *a, **k: k["out"])
    with pytest.raises(rv.RenderError, match="wrote no output"):
        rv.run(pd, A)
    assert not (pd / "out.mp4").exists() and rv.state(pd, A)["job"]["status"] == "failed"


@pytest.mark.parametrize("what", ["garbage", "wrong_size", "too_short", "no_audio", "wrong_fps"])
def test_an_output_that_does_not_match_the_approved_settings_is_never_published_and_the_last_good_one_survives(pd, good, tmp_path, monkeypatch, what):
    approved(pd)
    monkeypatch.setattr(render, "render", fake(good))
    ok = rv.run(pd, A)
    if what == "garbage":
        bad = tmp_path / "bad.mp4"
        bad.write_bytes(b"not a video" * 5000)
    elif what == "wrong_size":
        bad = encode(tmp_path / "bad.mp4", w=640, h=360)
    elif what == "too_short":
        bad = encode(tmp_path / "bad.mp4", frames=900)
    elif what == "no_audio":
        bad = encode(tmp_path / "bad.mp4", audio=False)
    else:
        bad = encode(tmp_path / "bad.mp4", fps=25, frames=1754)
    monkeypatch.setattr(render, "render", fake(bad))
    with pytest.raises(rv.RenderError, match="did not pass verification"):
        rv.run(pd, A)
    assert mprobe.sha256_file(pd / "out.mp4") == ok["output"]["sha256"]                                         # the last good video is untouched
    assert len(list(pd.glob("out.failed-*.mp4"))) == 1 and not list(pd.glob("out.rendering-*")) and report(pd)["output"]["sha256"] == ok["output"]["sha256"]
    st = rv.state(pd, A)
    assert st["status"] == "completed" and st["last_attempt_failed"] and st["last_attempt"]["status"] == "failed" and "verification" in st["last_attempt"]["error"]      # the good video is still the current one; the failed attempt is shown


def test_verify_output_says_what_it_cannot_measure_and_compares_everything_it_can(tmp_path):
    exp = {"width": 1920, "height": 1080, "fps": 30, "frames": 60, "duration_seconds": 2.0, "audio_required": True, "codec": "h264", "container": "mp4"}
    v = encode(tmp_path / "v.mp4", w=1920, h=1080, frames=60, a_src="sine=frequency=300:sample_rate=48000")
    obs, checks = rv.verify_output(v, exp, 2.0)
    assert {c["id"] for c in checks} >= {"readable", "dimensions", "fps", "codec", "frame_count", "duration", "audio_stream", "audio_duration"} and not [c for c in checks if c["status"] == "failed"]
    assert obs["frame_count"] == 60 and obs["audio_stream_present"]
    obs, checks = rv.verify_output(tmp_path / "missing.mp4", exp, 2.0)
    assert obs == {} and checks[0]["status"] == "failed"


# ---------- publishing, cancelling, concurrency, restart ----------
def test_a_failed_publish_puts_the_last_good_video_back_and_keeps_the_verified_temp_file(pd, good, tmp_path, monkeypatch):
    approved(pd)
    monkeypatch.setattr(render, "render", fake(good))
    ok = rv.run(pd, A)
    other = encode(tmp_path / "other.mp4", extra=("-metadata", "title=third"))
    monkeypatch.setattr(render, "render", fake(other))
    real = os.replace

    def failing(src, dst):
        if str(dst).endswith("out.mp4") and ".rendering-" in str(src):
            raise OSError("disk error (test)")
        return real(src, dst)
    monkeypatch.setattr(rv.os, "replace", failing)
    with pytest.raises(rv.RenderError, match="could not be published"):
        rv.run(pd, A)
    assert mprobe.sha256_file(pd / "out.mp4") == ok["output"]["sha256"] and len(list(pd.glob("out.rendering-*.mp4"))) == 1       # the good video is back, the verified new file is kept for recovery
    assert report(pd)["output"]["sha256"] == ok["output"]["sha256"]


def test_cancelling_stops_the_render_and_publishes_nothing(pd, good, monkeypatch):
    approved(pd)
    jobs._jobs[pd.name] = jobs.Job(pd.name, "build", ("render-final",), pipeline.Ctx())
    jobs._jobs[pd.name].cancel.set()
    monkeypatch.setattr(render, "render", fake(good))
    try:
        with pytest.raises(rv.RenderError, match="cancelled"):
            rv.run(pd, A)
    finally:
        jobs._jobs.pop(pd.name, None)
    assert not (pd / "out.mp4").exists() and not list(pd.glob("out.rendering-*")) and rv.state(pd, A)["status"] == "cancelled"


def test_two_renders_at_once_are_refused(pd, good, monkeypatch):
    approved(pd)
    lock = rv._running.setdefault(str(pd.resolve()), threading.Lock())
    lock.acquire()
    try:
        with pytest.raises(rv.RenderError, match="already running"):
            rv.run(pd, A)
    finally:
        lock.release()


def test_a_job_that_says_it_is_rendering_while_nothing_runs_is_interrupted_and_a_leftover_file_is_not_a_result(pd, good, monkeypatch):
    approved(pd)
    rv._job(pd, A, "deadbeef", status="rendering", phase="rendering", frames_total=2104, event="started")
    shutil.copyfile(good, pd / "out.rendering-deadbeef.mp4")
    st = rv.state(pd, A)
    assert st["status"] == "interrupted" and not st["output"]["published"] and rv.candidate(pd, A) is None
    monkeypatch.setattr(render, "render", fake(good))
    rep = rv.run(pd, A)                                                                                          # a new run removes the abandoned temp file (this stage's own naming only) and succeeds
    assert rep["status"] == "completed" and not list(pd.glob("out.rendering-deadbeef*"))


def test_a_video_without_a_render_report_is_never_a_candidate_and_a_changed_one_is_not_current(pd, good, monkeypatch):
    approved(pd)
    shutil.copyfile(good, pd / "out.mp4")                                                                         # a video made by hand / before Stage 13
    assert rv.state(pd, A)["status"] == "unverified_output" and rv.candidate(pd, A) is None
    monkeypatch.setattr(render, "render", fake(good))
    rv.run(pd, A)
    assert rv.state(pd, A)["status"] == "completed"
    with (pd / "out.mp4").open("ab") as f:
        f.write(b"x")                                                                                            # the published bytes change
    assert rv.candidate(pd, A) is None and rv.state(pd, A)["status"] != "completed"


def test_a_new_approved_version_makes_the_old_video_stale(pd, good, monkeypatch):
    approved(pd)
    monkeypatch.setattr(render, "render", fake(good))
    rv.run(pd, A)
    _ta.touch(pd)                                                                                                # the composition (and so the version) changes after the render
    st = rv.state(pd, A)
    assert st["status"] in ("stale", "not_ready") and not st["output"]["current"] and st["final_qc_status"] == "waiting_for_render"


# ---------- configuration ----------
def test_unsupported_settings_stop_the_render_by_name(pd):
    exp = rv.expected(pd, A)
    assert rv.validate_config(pd, A, exp) == []
    assert any("not supported" in w for w in rv.validate_config(pd, "4:3", exp))
    assert any("profile" in w for w in rv.validate_config(pd, "9:16", exp))                                       # a 16:9 composition under the 9:16 profile
    assert any("fps" in w for w in rv.validate_config(pd, A, {**exp, "fps": 500}))
    assert any("no duration" in w for w in rv.validate_config(pd, A, {**exp, "frames": 0}))
    assert exp["frames"] == mp.fr(exp["composition_duration_seconds"], exp["fps"])                              # the renderer's own frame rule, not an invented one


# ---------- the step and the API ----------
def test_the_final_render_step_runs_the_stage_for_motion_only_projects(pd, good, monkeypatch):
    approved(pd)
    monkeypatch.setattr(render, "render", fake(good))
    r = pipeline.execute(pd, "render-final", pipeline.Ctx())
    assert r["status"] == "ran" and "verified and published" in r["msg"] and "playback decision is pending" in r["msg"] and (pd / "render_report.json").exists()


def test_the_api_reads_the_render_state_and_cancel_needs_a_running_render(client):
    c = client
    pid, pdir = _v.api_project(c)
    st = c.get(f"/projects/{pid}/render-video").json()
    assert st["status"] == "not_ready" and st["final_qc_status"] == "waiting_for_render" and st["blockers"] and not st["output"]["published"]
    assert c.post(f"/projects/{pid}/render-video/cancel").status_code == 409
    r = c.post(f"/projects/{pid}/render")
    assert r.status_code == 409 and r.json()["error"]["code"] == "render_not_allowed"                           # the route's own gate, before any job exists
    assert not (pdir / "out.mp4").exists() and not (pdir / "render_manifest.json").exists()
