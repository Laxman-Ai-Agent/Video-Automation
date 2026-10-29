"""Sound design (VIDEO_ENGINE/stages/sound_design.py), with real ffmpeg on synthetic audio: the mix is -14 LUFS with a safe peak and exactly the narration's length, a whoosh sits at each cut,
the music bed is ducked under speech and is used ONLY with complete provenance, and the mix is rebuilt only when its inputs change. Run: python -m pytest tests/test_sound_design.py -q"""
import json
import subprocess
import wave
from pathlib import Path

import numpy as np
import pytest

from VIDEO_ENGINE.stages import sound_design as sd


def _ff(*args):
    subprocess.run(["ffmpeg", "-hide_banner", "-v", "error", "-y", *args], check=True, capture_output=True)


def _narration(path: Path, seconds: int, on_s: float, period_s: float, amp: float = 0.06):
    """A quiet 220 Hz 'voice' that speaks on_s seconds out of every period_s."""
    _ff("-f", "lavfi", "-i", f"aevalsrc={amp}*sin(2*PI*220*t)*lt(mod(t\\,{period_s})\\,{on_s}):s=48000:d={seconds}", "-ac", "2", str(path))


def _project(tmp_path, seconds=8, cuts=(48, 168), on_s=1.2, period_s=2.0, name="p"):
    pdir = tmp_path / name
    pdir.mkdir()
    nar = pdir / "audio.wav"
    _narration(nar, seconds, on_s, period_s)
    (pdir / "timeline.json").write_text(json.dumps({"transitions": [{"boundary_frame": f, "supported": True} for f in cuts]}), encoding="utf-8")
    return pdir, nar


