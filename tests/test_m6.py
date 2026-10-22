"""M6 regression tests: render freshness, single job.json writer, step registry, timings.
Run: python -m pytest tests/test_m6.py -q  (project .venv). No Remotion/Whisper/CLIP is started: render is faked."""
import json
import re
from pathlib import Path

import pytest

from backend import config, pipeline
from backend.pipeline import CHAINS, STEPS, Ctx, StepError, execute, run_chain

COMP = {"meta": {"audio": "audio.wav", "duration": 5, "fps": 30, "width": 1920, "height": 1080},
        "scenes": [{"id": 1, "start": 0, "end": 5, "pattern": "hero_text",
                    "camera": {"move": "push-in", "from": 1.0, "to": 1.1, "focus": [0.5, 0.5]},
                    "layers": [{"type": "image", "slot": "s01_0", "file": "projects/p1/s01_0.png", "z": 1},
                               {"type": "text", "text": "Hello", "z": 2}]}]}


@pytest.fixture
def env(tmp_path, monkeypatch):
    """A fake repo root with a Remotion folder and one project; config points at it."""
    root = tmp_path / "repo"
    (root / "VIDEO_ENGINE" / "remotion" / "src").mkdir(parents=True)
    (root / "VIDEO_ENGINE" / "remotion" / "public" / "geo").mkdir(parents=True)
    (root / "VIDEO_ENGINE" / "remotion" / "public" / "projects" / "p1").mkdir(parents=True)
    (root / "VIDEO_ENGINE" / "remotion" / "src" / "Main.tsx").write_text("export const Main = 1;")
    (root / "VIDEO_ENGINE" / "remotion" / "remotion.config.ts").write_text("cfg")
    (root / "VIDEO_ENGINE" / "remotion" / "package.json").write_text("{}")
    (root / "VIDEO_ENGINE" / "remotion" / "public" / "geo" / "w.json").write_text("{}")
    (root / "VIDEO_ENGINE" / "remotion" / "public" / "projects" / "p1" / "s01_0.png").write_bytes(b"img-v1")
    pdir = root / "projects" / "p1"
    (pdir / "assets" / "raw").mkdir(parents=True)
    (pdir / "assets" / "raw" / "a.jpg").write_bytes(b"raw-v1")
    (pdir / "audio.wav").write_bytes(b"audio-v1")
    (pdir / "composition.json").write_text(json.dumps(COMP))
    (pdir / "prompts_map.json").write_text(json.dumps({"prompts": []}))
    (pdir / "match_report.json").write_text(json.dumps({"matches": []}))
    monkeypatch.setattr(config, "PROJECT_ROOT", root)
    monkeypatch.setattr(config, "PROJECTS_DIR", root / "projects")
    monkeypatch.setattr(pipeline, "_REMOTION", root / "VIDEO_ENGINE" / "remotion")          # the render inputs are read from the Remotion folder (config.REMOTION_DIR): the fake one here
    return pdir


@pytest.fixture
def fake_render(monkeypatch):
    """Stands in for Remotion: stages audio and writes the mp4 like the real render.py does (outputs!)."""
    calls = []

    def fake(pdir, preview, on_progress=None):
        from backend.render import output_path, stage_audio
        calls.append("preview" if preview else "final")
        stage_audio(pdir)
        if on_progress:
            on_progress(50, 10)
        out = output_path(pdir, preview)
        out.write_bytes(b"mp4-%d" % len(calls))
        return out

    monkeypatch.setattr("backend.render.render", fake)
    monkeypatch.setattr(pipeline.shutil, "which", lambda t: "/fake/" + t)   # node/npx not needed
    return calls


def edit_comp(pdir: Path, fn):
    c = json.loads((pdir / "composition.json").read_text())
    fn(c)
    (pdir / "composition.json").write_text(json.dumps(c))


# ---------- 1. render freshness ----------
def test_render_freshness_first_run_skip_then_rerender_on_real_inputs(env, fake_render):
    """Through the preview render: a final render always goes through the timeline approval and Stage 13 (tests/test_render_video.py); both use the same fingerprint rules."""
    pdir, ctx, step = env, Ctx(preview=True), "render-preview"
    assert execute(pdir, step, ctx)["status"] == "ran"
    assert execute(pdir, step, ctx)["status"] == "fresh"          # identical second run = skipped
    assert fake_render == ["preview"]
    root = pipeline._REMOTION

    # files render itself creates are NOT inputs: touching them must not invalidate
    (root / "public" / "audio.wav").write_bytes(b"someone-edited-the-staged-copy")
    assert execute(pdir, step, ctx)["status"] == "fresh"

    changes = {
        "composition text": lambda: edit_comp(pdir, lambda c: c["scenes"][0]["layers"][1].update(text="Changed")),
        "referenced image": lambda: (root / "public" / "projects" / "p1" / "s01_0.png").write_bytes(b"img-v2"),
        "project audio": lambda: (pdir / "audio.wav").write_bytes(b"audio-v2"),
        "remotion source": lambda: (root / "src" / "Main.tsx").write_text("export const Main = 2;"),
        "remotion config": lambda: (root / "remotion.config.ts").write_text("cfg2"),
    }
    n = len(fake_render)
    for label, change in changes.items():
        change()
        assert execute(pdir, step, ctx)["status"] == "ran", label
        assert len(fake_render) == n + 1, label
        assert execute(pdir, step, ctx)["status"] == "fresh", label + " (fresh again)"
        n += 1

    (pdir / "out_preview.mp4").unlink()                                      # output missing = render again
    assert execute(pdir, step, ctx)["status"] == "ran"


