"""The child process a project is running right now (the Remotion render), so Cancel can stop it instead of waiting minutes for it to finish.
Only processes this app started are ever killed (A2V_CANCEL=1)."""
import subprocess
import sys
import threading

_lock = threading.Lock()
_running: dict[str, subprocess.Popen] = {}


def register(project: str, proc: subprocess.Popen) -> None:
    with _lock:
        _running[project] = proc


def unregister(project: str, proc: subprocess.Popen) -> None:
    with _lock:
        if _running.get(project) is proc:
            del _running[project]


def kill(project: str) -> bool:
    """Stop the registered process and everything it started (cmd -> node -> Chromium). True if there was one still running."""
    with _lock:
        proc = _running.get(project)
    if proc is None or proc.poll() is not None:
        return False
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    else:
        proc.kill()
    return True