def _samples(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as w:
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768.0
        return data.reshape(-1, w.getnchannels()).mean(axis=1), w.getframerate()


def _rms(x, sr, a, b):
    seg = x[int(a * sr):int(b * sr)]
    return float(np.sqrt(np.mean(seg ** 2)) + 1e-12)


def _tone_level(x, sr, a, b, hz):
    seg = x[int(a * sr):int(b * sr)] * np.hanning(int(b * sr) - int(a * sr))
    spec = np.abs(np.fft.rfft(seg))
    freqs = np.fft.rfftfreq(len(seg), 1 / sr)
    return float(spec[(freqs > hz - 6) & (freqs < hz + 6)].max() + 1e-12)


def _bed(pdir: Path, provenance: dict | None):
    folder = pdir / "assets" / "music"
    folder.mkdir(parents=True)
    _ff("-f", "lavfi", "-i", "sine=f=440:duration=5", "-ac", "2", str(folder / "bed.wav"))
    if provenance is not None:
        (folder / "bed.json").write_text(json.dumps(provenance), encoding="utf-8")


GOOD = {"source_url": "https://example.org/track", "license_name": "CC0 1.0", "attribution_text": "Track by Ann (CC0)", "commercial_use_known": True}


def test_the_mix_is_14_lufs_safe_and_exactly_as_long_as_the_narration(tmp_path):
    pdir, nar = _project(tmp_path)
    rep = sd.build(pdir, nar)
    assert abs(rep["loudness"]["integrated_lufs"] - sd.TARGET_LUFS) <= sd.LOUDNESS_TOLERANCE and rep["loudness"]["true_peak_dbtp"] <= sd.TRUE_PEAK_DB + 0.5
    assert rep["loudness_before_normalisation"]["input_i"] < -18                                    # the narration is quiet: the normalisation is a real gain
    x, sr = _samples(pdir / sd.MIX)
    assert sr == sd.SAMPLE_RATE and abs(len(x) / sr - rep["duration_s"]) <= 1 / sd.FPS and abs(rep["duration_s"] - 8.0) < 0.05
    assert rep["cuts_s"] == [1.6, 5.6] and (pdir / sd.REPORT).exists()
    assert np.abs(x).max() < 0.95                                                                  # no clipping


def test_a_whoosh_sits_at_every_cut_in_a_silent_stretch_of_the_narration(tmp_path):
    with_cuts, nar1 = _project(tmp_path, name="a")
    no_cuts, nar2 = _project(tmp_path, cuts=(), name="b")
    sd.build(with_cuts, nar1)
    sd.build(no_cuts, nar2)
    a, sr = _samples(with_cuts / sd.MIX)
    b, _ = _samples(no_cuts / sd.MIX)
    for cut in (1.6, 5.6):                                          # the narration is silent from 1.2-2.0 and 5.2-6.0
        assert _rms(a, sr, cut - 0.2, cut + 0.3) > 20 * _rms(b, sr, cut - 0.2, cut + 0.3)
    assert _rms(a, sr, 0.2, 0.9) == pytest.approx(_rms(b, sr, 0.2, 0.9), rel=0.15)                 # the voice far from a cut is the same


def test_the_music_bed_is_ducked_under_speech(tmp_path):
    pdir, nar = _project(tmp_path, seconds=12, cuts=(), on_s=1.0, period_s=4.0)                    # speaks 0-1, 4-5, 8-9 s
    _bed(pdir, GOOD)
    rep = sd.build(pdir, nar)
    assert rep["music"]["ducked"] and rep["music"]["provenance"]["license_name"] == "CC0 1.0" and rep["music_not_used"] is None
    x, sr = _samples(pdir / sd.MIX)
    speech = _tone_level(x, sr, 4.15, 4.9, 440)                                                    # the 440 Hz music while the voice speaks (after the fade-in)
    quiet = _tone_level(x, sr, 6.4, 7.5, 440)                                                      # the same music in a pause
    assert 20 * np.log10(quiet / speech) >= 6                                                      # ducked by at least 6 dB under speech


@pytest.mark.parametrize("prov", [None, {**GOOD, "source_url": ""}, {**GOOD, "license_name": ""}, {**GOOD, "attribution_text": ""}, {**GOOD, "commercial_use_known": False}, {**GOOD, "commercial_use_known": None}])
def test_music_without_complete_provenance_and_known_rights_is_not_used(tmp_path, prov):
    pdir, nar = _project(tmp_path)
    _bed(pdir, prov)
    rep = sd.build(pdir, nar)
    assert rep["music"] is None and "not used" in rep["music_not_used"]


def test_no_music_folder_is_fine(tmp_path):
    pdir, nar = _project(tmp_path)
    assert sd.build(pdir, nar)["music"] is None


def test_the_mix_is_rebuilt_only_when_its_inputs_change(tmp_path):
    pdir, nar = _project(tmp_path)
    first = sd.build(pdir, nar)
    again = sd.build(pdir, nar)
    assert first["reused"] is False and again["reused"] is True and again["input_digest"] == first["input_digest"]
    (pdir / "timeline.json").write_text(json.dumps({"transitions": [{"boundary_frame": 100, "supported": True}]}), encoding="utf-8")       # a cut moved
    moved = sd.build(pdir, nar)
    assert moved["reused"] is False and moved["cuts_s"] == [3.333] and moved["input_digest"] != first["input_digest"]


def test_the_render_fingerprint_inputs_change_with_the_music_and_its_provenance(tmp_path):
    pdir, nar = _project(tmp_path)
    plain = sd._digest(sd.inputs(pdir, nar))
    _bed(pdir, GOOD)
    with_music = sd._digest(sd.inputs(pdir, nar))
    (pdir / "assets" / "music" / "bed.json").write_text(json.dumps({**GOOD, "license_name": "CC BY 4.0"}), encoding="utf-8")
    assert len({plain, with_music, sd._digest(sd.inputs(pdir, nar))}) == 3


def test_the_render_plays_the_mix_when_there_is_one_and_the_narration_otherwise(tmp_path):
    pdir, nar = _project(tmp_path)
    assert sd.audio_for_render(pdir, nar) == nar
    sd.build(pdir, nar)
    assert sd.audio_for_render(pdir, nar) == pdir / sd.MIX


def test_a_mix_that_misses_the_loudness_is_refused_and_nothing_half_made_is_left(tmp_path, monkeypatch):
    pdir, nar = _project(tmp_path)
    real, calls = sd._loudness, []

    def measure(path, extra=""):
        calls.append(path)
        m = real(path, extra)
        return {**m, "input_i": -20.0} if len(calls) == 2 else m                                    # the second measurement (of the finished mix) is far from -14
    monkeypatch.setattr(sd, "_loudness", measure)
    with pytest.raises(sd.SoundDesignError, match="LUFS"):
        sd.build(pdir, nar)
    assert not (pdir / sd.MIX).exists() and not (pdir / sd.REPORT).exists()                          # the render would otherwise play a wrong mix


def test_the_render_stages_the_mix_and_the_render_stage_fingerprint_follows_the_sound_design(tmp_path, monkeypatch):
    from SYSTEM.policies import llm_review
    from VIDEO_ENGINE.stages import render
    pdir, nar = _project(tmp_path)
    remotion = tmp_path / "remotion"
    monkeypatch.setattr(render.config, "REMOTION_DIR", remotion)
    (pdir / "composition.json").write_text(json.dumps({"meta": {"audio": "audio_x.wav"}}), encoding="utf-8")
    plain = render.stage_audio(pdir)
    assert plain.read_bytes() == nar.read_bytes()                                                  # no mix yet: the narration, as before
    fp0 = llm_review.compute_stage_input_fingerprint(pdir, "render")
    sd.build(pdir, nar)
    assert render.stage_audio(pdir).read_bytes() == (pdir / sd.MIX).read_bytes()                  # the mix is what Remotion plays
    _bed(pdir, GOOD)
    assert llm_review.compute_stage_input_fingerprint(pdir, "render") != fp0                       # a music bed makes the Render stage stale (and with it QC and Final)
    assert llm_review.compute_stage_input_fingerprint(pdir, "assets") == llm_review.compute_stage_input_fingerprint(pdir, "assets")


def test_a_render_made_before_the_sound_design_or_with_another_mix_is_never_reused(tmp_path, monkeypatch):
    """Found on the real project (2026-10-29): the render agent reused out.mp4 because the approved timeline was unchanged, so the new mix never reached the video."""
    from VIDEO_ENGINE.stages import render_video
    pdir, nar = _project(tmp_path)
    old_report = {"input_fingerprints": {"approved_version": "x"}}                                   # a report from before the sound design existed
    assert not render_video.sound_current(pdir, "16:9", old_report)
    current = {"input_fingerprints": {"approved_version": "x", "sound_design": sd.fingerprint(pdir)}}
    assert render_video.sound_current(pdir, "16:9", current)
    _bed(pdir, GOOD)                                                                                 # a music bed arrives: the video must be rendered again
    assert not render_video.sound_current(pdir, "16:9", current)
    (pdir / "timeline.json").write_text(json.dumps({"transitions": []}), encoding="utf-8")           # or a cut moves
    assert sd.fingerprint(pdir) != current["input_fingerprints"]["sound_design"]
