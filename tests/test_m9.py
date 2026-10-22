"""M9 tests: transition audit (Phase 1). Run: python -m pytest tests/test_m9.py -q  (with the project .venv)"""
import errno
import json
import math
import re
import shutil
import struct
import wave
from collections import namedtuple
from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError

from backend import audio_utils, config, diagnose, pipeline, plan_checks, render
from backend.diagnose import UserProblem, check_disk, explain, explain_text
from backend.models import Composition, MatchItem, MatchReport, ScenePlan
from backend.pipeline import Ctx, Step, StepError, execute
from backend.transition_audit import BY_MOOD, KNOWN, audit, mood_key

SAMPLE = Path(__file__).parent / "fixtures" / "plan_sample"
needs_ffmpeg = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg/ffprobe not on PATH")


def sample():
    return (json.loads((SAMPLE / "scene_plan.json").read_text(encoding="utf-8")),
            json.loads((SAMPLE / "composition.json").read_text(encoding="utf-8")))


def run(plan: dict, comp: dict, types: list | None = None, moods: list | None = None):
    """Audit the sample with the given transition types / moods per scene (None keeps the sample's)."""
    for i, c in enumerate(comp["scenes"]):
        if types is not None:
            c["transition_out"] = {"type": types[i], "dur": 0.6} if types[i] else None
        if moods is not None:
            plan["scenes"][i]["mood"] = moods[i]
    return audit(ScenePlan.model_validate(plan), Composition.model_validate(comp))


def test_the_sample_plan_is_clean():
    rows, E, W = run(*sample())
    assert (E, W) == ([], [])
    assert rows[-1].type is None                                  # the last scene has no exit transition
    assert all(r.fits is not False for r in rows[:-1])            # a mood the table does not know is not judged (None), never a misfit


def test_adjacent_repeat_is_an_error_but_a_gap_resets_it():
    n = len(sample()[1]["scenes"])
    types = ["fade", "fade"] + ["blur", "wipe", "flip", "slide", "particle", "match-move"][: n - 3] + [None]
    _, E, _ = run(*sample(), types=types)
    assert E == ["scene 2: transition 'fade' repeats previous"]
    types[1] = None                                               # a hard cut between the two fades is not a repeat
    _, E, W = run(*sample(), types=types)
    assert E == [] and any("hard cut" in w for w in W)


def test_unknown_transition_is_an_error():
    n = len(sample()[1]["scenes"])
    _, E, _ = run(*sample(), types=["spin"] + [None] * (n - 1))
    assert E == ["scene 1: unknown transition 'spin' (renderer would fall back to fade)"]


def test_off_mood_warns_and_the_entering_scene_can_justify_it():
    n = len(sample()[1]["scenes"])
    types = ["fade", "wipe"] + [None] * (n - 2)
    moods = ["calm"] * n
    _, E, W = run(*sample(), types=types, moods=moods)
    assert E == [] and any(w.startswith("scene 2: 'wipe' does not fit mood 'calm'") for w in W)
    moods[2] = "tense"                                            # scene 3 (entered) is tense and wipe suits tense
    _, _, W = run(*sample(), types=types, moods=moods)
    assert not any(w.startswith("scene 2:") and "does not fit" in w for w in W)


def test_a_mood_the_table_does_not_know_is_not_judged_as_calm():
    n = len(sample()[1]["scenes"])
    types = ["fade", "slide"] + [None] * (n - 2)
    moods = ["calm", "busy, habitual"] + ["wonder"] * (n - 2)     # free text with no table mood, like the planner writes
    rows, _, W = run(*sample(), types=types, moods=moods)
    assert not any("does not fit" in w for w in W)                # 'slide' was flagged against calm before
    assert rows[1].fits is None                                   # nothing to judge, so no verdict
    moods[2] = "tense"                                            # a known neighbour can still justify the transition, but cannot condemn it
    rows, _, W = run(*sample(), types=["fade", "wipe"] + [None] * (n - 2), moods=moods)
    assert rows[1].fits is True                                   # wipe suits tense, the scene entered
    rows, _, W = run(*sample(), types=["fade", "fade"] + [None] * (n - 2), moods=moods)
    assert rows[1].fits is None and not any("does not fit" in w for w in W)
    moods[1] = "calm"                                             # both moods known: judged as before
    rows, _, W = run(*sample(), types=["fade", "slide"] + [None] * (n - 2), moods=moods)
    assert rows[1].fits is False and any(w.startswith("scene 2: 'slide' does not fit mood 'calm'") for w in W)


def test_last_scene_without_a_transition_is_not_a_hard_cut():
    n = len(sample()[1]["scenes"])
    distinct = ["fade", "blur", "wipe", "flip", "slide", "particle", "match-move", "zoom-through", "light-leak"]
    _, _, W = run(*sample(), types=distinct[: n - 1] + [None], moods=["calm"] * n)
    assert not any("hard cut" in w for w in W)                    # every scene but the last has one; the last needs none
    _, _, W = run(*sample(), types=distinct[: n - 2] + [None, None], moods=["calm"] * n)
    assert [w for w in W if "hard cut" in w] == [f"scene {n - 1}: no transition into scene {n} (hard cut)"]


def test_low_variety_warns():
    n = len(sample()[1]["scenes"])
    types = ["fade", "blur", "fade", "blur", "fade", "blur"] + [None] * (n - 6)
    _, E, W = run(*sample(), types=types, moods=["calm"] * n)
    assert E == []
    assert any(w.startswith("variety: only 2 different transitions in 6") for w in W)
    assert any(w.startswith("variety: 'fade' used 3x") for w in W)


def test_few_transitions_are_not_judged_for_variety():
    n = len(sample()[1]["scenes"])
    _, _, W = run(*sample(), types=["fade", "blur", "fade", "blur"] + [None] * (n - 4), moods=["calm"] * n)
    assert not any(w.startswith("variety") for w in W)


