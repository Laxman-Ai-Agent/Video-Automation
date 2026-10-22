"""A stage is STUCK only while it is running without progress: one waiting for a person's decision (Final QC) is not stuck, however long ago its last start event was."""
from backend import pipeline_issues as pi


def _issues(monkeypatch, tmp_path, status):
    start = {"stage_id": "qc", "timestamp": "2026-10-20T10:00:00", "sender_agent_id": "final_qc", "metadata": {"event": pi._START[0]}}
    monkeypatch.setattr(pi, "_events", lambda pdir: [start])
    monkeypatch.setattr(pi, "_subtask_issues", lambda pdir, stages: [])
    monkeypatch.setattr(pi, "_epoch", lambda iso: 1000.0)
    stages = [{"id": "qc", "label": "Final QC", "status": status}]
    return [i["id"] for i in pi.build(tmp_path, stages, now=1000.0 + 3 * 3600)]


def test_a_stage_waiting_for_a_person_is_not_stuck(monkeypatch, tmp_path):
    assert "qc:stuck" not in _issues(monkeypatch, tmp_path, "waiting_for_approval")


def test_a_running_stage_without_progress_is_stuck(monkeypatch, tmp_path):
    assert "qc:stuck" in _issues(monkeypatch, tmp_path, "running")
