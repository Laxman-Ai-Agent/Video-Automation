"""audio_analysis.json: probe errors, timing checks, atomic file, endpoint. Run: python -m pytest tests/test_audio_analysis.py -q"""
import importlib
import json
import shutil
import subprocess

import pytest

from backend import audio_analysis as aa
from backend import config
from backend.diagnose import UserProblem

_m7 = importlib.import_module("test_m7")
client, create = _m7.client, _m7.create


def _wav(path, secs=2):
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency=440:duration={secs}", str(path)], capture_output=True, check=True)


def test_probe_rejects_empty_garbage_and_missing(tmp_path):
    (tmp_path / "e.wav").write_bytes(b"")
    (tmp_path / "g.wav").write_bytes(b"not audio at all")
    for n in ("e.wav", "g.wav", "none.wav"):
        with pytest.raises(UserProblem):
            aa.probe(tmp_path / n)


def test_probe_measures_a_real_file(tmp_path):
    _wav(tmp_path / "a.wav")
    p = aa.probe(tmp_path / "a.wav")
    assert abs(p["duration_seconds"] - 2) < 0.1 and p["channels"] == 1 and p["metadata_source"] == "ffprobe" and p["sample_rate_hz"]


def test_timing_checks_catch_bad_times_and_untimed_segments():
    w = lambda i, a, b: {"index": i, "text": "x", "start_seconds": a, "end_seconds": b}
    u = [{"id": 0, "start_seconds": 0, "end_seconds": 1, "words": [w(0, 0, 0.5), w(1, 0.4, 0.3)]},
         {"id": 1, "start_seconds": 1, "end_seconds": 9, "words": []}]
    err, warn = aa.check_timing(u, 2.0)
    codes = {e["code"] for e in err} | {x["code"] for x in warn}
    assert {"word_out_of_range", "segment_out_of_range", "segment_without_words"} <= codes
    assert aa.check_timing([{"id": 0, "start_seconds": 0, "end_seconds": 1, "words": [w(0, 0, 1)]}], 1.0) == ([], [])


def test_endpoint_builds_once_from_the_files_and_keeps_the_transcript_untouched(client):
    pid = create(client).json()["id"]
    assert client.get(f"/projects/{pid}/analysis").json()["error"]["code"] == "analysis_missing"
    pdir = config.PROJECTS_DIR / pid
    for f in pdir.glob("audio.*"):
        f.unlink()
    _wav(pdir / "audio.wav", 3)
    tr = {"language": "te", "duration": 3.0, "segments": [{"id": 0, "start": 0.2, "end": 2.5, "text": "నమస్తే అందరికీ", "words": [{"w": "నమస్తే", "start": 0.2, "end": 1.0}, {"w": "అందరికీ", "start": 1.1, "end": 2.5}]}]}
    (pdir / "transcript.json").write_text(json.dumps(tr, ensure_ascii=False), encoding="utf-8")
    before = (pdir / "transcript.json").read_bytes()
    d = client.get(f"/projects/{pid}/analysis").json()
    assert d["schema_version"] == aa.SCHEMA and d["validation"]["status"] in ("ok", "warning") and [s["name"] for s in d["stages"]][-1] == "Caching & Resume" and len(d["stages"]) == 14
    assert d["utterances"][0]["text"] == "నమస్తే అందరికీ" and d["utterances"][0]["words"][1]["end_seconds"] == 2.5
    assert d["transcription"]["language"]["confidence"] is None                      # nothing invented
    assert (pdir / "audio_analysis.json").exists() and not (pdir / "audio_analysis.json.part").exists()
    assert (pdir / "transcript.json").read_bytes() == before
    (pdir / "audio_analysis.json").write_text("{bad", encoding="utf-8")
    assert client.get(f"/projects/{pid}/analysis").json()["error"]["code"] == "analysis_unreadable"


# ---------- a segment that ends before its last word: look at the audio before changing anything ----------
def _end_mismatch_project(tmp_path, mute=None, copy=True):
    """Segment 0 ends at 1.0 s but its last word ends at 1.4 s, and segment 1 starts at 1.4 s. The audio is a tone, optionally silent from `mute[0]` to `mute[1]`."""
    from backend.transcribe import Segment, Transcript, Word
    af = f"volume=enable='between(t,{mute[0]},{mute[1]})':volume=0" if mute else "anull"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=300:duration=3", "-af", af, "-ar", "16000", "-ac", "1", str(tmp_path / "audio.wav")], capture_output=True, check=True)
    if copy:
        shutil.copyfile(tmp_path / "audio.wav", tmp_path / "audio_16k.wav")
    w0 = [Word(w="ఒకటి", start=0.0, end=0.5), Word(w="రెండు.", start=0.5, end=1.4)]
    w1 = [Word(w="మూడు", start=1.4, end=2.0), Word(w="నాలుగు.", start=2.0, end=2.8)]
    t = Transcript(language="te", duration=3.0, segments=[Segment(id=0, start=0.0, end=1.0, text="ఒకటి రెండు.", words=w0), Segment(id=1, start=1.4, end=2.8, text="మూడు నాలుగు.", words=w1)])
    (tmp_path / "transcript.json").write_text(t.model_dump_json(), encoding="utf-8")
    return aa.build(tmp_path)