def test_mood_rule_matches_the_renderer():
    assert mood_key("powerful, majestic") == "majestic"
    assert mood_key("UPBEAT, practical") == "calm"                # no table mood in the text: calm, like pickTransition
    assert mood_key("sad and tense") == "tense"                   # first mood in TABLE order that appears, as in pickTransition


def test_shared_table_and_known_types_agree_with_remotion():
    ts = (config.PROJECT_ROOT / "VIDEO_ENGINE/remotion/src/transitions/index.ts").read_text(encoding="utf-8")
    assert "by_mood.json" in ts and "BY_MOOD" in ts and "calm: [" not in ts       # one table, not two
    assert len(KNOWN) == 11
    for mood, types in BY_MOOD.items():
        assert mood == mood.lower() and set(types) <= KNOWN, mood
        assert len(set(types)) == len(types) >= 2, mood           # a mood needs two options or pickTransition could repeat


def test_plan_checks_reports_the_audit(tmp_path):
    work = tmp_path / "p"
    shutil.copytree(SAMPLE, work)
    comp = json.loads((work / "composition.json").read_text(encoding="utf-8"))
    comp["scenes"][1]["transition_out"] = dict(comp["scenes"][0]["transition_out"])
    (work / "composition.json").write_text(json.dumps(comp), encoding="utf-8")
    E, _ = plan_checks.check(work)
    assert re.search(r"scene 2: transition '[\w-]+' repeats previous", "\n".join(E))
    E2, _ = plan_checks.check(SAMPLE)
    assert E2 == []


# ---------- Task 11: error handling ----------
def wav(path: Path, seconds: float = 2.0, amp: float = 0.0) -> Path:
    """16 kHz mono 440 Hz tone; amp 0 = digital silence."""
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"".join(struct.pack("<h", int(amp * 32767 * math.sin(2 * math.pi * 440 * i / 16000))) for i in range(int(16000 * seconds))))
    return path


def png(path: Path, size=(64, 36)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, "teal").save(path)
    return path


@pytest.fixture
def env(tmp_path, monkeypatch):
    """A fake repo root with one project p1 and a Remotion public folder; config points at it."""
    root = tmp_path / "repo"
    pdir = root / "projects" / "p1"
    pdir.mkdir(parents=True)
    (root / "VIDEO_ENGINE" / "remotion" / "public" / "projects" / "p1").mkdir(parents=True)
    monkeypatch.setattr(config, "PROJECT_ROOT", root)
    monkeypatch.setattr(config, "PROJECTS_DIR", root / "projects")
    monkeypatch.setattr(config, "REMOTION_DIR", root / "VIDEO_ENGINE" / "remotion")       # the render reads the Remotion folder from config.REMOTION_DIR
    return pdir


@pytest.mark.parametrize("exc, expected", [
    (MemoryError(), "Not enough free memory"),
    (RuntimeError("mkl_malloc: failed to allocate memory"), "Not enough free memory"),
    (OSError(errno.ENOSPC, "No space left on device"), "disk is full"),
    (PermissionError(13, "denied", "C:/x/job.json"), "(job.json) is locked by another program"),
    (json.JSONDecodeError("Expecting value", "{", 0), "not valid JSON (line 1)"),
    (FileNotFoundError(2, "gone", "a/b/prompts_map.json"), "required file is missing: prompts_map.json"),
    (RuntimeError("boom"), "boom"),
    (UserProblem("already clear"), "already clear"),
])
def test_explain_known_errors(exc, expected):
    assert expected in explain(exc)


def test_explain_a_damaged_project_file():
    with pytest.raises(ValidationError) as e:
        Composition.model_validate({})
    assert "unexpected format (meta: Field required)" in explain(e.value)


@pytest.mark.parametrize("output, expected", [
    ("Error: Failed to load font Poppins (timeout)", "Google Fonts"),
    ("Error: Cannot find module '@remotion/cli'", 'npm install'),
    ("Error: Cannot find module '@remotion/google-fonts/Poppins'", 'npm install'),   # not a network problem
    ("ENOSPC: no space left on device, write", "disk is full"),
    ("Error loading image with src /projects/p1/a.png", "image used by the video"),
])
def test_explain_text_recognises_render_failures(output, expected):
    assert expected in explain_text(output)
    assert explain_text("Rendered 12/300") is None


def test_check_disk(monkeypatch, tmp_path):
    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(diagnose.shutil, "disk_usage", lambda p: usage(10**12, 0, int(0.1 * 1024**3)))
    with pytest.raises(UserProblem, match=r"Not enough disk space for the render: 0\.1 GB free .* about 2 GB needed"):
        check_disk(tmp_path / "not" / "created" / "yet", 2, "the render")   # a path that does not exist yet is fine
    monkeypatch.setattr(diagnose.shutil, "disk_usage", lambda p: usage(10**12, 0, 50 * 1024**3))
    check_disk(tmp_path, 2, "the render")


@needs_ffmpeg
def test_silent_and_damaged_audio_get_clear_messages(tmp_path):
    silent, tone = wav(tmp_path / "silent.wav"), wav(tmp_path / "tone.wav", amp=0.3)
    assert audio_utils.is_silent(silent) is True and audio_utils.is_silent(tone) is False
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"this is not audio at all " * 20)
    empty = tmp_path / "empty.wav"
    empty.write_bytes(b"")
    for f in (bad, empty):
        with pytest.raises(UserProblem, match="could not read the audio|no readable length"):
            audio_utils.duration(f)
        with pytest.raises(UserProblem, match="could not read the audio"):
            audio_utils.to_wav16k(f, tmp_path / "out.wav")