def test_render_mode_is_part_of_the_fingerprint(env, fake_render):
    assert execute(env, "render-preview", Ctx(preview=True))["status"] == "ran"
    assert execute(env, "render-preview", Ctx(preview=True))["status"] == "fresh"
    assert pipeline.render_inputs(env, "preview") != pipeline.render_inputs(env, "final")       # the other mode has its own fingerprint
    with pytest.raises(StepError, match="approved"):
        execute(env, "render-final", Ctx())                                  # a final render without an approved timeline never starts


# ---------- render command (regression: --every-nth-frame made the audio play at 2x speed) ----------
def test_render_command_construction():
    from backend.render import build_command
    pre, fin = build_command(Path("p"), True), build_command(Path("p"), False)
    assert pre[:5] == fin[:5] == ["npx", "remotion", "render", "src/index.ts", "Main"]
    assert "--scale=0.5" in pre                                               # preview = spatial scaling
    assert not any(a.startswith("--scale") for a in fin)                      # final is full size
    for cmd in (pre, fin):                                                    # never drop frames, never change fps
        assert not any(a.startswith("--every-nth-frame") for a in cmd), cmd
        assert not any(a.startswith("--fps") for a in cmd), cmd
    assert pre[5].endswith("out_preview.mp4") and fin[5].endswith("out.mp4")
    for cmd in (pre, fin):                                                    # composition.json is the only props file
        assert any(a.startswith("--props=") and a.endswith("composition.json") for a in cmd)


def test_render_flags_are_part_of_the_fingerprint(env):
    from backend.render import render_flags
    pre = STEPS["render-preview"].fingerprint(env, Ctx())
    assert pre == pipeline.render_inputs(env, "preview " + " ".join(render_flags(True)))
    assert pre != pipeline.render_inputs(env, "preview")                      # flags change -> output goes stale
    assert STEPS["render-final"].fingerprint(env, Ctx()) == pipeline.render_inputs(env, "final " + " ".join(render_flags(False)))


# ---------- fingerprints never depend on the step's own outputs ----------
def test_fingerprints_ignore_generated_outputs(env):
    ctx = Ctx()
    root = pipeline._REMOTION
    fp = STEPS["render-final"].fingerprint(env, ctx)
    (env / "out.mp4").write_bytes(b"x")                                               # render outputs
    (root / "public" / "audio.wav").write_bytes(b"staged")
    assert STEPS["render-final"].fingerprint(env, ctx) == fp
    edit_comp(env, lambda c: c["scenes"][0]["layers"][1].update(text="x"))            # a real change of its input
    assert STEPS["render-final"].fingerprint(env, ctx) != fp


# ---------- 2. one job.json writer, one schema ----------
JOB_KEYS = {"step", "percent", "error", "eta_s"}


WRITE_MARKERS = re.compile(r"write_text|write_bytes|\.write\(|open\([^)]*[\"']w|json\.dump\(|os\.replace|shutil\.(copy|move)|\.touch\(|\.rename\(")


def job_json_writes(source: str) -> list[str]:
    """Lines that WRITE job.json (reading it, e.g. in the API status code, is fine)."""
    return [ln.strip() for ln in source.splitlines() if re.search(r"""["']job\.json["']""", ln) and WRITE_MARKERS.search(ln)]


def test_job_json_write_detector():
    assert job_json_writes('(pdir / "job.json").write_text(json.dumps(x))')
    assert job_json_writes("open(pdir / 'job.json', 'w')")
    assert not job_json_writes('json.loads((pdir / "job.json").read_text(encoding="utf-8"))')
    assert not job_json_writes('if (pdir / "job.json").exists():')


def test_only_pipeline_writes_job_json():
    owner = Path(config.PROJECT_ROOT) / "VIDEO_ENGINE" / "pipeline" / "legacy_pipeline_adapter.py"
    for d in ("UI/backend", "UI/backend/routes", "VIDEO_ENGINE/pipeline", "VIDEO_ENGINE/stages", "SYSTEM/core"):
        for f in Path(config.PROJECT_ROOT, d).glob("*.py"):
            if f != owner:
                assert not job_json_writes(f.read_text(encoding="utf-8", errors="replace")), f
    assert job_json_writes(owner.read_text(encoding="utf-8"))   # the owner


