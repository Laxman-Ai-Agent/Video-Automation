"""The interim analyzer report (before audio_analysis.json exists) measures the audio with ffprobe, like the finished report, and says so truthfully."""
import subprocess

from backend import step_llm_check


def _audio(path, secs=2):
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency=440:duration={secs}", str(path)], capture_output=True, check=True)


def _step(rep, n):
    return next(s for s in rep["stages"] if s["n"] == n)


def test_interim_report_measures_any_format_with_ffprobe(tmp_path):
    for name, codec in (("audio.wav", "pcm_s16le"), ("audio.flac", "flac")):     # the old wave-module reading could not open a flac
        pdir = tmp_path / name.split(".")[1]
        pdir.mkdir()
        _audio(pdir / name)
        rep = step_llm_check.synthesize_analyzer_stages(pdir)
        assert rep["source"]["metadata_source"] == "ffprobe" and rep["source"]["codec"] == codec
        assert abs(rep["source"]["duration_seconds"] - 2) < 0.1 and rep["source"]["sample_rate_hz"] and rep["source"]["channels"] == 1
        assert _step(rep, 2)["detail"].endswith("probed via ffprobe") and _step(rep, 2)["status"] == "completed"
        assert _step(rep, 1)["status"] == "completed"


def test_interim_report_fails_steps_1_and_2_for_an_unreadable_file(tmp_path):
    (tmp_path / "audio.wav").write_bytes(b"not audio at all")
    rep = step_llm_check.synthesize_analyzer_stages(tmp_path)
    assert rep["source"] == {} and rep["validation"]["status"] == "failed" and rep["validation"]["errors"]
    assert _step(rep, 1)["status"] == _step(rep, 2)["status"] == "failed"
    assert _step(rep, 1)["detail"] == rep["validation"]["errors"][0]


def test_interim_report_without_audio_waits(tmp_path):
    rep = step_llm_check.synthesize_analyzer_stages(tmp_path)
    assert _step(rep, 1)["status"] == _step(rep, 2)["status"] == "pending"
