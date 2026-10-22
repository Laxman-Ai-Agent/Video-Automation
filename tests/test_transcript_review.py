"""Stages 6-9 (backend/transcript_review.py) and their caching: raw transcript preserved, checked Claude corrections, estimated timings inside the replaced span, no fake success.
Run: python -m pytest tests/test_transcript_review.py -q"""
import json

import pytest

from backend import pipeline, promptgen
from backend import transcript_review as tr
from backend.transcribe import Segment, Transcript, Word, load_transcript


def W(w, a, b, p=0.9):
    return Word(w=w, start=a, end=b, p=p)


def make(pdir, p_bad=0.2):
    t = Transcript(language="te", duration=10.0, segments=[
        Segment(id=0, start=0, end=4, text="a", words=[W("నమస్తే", 0, 1), W("ఫాస్ట్", 1, 2, p_bad), W("API", 2, 3), W("2024", 3, 4)]),
        Segment(id=1, start=4, end=9, text="b", words=[W("సరే", 4, 5), W("అవును", 5, 9)])])
    (pdir / "transcript.json").write_text(t.model_dump_json(indent=1), encoding="utf-8")
    return t


def answer(*cs):
    return json.dumps({"corrections": list(cs)}, ensure_ascii=False)


GOOD = {"segment": 0, "from_index": 1, "to_index": 1, "from": "ఫాస్ట్", "to": "ఫాస్ట్ఏపీఐ", "reason": "misheard"}


class Ask:
    def __init__(self, reply):
        self.reply, self.calls = reply, 0

    def __call__(self, user, system="", timeout=0):
        self.calls += 1
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def test_vocabulary_finds_english_terms_and_numbers_by_script(tmp_path):
    t = make(tmp_path)
    terms = {x["text"]: x["kind"] for x in tr.vocabulary(t, {"సరే"})}
    assert terms == {"API": "english", "2024": "number", "సరే": "listed"}


def test_uncertain_uses_only_real_probabilities(tmp_path):
    t = make(tmp_path)
    c = tr.uncertain(t)
    assert c["status"] == "available" and [(f["segment"], f["index"]) for f in c["flagged"]] == [(0, 1)]
    old = Transcript(language="te", duration=1, segments=[Segment(id=0, start=0, end=1, text="x", words=[Word(w="x", start=0, end=1)])])
    assert tr.uncertain(old) == {"status": "unavailable", "threshold": tr.LOW_P, "words_total": 1, "words_with_confidence": 0, "flagged": []}


def test_only_checked_corrections_are_applied(tmp_path):
    t = make(tmp_path)
    flagged = tr.uncertain(t)["flagged"]
    bad = [{**GOOD, "from": "వేరే"}, {**GOOD, "from_index": 0, "to_index": 0, "from": "నమస్తే"}, {**GOOD, "to": "ఒకటి రెండు మూడు నాలుగు"}, {"segment": 9}, GOOD, GOOD]
    out = tr.validate_corrections(t, bad, flagged)
    assert [c["why"] for c in out] == ["from_mismatch", "not_uncertain", "adds_words", "malformed", None, "overlaps_another"]
    assert [c["status"] for c in out].count("applied") == 1


def test_corrected_words_get_estimated_times_inside_the_replaced_span_and_raw_is_untouched(tmp_path):
    t = make(tmp_path)
    c = tr.validate_corrections(t, [{**GOOD, "to": "ఫాస్ట్ ఏపీఐ"}], tr.uncertain(t)["flagged"])
    fixed, n = tr.apply_corrections(t, c)
    ws = fixed.segments[0].words
    assert n == 2 and [w.w for w in ws] == ["నమస్తే", "ఫాస్ట్", "ఏపీఐ", "API", "2024"]
    new = [w for w in ws if w.edit == "llm"]
    assert all(w.timing == "estimated" and w.p is None and 1.0 <= w.start < w.end <= 2.0 for w in new) and new[0].end == pytest.approx(new[1].start)
    assert ws[0].timing is None and ws[0].start == 0 and t.segments[0].words[1].w == "ఫాస్ట్"      # untouched words keep Whisper's timestamp; the input object is not changed


