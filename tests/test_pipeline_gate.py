"""The timeline approval and the separate Render Video action (timeline_gate.py, pipeline_view.py, routes/pipeline.py). Whisper, CLIP and Remotion are the fakes of test_m7; no network. Run: python -m pytest tests/test_pipeline_gate.py -q"""
import importlib

import pytest

from backend import jobs, motion_branch, review, timeline_gate

_m7 = importlib.import_module("test_m7")        # the M7 fakes (importlib keeps the requirements scan from treating it as a package)
client = _m7.client
create, install_plan = _m7.create, _m7.install_plan


@pytest.fixture(autouse=True)
def motion_done(monkeypatch):
    """These tests are about the image gate and the approval: the motion branch (tests/test_motion_only_mode.py) is taken as finished."""
    monkeypatch.setattr(motion_branch, "blockers", lambda pdir, aspect: [])
    monkeypatch.setattr(motion_branch, "complete", lambda pdir, aspect: True)      # and no motion job is started in the background of a test that does not wait for it


@pytest.fixture
def proj(client):
    pid = create(client).json()["id"]
    pdir = install_plan(pid)
    return client, pid, pdir


@pytest.fixture
def fake_start(monkeypatch):
    """jobs.start replaced by a recorder that registers a running job (no thread): counts how many jobs a request really queues."""
    calls = []

    def start(pid, label, names, ctx):
        j = jobs.Job(pid, label, tuple(names), ctx)
        jobs._jobs[pid] = j
        calls.append(label)
        return j
    monkeypatch.setattr(jobs, "start", start)
    return calls


def test_continue_starts_one_timeline_job_and_a_repeat_returns_it(proj, fake_start, monkeypatch):
    c, pid, pdir = proj
    monkeypatch.setattr(review, "set_gate", lambda *a, **k: {})
    monkeypatch.setattr(review, "approve_prompts", lambda *a, **k: 0)
    first, second = c.post(f"/projects/{pid}/continue"), c.post(f"/projects/{pid}/continue")
    assert first.status_code == second.status_code == 202 and first.json() == second.json()
    assert fake_start == ["timeline-9x16"]                                                   # one job, the build up to the timeline, no render


def test_approve_is_refused_while_the_timeline_is_not_verified(proj):
    c, pid, pdir = proj
    r = c.post(f"/projects/{pid}/timeline/approve")
    assert r.status_code == 409 and r.json()["error"]["code"] == "timeline_not_ready"


def test_a_final_render_needs_the_approval(proj, fake_start):
    c, pid, pdir = proj
    with pytest.raises(Exception) as e:
        timeline_gate.require_approved(pdir, "9:16")
    assert getattr(e.value, "code", "") == "timeline_not_approved"