@needs_ffmpeg
def test_bad_input_1_silent_audio_stops_before_whisper_loads(env, monkeypatch):
    wav(env / "audio.wav")
    monkeypatch.setattr("faster_whisper.WhisperModel", lambda *a, **k: pytest.fail("the model must not load for silent audio"))
    with pytest.raises(StepError, match="The audio is silent"):
        execute(env, "transcribe", Ctx())
    assert json.loads((env / "job.json").read_text())["error"].startswith("The audio is silent")
    assert not (env / "transcript.json").exists()


@needs_ffmpeg
def test_no_speech_is_an_error_and_writes_no_transcript(env, monkeypatch):
    wav(env / "audio.wav", seconds=2, amp=0.3)

    class NoSpeech:
        def __init__(self, *a, **k): ...
        def transcribe(self, audio, **k):
            return [], None

    monkeypatch.setattr("faster_whisper.WhisperModel", NoSpeech)
    with pytest.raises(StepError, match="No speech was found"):
        execute(env, "transcribe", Ctx())
    assert not (env / "transcript.json").exists()


def test_bad_input_3_render_preflight_names_missing_and_unreadable_files(env, monkeypatch):
    pub = config.REMOTION_DIR / "public" / "projects" / "p1"
    png(pub / "ok.png")
    (pub / "bad.png").write_bytes(b"\x89PNG\r\n\x1a\n not really a png")
    comp = {"meta": {"audio": "audio.wav", "duration": 5}, "scenes": [{"id": 1, "start": 0, "end": 5, "layers": [
        {"type": "image", "slot": "a", "file": "projects/p1/ok.png"},
        {"type": "image", "slot": "b", "file": "projects/p1/gone.png"},
        {"type": "image", "slot": "c", "file": "projects/p1/bad.png"},
        {"type": "image", "slot": "d"},                           # empty slot: renders empty, never an error
        {"type": "text", "text": "Hi"}]}]}
    (env / "composition.json").write_text(json.dumps(comp), encoding="utf-8")
    with pytest.raises(UserProblem) as e:
        render.preflight(env)
    msg = str(e.value)
    assert "missing files: projects/p1/gone.png" in msg and "unreadable images: projects/p1/bad.png" in msg
    assert "ok.png" not in msg and "slot" not in msg
    comp["scenes"][0]["layers"] = [l for l in comp["scenes"][0]["layers"] if l.get("file") in (None, "projects/p1/ok.png")]
    (env / "composition.json").write_text(json.dumps(comp), encoding="utf-8")
    render.preflight(env)                                          # only good files and an empty slot: passes
    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(diagnose.shutil, "disk_usage", lambda p: usage(10**12, 0, 10**8))
    with pytest.raises(UserProblem, match="Not enough disk space for the render"):
        render.preflight(env)


# ---------- Task 12: performance profile ----------
def comp4(duration=4):
    return {"meta": {"audio": "audio.wav", "duration": duration, "fps": 30, "width": 1920, "height": 1080},
            "scenes": [{"id": i + 1, "start": i, "end": i + 1, "pattern": "hero_text", "layers": []} for i in range(4)]}


def test_scene_profile_splits_the_render_time_by_scene():
    rows = render.scene_profile(comp4(), [(30, 3.0), (60, 6.0), (90, 30.0), (120, 33.0)])
    assert [r["seconds"] for r in rows] == [3.0, 3.0, 24.0, 3.0]
    assert [r["s_per_frame"] for r in rows] == [0.1, 0.1, 0.8, 0.1]
    assert render.heavy_scenes(rows) == [3]


def test_scene_profile_interpolates_between_samples():
    rows = render.scene_profile(comp4(), [(120, 12.0)])           # a single sample at the very end: all scenes cost the same
    assert [r["seconds"] for r in rows] == [3.0, 3.0, 3.0, 3.0]
    assert render.heavy_scenes(rows) == []


def test_heavy_scenes_needs_enough_scenes_to_compare():
    assert render.heavy_scenes([{"id": 1, "s_per_frame": 5.0}, {"id": 2, "s_per_frame": 0.1}]) == []


class FakeRemotion:
    """Stands in for `npx remotion render`: prints progress lines and moves a fake clock."""
    def __init__(self, clock, steps, exit_code=0):
        self.clock, self.steps, self.exit_code = clock, steps, exit_code
        self.stdout = self._lines()

    def _lines(self):
        for at, done in self.steps:
            self.clock[0] = at
            yield f"Rendered {done}/120\r\n"

    def wait(self):
        return self.exit_code


def run_render(env, monkeypatch, steps, exit_code=0):
    from types import SimpleNamespace
    (env / "composition.json").write_text(json.dumps(comp4()), encoding="utf-8")
    (env / "audio.wav").write_bytes(b"audio")
    clock = [100.0]
    monkeypatch.setattr(render, "time", SimpleNamespace(time=lambda: clock[0]))
    monkeypatch.setattr(render.subprocess, "Popen", lambda cmd, **k: FakeRemotion(clock, steps, exit_code))
    return render.render(env, True)


def test_render_writes_a_profile_with_the_slow_scene(env, monkeypatch):
    out = run_render(env, monkeypatch, [(103.0, 30), (106.0, 60), (130.0, 90), (133.0, 120)])
    assert out == env / "out_preview.mp4"
    prof = json.loads((env / "render_profile.json").read_text())
    assert prof["mode"] == "preview" and prof["seconds"] == 33.0 and prof["video_seconds"] == 4
    assert prof["x_video_length"] == 8.2 and prof["heavy"] == [3]
    assert [s["id"] for s in prof["scenes"]] == [1, 2, 3, 4]


def test_a_failed_render_leaves_no_profile(env, monkeypatch):
    with pytest.raises(RuntimeError, match="remotion render failed"):
        run_render(env, monkeypatch, [(103.0, 30)], exit_code=1)
    assert not (env / "render_profile.json").exists()


