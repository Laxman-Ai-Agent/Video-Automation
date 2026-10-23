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
    bad = [{**GOOD, "from": "వేరే"}, {**GOOD, "to": "ఒకటి రెండు మూడు నాలుగు"}, {"segment": 9}, GOOD, GOOD]
    out = tr.validate_corrections(t, bad)
    assert [c["why"] for c in out] == ["from_mismatch", "adds_words", "malformed", None, "overlaps_another"]
    assert [c["status"] for c in out].count("applied") == 1


def test_corrected_words_get_estimated_times_inside_the_replaced_span_and_raw_is_untouched(tmp_path):
    t = make(tmp_path)
    c = tr.validate_corrections(t, [{**GOOD, "to": "ఫాస్ట్ ఏపీఐ"}])
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


def _review(tmp_path, **changes):
    """transcript_review.json of a run, with the given top-level or nested ('llm.status') fields changed, written after the raw transcript."""
    f = tmp_path / "transcript_review.json"
    data = json.loads(f.read_text(encoding="utf-8"))
    for key, value in changes.items():
        node = data
        *path, last = key.split(".")
        for part in path:
            node = node[part]
        node[last] = value
    f.write_text(json.dumps(data), encoding="utf-8")


def test_a_transcript_the_llm_checked_is_verified_even_when_nothing_was_corrected(tmp_path):
    """transcript_corrected.json exists only when something was corrected, so the gate cannot look for the file: a transcript the LLM checked and left as it was is verified too."""
    import os
    make(tmp_path)
    assert not tr.is_verified(tmp_path)                                                     # no review yet
    tr.refine(tmp_path, ask=Ask(answer()))                                  # the LLM answers: nothing to correct
    assert (tmp_path / "transcript_corrected.json").exists() and tr.is_verified(tmp_path)
    _review(tmp_path, **{"llm.status": "unavailable"})
    assert not tr.is_verified(tmp_path)                                                     # the LLM did not check it
    _review(tmp_path, **{"llm.status": "cached", "alignment.status": "estimated_for_edits"})
    assert not tr.is_verified(tmp_path)                                                     # corrected words still wait for their timestamps
    _review(tmp_path, **{"alignment.status": "aligned_for_edits"})
    assert tr.is_verified(tmp_path)
    later = (tmp_path / "transcript_review.json").stat().st_mtime + 5
    os.utime(tmp_path / "transcript.json", (later, later))
    assert not tr.is_verified(tmp_path)                                                     # the review was made from an older raw transcript
    (tmp_path / "transcript_review.json").unlink()
    (tmp_path / "transcript_corrected.json").write_text("{}", encoding="utf-8")
    os.utime(tmp_path / "transcript_corrected.json", (later + 1, later + 1))
    assert tr.is_verified(tmp_path)                                                         # an older project that has only the corrected transcript, made after the raw one


def test_the_one_final_json_exists_whenever_the_llm_checked_the_transcript_and_is_not_written_when_it_did_not(tmp_path):
    """transcript_corrected.json is the final, LLM-verified transcript: the same words when the LLM found nothing to fix, never written when the LLM did not check."""
    make(tmp_path)
    raw = (tmp_path / "transcript.json").read_bytes()
    r = tr.refine(tmp_path, ask=Ask(answer()))
    assert r["corrected_file"] == "transcript_corrected.json" and (tmp_path / "transcript.json").read_bytes() == raw
    final = Transcript.model_validate_json((tmp_path / "transcript_corrected.json").read_text(encoding="utf-8"))
    assert final == Transcript.model_validate_json(raw) and all(w.edit is None and w.timing is None for s in final.segments for w in s.words)       # same words, Whisper's own timestamps
    other = tmp_path / "unchecked"
    other.mkdir()
    make(other)
    r = tr.refine(other, ask=Ask(promptgen.GenError("not signed in")))
    assert r["corrected_file"] is None and not (other / "transcript_corrected.json").exists()


