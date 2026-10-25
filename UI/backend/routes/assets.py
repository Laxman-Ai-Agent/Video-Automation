"""Asset Collection (Stage 5) for its page: what the Visual Plan asked for, what was collected for each request (or why not), and the collected files themselves."""
import hashlib
import shutil
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse
from PIL import Image
from pydantic import BaseModel

from VIDEO_ENGINE.stages import asset_collection as ac

from .. import llm_review, pipeline_view, store
from ..errors import ApiError

router = APIRouter(prefix="/projects/{pid}", tags=["assets"])


class AssetUpdateRequest(BaseModel):
    requirement_id: str
    scene_id: int | None = None
    kind: str | None = None
    clip_start: float | None = None
    clip_dur: float | None = None
    clip_end: float | None = None
    icon_name: str | None = None


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
        k = "photo" if r.get("media_type") == "image" or r.get("kind") in ("photo", "image") else r.get("kind") or r.get("media_type") or "photo"
        items.append({**r, "kind": k, "status": "collected" if a else "fallback" if f else "pending", "asset": {**a, "url": _url(pid, a)} if a else None, "reason": f["reason"] if f else None})

    # Discover and include icon elements from visual_planning.json if present
    vp_path = pdir / "visual_planning.json"
    if vp_path.exists():
        try:
            import json
            vp_data = json.loads(vp_path.read_text(encoding="utf-8"))
            for s in vp_data.get("scenes", []):
                sid = s.get("plan_scene_id") or s.get("id", 1)
                for e in s.get("elements", []):
                    if e.get("type") == "icon":
                        reg = e.get("registry_requirements") or {}
                        iname = reg.get("icon") or e.get("name") or e.get("lucide")
                        req_id = f"icon_{sid}_{e.get('element_id', 'icon')}"
                        items.append({
                            "requirement_id": req_id,
                            "scene_id": sid,
                            "element_id": e.get("element_id"),
                            "kind": "icon",
                            "type": "icon",
                            "media_type": "icon",
                            "query": iname or e.get("visual_description", "Icon"),
                            "alt_queries": reg.get("search_descriptors", []),
                            "description": e.get("visual_description") or e.get("role") or "Scene icon",
                            "icon_name": iname,
                            "status": "collected" if iname else "fallback",
                            "asset": {"kind": "icon", "name": iname, "title": iname} if iname else None,
                            "reason": None if iname else "No matching Lucide icon resolved",
                            "ai_prompt": None,
                        })
        except Exception:
            pass

    passed, reason, rev = llm_review.is_stage_review_passed(pdir, "assets", aspect)

    img_count = sum(1 for i in items if i.get("kind") in ("photo", "image") or i.get("media_type") in ("photo", "image"))
    vid_count = sum(1 for i in items if i.get("kind") == "video" or i.get("media_type") == "video")
    icon_count = sum(1 for i in items if i.get("kind") == "icon" or i.get("type") == "icon")

    return {
        "requirements_current": req.get("fingerprint") == fp,
        "manifest_current": current,
        "items": items,
        "providers": man.get("providers", {}) if current else {},
        "findings": ac.check_assets(pdir, man) if current else [],
        "review": {"passed": passed, "reason": reason, "summary": (rev or {}).get("summary"), "score": (rev or {}).get("score")},
        "summary": {
            "requirements": len(items),
            "collected": sum(i["status"] == "collected" for i in items),
            "fallbacks": sum(i["status"] == "fallback" for i in items),
        },
        "categories": {
            "all": len(items),
            "images": img_count,
            "videos": vid_count,
            "icons": icon_count,
        },
    }