def test_refine_writes_review_and_corrected_file_and_keeps_raw(tmp_path):
    make(tmp_path)
    raw = (tmp_path / "transcript.json").read_bytes()
    ask = Ask(answer(GOOD))
    r = tr.refine(tmp_path, ask=ask)
    assert ask.calls == 1 and r["llm"]["status"] == "applied" and r["alignment"]["status"] == "estimated_for_edits" and r["unresolved"] == []
    assert (tmp_path / "transcript.json").read_bytes() == raw
    assert load_transcript(tmp_path).segments[0].words[1].w == "ఫాస్ట్ఏపీఐ"               # downstream reads the corrected layer
    assert json.loads((tmp_path / "transcript_review.json").read_text(encoding="utf-8"))["corrected_file"] == "transcript_corrected.json"


def test_same_question_is_not_asked_twice(tmp_path):
    make(tmp_path)
    ask = Ask(answer(GOOD))
    tr.refine(tmp_path, ask=ask)
    r = tr.refine(tmp_path, ask=ask)
    assert ask.calls == 1 and r["llm"]["status"] == "cached"


def test_claude_unavailable_keeps_the_raw_transcript_and_says_so(tmp_path):
    make(tmp_path)
    r = tr.refine(tmp_path, ask=Ask(promptgen.GenError("the Claude CLI was not found on this machine")))
    assert r["llm"]["status"] == "unavailable" and r["llm"]["error"] and r["corrections"] == []
    assert not (tmp_path / "transcript_corrected.json").exists() and len(r["unresolved"]) == 1       # the uncertain word stays flagged for review
    assert load_transcript(tmp_path).segments[0].words[1].w == "ఫాస్ట్"


def test_an_answer_that_is_not_json_is_a_failure_not_a_correction(tmp_path):
    make(tmp_path)
    r = tr.refine(tmp_path, ask=Ask("sorry, I cannot"))
    assert r["llm"]["status"] == "failed" and not (tmp_path / "transcript_corrected.json").exists()


def test_no_uncertain_words_means_no_call(tmp_path):
    make(tmp_path, p_bad=0.95)
    ask = Ask(answer(GOOD))
    r = tr.refine(tmp_path, ask=ask)
    assert ask.calls == 0 and r["llm"]["status"] == "not_needed"


def test_a_stale_corrected_file_is_removed_when_nothing_applies_any_more(tmp_path):
    make(tmp_path)
    tr.refine(tmp_path, ask=Ask(answer(GOOD)))
    assert (tmp_path / "transcript_corrected.json").exists()
    make(tmp_path, p_bad=0.95)                                                                # the transcript changed: nothing is uncertain now
    tr.refine(tmp_path, ask=Ask(answer()))
    assert not (tmp_path / "transcript_corrected.json").exists()


def test_refine_step_is_cached_and_a_changed_transcript_reruns_only_what_depends_on_it(tmp_path, monkeypatch):
    t = make(tmp_path)
    asked = Ask(answer(GOOD))
    monkeypatch.setattr(promptgen, "run_claude", asked)
    assert pipeline.execute(tmp_path, "refine", pipeline.Ctx())["status"] == "ran"
    monkeypatch.setattr(tr, "whisper_aligner", lambda: exact())                                  # the aligner works now: the unfinished alignment is completed (resume)
    wav(tmp_path)
    assert pipeline.execute(tmp_path, "refine", pipeline.Ctx())["status"] == "ran"
    assert pipeline.execute(tmp_path, "refine", pipeline.Ctx())["status"] == "fresh" and asked.calls == 1      # finished: nothing re-run, no second call
    fp1 = pipeline.STEPS["cuts"].fingerprint(tmp_path, pipeline.Ctx())
    t.segments[1].words[0].p = 0.1                                                            # a different raw transcript
    (tmp_path / "transcript.json").write_text(t.model_dump_json(indent=1), encoding="utf-8")
    assert pipeline.execute(tmp_path, "refine", pipeline.Ctx())["status"] == "ran"
    assert pipeline.STEPS["cuts"].fingerprint(tmp_path, pipeline.Ctx()) != fp1                # downstream (cuts, plan-input, ...) is invalidated by the changed transcript


def test_correction_keeps_every_timestamp_valid(tmp_path):
    t = make(tmp_path)
    c = tr.validate_corrections(t, [{**GOOD, "to": "అ ఆ ఇ"}], tr.uncertain(t)["flagged"])
    fixed, _ = tr.apply_corrections(t, c)
    last = 0.0
    for s in fixed.segments:
        for w in s.words:
            assert 0 <= w.start <= w.end <= fixed.duration and w.start >= last - 1e-9
            last = w.end