def test_the_llm_gets_the_word_times_as_evidence_from_the_audio(tmp_path):
    t = make(tmp_path)
    words = json.loads(tr._request(t, [0]))["segments"][0]["words"]
    assert words[1] == {"i": 1, "w": "ఫాస్ట్", "p": 0.2, "s": 1.0, "e": 2.0}                  # the LLM cannot hear: probability and times are what the audio tells it
    assert "s/e" in tr.SYSTEM


def test_the_comparison_puts_the_raw_whisper_text_next_to_the_final_one_with_the_llm_edits_marked(tmp_path):
    make(tmp_path)
    tr.refine(tmp_path, ask=Ask(answer(GOOD)))
    c = tr.comparison(tmp_path)
    assert c["raw_file"] == "transcript.json" and c["final_file"] == "transcript_corrected.json" and c["llm"]["status"] == "applied" and c["corrections_applied"] == 1
    first, second = c["segments"]
    assert first["changed"] and first["raw_text"] == "a" and "ఫాస్ట్ఏపీఐ" in first["final_text"]
    assert [w["edit"] for w in first["final_words"]] == [None, "llm", None, None] and first["final_words"][1]["timing"] == "estimated"        # no model in tests: the time is estimated, and it says so
    assert not second["changed"] and "final_words" not in second
    assert c["alignment"] == "estimated_for_edits" and not c["verified"]                    # corrected words still wait for their timestamps


SPEC_RAW = "ఇంక ఫ్యూచర్ లో మనుం సేఫ్గా ఉండాల అంటే ఏమి చేయాలి"
SPEC_FINAL = "ఇంకా Future లో మనం Safe గా ఉండాలంటే ఏమి చేయాలి?"


def test_the_specified_sentence_is_corrected_word_for_word_and_the_original_stays(tmp_path):
    """Telugu spelling (ఇంక -> ఇంకా, మనుం -> మనం), English words in English spelling with the Telugu ending kept apart (Future లో, Safe గా), two words joined by grammar (ఉండాలంటే), the question mark; the raw
    transcript is untouched. (The wording of the LLM's answer is the prompt's job, checked against the real LLM; this checks that every such correction is accepted and applied exactly.)"""
    ws = SPEC_RAW.split()
    t = Transcript(language="te", duration=5.0, segments=[Segment(id=0, start=0, end=4.95, text=SPEC_RAW, words=[W(w, i * 0.5, i * 0.5 + 0.45, 0.9) for i, w in enumerate(ws)])])
    (tmp_path / "transcript.json").write_text(t.model_dump_json(indent=1), encoding="utf-8")
    raw = (tmp_path / "transcript.json").read_bytes()
    fix = lambda i, j, to: {"segment": 0, "from_index": i, "to_index": j, "from": " ".join(ws[i:j + 1]), "to": to, "reason": "spec"}
    ask = Ask(answer(fix(0, 0, "ఇంకా"), fix(1, 1, "Future"), fix(3, 3, "మనం"), fix(4, 4, "Safe గా"), fix(5, 6, "ఉండాలంటే"), fix(8, 8, "చేయాలి?")))
    r = tr.refine(tmp_path, ask=ask)
    assert [c["status"] for c in r["corrections"]] == ["applied"] * 6
    c = tr.comparison(tmp_path)["segments"][0]
    assert c["raw_text"] == SPEC_RAW and c["final_text"] == SPEC_FINAL and (tmp_path / "transcript.json").read_bytes() == raw
    final = {w["w"]: w for w in c["final_words"]}
    assert final["ఉండాలంటే"]["start"] == 2.5 and final["ఉండాలంటే"]["end"] == 3.45                           # the joined word spans both words it replaced
    assert 2.0 <= final["Safe"]["start"] < final["Safe"]["end"] <= final["గా"]["end"] <= 2.45                 # the split word shares the time of the word it replaced


