"""Plain-language failure messages (M9): the one place that turns low-level errors into text a user can act on.

UserProblem = something the user can fix; its message already says how (pipeline.StepError is one).
explain(exc) / explain_text(output) translate everything else; unknown errors keep their own text."""
import errno
import json
import shutil
from pathlib import Path

from pydantic import ValidationError

_MEMORY = "Not enough free memory (RAM) for this step. Close other programs (browser tabs, other apps) and run it again."
_DISK = "The disk is full. Free some space on the drive that holds the project and run it again."
_LOCKED = "A file is locked by another program. Close any program that has the project's files open and run it again."

# (substrings of the lower-cased text, message): first rule with a hit wins
_TEXT_RULES: list[tuple[tuple[str, ...], str]] = [
    (("mkl_malloc", "failed to allocate", "bad_alloc", "out of memory", "cannot allocate memory", "memoryerror"), _MEMORY),
    (("no space left", "enospc", "not enough space on the disk", "disk full"), _DISK),
    (("being used by another process", "winerror 32"), _LOCKED),
    # before the font rule: "Cannot find module '@remotion/google-fonts/...'" is a missing package, not a network problem
    (("cannot find module", "module_not_found"), 'Remotion\'s packages are missing. Run "npm install" in the remotion folder.'),
    (("failed to load font", "google-fonts", "fonts.gstatic", "fonts.googleapis"),
     "A font could not be loaded. The video fonts (Poppins, Noto Sans Telugu) are downloaded from Google Fonts while "
     "rendering, so the computer needs internet access. Check the connection and run it again."),
    (("error loading image", "failed to load image", "could not load image"),
     "An image used by the video could not be loaded. Re-export the images and upload them again."),
]


class UserProblem(Exception):
    """A problem the user can fix; the message says how."""


def explain_text(text: str) -> str | None:
    """A clear message for known failures in program output (Remotion, ffmpeg ...), else None."""
    low = text.lower()
    return next((msg for words, msg in _TEXT_RULES if any(w in low for w in words)), None)


def explain(exc: BaseException) -> str:
    """The message to show for any exception."""
    if isinstance(exc, UserProblem):
        return str(exc)
    if isinstance(exc, MemoryError):
        return _MEMORY
    if isinstance(exc, OSError) and (exc.errno == errno.ENOSPC or getattr(exc, "winerror", None) == 112):
        return _DISK
    if isinstance(exc, PermissionError):
        name = f" ({Path(exc.filename).name})" if exc.filename else ""
        return _LOCKED.replace("A file", f"A file{name}", 1)
    if isinstance(exc, json.JSONDecodeError):
        return f"A project file is not valid JSON (line {exc.lineno}). Run the step that creates it again, or restore it from a backup."
    if isinstance(exc, ValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", ())) or exc.title
        return f"A project file has an unexpected format ({where}: {first.get('msg', 'invalid')}). Run the step that creates it again."
    if isinstance(exc, FileNotFoundError):
        return f"A required file is missing: {Path(exc.filename).name if exc.filename else exc}."
    return explain_text(f"{type(exc).__name__}: {exc}") or str(exc) or type(exc).__name__


def check_disk(path: Path, need_gb: float, what: str) -> None:
    """Raise UserProblem when the drive holding `path` has less than need_gb free."""
    p = path
    while not p.exists() and p != p.parent:
        p = p.parent
    free = shutil.disk_usage(p).free / 1024**3
    if free < need_gb:
        raise UserProblem(f"Not enough disk space for {what}: {free:.1f} GB free on {p.anchor or p}, about {need_gb:g} GB needed. "
                          "Free some space and run it again.")
