"""Create or refresh the standalone Agent Building System repository from this checkout.

  python tools/export_agent_system.py <target-dir>

The Agent System's files are copied unchanged from the files git tracks here (no patching), minus what the video project owns
(tools/agent_system_boundaries.py) and minus accumulated runtime data. Exceptions, all listed here and nowhere else:
  - SEEDS: the skill catalog, installed-skills list and category taxonomy ship empty (the packs in them are video skill packs).
  - TESTS: the few tests under tests/ that exercise the Agent System, with TEST_REWRITES for the video project's `backend` alias.
Files that exist only in the standalone repository (README, requirements, UI, docs, hooks) are never touched. The only files removed are
ones a previous export wrote (listed in its EXPORT_MANIFEST.json) that this export no longer selects.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent_system_boundaries as rules  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

# Accumulated runtime data: a fresh Agent System starts without it.
RUNTIME_DATA = (
    "SYSTEM/agents/*/knowledge/archive/*",
    "SYSTEM/agents/*/memory/*.json",
    "SYSTEM/agents/*/memory/*.jsonl",
    "SYSTEM/agents/*/history/experiences.jsonl",
    "SYSTEM/config/*",
)

SEEDS = {
    "SYSTEM/skills/catalog.json": {"updated_at": "", "skills": {}},
    "SYSTEM/skills/installed_skills.json": {"updated_at": "", "total_installed": 0, "installed_skills": {}},
    "SYSTEM/skills/categories.json": {"total_categories": 0, "categories": []},
}

TOOLS = ("tools/agent_system_boundaries.py", "tools/check_boundaries.py")       # the export tool itself stays with the video project
TESTS = ("tests/test_integrations.py", "tests/test_boundaries.py", "tests/test_llm_client.py")
TEST_REWRITES = (
    (r"from backend\.main import app", "from UI.backend.main import app"),
    (r"from backend import llm_client", "from SYSTEM.core import llm_client"),
)


def tracked(root: Path) -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line]


def selected(files: list[str]) -> list[str]:
    keep = []
    for rel in files:
        if rel.startswith("SYSTEM/") and "/__pycache__/" not in rel:
            if rules.is_video_owned(rel) or rel in SEEDS or any(fnmatch.fnmatch(rel, p) for p in RUNTIME_DATA):
                continue
            keep.append(rel)
        elif rel in TOOLS or rel in TESTS:
            keep.append(rel)
    return keep


def export(root: Path, target: Path) -> dict:
    target.mkdir(parents=True, exist_ok=True)
    files = selected(tracked(root))
    for rel in files:
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        data = (root / rel).read_bytes()
        if rel in TESTS:
            text = data.decode("utf-8")
            for pattern, replacement in TEST_REWRITES:
                text = re.sub(pattern, replacement, text)
            data = text.encode("utf-8")
        dest.write_bytes(data)
    for rel, seed in SEEDS.items():
        version = json.loads((root / rel).read_text(encoding="utf-8")).get("version", "1.0.0")
        (target / rel).parent.mkdir(parents=True, exist_ok=True)
        (target / rel).write_text(json.dumps({"version": version, **seed}, indent=2) + "\n", encoding="utf-8")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True).stdout.strip()
    manifest = {"source_commit": commit, "files": sorted(files + list(SEEDS))}
    manifest_file = target / "EXPORT_MANIFEST.json"
    pruned = []
    if manifest_file.exists():
        for rel in set(json.loads(manifest_file.read_text(encoding="utf-8")).get("files", [])) - set(manifest["files"]):
            stale = target / rel
            if stale.is_file():
                stale.unlink()
                pruned.append(rel)
    manifest_file.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    return {"files": len(manifest["files"]), "source_commit": commit, "pruned": sorted(pruned)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target", help="the standalone repository folder (created if missing)")
    args = parser.parse_args()
    summary = export(ROOT, Path(args.target).resolve())
    print(f"exported {summary['files']} files from {summary['source_commit'][:7]} to {args.target}")
    for rel in summary["pruned"]:
        print(f"  removed (no longer exported): {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
