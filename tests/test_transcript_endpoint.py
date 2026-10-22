"""GET /projects/{id}/transcript: the JSON the analysis made from the audio, read-only. Run: python -m pytest tests/test_transcript_endpoint.py -q"""
import importlib
import json

import pytest

from backend import config

_m7 = importlib.import_module("test_m7")
client, create = _m7.client, _m7.create


def test_transcript_is_served_as_it_is_and_missing_is_a_clear_409(client):
    pid = create(client).json()["id"]
    r = client.get(f"/projects/{pid}/transcript")
    assert r.status_code == 409 and r.json()["error"]["code"] == "transcript_missing"            # not analyzed yet
    data = {"language": "te", "duration": 1.5, "segments": [{"id": 0, "start": 0.0, "end": 1.5, "text": "నమస్తే", "words": [{"w": "నమస్తే", "start": 0.0, "end": 0.9}]}]}
    (config.PROJECTS_DIR / pid / "transcript.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    r = client.get(f"/projects/{pid}/transcript")
    assert r.status_code == 200 and r.json() == data                                              # Telugu text and every word with its times
    (config.PROJECTS_DIR / pid / "transcript.json").write_text("{not json", encoding="utf-8")
    assert client.get(f"/projects/{pid}/transcript").json()["error"]["code"] == "transcript_unreadable"
    assert client.get("/projects/nope/transcript").status_code == 404


# ---------- the final transcript is the LLM-corrected one ----------
from backend import promptgen
from backend import transcript_review as tr


@pytest.fixture(autouse=True)
def no_real_model(monkeypatch):
    """The endpoint tests never load Whisper: the aligner fails like a machine without memory, so corrected words stay ESTIMATED."""
    def boom():
        raise RuntimeError("no model in tests")
    monkeypatch.setattr(tr, "whisper_aligner", boom)


def _put(pid, p=None):
    d = {"language": "te", "duration": 6.0, "segments": [{"id": 0, "start": 0.0, "end": 3.0, "text": "ముదటి కాలని", "words": [
        {"w": "ముదటి", "start": 0.0, "end": 1.0, **({"p": p} if p is not None else {})}, {"w": "కాలని", "start": 1.0, "end": 3.0}]}]}
    (config.PROJECTS_DIR / pid / "transcript.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return d


FIX = json.dumps({"corrections": [{"segment": 0, "from_index": 0, "to_index": 0, "from": "ముదటి", "to": "మొదటి", "reason": "spelling"}]}, ensure_ascii=False)


def test_the_final_transcript_is_the_llm_corrected_one_with_the_same_timestamps_and_the_original_stays(client, monkeypatch):
    pid = create(client).json()["id"]
    assert client.post(f"/projects/{pid}/transcript/correct").json()["error"]["code"] == "transcript_missing"
    raw = _put(pid, p=0.95)                                               # confident words: with the LLM option on, every word is still checked
    assert client.get(f"/projects/{pid}/transcript").json() == raw        # nothing corrected yet: the final is the original
    calls = []
    monkeypatch.setattr(promptgen, "run_claude", lambda user, system="", timeout=0: (calls.append(1) or FIX) if system == tr.SYSTEM_ALL else "{}")     # only the correction prompt counts: a thread of an earlier test must not
    before = (config.PROJECTS_DIR / pid / "transcript.json").read_bytes()
    r = client.post(f"/projects/{pid}/transcript/correct")
    d = r.json()
    w = d["transcript"]["segments"][0]["words"]
    assert r.status_code == 200 and [x["w"] for x in w] == ["మొదటి", "కాలని"] and d["llm"]["status"] == "applied" and d["corrections"][0]["status"] == "applied"
    assert (w[0]["start"], w[0]["end"]) == (0.0, 1.0) and (w[1]["start"], w[1]["end"]) == (1.0, 3.0)         # the timestamps are kept
    assert w[0]["edit"] == "llm" and w[0]["timing"] == "estimated"                                          # never presented as measured
    assert (config.PROJECTS_DIR / pid / "transcript.json").read_bytes() == before                           # the original is never edited
    assert client.get(f"/projects/{pid}/transcript").json() == d["transcript"]                               # the final JSON is the corrected one
    assert client.get(f"/projects/{pid}/transcript?view=original").json() == raw                             # the original stays available
    assert client.post(f"/projects/{pid}/transcript/correct").json()["llm"]["status"] == "cached" and len(calls) == 1


def test_claude_unavailable_keeps_the_original_as_the_final_transcript_and_says_why(client, monkeypatch):
    pid = create(client).json()["id"]
    raw = _put(pid)

    def down(user, system="", timeout=0):
        raise promptgen.GenError("the Claude CLI was not found on this machine")
    monkeypatch.setattr(promptgen, "run_claude", down)
    d = client.post(f"/projects/{pid}/transcript/correct").json()
    assert d["transcript"] == raw and d["llm"]["status"] == "unavailable" and d["llm"]["error"] and d["corrections"] == []
    assert not (config.PROJECTS_DIR / pid / "transcript_corrected.json").exists()


def test_correction_is_refused_while_a_job_runs(client, monkeypatch):
    from backend import jobs
    pid = create(client).json()["id"]
    _put(pid)
    monkeypatch.setattr(jobs, "is_running", lambda p: True)
    assert client.post(f"/projects/{pid}/transcript/correct").json()["error"]["code"] == "job_running"
