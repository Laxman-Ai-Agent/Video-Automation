import json
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from SYSTEM.core import media_kinds

from .. import jobs, pipeline, store
from ..api_models import Deleted, ProjectInfo, Status
from ..api_status import build_status
from ..audio_utils import duration as audio_duration
from ..errors import ApiError
from .uploads import check_ext, receive

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectInfo, status_code=201)
async def create_project(
    name: str = Form(...),
    audio: UploadFile = File(...),
    aspect: str | None = Form(None),
    reusable_motion_templates: bool = Form(False),
    reusable_templates: bool | None = Form(None),
    ai_images: bool = Form(False),
    motion_kit: bool = Form(False),
):
    if not name.strip():
        raise ApiError(422, "invalid_name", "the project needs a name", "send a non-empty name")
    try:
        media = media_kinds.normalise({"ai_images": ai_images})
    except ValueError as e:
        raise ApiError(422, "invalid_media", str(e), "send ai_images as true or false") from e
    if aspect is not None and aspect not in store.ASPECTS:
        raise ApiError(422, "invalid_aspect", f"aspect must be one of {', '.join(store.ASPECTS)}", "send 9:16 or 16:9, or leave it out")
    ext = Path(audio.filename or "").suffix.lower()
    check_ext(f"audio{ext}", store.AUDIO_EXTS, "audio")
    pdir = store.create(name, aspect, reusable_motion_templates=False, media=media, motion_kit=motion_kit)
    dest = pdir / f"audio{ext}"
    try:
        await receive(audio, dest, store.MAX_AUDIO_BYTES)
        info = store.read_info(pdir)
        try:
            seconds = round(audio_duration(dest), 1)
        except Exception:                     # the length is only shown in the UI; the analysis reports an unreadable file itself
            seconds = None
        info["audio"] = {"file": dest.name, "original_name": Path(audio.filename or dest.name).name[:200], "size_bytes": dest.stat().st_size, "format": ext[1:].upper(), "duration": seconds}
        store.write_info(pdir, info)
    except BaseException:
        store.delete(pdir)                    # the half-made project this request just created
        raise
    return store.read_info(pdir)


@router.get("", response_model=list[ProjectInfo])
def list_projects():
    return store.list_projects()


@router.get("/{pid}", response_model=ProjectInfo)
def get_project(pid: str):
    return store.read_info(store.project_dir(pid))


class Rename(BaseModel):
    name: str | None = None
    reusable_motion_templates: bool | None = None
    reusable_templates: bool | None = None


@router.patch("/{pid}", response_model=ProjectInfo)
def rename_project(pid: str, body: Rename):
    """Change the display name and/or reusable templates configuration."""
    pdir = store.project_dir(pid)
    with store._info_lock(pdir):                      # read-modify-write under the project's own lock: a running job's write cannot be lost
        info = store.read_info(pdir)
        if body.name is not None:
            name = " ".join(body.name.split())
            if not name or len(name) > 120:
                raise ApiError(422, "invalid_name", "the name must have 1 to 120 characters", "send a non-empty name")
            info["name"] = name
        reusable = body.reusable_motion_templates if body.reusable_templates is None else body.reusable_templates
        if reusable is not None:
            info["reusable_motion_templates"] = bool(reusable)
        store.write_info(pdir, info)
    return store.read_info(pdir)


@router.delete("/{pid}", response_model=Deleted)
def delete_project(pid: str, confirm: bool = False):
    pdir = store.project_dir(pid)
    if not confirm:
        raise ApiError(400, "confirmation_required", "deleting a project removes all of its files",
                       f"repeat the request as DELETE /projects/{pid}?confirm=true")
    if jobs.is_running(pid):
        raise ApiError(409, "job_running", "a job is running for this project", "cancel it first")
    store.delete(pdir)
    return Deleted(deleted=pid)


@router.get("/{pid}/status", response_model=Status)
def status(pid: str):
    return build_status(pid)