def test_render_step_reports_the_ratio_and_warns_when_slow(env, monkeypatch):
    (env / "composition.json").write_text(json.dumps(comp4()), encoding="utf-8")
    (env / "audio.wav").write_bytes(b"audio")
    monkeypatch.setattr(pipeline.shutil, "which", lambda t: "/fake/" + t)

    def fake(x, heavy):
        def render_fn(pdir, preview, on_progress=None):
            (pdir / "out_preview.mp4").write_bytes(b"mp4")
            (pdir / "render_profile.json").write_text(json.dumps({"mode": "preview", "seconds": 4 * x, "x_video_length": x, "heavy": heavy}))
            return pdir / "out_preview.mp4"
        return render_fn

    monkeypatch.setattr(render, "render", fake(5.25, [3]))
    res = execute(env, "render-preview", Ctx(preview=True, force=True))
    assert res["msg"].endswith("(5.25x video length, heavy scenes [3] - slower than 3x)")
    assert "WARNING render took 5.25x video length" in (env / "log.txt").read_text()
    (env / "out_preview.mp4").unlink()
    monkeypatch.setattr(render, "render", fake(2.0, []))
    res = execute(env, "render-preview", Ctx(preview=True, force=True))
    assert res["msg"].endswith("(2.0x video length)") and "slower" not in res["msg"]


def test_status_shows_the_last_render_profile(env):
    (env / "render_profile.json").write_text(json.dumps({"mode": "final", "seconds": 507.4, "x_video_length": 7.2, "heavy": [4, 7]}))
    assert "last render: final 507.4s = 7.2x video length; heavy scenes: [4, 7]" in pipeline.status(env)


def test_the_preview_help_text_matches_the_real_preview_mode():
    src = (config.PROJECT_ROOT / "SYSTEM" / "core" / "cli.py").read_text(encoding="utf-8")
    assert "15fps" not in src and "full frame rate" in src       # a lower fps would play the audio at the wrong speed
    assert "--scale=0.5" in " ".join(render.render_flags(True)) and "--every-nth-frame" not in " ".join(render.render_flags(True))


# ---------- Task 13: packaging ----------
ROOT = Path(__file__).resolve().parent.parent
IMPORT_TO_PIP = {"PIL": "pillow", "cv2": "opencv-python", "faster_whisper": "faster-whisper", "imagehash": "imagehash",
                 "open_clip": "open_clip_torch", "starlette": "fastapi", "yaml": "pyyaml"}      # starlette is installed by fastapi
OPTIONAL = {"psutil"}                    # imported inside try with a fallback, and not installed here (render_intelligence: memory headroom estimate)


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def requirements() -> dict[str, str]:
    """{normalized package: pinned version} from requirements.txt (comments and blank lines skipped)."""
    out = {}
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if line:
            name, _, version = line.partition("==")
            assert version, f"requirements.txt: '{line}' is not pinned with =="
            out[norm(name)] = version
    return out


def third_party_imports() -> set[str]:
    import ast
    import sys
    found = set()
    for folder in ("UI", "VIDEO_ENGINE", "SYSTEM", "scripts", "tests"):
        for f in (ROOT / folder).rglob("*.py"):
            if "node_modules" in f.parts:
                continue                                                     # third-party JavaScript packages ship their own build scripts
            for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Import):
                    found |= {a.name.split(".")[0] for a in node.names}
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    found.add(node.module.split(".")[0])
    local = {"backend", "tests", "UI", "VIDEO_ENGINE", "SYSTEM", "scripts", "conftest", "config", "llm_client"} | {f.stem for f in (ROOT / "tests").glob("*.py")} | {f.stem for f in (ROOT / "tools").glob("*.py")}     # this repository's own packages, test modules and tools
    return {m for m in found if m not in sys.stdlib_module_names and m not in local}


def test_requirements_cover_every_third_party_import():
    have = requirements()
    missing = sorted(m for m in third_party_imports() - OPTIONAL if norm(IMPORT_TO_PIP.get(m, m)) not in have)
    assert missing == [], f"add these to requirements.txt (or to IMPORT_TO_PIP): {missing}"
    for runtime_only in ("uvicorn", "python-multipart", "onnxruntime", "httpx", "torchvision"):   # needed but never imported by our code
        assert runtime_only in have


def test_requirements_are_pinned_to_the_versions_this_project_runs_with():
    from importlib.metadata import version
    wrong = {n: (v, version(n).split("+")[0]) for n, v in requirements().items() if version(n).split("+")[0] != v}
    assert wrong == {}, f"requirements.txt pin vs installed: {wrong}"


def test_root_package_json_forwards_to_real_scripts():
    pkg = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    assert pkg["scripts"]["start"] == "start.bat" and (ROOT / "start.bat").exists()
    for folder in ("VIDEO_ENGINE/remotion", "UI/frontend"):
        assert f"npm --prefix {folder} install" in pkg["scripts"]["install:all"] and (ROOT / folder / "package.json").exists()
    assert "pytest" in pkg["scripts"]["test:backend"]
    assert "npm --prefix UI/frontend test" in pkg["scripts"]["test"] and "npm --prefix VIDEO_ENGINE/remotion run tsc" in pkg["scripts"]["test"]
    assert "tsc" in json.loads((ROOT / "VIDEO_ENGINE/remotion/package.json").read_text(encoding="utf-8"))["scripts"]


def test_start_bat_runs_everything_on_distinct_ports():
    bat = (ROOT / "start.bat").read_bytes()
    assert b"\r\n" in bat and b"\n" not in bat.replace(b"\r\n", b"")       # cmd.exe needs CRLF
    text = bat.decode("utf-8")
    assert 'call "%~dp0runproject.bat"' in text and "dashboard" not in text
    for folder, port in (("UI/frontend", 5173),):          # whitespace-tolerant: the files are formatted differently
        assert re.search(rf"port:\s*{port},\s*strictPort:\s*true", (ROOT / folder / "vite.config.ts").read_text(encoding="utf-8")), folder
    assert "--port 8000" in (ROOT / "runproject.bat").read_text(encoding="utf-8")


