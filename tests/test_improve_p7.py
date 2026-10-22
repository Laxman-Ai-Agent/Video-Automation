"""Phase 7 of improvement/MASTER_PLAN.md: safe resume (cache hit, downstream invalidation, failed-stage resume, idempotent retry), the resume explainer,
and Cancel that really stops a running step (A2V_CANCEL). The real executor and job runner are used with small fake steps."""
import json
import subprocess
import sys
import time

import pytest

from backend import config, pipeline, procs, resume, store
from backend.pipeline import Ctx, Step, StepError, digest, run_chain

CHAIN = ("t_a", "t_b", "t_c")


@pytest.fixture
def proj(tmp_path, monkeypatch):
    """A project folder with three fake steps a -> b -> c; every run is counted, step b can be told to fail."""
    root = tmp_path / "repo"
    (root / "projects").mkdir(parents=True)
    monkeypatch.setattr(config, "PROJECT_ROOT", root)
    monkeypatch.setattr(config, "PROJECTS_DIR", root / "projects")
    for f in ("A2V_FINGERPRINTS", "A2V_CANCEL"):
        monkeypatch.delenv(f, raising=False)
    pdir = store.create("p7")
    (pdir / "in.txt").write_text("hello", encoding="utf-8")
    calls = {"t_a": 0, "t_b": 0, "t_c": 0, "fail_b": False}

    def make(name, src, dst, fn):
        def run(p, ctx):
            calls[name] += 1
            if name == "t_b" and calls["fail_b"]:
                raise RuntimeError("b broke")
            (p / dst).write_text(fn((p / src).read_text(encoding="utf-8")), encoding="utf-8")
            return "ok"
        monkeypatch.setitem(pipeline.STEPS, name, Step(name, (src,), lambda p, d=dst: [p / d], lambda p, c, s=src: digest(p / s), run, f"make {src}"))
    make("t_a", "in.txt", "a.txt", lambda s: s + "-a")
    make("t_b", "a.txt", "b.txt", lambda s: s.upper())
    make("t_c", "b.txt", "c.txt", lambda s: s + "!")
    return pdir, calls


def statuses(results):
    return [r["status"] for r in results]


def test_unchanged_input_is_a_cache_hit_and_a_retry_changes_nothing(proj):
    pdir, calls = proj
    assert statuses(run_chain(pdir, CHAIN, "t")) == ["ran", "ran", "ran"]
    before = {f: (pdir / f).read_bytes() for f in ("a.txt", "b.txt", "c.txt")}
    assert statuses(run_chain(pdir, CHAIN, "t")) == ["fresh", "fresh", "fresh"]                 # nothing runs again
    assert statuses(run_chain(pdir, CHAIN, "t")) == ["fresh", "fresh", "fresh"]                 # and again: idempotent
    assert calls == {"t_a": 1, "t_b": 1, "t_c": 1, "fail_b": False}
    assert before == {f: (pdir / f).read_bytes() for f in before}
    assert sorted(p.name for p in pdir.iterdir() if p.suffix == ".txt" and p.name != "log.txt") == ["a.txt", "b.txt", "c.txt", "in.txt"]      # no duplicate or leftover outputs


def test_changing_an_upstream_input_invalidates_everything_downstream(proj):
    pdir, calls = proj
    run_chain(pdir, CHAIN, "t")
    (pdir / "in.txt").write_text("changed", encoding="utf-8")
    assert statuses(run_chain(pdir, CHAIN, "t")) == ["ran", "ran", "ran"]
    assert (pdir / "c.txt").read_text(encoding="utf-8") == "CHANGED-A!"                          # the final output follows the new input, never the old one
    assert calls["t_c"] == 2


def test_only_the_affected_part_reruns(proj):
    pdir, calls = proj
    run_chain(pdir, CHAIN, "t")
    (pdir / "a.txt").write_text("hello-a", encoding="utf-8")                                      # same content as before: b and c must not rerun
    assert statuses(run_chain(pdir, CHAIN, "t"))[1:] == ["fresh", "fresh"]
    assert calls["t_b"] == 1


def test_failed_stage_resume_reuses_finished_work_and_never_runs_later_stages(proj):
    pdir, calls = proj
    calls["fail_b"] = True
    with pytest.raises(StepError):
        run_chain(pdir, CHAIN, "t")
    assert calls == {"t_a": 1, "t_b": 1, "t_c": 0, "fail_b": True}                               # c never ran after b failed
    assert not (pdir / "c.txt").exists()
    job = json.loads((pdir / "job.json").read_text(encoding="utf-8"))
    assert job["step"] == "t_b" and job["error"]                                                    # the failure is recorded, not hidden
    assert json.loads((pdir / "timings.json").read_text(encoding="utf-8"))["steps"]["t_b"]["status"] == "failed"
    calls["fail_b"] = False
    assert statuses(run_chain(pdir, CHAIN, "t")) == ["fresh", "ran", "ran"]                       # resumes at b: a is reused
    assert calls["t_a"] == 1
    assert json.loads((pdir / "job.json").read_text(encoding="utf-8"))["error"] is None


