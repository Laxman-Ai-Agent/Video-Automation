"""Uploads: image files for a project (many files / folders). Names are sanitized and flattened; limits enforced."""
import os
import re
from pathlib import Path

from fastapi import APIRouter, File, UploadFile
from PIL import Image

from ..errors import ApiError

router = APIRouter(prefix="/projects/{pid}", tags=["uploads"])
SAFE = re.compile(r"[^A-Za-z0-9._ -]")


MAX_NAME = 100                                                  # keeps full paths far below the Windows 260 limit
RESERVED = re.compile(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])$", re.I)   # Windows device names, with any extension


def safe_name(raw: str) -> str:
    """Flatten a relative path (folder uploads) to a file name that is safe on Windows: no odd characters,
    at most MAX_NAME characters (extension kept), and reserved device names (CON.png, nul.jpg) get a "_" prefix."""
    name = SAFE.sub("_", Path(raw.replace("\\", "/")).name).strip(". ") or "file"
    if RESERVED.match(name.split(".")[0]):
        name = "_" + name
    if len(name) > MAX_NAME:
        ext = Path(name).suffix[:16]
        name = name[: MAX_NAME - len(ext)] + ext
    return name


def check_ext(name: str, allowed: set[str], kind: str) -> None:
    if Path(name).suffix.lower() not in allowed:
        raise ApiError(415, "unsupported_media", f"{name}: not a supported {kind} file",
                       "allowed: " + ", ".join(sorted(allowed)))


async def receive(up: UploadFile, dest: Path, limit: int, verify_image: bool = False) -> None:
    """Stream to <dest>.part, enforce the size limit, verify images, then atomically replace dest."""
    tmp = dest.with_name(dest.name + ".part")
    size = 0
    try:
        with tmp.open("wb") as f:
            while chunk := await up.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise ApiError(413, "file_too_large", f"{dest.name} is larger than {limit // (1024 * 1024)} MB",
                                   "reduce the file size and upload again")
                f.write(chunk)
        if verify_image:
            try:
                with Image.open(tmp) as im:
                    im.verify()
            except Exception:
                raise ApiError(422, "invalid_image", f"{dest.name} is not a readable image", "re-export the image and upload again")
        os.replace(tmp, dest)
    except BaseException:
        tmp.unlink(missing_ok=True)      # our own partial file
        raise