def test_readme_is_short_and_matches_the_real_setup():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert len(readme.splitlines()) <= 120                                  # docs/m9.md: short
    for needle in ("pip install -r requirements.txt", "npm run install:all", "start.bat", "5173", "8000", "backend.cli build"):
        assert needle in readme, needle


# ---------- Tasks 3 + 4: typography and color ----------
import itertools          # noqa: E402
import os                 # noqa: E402
import subprocess         # noqa: E402

from backend import palette as pal                      # noqa: E402
from backend.models import Style                         # noqa: E402

THEME = json.loads((ROOT / "VIDEO_ENGINE/remotion/src/theme.json").read_text(encoding="utf-8"))
PLAN_PALETTE = ["#0B1D26", "#2A9D8F", "#F2A541"]        # the order real plans use: [dark, teal, amber]
needs_node = pytest.mark.skipif(shutil.which("npx") is None, reason="npx not on PATH")


def tsx(script: str, **env) -> str:
    """Run a Remotion script with tsx; returns stdout."""
    r = subprocess.run(f"npx tsx scripts/{script}", cwd=ROOT / "VIDEO_ENGINE" / "remotion", shell=True, capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, **env}, timeout=120)
    assert r.returncode == 0, r.stderr[-800:]
    return r.stdout


def test_theme_numbers_are_sane():
    t = THEME["type"]
    sizes = list(t.values())
    assert sizes == sorted(sizes) and len(set(sizes)) == len(sizes)                  # a real ladder: strictly increasing
    assert min(sizes) >= 34 and t["body"] >= 52                                      # readable at 1080p (3% / 5% of the height)
    assert all(b / a <= 1.7 for a, b in zip(sizes, sizes[1:]))                       # no huge jumps between steps
    assert THEME["safeMargin"] == 0.05                                               # docs/rules.md: respect safe margins (5%)


def test_scrim_keeps_white_text_readable_over_the_worst_case_photo():
    """Worst case = a pure white photo under the scrim. 'minContrast' is the WCAG ratio for large text."""
    def contrast_over_white_photo(alpha: float) -> float:
        grey = round(255 * (1 - alpha))
        return pal.contrast("#ffffff", f"#{grey:02x}{grey:02x}{grey:02x}")
    assert contrast_over_white_photo(THEME["scrim"]) >= THEME["minContrast"]
    assert contrast_over_white_photo(0.30) < THEME["minContrast"]                    # the check can fail: a weaker scrim is not enough


def test_palette_roles_do_not_depend_on_the_order_of_the_colors():
    expected = {"base": "#0B1D26", "accent": "#F2A541", "secondary": "#2A9D8F"}
    for perm in itertools.permutations(PLAN_PALETTE):
        assert pal.roles(list(perm)) == expected, perm
    assert pal.roles(["#0B1D26", "#F2A541"]) == {"base": "#0B1D26", "accent": "#F2A541", "secondary": "#F2A541"}


def test_contrast_math():
    assert pal.contrast("#ffffff", "#000000") == pytest.approx(21.0)
    assert pal.contrast("#777", "#777") == pytest.approx(1.0)
    assert pal.norm("#FFF") == "#ffffff"
    r = pal.roles(PLAN_PALETTE)
    assert pal.contrast("#ffffff", r["base"]) >= 4.5 and pal.contrast(r["accent"], r["base"]) >= THEME["minContrast"]


def comp_with(*layers):
    return {"scenes": [{"id": 1, "layers": [dict(l) for l in layers]}]}


def test_palette_check_flags_colors_outside_the_palette_only():
    ok = comp_with({"type": "shape", "color": "#F2A541"}, {"type": "shape", "color": "#fff"}, {"type": "background", "colors": ["#0B1D26", "#2A9D8F"]},
                   {"type": "effect", "color": "rgba(1,2,3,0.5)"})                    # neutrals, palette colors and rgba() are fine
    assert pal.check(ok, PLAN_PALETTE) == []
    bad = comp_with({"type": "shape", "color": "#FF00FF"}, {"type": "shape", "color": "#ff00ff"})
    assert pal.check(bad, PLAN_PALETTE) == ["scene 1: shape layer uses #ff00ff, which is not in the palette " + str(PLAN_PALETTE)]   # reported once


def test_palette_check_flags_unreadable_palettes():
    dim_accent = pal.check(comp_with(), ["#0B1D26", "#14283A"])
    assert any(w.startswith("palette: accent") for w in dim_accent)
    light_base = pal.check(comp_with(), ["#e8e8e8", "#ffffff"])
    assert any(w.startswith("palette: white text on base") for w in light_base)


def test_the_demo_composition_has_no_palette_warnings():
    plan = json.loads((SAMPLE / "scene_plan.json").read_text(encoding="utf-8"))
    comp = json.loads((SAMPLE / "composition.json").read_text(encoding="utf-8"))
    assert pal.check(comp, plan["style"]["palette"]) == []


def test_style_and_meta_accept_the_new_optional_fields():
    Style.model_validate({"suffix": "x", "palette": PLAN_PALETTE})
    assert Style.model_validate({"suffix": "x", "palette": PLAN_PALETTE, "grade": "warm"}).grade == "warm"
    with pytest.raises(ValidationError):
        Style.model_validate({"suffix": "x", "palette": PLAN_PALETTE, "grade": "sepia"})
    comp = json.loads((SAMPLE / "composition.json").read_text(encoding="utf-8"))
    comp["meta"].update(palette=PLAN_PALETTE, grade="cool")
    assert Composition.model_validate(comp).meta.palette == PLAN_PALETTE


