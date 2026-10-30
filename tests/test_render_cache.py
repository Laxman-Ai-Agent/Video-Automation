"""Phase 7: the scene-by-scene render cache (stages/render_cache.py + render.render). Run: python -m pytest tests/test_render_cache.py -q (with the project .venv)"""
import contextlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from backend import config, render
from VIDEO_ENGINE.stages import render_cache

needs_ffmpeg = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg/ffprobe not on PATH")


def comp(n=4, transitions=True):
    """n scenes of 2 s at 30 fps; every scene but the last fades into the next one over 0.4 s (12 frames)."""
    return {"meta": {"audio": "audio.wav", "duration": 2 * n, "fps": 30, "width": 1920, "height": 1080, "palette": "x"},
            "scenes": [{"id": i, "start": 2 * (i - 1), "end": 2 * i, "layers": [{"type": "custom_scene", "scene_id": i}],
                        "transition_out": {"type": "fade", "dur": 0.4} if transitions else None} for i in range(1, n + 1)]}


@pytest.fixture
def env(tmp_path, monkeypatch):
    """A fake repo root with a Remotion folder (src/, public/) and one project with four generated scenes; config points at it."""
    root = tmp_path / "repo"
    rd = root / "VIDEO_ENGINE" / "remotion"
    (rd / "src").mkdir(parents=True)
    (rd / "public").mkdir()
    (rd / "src" / "Main.tsx").write_text("main v1", encoding="utf-8")
    pdir = root / "projects" / "p1"
    (pdir / "generated_motion").mkdir(parents=True)
    for i in range(1, 5):
        (pdir / "generated_motion" / f"scene_{i}.tsx").write_text(f"scene {i} v1", encoding="utf-8")
    (pdir / "composition.json").write_text(json.dumps(comp()), encoding="utf-8")
    monkeypatch.setattr(config, "PROJECT_ROOT", root)
    monkeypatch.setattr(config, "PROJECTS_DIR", root / "projects")
    monkeypatch.setattr(config, "REMOTION_DIR", rd)
    monkeypatch.setattr("VIDEO_ENGINE.pipeline.browser_profiles.cleaned_after", contextlib.nullcontext)      # no browser runs here: the sweep of Chrome profile folders reads the machine's temp folder and process list
    return pdir


def keys(pdir, c=None, preview=False):
    c = c or json.loads((pdir / "composition.json").read_text(encoding="utf-8"))
    return [x["key"] for x in render_cache.plan(pdir, c, preview, render.render_flags(preview), pdir / "cache")]


def test_windows_are_laid_out_like_scene_root():
    w = render_cache.windows(comp())
    assert [(r["from"], r["to"], r["out_frames"]) for r in w] == [(0, 60, 12), (60, 120, 12), (120, 180, 12), (180, 240, 0)]    # the last scene has no exit transition
    assert [r["prev"] and r["prev"]["scene"]["id"] for r in w] == [None, 1, 2, 3]


def test_a_gap_in_the_scene_times_does_not_move_the_windows():
    c = comp()
    c["scenes"][1]["start"], c["scenes"][1]["end"] = 5.0, 7.0                      # SceneRoot lays the scenes out by their LENGTH, not by their start
    assert [(r["from"], r["to"]) for r in render_cache.windows(c)] == [(0, 60), (60, 120), (120, 180), (180, 240)]


def test_the_last_window_runs_to_the_end_of_the_video():
    c = comp()
    c["meta"]["duration"] = 7.5
    assert render_cache.windows(c)[-1]["to"] == 225
    c["meta"]["duration"] = 5.0                                                    # scenes that start after the end of the video are not rendered
    assert [(r["from"], r["to"]) for r in render_cache.windows(c)] == [(0, 60), (60, 120), (120, 150)]


def test_keys_are_stable(env):
    assert keys(env) == keys(env) and len(set(keys(env))) == 4


def test_a_rewritten_scene_costs_its_own_chunk_and_the_next_one(env):
    before = keys(env)
    (env / "generated_motion" / "scene_2.tsx").write_text("scene 2 v2", encoding="utf-8")
    after = keys(env)
    assert [a != b for a, b in zip(before, after)] == [False, True, True, False]  # scene 3's first frames blend in the tail of scene 2


