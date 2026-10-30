"""Tool smoke test of Render Video (Stage 13): the INSTALLED Remotion renders a small fixture composition (one real scene of the fixture project, 3 s, 1920x1080, with its audio) to the temporary target the stage asks for
(`render.render(..., out=)`), and Stage 13's own verifier accepts the encoded file against what the composition asks for. Everything else in the Stage 13 / 14 tests replaces the renderer with a real mp4 made by ffmpeg;
this is the one test where the real renderer runs. It never touches a real project. Run: python -m pytest tests/test_render_smoke.py -q"""
import importlib
import io
import json
import math
import struct
import wave

from backend import media_probe as mprobe, render, render_video as rv

_rv = importlib.import_module("test_render_video")
built = _rv.built


def test_the_installed_remotion_renders_a_small_composition_to_a_temp_target_and_the_stage_verifies_the_file(built, tmp_path):
    comp = json.loads((built / "composition.json").read_text(encoding="utf-8"))
    scene = {**comp["scenes"][0], "end": 3.0}
    scene.pop("transition_out", None)
    comp["scenes"], comp["words"] = [scene], [w for w in comp.get("words", []) if w["end"] <= 3.0]
    comp["meta"]["duration"] = 3.0
    d = tmp_path / "smoke"
    d.mkdir()
    (d / "composition.json").write_text(json.dumps(comp, ensure_ascii=False), encoding="utf-8")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:                                                                              # a tone, not silence: the sound design measures the narration's loudness and cannot normalise a silent file (Stage 1 never lets one through)
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / 16000))) for i in range(3 * 16000)))
    wav = buf.getvalue()
    for name in {"audio.wav", comp["meta"]["audio"]}:
        (d / name).write_bytes(wav)
    out = d / "out.rendering-smoke.mp4"
    seen = []
    got = render.render(d, False, lambda percent, eta=None: seen.append(percent), aspect="16:9", out=out)
    assert got == out and out.is_file() and not (d / "out.mp4").exists()                                         # the temp target was written, the final slot was not
    exp = rv.expected(d, "16:9")
    assert (exp["width"], exp["height"], exp["fps"], exp["frames"]) == (1920, 1080, 30, 90)
    observed, checks = rv.verify_output(out, exp, 3.0)
    assert not [c for c in checks if c["status"] == "failed"], [(c["id"], c["observed"], c["expected"]) for c in checks if c["status"] == "failed"]
    assert observed["video_stream_present"] and observed["audio_stream_present"] and observed["video_codec"] == "h264" and observed["frame_count"] == 90 and seen and 90 <= seen[-1] < 100.0              # the renderer reports frames up to its last chunk and finishes encoding afterwards: it never says 100 itself
    assert mprobe.sha256_file(out)