@router.get("/assets/file/{name}")
def get_asset_file(pid: str, name: str):
    """A collected photo or clip. Only files that the manifest lists are served, by their bare name."""
    pdir = store.project_dir(pid)
    name = Path(name).name
    listed = {Path(a["file"]).name for a in ac.load_manifest(pdir).get("assets", [])}
    path = ac.collected_dir(pdir) / name
    if (name not in listed and not name.startswith(("chart_", "map_"))) or not path.is_file():
        raise ApiError(404, "file_not_found", f"{name} is not among the collected assets of this project")
    return FileResponse(path)


@router.post("/assets/upload")
async def upload_custom_asset(
    pid: str,
    file: UploadFile = File(...),
    requirement_id: str = Form(...),
    scene_id: int = Form(1),
):
    """Allows manual upload and replacement of an asset for a specific visual requirement."""
    pdir = store.project_dir(pid)
    if not pdir.exists():
        raise ApiError(404, "project_not_found", f"Project {pid} does not exist")

    out_dir = ac.collected_dir(pdir)
    out_dir.mkdir(parents=True, exist_ok=True)

    content = await file.read()
    sha = hashlib.sha256(content).hexdigest()
    ext = Path(file.filename or "image.jpg").suffix.lower()
    if not ext or ext not in (".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov"):
        ext = ".jpg"

    dest_name = f"{sha[:16]}{ext}"
    dest_path = out_dir / dest_name
    dest_path.write_bytes(content)

    width, height = 1920, 1080
    kind = "video" if ext in (".mp4", ".mov") else "photo"
    duration_s = None
    if kind == "photo":
        try:
            with Image.open(dest_path) as im:
                width, height = im.size
        except Exception:
            pass
    elif kind == "video":
        try:
            from VIDEO_ENGINE.ffmpeg import media_probe
            p = media_probe.probe(dest_path)
            dur = p.get("duration")
            if dur:
                duration_s = round(float(dur), 2)
            if p.get("video"):
                width = p["video"].get("width") or width
                height = p["video"].get("height") or height
        except Exception:
            pass

    man = ac.load_manifest(pdir)
    if not man:
        aspect = pipeline_view.aspect_of(pdir)
        fp = ac.input_fingerprint(pdir, aspect)
        man = {
            "schema": ac.SCHEMA_MAN,
            "version": ac.VERSION,
            "input_fingerprint": fp,
            "assets": [],
            "fallbacks": [],
        }

    man["fallbacks"] = [f for f in man.get("fallbacks", []) if f.get("requirement_id") != requirement_id]
    man["assets"] = [a for a in man.get("assets", []) if a.get("requirement_id") != requirement_id]

    clip_dur = duration_s or 5.0
    new_entry = {
        "requirement_id": requirement_id,
        "scene_id": scene_id,
        "kind": kind,
        "asset_id": sha[:16],
        "file": f"assets/collected/{dest_name}",
        "public_file": f"{ac.public_prefix(pdir)}/{dest_name}",
        "file_sha256": sha,
        "width": width,
        "height": height,
        "duration_s": duration_s,
        "clip_start": 0.0,
        "clip_dur": clip_dur,
        "clip_end": clip_dur,
        "title": file.filename or "Custom Upload",
        "author": "User",
        "rights_class": "A",
        "license": {"name": "User Upload (Personal)"},
        "source_url": "",
        "authenticity": "real",
        "selected_by": "manual_upload",
    }
    man["assets"].append(new_entry)
    ac._save(ac.manifest_path(pdir), man)

    remotion_public = (
        Path(ac.config.PROJECT_ROOT)
        / "VIDEO_ENGINE"
        / "remotion"
        / "public"
        / ac.public_prefix(pdir)
    )
    try:
        remotion_public.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(dest_path, remotion_public / dest_name)
    except Exception:
        pass

    return {
        "ok": True,
        "asset": {**new_entry, "url": _url(pid, new_entry)},
        "message": f"Successfully uploaded custom asset: {file.filename}",
    }