def test_without_a_transition_only_the_scene_itself_is_rendered_again(env):
    c = comp(transitions=False)
    (env / "composition.json").write_text(json.dumps(c), encoding="utf-8")
    before = keys(env, c)
    (env / "generated_motion" / "scene_2.tsx").write_text("scene 2 v2", encoding="utf-8")
    assert [a != b for a, b in zip(before, keys(env, c))] == [False, True, False, False]


def test_a_file_a_layer_names_is_part_of_its_chunk(env):
    c = comp()
    c["scenes"][2]["layers"].append({"type": "image", "file": "img.png"})
    (config.REMOTION_DIR / "public" / "img.png").write_bytes(b"one")
    before = keys(env, c)
    (config.REMOTION_DIR / "public" / "img.png").write_bytes(b"two")
    assert [a != b for a, b in zip(before, keys(env, c))] == [False, False, True, True]


@pytest.mark.parametrize("change", ["main", "meta", "assets"])
def test_a_global_change_renders_every_scene_again(env, change):
    before = keys(env)
    if change == "main":
        (config.REMOTION_DIR / "src" / "Main.tsx").write_text("main v2", encoding="utf-8")
    elif change == "assets":
        (env / "assets_manifest.json").write_text("{}", encoding="utf-8")
    else:
        c = json.loads((env / "composition.json").read_text(encoding="utf-8"))
        c["meta"]["palette"] = "y"
        (env / "composition.json").write_text(json.dumps(c), encoding="utf-8")
    assert all(a != b for a, b in zip(before, keys(env)))


def captioned(subtitles=True):
    c = comp()
    c["meta"]["subtitles"] = subtitles
    c["words"] = [{"w": "a", "start": 0.5, "end": 1.5}, {"w": "z", "start": 7.0, "end": 7.5}]
    c["captions"] = [{"start": 0.5, "end": 1.5, "hook": True, "words": [{"w": "a", "start": 0.5, "end": 1.5, "key": False}]},
                     {"start": 7.0, "end": 7.5, "hook": False, "words": [{"w": "z", "start": 7.0, "end": 7.5, "key": False}]}]
    return c


def test_a_changed_caption_redraws_only_the_chunks_it_is_heard_in(env):
    c = captioned()
    before = keys(env, c)
    c["captions"][1]["words"][0]["w"] = "y"
    c["words"][1]["w"] = "y"
    assert [a != b for a, b in zip(before, keys(env, c))] == [False, False, False, True]    # the caption at 7 s is in the last scene's window only


def test_captions_that_are_not_drawn_do_not_change_a_chunk(env):
    c = captioned(subtitles=False)
    before = keys(env, c)
    c["captions"][0]["words"][0]["w"] = "q"                                                  # nothing draws it: the pixels are the same
    assert keys(env, c) == before


def test_turning_the_captions_on_redraws_every_chunk_that_has_one(env):
    off, on = keys(env, captioned(subtitles=False)), keys(env, captioned(subtitles=True))
    assert [a != b for a, b in zip(off, on)] == [True, False, False, True]                   # scenes 2 and 3 have no caption: they are the same pictures


def test_preview_and_final_do_not_share_chunks(env):
    assert set(keys(env, preview=True)).isdisjoint(keys(env, preview=False))


def test_a_generated_scene_of_another_project_is_not_part_of_the_key(env):
    before = keys(env)
    (config.REMOTION_DIR / "src" / "generated").mkdir()
    (config.REMOTION_DIR / "src" / "generated" / "scene_9.tsx").write_text("x", encoding="utf-8")      # staged scenes are hashed per scene (generated_motion/), not as part of the global code
    assert keys(env) == before


class FakeProc:
    stdout = iter(())

    def wait(self):
        return 0


def render_it(pdir, monkeypatch):
    """render.render with a fake Remotion: returns the commands that would have run."""
    cmds = []

    def popen(cmd, **kw):
        cmds.append(cmd)
        if cmd[2] == "render":
            Path(cmd[5]).write_bytes(b"chunk")
        return FakeProc()
    monkeypatch.setattr(render.subprocess, "Popen", popen)
    monkeypatch.setattr(render, "preflight", lambda *a, **k: None)
    monkeypatch.setattr(render, "stage_audio", lambda *a, **k: None)
    monkeypatch.setattr(render, "stage_motion", lambda *a, **k: None)
    monkeypatch.setattr(render.render_cache, "assemble", lambda chunks, audio, fps, out, work: out.write_bytes(b"mp4"))
    render.render(pdir, False)
    return cmds