def test_components_use_the_theme_not_literals():
    """Every font size, accent and base color in the renderer comes from theme.json."""
    offenders = []
    for f in list((ROOT / "VIDEO_ENGINE/remotion/src/components").glob("*.tsx")) + list((ROOT / "VIDEO_ENGINE/remotion/src/patterns").glob("*.ts")) + [ROOT / "VIDEO_ENGINE/remotion/src/Main.tsx"]:
        text = f.read_text(encoding="utf-8")
        for pattern in (r"fontSize[:=]\s*\{?\s*\d", r"#F2A541", r"#2A9D8F", r"#0B1D26", r"#1B2A4A"):
            if re.search(pattern, text, re.I):
                offenders.append(f"{f.name}: {pattern}")
    assert offenders == [], offenders


@needs_node
def test_the_renderer_agrees_with_python_on_roles_and_fits_text_inside_the_safe_margin():
    width = 1920
    safe_px = width * (1 - 2 * THEME["safeMargin"])
    fits = [["1,400 km", 144, 800, safe_px], ["x" * 20, 144, 800, safe_px], ["x" * 40, 144, 800, safe_px], ["a" * 400, 144, 800, safe_px]]
    out = json.loads(tsx("print_theme.ts", THEME_INPUT=json.dumps({"palettes": [list(p) for p in itertools.permutations(PLAN_PALETTE)] + [["#0B1D26", "#F2A541"]], "fits": fits})))
    assert out["type"] == THEME["type"] and out["safe"] == THEME["safeMargin"] and out["scrim"] == THEME["scrim"]
    for r in out["roles"][:6]:
        assert r == {"base": "#0B1D26", "accent": "#F2A541", "secondary": "#2A9D8F"}
    assert out["roles"][6] == pal.roles(["#0B1D26", "#F2A541"])
    short, medium, two_lines, absurd = out["fits"]
    assert short == 144                                                              # short text keeps the full size
    assert 144 * 0.7 <= medium < 144 and medium * 0.64 * 20 <= safe_px + 1           # a long headline shrinks until it fits the safe width
    assert two_lines == pytest.approx(144 * 0.7) == pytest.approx(absurd)            # too long even at 70%: it stops shrinking and wraps inside the margin


@needs_node
def test_build_composition_writes_the_palette_and_keeps_backgrounds_dark_to_secondary(tmp_path):
    work = tmp_path / "p"
    work.mkdir()
    for name in ("scene_plan.json", "transcript.json"):
        shutil.copyfile(SAMPLE / name, work / name)
    r = subprocess.run(f'npx tsx scripts/build_composition.ts "{work}"', cwd=ROOT / "VIDEO_ENGINE" / "remotion", shell=True, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-600:]
    comp = json.loads((work / "composition.json").read_text(encoding="utf-8"))
    assert comp["meta"]["palette"] == PLAN_PALETTE and "grade" not in comp["meta"]
    backgrounds = {tuple(l["colors"]) for s in comp["scenes"] for l in s["layers"] if l["type"] == "background"}
    assert backgrounds == {("#0B1D26", "#2A9D8F")}           # base -> secondary: never the amber accent (the old palette[1] bug)
    assert pal.check(comp, PLAN_PALETTE) == []


def fill_env(env, grade=None):
    """A project that fill() can run on: one scene, no prompts, plus a scene_plan with a style."""
    pdir = env
    comp = {"meta": {"audio": "audio.wav", "duration": 5, "fps": 30, "width": 1920, "height": 1080},
            "scenes": [{"id": 1, "start": 0, "end": 5, "pattern": "hero_text", "camera": {"move": "static"}, "layers": [{"type": "text", "text": "Hi", "z": 1}]}]}
    (pdir / "composition.json").write_text(json.dumps(comp), encoding="utf-8")
    (pdir / "match_report.json").write_text(json.dumps({"matches": []}), encoding="utf-8")
    (pdir / "prompts_map.json").write_text(json.dumps({"prompts": []}), encoding="utf-8")
    style = {"suffix": "x", "palette": PLAN_PALETTE, **({"grade": grade} if grade else {})}
    (pdir / "scene_plan.json").write_text(json.dumps({"style": style, "scenes": []}), encoding="utf-8")
    return pdir


# ---------- Tasks 2, 6, 8: camera, effects, word accents ----------
from backend import motion_checks                        # noqa: E402
from backend.focus import frame_focus                     # noqa: E402

CAMERA = THEME["camera"]


def bezier_y(x1, y1, x2, y2, x):
    """CSS cubic-bezier(x1, y1, x2, y2) evaluated at x (bisection on the curve's x)."""
    lo, hi = 0.0, 1.0
    for _ in range(60):
        t = (lo + hi) / 2
        bx = 3 * (1 - t) ** 2 * t * x1 + 3 * (1 - t) * t ** 2 * x2 + t ** 3
        lo, hi = (t, hi) if bx < x else (lo, t)
    t = (lo + hi) / 2
    return 3 * (1 - t) ** 2 * t * y1 + 3 * (1 - t) * t ** 2 * y2 + t ** 3


def peak_speed(ys):
    """Fastest step divided by the average step: 1.0 = perfectly even, 4+ = a burst followed by a crawl."""
    return max(b - a for a, b in zip(ys, ys[1:])) / ((ys[-1] - ys[0]) / (len(ys) - 1))


def cam(move, **extra):
    return {"move": move, "from": 1.0, "to": 1.1, "focus": [0.5, 0.5], **extra}