@router.post("/{pid}/transcript/correct")
def correct_transcript(pid: str):
    """Make the transcript the LLM-corrected one (what the `refine` step does, for a project that has none yet): Claude checks every word (answers are cached: asking again costs nothing),
    corrected words are re-aligned against the audio (or marked ESTIMATED), and `transcript_corrected.json` becomes the transcript every later step reads. `transcript.json` (the original) is
    never edited. If Claude is not available the original stays the transcript and the reason comes back."""
    from .. import audio_analysis, jobs, transcript_review
    pdir = store.project_dir(pid)
    if not (pdir / "transcript.json").exists():
        raise ApiError(409, "transcript_missing", "the audio has not been analyzed yet", "start the analysis first")
    if jobs.is_running(pid):
        raise ApiError(409, "job_running", "a job is running for this project", "try again when it has finished")
    review = transcript_review.refine(pdir)
    (pdir / "analysis_autofix.json").unlink(missing_ok=True)
    try:
        audio_analysis.write(pdir)          # the analysis file follows the transcript that is now the final one
    except Exception:
        pass
    return {"transcript": _final_transcript(pdir), "llm": review["llm"], "corrections": review["corrections"], "unresolved": review["unresolved"]}


@router.post("/{pid}/analysis/autofix")
def analysis_autofix(pid: str, additional: bool = False):
    """Clear the fixable Audio Analyzer warnings and re-check (backend/analysis_autofix.py). Idempotent: with no warnings it changes nothing. Refused while a job runs."""
    from .. import analysis_autofix, jobs
    pdir = store.project_dir(pid)
    if not (pdir / "audio_analysis.json").exists():
        raise ApiError(409, "analysis_missing", "the audio has not been analyzed yet", "wait for the Audio Analyzer to finish")
    if jobs.is_running(pid):
        raise ApiError(409, "job_running", "a job is running for this project", "try again when it has finished")
    try:
        return analysis_autofix.run(pdir, additional=additional)
    except analysis_autofix.Busy:
        raise ApiError(409, "autofix_running", "an automatic fix is already running for this project", "wait for it to finish")


@router.get("/{pid}/audio-analysis")
@router.get("/{pid}/analysis")
def analysis(pid: str):
    """audio_analysis.json or audio-analysis.json: audio facts, the 14 analyzer stages, pauses and the validation of the analysis.
    Read-only artifact lookup: reads existing saved file directly; never reruns ASR, transcription, or overwrites existing artifacts."""
    from .. import audio_analysis
    pdir = store.project_dir(pid)

    # 1. Resolve existing saved artifact without rewriting
    target_file = None
    for fname in ("audio-analysis.json", "audio_analysis.json"):
        candidate = pdir / fname
        if candidate.exists():
            target_file = candidate
            break

    if target_file is None:
        if not (pdir / "transcript.json").exists():
            raise ApiError(
                404,
                "analysis_missing",
                f"Audio analysis artifact (audio-analysis.json) is unavailable for project '{pid}'",
                "The audio has not been analyzed yet. Start the Audio Analysis workflow when requested."
            )
        try:
            data = audio_analysis.write(pdir)
            target_file = pdir / "audio_analysis.json"
        except Exception as e:
            raise ApiError(409, "analysis_unavailable", "the analysis could not be summarized", str(e)[:200]) from e
    else:
        try:
            data = json.loads(target_file.read_text(encoding="utf-8"))
        except ValueError as e:
            raise ApiError(409, "analysis_unreadable", f"{target_file.name} could not be parsed: {e}", str(e)) from e

    data["_artifact_path"] = f"projects/{pid}/{target_file.name}"
    data["_filename"] = target_file.name

    # Enrich utterances with separate raw Whisper text for comparison in UI
    raw_f = pdir / "transcript.json"
    raw_map = {}
    if raw_f.exists():
        try:
            t_raw = json.loads(raw_f.read_text(encoding="utf-8"))
            for s in t_raw.get("segments", []):
                raw_map[s.get("id")] = s.get("text", "")
        except Exception:
            pass

    for idx, u in enumerate(data.get("utterances", [])):
        uid = u.get("id", idx)
        u["llm_transcript"] = u.get("text", "")
        if uid in raw_map:
            u["whisper_transcript"] = raw_map[uid]
    fix_f = pdir / "analysis_autofix.json"
    if fix_f.exists():
        try:
            data["autofix"] = json.loads(fix_f.read_text(encoding="utf-8"))
        except Exception:
            pass
    return data


