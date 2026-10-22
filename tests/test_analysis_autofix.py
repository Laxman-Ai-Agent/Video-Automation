"""Audio Analyzer auto-fix (backend/analysis_autofix.py): only the word-starts-before-its-segment warning, only from sound in the audio, never the raw transcript."""
import json

import numpy as np

from backend import analysis_autofix as af

WARN = {"stage": "Word Timestamp Integrity", "code": "word_outside_segment", "message": "word 2 “x” lies outside its segment 1"}


def transcript(d, name):
    seg = lambda i, a, b, ws: {"id": i, "start": a, "end": b, "text": " ".join(w[0] for w in ws), "words": [{"w": w[0], "start": w[1], "end": w[2], "p": 0.9} for w in ws]}
    t = {"language": "te", "duration": 15.0, "segments": [seg(0, 0.0, 5.0, [("a", 0.0, 2.0), ("b", 2.0, 4.9)]), seg(1, 9.07, 13.0, [("x", 8.77, 10.03), ("y", 10.03, 12.9)])]}
    (d / name).write_text(json.dumps(t), encoding="utf-8")


def voiced_from(sec):
    return lambda pdir: (0.025, np.arange(600) * 0.025 >= sec)


def test_the_word_start_moves_to_the_first_sound_and_the_file_it_came_from_is_rewritten(tmp_path, monkeypatch):
    transcript(tmp_path, "transcript.json")
    transcript(tmp_path, "transcript_corrected.json")
    monkeypatch.setattr(af, "_voiced", voiced_from(9.475))
    changes, left = af._fix_once(tmp_path, [WARN])
    assert left == [] and len(changes) == 1 and changes[0]["start_before"] == 8.77 and abs(changes[0]["start_after"] - 9.475) < 0.03
    fixed = json.loads((tmp_path / "transcript_corrected.json").read_text(encoding="utf-8"))["segments"][1]["words"][0]
    assert fixed["start"] > 9.07 and fixed["timing"] == "aligned"
    assert json.loads((tmp_path / "transcript.json").read_text(encoding="utf-8"))["segments"][1]["words"][0]["start"] == 8.77       # the raw output is untouched


def test_nothing_is_invented_without_sound_or_when_only_the_raw_transcript_exists(tmp_path, monkeypatch):
    transcript(tmp_path, "transcript_corrected.json")
    monkeypatch.setattr(af, "_voiced", voiced_from(99))                  # no sound anywhere
    changes, left = af._fix_once(tmp_path, [WARN])
    assert changes == [] and "no sound" in left[0]["why_not_fixed"]
    raw = tmp_path / "raw"
    raw.mkdir()
    transcript(raw, "transcript.json")
    monkeypatch.setattr(af, "_voiced", voiced_from(9.475))
    changes, left = af._fix_once(raw, [WARN])
    assert changes == [] and "never edited" in left[0]["why_not_fixed"]


def test_other_warnings_are_left_alone(tmp_path, monkeypatch):
    transcript(tmp_path, "transcript_corrected.json")
    monkeypatch.setattr(af, "_voiced", voiced_from(9.475))
    other = {"stage": "Speech-to-Text (ASR)", "code": "duration_mismatch", "message": "transcript duration differs"}
    assert af._fix_once(tmp_path, [other]) == ([], [other])


def test_a_project_past_the_analyzer_is_not_touched(tmp_path):
    (tmp_path / "scene_segmentation.json").write_text("{}", encoding="utf-8")
    assert "stale" in af.blocked(tmp_path)


# ---------- the loop: attempts, lock, stop conditions (the analysis and the single fix are replaced; they have their own tests) ----------
import pytest


def W(n):
    return {"stage": "Word Timestamp Integrity", "code": "word_outside_segment", "message": f"word {n} lies outside its segment 1"}


class Fake:
    """audio_analysis.write answers the warnings the 'file' has now; each real fix removes the first one (or none, for an unfixable case)."""
    def __init__(self, warnings, fixable=True, errors=()):
        self.w, self.fixable, self.errors, self.writes, self.fixes = list(warnings), fixable, list(errors), 0, 0

    def write(self, pdir, progress=None):
        self.writes += 1
        return {"validation": {"warnings": list(self.w), "errors": list(self.errors)}}

    def fix(self, pdir, warnings):
        self.fixes += 1
        if not self.fixable:
            return [], [{**w, "why_not_fixed": "no sound found inside the word"} for w in warnings]
        w = self.w.pop(0)
        return [{"word_index": 1, "word": "x", "segment": 1, "start_before": 1.0, "start_after": 2.0}], []


