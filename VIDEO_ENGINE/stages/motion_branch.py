"""The right-hand branch of the Pipeline page: Motion Planning -> Motion Generation (steps motion-plan / motion-build in pipeline.py). It runs next to the image
branch (Asset Collection -> Image Generation) and both must be complete before the Timeline Build. With Use Images OFF it is the only branch.
Nothing is stored here: the state is read from the step fingerprints (pipeline.is_fresh) and the files, so a refresh or a restart gives the same answer.
Projects made before the branch existed (project.json has no `motion_branch`, Use Images ON) are left alone: their stages read "skipped" and nothing waits for them."""
import json
from pathlib import Path

from . import llm_review, pipeline, store


def required(pdir: Path) -> bool:
    return store.motion_branch(pdir)


def names(aspect: str) -> tuple[str, str]:
    tag = "-9x16" if aspect == "9:16" else ""
    return f"motion-plan{tag}", f"motion-build{tag}"


def plan_file(pdir: Path, aspect: str) -> Path:
    return pdir / ("motion_plan_9x16.json" if aspect == "9:16" else "motion_plan.json")


def _built_for_mode(pdir: Path, aspect: str) -> bool:
    try:
        meta = json.loads(pipeline._comp(pdir, aspect).read_text(encoding="utf-8")).get("meta", {})
    except (OSError, ValueError):
        return False
    return meta.get("motion") == "rich" and bool(meta.get("motionOnly")) == (not store.uses_images(pdir))


def complete(pdir: Path, aspect: str) -> bool:
    plan, build = names(aspect)
    from . import motion_gen_report
    return (pipeline.is_fresh(pdir, plan) and pipeline.is_fresh(pdir, build) and
            _built_for_mode(pdir, aspect) and motion_gen_report.blockers(pdir, aspect) is None)


def blockers(pdir: Path, aspect: str) -> list[str]:
    """Why the timeline cannot be built / rendered yet because of the motion branch: Motion Planning and Motion Animation finished, then Stage 7
    (Motion & Timeline Validation) current and ready. Read now, nothing is started."""
    if not required(pdir):
        return []
    if complete(pdir, aspect):
        from . import motion_validation
        return motion_validation.blockers(pdir, aspect)
    plan, build = names(aspect)
    if not pipeline.is_fresh(pdir, plan):
        return ["Motion Planning is not finished"]
    return ["Motion Animation is not finished"]


def validation_stage(pdir: Path, aspect: str, step: str, running: bool, failed: str | None) -> dict:
    """The stage dict (id, label, status, detail, action) of Stage 10, Motion & Timeline Validation, from its report: ready / ready with warnings = completed, needs review = waiting_for_approval
    (a person decides), blocked / failed = failed, out of date or not run = queued. Read-only; a blocked verdict is shown as it is, never as green."""
    from . import motion_validation
    sid, label = "motion_validation", "Motion & Timeline Validation"
    open_it = {"kind": "open_motion_validation", "label": "Open"}
    if not required(pdir):
        return dict(id=sid, label=label, status="skipped", detail="made before the motion branch existed: nothing waits for it")
    if running and step.startswith("motion-validation"):
        return dict(id=sid, label=label, status="running", detail="checking the motion output before the timeline is built")
    if failed and not running and step.startswith("motion-validation"):
        return dict(id=sid, label=label, status="failed", detail=failed, action={"kind": "run_motion_validation", "label": "Retry"})
    rep = motion_validation.load(pdir, aspect)
    if rep is None:
        return dict(id=sid, label=label, status="queued", detail="ready: click Run" if complete(pdir, aspect) else "waits for Motion Generation")
    if rep["phase_status"] != "completed":
        return dict(id=sid, label=label, status="failed", detail=f"the validation did not finish: {rep.get('error') or 'run it again'}", action={"kind": "run_motion_validation", "label": "Retry"})
    s = rep["summary"]
    if rep["stale"]:
        return dict(id=sid, label=label, status="queued", detail="an input changed since the last validation: run it again", action=open_it)
    if rep["readiness"] in ("ready", "ready_with_warnings"):
        mv_ok, mv_reason, mv_rev = llm_review.is_stage_review_passed(pdir, "motion_validation", aspect)
        if mv_ok:
            warn_msg = f"ready with warnings: {s['warnings']} warning(s), {s['accepted_exceptions']} accepted exception(s)" if rep["readiness"] == "ready_with_warnings" else f"ready: {s['checks_passed']} of {s['checks_total']} checks passed"
            return dict(id=sid, label=label, status="completed", detail=f"{warn_msg} (LLM reviewed)", action=open_it)
        elif mv_reason in ("llm_review_blocked", "llm_review_has_blockers"):
            return dict(id=sid, label=label, status="failed", detail=f"LLM validation review blocked: {mv_rev['summary'] if mv_rev else mv_reason}", action={"kind": "run_motion_validation", "label": "Retry"})
        elif mv_reason == "llm_review_needs_review":
            return dict(id=sid, label=label, status="waiting_for_approval", detail=f"LLM review requires decision: {mv_rev['summary'] if mv_rev else ''}", action=open_it)
        else:
            why = {"llm_review_missing": "pending LLM review", "llm_review_stale_inputs": "the LLM review is out of date (an input changed): run the validation again",
                   "llm_review_stale_outputs": "the LLM review is out of date (the report changed): run the validation again"}.get(mv_reason, f"LLM review not passed ({mv_reason})")
            return dict(id=sid, label=label, status="queued", detail=f"deterministic checks passed: {why}", action=open_it)
    if rep["readiness"] == "needs_review":
        return dict(id=sid, label=label, status="waiting_for_approval", detail=f"{s['unresolved_review_items']} warning(s) need a decision", action=open_it)
    return dict(id=sid, label=label, status="failed", detail=f"blocked: {s['blockers']} blocker(s), {s['errors']} error(s) (the timeline is not built)", action=open_it)


