"""The stage list of the Pipeline page, derived from the files and the running job (read-only, nothing is stored here, so a refresh or a restart gives the
same answer). A percentage is only given where the pipeline really reports one (Whisper, the prompt writer's counts, the render); everything else
that is running has percent = None (the page shows an indeterminate bar). Stage states: queued, running, completed, waiting_for_images,
waiting_for_approval (an LLM review has not decided yet), failed, skipped."""
import json
import time
from pathlib import Path

from . import final_qc, jobs, llm_review, motion_branch, pipeline_issues, promptgen, review, scene_segmentation, store, render_video, timeline_approval, timeline_build, timeline_gate, visual_planning

TRANSCRIBE_STEPS = ("transcribe", "refine", "cuts")
BUILD_STEPS = ("motion-validate", "motion-validate-9x16", "timeline-build", "timeline-build-9x16")



def _visual_plan_errors(pdir: Path) -> list[str]:
    """The blocking errors recorded in visual_planning.json (an invalid visual plan must not go on silently). A project without one has none: its plan is derived on demand."""
    try:
        return [f"visual plan: {m}" for m in json.loads((pdir / "visual_planning.json").read_text(encoding="utf-8")).get("validation", {}).get("errors", [])]
    except (OSError, ValueError, AttributeError):
        return []

