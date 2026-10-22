"""The boundary checker really catches what it exists to catch, and the real repository passes it."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import agent_system_boundaries as rules  # noqa: E402
import check_boundaries as cb  # noqa: E402


def _tree(base: Path, files: dict) -> Path:
    for rel, content in files.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
    return base


def test_the_agent_system_in_this_checkout_does_not_depend_on_the_video_project():
    assert cb.check(ROOT, standalone=False) == []


def test_a_direct_import_of_the_video_project_is_flagged(tmp_path):
    root = _tree(tmp_path, {"SYSTEM/core/a.py": "from VIDEO_ENGINE.pipeline import orchestrator\n"})
    assert cb.check(root, standalone=False) == ["SYSTEM/core/a.py: imports ['VIDEO_ENGINE']"]


def test_a_lazy_import_inside_a_function_is_flagged(tmp_path):
    root = _tree(tmp_path, {"SYSTEM/core/a.py": "def f():\n    import cv2\n    return cv2\n"})
    assert cb.check(root, standalone=False) == ["SYSTEM/core/a.py: imports ['cv2']"]


def test_a_relative_import_of_a_video_owned_module_is_flagged(tmp_path):
    root = _tree(tmp_path, {
        "SYSTEM/core/__init__.py": "",
        "SYSTEM/core/pipeline_state.py": "X = 1\n",                 # video-owned
        "SYSTEM/core/a.py": "from . import pipeline_state\n",
        "SYSTEM/core/b.py": "from .pipeline_state import X\n",
    })
    problems = cb.check(root, standalone=False)
    assert any(p.startswith("SYSTEM/core/a.py") for p in problems) and any(p.startswith("SYSTEM/core/b.py") for p in problems)
    assert not any(p.startswith("SYSTEM/core/pipeline_state.py") for p in problems)      # the video-owned file itself is not the Agent System's


def test_the_standalone_check_flags_media_video_code_video_folders_and_big_files(tmp_path):
    root = _tree(tmp_path, {
        "SYSTEM/core/ok.py": "import json\n",
        "tests/fixtures/narration.wav": b"RIFF",
        "SYSTEM/core/pipeline_state.py": "X = 1\n",
        "VIDEO_ENGINE/stage.py": "x = 1\n",
        "docs/huge.bin": b"0" * (rules.MAX_FILE_BYTES + 1),
    })
    problems = "\n".join(cb.check(root, standalone=True))
    assert "narration.wav: media file" in problems
    assert "pipeline_state.py: video-owned file" in problems
    assert "VIDEO_ENGINE/stage.py: video folder" in problems
    assert "huge.bin" in problems and "exceeds" in problems
    assert "ok.py" not in problems


def test_ui_is_forbidden_in_the_video_checkout_but_is_the_agent_systems_own_in_the_standalone_repo(tmp_path):
    root = _tree(tmp_path, {"SYSTEM/core/a.py": "from UI.backend import main\n", "UI/backend/main.py": "x = 1\n"})
    assert cb.check(root, standalone=False) == ["SYSTEM/core/a.py: imports ['UI']"]
    assert cb.check(root, standalone=True) == []
    assert rules.import_violations(root, rules.python_files(root, ("SYSTEM",)), standalone=True) == []


def test_the_video_alias_is_forbidden_in_both_modes(tmp_path):
    root = _tree(tmp_path, {"SYSTEM/core/a.py": "from backend import config\n"})
    assert cb.check(root, standalone=False) == ["SYSTEM/core/a.py: imports ['backend']"]
    assert cb.check(root, standalone=True) == ["SYSTEM/core/a.py: imports ['backend']"]


def test_in_a_git_repository_only_what_a_commit_would_contain_is_checked(tmp_path):
    import subprocess
    root = _tree(tmp_path, {".gitignore": "projects/\n", "SYSTEM/core/ok.py": "import json\n",
                            "projects/p/log.jsonl": "{}\n", "docs/clip.mp4": b"\x00"})
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    problems = "\n".join(cb.check(root, standalone=True))
    assert "docs/clip.mp4: media file" in problems          # not ignored: a commit would contain it
    assert "projects" not in problems                       # ignored runtime data can never be committed


def test_a_clean_standalone_tree_passes(tmp_path):
    root = _tree(tmp_path, {"SYSTEM/core/ok.py": "import json\nfrom SYSTEM.core import integrations\n", "README.md": "# Agent System\n"})
    assert cb.check(root, standalone=True) == []