@needs_node
def test_camera_moves_are_even_and_bounded_and_the_old_curve_was_not():
    samples = [i / 100 for i in range(101)]
    frames = list(range(151))
    out = json.loads(tsx("print_motion.ts", THEME_INPUT=json.dumps({"curveSamples": samples, "cams": [
        {"cam": cam("push-in"), "dur": 150, "seed": "s", "frames": frames},
        {"cam": cam("pull-out"), "dur": 150, "seed": "s", "frames": frames},
        {"cam": cam("pan-right"), "dur": 150, "seed": "s", "frames": frames},
        {"cam": cam("zoom-to-focus", to=1.1), "dur": 150, "seed": "s", "frames": frames},
        {"cam": cam("static"), "dur": 150, "seed": "s", "frames": frames}]})))
    for name, ys in out["curves"].items():
        assert ys[0] == pytest.approx(0, abs=1e-6) and ys[-1] == pytest.approx(1, abs=1e-6)
        assert all(b >= a - 1e-9 for a, b in zip(ys, ys[1:])), name                # never goes backwards: no jitter
    assert peak_speed(out["curves"]["push"]) <= 2.0 and peak_speed(out["curves"]["pan"]) <= 2.0 and peak_speed(out["curves"]["focus"]) <= 2.6
    old = [bezier_y(0.22, 1, 0.36, 1, x) for x in samples]
    assert peak_speed(old) > 4.0                                                    # the previous global curve: a burst, then a crawl
    push, pull, pan, focus, static = ([s["scale"] for s in c] for c in out["cams"])
    assert push[0] == pytest.approx(1.0) and push[-1] == pytest.approx(1.1) and pull[0] == pytest.approx(1.1) and pull[-1] == pytest.approx(1.0)
    assert focus[-1] == pytest.approx(CAMERA["focusScale"]) and set(static) == {1.0}
    assert [s["tx"] for s in out["cams"][2]][0] == pytest.approx(-3) and out["cams"][2][-1]["tx"] == pytest.approx(3)
    assert max(push) <= CAMERA["maxScale"]
    assert all(s["ty"] == 0 and s["rot"] == 0 for c in out["cams"] for s in c)      # no drift unless asked for


@needs_node
def test_handheld_drift_is_small_smooth_repeatable_and_off_by_default():
    frames = list(range(151))
    cases = [{"cam": cam("static", drift=1), "dur": 150, "seed": "a", "frames": frames},
             {"cam": cam("static", drift=1), "dur": 150, "seed": "a", "frames": frames},
             {"cam": cam("static", drift=1), "dur": 150, "seed": "b", "frames": frames},
             {"cam": cam("static", drift=0.5), "dur": 150, "seed": "a", "frames": frames},
             {"cam": cam("static", drift=0), "dur": 150, "seed": "a", "frames": frames}]
    a, a2, b, half, off = json.loads(tsx("print_motion.ts", THEME_INPUT=json.dumps({"cams": cases})))["cams"]
    d = CAMERA["drift"]
    assert a == a2 and a != b                                                       # same seed: identical frames; other scene: other sway
    assert max(abs(s["tx"]) for s in a) <= d["maxShiftPct"] and max(abs(s["ty"]) for s in a) <= d["maxShiftPct"]
    assert max(abs(s["rot"]) for s in a) <= d["maxRotateDeg"]
    assert max(abs(s["tx"]) for s in a) > 0.05                                      # it really moves
    assert max(abs(y["tx"] - x["tx"]) for x, y in zip(a, a[1:])) < 0.05            # smooth: a few hundredths of a percent per frame
    assert max(abs(s["tx"]) for s in half) <= max(abs(s["tx"]) for s in a) * 0.51   # strength scales it
    assert all(s["scale"] == pytest.approx(1 + d["headroom"]) for s in a)           # extra scale keeps the frame edges hidden
    assert all((s["tx"], s["ty"], s["rot"], s["scale"]) == (0, 0, 0, 1) for s in off)


@needs_node
def test_accent_pulses_are_small_brief_and_never_stack():
    fps = 30
    out = json.loads(tsx("print_motion.ts", THEME_INPUT=json.dumps({"pulses": [
        {"times": [1.0], "fps": fps, "frames": list(range(100))},
        {"times": [1.0, 1.1], "fps": fps, "frames": list(range(100))}]})))
    one, two = out["pulses"]
    a = THEME["accent"]
    assert max(one) == pytest.approx(a["pulseScale"], abs=1e-3) and max(two) <= a["pulseScale"] + 1e-9    # two close pulses do not add up
    assert all(v == 1 for v in one[:fps]) and all(v == 1 for v in one[fps + a["upFrames"] + a["downFrames"] + 1:])   # exactly 1 outside the window
    assert sum(1 for v in one if v > 1) <= a["upFrames"] + a["downFrames"]
    assert a["pulseScale"] <= 1.06                                                  # "small pulses"


def test_frame_focus_converts_a_photo_point_to_a_screen_point():
    assert frame_focus([0.4, 0.6], (1920, 1080)) == [0.4, 0.6]                      # 16:9 photo filling the frame: unchanged
    square = frame_focus([0.5, 0.4], (1000, 1000), "full")                          # 1:1 photo is cropped top and bottom by object-fit: cover
    assert square == [0.5, 0.322] and square[1] != 0.4                              # the old code aimed at 0.4: 84 px off
    assert frame_focus([0.5, 0.5], (2000, 1500), "left-half") == [0.25, 0.5]        # centre of a photo in the left half is the centre of that half
    assert frame_focus([0.5, 0.5], (2000, 1500), [960, 0, 960, 1080]) == [0.75, 0.5]    # same box given in pixels: the right half
    assert frame_focus([0.95, 0.5], (1000, 1000), "full")[0] == 0.85                # never aims at the very edge of the visible photo
    assert frame_focus([0.5, 0.5], (1000, 1000), "no-such-box") == frame_focus([0.5, 0.5], (1000, 1000), "full")


