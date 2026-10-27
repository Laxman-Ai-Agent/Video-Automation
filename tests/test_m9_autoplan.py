"""Automatic planning (backend/autoplan.py): starts when transcription and cut points are done, builds the same files /plan builds, shows progress,
fails without leaving a half plan, retries without a second job and leaves existing plans alone. The Claude CLI and the Remotion build are fakes.
Run: python -m pytest tests/test_m9_autoplan.py -q"""
import importlib
import json
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

import pytest

from VIDEO_ENGINE.stages import visual_planning
from backend import autoplan, plan_checks, promptgen  # plan_checks is imported now: it reads VIDEO_ENGINE/remotion/src/patterns/images.json when first imported

_m7 = importlib.import_module("test_m7")
client, create, wait_job, FIXTURE = _m7.client, _m7.create, _m7.wait_job, _m7.FIXTURE
PLAN_FILES = ("scene_plan.json", "prompts_map.json", "composition.json")          # (prompts.txt, the image prompt list, belongs to the removed image workflow)


class Llm:
    """The Claude CLI: answers the translation and the plan, counts calls, can fail, block, or be told what the checks find."""
    def __init__(self):
        self.calls = []
        self.fail = {}                       # stage -> remaining failures ("translate" / "plan")
        self.gate = None
        self.during = None

    def __call__(self, user, system="", timeout=0):
        stage = "translate" if system == autoplan.TRANSLATE_SYSTEM else "visual" if system == visual_planning.VISUAL_SYSTEM else "plan"
        self.calls.append(stage)
        if self.gate:
            self.gate.wait(5)
        if stage == "visual":                # the Visual Planning call over the scene plan that was just published (within the shares of the default 60/30/10: one ask)
            _v = importlib.import_module("test_visual_planning")
            return json.dumps({"visual_plan": _v.raw_for(json.loads((FIXTURE / "scene_plan.json").read_text(encoding="utf-8")), _v.REAL)})
        if self.during and stage == "plan":
            self.during()
        if self.fail.get(stage, 0) > 0:
            self.fail[stage] -= 1
            raise promptgen.GenError("not signed in")
        if stage == "translate":
            return json.dumps({"segments": []})
        read = lambda n: json.loads((FIXTURE / n).read_text(encoding="utf-8"))
        return "Here is the plan:\n" + json.dumps({"scene_plan": read("scene_plan.json"), "prompts_map": read("prompts_map.json")})


@pytest.fixture
def auto(client, monkeypatch):
    llm = Llm()
    monkeypatch.setattr(promptgen, "run_claude", llm)
    monkeypatch.setattr(autoplan, "ENABLED", True)
    from backend import transcript_review
    monkeypatch.setattr(transcript_review, "is_verified", lambda pdir: True)       # the Audio Analyzer's LLM check is tested elsewhere; here the plan job is
    real = subprocess.run

    def run(cmd, *a, **k):
        if isinstance(cmd, str) and "build_composition.ts" in cmd:
            shutil.copyfile(FIXTURE / "composition.json", Path(re.search(r'"([^"]+)"', cmd).group(1)) / "composition.json")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return real(cmd, *a, **k)

    monkeypatch.setattr(subprocess, "run", run)
    rounds = []                              # plan_checks errors, one list per call to the checks (then none)
    monkeypatch.setattr(plan_checks, "check", lambda pdir: (rounds.pop(0) if rounds else [], []))
    llm.problems = rounds
    yield client, llm
    if llm.gate:
        llm.gate.set()
    for _ in range(200):                     # a planning thread must not outlive its test: it would call the NEXT test's fake Claude (promptgen.run_claude) and eat its answers
        if not promptgen._running:
            break
        time.sleep(0.05)
    assert not promptgen._running, f"planning threads still running after the test: {promptgen._running}"


def generation(c, pid):
    from backend import store
    return promptgen.state(store.project_dir(pid))                  # the generation record (there is no page that reads it any more)


def settle(c, pid):
    for _ in range(200):
        g = generation(c, pid)
        if g["state"] in ("done", "failed"):
            return g
        time.sleep(0.05)
    raise AssertionError(f"planning did not finish: {generation(c, pid)}")


def upload_and_transcribe(c, run_plan=True):
    """Upload, analyze, and (like a click on Run Visual Planning) start the planning: nothing plans by itself any more after the analysis."""
    pid = create(c).json()["id"]
    assert c.post(f"/projects/{pid}/transcribe").status_code == 202
    wait_job(c, pid)
    if run_plan:
        r = c.post(f"/projects/{pid}/visual-planning/run")
        assert r.status_code == 202, r.text
    return pid, _m7.config.PROJECTS_DIR / pid