def test_asr_keeps_whisper_word_probabilities(tmp_path, monkeypatch):
    """transcribe() stores Whisper's own probability of every word (the only source of the confidence the correction stage uses)."""
    import sys
    import types

    import numpy as np

    from backend import audio_analysis, transcribe

    class FakeWord:
        def __init__(self, w, a, b, p):
            self.word, self.start, self.end, self.probability = w, a, b, p

    class FakeSeg:
        start, end, text = 0.0, 2.0, " ఒకటి రెండు"
        words = [FakeWord(" ఒకటి", 0.0, 1.0, 0.91234), FakeWord(" రెండు", 1.0, 2.0, 0.2)]

    class FakeModel:
        def __init__(self, *a, **k):
            pass

        def transcribe(self, pcm, **k):
            return [FakeSeg()], None

    fw, audio_mod = types.ModuleType("faster_whisper"), types.ModuleType("faster_whisper.audio")
    fw.WhisperModel, audio_mod.decode_audio = FakeModel, lambda path, sampling_rate: np.zeros(16000 * 3, dtype="float32")
    monkeypatch.setitem(sys.modules, "faster_whisper", fw)
    monkeypatch.setitem(sys.modules, "faster_whisper.audio", audio_mod)
    (tmp_path / "audio.wav").write_bytes(b"x")
    monkeypatch.setattr(audio_analysis, "probe", lambda p: {})
    monkeypatch.setattr(transcribe, "to_wav16k", lambda a, b: b)
    monkeypatch.setattr(transcribe, "duration", lambda p: 3.0)
    monkeypatch.setattr(transcribe, "is_silent", lambda p: False)
    monkeypatch.setattr(transcribe, "chunk_points", lambda p, a, b: [(0.0, 3.0)])
    t = transcribe.transcribe(tmp_path)
    assert [w.p for w in t.segments[0].words] == [0.912, 0.2]
    saved = Transcript.model_validate_json((tmp_path / "transcript.json").read_text(encoding="utf-8"))
    assert saved.segments[0].words[1].p == 0.2 and tr.uncertain(saved)["flagged"][0]["text"] == "రెండు"


# ---------- forced alignment of corrected words, against real audio ----------
import subprocess


@pytest.fixture(autouse=True)
def no_real_model(monkeypatch):
    """Tests never load Whisper: the default aligner fails like a machine without memory, so corrected words stay ESTIMATED unless a test passes its own aligner."""
    def boom():
        raise RuntimeError("no model in tests")
    monkeypatch.setattr(tr, "whisper_aligner", boom)


def wav(pdir, secs=10):
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency=300:duration={secs}", "-ar", "16000", "-ac", "1", str(pdir / "audio_16k.wav")], capture_output=True, check=True)


def exact(words_by_call=None, shift=0.0):
    """A fake aligner that returns the times Whisper measured (plus an optional shift): what a trustworthy alignment of the same audio looks like."""
    def align(audio, words):
        return [(round(i * 1.0 + shift, 3), round(i * 1.0 + 1.0 + shift, 3)) for i in range(len(words))]
    return align


def test_corrected_words_are_realigned_against_the_audio_and_cross_checked(tmp_path):
    make(tmp_path)
    wav(tmp_path)
    r = tr.refine(tmp_path, ask=Ask(answer(GOOD)), aligner=exact())
    seg = load_transcript(tmp_path).segments[0]
    assert r["alignment"]["status"] == "aligned_for_edits" and r["alignment"]["segments"][0]["median_shift"] == 0.0
    new = [w for w in seg.words if w.edit == "llm"]
    assert [w.timing for w in new] == ["aligned"] and [w.timing for w in seg.words if w.edit is None] == [None, None, None]      # the unchanged words keep Whisper's own timestamps
    assert "re-aligned against the original audio" in r["alignment"]["method"] and "model-inferred" in r["alignment"]["method"]


def test_an_alignment_that_disagrees_with_whisper_is_refused_and_the_words_stay_estimated(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "PAD", 1.0)                                                  # room for the shifted times: the refusal must come from the disagreement, not the bounds
    make(tmp_path)
    wav(tmp_path)
    r = tr.refine(tmp_path, ask=Ask(answer(GOOD)), aligner=exact(shift=0.2 + tr.MAX_SHIFT))
    seg = load_transcript(tmp_path).segments[0]
    rec = r["alignment"]["segments"][0]
    assert r["alignment"]["status"] == "estimated_for_edits" and rec["status"] == "estimated" and "disagrees" in rec["reason"]
    assert [w.timing for w in seg.words if w.edit == "llm"] == ["estimated"]
    assert 1.0 <= seg.words[1].start < seg.words[1].end <= 2.0                       # still inside the span of the word it replaced