def test_named_image_boxes_are_complete_and_inside_the_frame():
    boxes = THEME["boxes"]
    used = set(re.findall(r'pos: "([a-z0-9-]+)"', (ROOT / "VIDEO_ENGINE/remotion/src/patterns/index.ts").read_text(encoding="utf-8")))
    used |= {f"grid-{i}" for i in range(4)}
    assert used <= set(boxes), used - set(boxes)
    for name, (x, y, w, h) in boxes.items():
        assert 0 <= x and 0 <= y and w > 0 and h > 0 and x + w <= 1 + 1e-9 and y + h <= 1 + 1e-9, name


def test_motion_checks_on_the_demo_plan_only_flag_the_long_glow():
    plan = json.loads((SAMPLE / "scene_plan.json").read_text(encoding="utf-8"))
    comp = json.loads((SAMPLE / "composition.json").read_text(encoding="utf-8"))
    assert motion_checks.check(comp, plan) == ["scene 7: glow effect lasts 5.8s (accents are short, default 1.2s)"]


def test_camera_limits_are_flagged():
    mk = lambda **c: {"scenes": [{"id": 1, "layers": [], "camera": {"move": "push-in", "from": 1.0, "to": 1.1, "focus": [0.5, 0.5], **c}}]}   # noqa: E731
    assert motion_checks.camera_warnings(mk()) == []
    assert "zoom 1.3 is above 1.15" in motion_checks.camera_warnings(mk(to=1.3))[0]
    assert "zoom-to-focus" not in motion_checks.camera_warnings(mk(move="zoom-to-focus", to=1.25))                  # its own, higher limit
    assert "below 1" in motion_checks.camera_warnings(mk(**{"from": 0.9}))[0]
    assert "close to the edge" in motion_checks.camera_warnings(mk(focus=[0.05, 0.5]))[0]
    assert motion_checks.camera_warnings(mk(move="static", focus=[0.05, 0.5])) == []                              # a static camera never crops
    assert "drift" in motion_checks.camera_warnings(mk(drift=2))[0]


def test_effects_only_at_emphasis_moments_and_with_limits():
    plan = {"scenes": [{"id": 1, "keywords": [{"text": "x", "at": 3.0}]}]}
    sparkle = lambda at, **k: {"type": "effect", "name": "sparkle", "at": at, **k}      # noqa: E731
    scene = lambda *layers: {"scenes": [{"id": 1, "layers": list(layers)}]}              # noqa: E731
    assert motion_checks.effect_warnings(scene(sparkle(3.4)), plan) == []                        # near a keyword
    icon_pop = {"type": "icon", "enter": {"at": 7.0, "anim": "pop", "dur": 0.5}}
    assert motion_checks.effect_warnings(scene(icon_pop, sparkle(7.3)), plan) == []              # near an element entering
    assert "not near a keyword" in motion_checks.effect_warnings(scene(sparkle(5.5)), plan)[0]
    assert "3 effects" in motion_checks.effect_warnings(scene(sparkle(3.0), sparkle(3.1), sparkle(3.2)), plan)[0]
    assert "capped at 60" in motion_checks.effect_warnings(scene({"type": "effect", "name": "particles", "at": 3.0, "count": 200}), plan)[0]
    assert motion_checks.effect_warnings(scene({"type": "effect", "name": "particles", "at": 3.0, "dur": 8}), plan) == []   # ambient particles may be long
    assert "lasts 6.0s" in motion_checks.effect_warnings(scene(sparkle(3.0, dur=6.0)), plan)[0]


@needs_node
def test_build_composition_pulses_the_headline_at_the_scene_s_later_keywords(tmp_path):
    work = tmp_path / "p"
    work.mkdir()
    plan = json.loads((SAMPLE / "scene_plan.json").read_text(encoding="utf-8"))
    scene = plan["scenes"][0]
    scene["keywords"] = [{"text": "one", "at": scene["start"] + 1.0}, {"text": "two", "at": scene["start"] + 3.0}]
    (work / "scene_plan.json").write_text(json.dumps(plan), encoding="utf-8")
    shutil.copyfile(SAMPLE / "transcript.json", work / "transcript.json")
    r = subprocess.run(f'npx tsx scripts/build_composition.ts "{work}"', cwd=ROOT / "VIDEO_ENGINE" / "remotion", shell=True, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-600:]
    comp = json.loads((work / "composition.json").read_text(encoding="utf-8"))
    texts = [(s["id"], l) for s in comp["scenes"] for l in s["layers"] if l["type"] == "text"]
    first = next(l for sid, l in texts if sid == scene["id"])
    assert first["pulses"] == [scene["start"] + 3.0] and first["at"] == scene["start"] + 1.0     # entrance at keyword 1, pulse at keyword 2
    assert all("pulses" not in l for sid, l in texts if sid != scene["id"])                       # one keyword: nothing to pulse for


def test_executor_turns_every_failure_into_a_clear_step_error(env, monkeypatch):
    def add(name, fn):
        monkeypatch.setitem(pipeline.STEPS, name, Step(name, (), lambda p: [], None, fn))

    def clear(pdir, ctx):
        raise UserProblem("Put the audio file in the project folder.")

    def memory(pdir, ctx):
        raise RuntimeError("mkl_malloc: failed to allocate memory")

    def unknown(pdir, ctx):
        raise KeyError("odd")

    add("t-clear", clear), add("t-mem", memory), add("t-odd", unknown)
    with pytest.raises(StepError) as e:
        execute(env, "t-clear", Ctx())
    assert str(e.value) == "Put the audio file in the project folder."            # a lower-layer UserProblem is not "unexpected"
    assert json.loads((env / "job.json").read_text())["error"] == str(e.value)
    with pytest.raises(StepError) as e:
        execute(env, "t-mem", Ctx())
    assert "t-mem failed: Not enough free memory" in str(e.value) and "mkl_malloc" not in str(e.value)
    assert "mkl_malloc" in (env / "log.txt").read_text()                           # the raw detail stays in the log
    with pytest.raises(StepError, match="t-odd failed"):
        execute(env, "t-odd", Ctx())
