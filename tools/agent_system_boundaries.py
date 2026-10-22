"""Where the Agent Building System ends and the video project begins: the ownership rules every boundary tool shares.

Dependency rule: the video project may depend on the Agent System, never the other way round. The Agent System reaches a domain project only
through SYSTEM/core/integrations.py. Some video-owned files live under SYSTEM/ for historical reasons; VIDEO_OWNED lists them.
"""
from __future__ import annotations

import ast
import fnmatch
from pathlib import Path

# Paths (relative to the repository root, forward slashes) owned by the video project even though they sit under SYSTEM/.
VIDEO_OWNED = (
    "SYSTEM/agents/video_generation_agents/*",
    "SYSTEM/skills/remotion/*",
    "SYSTEM/skills/motion/*",
    "SYSTEM/skills/rendering/*",
    "SYSTEM/skills/timeline/*",
    "SYSTEM/skills/animation/*",
    "SYSTEM/skills/audio/*",
    "SYSTEM/skills/transcript/*",
    "SYSTEM/skills/scene_segmentation/*",
    "SYSTEM/skills/visual_planning/*",
    "SYSTEM/skills/media/*",
    "SYSTEM/skills/graphics/*",
    "SYSTEM/skills/library/*",                        # installed skill packs (Remotion charts, layouts, ...) and their version archive and staging
    "SYSTEM/skills/archive/*",
    "SYSTEM/skills/staging/*",
    "SYSTEM/policies/llm_review.py",                  # the video stage gate built on the generic SYSTEM/policies/llm_reviewer.py
    "SYSTEM/core/pipeline_state.py",
    "SYSTEM/core/artifact_contracts.py",
    "SYSTEM/core/cli.py",
    "SYSTEM/core/checks.py",                          # image quality checks (OpenCV / PIL)
    "SYSTEM/observability/evaluation.py",             # evaluation suites over the video stages
    "SYSTEM/agents/architecture_validator/validators/video_pipeline_validator.py",
    "SYSTEM/agents/architecture_validator/tests/test_video_pipeline_validator.py",
)

# Top-level modules the Agent System must never import: the video project and the libraries only it needs.
FORBIDDEN_IMPORTS = frozenset({
    "VIDEO_ENGINE", "backend", "UI",
    "torch", "torchvision", "open_clip", "cv2", "faster_whisper", "rembg", "onnxruntime", "imagehash", "pydub", "scipy", "numpy", "PIL",
})

# Generated or media files never belong in the Agent System repository.
FORBIDDEN_SUFFIXES = frozenset({
    ".mp4", ".mov", ".avi", ".mkv", ".webm", ".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac", ".psd", ".blend",
})
FORBIDDEN_TOP_DIRS = frozenset({"VIDEO_ENGINE", "projects", "reports", "resource-library", "remotion"})
MAX_FILE_BYTES = 2 * 1024 * 1024


def is_video_owned(rel: str) -> bool:
    return any(fnmatch.fnmatch(rel, pattern) for pattern in VIDEO_OWNED)


def python_files(root: Path, folders: tuple[str, ...]) -> list[str]:
    out = []
    for folder in folders:
        base = root / folder
        if base.is_dir():
            out += [p.relative_to(root).as_posix() for p in base.rglob("*.py") if "__pycache__" not in p.parts and "node_modules" not in p.parts]
    return sorted(out)


def module_name(rel: str) -> str:
    dotted = rel[:-3].replace("/", ".")
    return dotted[: -len(".__init__")] if dotted.endswith(".__init__") else dotted


def imports_of(root: Path, rel: str) -> set[str]:
    """Every module a file imports, including lazy imports inside functions and relative imports (resolved to absolute names)."""
    tree = ast.parse((root / rel).read_text(encoding="utf-8"))
    package = module_name(rel).rsplit(".", 1)[0] if not rel.endswith("__init__.py") else module_name(rel)
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".")
                base = ".".join(parts[: len(parts) - (node.level - 1)]) if node.level > 1 else package
                module = f"{base}.{node.module}" if node.module else base
            else:
                module = node.module or ""
            found.add(module)
            found.update(f"{module}.{alias.name}" for alias in node.names)
    return found


def import_violations(root: Path, files: list[str]) -> list[str]:
    """Agent System files (not video-owned) that import video-owned modules, the video project or a video-only library."""
    video_modules = {module_name(f) for f in files if is_video_owned(f)}
    problems = []
    for rel in files:
        if is_video_owned(rel):
            continue
        bad = set()
        for name in imports_of(root, rel):
            if name.split(".")[0] in FORBIDDEN_IMPORTS:
                bad.add(name.split(".")[0])
            elif any(name == m or name.startswith(m + ".") for m in video_modules):
                bad.add(name)
        if bad:
            problems.append(f"{rel}: imports {sorted(bad)}")
    return problems
