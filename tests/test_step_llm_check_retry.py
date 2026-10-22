"""LLM step checks: an `error` verdict is retried and never counts as a check; a blocked LLM stops the run instead of failing every remaining step."""
import json

from backend import step_llm_check as sc


class _P:
    name = "proj"


def _setup(monkeypatch, tmp_path, verdicts):
    steps = [{"n": i, "name": f"s{i}", "status": "completed", "detail": "d", "checks_passed": 1, "checks_total": 1} for i in (1, 2, 3)]
    monkeypatch.setattr(sc, "steps", lambda p, st, asp: (steps, {"x": 1}, tmp_path / "r.json"))
    monkeypatch.setattr(sc, "report_file", lambda p, st, asp: tmp_path / "r.json")
    monkeypatch.setattr(sc, "_checks_file", lambda p, st, asp: tmp_path / "checks.json")
    seq = iter(verdicts)
    monkeypatch.setattr(sc, "_ask", lambda *a, **k: next(seq))


def test_a_blocked_llm_stops_the_run_and_the_errors_are_asked_again(monkeypatch, tmp_path):
    ok = {"verdict": "confirms", "note": "ok"}
    _setup(monkeypatch, tmp_path, [{"verdict": "error", "note": "session limit", "blocked": True}, ok, ok, ok])
    sc._run(_P(), "qc", "16:9")
    data = json.loads((tmp_path / "checks.json").read_text(encoding="utf-8"))
    assert list(data["steps"]) == ["1"] and data["steps"]["1"]["verdict"] == "error"      # stopped after the first blocked call
    assert sc.pending(_P(), "qc", "16:9") == 3                                              # an error is not a check
    sc._run(_P(), "qc", "16:9")                                                             # the LLM is back: every step gets a real verdict (the error one too)
    data = json.loads((tmp_path / "checks.json").read_text(encoding="utf-8"))
    assert [data["steps"][k]["verdict"] for k in "123"] == ["confirms"] * 3 and sc.pending(_P(), "qc", "16:9") == 0
