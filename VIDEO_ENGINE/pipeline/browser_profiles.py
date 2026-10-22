"""Removes the temporary folders that Remotion leaves in the temp folder: Chrome profiles, webpack bundles and render asset folders.

Why they leak: Remotion (@remotion/renderer open-browser.js) makes `%TEMP%\\puppeteer_dev_chrome_profile-XXXX` for every browser it starts. On Windows it stops Chrome with an
un-awaited `taskkill` and deletes the folder at once; Chrome still holds files, the delete fails after 3 tries and the error is ignored. A render killed by Cancel (`taskkill /F /T`
on node) never reaches the cleanup at all. About 3 MB each; thousands in two days. A render or still without a prebuilt bundle also writes `remotion-webpack-bundle-XXXX` (a copy of
VIDEO_ENGINE/remotion/public: about 200 MB each) and `remotion-v<version>-assetsXXXX`, and never removes them: they filled C: during test runs.

What this does: only folders with one of those prefixes, that are not in the `before` snapshot (made by the run we are cleaning up after) or are older than STALE_SECONDS, that hold
the marker files of their kind, and that no running process references. Everything else in the temp folder is left alone. Every pass is logged."""
import logging
import os
import shutil
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

log = logging.getLogger("a2v.browser_profiles")
PREFIX = "puppeteer_dev_chrome_profile-"
STALE_SECONDS = 3600          # a folder this old with no process using it is a leftover of an earlier killed run
KINDS = {                     # prefix -> the files one of which a real folder of that kind contains
    PREFIX: ("Default", "Local State", "First Run"),
    "remotion-webpack-bundle-": ("index.html",),
    "remotion-v": ("remotion-assets-dir",),
}


def _folders():
    for prefix, markers in KINDS.items():
        for p in _tmp().glob(prefix + "*"):
            yield p, markers


def _tmp() -> Path:
    return Path(tempfile.gettempdir())


def snapshot() -> set[str]:
    """Names of the profile folders that exist now (so a later sweep knows which ones a run created)."""
    return {p.name for p, _ in _folders() if p.is_dir()}


def _in_use() -> str | None:
    """The command lines of all running processes joined (lower case), or None when they cannot be read (then nothing is deleted)."""
    try:
        if os.name == "nt":
            r = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_Process | % { $_.CommandLine }"], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=60)
        else:
            r = subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.lower() if r.returncode == 0 and r.stdout else None


def _size(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def sweep(before: set[str] | None = None, retries: int = 5, wait: float = 1.0) -> dict:
    """Delete finished profiles. `before` = snapshot taken before the run: only newer folders (plus stale ones) are considered; None = stale ones only.
    Folders a running process still references are kept and not retried. Returns {"removed", "bytes", "kept_in_use", "failed"}."""
    out = {"removed": 0, "bytes": 0, "kept_in_use": 0, "failed": 0}
    now = time.time()
    todo = []
    for p, markers in _folders():
        try:
            if not p.is_dir() or not any((p / m).exists() for m in markers):
                continue
            stale = now - p.stat().st_mtime > STALE_SECONDS
        except OSError:
            continue
        if stale or (before is not None and p.name not in before):
            todo.append(p)
    if not todo:
        return out
    procs = _in_use()
    if procs is None:
        log.warning("browser profiles: could not list running processes, nothing deleted (%d candidates)", len(todo))
        return out
    for attempt in range(retries):
        left = []
        for p in todo:
            if str(p).lower() in procs:
                out["kept_in_use"] += 1 if attempt == 0 else 0
                continue
            try:
                size = _size(p)
                shutil.rmtree(p)
                out["removed"] += 1
                out["bytes"] += size
            except OSError:
                left.append(p)           # Chrome may still be closing: try again
        todo = left
        if not todo:
            break
        time.sleep(wait)
    out["failed"] = len(todo)
    log.info("browser profiles: removed %d (%.1f MB), kept %d in use, %d could not be removed", out["removed"], out["bytes"] / 1e6, out["kept_in_use"], out["failed"])
    return out


@contextmanager
def cleaned_after():
    """Around anything that starts Remotion's browser: whatever happens (done, error, timeout, interrupted), the profiles it made are removed once their Chrome has exited."""
    before = snapshot()
    try:
        yield
    finally:
        sweep(before)
