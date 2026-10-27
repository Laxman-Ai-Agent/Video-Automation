"""Automatic planning: what `/plan <id>` does by hand, done by the app with the user's signed-in Claude CLI (promptgen.run_claude; no API key, no new provider).
It starts by itself when transcription and cut points have finished (jobs.py), or from POST /prompts/generate (retry, or a project that was already waiting).
  1. translation.json   Telugu -> English, same ids (translate_io), then transcript_en.json + plan_input.txt
  2. scene plan         scene_plan.json + prompts_map.json, written from the instructions of .claude/commands/plan.md steps 3-5 and the real schemas
  3. checks             composition.json (remotion build_composition.ts), validate, plan_checks, prompts.txt
Everything is built in a temp folder first and published only when it passed, with prompts_map.json last, so a failed or half-finished run leaves
no plan behind (the UI keeps showing "waiting for the plan" with the manual /plan command as the recovery). An existing plan is never replaced.
Progress lives in review.json "generation" (kind "plan", 3 stages), shared with promptgen so there is never a second job for a project."""
import json
import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from pydantic import ValidationError

from . import config, llm_review, plan_input, promptgen, review, store, translate_io, visual_planning
from .models import PromptsMap, ScenePlan
from .promptgen import GenError
from .validate import validate_project

ENABLED = os.environ.get("AUTOPLAN", "1") != "0"
STAGES = ("Translating the narration", "Writing the scene plan", "Checking the plan", "Planning the visuals")
TRANSLATE_TIMEOUT, PLAN_TIMEOUT = 300, 900
CODE_ROOT = Path(__file__).resolve().parent.parent
AUDIO_NAMES = ("audio.mp3", "audio.wav", "audio.m4a")

TRANSLATE_SYSTEM = ('Translate Telugu narration lines to clean English (keep the meaning, fix obvious ASR slips, keep the ids). '
                    'Output ONLY one JSON object: {"segments":[{"id":0,"en":"..."}]} with every id of the input. No markdown, no comments.')
PLAN_SYSTEM = ("You plan a documentary video from an English narration. TEXT ONLY, English only, no images. Output ONLY one JSON object "
               '{"scene_plan": {...}, "prompts_map": {...}} that follows the given schemas exactly. No markdown, no comments, no extra keys. (The visual plan is a separate step: Visual Planning.)')


class _Kept(Exception):
    """A plan appeared while this one was being written (the user ran /plan): theirs stays."""


def needs_plan(pdir: Path) -> bool:
    has = lambda n: (pdir / n).exists()
    return has("transcript.json") and has("cuts.json") and not has("scene_plan.json") and not has("prompts_map.json")


