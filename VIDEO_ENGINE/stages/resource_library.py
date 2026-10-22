"""Reusable Resource Library: the ONE canonical registry of reusable fonts, icons and local render components (docs/resources.md).
Shared infrastructure, not a pipeline stage: nothing here runs per video and nothing here touches the network (resource_audit.py does that, only on request).
`resource-library/catalog/registry.json` is the registry; `resource-library/bundle/render_bundle.json` is DERIVED from it (what the renderer needs: icon drawings, font files)
and is checked against it. A resource is selectable only while its status is `verified` AND the files on disk still hash to the recorded sha256 (else it is shown as `stale`).
Compositions carry `resource_id` + `resource_sha256` on the layers that use a resource; `check_composition` is what Motion Generation, Stage 10 and Final QC ask."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

from . import config

BASE = config.PROJECT_ROOT                      # fixed at import: the registry, the staged fonts and the hashed source files all live under ONE root (a test that moves config.PROJECT_ROOT must not split them)
ROOT = BASE / "resource-library"
REGISTRY = ROOT / "catalog" / "registry.json"
BUNDLE = ROOT / "bundle" / "render_bundle.json"
FONT_STAGE = config.REMOTION_DIR / "public" / "resource-fonts"     # a byte copy the renderer reads through staticFile (offline); checked by hash
SCHEMA_VERSION = 1
STATUSES = ("discovered", "auditing", "selected", "installed", "imported", "verified", "skipped", "failed", "stale")
CATEGORIES = ("font", "icon", "animated_icon", "diagram", "chart", "template", "background", "effect", "illustration", "media_asset", "3d_component", "react_component", "map")
ALLOWED_LICENSES = ("MIT", "ISC", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "OFL-1.1", "LicenseRef-project")   # LicenseRef-project = code written in this project
_ID = re.compile(r"^[a-z0-9][a-z0-9._/-]{2,120}$")
_lock = threading.RLock()


class ResourceError(Exception):
    """A registry or resource problem; `code` is stable (the API and the validators use it), the message is safe to show."""
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Source(_M):
    kind: Literal["github_repo", "github_release", "npm_package", "selected_file", "local"]
    url: str
    repository: str | None = None
    ref: str | None = None
    commit_sha: str | None = None
    release: str | None = None
    package_name: str | None = None
    package_version: str | None = None
    audit_date: str | None = None


class License(_M):
    spdx_id: str
    verified: bool
    license_url: str | None = None
    notices_path: str | None = None
    asset_license_notes: str = ""
    obligations: list[str] = []


class Integrity(_M):
    sha256: str | None = None
    pinned: bool = False
    source_files: list[str] = []


class Dependency(_M):
    name: str
    version: str
    direct: bool = True
    license: str | None = None


class Compatibility(_M):
    react: bool | str
    remotion: bool | str
    node: bool | str | None = None
    headless_render: bool = False
    deterministic: bool = False
    aspect_ratios: list[Literal["16:9", "9:16", "1:1", "other"]] = []


class Adapter(_M):
    adapter_id: str
    entrypoint: str
    props_schema_ref: str | None = None
    animation_presets: list[str] = []
    bounds_supported: bool = False
    layer_match: dict[str, str] | None = None            # which existing layer this resource is: {"type": "background", "look": "aurora"}; used to tag the layers the builder makes


class Usage(_M):
    import_mode: Literal["package", "selected_files", "local_component", "reference_only"]
    offline_required: bool = True
    preview_path: str | None = None
    used_by_pipeline_stages: list[str] = []


class Decision(_M):
    score: float | None = None
    decision: Literal["install", "import", "reference_only", "skip", "keep_reusable"]
    rationale: str = ""
    alternatives_considered: list[str] = []
    hard_gate_results: dict[str, bool] = {}


class Verification(_M):
    at: str
    ok: bool
    checks: dict[str, bool]
    aspects: list[str] = []
    evidence: str | None = None                          # path of the gallery still that shows the resource
    input_sha256: str | None = None                      # the resource hash that was verified
    notes: str = ""


class Entry(_M):
    resource_id: str
    display_name: str
    category: Literal[CATEGORIES]                       # type: ignore[valid-type]
    tags: list[str] = []
    status: Literal[STATUSES]                           # type: ignore[valid-type]
    source: Source
    license: License
    integrity: Integrity
    dependencies: list[Dependency] = []
    compatibility: Compatibility
    adapter: Adapter | None = None
    usage: Usage
    decision: Decision | None = None
    verification: Verification | None = None
    data: dict = {}                                      # per category: icon {viewBox, group}, font {family, files: [{weight, style, file, sha256}], scripts}

    @field_validator("resource_id")
    @classmethod
    def _id_ok(cls, v: str) -> str:
        if not _ID.match(v):
            raise ValueError("resource_id must match ^[a-z0-9][a-z0-9._/-]{2,120}$")
        return v

    @field_validator("integrity")
    @classmethod
    def _files_ok(cls, v: Integrity) -> Integrity:
        for f in v.source_files:
            safe_rel(f)
        return v

    @model_validator(mode="after")
    def _gates(self) -> "Entry":
        """The hard rules of the plan: only a pinned, licensed, hashed, really rendered resource can be `verified`."""
        s, here = self.status, self.status in ("installed", "imported", "verified")
        if self.license.notices_path:
            safe_rel(self.license.notices_path)
        if here and not (self.integrity.sha256 and re.fullmatch(r"[0-9a-f]{64}", self.integrity.sha256)):
            raise ValueError(f"{s}: integrity.sha256 is required")
        if here and self.source.kind != "local" and not (self.source.commit_sha and re.fullmatch(r"[0-9a-f]{40}", self.source.commit_sha)):
            raise ValueError(f"{s}: source.commit_sha (40 hex) is required: a mutable branch is not a version")
        if s == "verified":
            if not self.license.verified or self.license.spdx_id not in ALLOWED_LICENSES:
                raise ValueError("verified: the licence must be verified and one of " + ", ".join(ALLOWED_LICENSES))
            if self.source.kind != "local" and not self.license.notices_path:
                raise ValueError("verified: the licence text must be kept (license.notices_path)")
            if not self.integrity.pinned:
                raise ValueError("verified: integrity.pinned must be true")
            if not (self.compatibility.headless_render and self.compatibility.deterministic):
                raise ValueError("verified: headless_render and deterministic must have been shown")
            if self.verification:
                if not (self.verification.ok and self.verification.checks and all(self.verification.checks.values())):
                    raise ValueError("verified: a passing verification record is required")
                if self.verification.input_sha256 != self.integrity.sha256:
                    raise ValueError("verified: the verification belongs to another version of the files")
            elif self.source.kind != "local":
                raise ValueError("verified: a passing verification record is required")
        if self.category == "font" and here:
            fam, files = self.data.get("family"), self.data.get("files")
            if not fam or not files or not all(isinstance(x, dict) and x.get("file") and x.get("sha256") for x in files):
                raise ValueError("a font needs data.family and data.files [{weight, file, sha256}]")
        return self


# ---------------------------------------------------------------- paths and hashes
def safe_rel(p: str) -> str:
    """A repo-relative path with no `..`, no drive and no leading slash: a resource path can never leave the project."""
    q = Path(p)
    if q.is_absolute() or ".." in q.parts or ":" in p or p.startswith(("/", "\\")) or "\\" in p:
        raise ValueError(f"unsafe path {p!r}")
    return p


def _abs(rel: str) -> Path:
    return BASE / safe_rel(rel)


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def combined_sha(rels: list[str]) -> str:
    """One hash for a resource: its files by path and content, in path order (a renamed or edited file changes it)."""
    h = hashlib.sha256()
    for r in sorted(rels):
        h.update(r.encode() + b"\0" + file_sha(_abs(r)).encode() + b"\n")
    return h.hexdigest()


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


# ---------------------------------------------------------------- the registry
def load() -> list[Entry]:
    """Every entry validated; a broken registry is an error, never a silently shorter list."""
    with _lock:
        if not REGISTRY.exists():
            return []
        try:
            raw = json.loads(REGISTRY.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise ResourceError("registry_unreadable", f"the registry could not be read: {e}") from e
        if raw.get("schema_version") != SCHEMA_VERSION or not isinstance(raw.get("resources"), list):
            raise ResourceError("registry_schema", "the registry has an unknown schema_version or no resources list")
        out, seen = [], set()
        for i, r in enumerate(raw["resources"]):
            try:
                e = Entry.model_validate(r)
            except ValidationError as ex:
                raise ResourceError("registry_invalid", f"resources[{i}] ({r.get('resource_id') if isinstance(r, dict) else '?'}): {ex.errors()[0]['msg']}") from ex
            if e.resource_id in seen:
                raise ResourceError("registry_duplicate", f"duplicate resource_id {e.resource_id}")
            seen.add(e.resource_id)
            out.append(e)
        return out


def save(entries: list[Entry]) -> None:
    """Validate everything first (duplicates, schema), then replace the file in one step: a failed save leaves the old registry untouched."""
    ids = [e.resource_id for e in entries]
    if len(set(ids)) != len(ids):
        raise ResourceError("registry_duplicate", "duplicate resource_id in the registry")
    for e in entries:
        Entry.model_validate(e.model_dump())
    entries = sorted(entries, key=lambda e: e.resource_id)
    with _lock:
        atomic_write(REGISTRY, json.dumps({"schema_version": SCHEMA_VERSION, "updated_at": now(), "resources": [e.model_dump(exclude_none=True) for e in entries]}, indent=1, ensure_ascii=False) + "\n")


def upsert(new: list[Entry]) -> None:
    with _lock:
        cur = {e.resource_id: e for e in load()}
        for e in new:
            cur[e.resource_id] = e
        save(list(cur.values()))


def get(rid: str) -> Entry:
    for e in load():
        if e.resource_id == rid:
            return e
    raise ResourceError("resource_unknown", f"no resource {rid!r} in the registry")


def check_files(e: Entry) -> dict:
    """Do the files on disk still hash to what the registry recorded? (a local component, an imported SVG, a font and its staged copy)"""
    missing = [f for f in e.integrity.source_files if not _abs(f).is_file()]
    if missing:
        return {"ok": False, "reason": "missing_file", "missing": missing, "expected": e.integrity.sha256, "actual": None}
    actual = combined_sha(e.integrity.source_files) if e.integrity.source_files else None
    ok = actual == e.integrity.sha256
    return {"ok": ok, "reason": None if ok else "hash_mismatch", "missing": [], "expected": e.integrity.sha256, "actual": actual}


def effective_status(e: Entry) -> str:
    """What the entry really is NOW: a `verified` resource whose files changed is `stale`."""
    if e.status == "verified" and not check_files(e)["ok"]:
        return "stale"
    return e.status


def view(category: str | None = None, status: str | None = None, q: str | None = None) -> list[dict]:
    rows = []
    for e in load():
        st = effective_status(e)
        if category and e.category != category or status and st != status:
            continue
        if q and q.lower() not in " ".join([e.resource_id, e.display_name, *e.tags]).lower():
            continue
        d = e.model_dump(exclude_none=True)
        d["effective_status"] = st
        rows.append(d)
    return rows


def registry_digest() -> str:
    """Hash of the registry file ('' when there is none): a cache of something derived from the registry (the planner's primitive list) is keyed with it."""
    return file_sha(REGISTRY) if REGISTRY.exists() else ""


def icon_candidates() -> list[dict]:
    """The verified icons Motion Planning may choose from (id, tags, hash): what `motion_list.ts` hands to the planner."""
    return [{"id": e.resource_id, "tags": e.tags, "sha256": e.integrity.sha256, "name": e.display_name} for e in load() if e.category == "icon" and effective_status(e) == "verified"]


# ---------------------------------------------------------------- SVG: sanitise and read (an icon is data, never code)
SVG_TAGS = {"svg", "g", "path", "circle", "ellipse", "rect", "line", "polyline", "polygon"}
SVG_ATTRS = {"viewBox", "xmlns", "width", "height", "d", "cx", "cy", "r", "rx", "ry", "x", "y", "x1", "y1", "x2", "y2", "points", "transform", "fill", "stroke", "stroke-width",
             "stroke-linecap", "stroke-linejoin", "stroke-opacity", "fill-opacity", "opacity", "fill-rule", "clip-rule", "stroke-miterlimit"}
MAX_SVG = 20_000
_BAD_VALUE = re.compile(r"url\s*\(|javascript:|data:|https?:|<|&", re.I)


def parse_svg(text: str) -> dict:
    """Return {viewBox, children, tags, category} or raise ResourceError('svg_unsafe'). No script, style, foreignObject, image, use, event handler, external reference or entity."""
    if len(text) > MAX_SVG:
        raise ResourceError("svg_unsafe", "the SVG is larger than 20 KB")
    if re.search(r"<!DOCTYPE|<!ENTITY|<\?xml-stylesheet", text, re.I):
        raise ResourceError("svg_unsafe", "the SVG has a DOCTYPE, an entity or a stylesheet")
    head = re.match(r"\s*<!--(.*?)-->", text, re.S)
    meta = head.group(1) if head else ""
    tags = [t.strip() for t in (re.search(r"tags:\s*\[(.*?)\]", meta) or [None, ""])[1].split(",") if t.strip()]
    cat = (re.search(r"category:\s*(.+)", meta) or [None, ""])[1].strip()
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        raise ResourceError("svg_unsafe", f"the SVG is not well-formed: {e}") from e

    def walk(el: ET.Element, top: bool) -> dict:
        tag = el.tag.split("}")[-1]
        if tag not in SVG_TAGS or (not top and tag == "svg"):
            raise ResourceError("svg_unsafe", f"element <{tag}> is not allowed")
        attrs = {}
        for k, v in el.attrib.items():
            name = k.split("}")[-1]
            if name.lower().startswith("on") or name in ("href", "style", "class", "id") or name not in SVG_ATTRS:
                raise ResourceError("svg_unsafe", f"attribute {name!r} on <{tag}> is not allowed")
            if name != "xmlns" and _BAD_VALUE.search(v):
                raise ResourceError("svg_unsafe", f"attribute {name!r} has an external or active value")
            attrs[name] = v
        return {"tag": tag, "attrs": attrs, "children": [walk(c, False) for c in el]}

    top = walk(root, True)
    if not top["attrs"].get("viewBox"):
        raise ResourceError("svg_unsafe", "the SVG has no viewBox")
    if not top["children"]:
        raise ResourceError("svg_unsafe", "the SVG draws nothing")
    return {"viewBox": top["attrs"]["viewBox"], "children": top["children"], "tags": tags, "category": cat}


# ---------------------------------------------------------------- the render bundle (derived, checked)
def build_bundle() -> dict:
    """Write the derived bundle the renderer imports: for every installed / imported / verified icon its drawing, for a font its files. Same registry = same bytes."""
    items: dict[str, dict] = {}
    for e in load():
        if e.status not in ("installed", "imported", "verified"):
            continue
        if e.category == "icon" and e.integrity.source_files:
            svg = parse_svg(_abs(e.integrity.source_files[0]).read_text(encoding="utf-8"))
            items[e.resource_id] = {"kind": "icon", "sha256": e.integrity.sha256, "viewBox": svg["viewBox"], "children": svg["children"]}
        elif e.category == "font":
            items[e.resource_id] = {"kind": "font", "sha256": e.integrity.sha256, "family": e.data["family"],
                                    "files": [{"weight": f["weight"], "style": f.get("style", "normal"), "url": "resource-fonts/" + Path(f["file"]).name, "sha256": f["sha256"]} for f in e.data["files"]]}
        else:
            items[e.resource_id] = {"kind": "local", "sha256": e.integrity.sha256}
    out = {"schema_version": SCHEMA_VERSION, "resources": dict(sorted(items.items()))}
    text = json.dumps(out, indent=1, ensure_ascii=False, sort_keys=False) + "\n"
    if not BUNDLE.exists() or BUNDLE.read_text(encoding="utf-8") != text:
        atomic_write(BUNDLE, text)
    return out


def stage_fonts() -> list[str]:
    """Copy the font files of the registered fonts to VIDEO_ENGINE/remotion/public/resource-fonts (the renderer's offline source); a copy that differs from the registry hash is replaced."""
    FONT_STAGE.mkdir(parents=True, exist_ok=True)
    done = []
    for e in load():
        if e.category != "font" or e.status not in ("installed", "imported", "verified"):
            continue
        for f in e.data["files"]:
            src, dst = _abs(f["file"]), FONT_STAGE / Path(f["file"]).name
            if not dst.exists() or file_sha(dst) != f["sha256"]:
                dst.write_bytes(src.read_bytes())
            done.append(dst.name)
    return done


# ---------------------------------------------------------------- lineage: what a composition uses, and whether it is still right
def _refs(comp: dict) -> list[dict]:
    out = []

    def one(d: dict, where: str):
        if d.get("resource_id"):
            out.append({"resource_id": d["resource_id"], "declared_sha256": d.get("resource_sha256"), "layer_type": d.get("type") or d.get("kind"), "where": where, "props": d})
        if d.get("fontId"):
            out.append({"resource_id": d["fontId"], "declared_sha256": d.get("fontSha") or d.get("fontSha256"), "layer_type": "font", "where": where, "props": d})

    for s in comp.get("scenes", []):
        for i, l in enumerate(s.get("layers", [])):
            if not isinstance(l, dict):
                continue
            w = f"scene_{int(s.get('id', 0)):02d}/layer {i + 1} ({l.get('type')})"
            one(l, w)
            for j, it in enumerate(l.get("items", []) or []):
                if isinstance(it, dict):
                    one(it, f"{w}/item {j + 1}")
    return out


_LAYER_CATEGORY = {"icon": ("icon",), "font": ("font",), "background": ("background", "effect"), "chart": ("chart",)}


def used_resources(comp: dict) -> list[dict]:
    """The compact manifest of the resources a composition really uses (Stage 11 fingerprint, Stage 13 manifest, Stage 14 and the archive)."""
    try:
        reg = {e.resource_id: e for e in load()}
    except ResourceError:
        reg = {}
    seen: dict[str, dict] = {}
    for r in _refs(comp):
        e = reg.get(r["resource_id"])
        row = seen.setdefault(r["resource_id"], {"resource_id": r["resource_id"], "category": e.category if e else None, "declared_sha256": r["declared_sha256"],
                                                 "registry_sha256": e.integrity.sha256 if e else None, "license_id": e.license.spdx_id if e else None, "source_url": e.source.url if e else None,
                                                 "commit_sha": e.source.commit_sha if e else None, "notices_path": e.license.notices_path if e else None,
                                                 "adapter_id": e.adapter.adapter_id if e and e.adapter else None, "status": effective_status(e) if e else "unknown", "used_in": []})
        row["used_in"].append(r["where"])
    return sorted(seen.values(), key=lambda x: x["resource_id"])


def check_composition(comp: dict, offline: bool = True) -> list[dict]:
    """Findings for the resources a composition uses: {code, severity, resource_id, where, message}. Empty = every used resource exists, is verified, matches the pinned hash and resolves locally."""
    refs = _refs(comp)
    if not refs:
        return []
    try:
        reg = {e.resource_id: e for e in load()}
        bundle = json.loads(BUNDLE.read_text(encoding="utf-8"))["resources"] if BUNDLE.exists() else {}
    except (ResourceError, OSError, json.JSONDecodeError, KeyError) as e:
        return [{"code": "registry_unreadable", "severity": "error", "resource_id": None, "where": "registry", "message": f"the resource registry or its render bundle could not be read: {e}"}]
    out: list[dict] = []

    def add(code, rid, where, msg):
        out.append({"code": code, "severity": "error", "resource_id": rid, "where": where, "message": msg})

    for r in refs:
        rid, where, e = r["resource_id"], r["where"], reg.get(r["resource_id"])
        if e is None:
            add("resource_unknown", rid, where, f"{where}: resource {rid!r} is not in the registry")
            continue
        st = effective_status(e)
        if st != "verified":
            add("resource_stale" if st == "stale" else "resource_not_verified", rid, where, f"{where}: resource {rid} is {st}, only verified resources can be used")
            continue
        if r["declared_sha256"] and r["declared_sha256"] != e.integrity.sha256:
            add("resource_hash_mismatch", rid, where, f"{where}: the composition was built with another version of {rid} (its hash differs from the registry)")
        elif not r["declared_sha256"]:
            add("resource_hash_missing", rid, where, f"{where}: the layer does not record the pinned hash of {rid}")
        b = bundle.get(rid)
        if e.category in ("icon", "font") and (b is None or b.get("sha256") != e.integrity.sha256):
            add("resource_bundle_mismatch", rid, where, f"{where}: the render bundle does not hold the registered version of {rid} (rebuild it from the Resource Manager)")
        want = _LAYER_CATEGORY.get(str(r["layer_type"]))
        if want and e.category not in want:
            add("resource_category_mismatch", rid, where, f"{where}: a {r['layer_type']} layer cannot use the {e.category} resource {rid}")
        p = r["props"]
        if r["layer_type"] == "icon" and e.category == "icon":
            if "size" in p and not (isinstance(p["size"], (int, float)) and 16 <= p["size"] <= 1200):
                add("resource_props_invalid", rid, where, f"{where}: icon size must be a number between 16 and 1200")
            if "color" in p and not isinstance(p["color"], str):
                add("resource_props_invalid", rid, where, f"{where}: icon color must be a string")
        if offline and e.category == "font":
            for f in e.data["files"]:
                st_file = FONT_STAGE / Path(f["file"]).name
                if not st_file.is_file() or file_sha(st_file) != f["sha256"]:
                    add("resource_offline_missing", rid, where, f"{where}: the staged copy of {Path(f['file']).name} is missing or differs (run Refresh in the Resource Manager)")
    return out


def fingerprint(comp: dict) -> str:
    """Hash of ONLY the used resources (their registry hashes): an unrelated registry change does not change it."""
    rows = [(u["resource_id"], u["registry_sha256"], u["status"]) for u in used_resources(comp)]      # the status is in it: a used resource that turns stale changes it
    return hashlib.sha256(json.dumps(rows).encode()).hexdigest()