def stages(pdir: Path, aspect: str, step: str, running: bool, failed: str | None, has_plan: bool) -> list[dict]:
    """The two stage dicts (id, label, status, detail) of the motion branch: Motion Planning, Motion Animation."""
    plan, build = names(aspect)
    if not required(pdir):
        why = "made before the motion branch existed: nothing waits for it"
        return [
            dict(id="motion_plan", label="Motion Planning", status="skipped", detail=why),
            dict(id="motion_gen", label="Motion Generation", status="skipped", detail=why),
        ]
    out = []

    # 1. Motion Planning
    if running and step == plan:
        out.append(dict(id="motion_plan", label="Motion Planning", status="running", detail="planning timing, text animations and transitions"))
    elif failed and not running and step == plan:
        out.append(dict(id="motion_plan", label="Motion Planning", status="failed", detail=failed))
    elif pipeline.is_fresh(pdir, plan):
        mp_ok, mp_reason, mp_rev = llm_review.is_stage_review_passed(pdir, "motion_plan", aspect)
        if mp_ok:
            out.append(dict(id="motion_plan", label="Motion Planning", status="completed", detail="motion plan and scene timings ready (LLM reviewed)"))
        elif mp_reason in ("llm_review_blocked", "llm_review_has_blockers"):
            out.append(dict(id="motion_plan", label="Motion Planning", status="failed", detail=f"LLM review blocked: {mp_rev['summary'] if mp_rev else mp_reason}", action={"kind": "run_motion", "label": "Retry"}))
        elif mp_reason == "llm_review_needs_review":
            out.append(dict(id="motion_plan", label="Motion Planning", status="waiting_for_approval", detail=f"LLM review requires decision: {mp_rev['summary'] if mp_rev else ''}"))
        else:
            out.append(dict(id="motion_plan", label="Motion Planning", status="queued", detail="motion plan computed: pending LLM review"))
    else:
        out.append(dict(id="motion_plan", label="Motion Planning", status="queued", detail="waits for the scene plan" if not has_plan else "ready: run Motion Planning"))

    # 2. Motion Animation
    if running and step == build:
        out.append(dict(id="motion_gen", label="Motion Generation", status="running", detail="generating executable scene-specific React/TSX animation code"))
    elif failed and not running and step == build:
        out.append(dict(id="motion_gen", label="Motion Generation", status="failed", detail=failed))
    elif complete(pdir, aspect):
        mg_ok, mg_reason, mg_rev = llm_review.is_stage_review_passed(pdir, "motion_gen", aspect)
        if mg_ok:
            out.append(dict(id="motion_gen", label="Motion Generation", status="completed", detail="scenes generated in custom code mode (compiled TSX, LLM reviewed)"))
        elif mg_reason in ("llm_review_blocked", "llm_review_has_blockers"):
            out.append(dict(id="motion_gen", label="Motion Generation", status="failed", detail=f"LLM animation review blocked: {mg_rev['summary'] if mg_rev else mg_reason}"))
        elif mg_reason == "llm_review_needs_review":
            out.append(dict(id="motion_gen", label="Motion Generation", status="waiting_for_approval", detail=f"LLM animation review requires decision: {mg_rev['summary'] if mg_rev else ''}"))
        else:
            out.append(dict(id="motion_gen", label="Motion Generation", status="queued", detail="scenes compiled: pending LLM review"))
    else:
        out.append(dict(id="motion_gen", label="Motion Generation", status="queued", detail="waits for Motion Planning"))

    return out


def data(pdir: Path, aspect: str) -> dict:
    """What the Motion Planning / Motion Animation pages show: the plan per scene and what the composition really contains."""
    from . import motion_animation
    pf = plan_file(pdir, aspect)
    plan = json.loads(pf.read_text(encoding="utf-8")) if pf.exists() else None
    comp_file = pipeline._comp(pdir, aspect)
    built = None
    if comp_file.exists():
        comp = json.loads(comp_file.read_text(encoding="utf-8"))
        built = {"fps": comp["meta"].get("fps"), "width": comp["meta"].get("width"), "height": comp["meta"].get("height"), "motion_only": bool(comp["meta"].get("motionOnly")),
                 "speed": comp["meta"].get("motionSpeed"), "scenes": len(comp["scenes"]),
                 "pictures": sum(l["type"] == "image" for s in comp["scenes"] for l in s["layers"]),
                 "texts": sum(l["type"] == "motion_text" for s in comp["scenes"] for l in s["layers"]),
                 "graphics": sum(len(l.get("items", [])) for s in comp["scenes"] for l in s["layers"] if l["type"] == "motion_scene"),
                 "custom": sum(l.get("type") in ("custom_scene", "custom_motion") for s in comp["scenes"] for l in s.get("layers", []))}
    plan_name, build_name = names(aspect)
    return {
        "aspect": aspect, "required": required(pdir), "plan": plan, "built": built, "planned": pipeline.is_fresh(pdir, plan_name),
        "generated": complete(pdir, aspect), "use_images": store.uses_images(pdir),
        "mode": "custom_code",
        "motion_animation": motion_animation.load_animation(pdir, aspect),
    }