def test_alignment_errors_never_become_a_success(tmp_path):
    make(tmp_path)
    wav(tmp_path)

    def crash(audio, words):
        raise MemoryError("not enough memory")

    r = tr.refine(tmp_path, ask=Ask(answer(GOOD)), aligner=crash)
    assert r["alignment"]["status"] == "estimated_for_edits" and "memory" in r["alignment"]["segments"][0]["reason"]
    r2 = tr.refine(tmp_path, ask=Ask(answer(GOOD)))                                    # default aligner: no model on this machine
    assert r2["alignment"]["status"] == "estimated_for_edits" and "could not start" in r2["alignment"]["segments"][0]["reason"]


def test_without_audio_the_edited_words_are_estimated_and_the_reason_is_recorded(tmp_path):
    make(tmp_path)                                                                       # no audio at all
    r = tr.refine(tmp_path, ask=Ask(answer(GOOD)))
    assert r["alignment"]["status"] == "estimated_for_edits" and "could not start" in r["alignment"]["segments"][0]["reason"]


def test_partial_alignment_is_reported_as_partial(tmp_path):
    t = make(tmp_path)
    t.segments[1].words[0].p = 0.1
    (tmp_path / "transcript.json").write_text(t.model_dump_json(indent=1), encoding="utf-8")
    wav(tmp_path)
    second = {"segment": 1, "from_index": 0, "to_index": 0, "from": "సరే", "to": "సరేనా", "reason": "misheard"}

    def align(audio, words):
        if len(words) == 4:
            return [(i * 1.0, i * 1.0 + 1.0) for i in range(4)]                         # segment 0: trustworthy
        raise ValueError("no unchanged word agrees")                                      # segment 1: refused

    r = tr.refine(tmp_path, ask=Ask(answer(GOOD, second)), aligner=align)
    assert r["alignment"]["status"] == "partial" and [s["status"] for s in r["alignment"]["segments"]] == ["aligned", "estimated"]


def test_analysis_never_calls_estimated_timestamps_completed(tmp_path):
    from backend import audio_analysis as aa
    make(tmp_path)
    wav(tmp_path)
    (tmp_path / "audio.wav").write_bytes((tmp_path / "audio_16k.wav").read_bytes())
    tr.refine(tmp_path, ask=Ask(answer(GOOD)))                                           # no model: estimated
    d = aa.build(tmp_path)
    s9 = d["stages"][8]
    assert s9["name"] == "Word-Level Alignment" and s9["status"] == "warning" and "ESTIMATED" in s9["detail"]
    assert any(w["code"] == "estimated_timestamps" for w in d["validation"]["warnings"]) and d["validation"]["status"] == "warning"
    assert [w["timing"] for u in d["utterances"] for w in u["words"]].count("estimated") == 1
    tr.refine(tmp_path, ask=Ask(answer(GOOD)), aligner=exact())
    d2 = aa.build(tmp_path)
    assert d2["stages"][8]["status"] == "completed" and not any(w["code"] == "estimated_timestamps" for w in d2["validation"]["warnings"])


# ---------- caching and resume never reuse stale results ----------
def test_estimated_timestamps_keep_the_step_unfinished_until_the_alignment_succeeds(tmp_path, monkeypatch):
    make(tmp_path)
    wav(tmp_path)
    asked = Ask(answer(GOOD))
    monkeypatch.setattr(promptgen, "run_claude", asked)
    assert pipeline.execute(tmp_path, "refine", pipeline.Ctx())["status"] == "ran"      # no model: ESTIMATED
    assert pipeline.execute(tmp_path, "refine", pipeline.Ctx())["status"] == "ran"      # resume: not finished, tried again
    monkeypatch.setattr(tr, "whisper_aligner", lambda: exact())
    assert pipeline.execute(tmp_path, "refine", pipeline.Ctx())["status"] == "ran"      # now aligned
    assert tr.last_alignment(tmp_path) == "aligned_for_edits"
    assert pipeline.execute(tmp_path, "refine", pipeline.Ctx())["status"] == "fresh"
    assert asked.calls == 1                                                              # the Claude answer was cached all along


