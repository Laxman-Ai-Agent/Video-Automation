"""Prompt writer (backend/promptgen.py): started by the analysis approval, one prompt at a time on request, kept in review.json, retry after a failure.
The Claude CLI is replaced by a fake (run_claude). Run: python -m pytest tests/test_m9_promptgen.py -q"""
import importlib
import threading
import time

import pytest

from backend import promptgen, review

_r = importlib.import_module("test_m9_review")
client, proj, get = _r.client, _r.proj, _r.get


class Fake:
    """Stands in for the CLI: numbered texts, optional failures, optional blocking."""
    def __init__(self):
        self.calls, self.fail_first, self.gate, self.during = 0, 0, None, None

    def __call__(self, user):
        self.calls += 1
        if self.gate:
            self.gate.wait(5)
        if self.during:
            self.during()
        if self.calls <= self.fail_first:
            raise promptgen.GenError("not signed in")
        return f"Generated scene image number {self.calls}, soft light\n\nextra paragraph is dropped"


@pytest.fixture
def fake(monkeypatch):
    f = Fake()
    monkeypatch.setattr(promptgen, "run_claude", f)
    return f


def settle(c, pid):
    for _ in range(100):
        g = get(c, pid)["generation"]
        if g["state"] != "running":
            return g
        time.sleep(0.05)
    raise AssertionError("the writer did not finish")


def texts(c, pid):
    return [p["text"] for p in get(c, pid)["prompts"]]


def approve_analysis(c, pid):
    r = c.post(f"/projects/{pid}/approve", json={"gate": "analysis"})
    assert r.status_code == 200, r.text


def test_approving_the_analysis_writes_every_prompt_and_keeps_the_history(proj, fake):
    c, pid, _ = proj
    before = get(c, pid)["prompts"]
    approve_analysis(c, pid)
    g = settle(c, pid)
    assert g["state"] == "done" and g["kind"] == "all" and g["done"] == g["total"] == len(before) and g["failed"] == []
    after = get(c, pid)["prompts"]
    assert all(p["text"].startswith("Generated scene image") and "extra paragraph" not in p["text"] for p in after)
    assert all(p["history"][-1]["by"] == "regenerated" and p["history"][-1]["text"] == b["text"] for p, b in zip(after, before))
    assert fake.calls == len(before)


def test_a_text_the_user_changes_while_it_is_written_is_kept(proj, fake):
    c, pid, pdir = proj
    fake.during = lambda: review.save_prompt(pdir, 1, "Changed by the user in the middle of the run") if fake.calls == 1 else None
    approve_analysis(c, pid)
    g = settle(c, pid)
    assert get(c, pid)["prompts"][0]["text"] == "Changed by the user in the middle of the run" and 1 in g["skipped"] and g["state"] == "done"


def test_a_run_left_on_running_by_a_restart_shows_as_failed(proj, fake):
    c, pid, pdir = proj
    promptgen._record(pdir, state="running", kind="all", total=3)
    g = get(c, pid)["generation"]
    assert g["state"] == "failed" and "Retry" in g["error"]


def test_a_finished_worker_never_frees_the_job_a_retry_started(tmp_path):
    """Only the thread that runs the generation job releases it: an old worker finishing after a Retry started a new run must not free (and so
    'interrupt') the new one."""
    gate = threading.Event()
    with promptgen._guard:
        promptgen.launch(tmp_path, lambda p: gate.wait(5))
    owner = promptgen._running[str(tmp_path)]
    other = threading.Thread(target=promptgen._release, args=(tmp_path,))                  # a worker that is not the owner
    other.start()
    other.join()
    assert promptgen._running[str(tmp_path)] is owner
    gate.set()
    owner.join(5)
    assert str(tmp_path) not in promptgen._running                                         # the owner released it when it finished
