"""Whisper is chunked: every finished chunk is checkpointed, so a restart or crash continues after the last finished chunk instead of from 0%."""
import sys
import types

import numpy as np
import pytest

from backend import audio_analysis as aa
from backend import transcribe

CHUNKS = [(0.0, 3.0), (3.0, 6.0), (6.0, 9.0)]


class Interrupted(Exception):
    pass


@pytest.fixture
def whisper(tmp_path, monkeypatch):
    """A fake Whisper: chunk i answers one segment 'c<i>'; `calls` lists the chunks it was asked for, `fail_on` kills the run on that chunk."""
    state = types.SimpleNamespace(calls=[], fail_on=None, chunks=CHUNKS)

    class FW:
        def __init__(self, w, a, b):
            self.word, self.start, self.end, self.probability = w, a, b, 0.9

    class FM:
        def __init__(self, *a, **k):
            pass

        def transcribe(self, pcm, **k):
            i = int(pcm[0] // 16000 // 3)
            state.calls.append(i)
            if state.fail_on == i:
                raise Interrupted()
            seg = types.SimpleNamespace(start=0.0, end=1.0, text=f" c{i}", words=[FW(" a", 0.0, 0.5), FW(" b", 0.5, 1.0)])
            return [seg], None

    fw, audio_mod = types.ModuleType("faster_whisper"), types.ModuleType("faster_whisper.audio")
    fw.WhisperModel, audio_mod.decode_audio = FM, lambda path, sampling_rate: np.arange(16000 * 9, dtype="float32")
    monkeypatch.setitem(sys.modules, "faster_whisper", fw)
    monkeypatch.setitem(sys.modules, "faster_whisper.audio", audio_mod)
    (tmp_path / "audio.wav").write_bytes(b"x")
    monkeypatch.setattr(aa, "probe", lambda p: {})
    monkeypatch.setattr(transcribe, "to_wav16k", lambda a, b: b)
    monkeypatch.setattr(transcribe, "duration", lambda p: 9.0)
    monkeypatch.setattr(transcribe, "is_silent", lambda p: False)
    monkeypatch.setattr(transcribe, "chunk_points", lambda p, a, b: state.chunks)
    return state


def _texts(t):
    return [(s.id, s.text, round(s.start, 1)) for s in t.segments]


def test_an_interrupted_run_continues_after_its_last_finished_chunk(tmp_path, whisper):
    expected = _texts(transcribe.transcribe(tmp_path))
    (tmp_path / "transcript.json").unlink()
    (tmp_path / ".audio.sha1").unlink()
    whisper.calls.clear()

    whisper.fail_on = 2                                                   # killed while the 3rd chunk runs
    with pytest.raises(Interrupted):
        transcribe.transcribe(tmp_path)
    assert whisper.calls == [0, 1, 2] and (tmp_path / transcribe.PARTIAL).exists() and not (tmp_path / "transcript.json").exists()

    whisper.fail_on, whisper.calls[:] = None, []
    seen = []
    t = transcribe.transcribe(tmp_path, progress=seen.append)
    assert whisper.calls == [2]                                           # chunks 0 and 1 are not transcribed again
    assert _texts(t) == expected                                          # the same transcript an uninterrupted run gives, ids included
    assert seen[0] == pytest.approx(100 * 6 / 9) and seen[-1] == pytest.approx(100)     # shows where it continues, not 0%
    assert not (tmp_path / transcribe.PARTIAL).exists()                   # the checkpoint is gone once the transcript is complete


def test_a_checkpoint_of_other_audio_or_other_chunking_is_ignored(tmp_path, whisper):
    whisper.fail_on = 1
    with pytest.raises(Interrupted):
        transcribe.transcribe(tmp_path)
    whisper.fail_on, whisper.calls[:] = None, []

    whisper.chunks = [(0.0, 4.5), (4.5, 9.0)]                             # chunked differently: the saved chunks do not apply
    transcribe.transcribe(tmp_path)
    assert whisper.calls == [0, 1]

    (tmp_path / "transcript.json").unlink()
    (tmp_path / ".audio.sha1").unlink()
    whisper.chunks = CHUNKS
    whisper.fail_on = 2
    with pytest.raises(Interrupted):
        transcribe.transcribe(tmp_path)
    (tmp_path / "audio.wav").write_bytes(b"another recording")           # the audio changed: the saved chunks are of the old one
    whisper.fail_on, whisper.calls[:] = None, []
    transcribe.transcribe(tmp_path)
    assert whisper.calls == [0, 1, 2]


def test_a_damaged_checkpoint_is_ignored(tmp_path, whisper):
    (tmp_path / transcribe.PARTIAL).write_text('{"key": "x", "chunks": [', encoding="utf-8")
    t = transcribe.transcribe(tmp_path)
    assert whisper.calls == [0, 1, 2] and len(t.segments) == 3
