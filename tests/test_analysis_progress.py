"""The Audio Analyzer subtasks come from what the executor really wrote: job.json, timings.json, the step outputs and the LLM review files."""
import json

import pytest

from VIDEO_ENGINE.stages import analysis_progress


def put(pdir, name, data):
    (pdir / name).write_text(json.dumps(data) if not isinstance(data, str) else data, encoding="utf-8")


def by_id(result):
    return {t["id"]: t for t in result["subtasks"]}


def test_empty_project_is_all_pending(tmp_path):
    r = analysis_progress.subtasks(tmp_path, running=False)
    assert [t["status"] for t in r["subtasks"]] == ["pending"] * 4
    assert r["percent"] == 0


def test_running_step_reports_the_real_job_percent(tmp_path):
    put(tmp_path, "transcript.json", "{}")
    put(tmp_path, "job.json", {"step": "refine", "percent": 60, "error": None})
    t = by_id(analysis_progress.subtasks(tmp_path, running=True))
    assert t["transcribe"]["status"] == "completed" and t["transcribe"]["percent"] == 100
    assert t["refine"]["status"] == "running" and t["refine"]["percent"] == 60
    assert t["refine"]["llm"]["status"] == "running"          # 50 <= percent < 75: the LLM call is in flight
    assert t["cuts"]["status"] == "pending"


def test_llm_check_completed_failed_and_pending(tmp_path):
    put(tmp_path, "transcript.json", "{}")
    put(tmp_path, "transcript_review.json", {"llm": {"status": "applied", "model": "claude-code"}})
    assert by_id(analysis_progress.subtasks(tmp_path, False))["refine"]["llm"]["status"] == "completed"
    put(tmp_path, "transcript_review.json", {"llm": {"status": "unavailable", "error": "not signed in"}})
    llm = by_id(analysis_progress.subtasks(tmp_path, False))["refine"]["llm"]
    assert llm == {"status": "failed", "detail": "not signed in"}
    (tmp_path / "transcript_review.json").unlink()
    assert by_id(analysis_progress.subtasks(tmp_path, False))["refine"]["llm"]["status"] == "pending"


def test_failed_step_carries_the_error(tmp_path):
    put(tmp_path, "job.json", {"step": "transcribe", "percent": 0, "error": "the audio is silent"})
    t = by_id(analysis_progress.subtasks(tmp_path, running=False))["transcribe"]
    assert t["status"] == "failed" and t["message"] == "the audio is silent"


@pytest.mark.parametrize("review,running,status,llm", [
    ({"status": "passed", "score": 0.9}, False, "completed", "completed"),
    ({"status": "needs_review", "score": 0.5}, False, "failed", "failed"),
    (None, True, "running", "running"),
    (None, False, "pending", "pending"),
])
def test_final_approval_follows_the_llm_review(tmp_path, review, running, status, llm):
    for f in ("transcript.json", "transcript_review.json", "cuts.json", "audio_analysis.json"):
        put(tmp_path, f, {"llm": {"status": "applied"}} if f == "transcript_review.json" else "{}")
    if review:
        put(tmp_path, "llm_review_analyzer.json", review)
    a = by_id(analysis_progress.subtasks(tmp_path, running))["approval"]
    assert (a["status"], a["llm"]["status"]) == (status, llm)