def _final_transcript(pdir) -> dict:
    """The transcript every later step reads: the user's fix, else the LLM-corrected one, else the original."""
    for name in ("transcript_fixed.json", "transcript_corrected.json", "transcript.json"):
        if (pdir / name).exists():
            return json.loads((pdir / name).read_text(encoding="utf-8"))
    for name in ("audio_analysis.json", "audio-analysis.json"):
        if (pdir / name).exists():
            from ..transcribe import transcript_from_analysis_json
            t = transcript_from_analysis_json(pdir / name)
            if t is not None:
                return json.loads(t.model_dump_json(exclude_none=True))
    raise FileNotFoundError("transcript")


@router.get("/{pid}/transcript")
def transcript(pid: str, view: str = "final"):
    """The JSON the Audio Analyzer made from the audio: language, duration, segments with their words and times. `view=final` (default): the transcript the video is made from (LLM-corrected
    when the correction exists); `view=original`: transcript.json exactly as the speech recognizer wrote it; `view=compare`: both side by side per segment, with the LLM's corrections, the
    alignment of the corrected words and the review status (the Audio Analyzer page). Read-only."""
    from .. import transcript_review
    pdir = store.project_dir(pid)
    f = pdir / "transcript.json"
    if not f.exists():
        raise ApiError(409, "transcript_missing", "the audio has not been analyzed yet", "start the analysis first")
    try:
        if view == "compare":
            return transcript_review.comparison(pdir)
        return json.loads(f.read_text(encoding="utf-8")) if view == "original" else _final_transcript(pdir)
    except ValueError as e:
        raise ApiError(409, "transcript_unreadable", "the transcript could not be read", str(e)) from e


@router.get("/{pid}/logs")
def project_logs(pid: str):
    pdir = store.project_dir(pid)
    log_file = pdir / "log.txt"
    if not log_file.exists():
        return {"lines": [], "text": "No logs recorded yet."}
    try:
        text = log_file.read_text(encoding="utf-8", errors="replace")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return {"lines": lines[-300:], "text": "\n".join(lines[-300:])}
    except Exception as e:
        return {"lines": [], "text": f"Error reading log file: {e}"}


@router.get("/{pid}/timings")
def project_timings(pid: str):
    pdir = store.project_dir(pid)
    f = pdir / "timings.json"
    if not f.exists():
        return {"steps": {}, "last_build": {}}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return {"steps": {}, "last_build": {}}


