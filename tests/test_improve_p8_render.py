"""Phase 8: a real, tiny render (9:16, 360x640, 10 fps, 12 s) of a scene the improvements rewrote: three timed shots, an icon with backing, a headline and a
number callout. Checks the file with ffprobe (shape, length, frame rate, audio) and samples frames around the shot changes (no blank frame, the picture really
changes). Cheap on purpose: nothing here is a final render."""
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from backend import shots

ROOT = Path(__file__).parent.parent


def _ready() -> str | None:
    if not shutil.which("node") or not shutil.which("npx"):
        return "node/npx not on PATH"
    if not shutil.which("ffprobe") or not shutil.which("ffmpeg"):
        return "ffmpeg/ffprobe not on PATH"
    if not (ROOT / "VIDEO_ENGINE" / "remotion" / "node_modules" / "@remotion" / "cli").exists():
        return "remotion dependencies are not installed"
    import socket
    try:
        [socket.create_connection((h, 443), timeout=4).close() for h in ("fonts.googleapis.com", "fonts.gstatic.com")]
    except OSError:
        return "Google Fonts unreachable (the renderer fetches the fonts at render time)"
    return None


def mini_project(pdir: Path) -> dict:
    """A 12 s scene with three pictures whose narration phrases are 4 s apart; returns the composition after apply_shots (the real rewrite)."""
    pdir.mkdir(parents=True)
    words = [(f"w{i}", 0.5 * i, 0.5 * i + 0.4) for i in range(24)]
    (pdir / "transcript.json").write_text(json.dumps({"language": "te", "duration": 12.0, "segments": [{"id": 0, "start": 0.0, "end": 11.9, "text": "x", "words": [{"w": w, "start": a, "end": b} for w, a, b in words]}]}), encoding="utf-8")
    (pdir / "transcript_en.json").write_text(json.dumps({"duration": 12.0, "segments": [
        {"id": 0, "start": 0.0, "end": 3.9, "te": "x", "en": "Rivers carry water to farms."}, {"id": 1, "start": 4.0, "end": 7.9, "te": "x", "en": "Mountains hold the snow."},
        {"id": 2, "start": 8.0, "end": 12.0, "te": "x", "en": "Cities depend on dams."}]}), encoding="utf-8")
    (pdir / "cuts.json").write_text(json.dumps({"cuts": [{"t": 3.9, "reason": "sentence_end", "silence": 0.3}, {"t": 7.9, "reason": "sentence_end", "silence": 0.3}]}), encoding="utf-8")
    plan = {"style": {"suffix": "x", "palette": ["#0B1D26", "#F2A541", "#2A9D8F"]}, "scenes": [{"id": 1, "start": 0, "end": 12, "meaning": "m", "concept": "c", "mood": "calm",
            "mode": "image-composite", "pattern": "triple_stack", "keywords": [], "params": {}}]}
    (pdir / "scene_plan.json").write_text(json.dumps(plan), encoding="utf-8")
    prompts = [{"n": i + 1, "scene": 1, "slot": f"s01_{i}", "role": "main" if i == 0 else "supporting", "ratio": "9:16", "required": True, "bg": "full", "text": t}
               for i, t in enumerate(["Rivers flowing to farms", "Snowy mountains", "A city with dams"])]
    (pdir / "prompts_map.json").write_text(json.dumps({"prompts": prompts}), encoding="utf-8")
    (pdir / "match_report.json").write_text(json.dumps({"matches": [{"n": i + 1, "file": f"{i + 1}.png", "method": "filename", "status": "ok", "score": None, "margin": None} for i in range(3)],
                                                        "unused": [], "duplicates": [], "warnings": [], "broken": []}), encoding="utf-8")
    layers = [{"type": "background", "kind": "gradient", "colors": ["#0B1D26", "#2A9D8F"], "z": 0}] + \
             [{"type": "image", "slot": f"s01_{i}", "file": f"img_0{i + 1}.png", "z": 1 + i} for i in range(3)] + \
             [{"type": "icon", "lucide": "droplet", "pos": [900, 300], "size": 160, "z": 10, "backing": True, "enter": {"at": 1.0, "anim": "pop", "dur": 0.5}},
              {"type": "text", "style": "big-highlight", "text": "Water", "at": 1.5, "z": 11},
              {"type": "counter", "from": 0, "to": 1400, "unit": "km", "at": 2.0, "dur": 1.5, "pos": [540, 1500], "z": 12, "backing": True}]
    comp = {"meta": {"fps": 10, "width": 1080, "height": 1920, "audio": "audio_test.wav", "duration": 12.0, "subtitles": False, "palette": ["#0B1D26", "#F2A541", "#2A9D8F"]},
            "scenes": [{"id": 1, "start": 0, "end": 12, "pattern": "triple_stack", "camera": {"move": "push-in", "from": 1, "to": 1.1, "focus": [0.5, 0.5]}, "layers": layers}]}
    assert shots.apply_shots(pdir, comp) == 1
    return comp