def test_job_json_schema_and_progress_route(env, monkeypatch):
    seen = []

    def run(pdir, ctx):
        ctx.progress(40, eta=12.4)
        seen.append(json.loads((pdir / "job.json").read_text()))
        return "done"

    def run_stop(pdir, ctx):
        raise StepError("fix me")

    pipeline.step("t-ok")(run)
    pipeline.step("t-stop")(run_stop)
    try:
        execute(env, "t-ok", Ctx())
        assert set(seen[0]) == JOB_KEYS and seen[0]["step"] == "t-ok" and seen[0]["percent"] == 40 and seen[0]["eta_s"] == 12
        done = json.loads((env / "job.json").read_text())
        assert set(done) == JOB_KEYS and done["percent"] == 100 and done["error"] is None
        with pytest.raises(StepError):
            execute(env, "t-stop", Ctx())
        err = json.loads((env / "job.json").read_text())
        assert set(err) == JOB_KEYS and err["error"] == "fix me"
        # transcribe progress arrives through the pipeline callback, not through its own job.json
        got = []

        def fake_transcribe(pdir, progress=None):
            progress(25)
            got.append(json.loads((pdir / "job.json").read_text()))
            from backend.transcribe import Transcript
            return Transcript(language="te", duration=1, segments=[])
        monkeypatch.setattr("backend.transcribe.transcribe", fake_transcribe)
        monkeypatch.setattr(pipeline.shutil, "which", lambda t: "/fake/" + t)
        execute(env, "transcribe", Ctx())
        assert set(got[0]) == JOB_KEYS and got[0]["step"] == "transcribe" and got[0]["percent"] == 25
    finally:
        STEPS.pop("t-ok", None)
        STEPS.pop("t-stop", None)


# ---------- 3. registry ----------
def test_registry_is_complete_and_used_by_chains():
    assert list(STEPS) == ["transcribe", "refine", "cuts", "segment", "plan-input", "prompts",
                           "motion-plan", "motion-build", "motion-plan-9x16", "motion-build-9x16", "motion-validate", "motion-validate-9x16",      # the motion branch
                           "motion-validation", "motion-validation-preview", "motion-validation-9x16", "motion-validation-preview-9x16",       # Stage 10: Motion & Timeline Validation (read-only) and its optional preview stills
                               "timeline-build", "timeline-build-9x16",       # Stage 11: Timeline Build (timeline.json + its report)
                               "timeline-approve", "timeline-approve-9x16",   # Stage 12: Timeline Approval, decided by the LLM review
                               "final-qc", "final-qc-9x16",       # Stage 14: Final QC (reads the verified rendered video)
                           "render-preview", "render-final", "render-preview-9x16", "render-final-9x16"]   # 9x16 steps: optional vertical variant (M9)
    for name, s in STEPS.items():
        assert s.name == name and callable(s.run) and callable(s.outputs)
        assert isinstance(s.requires, tuple)
        if s.outputs(Path("x")):                      # a skippable step must define a fingerprint
            assert callable(s.fingerprint), name
    for chain, names in CHAINS.items():
        assert all(n in STEPS for n in names), chain
    assert CHAINS["build"][-1] == "render-final" and CHAINS["build-preview"][-1] == "render-preview"


def test_missing_requirements_give_a_hint_and_chain_stops(env):
    with pytest.raises(StepError, match="run /plan"):
        execute(env, "prompts", Ctx())                # no scene_plan.json in the fake project
    with pytest.raises(StepError):
        run_chain(env, ["prompts", "segment"], "t", Ctx())          # prompts stops the chain: segment never runs
    last = json.loads((env / "timings.json").read_text())["last_build"]
    assert "segment" not in last["steps"]


# ---------- 5. timings ----------
def test_timings_record_runs_without_losing_the_last_real_duration(env, fake_render):
    run_chain(env, ["render-preview"], "build-preview", Ctx(preview=True))
    run_chain(env, ["render-preview"], "build-preview", Ctx(preview=True))         # second one is fresh
    t = json.loads((env / "timings.json").read_text())
    s = t["steps"]["render-preview"]
    assert set(s) == {"seconds", "status", "runs", "total_seconds", "last_run"}
    assert s["runs"] == 1 and s["status"] == "fresh" and s["total_seconds"] >= s["seconds"] >= 0
    lb = t["last_build"]
    assert lb["label"] == "build-preview" and lb["steps"]["render-preview"]["status"] == "fresh" and "total_seconds" in lb
    edit_comp(env, lambda c: c["scenes"][0]["layers"][1].update(text="again"))
    run_chain(env, ["render-preview"], "build-preview", Ctx(preview=True))
    s2 = json.loads((env / "timings.json").read_text())["steps"]["render-preview"]
    assert s2["runs"] == 2 and s2["status"] == "ran"
