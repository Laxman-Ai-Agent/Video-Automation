"""Boundary check between the Agent Building System and the video project.

  python tools/check_boundaries.py               in the video checkout: the Agent System's files must not depend on the video project
  python tools/check_boundaries.py --standalone  in the Agent System repository: also no video-owned code, generated media, video folders or oversized files

Exit code 1 and a list of problems when a rule is broken. See tools/agent_system_boundaries.py for the rules.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent_system_boundaries as rules  # noqa: E402

SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", "dist", ".pytest_cache"}


def tracked_files(root: Path) -> list[str]:
    out = []
    for folder, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        out += [(Path(folder) / n).relative_to(root).as_posix() for n in names]
    return sorted(out)


def check(root: Path, standalone: bool) -> list[str]:
    folders = ("SYSTEM", "UI", "tools", "tests") if standalone else ("SYSTEM",)
    problems = rules.import_violations(root, rules.python_files(root, folders), standalone)
    if standalone:
        for rel in tracked_files(root):
            path = root / rel
            if rules.is_video_owned(rel):
                problems.append(f"{rel}: video-owned file in the Agent System repository")
            if rel.split("/")[0] in rules.FORBIDDEN_TOP_DIRS:
                problems.append(f"{rel}: video folder in the Agent System repository")
            if path.suffix.lower() in rules.FORBIDDEN_SUFFIXES:
                problems.append(f"{rel}: media file ({path.suffix.lower()}) in the Agent System repository")
            if path.stat().st_size > rules.MAX_FILE_BYTES:
                problems.append(f"{rel}: {path.stat().st_size // 1024} KB exceeds the {rules.MAX_FILE_BYTES // 1024} KB limit")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--standalone", action="store_true")
    args = parser.parse_args()
    problems = check(Path(args.root), args.standalone)
    for p in problems:
        print(p)
    print(f"boundary check: {'FAILED, ' + str(len(problems)) + ' problem(s)' if problems else 'ok'}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
