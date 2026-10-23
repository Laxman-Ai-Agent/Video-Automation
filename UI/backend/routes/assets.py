"""Asset Collection (Stage 5) for its page: what the Visual Plan asked for, what was collected for each request (or why not), and the collected files themselves."""
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from VIDEO_ENGINE.stages import asset_collection as ac

from .. import llm_review, pipeline_view, store
from ..errors import ApiError

router = APIRouter(prefix="/projects/{pid}", tags=["assets"])


def _url(pid: str, a: dict) -> str:
    return f"/projects/{pid}/assets/file/{Path(a['file']).name}"


@router.get("/assets")
def get_assets(pid: str):
    """One item for every requirement of the Visual Plan: `collected` (with its file, source, licence and rights class), `fallback` (nothing suitable: the scene draws the plan's motion graphic, the reason
    is recorded) or `pending` (the stage has not run for this plan). Read-only: opening the page starts nothing."""
    pdir = store.project_dir(pid)
    aspect = pipeline_view.aspect_of(pdir)
    fp = ac.input_fingerprint(pdir, aspect)
    req, man = ac.load_requirements(pdir), ac.load_manifest(pdir)
    current = bool(man) and man.get("input_fingerprint") == fp
    got = {a["requirement_id"]: a for a in man.get("assets", [])} if current else {}
    missed = {f["requirement_id"]: f for f in man.get("fallbacks", [])} if current else {}
    items = []
    for r in req.get("requirements", []) if req.get("fingerprint") == fp else []:
        a, f = got.get(r["requirement_id"]), missed.get(r["requirement_id"])
        items.append({**r, "status": "collected" if a else "fallback" if f else "pending", "asset": {**a, "url": _url(pid, a)} if a else None, "reason": f["reason"] if f else None})
    passed, reason, rev = llm_review.is_stage_review_passed(pdir, "assets", aspect)
    return {"requirements_current": req.get("fingerprint") == fp, "manifest_current": current, "items": items, "providers": man.get("providers", {}) if current else {},
            "findings": ac.check_assets(pdir, man) if current else [], "review": {"passed": passed, "reason": reason, "summary": (rev or {}).get("summary"), "score": (rev or {}).get("score")},
            "summary": {"requirements": len(items), "collected": sum(i["status"] == "collected" for i in items), "fallbacks": sum(i["status"] == "fallback" for i in items)}}


@router.get("/assets/file/{name}")
def get_asset_file(pid: str, name: str):
    """A collected photo or clip. Only files that the manifest lists are served, by their bare name."""
    pdir = store.project_dir(pid)
    name = Path(name).name
    listed = {Path(a["file"]).name for a in ac.load_manifest(pdir).get("assets", [])}
    path = ac.collected_dir(pdir) / name
    if name not in listed or not path.is_file():
        raise ApiError(404, "file_not_found", f"{name} is not among the collected assets of this project")
    return FileResponse(path)
