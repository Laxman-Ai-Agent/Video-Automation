"""Resource Manager endpoints (additive; docs/resources.md): the registry, its licences, discover / audit / import / verify / refresh as jobs, and the gallery previews.
Shared infrastructure: nothing here belongs to a project. The frontend names a recipe or a repository and file names; it never sends a command, a URL to download or a path to write.
Reading never uses the network; only discover / audit / import do, and only when asked."""
import json
import re

from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .. import resource_audit as ra, resource_jobs, resource_library as rl, resource_local, resource_verify as rv
from ..errors import ApiError

router = APIRouter(prefix="/resource-library", tags=["resource-library"])
_STATUS = {"invalid_request": 422, "unsafe_path": 422, "file_type": 422, "unsupported_category": 422, "rate_limited": 429, "network": 502, "http_error": 502, "not_found": 502,
           "gates_failed": 409, "audit_missing": 404, "host_not_allowed": 422, "changed_since_audit": 409, "too_large": 422}


class DiscoverBody(BaseModel):
    category: str
    query: str = ""


class AuditBody(BaseModel):
    recipe: str | None = None
    repository: str | None = None
    ref: str | None = None
    category: str | None = None
    files: list[str] | None = None
    names: list[str] | None = None
    license_file: str | None = None


class ImportBody(BaseModel):
    audit_id: str


class VerifyBody(BaseModel):
    ids: list[str] | None = None


def _guard(fn, *args):
    try:
        return fn(*args)
    except rl.ResourceError as e:
        raise ApiError(500 if e.code.startswith("registry") else 404 if e.code == "resource_unknown" else 422, e.code, e.message) from e
    except ra.AuditError as e:
        raise ApiError(_STATUS.get(e.code, 400), e.code, e.message) from e


def _job(kind: str, fn, *args) -> dict:
    return resource_jobs.start(kind, fn, *args)


@router.get("")
def list_resources(category: str | None = None, status: str | None = None, q: str | None = None):
    rows = _guard(rl.view, category, status, q)
    allrows = _guard(rl.view) if (category or status or q) else rows
    counts: dict = {}
    for r in allrows:
        counts[r["effective_status"]] = counts.get(r["effective_status"], 0) + 1
    return {"resources": rows, "counts": counts, "total": len(allrows), "categories": sorted({r["category"] for r in allrows}), "recipes": sorted(ra.RECIPES), "job": resource_jobs.running()}


@router.get("/licenses")
def licenses():
    out: dict[str, dict] = {}
    for e in _guard(rl.load):
        k = (e.license.spdx_id, e.license.notices_path or "-")
        o = out.setdefault(f"{k[0]}|{k[1]}", {"spdx_id": k[0], "notices_path": e.license.notices_path, "source": e.source.repository or e.source.url, "obligations": e.license.obligations, "resources": 0})
        o["resources"] += 1
    return {"licenses": sorted(out.values(), key=lambda x: (x["spdx_id"], x["notices_path"] or ""))}


@router.get("/jobs/{job_id}")
def job(job_id: str):
    return resource_jobs.get(job_id)


@router.get("/audits/{audit_id}")
def audit_get(audit_id: str):
    return _guard(ra.load_audit, audit_id)


@router.get("/previews/manifest")
def preview_manifest():
    """Which gallery still shows which resource and where (cell boxes in full-size px): a sheet holds many icons, so the page crops its cell instead of showing the whole sheet."""
    p = rv.PREVIEWS / "gallery_manifest.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {"created_at": None, "aspects": {}}


@router.get("/previews/{aspect}/{name}")
def preview(aspect: str, name: str):
    if aspect not in ("16x9", "9x16") or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}\.jpg", name):
        raise ApiError(404, "not_found", "no such preview")
    p = rv.PREVIEWS / aspect / name
    if not p.is_file():
        raise ApiError(404, "not_found", "no such preview (run Verify to make the gallery)")
    return FileResponse(p, media_type="image/jpeg")


@router.post("/discover")
def discover(body: DiscoverBody):
    return _job("discover", lambda c, q, progress: ra.discover(c, q), body.category, body.query)


@router.post("/audit")
def audit(body: AuditBody):
    spec = body.model_dump(exclude_none=True)
    return _job("audit", lambda s, progress: ra.audit(s, progress), spec)


@router.post("/import")
def import_(body: ImportBody):
    return _job("import", lambda a, progress: ra.import_audit(a, progress), body.audit_id)


@router.post("/verify")
def verify(body: VerifyBody):
    return _job("verify", lambda ids, progress: rv.verify(ids, progress), body.ids)


def _refresh(progress=None) -> dict:
    """Re-register the local components, rebuild the render bundle, re-stage fonts and mark a registered resource whose files changed as `stale` (nothing is upgraded or downloaded)."""
    local = resource_local.register()
    cur, stale = rl.load(), []
    for e in cur:
        if e.status in ("verified", "imported", "installed") and not rl.check_files(e)["ok"]:
            e.status = "stale"
            stale.append(e.resource_id)
    if stale:
        rl.save(cur)
    bundle = rl.build_bundle()
    return {"local": local, "stale": stale, "bundle_resources": len(bundle["resources"]), "staged_fonts": rl.stage_fonts()}


@router.post("/refresh")
def refresh():
    return _job("refresh", _refresh)


@router.get("/{resource_id:path}")
def detail(resource_id: str):
    e = _guard(rl.get, resource_id)
    d = e.model_dump(exclude_none=True)
    d["effective_status"] = rl.effective_status(e)
    d["file_check"] = rl.check_files(e)
    return d