@router.get("/{pid}/monitor")
def project_monitor(pid: str):
    pdir = store.project_dir(pid)
    info = store.read_info(pdir)
    status_obj = build_status(pid)
    timings = {}
    if (pdir / "timings.json").exists():
        try:
            timings = json.loads((pdir / "timings.json").read_text(encoding="utf-8"))
        except Exception:
            pass

    def _json(name):
        f = pdir / name
        if f.exists():
            try:
                return json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                return None
        return None

    def _file_info(name):
        f = pdir / name
        return {
            "exists": f.exists(),
            "path": name,
            "size_bytes": f.stat().st_size if f.exists() else 0,
            "modified": f.stat().st_mtime if f.exists() else None,
        }

    transcript = _json("transcript.json")
    cuts = _json("cuts.json")
    scene_plan = _json("scene_plan.json")
    visual_plan = _json("visual_plan.json")
    prompts_map = _json("prompts_map.json")
    match_rep = _json("match_report.json")
    comp_16 = _json("composition.json")
    comp_9 = _json("composition_9x16.json")
    prerender = _json("prerender_report.json")
    render_prof = _json("render_profile.json")

    inbox = pdir / "assets" / "inbox"
    raw = pdir / "assets" / "raw"
    inbox_count = sum(1 for f in inbox.iterdir() if f.is_file()) if inbox.exists() else 0
    raw_count = sum(1 for f in raw.iterdir() if f.is_file()) if raw.exists() else 0

    video_16 = pdir / "out.mp4"
    preview_16 = pdir / "out_preview.mp4"
    video_9 = pdir / "out_9x16.mp4"
    preview_9 = pdir / "out_preview_9x16.mp4"
    final_video = video_16 if video_16.exists() else (video_9 if video_9.exists() else None)
    preview_video = preview_16 if preview_16.exists() else (preview_9 if preview_9.exists() else None)

    active_video = final_video or preview_video
    video_meta = None
    if active_video and active_video.exists():
        video_meta = {
            "name": active_video.name,
            "path": active_video.name,
            "size_bytes": active_video.stat().st_size,
            "modified": active_video.stat().st_mtime,
            "is_preview": active_video == preview_video,
        }

    log_file = pdir / "log.txt"
    log_tail = []
    if log_file.exists():
        try:
            lines = [l.strip() for l in log_file.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
            log_tail = lines[-20:]
        except Exception:
            pass

    active_job = jobs.current(pid)
    job_data = None
    if active_job:
        job_data = {
            "label": active_job.label,
            "state": active_job.state,
            "step": active_job.step,
            "message": active_job.message,
            "error": active_job.error,
            "steps": list(active_job.names),
        }

    return {
        "project_id": pid,
        "name": info.get("name", pid),
        "job": job_data,
        "created": info.get("created", ""),
        "aspect": info.get("aspect", "16:9"),
        "state": info.get("state", ""),
        "audio": info.get("audio"),
        "status": status_obj.model_dump(),
        "timings": timings,
        "artifacts": {
            "audio": _file_info(info.get("audio", {}).get("file", "audio.wav")),
            "transcript": {
                "exists": bool(transcript),
                "segments_count": len(transcript.get("segments", [])) if transcript else 0,
                "words_count": sum(len(s.get("words", [])) for s in transcript.get("segments", [])) if transcript else 0,
            },
            "cuts": {
                "exists": bool(cuts),
                "count": len(cuts.get("cuts", [])) if cuts else 0,
            },
            "scene_plan": {
                "exists": bool(scene_plan),
                "count": len(scene_plan.get("scenes", [])) if scene_plan else 0,
            },
            "visual_plan": {
                "exists": bool(visual_plan),
                "count": len(visual_plan.get("scenes", [])) if visual_plan else 0,
                "approved_count": sum(1 for s in visual_plan.get("scenes", []) if s.get("approval", {}).get("status") == "approved") if visual_plan else 0,
            },
            "prompts": {
                "exists": bool(prompts_map),
                "count": len(prompts_map.get("prompts", [])) if prompts_map else 0,
                "required_count": sum(1 for p in prompts_map.get("prompts", []) if p.get("required")) if prompts_map else 0,
            },
            "images": {
                "inbox_count": inbox_count,
                "raw_count": raw_count,
            },
            "match": {
                "exists": bool(match_rep),
                "matched_count": sum(1 for m in match_rep.get("matches", []) if m.get("status") == "ok") if match_rep else 0,
                "missing_count": sum(1 for m in match_rep.get("matches", []) if m.get("status") == "missing") if match_rep else 0,
                "review_count": sum(1 for m in match_rep.get("matches", []) if m.get("status") == "review") if match_rep else 0,
                "unused_count": len(match_rep.get("unused", [])) if match_rep else 0,
                "broken_count": len(match_rep.get("broken", [])) if match_rep else 0,
                "matches": match_rep.get("matches", []) if match_rep else [],
            },
            "composition": {
                "exists": bool(comp_16 or comp_9),
                "scenes_count": len((comp_16 or comp_9 or {}).get("scenes", [])),
            },
            "prerender": {
                "exists": bool(prerender),
                "blocking": prerender.get("blocking", False) if prerender else False,
                "warnings_count": len(prerender.get("warnings", [])) if prerender else 0,
            },
            "video": video_meta,
            "render_profile": render_prof,
        },
        "log_tail": log_tail,
    }
