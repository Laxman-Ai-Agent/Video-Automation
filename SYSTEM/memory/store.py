"""Project store: projects/<id>/project.json = {id, name, created, state, aspect?, audio?}. All path logic goes through config.
aspect is the output shape chosen at creation ("9:16" or "16:9"); use_images is always false (Motion-Only); audio is the reference to the uploaded file {file, original_name, size_bytes, format}."""
import json
import os
import re
import secrets
import shutil
import threading
import time
from pathlib import Path

from SYSTEM.core import config, media_kinds
from SYSTEM.core.errors import ApiError

ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$")     # slugs made here are lowercase; CLI projects (e.g. demo) also fit
MAX_IMAGE_BYTES = 50 * 1024 * 1024
MAX_AUDIO_BYTES = 500 * 1024 * 1024
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac"}
IMAGE_EXTS = set(config.IMAGE_EXTS)


def slug(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:24] or "project"
    return f"{base}-{secrets.token_hex(2)}"


def project_dir(pid: str) -> Path:
    """Validated project folder; unknown or malformed ids give a 404 (never a path outside projects/)."""
    pdir = config.PROJECTS_DIR / pid
    if not ID_RE.match(pid) or not pdir.is_dir():
        raise ApiError(404, "project_not_found", "project not found", "list projects with GET /projects")
    return pdir


_locks: dict[Path, threading.RLock] = {}
_locks_guard = threading.Lock()


def _info_lock(pdir: Path) -> threading.RLock:
    """One lock per project.json. On Windows os.replace fails a concurrent read of the target with PermissionError, and two writers share one .tmp file, so every read and write of the
    file (the API threads and the job threads of this one server process) takes it; other projects and other files are never blocked."""
    with _locks_guard:
        return _locks.setdefault(pdir.resolve(), threading.RLock())


def read_info(pdir: Path) -> dict:
    f = pdir / "project.json"
    with _info_lock(pdir):
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
    created = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(pdir.stat().st_mtime))   # folder made by the CLI
    return {"id": pdir.name, "name": pdir.name, "created": created, "state": "legacy"}


def write_info(pdir: Path, info: dict) -> None:
    tmp = pdir / "project.json.tmp"                       # atomic: readers never see a half-written file
    with _info_lock(pdir):
        tmp.write_text(json.dumps(info, indent=1), encoding="utf-8")
        os.replace(tmp, pdir / "project.json")


ASPECTS = ("9:16", "16:9")


def create(name: str, aspect: str | None = None, reusable_motion_templates: bool = False, media: dict | None = None, motion_kit: bool = False) -> Path:
    media = media_kinds.normalise(media)                  # ValueError before anything is made: the media settings are set here, at upload, and never change afterwards
    pid = slug(name)
    while (config.PROJECTS_DIR / pid).exists():
        pid = slug(name)
    pdir = config.PROJECTS_DIR / pid
    pdir.mkdir(parents=True)
    info = {"id": pid, "name": name.strip()[:80] or pid, "created": time.strftime("%Y-%m-%dT%H:%M:%S"), "state": "created"}
    if aspect:
        info["aspect"] = aspect
    info["use_images"] = False                            # Motion-Only: kept in project.json for the readers and fingerprints that include it
    info["motion_branch"] = True                          # new projects run the Motion Planning -> Motion Generation branch
    info["reusable_motion_templates"] = bool(reusable_motion_templates)
    info["media"] = media
    info["motion_kit"] = bool(motion_kit)                 # set here, at upload, never afterwards (own key, not in `media`: the Visual Plan fingerprint hashes `media` and does not depend on the kit)
    write_info(pdir, info)
    return pdir


def motion_kit(pdir: Path) -> bool:
    """Is the optional motion kit on for this project? Off by default and for every project made before the option existed."""
    return read_info(pdir).get("motion_kit", False) is True


def media(pdir: Path) -> dict:
    """The media settings of the project: {"ai_images"}. Set at upload; a project made before it existed gets the defaults."""
    return media_kinds.options(read_info(pdir))


def motion_branch(pdir: Path) -> bool:
    """Does this run have the motion branch (Motion Planning -> Motion Generation)? Always active in Motion-Only mode."""
    return True


def uses_images(pdir: Path) -> bool:
    """True when the project has real media enabled (use_images is True in project.json)."""
    return bool(read_info(pdir).get("use_images", False))


def reusable_motion_templates(pdir: Path) -> bool:
    """Reusable Motion Templates (per project): False = Custom Code Mode (generate original scene-specific executable TSX code)."""
    return read_info(pdir).get("reusable_motion_templates", False) is True


def set_reusable_motion_templates(pdir: Path, enabled: bool) -> bool:
    with _info_lock(pdir):
        info = read_info(pdir)
        info["reusable_motion_templates"] = bool(enabled)
        write_info(pdir, info)
    return info["reusable_motion_templates"]


def list_projects() -> list[dict]:
    if not config.PROJECTS_DIR.exists():
        return []
    dirs = [d for d in sorted(config.PROJECTS_DIR.iterdir()) if d.is_dir() and not d.name.startswith(("_", "."))]
    return sorted((read_info(d) for d in dirs), key=lambda i: i["created"], reverse=True)


def set_state(pid: str, state: str) -> None:
    pdir = config.PROJECTS_DIR / pid
    if pdir.is_dir():
        with _info_lock(pdir):                            # read-modify-write: two state changes must not lose one another
            info = read_info(pdir)
            info["state"] = state
            write_info(pdir, info)


def delete(pdir: Path) -> None:
    shutil.rmtree(pdir)
