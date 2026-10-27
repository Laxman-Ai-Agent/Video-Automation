"""The Audio Analyzer's fixer: what the stage review still found goes back to the transcript correction (second pass, same checks, re-aligned), bounded per raw transcript, recorded.
Run: python -m pytest tests/test_analyzer_fixer.py -q"""
import json

import pytest

from VIDEO_ENGINE.stages import transcript_review as tr
from VIDEO_ENGINE.stages.transcribe import Segment, Transcript, Word

FINDINGS = [{"severity": "warning", "category": "terminology_script", "message": "'directగా' has no space before the Telugu suffix"},
            {"severity": "info", "category": "formatting", "message": "punctuation is inconsistent"}]


def _w(w, a, b, **kw):
    return Word(w=w, start=a, end=b, p=0.9, **kw)


@pytest.fixture
def pdir(tmp_path):
    p = tmp_path / "proj_fix"
    p.mkdir()
    t = Transcript(language="te", duration=10.0, segments=[
        Segment(id=0, start=0.0, end=4.0, text="this is directగా ready", words=[_w("this", 0.0, 0.5), _w("is", 0.5, 1.0), _w("directగా", 1.0, 2.0), _w("ready", 2.0, 4.0)])])
    (p / "transcript.json").write_text(t.model_dump_json(), encoding="utf-8")
    (p / "transcript_corrected.json").write_text(t.model_dump_json(), encoding="utf-8")
    (p / "transcript_review.json").write_text(json.dumps({"alignment": {"status": "unchanged", "edited_words": 0, "estimated_words": 0, "segments": []}, "llm": {"status": "applied"}}), encoding="utf-8")
    return p


def _answer(to="direct గా"):
    return json.dumps({"corrections": [{"segment": 0, "from_index": 2, "to_index": 2, "from": "directగా", "to": to, "reason": "script space"}]}, ensure_ascii=False)


def test_the_findings_reach_the_llm_and_the_checked_correction_is_applied_and_recorded(pdir, monkeypatch):
    seen = {}
    monkeypatch.setattr(tr, "realign", lambda pdir, fixed, aligner=None: {"status": "aligned_for_edits", "segments": [{"segment": 0, "status": "aligned"}]})

    def ask(user, system="", timeout=0):
        seen["user"], seen["system"] = json.loads(user), system
        return _answer()
    rec = tr.fix(pdir, FINDINGS, ask=ask)
    assert [f["category"] for f in seen["user"]["review_findings"]] == ["terminology_script"] and "SECOND PASS" in seen["system"]      # only warnings and errors are sent
    final = Transcript.model_validate_json((pdir / "transcript_corrected.json").read_text(encoding="utf-8"))
    assert [w.w for w in final.segments[0].words] == ["this", "is", "direct", "గా", "ready"]
    review = json.loads((pdir / "transcript_review.json").read_text(encoding="utf-8"))
    assert review["fix_rounds"][0]["round"] == 1 and rec["edited_words"] == 2 and review["alignment"]["status"] == "aligned_for_edits"


def test_a_correction_that_fails_the_checks_is_not_applied_and_the_fix_says_so(pdir):
    with pytest.raises(tr.FixError, match="found nothing it could fix"):
        tr.fix(pdir, FINDINGS, ask=lambda user, system="", timeout=0: json.dumps({"corrections": [{"segment": 0, "from_index": 2, "to_index": 2, "from": "WRONG", "to": "x", "reason": "r"}]}))
    final = Transcript.model_validate_json((pdir / "transcript_corrected.json").read_text(encoding="utf-8"))
    assert [w.w for w in final.segments[0].words] == ["this", "is", "directగా", "ready"]                   # untouched


def test_it_is_bounded_per_raw_transcript_and_a_new_raw_transcript_starts_again(pdir, monkeypatch):
    monkeypatch.setattr(tr, "realign", lambda pdir, fixed, aligner=None: {"status": "aligned_for_edits", "segments": []})
    raw = (pdir / "transcript.json").read_text(encoding="utf-8")
    tr.fix(pdir, FINDINGS, ask=lambda *a, **k: _answer())
    (pdir / "transcript_corrected.json").write_text(raw, encoding="utf-8")                                 # as if the LLM undid it
    tr.fix(pdir, FINDINGS, ask=lambda *a, **k: _answer("direct  గా "))
    (pdir / "transcript_corrected.json").write_text(raw, encoding="utf-8")
    tr.fix(pdir, FINDINGS, ask=lambda *a, **k: _answer("direct గా  "))
    (pdir / "transcript_corrected.json").write_text(raw, encoding="utf-8")
    with pytest.raises(tr.FixError, match="3 automatic fix passes"):
        tr.fix(pdir, FINDINGS, ask=lambda *a, **k: _answer())
    t = Transcript.model_validate_json(raw)
    t.segments[0].words[0].w = "THIS"                                                                       # another raw transcript
    (pdir / "transcript.json").write_text(t.model_dump_json(), encoding="utf-8")
    (pdir / "transcript_corrected.json").write_text(t.model_dump_json(), encoding="utf-8")
    assert tr.fix(pdir, FINDINGS, ask=lambda *a, **k: _answer())["round"] == 1


def test_nothing_to_fix_and_an_llm_that_cannot_be_asked_are_clear_errors(pdir):
    with pytest.raises(tr.FixError, match="no warning or error left"):
        tr.fix(pdir, [FINDINGS[1]], ask=lambda *a, **k: _answer())

    def down(user, system="", timeout=0):
        raise RuntimeError("claude not found")
    with pytest.raises(tr.FixError, match="could not be asked"):
        tr.fix(pdir, FINDINGS, ask=down)


def test_the_orchestrator_runs_the_fixer_for_the_analyzer_and_reviews_again(pdir, monkeypatch):
    from types import SimpleNamespace

    from SYSTEM.policies import llm_review
    from VIDEO_ENGINE.pipeline import orchestrator, stage_gate
    calls = []
    verdicts = iter([[{"n": None, "name": "LLM review", "severity": "error", "message": "x"}], []])
    monkeypatch.setattr(stage_gate, "unresolved", lambda *a, **k: next(verdicts))
    monkeypatch.setattr(tr, "fix", lambda p, findings, **k: calls.append(("fix", [f["category"] for f in findings])))
    monkeypatch.setattr(llm_review, "load_review", lambda *a, **k: {"findings": FINDINGS})
    monkeypatch.setattr(llm_review, "run_stage_llm_review", lambda *a, **k: calls.append(("review",)))
    o = orchestrator.PipelineOrchestrator.__new__(orchestrator.PipelineOrchestrator)
    o.pdir, o.aspect, o.project_id = pdir, "16:9", "proj_fix"
    run = SimpleNamespace(run_id="r", correlation_id="c")
    monkeypatch.setattr(orchestrator.communication, "publish_lifecycle_event", lambda **k: None)
    o._resolve_stage_issues("analyzer", run, None)
    assert calls == [("fix", ["terminology_script", "formatting"]), ("review",)]