def test_planning_does_not_start_by_itself_after_the_analysis(auto):
    c, llm = auto
    pid, pdir = upload_and_transcribe(c, run_plan=False)
    time.sleep(0.5)
    assert llm.calls == [] and generation(c, pid)["state"] == "idle" and not (pdir / "scene_plan.json").exists()      # it waits for the user's Run Visual Planning


def test_planning_runs_on_the_run_request_and_builds_the_plan_files(auto):
    c, llm = auto
    pid, pdir = upload_and_transcribe(c)
    g = settle(c, pid)
    assert g["kind"] == "plan" and g["state"] == "done" and g["done"] == g["total"] == 4 and g["error"] is None
    assert all((pdir / f).exists() for f in (*PLAN_FILES, "translation.json", "transcript_en.json", "plan_input.txt"))
    assert llm.calls == ["translate", "plan", "visual"]
    from backend import review
    assert review.plan_blockers(pdir) == [] and "generated_for" not in (pdir / "review.json").read_text(encoding="utf-8")      # the plan can be used and no prompt was written


def test_planning_does_not_start_before_the_transcription_job_has_finished(auto):
    c, llm = auto
    pid = create(c).json()["id"]
    assert generation(c, pid)["state"] == "idle" and llm.calls == []
    assert c.get(f"/projects/{pid}/status").json()["waiting_for"] is None


def test_progress_is_visible_while_it_runs(auto):
    c, llm = auto
    llm.gate = threading.Event()
    pid, _ = upload_and_transcribe(c)
    for _ in range(100):
        g = generation(c, pid)
        if g["state"] == "running":
            break
        time.sleep(0.05)
    assert g["state"] == "running" and g["kind"] == "plan" and g["total"] == 4 and g["current"] == 1
    llm.gate.set()
    assert settle(c, pid)["state"] == "done"


def test_a_failure_is_reported_leaves_no_half_plan_and_keeps_the_manual_command(auto):
    c, llm = auto
    llm.fail["plan"] = 1
    pid, pdir = upload_and_transcribe(c)
    g = settle(c, pid)
    assert g["state"] == "failed" and g["error"].startswith("Writing the scene plan: not signed in")
    assert not any((pdir / f).exists() for f in PLAN_FILES)
    s = c.get(f"/projects/{pid}/status").json()
    assert s["waiting_for"] == "plan" and s["command"] == f"/plan {pid}"             # the manual recovery is still offered


def test_retry_continues_without_repeating_finished_work_and_without_a_second_job(auto):
    c, llm = auto
    llm.fail["plan"] = 1
    pid, pdir = upload_and_transcribe(c)
    settle(c, pid)
    assert llm.calls == ["translate", "plan"]                                           # the plan failed once: nothing was planned over it
    r = c.post(f"/projects/{pid}/visual-planning/run")
    assert r.status_code == 202 and r.json()["kind"] == "plan"
    g = settle(c, pid)
    assert g["state"] == "done" and all((pdir / f).exists() for f in PLAN_FILES)
    assert llm.calls == ["translate", "plan", "plan", "visual"]                                  # the translation was not asked again
    again = c.post(f"/projects/{pid}/visual-planning/run")                                 # the plan exists: only the visual plan is made over it, the scene plan is not planned again
    assert again.status_code == 202 and llm.calls[:3] == ["translate", "plan", "plan"] and llm.calls.count("translate") == 1
    settle(c, pid)


def test_clicking_retry_repeatedly_runs_one_job(auto):
    c, llm = auto
    llm.fail["translate"] = 1
    pid, _ = upload_and_transcribe(c)
    settle(c, pid)
    llm.gate = threading.Event()
    first = c.post(f"/projects/{pid}/visual-planning/run").json()
    second = c.post(f"/projects/{pid}/visual-planning/run").json()
    assert first["state"] == second["state"] == "running" and first["started"] == second["started"]
    llm.gate.set()
    assert settle(c, pid)["state"] == "done"
    assert llm.calls.count("translate") == 2 and llm.calls.count("plan") == 1