def frame_at(video: Path, t: float, out: Path) -> np.ndarray:
    from PIL import Image
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1", str(out)], check=True, capture_output=True)
    return np.array(Image.open(out).convert("RGB")).astype(float)


def test_tiny_render_has_the_right_shape_length_audio_and_shot_changes(tmp_path):
    why = _ready()
    if why:
        pytest.skip(why)
    comp = mini_project(tmp_path / "proj")
    s = comp["scenes"][0]
    assert len(s["shots"]) == 3
    props = tmp_path / "props.json"
    props.write_text(json.dumps(comp), encoding="utf-8")
    out = tmp_path / "tiny.mp4"
    from backend.render import _free_port      # Remotion's default port 3000 can belong to another application on this machine ("Does this look like a foreign page?")
    cmd = f'npx remotion render src/index.ts Main "{out}" --props="{props}" --scale=0.3333333333333333 --concurrency=2 --log=error --port={_free_port()}'
    for attempt in range(2):                                                             # the renderer start can fail once on a locked temp file (Windows)
        r = subprocess.run(cmd, cwd=ROOT / "VIDEO_ENGINE" / "remotion", shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        if r.returncode == 0:
            break
    if r.returncode != 0 and "fetchFontData" in (r.stderr + r.stdout):
        pytest.skip("the web fonts could not be downloaded at render time (network): not a code failure")
    assert r.returncode == 0, (r.stderr or r.stdout)[-800:]
    info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(out)], capture_output=True, text=True, check=True).stdout)
    v = next(x for x in info["streams"] if x["codec_type"] == "video")
    a = [x for x in info["streams"] if x["codec_type"] == "audio"]
    assert (v["width"], v["height"]) == (360, 640)                                         # 9:16 at the small test size
    assert v["r_frame_rate"] == "10/1"
    assert abs(float(info["format"]["duration"]) - 12.0) < 0.25                              # the video is as long as the composition (= the narration)
    assert a and abs(float(a[0]["duration"]) - 12.0) < 0.5                                   # the audio is in the file and as long
    assert out.stat().st_size > 5_000

    b1, b2 = s["shots"][1]["start"], s["shots"][2]["start"]
    names = {"before1": b1 - 0.3, "after1": b1 + 0.8, "before2": b2 - 0.3, "after2": b2 + 0.8, "mid1": b1 + s["shots"][1]["transition_dur"] / 2}
    f = {k: frame_at(out, t, tmp_path / f"{k}.png") for k, t in names.items()}
    for k, im in f.items():
        assert im.std() > 12, f"{k}: the frame looks blank (std {im.std():.1f})"            # no empty / flat frame anywhere around a change
    diff = lambda x, y: float(np.abs(f[x] - f[y]).mean())
    assert diff("before1", "after1") > 15 and diff("before2", "after2") > 15                 # the picture really changes at each shot boundary