def test_a_changed_audio_or_vocabulary_or_transcript_invalidates_refine_and_what_follows(tmp_path):
    make(tmp_path)
    (tmp_path / "audio.wav").write_bytes(b"a")
    fp = lambda: (pipeline.STEPS["refine"].fingerprint(tmp_path, pipeline.Ctx()), pipeline.STEPS["cuts"].fingerprint(tmp_path, pipeline.Ctx()), pipeline.STEPS["plan-input"].fingerprint(tmp_path, pipeline.Ctx()))
    base = fp()
    (tmp_path / "audio.wav").write_bytes(b"b")
    assert fp()[0] != base[0] and fp()[1] != base[1]                                      # other audio: re-review and re-analyze
    (tmp_path / "audio.wav").write_bytes(b"a")
    assert fp() == base
    (tmp_path / "vocabulary.txt").write_text("API", encoding="utf-8")
    assert fp()[0] != base[0]
    (tmp_path / "vocabulary.txt").unlink()
    (tmp_path / "transcript_corrected.json").write_text((tmp_path / "transcript.json").read_text(encoding="utf-8").replace("సరే", "సరేనా"), encoding="utf-8")
    after = fp()
    assert after[1] != base[1] and after[2] != base[2]                                    # a new corrected transcript reaches the cuts and the plan input


def test_refine_with_unchanged_inputs_is_not_run_again(tmp_path, monkeypatch):
    make(tmp_path, p_bad=0.95)                                                           # nothing uncertain, but the final transcript is the LLM one: every word is checked, once
    asked = Ask(answer())
    monkeypatch.setattr(promptgen, "run_claude", asked)
    assert pipeline.execute(tmp_path, "refine", pipeline.Ctx())["status"] == "ran" and asked.calls == 1
    assert pipeline.execute(tmp_path, "refine", pipeline.Ctx())["status"] == "fresh" and asked.calls == 1
    monkeypatch.setattr(pipeline.config, "LLM_CORRECT_ALL", False)                         # turned off: only uncertain words may be corrected, and nobody is uncertain
    assert pipeline.execute(tmp_path, "refine", pipeline.Ctx())["status"] == "ran" and asked.calls == 1


def test_the_pipeline_step_lets_the_llm_check_every_word(tmp_path, monkeypatch):
    make(tmp_path, p_bad=0.95)
    wav(tmp_path)
    monkeypatch.setattr(promptgen, "run_claude", Ask(answer({"segment": 1, "from_index": 0, "to_index": 0, "from": "సరే", "to": "సరేనా", "reason": "x"})))
    pipeline.execute(tmp_path, "refine", pipeline.Ctx())
    assert [w.w for w in load_transcript(tmp_path).segments[1].words][0] == "సరేనా"        # a confident word was corrected: the final transcript is the LLM one


def test_an_earlier_llm_verified_file_survives_when_the_llm_is_down(tmp_path):
    make(tmp_path)
    tr.refine(tmp_path, ask=Ask(answer(GOOD)))
    assert (tmp_path / "transcript_corrected.json").exists()
    (tmp_path / "asr_llm_cache.json").unlink()                                           # (no cached answer: Claude would really have to be asked)
    r = tr.refine(tmp_path, ask=Ask(promptgen.GenError("not signed in")))               # the next run cannot reach Claude
    assert r["llm"]["status"] == "unavailable" and r["llm"]["kept_earlier_correction"] and r["corrected_file"] == "transcript_corrected.json"
    assert load_transcript(tmp_path).segments[0].words[1].w == "ఫాస్ట్ఏపీఐ"                  # the verified final JSON is still the transcript


def test_the_analysis_stops_when_the_llm_check_cannot_run_and_nothing_verified_exists(tmp_path, monkeypatch):
    make(tmp_path)
    wav(tmp_path)
    monkeypatch.setattr(promptgen, "run_claude", Ask(promptgen.GenError("not signed in")))
    with pytest.raises(pipeline.StepError, match="LLM check"):
        pipeline.execute(tmp_path, "refine", pipeline.Ctx())
    assert "refine" not in json.loads((tmp_path / ".build_state.json").read_text(encoding="utf-8")).get("fingerprints", {}) if (tmp_path / ".build_state.json").exists() else True
    monkeypatch.setattr(promptgen, "run_claude", Ask(answer(GOOD)))                      # signed in again: the same step runs again and finishes
    assert pipeline.execute(tmp_path, "refine", pipeline.Ctx())["status"] == "ran"
    assert load_transcript(tmp_path).segments[0].words[1].w == "ఫాస్ట్ఏపీఐ"
