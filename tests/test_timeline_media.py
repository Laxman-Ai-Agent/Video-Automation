"""Read-only media of the Timeline page (backend/timeline_media.py). Run: python -m pytest tests/test_timeline_media.py -q"""
import json
import wave

from backend import timeline_media as tm


def _wav(path, seconds=2, rate=16000, loud_from=1.0):
    frames = bytearray()
    for i in range(int(seconds * rate)):
        v = 20000 if i / rate >= loud_from else 200
        frames += int(v if i % 2 else -v).to_bytes(2, "little", signed=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))


def test_waveform_peaks_follow_the_real_audio_and_are_cached(tmp_path):
    _wav(tmp_path / "audio_16k.wav")
    w = tm.waveform(tmp_path)
    assert w["per_second"] == tm.PER_SECOND and w["duration_seconds"] == 2.0
    assert len(w["peaks"]) == 2 * tm.PER_SECOND
    assert max(w["peaks"]) == 1.0 and w["peaks"][0] < 0.05 and w["peaks"][-1] == 1.0       # quiet first second, loud second
    assert json.loads((tmp_path / tm.CACHE).read_text(encoding="utf-8"))["key"] == w["key"]
    (tmp_path / tm.CACHE).write_text(json.dumps({**w, "peaks": [0.5]}), encoding="utf-8")
    assert tm.waveform(tmp_path)["peaks"] == [0.5]                                          # same file, the cache is used


def test_no_analyzer_wav_means_no_waveform(tmp_path):
    assert tm.waveform(tmp_path) is None


def test_audio_file_is_a_plain_name_inside_the_project(tmp_path):
    (tmp_path / "audio.mp3").write_bytes(b"x")
    assert tm.audio_file(tmp_path, "audio.mp3") == tmp_path / "audio.mp3"
    for bad in ("../audio.mp3", "sub/audio.mp3", "", "C:\\x.mp3", "missing.mp3"):
        assert tm.audio_file(tmp_path, bad) is None
