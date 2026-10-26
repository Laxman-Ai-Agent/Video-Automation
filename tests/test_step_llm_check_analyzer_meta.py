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
    assert _step(rep, 1)["detail"] == rep["validation"]["errors"][0]["message"]


def test_a_check_made_on_other_measured_facts_is_not_current(tmp_path):
    """A step whose text stays the same but whose evidence changed (wave -> ffprobe) must be checked again."""
    _audio(tmp_path / "audio.wav")
    rep = step_llm_check.synthesize_analyzer_stages(tmp_path)
    step = _step(rep, 2)
    assert step_llm_check._hash(step, rep) == step_llm_check._hash(step, step_llm_check.synthesize_analyzer_stages(tmp_path))     # same facts: same check
    old = {**rep, "source_fingerprint": "evidence-as-the-wave-module-reported-it"}
    assert step_llm_check._hash(step, rep) != step_llm_check._hash(step, old)


def test_step_evidence_holds_what_the_step_detail_says():
    """The LLM check sees this stage's own findings: step 10 its timestamp warnings (dicts), step 1 not the status of the whole analysis."""
    warn = {"stage": "Word Timestamp Integrity", "code": "segment_without_words", "message": "segment 1 has text but no word timings"}
    other = {"stage": "Word-Level Alignment", "code": "alignment_incomplete", "message": "some or all segments have no word times"}
    report = {"source": {"file": "audio.wav"}, "validation": {"status": "warning", "errors": [], "warnings": [warn, other]}, "utterances": [{"words": [1, 2]}]}
    ev10 = step_llm_check.build_step_evidence("analyzer", {"n": 10, "name": "Word Timestamp Integrity", "detail": "0 errors, 1 warnings", "status": "warning"}, report)
    assert ev10["word_timestamp_warnings"] == [warn] and ev10["word_timestamp_errors"] == [] and ev10["total_words"] == 2
    ev1 = step_llm_check.build_step_evidence("analyzer", {"n": 1, "name": "Audio File Validation", "detail": "file readable", "status": "completed"}, report)
    assert ev1["file_validation"] == {"errors": [], "warnings": []} and "validation_status" not in ev1


def test_interim_report_claims_nothing_it_did_not_measure(tmp_path):
    """Before audio_analysis.json exists nothing has validated timestamps, alignment or quality: those steps wait instead of saying 'passed'."""
    _audio(tmp_path / "audio.wav")
    for n in ("audio_16k.wav", "transcript.json", "cuts.json"):
        (tmp_path / n).write_bytes(b"x")
    (tmp_path / "transcript_review.json").write_text('{"llm": {"status": "applied"}}', encoding="utf-8")
    rep = step_llm_check.synthesize_analyzer_stages(tmp_path)
    for n in (9, 10, 12, 13):
        assert _step(rep, n)["status"] == "pending" and _step(rep, n)["detail"].startswith("measured when audio_analysis.json") and _step(rep, n)["checks_passed"] == 0
    claims = " ".join(s["detail"] for s in rep["stages"]).lower()
    assert not any(x in claims for x in ("0 errors", "forced alignment", "monotonic", "snr"))
    assert _step(rep, 8)["status"] == "completed" and "applied" in _step(rep, 8)["detail"]
    (tmp_path / "transcript_review.json").write_text('{"llm": {"status": "failed"}}', encoding="utf-8")      # the LLM check did not happen: it is not 'finished'
    rep = step_llm_check.synthesize_analyzer_stages(tmp_path)
    assert _step(rep, 8)["status"] == "pending" and "failed" in _step(rep, 8)["detail"]


def test_interim_report_without_audio_waits(tmp_path):
    rep = step_llm_check.synthesize_analyzer_stages(tmp_path)
    assert _step(rep, 1)["status"] == _step(rep, 2)["status"] == "pending"
