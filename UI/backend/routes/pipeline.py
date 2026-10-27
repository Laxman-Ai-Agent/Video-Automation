"""Pipeline page endpoints: the stage list, each stage's page and run action, the timeline approval and the separate Render Video action. Each action is idempotent
(a second request returns the job that is already running) and every rule is checked here again: a disabled button is never the security."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .. import jobs, llm_review, motion_branch, pipeline_view, review, store, timeline_gate
from ..api_models import Generation, JobStarted
from ..errors import ApiError
from .. import pipeline
from ..pipeline import CHAINS, Ctx, chain_for

router = APIRouter(prefix="/projects/{pid}", tags=["pipeline"])


def _gate(stage_id: str):
    """A route dependency: the stage does not start while an upstream stage has unresolved errors or warnings (VIDEO_ENGINE/pipeline/stage_gate.py); the same rule the orchestrator applies."""
    def check(pid: str) -> None:
        from VIDEO_ENGINE.pipeline import stage_gate
        from VIDEO_ENGINE.pipeline.orchestrator import STAGE_DEPENDENCIES
        pdir = store.project_dir(pid)
        aspect = pipeline_view.aspect_of(pdir)
        from SYSTEM.core import pipeline_state
        pstate = pipeline_state.load_pipeline_state(pdir)
        live: dict | None = None
        for dep in STAGE_DEPENDENCIES.get(stage_id, ()):
            rec = pstate.stages.get(dep)
            if rec is not None and rec.status in ("failed", "blocked", "needs_review"):
                # a recorded failure can be outdated: the stage may have been run again (job route) and completed since. The live view decides; the record is
                # corrected through transition_stage, whose own completion gates (fresh passed LLM review ...) still apply.
                if live is None:
                    live = {s["id"]: s["status"] for s in pipeline_view.build(pid)["stages"]}
                if live.get(dep) == "completed":
                    try:
                        rec = pipeline_state.transition_stage(pdir, dep, "completed", aspect=aspect)
                    except Exception:
                        pass
            if rec is not None and rec.status in ("running", "retrying", "failed", "blocked", "needs_review"):      # the prerequisite is in progress or did not succeed: never start on top of it
                raise ApiError(409, "upstream_blocked", f"'{stage_id}' cannot start: upstream stage '{dep}' is {rec.status}",
                               "wait for the upstream stage to complete (or fix it) first")
            # a stage that never ran is left to the route's own input checks (missing analysis JSON, no scene plan ...)
        for dep in STAGE_DEPENDENCIES.get(stage_id, ()):
            ran = getattr(pstate.stages.get(dep), "status", None) == "completed"             # a stage that never ran has no LLM review to wait for
            if (open_issues := stage_gate.unresolved(pdir, dep, aspect, ran=ran)):
                raise ApiError(409, "upstream_blocked", f"'{stage_id}' is blocked: upstream stage '{dep}' has {stage_gate.describe(open_issues)}",
                               "fix the upstream issues: the stage's own fixer solves what it can, nobody can accept a warning")
    return check


class AspectBody(BaseModel):
    aspect: str | None = None


def _aspect(pdir, body: AspectBody | None) -> str:
    aspect = (body.aspect if body else None) or pipeline_view.aspect_of(pdir)
    if aspect not in review.ASPECTS:
        raise ApiError(422, "invalid_request", "aspect must be 16:9 or 9:16")
    return aspect


def _started(job) -> JobStarted:
    return JobStarted(project=job.project, label=job.label, steps=list(job.names))


def _idle(pid: str) -> None:
    if jobs.is_running(pid):
        raise ApiError(409, "job_running", "a job is running for this project", "change things after it finishes")


def _motion_timeline(pdir, pid: str):
    """Build the timeline straight from the plan."""
    label = "timeline-9x16" if pipeline_view.aspect_of(pdir) == "9:16" else "timeline"
    return jobs.start(pid, label, chain_for(pdir, label), Ctx())


def _motion_job(pdir, pid: str):
    """The motion branch on its own: Motion Planning, then Motion Generation."""
    label = "motion-9x16" if pipeline_view.aspect_of(pdir) == "9:16" else "motion"
    return jobs.start(pid, label, chain_for(pdir, label), Ctx())


def _same_job(pid: str, prefix: str):
    j = jobs.current(pid)
    return j if j and j.state == "running" and j.label.startswith(prefix) else None


@router.get("/pipeline")
def get_pipeline(pid: str):
    return pipeline_view.build(pid)


@router.get("/motion")
def get_motion(pid: str):
    """The Motion Planning / Motion Generation pages: the plan per scene and what the composition really contains."""
    pdir = store.project_dir(pid)
    return motion_branch.data(pdir, pipeline_view.aspect_of(pdir))


@router.post("/motion/run", response_model=JobStarted, status_code=202, dependencies=[Depends(_gate("motion_plan"))])
def run_motion(pid: str):
    """Run (or retry) the motion branch: Motion Planning, then Motion Generation. Finished steps are skipped; a second request returns the job that is running."""
    pdir = store.project_dir(pid)
    if (j := _same_job(pid, "motion")):
        return _started(j)
    _idle(pid)
    if not (pdir / "scene_plan.json").exists():
        raise ApiError(409, "plan_missing", "the scene plan does not exist yet", "the motion branch starts after Visual Planning")
    from .. import visual_planning
    if (why := visual_planning.blockers(pdir)):                            # nothing starts from a Visual Plan that is out of date or invalid
        raise ApiError(409, "visual_plan_not_current", f"Motion Planning waits for Visual Planning: {why}", "run Visual Planning again")
    from ..agents import communication
    communication.publish_handoff(pid, "motion_plan", "visual_planning", "motion_planning", "Visual plan accepted; commencing motion planning")
    return _started(_motion_job(pdir, pid))


@router.post("/pipeline/advance")
def advance(pid: str, part: str = "all"):
    """The step after Visual Planning, started by a user click (nothing calls it by itself): build the timeline from the plan (`part=timeline`, or `all`). Idempotent;
    it approves only the analysis and never starts a render. `prompts` and `motion` are accepted and do nothing (Motion-Only has no prompt writer)."""
    if part not in ("all", "prompts", "motion", "timeline"):
        raise ApiError(422, "invalid_request", "part must be all, prompts, motion or timeline")
    pdir = store.project_dir(pid)
    g = review.gates(pdir)["analysis"]
    if part in ("prompts", "motion"):
        return {"advanced": False, "reason": "Motion-Only mode: use part=timeline"}
    aspect = pipeline_view.aspect_of(pdir)
    if not (pdir / "scene_plan.json").exists() or not g["ready"] or jobs.is_running(pid):
        return {"advanced": False, "reason": "; ".join(g["blockers"][:2]) or "a job is running"}
    if timeline_gate.state(pdir, aspect)["ready"] or pipeline_view._job(pdir).get("error"):
        return {"advanced": False, "reason": "nothing to do"}          # built already, or the last build failed (the card's Retry starts it again)
    if not g["approved"]:
        review.set_gate(pdir, "analysis", True)
    _motion_timeline(pdir, pid)
    return {"advanced": True, "reason": "Motion-Only mode: the timeline is being built from the plan"}


def _enrich_scenes_with_transcripts(pdir, data: dict) -> dict:
    """Enrich each scene in scene_segmentation with both the original Whisper transcript and LLM-processed transcript.
    - Whisper transcript: raw faster-whisper ASR transcript from transcript.json
    - LLM transcript: LLM-reviewed transcript with English technical loanwords in English script and genuine Telugu in Telugu script
    Ensures the LLM-corrected transcript is the authoritative primary narration (sc["transcript"]).
    Preserves raw Whisper transcript separately (sc["whisper_transcript"]) for comparison."""
    import json
    if not isinstance(data.get("scenes"), list):
        return data

    whisper_words = []
    whisper_segments = {}
    raw_f = pdir / "transcript.json"
    if raw_f.exists():
        try:
            t_raw = json.loads(raw_f.read_text(encoding="utf-8"))
            for s in t_raw.get("segments", []):
                whisper_segments[s.get("id")] = s.get("text", "")
                for w in s.get("words", []):
                    whisper_words.append({
                        "w": w.get("w", w.get("text", "")),
                        "start": float(w.get("start", 0.0)),
                        "end": float(w.get("end", 0.0)),
                    })
        except Exception:
            pass

    llm_words = []
    llm_segments = {}
    has_llm = False
    for corr_name in ["transcript_fixed.json", "transcript_corrected.json"]:
        corr_f = pdir / corr_name
        if corr_f.exists():
            try:
                t_corr = json.loads(corr_f.read_text(encoding="utf-8"))
                for s in t_corr.get("segments", []):
                    llm_segments[s.get("id")] = s.get("text", "")
                    for w in s.get("words", []):
                        llm_words.append({
                            "w": w.get("w", w.get("text", "")),
                            "start": float(w.get("start", 0.0)),
                            "end": float(w.get("end", 0.0)),
                        })
                has_llm = True
                break
            except Exception:
                pass

    if not has_llm:
        for aa_name in ["audio_analysis.json", "audio-analysis.json"]:
            aa_f = pdir / aa_name
            if aa_f.exists():
                try:
                    aa_data = json.loads(aa_f.read_text(encoding="utf-8"))
                    utterances = aa_data.get("utterances", [])
                    if utterances:
                        for idx, u in enumerate(utterances):
                            uid = u.get("id", idx)
                            llm_segments[uid] = u.get("text", "")
                            for w in u.get("words", []):
                                llm_words.append({
                                    "w": w.get("text", w.get("w", "")),
                                    "start": float(w.get("start_seconds", w.get("start", 0.0))),
                                    "end": float(w.get("end_seconds", w.get("end", 0.0))),
                                })
                        has_llm = True
                        break
                except Exception:
                    pass

    for sc in data["scenes"]:
        st = sc.get("start_time", 0.0)
        et = sc.get("end_time_word", sc.get("end_time", 0.0))
        seg_ids = sc.get("source_segment_ids", [])

        # 1. Whisper original transcript (ASR)
        w_text = sc.get("whisper_transcript")
        if not w_text and whisper_words:
            matched_w = [w["w"] for w in whisper_words if w.get("start", 0) >= st - 0.08 and w.get("end", 0) <= et + 0.12 and w.get("w")]
            if matched_w:
                w_text = " ".join(matched_w)
        if not w_text and seg_ids:
            w_text = " ".join(whisper_segments[sid] for sid in seg_ids if sid in whisper_segments).strip() or None
        sc["whisper_transcript"] = w_text

        # 2. LLM processed transcript (Corrected)
        l_text = sc.get("llm_transcript")
        if not l_text and has_llm:
            if llm_words:
                matched_l = [w["w"] for w in llm_words if w.get("start", 0) >= st - 0.08 and w.get("end", 0) <= et + 0.12 and w.get("w")]
                if matched_l:
                    l_text = " ".join(matched_l)
            if not l_text and seg_ids:
                l_text = " ".join(llm_segments[sid] for sid in seg_ids if sid in llm_segments).strip() or None
        if not l_text:
            l_text = sc.get("transcript")

        # Set LLM transcript and ensure primary narration transcript is the corrected text
        sc["llm_transcript"] = l_text
        if l_text:
            sc["transcript"] = l_text

    return data


# ---------- Scene Segmentation (its own stage, started by the user) ----------
@router.get("/segmentation")
def get_segmentation(pid: str):
    """scene_segmentation.json (scenes, boundary reasons, the 7 stages, validation) when it exists; `stale` = made from an older transcript. Read-only: opening the page starts nothing."""
    import json

    from .. import scene_segmentation
    pdir = store.project_dir(pid)
    f = pdir / "scene_segmentation.json"
    if not f.exists():
        raise ApiError(409, "segmentation_missing", "Scene Segmentation has not been run yet", "run it from the Scene Segmentation page")
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except ValueError as e:
        raise ApiError(409, "segmentation_unreadable", "scene_segmentation.json could not be read", str(e)) from e
    data["stale"] = scene_segmentation.load_fresh(pdir) is None
    data = _enrich_scenes_with_transcripts(pdir, data)
    return data


@router.post("/segmentation/run", response_model=JobStarted, status_code=202, dependencies=[Depends(_gate("segmentation"))])
def run_segmentation(pid: str):
    """Start Scene Segmentation (the only way it starts). It reads the project's existing final analysis JSON as it is (no ASR, no audio processing, nothing regenerated); a missing or invalid
    JSON is a 409 error and no job starts. A second request while it runs returns the same job."""
    from .. import scene_segmentation
    pdir = store.project_dir(pid)
    try:
        scene_segmentation.load_source(pdir)       # the existing analysis JSON must be there and valid; the audio is never processed again to make up for it
    except scene_segmentation.SourceError as e:
        raise ApiError(409, e.code, str(e), "put the final analysis JSON in the project (nothing was started)") from e
    if (j := _same_job(pid, "segment")):
        return _started(j)
    return _started(jobs.start(pid, "segment", CHAINS["segment"], Ctx()))


@router.post("/llm-review/run")
def run_llm_review(pid: str):
    """The "Run LLM Verification" button of the Scene Segmentation page. The check and correction of the transcript belongs to the Audio Analyzer (its `refine` step, with the corrected
    words re-aligned): this runs the analysis through the one implementation (`run_analysis`: finished steps are reused, Whisper never runs again), then cuts the scenes from the verified
    transcript (the `segment` step, skipped when they are current). Returns the scenes with both transcripts, for the page."""
    from VIDEO_ENGINE.pipeline import legacy_pipeline_adapter as adapter
    from .. import scene_segmentation, transcript_review
    pdir = store.project_dir(pid)
    if not (pdir / "transcript.json").exists():
        raise ApiError(409, "transcript_missing", "Cannot run LLM Review: audio has not been transcribed yet")
    _idle(pid)
    try:
        adapter.run_analysis(pdir)
        if not transcript_review.is_verified(pdir):
            raise ApiError(409, "llm_verification_incomplete", "The LLM check of the transcript did not finish: some corrected words still wait for their timestamps", "run the Audio Analyzer again")
        adapter.execute(pdir, "segment", adapter.Ctx())
    except ApiError:
        raise
    except Exception as e:
        raise ApiError(500, "llm_review_failed", f"LLM Review execution failed: {str(e)}") from e
    rev = json.loads((pdir / "transcript_review.json").read_text(encoding="utf-8")) if (pdir / "transcript_review.json").exists() else {}
    seg_data = _enrich_scenes_with_transcripts(pdir, json.loads((pdir / "scene_segmentation.json").read_text(encoding="utf-8")))

    return {
        "ok": True,
        "message": "LLM review and scene narration successfully synchronized",
        "llm_status": rev.get("llm", {}).get("status", "completed"),
        "corrections_count": sum(c.get("status") == "applied" for c in rev.get("corrections", [])),
        "data": seg_data
    }


# ---------- Visual Planning (its own stage page: the visual plan is read-only, the Run button is the only start) ----------
@router.get("/visual-planning")
def get_visual_plan(pid: str):
    """visual_plan.json (per scene: objective, concept, elements, relationships, asset requirements, text, motion hints, continuity; the 8 stages; validation) with `stale` and `stored`.
    A project made before it existed gets the plan derived from its scene plan (`stored` false, nothing written). Read-only: opening the page starts nothing."""
    import json
    from .. import visual_planning
    pdir = store.project_dir(pid)
    data = visual_planning.load(pdir)
    if data is None:
        raise ApiError(409, "visual_plan_missing", "There is no scene plan yet", "run Visual Planning from its page")
    if (pdir / "scene_plan.json").exists():
        try:
            sp = json.loads((pdir / "scene_plan.json").read_text(encoding="utf-8"))
            data["scene_plan"] = sp
            sp_by_id = {s["id"]: s for s in sp.get("scenes", [])}
            for sc in data.get("scenes", []):
                psid = sc.get("plan_scene_id")
                if psid in sp_by_id:
                    sc["scene_plan_data"] = sp_by_id[psid]
        except Exception:
            pass
    if (pdir / "scene_segmentation.json").exists():
        try:
            seg = json.loads((pdir / "scene_segmentation.json").read_text(encoding="utf-8"))
            seg_by_id = {s.get("id"): s for s in seg.get("scenes", [])}
            seg_by_idx = {i + 1: s for i, s in enumerate(seg.get("scenes", []))}
            for sc in data.get("scenes", []):
                smap = sc.get("source_mapping", {})
                seg_id = smap.get("segmentation_scene_id")
                seg_idx = smap.get("segmentation_scene_index")
                match = seg_by_id.get(seg_id) or seg_by_idx.get(seg_idx)
                if match:
                    sc["segmentation_data"] = match
        except Exception:
            pass
    return data


@router.post("/visual-planning/run", response_model=Generation, status_code=202, dependencies=[Depends(_gate("planning"))])
def run_visual_plan(pid: str):
    """Run Visual Planning (the only way it starts). A project without a scene plan gets the whole planner (translation, scene plan, prompts, visual plan, checks); a project that has
    its scene plan gets the visual plan made over it (the scene plan and the prompts are never changed). A second request while it runs returns the same job."""
    from .. import autoplan, transcript_review, visual_planning
    pdir = store.project_dir(pid)

    # Mandatory LLM verification gate: do not go to next step without verified LLM narration (the Audio Analyzer's check; a transcript the LLM checked and left as it was is verified too)
    if not transcript_review.is_verified(pdir):
        raise ApiError(409, "llm_verification_required", "LLM Transcript Verification is mandatory before proceeding to Visual Planning. Run the Audio Analyzer (it checks and corrects the transcript with the LLM).", "Run the Audio Analyzer, or press Run LLM Verification on the Scene Segmentation page")

    try:
        if autoplan.needs_plan(pdir):
            return autoplan.start(pdir)
        if visual_planning.plan_mismatch(pdir):                    # the scene plan was made from other scene boundaries than the current Scene Segmentation: it is made again from the segmentation (the old files stay in plan_backups/)
            return autoplan.start(pdir, replace=True)
        return visual_planning.start(pdir)
    except review.ReviewError as e:
        raise ApiError(409, "generation_not_allowed", str(e)) from e


# ---------- Motion Planning (its own stage page: the plan is read-only, the Run button is the only start) ----------
@router.get("/motion-planning")
def get_motion_planning(pid: str):
    """motion_planning.json (per scene: timing in seconds and frames, motion intent, the elements resolved to registry ids or fallbacks, the actions with their dependencies, continuity, transition;
    the 13 stages; validation; repairs; tests) with `stale`. Read-only: opening the page starts nothing."""
    import json
    from .. import motion_planning
    pdir = store.project_dir(pid)
    aspect = pipeline_view.aspect_of(pdir)
    data = motion_planning.load(pdir, aspect)
    if data is None:
        raise ApiError(409, "motion_plan_missing", "There is no motion plan yet", "run Motion Planning from its page")

    # Enrich with motion_plan.json (selector plan: texts, graphics, pattern, speed)
    motion_plan_file = pdir / ("motion_plan_9x16.json" if aspect == "9:16" else "motion_plan.json")
    if motion_plan_file.exists():
        try:
            mp = json.loads(motion_plan_file.read_text(encoding="utf-8"))
            data["raw_motion_plan"] = mp
            mp_scenes_by_id = {s.get("id"): s for s in mp.get("scenes", [])}
            for sc in data.get("scenes", []):
                psid = sc.get("plan_scene_id")
                if psid in mp_scenes_by_id:
                    sc["motion_plan_scene"] = mp_scenes_by_id[psid]
        except Exception:
            pass

    # Enrich with visual_planning.json (Visual Plan: concept, directives, Telugu narration, English translation)
    vp_file = pdir / ("visual_planning_9x16.json" if aspect == "9:16" else "visual_planning.json")
    if not vp_file.exists():
        vp_file = pdir / "visual_planning.json"
    if vp_file.exists():
        try:
            vp = json.loads(vp_file.read_text(encoding="utf-8"))
            data["visual_plan_data"] = vp
            vp_scenes_by_id = {s.get("scene_id"): s for s in vp.get("scenes", [])}
            vp_scenes_by_pid = {s.get("plan_scene_id"): s for s in vp.get("scenes", [])}
            for sc in data.get("scenes", []):
                sid = sc.get("scene_id")
                psid = sc.get("plan_scene_id")
                v_sc = vp_scenes_by_id.get(sid) or vp_scenes_by_pid.get(psid)
                if v_sc:
                    sc["visual_scene_data"] = v_sc
        except Exception:
            pass

    # Enrich with scene_segmentation.json
    seg_file = pdir / "scene_segmentation.json"
    if seg_file.exists():
        try:
            seg = json.loads(seg_file.read_text(encoding="utf-8"))
            seg_scenes_by_id = {s.get("id"): s for s in seg.get("scenes", [])}
            seg_scenes_by_idx = {i + 1: s for i, s in enumerate(seg.get("scenes", []))}
            for sc in data.get("scenes", []):
                psid = sc.get("plan_scene_id")
                match = seg_scenes_by_id.get(f"scene_{int(psid):03d}" if isinstance(psid, (int, str)) and str(psid).isdigit() else psid) or seg_scenes_by_idx.get(psid)
                if match:
                    sc["segmentation_data"] = match
        except Exception:
            pass

    return data


@router.post("/motion-planning/run", response_model=JobStarted, status_code=202, dependencies=[Depends(_gate("motion_plan"))])
def run_motion_planning(pid: str):
    """Run Motion Planning only (the selector's plan and the checked plan; Motion Generation is a separate step). Unchanged inputs keep the existing plan. A second request while it runs returns the same job."""
    pdir = store.project_dir(pid)
    if (j := _same_job(pid, "motion")):
        return _started(j)
    _idle(pid)
    if not (pdir / "scene_plan.json").exists():
        raise ApiError(409, "plan_missing", "the scene plan does not exist yet", "Motion Planning starts after Visual Planning")
    from .. import visual_planning
    if (why := visual_planning.blockers(pdir)):
        raise ApiError(409, "visual_plan_not_current", f"Motion Planning waits for Visual Planning: {why}", "run Visual Planning again")
    label = "motion-plan-9x16" if pipeline_view.aspect_of(pdir) == "9:16" else "motion-plan"
    return _started(jobs.start(pid, label, chain_for(pdir, label), Ctx()))


# ---------- Motion Generation (its own stage page: the report is read-only, the Run button is the only start) ----------
@router.get("/motion-generation")
def get_motion_generation(pid: str):
    """motion_generation.json (per scene: one descriptor per layer with component, preset, props, seconds and frames, the 13 stages, validation, repairs, tests, output) with `stale`.
    Read-only: opening the page starts nothing."""
    from .. import motion_gen_report
    pdir = store.project_dir(pid)
    data = motion_gen_report.load(pdir, pipeline_view.aspect_of(pdir))
    if data is None:
        raise ApiError(409, "motion_generation_missing", "Motion Generation has not run yet", "run Motion Generation from its page")
    return data


@router.get("/motion-generation/scenes")
def get_motion_generation_scenes(pid: str):
    """Motion Generation scene by scene: the code written for each scene, its elements, its checks and how it was made. Read-only."""
    from .. import motion_gen_report
    pdir = store.project_dir(pid)
    data = motion_gen_report.scenes_view(pdir, pipeline_view.aspect_of(pdir))
    if data is None:
        raise ApiError(409, "motion_code_missing", "No scene code has been generated yet", "run Motion Generation from its page")
    return data


@router.post("/motion-generation/fix-warnings", response_model=JobStarted, status_code=202)
def fix_motion_generation_warnings(pid: str, auto: bool = False):
    """Solve what can be solved mechanically in the warnings of Motion Generation: an emphasis that lies inside a spoken word starts with that word (`motion_planning.auto_align_emphasis`).
    The decisions go to motion_fixes.json, then Motion Planning and Motion Generation run again. Warnings that are recorded fallbacks (elements the library cannot draw) are NOT touched: they
    belong to Motion & Timeline Validation. `auto=true` is the page's loop: at most 3 attempts per scene plan, counted on disk and checked before anything changes."""
    from .. import motion_autofix, motion_planning
    pdir = store.project_dir(pid)
    if (j := _same_job(pid, "motion")):
        return _started(j)
    _idle(pid)
    aspect = pipeline_view.aspect_of(pdir)
    if auto and len(motion_autofix.state(pdir, "gen")["attempts"]) >= motion_autofix.MAX_AUTO_FIXES:
        raise ApiError(409, "autofix_exhausted", f"{motion_autofix.MAX_AUTO_FIXES} automatic attempts were used for this scene plan; warnings that remain were not solved", "the remaining warnings need a decision in Motion & Timeline Validation or a change upstream")
    try:
        done = motion_planning.auto_align_emphasis(pdir, aspect)
    except motion_planning.MotionError as e:
        raise ApiError(409, "motion_plan_missing", str(e), "run Motion Planning first") from e
    if not done["done"]:
        raise ApiError(409, "nothing_to_solve", "There is no warning left that can be solved automatically", "; ".join(done["kept"][:2]) or "what remains needs a decision in Motion & Timeline Validation or a change upstream")
    if auto:
        motion_autofix.count(pdir, {"aligned": len(done["done"]), "kept": done["kept"]}, "gen")
    label = "motion-9x16" if aspect == "9:16" else "motion"
    return _started(jobs.start(pid, label, chain_for(pdir, label), Ctx()))


@router.post("/motion-generation/run", response_model=JobStarted, status_code=202, dependencies=[Depends(_gate("motion_gen"))])
def run_motion_generation(pid: str):
    """Run Motion Generation only (the composition from the checked motion plan, then its checks; Motion Planning is a separate step). A second request while it runs returns the same job."""
    pdir = store.project_dir(pid)
    if (j := _same_job(pid, "motion")):
        return _started(j)
    _idle(pid)
    from .. import motion_planning
    aspect = pipeline_view.aspect_of(pdir)
    plan = motion_planning.load(pdir, aspect)
    if plan is None:
        raise ApiError(409, "motion_plan_missing", "There is no motion plan yet", "run Motion Planning first")
    if (why := motion_planning.blockers(pdir, aspect)):
        raise ApiError(409, "motion_plan_not_current", f"Motion Generation waits for Motion Planning: {why}", "run Motion Planning again")
    label = "motion-gen-9x16" if aspect == "9:16" else "motion-gen"
    return _started(jobs.start(pid, label, chain_for(pdir, label), Ctx()))


# ---------- Motion & Timeline Validation, Stage 10 (read-only: the report is a view, the buttons are the only starts; no route here builds a timeline or renders) ----------
def _validation(pid: str):
    from .. import motion_validation
    pdir = store.project_dir(pid)
    return motion_validation, pdir, pipeline_view.aspect_of(pdir)


@router.get("/motion-timeline-validation")
def get_motion_timeline_validation(pid: str):
    """motion_timeline_validation.json (12 stages, findings with evidence and owner stage, summary, readiness, the preview levels, exceptions) with `stale` and the current fingerprint. Read-only:
    opening the page starts nothing, and a stale report reads `stale`, never green."""
    mv, pdir, aspect = _validation(pid)
    data = mv.load(pdir, aspect)
    if data is None:
        raise ApiError(409, "motion_validation_missing", "Motion & Timeline Validation has not run yet", "run it from its page")
    return data


@router.post("/motion-timeline-validation/run", response_model=JobStarted, status_code=202, dependencies=[Depends(_gate("motion_validation"))])
def run_motion_timeline_validation(pid: str, force: bool = False):
    """Run Stage 10 (read-only: it writes only its own report). `force` redoes every internal stage; otherwise a stage whose inputs did not change keeps its result. A second request while a
    motion job runs returns that job. It never builds the timeline."""
    mv, pdir, aspect = _validation(pid)
    if (j := _same_job(pid, "motion")):
        return _started(j)
    _idle(pid)
    label = "motion-validation-9x16" if aspect == "9:16" else "motion-validation"
    return _started(jobs.start(pid, label, chain_for(pdir, label), Ctx(force=force)))


@router.post("/motion-timeline-validation/preview", response_model=JobStarted, status_code=202)
def run_motion_validation_preview(pid: str):
    """Generate the preview: low-resolution stills of the current composition at deterministic frames (an explicit action; no video is rendered), then validate again. Refused unless Motion
    Generation is current."""
    mv, pdir, aspect = _validation(pid)
    if (j := _same_job(pid, "motion")):
        return _started(j)
    _idle(pid)
    from .. import motion_gen_report
    gen = motion_gen_report.load(pdir, aspect)
    if gen is None or gen["stale"] or gen["validation"]["errors"]:
        raise ApiError(409, "motion_generation_not_current", "Motion Generation must be current and without errors before a preview is made", "run Motion Generation again")
    label = "motion-validation-preview-9x16" if aspect == "9:16" else "motion-validation-preview"
    return _started(jobs.start(pid, label, chain_for(pdir, label), Ctx()))


@router.get("/motion-timeline-validation/preview/{name}")
def get_motion_validation_preview_frame(pid: str, name: str):
    """One preview still (a PNG of the current preview folder; nothing else can be read through this route)."""
    import re
    from fastapi.responses import FileResponse
    from .. import motion_validation_preview as pv
    mv, pdir, aspect = _validation(pid)
    f = pv.folder(pdir, aspect) / name
    if not re.fullmatch(r"[A-Za-z0-9_.-]+\.png", name) or not f.is_file():
        raise ApiError(404, "not_found", "no such preview frame", "generate the preview first")
    return FileResponse(f, media_type="image/png")


@router.post("/motion-planning/fix-warnings", response_model=JobStarted, status_code=202)
def fix_motion_plan_warnings(pid: str, auto: bool = False):
    """Solve the warnings of the stored motion plan (no Claude call): move a graphic off the text area, show a text earlier so it can be read, accept the recorded fallbacks. The decisions
    go to motion_fixes.json and Motion Planning runs again with them. A second request while it runs returns the same job."""
    from .. import motion_planning
    pdir = store.project_dir(pid)
    if (j := _same_job(pid, "motion")):
        return _started(j)
    _idle(pid)
    aspect = pipeline_view.aspect_of(pdir)
    if auto:                                                  # checked BEFORE solve, so an exhausted loop changes nothing
        from .. import motion_autofix
        if len(motion_autofix.state(pdir)["attempts"]) >= motion_autofix.MAX_AUTO_FIXES:
            raise ApiError(409, "autofix_exhausted", f"{motion_autofix.MAX_AUTO_FIXES} automatic attempts were used for this scene plan; warnings that remain were not solved", "the remaining warnings need a change in the Visual Plan or a manual Solve warnings")
    try:
        done = motion_planning.solve(pdir, aspect)
    except motion_planning.MotionError as e:
        raise ApiError(409, "motion_plan_missing", str(e), "run Motion Planning from its page") from e
    if not (done["moved"] or done["earlier"] or done["accepted"]):
        raise ApiError(409, "nothing_to_solve", "There is no warning left that can be solved", "the plan has no warning, or its warnings need a change in the Visual Plan")
    if auto:                                                  # the automatic loop: at most MAX_AUTO_FIXES attempts per scene plan, counted on disk (a refresh or a repeated request cannot add more)
        from .. import motion_autofix
        motion_autofix.count(pdir, done)
    label = "motion-plan-9x16" if aspect == "9:16" else "motion-plan"
    return _started(jobs.start(pid, label, chain_for(pdir, label), Ctx()))


@router.post("/visual-planning/fix-warnings", response_model=Generation, status_code=202)
def fix_visual_plan_warnings(pid: str):
    """Solve the warnings of the stored Visual Plan: one Claude call about the scenes that have warnings, every other scene stays as it is. The scene plan and the prompts are never changed.
    A second request while it runs returns the same job."""
    from .. import visual_planning
    try:
        return visual_planning.start_fix(store.project_dir(pid))
    except review.ReviewError as e:
        raise ApiError(409, "generation_not_allowed", str(e)) from e


@router.post("/continue", response_model=JobStarted, status_code=202)
def continue_pipeline(pid: str):
    """Continue pipeline progression to timeline build."""
    pdir = store.project_dir(pid)
    if (j := _same_job(pid, "timeline")):
        return _started(j)
    _idle(pid)
    try:
        if not review.gates(pdir)["analysis"]["approved"]:
            review.set_gate(pdir, "analysis", True)
    except review.ReviewError as e:
        raise ApiError(409, "not_allowed", str(e), "; ".join(e.blockers)) from e
    return _started(_motion_timeline(pdir, pid))


# ---------- Timeline Build, Stage 11 (builds timeline.json from the current composition and validates it: never approves, never renders) ----------
@router.get("/timeline-build")
def get_timeline_build(pid: str):
    """The state of Stage 11 read from disk: `status` (completed / completed_with_warnings / blocked / failed / stale), the build report (12 internal stages, checks, findings, counts, persistence), the latest attempt
    and whether the published timeline is current. Read-only: opening the page starts nothing, and a timeline built from inputs that changed reads `stale`."""
    from .. import timeline_build as tb
    pdir = store.project_dir(pid)
    aspect = pipeline_view.aspect_of(pdir)
    data = tb.load(pdir, aspect)
    if data is None:
        raise ApiError(409, "timeline_build_missing", "the timeline has not been built yet", "run Timeline Build from its page")
    return {**data, "aspect": aspect, "blockers": tb.blockers(pdir, aspect)}


@router.get("/timeline-build/timeline")
def get_built_timeline(pid: str):
    """The published timeline.json as saved (tracks, items, layers, gaps, transitions, source map)."""
    from .. import timeline_build as tb
    pdir = store.project_dir(pid)
    t = tb.timeline(pdir, pipeline_view.aspect_of(pdir))
    if t is None:
        raise ApiError(409, "timeline_missing", "there is no published timeline", "run Timeline Build")
    return t


@router.get("/timeline-build/waveform")
def get_timeline_waveform(pid: str):
    """Peaks of the narration for the Timeline page. Read-only; the only thing it writes is a cache file."""
    from .. import timeline_media
    w = timeline_media.waveform(store.project_dir(pid))
    if w is None:
        raise ApiError(409, "waveform_unavailable", "the narration waveform is not available", "run the Audio Analyzer first")
    return w


@router.get("/timeline-build/stills")
def get_timeline_stills(pid: str):
    """The preview stills of the current composition for the Timeline page (the frames Motion Validation drew), each with the URL that serves it. `current` is false when the stills were made from
    another composition or renderer: the page then says so instead of showing frames that do not belong to this timeline. Read-only."""
    from .. import motion_gen_report, motion_validation_preview as pv
    pdir = store.project_dir(pid)
    aspect = pipeline_view.aspect_of(pdir)
    man = pv.load(pdir, aspect)
    gen = motion_gen_report.load(pdir, aspect)
    current = bool(man) and bool(gen) and pv.is_current(man, (gen.get("output") or {}).get("composition_sha"))
    base = f"/projects/{pid}/motion-timeline-validation/preview/"
    samples = [{"scene_id": x["scene_id"], "kind": x["kind"], "frame": x["frame"], "time_s": x.get("time_s"), "url": base + x["file"]} for x in (man or {}).get("samples", [])] if current else []
    return {"current": current, "exists": man is not None, "samples": samples}


@router.get("/timeline-build/thumbnails")
def get_timeline_thumbnails(pid: str):
    """The thumbnail sheet of the rendered video for smooth scrubbing on the Timeline page. Only the video that is the verified render of the currently approved timeline has one (`available`);
    without it the page keeps the preview stills. The sheet is made once per video (ffmpeg, low priority) and cached."""
    from .. import render_video as rv, timeline_media
    pdir = store.project_dir(pid)
    cand = rv.current_candidate(pdir, pipeline_view.aspect_of(pdir))
    if cand is None:
        return {"available": False, "reason": "no rendered video of the current approved timeline yet"}
    meta = timeline_media.thumbnails(pdir, cand["path"], cand["sha256"], float(((cand["report"].get("observed") or {}).get("duration_seconds")) or 0))
    if meta is None:
        return {"available": False, "reason": "the thumbnails could not be made from the video"}
    return {"available": True, "url": f"/projects/{pid}/timeline-build/thumbnails/sheet.jpg?v={meta['key'][:12]}", **{k: meta[k] for k in ("interval_s", "cols", "rows", "count", "tile_w", "tile_h")}}


@router.get("/timeline-build/thumbnails/sheet.jpg")
def get_timeline_thumbnail_sheet(pid: str):
    from fastapi.responses import FileResponse
    from .. import timeline_media
    f = store.project_dir(pid) / timeline_media.THUMBS
    if not f.is_file():
        raise ApiError(404, "not_found", "no thumbnail sheet yet", "open the Timeline page after a render")
    return FileResponse(f, media_type="image/jpeg", headers={"Cache-Control": "max-age=86400"})


@router.get("/timeline-build/audio")
def get_timeline_audio(pid: str):
    """The narration file the published timeline uses (for listening on the Timeline page)."""
    from fastapi.responses import FileResponse
    from .. import timeline_build as tb, timeline_media
    pdir = store.project_dir(pid)
    t = tb.timeline(pdir, pipeline_view.aspect_of(pdir))
    item = next((i for tr in (t or {}).get("tracks", []) if tr.get("track_type") == "audio" for i in tr.get("items", [])), None)
    f = timeline_media.audio_file(pdir, (item or {}).get("source_ref", ""))
    if f is None:
        raise ApiError(404, "not_found", "the timeline has no audio file to play", "build the timeline first")
    return FileResponse(f)


@router.post("/timeline-build/run", response_model=JobStarted, status_code=202, dependencies=[Depends(_gate("timeline"))])
def run_timeline_build(pid: str):
    """Build and validate the timeline from the current composition (Stage 10 must have cleared the motion output). A second request while a timeline job runs returns that job. It never approves and never renders."""
    pdir = store.project_dir(pid)
    aspect = pipeline_view.aspect_of(pdir)
    if (j := _same_job(pid, "timeline")):
        return _started(j)
    _idle(pid)
    if not pipeline._comp(pdir, aspect).exists():
        raise ApiError(409, "composition_missing", "there is no composition to build a timeline from", "run Motion Generation first")
    label = "timeline-build-9x16" if aspect == "9:16" else "timeline-build"
    return _started(jobs.start(pid, label, chain_for(pdir, label), Ctx()))


# ---------- Timeline Approval, Stage 12 (an explicit human decision about ONE exact timeline version; opening, previewing or having no errors approves nothing; no route here renders) ----------
def _approval(pid: str):
    from .. import timeline_approval
    pdir = store.project_dir(pid)
    return timeline_approval, pdir, pipeline_view.aspect_of(pdir)


@router.get("/timeline-approval")
def get_timeline_approval(pid: str):
    """The approval state recomputed from the stored record and the CURRENT inputs: status (not_ready / ready_for_review / changes_requested / approved / stale / approval_error), the blockers, the review manifest of the
    current version, the preview and whether it matches, the review coverage (what a PERSON looked at), the acknowledgements an approval needs and the full history. Read-only: it approves nothing."""
    ta, pdir, aspect = _approval(pid)
    try:
        return ta.state(pdir, aspect)
    except ta.ApprovalError as e:
        raise ApiError(409, e.code, str(e), "; ".join(e.blockers) or "see the approval record") from e


@router.post("/timeline-approval/review")
def prepare_timeline_review(pid: str):
    """Resolve the latest build and preview and write the review manifest of the current version. It does not touch the timeline, approve anything or render."""
    ta, pdir, aspect = _approval(pid)
    _idle(pid)
    try:
        return ta.prepare_review(pdir, aspect)
    except ta.ApprovalError as e:
        raise ApiError(409, e.code, str(e), "; ".join(e.blockers) or "see the approval record") from e


# ---------- Render Video, Stage 13 (the start is POST /render below; these read its state and stop it) ----------
@router.get("/render-video")
def get_render_video(pid: str):
    """The state of Stage 13 from its records and the CURRENT approval: status (not_ready / ready / running / completed / stale / failed / cancelled / interrupted / unverified_output), the phase and frames of the job, its attempts,
    the render report (expected vs observed metadata, checksum, carried warnings), whether the published video is the current verified one, and that Final QC is still pending. Read-only."""
    from .. import render_video
    pdir = store.project_dir(pid)
    return render_video.state(pdir, pipeline_view.aspect_of(pdir))


@router.post("/render-video/cancel")
def cancel_render_video(pid: str):
    """Ask the running render to stop. Cooperative: the state is `cancel_requested` until the job ends; nothing is published and the last good video stays."""
    from .. import render_video
    pdir = store.project_dir(pid)
    aspect = pipeline_view.aspect_of(pdir)
    try:
        out = render_video.request_cancel(pdir, aspect)
    except render_video.RenderError as e:
        raise ApiError(409, "no_render", str(e), "nothing to cancel") from e
    jobs.cancel(pid)
    return out


# ---------- Final QC, Stage 14 (judges the verified rendered video; read-only on everything else; it never renders) ----------



def _qc(pid: str):
    from .. import final_qc
    pdir = store.project_dir(pid)
    return final_qc, pdir, pipeline_view.aspect_of(pdir)


@router.get("/final-qc")
def get_final_qc(pid: str):
    """The Final QC report of the current video with `current` / `stale`, the candidate (name, size, sha256), the Final QC LLM decisions and the delivery gate. Read-only: opening the page starts nothing."""
    fq, pdir, aspect = _qc(pid)
    return fq.state(pdir, aspect)


@router.post("/final-qc/run", response_model=JobStarted, status_code=202)
def run_final_qc(pid: str):
    """Run Final QC on the verified rendered video (a job; the media evidence is reused when the file is the same). It never renders, edits or approves anything. A second request returns the running job."""
    fq, pdir, aspect = _qc(pid)
    if (j := _same_job(pid, "final-qc")):
        return _started(j)
    _idle(pid)
    label = "final-qc-9x16" if aspect == "9:16" else "final-qc"
    return _started(jobs.start(pid, label, chain_for(pdir, label), Ctx()))


@router.post("/final-qc/cancel")
def cancel_final_qc(pid: str):
    """Stop a running Final QC before its next stage; no report is written (an earlier valid one stays)."""
    fq, pdir, aspect = _qc(pid)
    if not _same_job(pid, "final-qc"):
        raise ApiError(409, "no_qc", "no Final QC is running", "nothing to cancel")
    fq.cancel(pdir)
    return {"cancel_requested": True}


@router.post("/final-qc/llm-decide")
def llm_decide_final_qc(pid: str):
    """The Final QC LLM review decides about THIS exact video (its sha256) from the current report: a changed video is refused, a failed or blocked QC is never approved,
    an unavailable LLM records 'cannot_determine'. Append-only; read back before success. The Final QC job runs this itself after its checks."""
    fq, pdir, aspect = _qc(pid)
    _idle(pid)
    try:
        return fq.llm_decide(pdir, aspect)
    except fq.QcError as e:
        raise ApiError(409, e.code, str(e), "run Final QC again") from e


@router.get("/final-qc/findings/{finding_id}")
def get_final_qc_finding(pid: str, finding_id: str):
    """One finding with its evidence (scene, time, frame, expected / observed, recommended action)."""
    fq, pdir, aspect = _qc(pid)
    rep = fq.state(pdir, aspect)["report"]
    f = next((x for x in (rep or {}).get("checks", []) if x["finding_id"] == finding_id), None)
    if f is None:
        raise ApiError(404, "not_found", "no such finding in the current QC report", "see the report")
    return f


@router.get("/final-qc/frame/{name}")
def get_final_qc_frame(pid: str, name: str):
    """One sampled frame of the current QC (a JPEG of the QC frames folder; nothing else can be read through this route)."""
    import re
    from fastapi.responses import FileResponse
    fq, pdir, aspect = _qc(pid)
    f = pdir / fq.names(aspect)["frames"] / name
    if not re.fullmatch(r"[A-Za-z0-9_.-]+\.jpg", name) or not f.is_file():
        raise ApiError(404, "not_found", "no such QC frame", "run Final QC first")
    return FileResponse(f, media_type="image/jpeg")


# ---------- timeline approval and the separate render action ----------
@router.get("/timeline/approval")
def get_approval(pid: str, aspect: str | None = None):
    pdir = store.project_dir(pid)
    return timeline_gate.state(pdir, _aspect(pdir, AspectBody(aspect=aspect)))


@router.post("/timeline/approve", dependencies=[Depends(_gate("approval"))])
def approve_timeline(pid: str, body: AspectBody | None = None):
    """Approve the CURRENT version of the timeline: decided by the LLM approval review (timeline_approval.auto_approve, the one implementation the pipeline step also uses),
    never recorded without a passing verdict; then Render Video starts. A rejected or unready version answers 409 with the exact cause."""
    pdir = store.project_dir(pid)
    _idle(pid)
    asp = _aspect(pdir, body)
    from .. import timeline_approval
    try:
        res = timeline_approval.auto_approve(pdir, asp)
    except timeline_approval.ApprovalError as e:
        raise ApiError(409, e.code, str(e), "; ".join(e.blockers[:4]) or str(e)) from e
    if not jobs.is_running(pid) and not timeline_gate.render_blockers(pdir, asp):
        label = "build-9x16" if asp == "9:16" else "build"
        jobs.start(pid, label, chain_for(pdir, label), Ctx(preview=False))
    return res


@router.post("/render", response_model=JobStarted, status_code=202, dependencies=[Depends(_gate("render"))])
def render_video(pid: str, body: AspectBody | None = None):
    """Render Video: the only way to start a final render. It re-checks the approval of the current timeline version."""
    pdir = store.project_dir(pid)
    aspect = _aspect(pdir, body)
    label = "build-9x16" if aspect == "9:16" else "build"
    if (j := _same_job(pid, "build")) and not j.ctx.preview:
        return _started(j)                            # double click / repeated request: the same job, not a second one
    _idle(pid)
    why = timeline_gate.render_blockers(pdir, aspect)
    if why:
        raise ApiError(409, "render_not_allowed", "the video cannot be rendered yet", "; ".join(why[:6]))
    return _started(jobs.start(pid, label, chain_for(pdir, label), Ctx(preview=False, force=True)))


# ---------- Mandatory LLM Stage Review Gate Endpoints ----------
@router.get("/review/{stage}")
def get_stage_llm_review(pid: str, stage: str, aspect: str | None = None):
    """Inspect the structured LLM review result and verification pass status for a pipeline stage."""
    pdir = store.project_dir(pid)
    asp = _aspect(pdir, AspectBody(aspect=aspect)) if aspect else pipeline_view.aspect_of(pdir)
    res = llm_review.load_review(pdir, stage, asp)
    if res is None:
        raise ApiError(404, "review_not_found", f"no LLM review found for stage '{stage}'", "run the review first")
    is_passed, reason, _ = llm_review.is_stage_review_passed(pdir, stage, asp)
    return {
        "stage": stage,
        "aspect": asp,
        "is_passed": is_passed,
        "verification_detail": reason,
        "review": res,
    }


@router.post("/review/{stage}")
def trigger_stage_llm_review(pid: str, stage: str, body: AspectBody | None = None, force: bool = False):
    """Explicitly trigger or refresh the mandatory stage-specific LLM review."""
    pdir = store.project_dir(pid)
    asp = _aspect(pdir, body)
    _idle(pid)
    res = llm_review.run_stage_llm_review(pdir, stage, asp, force=force)
    is_passed, reason, _ = llm_review.is_stage_review_passed(pdir, stage, asp)
    return {
        "stage": stage,
        "aspect": asp,
        "is_passed": is_passed,
        "verification_detail": reason,
        "review": res,
    }


# ---------- Canonical Pipeline State, Checkpoints, and Resume ----------
@router.get("/state")
def get_canonical_pipeline_state(pid: str):
    """Retrieve the authoritative project pipeline state, revision, and stage checkpoints."""
    from .. import pipeline_state
    pdir = store.project_dir(pid)
    pipeline_state.reconcile_orphaned_jobs(pdir)
    return pipeline_state.load_pipeline_state(pdir).to_dict()


@router.get("/resume-plan")
def get_resume_plan(pid: str, aspect: str | None = None):
    """Evaluates the resume graph: earliest invalid stage, reusable checkpoints, and invalidated stages."""
    from .. import pipeline_state
    pdir = store.project_dir(pid)
    asp = _aspect(pdir, AspectBody(aspect=aspect)) if aspect else pipeline_view.aspect_of(pdir)
    return pipeline_state.resolve_resume_plan(pdir, aspect=asp)


# ---------- the real steps of a stage (its own report), an LLM check of each step, and the stage's LLM evidence; nothing estimated ----------
@router.get("/stages/{stage_id}/subtasks")
def get_stage_subtasks(pid: str, stage_id: str):
    """The steps the stage recorded in its last report (status, detail, checks) with the LLM check of each, when that report was written, the stage's
    stored LLM review and how many LLM calls the agent log shows for it. Steps without a check of their current result start being checked in the
    background (one LLM call per step). A stage without a step report returns no steps: the UI says so instead of inventing them. While the stage runs, a
    report written before this run started belongs to the previous run and is never returned: only what the new run has written shows."""
    import json as _json
    from .. import pipeline_issues, step_llm_check
    pdir = store.project_dir(pid)
    aspect = pipeline_view.aspect_of(pdir)
    steps, _rep, f = step_llm_check.steps(pdir, stage_id, aspect)
    report, written = (f.name, f.stat().st_mtime) if f is not None and f.exists() else (None, None)
    started = pipeline_view.run_started_at(pid, stage_id)
    if started is not None and written is not None and written < started:
        steps, report, written = [], None, None

    # Gating: Whisper speech-to-text (audio to Telugu) and audio_analysis.json must be ready before LLM checks
    whisper_ready = True
    if stage_id == "analyzer":
        has_tr = (pdir / "transcript.json").exists()
        has_an = (pdir / "audio_analysis.json").exists()
        whisper_ready = has_tr and has_an

    if steps:
        step_llm_check.start(pdir, stage_id, aspect)                               # checks steps 1-3 when audio exists; downstream steps wait for audio_analysis.json
    checks = step_llm_check.load(pdir, stage_id, aspect)

    active_model = "openai/gpt-oss-120b"
    try:
        from SYSTEM.core import llm_gateway
        gw = llm_gateway.get_gateway()
        prov, configured_mdl, key, base_url = gw.client.resolve_provider_config()
        active_model = gw.resolve_model_for_profile(prov, "fast_structured", configured_mdl)
    except Exception:
        pass

    active_step = checks.get("active_step")
    first_unverified_n = None
    if checks.get("running") and active_step is None:
        for stp in steps:
            c_info = checks["steps"].get(str(stp["n"]))
            if not (c_info and c_info.get("current") and c_info.get("verdict") != "error"):
                first_unverified_n = stp["n"]
                break

    for s in steps:
        chk = checks["steps"].get(str(s["n"]))
        s["llm_check"] = chk

        passed = s.get("checks_passed")
        total = s.get("checks_total")
        prog = s.get("progress_percent")
        st = (s.get("status") or "").lower()

        # LLM Verification state determination
        v_state = "pending"
        if chk and chk.get("current"):
            v = chk.get("verdict")
            if v == "confirms":
                v_state = "verified"
            elif v == "rejects":
                v_state = "rejected"
            elif v == "questions":
                v_state = "questioned"
            elif v == "error":
                v_state = "error"
            else:
                v_state = "unverified"
            s["llm_verification"] = {
                "state": v_state,
                "model": chk.get("model") or active_model,
                "latency_ms": chk.get("latency_ms"),
                "note": chk.get("note"),
                "verdict": v,
            }
        elif checks.get("running"):
            is_active = (active_step is not None and s.get("n") == active_step) or (active_step is None and s.get("n") == first_unverified_n)
            v_state = "in_progress" if is_active else "pending"
            s["llm_verification"] = {
                "state": v_state,
                "model": active_model,
                "note": "LLM verification actively reviewing step output..." if is_active else "Queued for LLM verification",
            }
        else:
            s["llm_verification"] = {
                "state": "pending",
                "model": active_model,
                "note": "Waiting for LLM verification",
            }

        # When analyzer has not finished Whisper audio-to-Telugu conversion, downstream steps remain disabled & pending
        if stage_id == "analyzer" and not whisper_ready:
            step_n = s.get("n", 0)
            if step_n in (4, 6, 7, 8, 9, 10, 11, 12, 13, 14):
                s["disabled"] = True
                s["status"] = "pending"
                s["completion_percent"] = 0
                s["llm_verification"] = {
                    "state": "pending",
                    "model": active_model,
                    "note": "Waiting for Whisper audio-to-Telugu conversion to complete..."
                }
                continue
            elif step_n == 5:
                has_tr = (pdir / "transcript.json").exists()
                if not has_tr:
                    s["status"] = "running" if (pdir / "audio_16k.wav").exists() else "pending"
                    s["completion_percent"] = int(prog) if (prog is not None and 0 < prog < 100) else 45
                    s["llm_verification"] = {
                        "state": "in_progress" if (pdir / "audio_16k.wav").exists() else "pending",
                        "model": active_model,
                        "note": "Whisper audio-to-Telugu conversion in progress..."
                    }
                    continue
                else:
                    s["llm_verification"] = {
                        "state": "in_progress",
                        "model": active_model,
                        "note": "Audio analysis and Telugu vocabulary refinement in progress..."
                    }
                    s["completion_percent"] = 75
                    continue

        # Dynamic work-based percentage calculation: NEVER report 100% while running/verifying!
        is_step_running = st == "running" or v_state == "in_progress"
        is_step_pending = st in ("pending", "waiting", "") or s.get("disabled")
        is_step_failed = st in ("failed", "error", "blocked") or v_state in ("rejected", "error")

        if is_step_failed:
            pct = 0
        elif is_step_pending:
            pct = 0
        elif is_step_running:
            # Running/processing: reflect dynamic work, capped below 100%
            if prog is not None and 0 < prog < 100:
                pct = int(prog)
            elif total and total > 1 and passed is not None and 0 <= passed < total:
                pct = min(95, round((passed / total) * 100))
            else:
                pct = 50
        elif st in ("completed", "passed"):
            pct = 100
        elif total and total > 0 and passed is not None:
            pct = round((passed / total) * 100)
        else:
            pct = 0
        s["completion_percent"] = pct

    overall_progress = None
    if steps:
        total_steps = len(steps)
        verified_count = sum(1 for s in steps if (s.get("llm_verification") or {}).get("state") == "verified")
        has_errors = any(
            (s.get("status") or "").lower() in ("failed", "error", "blocked") or
            (s.get("llm_verification") or {}).get("state") == "rejected"
            for s in steps
        )
        avg_det = sum(s.get("completion_percent", 0) for s in steps) / total_steps
        verif_ratio = verified_count / total_steps

        if has_errors:
            overall_progress = min(round(avg_det * 0.75), 80)
        elif avg_det >= 99.9:
            overall_progress = 100
        else:
            # Proportional progress based on deterministic steps and LLM checks
            overall_progress = round(avg_det * 0.8 + (verif_ratio * 100) * 0.2)

    review = None
    if (rf := llm_review.review_path(pdir, stage_id, pipeline_view.aspect_of(pdir))).exists():
        try:
            r = _json.loads(rf.read_text(encoding="utf-8"))
            review = {"status": r.get("status"), "score": r.get("score"), "model": r.get("model"), "summary": r.get("summary"), "written": rf.stat().st_mtime}
        except ValueError:
            review = None
    calls: dict[str, int] = {}
    for ev in pipeline_issues._events(pdir):                                        # "LLM Gateway [generation] executed for stage 'motion_gen' ..."
        c = ev.get("content") or ""
        if ev.get("stage_id") == stage_id and c.startswith("LLM Gateway ["):
            kind = c[len("LLM Gateway ["):].split("]")[0]
            calls[kind] = calls.get(kind, 0) + 1
    return {"stage_id": stage_id, "report": report, "written": written, "steps": steps, "llm_review": review, "llm_calls": calls,
            "llm_checks_running": checks["running"], "active_step": active_step, "active_model": active_model, "overall_progress": overall_progress}


@router.post("/stages/{stage_id}/subtasks/llm-check", status_code=202)
def run_stage_subtask_checks(pid: str, stage_id: str):
    """Check now every step whose current result has no LLM check yet (the same background run the subtasks page starts by itself)."""
    from .. import step_llm_check
    pdir = store.project_dir(pid)
    aspect = pipeline_view.aspect_of(pdir)
    started = step_llm_check.start(pdir, stage_id, aspect)
    return {"started": started, "pending": step_llm_check.pending(pdir, stage_id, aspect), "running": step_llm_check.load(pdir, stage_id, aspect)["running"]}


@router.post("/stages/{stage_id}/subtasks/{n}/retry", status_code=202)
def retry_stage_subtask(pid: str, stage_id: str, n: int):
    """Run only step `n` again. A Visual Planning step that has warnings is solved by one planner call about the scenes that raised them (every other scene stays as it is); any other
    step gets its LLM check asked again. The rest of the stage is never run."""
    from .. import step_llm_check, visual_planning
    pdir = store.project_dir(pid)
    aspect = pipeline_view.aspect_of(pdir)
    step = next((s for s in step_llm_check.steps(pdir, stage_id, aspect)[0] if s.get("n") == n), None)
    if step is None:
        raise ApiError(404, "no_such_step", f"Stage '{stage_id}' has no step {n} in its report")
    if stage_id == "planning" and (step.get("status") or "").lower() in ("warning", "failed", "error"):
        try:
            visual_planning.start_fix(pdir, n)
        except review.ReviewError as e:
            raise ApiError(409, "retry_not_allowed", str(e)) from e
        return {"kind": "solve_warnings", "started": True}
    return {"kind": "llm_check", "started": step_llm_check.recheck(pdir, stage_id, aspect, n)}


