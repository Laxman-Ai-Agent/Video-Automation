"""The API must start the way runproject.bat starts it (`uvicorn UI.backend.main:app`), without tests/conftest.py.

Production code still imports through the compatibility name `backend` (an alias of `UI.backend`). Each check runs in a
clean interpreter, because pytest has already registered the alias in this process and would hide the failure."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _clean_python(code: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    return subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True, timeout=180)


def test_api_app_imports_in_a_clean_interpreter():
    r = _clean_python("import UI.backend.main as m; assert m.app.routes")
    assert r.returncode == 0, r.stderr[-1500:]


def test_backend_is_the_ui_backend_package_and_config_is_the_canonical_module():
    r = _clean_python(
        "import UI.backend\n"
        "import SYSTEM.core.config as canonical\n"
        "import backend\n"
        "from backend import config\n"
        "assert backend is UI.backend\n"
        "assert config is canonical, config\n")
    assert r.returncode == 0, r.stderr[-1500:]


def test_engine_modules_import_without_the_api():
    r = _clean_python("import VIDEO_ENGINE.pipeline.orchestrator")
    assert r.returncode == 0, r.stderr[-1500:]