def test_a_plan_that_fails_the_checks_is_corrected_once_and_a_second_failure_publishes_nothing(auto):
    c, llm = auto
    llm.problems += [["scene 2: 3 prompts but pattern 'hero_only' shows 1 images"], []]
    pid, pdir = upload_and_transcribe(c)
    assert settle(c, pid)["state"] == "done" and llm.calls == ["translate", "plan", "plan", "visual"]

    llm.problems += [["coverage: first scene starts at 1"], ["coverage: first scene starts at 1"]]
    pid2, pdir2 = upload_and_transcribe(c)
    g = settle(c, pid2)
    assert g["state"] == "failed" and "did not pass the checks" in g["error"] and "coverage" in g["error"]
    assert not any((pdir2 / f).exists() for f in PLAN_FILES)


def test_a_plan_made_by_hand_meanwhile_is_never_replaced(auto):
    c, llm = auto
    pid = create(c).json()["id"]
    pdir = _m7.config.PROJECTS_DIR / pid
    mine = (FIXTURE / "scene_plan.json").read_text(encoding="utf-8") + chr(10) * 2   # a valid plan, recognisable by its two trailing newlines

    def user_runs_plan():
        (pdir / "scene_plan.json").write_text(mine, encoding="utf-8")
        shutil.copyfile(FIXTURE / "prompts_map.json", pdir / "prompts_map.json")
    llm.during = user_runs_plan
    c.post(f"/projects/{pid}/transcribe")
    wait_job(c, pid)
    assert c.post(f"/projects/{pid}/visual-planning/run").status_code == 202          # the user clicks Run Visual Planning
    g = settle(c, pid)
    assert g["state"] == "done" and (pdir / "scene_plan.json").read_text(encoding="utf-8") == mine and not (pdir / "composition.json").exists()


def test_existing_projects_with_a_plan_are_not_planned_again(auto):
    c, llm = auto
    pid = create(c).json()["id"]
    pdir = _m7.install_plan(pid)
    before = {f: (pdir / f).read_bytes() for f in ("scene_plan.json", "prompts_map.json", "composition.json")}
    c.post(f"/projects/{pid}/transcribe")
    wait_job(c, pid)
    time.sleep(0.3)
    assert llm.calls == [] and generation(c, pid)["state"] == "idle"
    assert {f: (pdir / f).read_bytes() for f in before} == before
    # the run endpoint on a project with a plan makes the visual plan over it (the scene plan, prompts and composition are never changed)
    assert c.post(f"/projects/{pid}/visual-planning/run").status_code == 202
    settle(c, pid)
    assert {f: (pdir / f).read_bytes() for f in before} == before


def test_a_project_that_was_already_waiting_is_planned_from_the_generate_endpoint(auto, monkeypatch):
    c, llm = auto
    monkeypatch.setattr(autoplan, "ENABLED", False)                       # transcribed earlier, before the automation existed
    pid, pdir = upload_and_transcribe(c)
    assert llm.calls == [] and c.get(f"/projects/{pid}/status").json()["waiting_for"] == "plan"
    assert c.post(f"/projects/{pid}/visual-planning/run").status_code == 202
    assert settle(c, pid)["state"] == "done" and (pdir / "prompts_map.json").exists()


def test_a_run_request_on_a_planned_project_never_changes_the_prompts(auto):
    c, llm = auto
    pid, pdir = upload_and_transcribe(c)
    settle(c, pid)
    prompts = lambda: [p["text"] for p in json.loads((pdir / "prompts_map.json").read_text(encoding="utf-8"))["prompts"]]
    texts = prompts()
    assert c.post(f"/projects/{pid}/visual-planning/run").status_code == 202            # plan exists: the visual plan is made over it
    settle(c, pid)
    assert prompts() == texts and llm.calls[:2] == ["translate", "plan"]


def test_run_waits_for_the_plan_and_raises_the_cause_when_it_fails(auto):
    """autoplan.run is the plan job in the caller's thread (the orchestrator's planning stage): a failure names its cause and leaves no half plan, the next call plans."""
    c, llm = auto
    pid, pdir = upload_and_transcribe(c, run_plan=False)
    llm.fail["plan"] = 1
    with pytest.raises(promptgen.GenError, match="not signed in"):
        autoplan.run(pdir)
    assert generation(c, pid)["state"] == "failed" and not promptgen._running
    assert not any((pdir / f).exists() for f in PLAN_FILES)
    autoplan.run(pdir)
    assert generation(c, pid)["state"] == "done" and all((pdir / f).exists() for f in PLAN_FILES) and not promptgen._running
