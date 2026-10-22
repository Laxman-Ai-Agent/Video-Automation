"""Root conftest: loaded for every test folder (tests/ and SYSTEM/**/tests).

Many modules keep their state in files inside the repository (agent memory, LLM usage,
shared memory, skill catalog, approvals queue, generated scenes). Tests that run those
modules write there. This fixture puts every such file back as it was when the run ends,
and removes the ones the run created, so a test run never changes the checkout.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent

# Browser (Playwright) checks drive a running UI at http://localhost:5173 and need a browser: they are opt-in (A2V_BROWSER_TESTS=1), not part of a plain `pytest`.
collect_ignore_glob = [] if os.environ.get("A2V_BROWSER_TESTS") == "1" else ["tests/test_playwright_*.py", "tests/test_verify_*.py", "verify_timeline_ui.py"]
STATE_DIRS = ("SYSTEM", "config", "VIDEO_ENGINE/remotion/src/generated")
STATE_SUFFIXES = {".json", ".jsonl", ".md", ".ts", ".tsx"}
PUBLIC_DIR = ROOT / "VIDEO_ENGINE" / "remotion" / "public"   # large media: only files a run adds are removed


def _state_files() -> dict[Path, bytes]:
    files: dict[Path, bytes] = {}
    for d in STATE_DIRS:
        for p in (ROOT / d).rglob("*"):
            if p.suffix in STATE_SUFFIXES and "node_modules" not in p.parts and p.is_file():
                files[p] = p.read_bytes()
    return files


@pytest.fixture(scope="session", autouse=True)
def repository_state_unchanged():
    # ponytail: restores at session end, so a file a person edits in these folders during a run is reverted; isolate each store per test if that matters
    before = _state_files()
    public_before = {p for p in PUBLIC_DIR.rglob("*") if p.is_file()}
    yield
    for p in {p for p in PUBLIC_DIR.rglob("*") if p.is_file()} - public_before:
        p.unlink(missing_ok=True)
    for p, data in _state_files().items():
        if p not in before:
            p.unlink(missing_ok=True)
        elif data != before[p]:
            p.write_bytes(before[p])
    for p, data in before.items():
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)


@pytest.fixture
def llm_review_says(monkeypatch):
    """Opt-in: every LLM review (stage reviews, Final QC, approval requests) answers with the verdict last given to the returned function
    (default: passed, 0.9, no findings); the review code itself still runs and saves its record. Other gateway calls go through unchanged.
    Tests of the review gate itself must not use this."""
    from SYSTEM.core import llm_gateway
    inner = llm_gateway.gateway.execute
    answer: dict = {}

    def execute(req):
        if req.purpose != "review":
            return inner(req)
        return llm_gateway.LlmGatewayResponse(
            request_id=req.request_id, correlation_id=req.correlation_id, project_id=req.project_id, stage_id=req.stage_id,
            agent_id=req.agent_id, purpose=req.purpose, status="passed", raw_text="", structured_data=dict(answer),
            model_profile=req.model_profile, provider="stub", model="stub", latency_ms=1, attempt_count=1)

    def say(status="passed", score=0.9, findings=()):
        answer.clear()
        answer.update(status=status, score=score, summary=f"stub review: {status}", findings=list(findings))

    say()
    monkeypatch.setattr(llm_gateway.gateway, "execute", execute)
    return say
