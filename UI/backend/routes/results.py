"""The rendered video (served with HTTP range requests) and the final delivery."""
from fastapi import APIRouter
from fastapi.responses import FileResponse

from .. import review, store
from ..errors import ApiError
from .uploads import safe_name

router = APIRouter(prefix="/projects/{pid}", tags=["results"])


@router.get("/result")
def result(pid: str, preview: bool = False, aspect: str = "16:9"):
    pdir = store.project_dir(pid)
    from ..artifact_contracts import verify_path_confinement
    verify_path_confinement(pdir, pdir)

    sfx = "_9x16" if aspect == "9:16" else ""
    f = pdir / (f"out_preview{sfx}.mp4" if preview else f"out{sfx}.mp4")
    verify_path_confinement(pdir, f)
    if not f.exists():
        raise ApiError(404, "result_missing", "the video has not been rendered yet", "POST /projects/{id}/render")
    return FileResponse(f, media_type="video/mp4")          # Starlette answers Range requests (seeking works)


@router.get("/delivery")
def get_delivery(pid: str, aspect: str = "16:9"):
    """Returns final video delivery manifest, gates status, and provenance."""
    import json
    pdir = store.project_dir(pid)
    from .. import final_qc
    from ..artifact_contracts import verify_path_confinement
    verify_path_confinement(pdir, pdir)

    sfx = "_9x16" if aspect == "9:16" else ""
    manifest_file = pdir / f"delivery_manifest{sfx}.json"
    reasons = final_qc.gate(pdir, aspect)

    manifest_data = None
    if manifest_file.exists():
        try:
            manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
        except Exception:
            manifest_data = None

    summary_file = pdir / f"delivery_summary{sfx}.json"
    summary_data = None
    if summary_file.exists():
        try:
            summary_data = json.loads(summary_file.read_text(encoding="utf-8"))
        except Exception:
            summary_data = None

    return {
        "project_id": pid,
        "aspect": aspect,
        "delivery_ready": len(reasons) == 0 and (manifest_data is not None or summary_data is not None),
        "gate_open": len(reasons) == 0,
        "gate_reasons": reasons,
        "manifest": manifest_data,
        "summary": summary_data,
        "download_url": f"/projects/{pid}/delivery/download?aspect={aspect}",
    }


@router.get("/delivery/download")
def download_delivery(pid: str, aspect: str = "16:9"):
    """Download the final delivered video file safely."""
    pdir = store.project_dir(pid)
    from ..artifact_contracts import verify_path_confinement
    from .. import final_qc

    sfx = "_9x16" if aspect == "9:16" else ""
    vid_name = f"out{sfx}.mp4"
    vid_path = pdir / vid_name

    verify_path_confinement(pdir, vid_path)

    if not vid_path.exists():
        raise ApiError(404, "video_not_found", f"Delivered video file {vid_name} not found")

    reasons = final_qc.gate(pdir, aspect)
    manifest_file = pdir / f"delivery_manifest{sfx}.json"
    if reasons and not manifest_file.exists():
        raise ApiError(409, "delivery_not_ready", "Video delivery is not approved or QC is incomplete", "; ".join(reasons))

    safe_filename = f"{safe_name(pid)}_{aspect.replace(':', 'x')}.mp4"
    return FileResponse(
        vid_path,
        media_type="video/mp4",
        filename=safe_filename,
    )


@router.get("/video")
def video(pid: str, aspect: str = "9:16", preview: bool = True):
    pdir = store.project_dir(pid)
    if aspect not in review.ASPECTS:
        raise ApiError(422, "invalid_request", "aspect must be 16:9 or 9:16")
    f = pdir / f"{'out_preview' if preview else 'out'}{'_9x16' if aspect == '9:16' else ''}.mp4"
    if not f.exists():
        raise ApiError(404, "result_missing", "the video has not been rendered yet", "run Preview or Render")
    return FileResponse(f, media_type="video/mp4")