def _json_from(text: str) -> dict:
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b <= a:
        raise GenError("the answer contained no JSON")
    try:
        data = json.loads(text[a:b + 1])
    except ValueError as e:
        raise GenError(f"the answer was not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise GenError("the answer was not a JSON object")
    return data


def _instructions() -> str:
    """Steps 3-5 of the /plan command (scene splitting, scene_plan fields, prompts_map fields), plus the exact schemas and the pattern image counts."""
    plan_md = CODE_ROOT / ".claude" / "commands" / "plan.md"
    if not plan_md.exists():
        plan_md = CODE_ROOT.parent / ".claude" / "commands" / "plan.md"
    text = plan_md.read_text(encoding="utf-8")
    a, b = text.find("3. Split into scenes"), text.find("6. Build and check")
    if a < 0 or b <= a:
        raise GenError("the planning instructions (.claude/commands/plan.md) were not found")
    patterns = (config.REMOTION_DIR / "src" / "patterns" / "images.json").read_text(encoding="utf-8")
    return (f"{text[a:b].strip()}\n\nPattern -> number of image slots:\n{patterns}\n\nscene_plan schema:\n{json.dumps(ScenePlan.model_json_schema())}\n\n"
            f"prompts_map schema:\n{json.dumps(PromptsMap.model_json_schema())}\n\nplan_input.txt:\n")


# ---------- stage 1 ----------
def _translate(pdir: Path) -> None:
    if (pdir / "translation.json").exists():              # a finished translation (from /plan or an earlier run) is kept
        try:
            translate_io.merge(pdir)
            return
        except (ValueError, KeyError, OSError):
            pass
    asked = translate_io.prepare(pdir)
    segs = _json_from(promptgen.run_claude(asked, system=TRANSLATE_SYSTEM, timeout=TRANSLATE_TIMEOUT)).get("segments")
    if not isinstance(segs, list) or not all(isinstance(s, dict) and isinstance(s.get("id"), int) and str(s.get("en", "")).strip() for s in segs):
        raise GenError("the translation answer had the wrong shape")
    (pdir / "translation.json").write_text(json.dumps({"segments": [{"id": s["id"], "en": str(s["en"]).strip()} for s in segs]}, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        translate_io.merge(pdir)
    except ValueError as e:
        (pdir / "translation.json").replace(pdir / "translation.rejected.json")   # keep what was answered, but do not let it pass as a translation
        raise GenError(str(e)) from e


# ---------- stage 2 and 3 ----------
def _stage(pdir: Path, sp: dict, pm: dict, d: Path) -> list[str]:
    """Build the whole plan in folder d and return everything that is wrong with it (empty = ready to publish)."""
    try:
        ScenePlan.model_validate(sp)
        PromptsMap.model_validate(pm)
    except ValidationError as e:
        return [f"{'.'.join(str(p) for p in x['loc'])}: {x['msg']}" for x in e.errors()[:8]]
    for name in ("transcript.json", "transcript_fixed.json", "transcript_corrected.json", "transcript_en.json", "cuts.json", "scene_segmentation.json", "audio_analysis.json"):    # Scene Segmentation too: the checks compare the plan with it
        if (pdir / name).exists():
            shutil.copyfile(pdir / name, d / name)
    (d / "scene_plan.json").write_text(json.dumps(sp, ensure_ascii=False, indent=1), encoding="utf-8")
    (d / "prompts_map.json").write_text(json.dumps(pm, ensure_ascii=False, indent=1), encoding="utf-8")
    r = subprocess.run(f'npx tsx scripts/build_composition.ts "{d.resolve()}"', cwd=config.REMOTION_DIR, shell=True,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        return ["build_composition failed: " + (r.stderr or r.stdout)[-300:]]
    comp = json.loads((d / "composition.json").read_text(encoding="utf-8"))
    comp["meta"]["audio"] = next((n for n in AUDIO_NAMES if (pdir / n).exists()), comp["meta"]["audio"])    # the staging folder has no audio file
    (d / "composition.json").write_text(json.dumps(comp, indent=1), encoding="utf-8")
    from . import plan_checks                              # reads VIDEO_ENGINE/remotion/src/patterns/images.json when imported
    errors, _ = plan_checks.check(d)
    errors += validate_project(d)
    return errors


BACKED_UP = ("scene_plan.json", "prompts_map.json", "composition.json", "prompts.txt", visual_planning.FILE, "plan_input.txt", "visual_plan.json")      # visual_plan.json = the user's edits


def replace_blocker(pdir: Path) -> str | None:
    """Why a scene plan that does not follow Scene Segmentation must NOT be made again (the user's work depends on it): pictures were uploaded or prompts were approved. None = it may be replaced."""
    if not store.uses_images(pdir):
        return None
    from .api_status import image_count
    if image_count(pdir):
        return "images were already uploaded for the current prompts: remove them (or make a new project) before the plan is made again"
    return None


def _backup(pdir: Path) -> Path:
    """The plan that is replaced is kept, never deleted: plan_backups/<time>/ next to the new one."""
    dest = pdir / "plan_backups" / review.now().replace(":", "-")
    dest.mkdir(parents=True, exist_ok=True)
    for name in BACKED_UP:
        if (pdir / name).exists():
            shutil.copyfile(pdir / name, dest / name)
    return dest


def _publish(pdir: Path, d: Path, replace: bool = False) -> None:
    if replace:
        _backup(pdir)
    elif (pdir / "scene_plan.json").exists() or (pdir / "prompts_map.json").exists():
        raise _Kept()
    for name in ("composition.json", "prompts.txt", "scene_plan.json", "prompts_map.json"):      # the file that makes the plan "ready" goes last
        if (d / name).exists():
            tmp = pdir / (name + ".tmp")
            shutil.copyfile(d / name, tmp)
            tmp.replace(pdir / name)


def _plan(pdir: Path, replace: bool = False) -> None:
    pi = plan_input.build(pdir)
    (pdir / "plan_input.txt").write_text(pi, encoding="utf-8")
    asked = _instructions() + pi
    answer = promptgen.run_claude(asked, system=PLAN_SYSTEM, timeout=PLAN_TIMEOUT)
    promptgen._record(pdir, done=2, current=3)                                  # the answer is here: what follows is checking (the scene plan and the prompts against the legacy checks)
    d = Path(tempfile.mkdtemp(prefix="autoplan-"))
    try:
        for attempt in (0, 1):
            try:
                data = _json_from(answer)
                errors = _stage(pdir, data["scene_plan"], data["prompts_map"], d)
            except (GenError, KeyError, TypeError) as e:
                errors = [f"the answer needs both scene_plan and prompts_map as JSON objects ({e})"]
            if not errors:
                _publish(pdir, d, replace)
                return
            if attempt:
                raise GenError("the plan did not pass the checks: " + "; ".join(errors[:4]))
            answer = promptgen.run_claude(f"{asked}\n\nYour previous answer had these problems:\n- " + "\n- ".join(errors[:12]) +
                                          "\n\nReturn the complete corrected JSON object.", system=PLAN_SYSTEM, timeout=PLAN_TIMEOUT)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _generate(pdir: Path, replace: bool = False) -> None:
    """Stages 1 and 2 of the plan job: translate the narration, then write and publish the plan."""
    promptgen._record(pdir, current=1, done=0)
    _translate(pdir)
    promptgen._record(pdir, current=2, done=1)
    _plan(pdir, replace)
    promptgen._record(pdir, current=4, done=3)
    visual_planning.run(pdir)                                           # the visuals of the scene plan that was just published (the planner call of Visual Planning, its own checks)


def _begin(pdir: Path) -> None:
    promptgen._record(pdir, kind="plan", n=None, total=len(STAGES), done=0, failed=[], skipped=[], current=1, error=None,
                      started=review.now(), finished=None, state="running")


def run(pdir: Path, replace: bool = False) -> None:
    """The plan job of start(), done in the caller's thread (the orchestrator's planning stage waits for it). Raises GenError with the cause when no plan was published;
    an existing plan is left alone unless `replace` (same rules as start())."""
    with promptgen._guard:
        if str(pdir) in promptgen._running:
            raise review.ReviewError("this project is being planned right now: wait until that finishes")
        if replace and (why := replace_blocker(pdir)):
            raise review.ReviewError(why)
        _begin(pdir)
        promptgen._running[str(pdir)] = threading.current_thread()
    try:
        _generate(pdir, replace)
        promptgen._record(pdir, state="done", done=len(STAGES), current=None, error=None, finished=review.now())
    except _Kept:
        promptgen._record(pdir, state="done", done=len(STAGES), current=None, error=None, finished=review.now())
    except Exception as e:
        stage = promptgen.state(pdir).get("current") or 1
        err_msg = f"{STAGES[min(stage, len(STAGES)) - 1]}: {e}"
        promptgen._record(pdir, state="failed", error=err_msg, current=None, finished=review.now())
        raise GenError(err_msg) from e
    finally:
        promptgen._release(pdir)


def _work(pdir: Path, replace: bool = False) -> None:
    try:
        from SYSTEM.agents.shared import communication
        communication.publish_lifecycle_event(
            project_id=pdir.name,
            stage_id="planning",
            sender_agent_id="visual_planning",
            event="stage_started",
            detail="Visual Planning generation started",
        )
    except Exception:
        pass

    try:
        _generate(pdir, replace)
        llm_review.run_stage_llm_review(pdir, "planning")
        promptgen._record(pdir, state="done", done=len(STAGES), current=None, error=None, finished=review.now())
        try:
            from SYSTEM.agents.shared import communication
            from SYSTEM.agents.shared.contracts import ArtifactRef
            communication.publish_message(
                project_id=pdir.name,
                stage_id="planning",
                sender_agent_id="visual_planning",
                recipient_agent_ids=["main_orchestrator", "motion_planning"],
                content="Visual Planning completed successfully. Scene plan, visual plan, and Remotion composition verified.",
                status="completed",
                artifact_refs=[
                    ArtifactRef(path=str(pdir / "scene_plan.json"), description="Scene Plan"),
                    ArtifactRef(path=str(pdir / visual_planning.FILE), description="Visual Planning Specification"),
                    ArtifactRef(path=str(pdir / "composition.json"), description="Remotion Composition"),
                ],
                metadata={"status": "completed"},
            )
            communication.publish_lifecycle_event(
                project_id=pdir.name,
                stage_id="planning",
                sender_agent_id="visual_planning",
                event="completed",
                detail="Visual Planning completed successfully",
            )
            try:
                from SYSTEM.core import pipeline_state
                from UI.backend import pipeline_view
                asp = pipeline_view.aspect_of(pdir)
                try:
                    pipeline_state.transition_stage(pdir, "planning", "running", aspect=asp)
                except Exception:
                    pass
                pipeline_state.transition_stage(pdir, "planning", "completed", aspect=asp)
            except Exception:
                pass
        except Exception:
            pass
    except _Kept:
        promptgen._record(pdir, state="done", done=len(STAGES), current=None, error=None, finished=review.now())
    except GenError as e:
        stage = promptgen.state(pdir).get("current") or 1
        err_msg = f"{STAGES[min(stage, len(STAGES)) - 1]}: {e}"
        promptgen._record(pdir, state="failed", error=err_msg, current=None, finished=review.now())
        try:
            from SYSTEM.agents.shared import communication
            communication.publish_message(
                project_id=pdir.name,
                stage_id="planning",
                sender_agent_id="visual_planning",
                recipient_agent_ids=["main_orchestrator"],
                content=f"Visual Planning execution failed at stage {stage} ({STAGES[min(stage, len(STAGES)) - 1]}): {e}",
                status="failed",
                metadata={"error": err_msg, "stage": stage},
            )
            communication.publish_lifecycle_event(
                project_id=pdir.name,
                stage_id="planning",
                sender_agent_id="visual_planning",
                event="failed",
                detail=err_msg,
            )
        except Exception:
            pass
    except Exception as e:                                                  # never leave the record on "running"
        err_msg = f"unexpected error: {e}"
        promptgen._record(pdir, state="failed", error=err_msg, current=None, finished=review.now())
        try:
            from SYSTEM.agents.shared import communication
            communication.publish_message(
                project_id=pdir.name,
                stage_id="planning",
                sender_agent_id="visual_planning",
                recipient_agent_ids=["main_orchestrator"],
                content=f"Visual Planning unexpected failure: {err_msg}",
                status="failed",
                metadata={"error": str(e)},
            )
            communication.publish_lifecycle_event(
                project_id=pdir.name,
                stage_id="planning",
                sender_agent_id="visual_planning",
                event="failed",
                detail=err_msg,
            )
        except Exception:
            pass


def start(pdir: Path, replace: bool = False) -> dict:
    """Plan this project. Returns the state; asking again while it runs returns the running job, and a project that has its plan is left alone.
    `replace`: only for a scene plan that does not follow the current Scene Segmentation (visual_planning.plan_mismatch): it is made again from the segmentation, the old files are kept in plan_backups/."""
    key = str(pdir)
    with promptgen._guard:
        if key in promptgen._running:
            cur = promptgen.state(pdir)
            if cur["kind"] == "plan":
                return cur
            raise review.ReviewError("prompts are being written right now: wait until that finishes")
        if replace:
            if not visual_planning.plan_mismatch(pdir):
                raise review.ReviewError("the scene plan follows Scene Segmentation: there is nothing to replace")
            if (why := replace_blocker(pdir)):
                raise review.ReviewError(why)
        elif not needs_plan(pdir):
            return promptgen.state(pdir)
        _begin(pdir)
        promptgen.launch(pdir, _work, replace)
    return promptgen.state(pdir)


def maybe_start(pdir: Path) -> None:
    """Plan by itself (never for a project that has a plan, never when switched off). NOT called automatically any more: Visual Planning starts only when the user runs it (POST /prompts/generate)."""
    if ENABLED and needs_plan(pdir):
        try:
            start(pdir)
        except review.ReviewError:
            pass