def test_a_failed_rerun_never_leaves_stale_output_looking_fresh(proj):
    pdir, calls = proj
    run_chain(pdir, CHAIN, "t")
    (pdir / "in.txt").write_text("v2", encoding="utf-8")
    calls["fail_b"] = True
    with pytest.raises(StepError):
        run_chain(pdir, CHAIN, "t")
    rows = {r["step"]: r for r in resume.state(pdir, CHAIN)}
    assert rows["t_b"]["state"] == "stale"                                                          # old b.txt exists, but it is from the old input
    assert rows["t_c"]["state"] == "recheck"                                                        # c looks unchanged only against OLD data: not called fresh
    assert resume.resume_point(list(rows.values()))["step"] == "t_b"
    calls["fail_b"] = False
    run_chain(pdir, CHAIN, "t")
    assert (pdir / "c.txt").read_text(encoding="utf-8") == "V2-A!"


def test_resume_explains_each_reason(proj):
    pdir, calls = proj
    assert [r["state"] for r in resume.state(pdir, CHAIN)] == ["stale", "recheck", "recheck"] or [r["state"] for r in resume.state(pdir, CHAIN)] == ["stale", "blocked", "blocked"]
    run_chain(pdir, CHAIN, "t")
    assert [r["state"] for r in resume.state(pdir, CHAIN)] == ["fresh"] * 3
    (pdir / "in.txt").write_text("x", encoding="utf-8")
    rows = resume.state(pdir, CHAIN)
    assert rows[0]["state"] == "stale" and "changed" in rows[0]["reason"] and [r["state"] for r in rows[1:]] == ["recheck", "recheck"]
    (pdir / "in.txt").write_text("hello", encoding="utf-8")
    (pdir / "c.txt").rename(pdir / "c.moved")                                                       # output missing (moved, never deleted)
    assert resume.state(pdir, CHAIN)[2]["reason"] == "its output is missing"
    (pdir / "c.moved").rename(pdir / "c.txt")
    (pdir / ".build_state.json").write_text("{ not json", encoding="utf-8")                          # a damaged state file: nothing is trusted
    assert resume.state(pdir, CHAIN)[0]["state"] == "stale"


def test_flag_makes_settings_and_logic_version_part_of_the_cache(proj, monkeypatch):
    pdir, calls = proj
    monkeypatch.setitem(config.STAGE_VERSIONS, "t_a", 1)
    monkeypatch.setitem(config.STAGE_CONFIG_KEYS, "t_a", ("MIN_SHOT_SEC",))
    run_chain(pdir, CHAIN, "t")                                                                     # flag OFF: recorded plainly
    monkeypatch.setitem(config.STAGE_VERSIONS, "t_a", 2)
    assert statuses(run_chain(pdir, CHAIN, "t")) == ["fresh"] * 3                                  # off: a version bump changes nothing (old caches stay valid)
    monkeypatch.setenv("A2V_FINGERPRINTS", "1")
    assert statuses(run_chain(pdir, CHAIN, "t"))[0] == "ran"                                        # turning the flag on rebuilds once, on purpose
    assert statuses(run_chain(pdir, CHAIN, "t")) == ["fresh"] * 3
    monkeypatch.setitem(config.STAGE_VERSIONS, "t_a", 3)
    assert statuses(run_chain(pdir, CHAIN, "t"))[0] == "ran"                                        # the stage logic changed: its cache is not reused
    monkeypatch.setattr(config, "MIN_SHOT_SEC", 2.5)
    assert statuses(run_chain(pdir, CHAIN, "t"))[0] == "ran"                                        # a setting it depends on changed
    assert statuses(run_chain(pdir, CHAIN, "t")) == ["fresh"] * 3


# ---------- cancel ----------
def test_procs_kill_stops_a_running_process_and_only_that():
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        procs.register("one", p)
        assert procs.kill("one") is True
        assert p.wait(timeout=10) != 0
        assert procs.kill("one") is False                                                           # already gone
        assert procs.kill("nobody") is False
        assert other.poll() is None                                                                 # a process of another project is untouched
    finally:
        other.kill()
        procs.unregister("one", p)


def _wait(cond, timeout=15.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if cond():
            return True
        time.sleep(0.05)
    return False


def test_kill_takes_down_the_whole_process_tree_started_through_a_shell(tmp_path):
    pidfile = tmp_path / "child.pid"
    code = f"import os,time; open(r'{pidfile}','w').write(str(os.getpid())); time.sleep(60)"
    proc = subprocess.Popen(f'"{sys.executable}" -c "{code}"', shell=True)            # cmd.exe -> python: like cmd -> node in render.py
    try:
        assert _wait(pidfile.exists)
        child = int(pidfile.read_text())
        procs.register("tree", proc)
        assert procs.kill("tree") is True
        alive = lambda: str(child) in subprocess.run(["tasklist", "/FI", f"PID eq {child}", "/NH"], capture_output=True, text=True).stdout.split()
        assert _wait(lambda: not alive(), 10), "the grandchild process is still running"
    finally:
        procs.unregister("tree", proc)
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