def test_the_instructions_ask_for_telugu_grammar_english_spelling_only_for_spoken_english_and_punctuation():
    for system in (tr.SYSTEM,):
        assert "'ఉండాల అంటే' -> 'ఉండాలంటే'" in system and "'ఫ్యూచర్ లో' -> 'future లో'" in system and "Decide the capital letters from the sentence and the situation" in system and "'చేయాలి' -> 'చేయాలి?'" in system
        assert "ONLY when the Telugu-script word is clearly the sound of an English word" in system and "never turn a genuine Telugu word into English" in system


def test_the_analysis_runs_whisper_only_when_there_is_no_transcript_and_the_llm_check_before_the_cuts(tmp_path, monkeypatch):
    ran = []
    monkeypatch.setattr(pipeline, "execute", lambda pdir, name, ctx: ran.append(name) or {"name": name, "status": "ran"})
    monkeypatch.setattr(pipeline.llm_review, "run_stage_llm_review", lambda pdir, stage, *a, **k: ran.append(f"review:{stage}"))
    pipeline.run_analysis(tmp_path)
    assert ran == ["transcribe", "refine", "cuts", "review:analyzer"]                       # the LLM approval of the final transcript comes last (a cached answer costs nothing)
    ran.clear()
    make(tmp_path)
    pipeline.run_analysis(tmp_path)
    assert ran == ["refine", "cuts", "review:analyzer"]                                                        # the project has its transcript: Whisper does not run again


def test_a_low_confidence_word_the_llm_checked_and_kept_is_reviewed_not_unresolved(tmp_path):
    """The LLM looks at every word: a word below the confidence threshold that it leaves unchanged was reviewed and kept. It used to stay "unresolved" and raise a warning that stopped the pipeline
    until a person ran the auto-fix; only when the LLM did NOT check, the uncertain word stays unresolved."""
    from backend import audio_analysis as aa
    make(tmp_path)                                                                           # "ఫాస్ట్" has p 0.2
    wav(tmp_path)
    (tmp_path / "audio.wav").write_bytes((tmp_path / "audio_16k.wav").read_bytes())
    r = tr.refine(tmp_path, ask=Ask(answer()))
    assert r["unresolved"] == [] and [c["text"] for c in r["confirmed"]] == ["ఫాస్ట్"] and r["confirmed"][0]["reason"] == "checked by the LLM and kept"
    codes = [w["code"] for w in aa.build(tmp_path)["validation"]["warnings"]]
    assert "uncertain_words" not in codes and "unresolved_words" not in codes
    other = tmp_path / "unchecked"
    other.mkdir()
    make(other)
    wav(other)
    (other / "audio.wav").write_bytes((other / "audio_16k.wav").read_bytes())
    r = tr.refine(other, ask=Ask(promptgen.GenError("not signed in")))                      # the LLM did not check: the uncertain word stays unresolved and says so
    assert [f["text"] for f in r["unresolved"]] == ["ఫాస్ట్"] and r["confirmed"] == []
    assert "unresolved_words" in [w["code"] for w in aa.build(other)["validation"]["warnings"]]


def test_a_stale_corrected_file_is_replaced_by_the_final_json_of_the_new_transcript(tmp_path):
    make(tmp_path)
    tr.refine(tmp_path, ask=Ask(answer(GOOD)))
    assert load_transcript(tmp_path).segments[0].words[1].w == "ఫాస్ట్ఏపీఐ"
    make(tmp_path, p_bad=0.95)                                                                # the transcript changed
    tr.refine(tmp_path, ask=Ask(answer()))                                                    # the LLM checks it and finds nothing to fix
    assert load_transcript(tmp_path).segments[0].words[1].w == "ఫాస్ట్"                         # the old correction no longer applies: the final JSON has the new transcript's words


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
    c = tr.validate_corrections(t, [{**GOOD, "to": "అ ఆ ఇ"}])
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