def _job(pdir: Path) -> dict:
    try:
        return json.loads((pdir / "job.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _stage(id_: str, label: str, status: str, detail: str = "", percent: float | None = None, action: dict | None = None, **extra) -> dict:
    return {"id": id_, "label": label, "status": status, "detail": detail, "percent": None if percent is None else round(percent, 1), "action": action, **extra}


def _assets_stage(pdir: Path, aspect: str, plan_ok: bool) -> dict:
    """Stage 5, Asset Collection (optional real photos/clips): derived from its manifest, the scenes it was made for and its stored LLM review."""
    from VIDEO_ENGINE.stages import asset_collection as ac
    label, run = "Asset Collection", {"kind": "start_run", "label": "Run"}
    man = ac.load_manifest(pdir)
    if not plan_ok:
        return _stage("assets", label, "queued", "waits for Visual Planning")
    if man.get("schema") != ac.SCHEMA_MAN or man.get("input_fingerprint") != ac.input_fingerprint(pdir, aspect):
        return _stage("assets", label, "queued", "runs before Motion Planning: real photos and clips, only for scenes that need them", action=run)
    if errs := [f["message"] for f in ac.check_assets(pdir, man) if f["severity"] == "error"]:
        return _stage("assets", label, "failed", "; ".join(errs[:2]), action=run)
    what = f"{len(man['assets'])} real asset(s) for {man['requirement_count']} requirement(s)" if man["requirement_count"] else "no scene needs real media"
    passed, reason, rev = llm_review.is_stage_review_passed(pdir, "assets", aspect)
    if passed:
        return _stage("assets", label, "completed", f"{what} (LLM reviewed)")
    if reason in ("llm_review_blocked", "llm_review_has_blockers"):
        return _stage("assets", label, "failed", f"LLM asset review blocked: {rev['summary'] if rev else reason}", action=run)
    return _stage("assets", label, "queued", f"{what}: pending LLM review", action=run)


def aspect_of(pdir: Path) -> str:
    return store.read_info(pdir).get("aspect") or "9:16"


def _video(pdir: Path, aspect: str) -> Path:
    return pdir / ("out_9x16.mp4" if aspect == "9:16" else "out.mp4")


def _enrich_stages_with_timings(pdir: Path, stages: list[dict], pid: str) -> list[dict]:
    aspect = aspect_of(pdir)
    from VIDEO_ENGINE.pipeline import stage_gate
    blocker = None                                                                  # the first stage (in pipeline order) whose own errors / warnings are unresolved
    prev = None
    for s in stages:
        if blocker is not None and s["status"] == "queued":                         # not started yet: it waits BLOCKED, never "ready" or running
            s["status"] = "blocked"
            s["detail"] = f"blocked by '{blocker[0]}': {blocker[1]}"
        elif s["status"] in ("queued", "waiting_for_approval") and prev is not None and prev["status"] not in ("completed", "skipped"):
            s["status"] = "waiting"                                                 # its prerequisite has not completed (running, failed, queued, waiting for an LLM review): not runnable yet
            s["waiting_for"] = f"{prev['label']} ({prev['status'].replace('_', ' ')})"
            s["detail"] = f"waits for '{prev['label']}' to complete ({prev['status'].replace('_', ' ')})"
        elif blocker is None and s["status"] in ("completed", "failed") and (open_issues := stage_gate.unresolved(pdir, s["id"], aspect)):
            blocker = (s["label"], stage_gate.describe(open_issues))
        prev = s
    for s in stages:                                                                # the card shows "LLM verified" only when the stage's stored LLM review passed
        try:
            s["llm_verified"] = bool(llm_review.is_stage_review_passed(pdir, s["id"], aspect)[0])
        except Exception:
            s["llm_verified"] = False

    pstate = None
    pstate_file = pdir / "pipeline_state.json"
    if pstate_file.exists():
        try:
            pstate = json.loads(pstate_file.read_text(encoding="utf-8"))
        except Exception:
            pstate = None

    timings_data = None
    timings_file = pdir / "timings.json"
    if timings_file.exists():
        try:
            timings_data = json.loads(timings_file.read_text(encoding="utf-8"))
        except Exception:
            timings_data = None

    active_run = None
    try:
        from VIDEO_ENGINE.pipeline import orchestrator
        active_run = orchestrator.current_run(pid)
    except Exception:
        active_run = None

    active_job = jobs.current(pid)

    for s in stages:
        sid = s.get("id")
        srec = pstate.get("stages", {}).get(sid, {}) if (pstate and isinstance(pstate.get("stages"), dict)) else {}

        started_at = srec.get("started_at")
        completed_at = srec.get("completed_at")
        duration_ms = None

        if s.get("status") == "running":
            if started_at is None and active_run and active_run.current_stage == sid:
                started_at = active_run.started_at
            if started_at is None and active_job:
                started_at = getattr(active_job, "started_at", None) or time.time()
            completed_at = None

        if started_at is not None and completed_at is not None:
            try:
                duration_ms = max(0, int(round((float(completed_at) - float(started_at)) * 1000)))
            except (ValueError, TypeError):
                duration_ms = None

        # Fallback to timings.json for legacy steps if duration_ms is missing
        if duration_ms is None and timings_data and isinstance(timings_data.get("steps"), dict):
            t_steps = timings_data["steps"]
            step_names = {
                "analyzer": ["transcribe", "cuts"],
                "segmentation": ["segment"],
                "motion_plan": ["motion-plan", "motion-plan-9x16"],
                "motion_gen": ["motion-build", "motion-build-9x16", "motion-gen"],
                "motion_validation": ["motion-validate", "motion-validate-9x16"],
                "timeline": ["timeline-build", "timeline-build-9x16"],
                "render": ["render-final", "render"],
            }.get(sid, [])
            total_sec = 0.0
            found_any = False
            for sn in step_names:
                if sn in t_steps:
                    entry = t_steps[sn]
                    sec = entry.get("total_seconds") if entry.get("total_seconds") is not None else entry.get("seconds")
                    if sec is not None:
                        total_sec += float(sec)
                        found_any = True
            if found_any and total_sec >= 0:
                duration_ms = int(round(total_sec * 1000))

        s["started_at"] = started_at
        s["completed_at"] = completed_at
        s["duration_ms"] = duration_ms

    return stages


def build(pid: str) -> dict:
    pdir = store.project_dir(pid)
    aspect = aspect_of(pdir)
    use_images = store.uses_images(pdir)
    job, running, disk = jobs.current(pid), jobs.is_running(pid), _job(pdir)
    step = (job.step if job and job.step else disk.get("step")) or ""
    failed_step = None if running else ((job.error if job else None) or disk.get("error"))
    has = lambda n: (pdir / n).exists()
    gen = promptgen.state(pdir) if has("scene_plan.json") or has("transcript.json") else {"state": "idle"}
    stages = []

    audio = next(iter(pdir.glob("audio.*")), None)
    if not audio:
        stages.append(_stage("audio", "Audio Input", "queued", "no audio uploaded"))
    else:
        passed, reason, rev = llm_review.is_stage_review_passed(pdir, "audio", aspect)
        if passed:
            stages.append(_stage("audio", "Audio Input", "completed", f"{audio.name} (LLM verified)"))
        elif reason in ("llm_review_blocked", "llm_review_has_blockers"):
            stages.append(_stage("audio", "Audio Input", "failed", f"LLM audio review blocked: {rev['summary'] if rev else reason}"))
        elif reason == "llm_review_needs_review":
            stages.append(_stage("audio", "Audio Input", "waiting_for_approval", f"LLM audio review requires decision: {rev['summary'] if rev else ''}"))
        else:
            stages.append(_stage("audio", "Audio Input", "queued", f"{audio.name} uploaded: pending LLM review"))
    done_tr = has("transcript.json") and has("cuts.json")
    if not audio:
        stages.append(_stage("analyzer", "Audio Analysis", "queued", "waits for audio upload"))
    elif running and step in TRANSCRIBE_STEPS:
        stages.append(_stage("analyzer", "Audio Analysis", "running", step, disk.get("percent") if step == "transcribe" else None))
    elif failed_step and step in TRANSCRIBE_STEPS:
        stages.append(_stage("analyzer", "Audio Analysis", "failed", failed_step, action={"kind": "retry_transcribe", "label": "Retry"}))
    elif done_tr:
        passed, reason, rev = llm_review.is_stage_review_passed(pdir, "analyzer", aspect)
        if passed:
            stages.append(_stage("analyzer", "Audio Analysis", "completed", "transcript and cut points ready (LLM reviewed)"))
        elif reason in ("llm_review_blocked", "llm_review_has_blockers"):
            stages.append(_stage("analyzer", "Audio Analysis", "failed", f"LLM transcript review blocked: {rev['summary'] if rev else reason}", action={"kind": "run_review_analyzer", "label": "Retry"}))
        elif reason == "llm_review_needs_review":
            stages.append(_stage("analyzer", "Audio Analysis", "waiting_for_approval", f"LLM review requires decision: {rev['summary'] if rev else ''}"))
        else:
            stages.append(_stage("analyzer", "Audio Analysis", "queued", "transcript generated: pending LLM review", action={"kind": "run_review_analyzer", "label": "Review"}))
    else:
        stages.append(_stage("analyzer", "Audio Analysis", "queued", f"{audio.name} ready for transcription", action={"kind": "retry_transcribe", "label": "Transcribe"}))

    seg_ok = scene_segmentation.load_fresh(pdir) is not None if has("scene_segmentation.json") else False
    if running and step == "segment":
        stages.append(_stage("segmentation", "Scene Segmentation", "running", "grouping the narration into scenes", disk.get("percent")))
    elif failed_step and step == "segment":
        stages.append(_stage("segmentation", "Scene Segmentation", "failed", failed_step, action={"kind": "run_segmentation", "label": "Retry"}))
    elif seg_ok:
        passed, reason, rev = llm_review.is_stage_review_passed(pdir, "segmentation", aspect)
        n = len(json.loads((pdir / "scene_segmentation.json").read_text(encoding="utf-8")).get("scenes", []))
        if passed:
            stages.append(_stage("segmentation", "Scene Segmentation", "completed", f"{n} scenes (LLM reviewed)"))
        elif reason in ("llm_review_blocked", "llm_review_has_blockers"):
            stages.append(_stage("segmentation", "Scene Segmentation", "failed", f"LLM segmentation review blocked: {rev['summary'] if rev else reason}", action={"kind": "run_segmentation", "label": "Retry"}))
        elif reason == "llm_review_needs_review":
            stages.append(_stage("segmentation", "Scene Segmentation", "waiting_for_approval", f"LLM review requires decision: {rev['summary'] if rev else ''}"))
        else:
            stages.append(_stage("segmentation", "Scene Segmentation", "queued", f"{n} scenes segmented: pending LLM review", action={"kind": "run_segmentation", "label": "Run Review"}))
    elif has("scene_segmentation.json"):
        stages.append(_stage("segmentation", "Scene Segmentation", "queued", "the transcript changed: run it again", action={"kind": "run_segmentation", "label": "Run"}))
    else:
        stages.append(_stage("segmentation", "Scene Segmentation", "queued", "ready: click Run" if has("transcript.json") else "waits for the analysis JSON"))

    plan_ok = has("scene_plan.json") and has("prompts_map.json")
    if gen.get("state") == "running" and gen.get("kind") == "plan":
        stages.append(_stage("planning", "Visual Planning", "running", f"stage {gen.get('current') or 1} of {gen.get('total') or '?'}",
                             100 * gen["done"] / gen["total"] if gen.get("total") else None))
    elif gen.get("state") == "failed" and gen.get("kind") == "plan":
        stages.append(_stage("planning", "Visual Planning", "failed", gen.get("error") or "planning failed", action={"kind": "retry_plan", "label": "Retry"}))
    elif plan_ok:
        errs = review.gates(pdir)["analysis"]["blockers"] + _visual_plan_errors(pdir) + visual_planning.plan_mismatch(pdir)
        if errs:
            stages.append(_stage("planning", "Visual Planning", "failed", "; ".join(errs[:2]), action={"kind": "retry_plan", "label": "Retry"}))
        else:
            passed, reason, rev = llm_review.is_stage_review_passed(pdir, "planning", aspect)
            if passed:
                stages.append(_stage("planning", "Visual Planning", "completed", "scene plan, visual plan and image prompts ready (LLM reviewed)"))
            elif reason in ("llm_review_blocked", "llm_review_has_blockers"):
                stages.append(_stage("planning", "Visual Planning", "failed", f"LLM visual plan review blocked: {rev['summary'] if rev else reason}", action={"kind": "retry_plan", "label": "Retry"}))
            elif reason == "llm_review_needs_review":
                stages.append(_stage("planning", "Visual Planning", "waiting_for_approval", f"LLM review requires decision: {rev['summary'] if rev else ''}"))
            else:
                stages.append(_stage("planning", "Visual Planning", "queued", "visual plan generated: pending LLM review", action={"kind": "retry_plan", "label": "Review"}))
    else:
        stages.append(_stage("planning", "Visual Planning", "queued", "waits for the analysis"))

    stages.append(_assets_stage(pdir, aspect, plan_ok))                                  # Stage 5, between Visual Planning and Motion Planning
    for s in motion_branch.stages(pdir, aspect, step, running, failed_step, plan_ok):
        stages.append(_stage(s["id"], s["label"], s["status"], s["detail"], disk.get("percent") if s["status"] == "running" and s["id"] in ("motion_plan", "motion_gen") else None,      # the step reports its own progress (5 -> 100)
                             action={"kind": "run_motion", "label": "Retry"} if s["status"] == "failed" else None))

    v = motion_branch.validation_stage(pdir, aspect, step, running, failed_step)      # Stage 7, between Motion Generation and the Timeline Build
    stages.append(_stage(v["id"], v["label"], v["status"], v["detail"], disk.get("percent") if v["status"] == "running" else None, action=v.get("action")))

    tl = timeline_gate.state(pdir, aspect)
    built = review.timeline_state(pdir)[aspect]["ready"] and timeline_gate.built_for_mode(pdir, aspect)      # the composition is built and its pre-render check passed
    tb = None
    if running and step in BUILD_STEPS:
        stages.append(_stage("timeline", "Timeline Build", "running", step))
    elif built and (tb := timeline_build.load(pdir, aspect)) is not None and tb["current"]:
        c = tb["report"]["counts"]
        tl_ok, tl_reason, tl_rev = llm_review.is_stage_review_passed(pdir, "timeline", aspect)
        if tl_ok:
            stages.append(_stage("timeline", "Timeline Build", "completed", f"timeline built and validated: {c['scenes']} scenes, {c['duration_frames']} frames (LLM reviewed)", action={"kind": "open_timeline_build", "label": "Open"}))
        elif tl_reason in ("llm_review_blocked", "llm_review_has_blockers"):
            stages.append(_stage("timeline", "Timeline Build", "failed", f"LLM timeline review blocked: {tl_rev['summary'] if tl_rev else tl_reason}", action={"kind": "open_timeline_build", "label": "Open"}))
        elif tl_reason == "llm_review_needs_review":
            stages.append(_stage("timeline", "Timeline Build", "waiting_for_approval", f"LLM timeline review requires decision: {tl_rev['summary'] if tl_rev else ''}", action={"kind": "open_timeline_build", "label": "Open"}))
        else:
            stages.append(_stage("timeline", "Timeline Build", "queued", "timeline built: pending LLM review", action={"kind": "open_timeline_build", "label": "Open"}))
    elif built and tb is not None and tb["status"] in ("blocked", "failed"):
        stages.append(_stage("timeline", "Timeline Build", "failed", "; ".join(timeline_build.blockers(pdir, aspect)), action={"kind": "retry_timeline", "label": "Retry"}))
    elif built:
        stages.append(_stage("timeline", "Timeline Build", "queued", "the composition is checked: press Build Timeline to build and validate the timeline" if tb is None else "an input changed since the timeline was built: build it again"))
    elif failed_step and step in BUILD_STEPS:
        stages.append(_stage("timeline", "Timeline Build", "failed", failed_step, action={"kind": "retry_timeline", "label": "Retry"}))
    else:
        stages.append(_stage("timeline", "Timeline Build", "queued", "starts by itself once Motion Animation and Validation are complete"))

    ap = timeline_approval.stage(pdir, aspect)                                       # Stage 12: the stored record against the current inputs (backend/timeline_approval.py)
    stages.append(_stage(ap["id"], ap["label"], ap["status"], ap["detail"], action=ap.get("action")))

    blockers = timeline_gate.render_blockers(pdir, aspect)
    final = _video(pdir, aspect)
    render_job = running and step.startswith("render")
    rv_ = render_video.stage_view(pdir, aspect, disk.get("percent") if render_job else None)      # Stages 13 and 14 (render_video.py, final_qc.py): the stored records against the current approval and the file's hash
    rv_status = rv_["status"]
    if rv_status == "completed":
        rn_ok, rn_reason, rn_rev = llm_review.is_stage_review_passed(pdir, "render", aspect)
        if not rn_ok:
            rv_status = "failed" if rn_reason in ("llm_review_blocked", "llm_review_has_blockers") else "queued"
            rv_["detail"] = f"LLM render review blocked: {rn_rev['summary'] if rn_rev else rn_reason}" if rv_status == "failed" else "video rendered: pending LLM review"
    stages.append(_stage(rv_["id"], rv_["label"], rv_status, rv_["detail"], rv_.get("percent"), action=rv_.get("action")))

    if running and step.startswith("final-qc"):
        qv = dict(id="qc", label="Final QC", status="running", detail="checking the rendered video", action={"kind": "open_final_qc", "label": "Open"})
    else:
        qv = final_qc.stage_view(pdir, aspect)
        if qv["status"] == "completed":
            qc_ok, qc_reason, qc_rev = llm_review.is_stage_review_passed(pdir, "qc", aspect)
            if not qc_ok:
                qv["status"] = "failed" if qc_reason in ("llm_review_blocked", "llm_review_has_blockers") else "queued"
                qv["detail"] = f"LLM QC review blocked: {qc_rev['summary'] if qc_rev else qc_reason}" if qv["status"] == "failed" else "QC checks passed: pending LLM review"
    stages.append(_stage(qv["id"], qv["label"], qv["status"], qv["detail"], disk.get("percent") if qv["status"] == "running" else None, action=qv.get("action")))

    gate_ = final_qc.gate(pdir, aspect)
    fn_ok, fn_reason, fn_rev = llm_review.is_stage_review_passed(pdir, "final", aspect)
    final_completed = not gate_ and qv["status"] == "completed" and fn_ok
    stages.append(_stage("final", "Final Video", "completed" if final_completed else "queued", f"{final.name}: Final QC passed and decided by the Final QC LLM review" if final_completed else "waits for Final QC and LLM verification on current video"))
    stages = _enrich_stages_with_timings(pdir, stages, pid)
    return {"project": pid, "aspect": aspect, "use_images": use_images, "running": running, "stages": stages,
            "issues": pipeline_issues.build(pdir, stages, failed_step),
            "reusable_motion_templates": store.reusable_motion_templates(pdir),
            "render": {"enabled": not blockers and not running, "blockers": blockers, "running": bool(render_job), "approved": tl["approved"], "version": tl["version"]}, "timeline": tl}