def test_a_last_word_that_reaches_into_a_silent_pause_is_explained_not_changed(tmp_path):
    d = _end_mismatch_project(tmp_path, mute=(1.0, 1.4))
    note = d["validation"]["notes"][0]
    u = {x["id"]: x for x in d["utterances"]}
    assert note["code"] == "word_end_in_silence" and note["audio_check"] == "silence in the gap" and "matches the audio" in note["message"]
    assert u[0]["end_seconds"] == 1.0 and u[0]["words"][-1]["end_seconds"] == 1.4                      # nothing is changed: no timestamp is invented
    assert not any("could not be confirmed" in w["message"] for w in d["validation"]["warnings"])


def test_a_segment_end_is_extended_only_when_the_audio_has_sound_in_the_gap(tmp_path):
    d = _end_mismatch_project(tmp_path)                                                              # a continuous tone: sound everywhere
    note = d["validation"]["notes"][0]
    assert note["code"] == "segment_end_adjusted" and note["audio_check"] == "sound in the gap"
    assert {x["id"]: x for x in d["utterances"]}[0]["end_seconds"] == 1.4


def test_without_audio_to_check_nothing_is_changed_and_a_warning_says_so(tmp_path):
    d = _end_mismatch_project(tmp_path, copy=False)
    note = d["validation"]["notes"][0]
    assert note["code"] == "segment_end_unconfirmed" and "not checked" in note["audio_check"]
    assert {x["id"]: x for x in d["utterances"]}[0]["end_seconds"] == 1.0
    assert any(w["code"] == "segment_end_unconfirmed" for w in d["validation"]["warnings"]) and d["stages"][9]["status"] == "warning"


def test_transcribe_never_ends_a_segment_before_its_last_word(tmp_path, monkeypatch):
    import sys
    import types

    import numpy as np

    from backend import transcribe

    class FW:
        def __init__(self, w, a, b):
            self.word, self.start, self.end, self.probability = w, a, b, 0.9

    class FS:
        start, end, text = 0.0, 1.0, " ఒకటి రెండు"
        words = [FW(" ఒకటి", 0.0, 0.5), FW(" రెండు", 0.5, 1.4)]

    class FM:
        def __init__(self, *a, **k):
            pass

        def transcribe(self, pcm, **k):
            return [FS()], None

    fw, audio_mod = types.ModuleType("faster_whisper"), types.ModuleType("faster_whisper.audio")
    fw.WhisperModel, audio_mod.decode_audio = FM, lambda path, sampling_rate: np.zeros(16000 * 3, dtype="float32")
    monkeypatch.setitem(sys.modules, "faster_whisper", fw)
    monkeypatch.setitem(sys.modules, "faster_whisper.audio", audio_mod)
    (tmp_path / "audio.wav").write_bytes(b"x")
    monkeypatch.setattr(aa, "probe", lambda p: {})
    monkeypatch.setattr(transcribe, "to_wav16k", lambda a, b: b)
    monkeypatch.setattr(transcribe, "duration", lambda p: 3.0)
    monkeypatch.setattr(transcribe, "is_silent", lambda p: False)
    monkeypatch.setattr(transcribe, "chunk_points", lambda p, a, b: [(0.0, 3.0)])
    t = transcribe.transcribe(tmp_path)
    assert t.segments[0].end == 1.4 and t.segments[0].words[-1].end == 1.4


# ---------- clipping: a peak at 0 dB is not clipping ----------
def test_a_few_samples_at_full_scale_are_not_clipping(monkeypatch):
    """Real case (07-5df8): max -0.0 dB with 37 of 1,246,343 samples in the top bin is a peak-normalized recording, not a clipped one."""
    out = "n_samples: 0\nn_samples: 1246343\nmean_volume: -19.1 dB\nmax_volume: -0.0 dB\nhistogram_0db: 37\n"
    monkeypatch.setattr(aa, "_run", lambda cmd: out)
    q = aa.quality(shutil.which("ffmpeg") and __import__("pathlib").Path("x.wav"))
    assert q["max_volume_db"] == -0.0 and q["peak_samples"] == 37 and q["peak_share"] < aa.CLIP_SHARE


def test_a_really_clipped_file_is_over_the_clipping_share(tmp_path):
    f = tmp_path / "clipped.wav"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2,volume=8,alimiter=limit=1:level=disabled", str(f)], capture_output=True, check=True)
    q = aa.quality(f)
    assert q["peak_share"] >= aa.CLIP_SHARE
