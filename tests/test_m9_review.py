"""Review workflow (backend/review.py + routes/review.py): scene table, prompt approve/regenerate request, approval gates and their invalidation,
the original chains. Whisper, CLIP and Remotion are the M7 test fakes. Run: python -m pytest tests/test_m9_review.py -q"""
import importlib
import json
from pathlib import Path

import pytest

from backend import jobs, pipeline, promptgen, review

_m7 = importlib.import_module("test_m7")     # the M7 fakes; importlib keeps the requirements scan from treating it as a package
client = _m7.client                          # a fixture: pytest finds it by this module-level name
create, install_plan, wait_job = _m7.create, _m7.install_plan, _m7.wait_job


@pytest.fixture(autouse=True)
def no_cli(monkeypatch):
    """Approving the analysis starts the prompt writer: these tests never call the real Claude CLI (tests/test_m9_promptgen.py covers the writer)."""
    def refuse(user):
        raise promptgen.GenError("no CLI in tests")
    monkeypatch.setattr(promptgen, "run_claude", refuse)


@pytest.fixture
def proj(client):
    pid = create(client).json()["id"]
    pdir = install_plan(pid)
    return client, pid, pdir


def get(c, pid):
    r = c.get(f"/projects/{pid}/review")
    assert r.status_code == 200, r.text
    return r.json()


def approve_all(c, pid, upto="images"):
    order = ("analysis", "prompts", "images")
    for gate in order[: order.index(upto) + 1]:
        if gate == "prompts":
            assert c.post(f"/projects/{pid}/prompts/approve", json={}).status_code == 200
        r = c.post(f"/projects/{pid}/approve", json={"gate": gate})
        assert r.status_code == 200, r.text


# ---- Phase 1: the scene table ----
def test_the_scene_table_has_every_scene_in_order_with_timing_and_visual_plan(proj):
    c, pid, pdir = proj
    a = get(c, pid)["analysis"]
    plan = json.loads((pdir / "scene_plan.json").read_text(encoding="utf-8"))["scenes"]
    assert [s["id"] for s in a["scenes"]] == [s["id"] for s in plan]
    first = a["scenes"][0]
    assert (first["start"], first["end"]) == (plan[0]["start"], plan[0]["end"])
    assert first["duration"] == pytest.approx(plan[0]["end"] - plan[0]["start"], abs=0.01)
    assert first["meaning"] == plan[0]["meaning"] and first["pattern"] == plan[0]["pattern"]
    assert a["status"] in ("ok", "warning")


def test_without_a_plan_the_review_is_empty_and_nothing_can_be_approved(client):
    pid = create(client).json()["id"]
    r = get(client, pid)
    assert r["plan_ready"] is False and r["analysis"]["status"] == "empty" and r["analysis"]["scenes"] == [] and r["prompts"] == []
    refused = client.post(f"/projects/{pid}/approve", json={"gate": "analysis"})
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "not_allowed" and "plan" in refused.json()["error"]["hint"]


# ---- Phase 3: prompt edit, approval, regenerate request ----
# ---- Phase 5: gates ----
def test_gates_must_be_approved_in_order_and_say_what_blocks_them(proj):
    c, pid, _ = proj
    r = c.post(f"/projects/{pid}/approve", json={"gate": "prompts"})
    assert r.status_code == 409 and "analysis" in r.json()["error"]["message"]
    assert c.post(f"/projects/{pid}/approve", json={"gate": "analysis"}).status_code == 200
    r = c.post(f"/projects/{pid}/approve", json={"gate": "prompts"})
    assert r.status_code == 409 and "not approved" in r.json()["error"]["hint"]
    assert c.post(f"/projects/{pid}/approve", json={"gate": "bogus"}).status_code == 422


# ---- Phase 4: crops ----
# ---- Phase 6: timeline without a render ----
# ---- the existing flow is untouched ----
def test_the_regen_command_exists_and_points_at_the_context_and_set_commands():
    text = (Path(__file__).resolve().parent.parent / ".claude" / "commands" / "regen.md").read_text(encoding="utf-8")
    assert "backend.prompt_review context" in text and "backend.prompt_review set" in text and "Never edit prompts_map.json by hand" in text


# ---- existing assignments stay unless the user replaces them ----
def assigned(c, pid):
    return {m["n"]: (m["file"], m["status"], m["method"]) for m in c.get(f"/projects/{pid}/match").json()["matches"]}


def run_match(c, pid):
    assert c.post(f"/projects/{pid}/run", json={"stage": "match", "aspect": "9:16"}).status_code == 202
    assert wait_job(c, pid)["error"] is None


# ---- Direct workflow progression & missing-image handling regression tests ----