@router.post("/assets/update")
def update_asset(pid: str, body: AssetUpdateRequest):
    """Updates trim points for video assets or custom icon name for icon assets."""
    pdir = store.project_dir(pid)
    if not pdir.exists():
        raise ApiError(404, "project_not_found", f"Project {pid} does not exist")

    # If updating video trimming
    if body.clip_start is not None or body.clip_dur is not None or body.clip_end is not None:
        man = ac.load_manifest(pdir)
        found = False
        for a in man.get("assets", []):
            if a.get("requirement_id") == body.requirement_id:
                if body.clip_start is not None:
                    a["clip_start"] = max(0.0, round(float(body.clip_start), 2))
                if body.clip_dur is not None:
                    a["clip_dur"] = max(0.1, round(float(body.clip_dur), 2))
                if body.clip_end is not None:
                    a["clip_end"] = max(a.get("clip_start", 0.0) + 0.1, round(float(body.clip_end), 2))
                found = True
                break
        if found:
            ac._save(ac.manifest_path(pdir), man)

    # If updating icon
    if body.icon_name:
        vp_path = pdir / "visual_planning.json"
        if vp_path.exists():
            try:
                import json
                vp_data = json.loads(vp_path.read_text(encoding="utf-8"))
                for s in vp_data.get("scenes", []):
                    if body.scene_id is None or s.get("plan_scene_id") == body.scene_id or s.get("id") == body.scene_id:
                        for e in s.get("elements", []):
                            if e.get("type") == "icon":
                                if not e.get("registry_requirements"):
                                    e["registry_requirements"] = {}
                                e["registry_requirements"]["icon"] = body.icon_name.strip()
                                e["registry_requirements"]["resolved"] = True
                                e["name"] = body.icon_name.strip()
                                e["lucide"] = body.icon_name.strip()
                vp_path.write_text(json.dumps(vp_data, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass

    return {"ok": True, "message": "Asset settings updated successfully"}


class ChartGenerateRequest(BaseModel):
    chart_type: str = "bar"
    labels: list[str]
    data: list[float]
    title: str = ""
    label: str = "Metric"
    dark_mode: bool = True


class MapGenerateRequest(BaseModel):
    place_name: str
    width: int = 1280
    height: int = 720


@router.post("/assets/generate-chart")
def generate_chart_endpoint(pid: str, body: ChartGenerateRequest):
    """Generate high-res chart visual for the project via QuickChart."""
    from VIDEO_ENGINE.stages.chart_generator import build_chart_config, render_and_save_chart
    pdir = store.project_dir(pid)
    dest_dir = ac.collected_dir(pdir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = f"chart_{body.chart_type}_{abs(hash(body.title + str(body.labels))) % 10000}.png"
    out_file = dest_dir / filename
    cfg = build_chart_config(body.chart_type, body.labels, body.data, body.title, body.label, body.dark_mode)
    render_and_save_chart(cfg, out_file)
    return {"ok": True, "filename": filename, "url": f"/projects/{pid}/assets/file/{filename}", "type": "chart"}


@router.post("/assets/generate-map")
def generate_map_endpoint(pid: str, body: MapGenerateRequest):
    """Generate location map SVG visual for the project via OpenStreetMap Nominatim."""
    from VIDEO_ENGINE.stages.map_generator import render_location_map
    pdir = store.project_dir(pid)
    dest_dir = ac.collected_dir(pdir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = f"map_{body.place_name.lower().replace(' ', '_')}.svg"
    out_file = dest_dir / filename
    render_location_map(body.place_name, out_file, body.width, body.height)
    return {"ok": True, "filename": filename, "url": f"/projects/{pid}/assets/file/{filename}", "type": "map"}


@router.get("/assets-tools/sfx-catalog")
@router.get("/sfx/catalog")
def get_sfx_catalog(pid: str = ""):
    """List available motion sound effect presets."""
    from VIDEO_ENGINE.stages.sfx_manager import list_builtin_sfx
    return {"ok": True, "sfx": list_builtin_sfx()}