@pytest.fixture
def proj(tmp_path):
    (tmp_path / "transcript.json").write_text("{}", encoding="utf-8")
    return tmp_path


@pytest.fixture
def install(monkeypatch):
    def put(fake):
        monkeypatch.setattr(af.audio_analysis, "write", fake.write)
        monkeypatch.setattr(af, "_fix_once", fake.fix)
        return fake
    return put


def test_zero_warnings_changes_nothing(proj, install):
    f = install(Fake([]))
    r = af.run(proj)
    assert r["status"] == "clean" and r["rounds"] == 0 and f.fixes == 0 and r["remaining"] == []


def test_cleared_on_the_first_attempt(proj, install):
    f = install(Fake([W(1)]))
    r = af.run(proj)
    assert r["status"] == "clean" and r["attempts"] == 1 and f.fixes == 1 and len(r["changes"]) == 1
    assert json.loads((proj / af.LOG).read_text(encoding="utf-8"))["status"] == "clean"


def test_cleared_after_several_attempts_and_not_beyond_what_is_needed(proj, install):
    f = install(Fake([W(1), W(2), W(3)]))
    r = af.run(proj)
    assert r["status"] == "clean" and r["attempts"] == 3 and f.fixes == 3 and r["remaining"] == []


def test_still_warnings_after_three_attempts_stops_and_a_repeat_request_adds_no_attempt(proj, install):
    f = install(Fake([W(i) for i in range(5)]))
    r = af.run(proj, rounds=3)
    assert r["status"] == "exhausted" and r["attempts"] == 3 and f.fixes == 3 and len(r["remaining"]) == 2
    assert all("used up" in x["why_not_fixed"] for x in r["remaining"])
    again = af.run(proj, rounds=3)                                         # duplicate request, same analysis run
    assert again["status"] == "exhausted" and again["attempts"] == 3 and f.fixes == 3


def test_a_new_analysis_run_starts_the_count_again(proj, install):
    f = install(Fake([W(i) for i in range(5)]))
    af.run(proj)
    (proj / "transcript.json").write_text('{"again": 1}', encoding="utf-8")                     # a new analysis wrote a new raw transcript
    af.run(proj)
    assert f.fixes == 5 and f.w == []


def test_a_warning_that_cannot_be_fixed_stops_at_once_with_its_reason(proj, install):
    f = install(Fake([W(1)], fixable=False))
    r = af.run(proj)
    assert r["status"] == "warnings_remain" and r["attempts"] == 1 and f.fixes == 1
    assert r["remaining"][0]["why_not_fixed"] == "no sound found inside the word"


def test_errors_are_never_reported_as_clean(proj, install):
    install(Fake([], errors=["segment out of range"]))
    assert af.run(proj)["status"] == "errors"


def test_a_second_request_during_a_running_loop_is_refused_and_a_failure_frees_the_lock(proj, install, monkeypatch):
    f = install(Fake([W(1)]))
    lock = af._locks.setdefault(proj.name, __import__("threading").Lock())
    lock.acquire()
    with pytest.raises(af.Busy):
        af.run(proj)
    lock.release()
    monkeypatch.setattr(af.audio_analysis, "write", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("ffmpeg failed")))
    with pytest.raises(RuntimeError):
        af.run(proj)
    f2 = install(Fake([]))
    assert af.run(proj)["status"] == "clean" and f2.fixes == 0       # the failure did not leave the project locked


def test_a_project_with_scene_segmentation_is_not_fixed(proj, install):
    f = install(Fake([W(1)]))
    (proj / "scene_segmentation.json").write_text("{}", encoding="utf-8")
    r = af.run(proj)
    assert r["status"] == "blocked" and f.fixes == 0 and not (proj / af.LOG).exists()


def test_solve_error_additional_attempts_allows_five_more_rounds(proj, install):
    # Initial run uses 3 attempts and exhausts with 2 warnings left
    f = install(Fake([W(i) for i in range(5)]))
    r = af.run(proj, rounds=3)
    assert r["status"] == "exhausted" and r["attempts"] == 3 and f.fixes == 3

    # Solving error with additional=True grants 5 additional attempts, resolving the remaining 2 warnings
    r_more = af.run(proj, rounds=5, additional=True)
    assert r_more["status"] == "clean" and f.fixes == 5 and f.w == []