def frames_of(cmds):
    return [next(a for a in c if a.startswith("--frames=")) for c in cmds if c[2] == "render"]


def test_the_second_render_takes_every_scene_from_the_cache(env, monkeypatch):
    first = render_it(env, monkeypatch)
    assert frames_of(first) == ["--frames=0-59", "--frames=60-119", "--frames=120-179", "--frames=180-239"]
    assert sum(c[2] == "bundle" for c in first) == 1                               # one bundle for all the chunks
    second = render_it(env, monkeypatch)
    assert second == []                                                            # nothing to render: no bundle either
    assert json.loads((env / "render_profile.json").read_text(encoding="utf-8"))["cached_frames"] == 240


def test_one_rewritten_scene_renders_two_chunks(env, monkeypatch):
    render_it(env, monkeypatch)
    (env / "generated_motion" / "scene_2.tsx").write_text("scene 2 v2", encoding="utf-8")
    again = render_it(env, monkeypatch)
    assert frames_of(again) == ["--frames=60-119", "--frames=120-179"]
    assert len(list((env / "render_cache" / "final").glob("*.mp4"))) == 4        # the two old clips are gone
    assert render_it(env, monkeypatch) == []


def test_a_chunk_that_failed_is_not_cached(env, monkeypatch):
    render_it(env, monkeypatch)
    (env / "generated_motion" / "scene_1.tsx").write_text("scene 1 v2", encoding="utf-8")

    class Failing(FakeProc):
        def wait(self):
            return 1
    monkeypatch.setattr(render.subprocess, "Popen", lambda cmd, **k: Failing() if cmd[2] == "render" else FakeProc())
    with pytest.raises(RuntimeError):
        render.render(env, False)
    assert not list((env / "render_cache" / "final").glob("*.part.mp4"))
    assert not (env / "render_cache" / "_bundle").exists()
    assert len(frames_of(render_it(env, monkeypatch))) == 2                         # scene 1 and 2 are still to do, 3 and 4 stay cached


def run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


@needs_ffmpeg
@pytest.mark.parametrize("relative", [False, True])
def test_assemble_joins_the_chunks_and_adds_the_audio_once(tmp_path, monkeypatch, relative):
    clips = []
    (tmp_path / "cache").mkdir()
    (tmp_path / "work").mkdir()
    for i in range(2):
        f = tmp_path / "cache" / f"c{i}.mp4"
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=64x64:rate=30", "-t", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(f)])
        clips.append({"path": f, "from": 30 * i, "to": 30 * (i + 1)})
    audio = tmp_path / "a.wav"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=3", str(audio)])      # longer than the picture: it is cut where the picture ends
    out, work = tmp_path / "out.mp4", tmp_path / "work"
    if relative:                                                                   # a project folder given as a relative path (a script run from the repo root): the chunk list lives in another folder than the chunks
        monkeypatch.chdir(tmp_path)
        clips = [{**c, "path": Path("cache") / c["path"].name} for c in clips]
        audio, out, work = Path("a.wav"), Path("out.mp4"), Path("work")
    render_cache.assemble(clips, audio, 30, out, work)
    out = tmp_path / "out.mp4"
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-show_entries", "stream=codec_type,nb_read_frames,duration", "-of", "json", str(out)],
                                      check=True, capture_output=True, text=True).stdout)["streams"]
    video = next(s for s in probe if s["codec_type"] == "video")
    sound = next(s for s in probe if s["codec_type"] == "audio")
    assert video["nb_read_frames"] == "60"
    assert abs(float(sound["duration"]) - 2.0) < 0.1


def test_prune_keeps_only_the_clips_of_the_current_plan(tmp_path):
    for n in ("a", "b", "c"):
        (tmp_path / f"{n}.mp4").write_bytes(b"x")
    render_cache.prune(tmp_path, [{"path": tmp_path / "a.mp4"}, {"path": tmp_path / "c.mp4"}])
    assert sorted(p.name for p in tmp_path.glob("*.mp4")) == ["a.mp4", "c.mp4"]
