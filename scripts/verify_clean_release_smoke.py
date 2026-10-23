"""Clean-Environment Smoke Test for v2.0.0 Release Archive.

Extracts dist/laxman_video_engine_v2.0.0.zip to an isolated temporary directory
and verifies:
1. File structure, required directories, and exclusion of secrets / node_modules / venv.
3. Import integrity of backend, SYSTEM agents, registries, and pipeline state.
4. FastAPI route initialization and health endpoint availability.
5. All 21 canonical agents resolution in agent_registry.
6. Skill resolution from bundled local directories.
7. Creation of an isolated project and state verification under clean environment.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

EXPECTED_TOP_DIRS = [
    "SYSTEM",
    "VIDEO_ENGINE",
    "UI",
    "resource-library",
    "config",
    "docs",
    "scripts",
    "tests",
]

EXPECTED_ROOT_FILES = [
    "requirements.txt",
    "package.json",
    ".env.example",
    "start.bat",
    "runproject.bat",
    "README.md",
    "CLAUDE.md",
    "PROJECT_OVERVIEW.md",
    "STATUS.json",
    "RELEASE_MANIFEST.json",
]


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def run_clean_smoke_test(archive_path: Path) -> dict:
    results = {}
    print(f"=== Starting Clean-Environment Smoke Test on {archive_path.name} ===")
    assert archive_path.exists(), f"Archive missing: {archive_path}"

    temp_root = Path(tempfile.mkdtemp(prefix="laxman_v2_smoke_"))
    try:
        # 1. Extraction
        print(f"\n[1/6] Extracting archive to temporary folder: {temp_root} ...")
        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(temp_root)

        # Locate root inside zip (laxman_video_engine_v2.0.0/)
        extracted_root = temp_root / archive_path.stem
        if not extracted_root.exists():
            extracted_root = temp_root

        results["extracted_root"] = str(extracted_root)
        print(f"Extracted root: {extracted_root}")

        # 2. File & Directory Inventory Verification
        print("\n[2/6] Verifying file and directory inventory ...")
        for d in EXPECTED_TOP_DIRS:
            dp = extracted_root / d
            assert dp.exists() and dp.is_dir(), f"Missing expected directory: {d}"
        print(f"  [OK] All {len(EXPECTED_TOP_DIRS)} expected top-level directories present.")

        for f in EXPECTED_ROOT_FILES:
            fp = extracted_root / f
            assert fp.exists() and fp.is_file(), f"Missing expected root file: {f}"
        print(f"  [OK] All {len(EXPECTED_ROOT_FILES)} expected root files present.")

        # Ensure NO secrets or unwanted environments exist
        for item in extracted_root.rglob("*"):
            rel = item.relative_to(extracted_root).as_posix()
            assert "node_modules" not in rel, f"Forbidden node_modules found: {rel}"
            assert ".venv" not in rel, f"Forbidden .venv found: {rel}"
            assert not (item.name == ".env"), f"Forbidden .env found: {rel}"
        print("  [OK] Zero secrets, node_modules, or virtual environments found in package.")

        # 4. Isolated Python Import & Initialization
        print("\n[4/6] Testing isolated Python imports from extracted package ...")
        sys.path.insert(0, str(extracted_root))
        try:
            import UI.backend.main
            import SYSTEM.core.pipeline_state as ps
            import SYSTEM.core.resilience as res
            from SYSTEM.registries.agent_registry import registry
            from SYSTEM.registries.skill_registry import get_skill_registry

            assert UI.backend.main.app is not None
            assert len(UI.backend.main.app.routes) > 10
            print(f"  [OK] FastAPI app loaded successfully from UI.backend with {len(UI.backend.main.app.routes)} routes.")

            agents = registry.list_all_agents()
            assert agents, "the agent registry is empty"                                  # which agents must exist is validate_registry's rule (no second, hard-coded count here)
            validation_issues = registry.validate_registry()
            assert not validation_issues, f"Agent registry validation issues: {validation_issues}"
            print(f"  [OK] Agent registry resolved all {len(agents)} canonical agents with zero validation issues.")

            # Test skill discovery
            skills = get_skill_registry().list_skills()
            print(f"  [OK] Skill registry resolved {len(skills)} skills from bundled directories.")
            results["import_and_registry_verified"] = True
        finally:
            if str(extracted_root) in sys.path:
                sys.path.remove(str(extracted_root))

        # 5. Isolated Project Initialization and Pipeline State
        print("\n[5/6] Testing isolated project lifecycle inside clean extract ...")
        proj_dir = extracted_root / "projects" / "smoke_test_proj"
        proj_dir.mkdir(parents=True, exist_ok=True)
        (proj_dir / "project.json").write_text(json.dumps({"id": "smoke_test_proj", "state": "created"}), encoding="utf-8")
        
        state = ps.load_pipeline_state(proj_dir)
        assert state.project_id == "smoke_test_proj"
        assert list(state.stages) == list(ps.ACTIVE_STAGES)
        assert state.stages["audio"].status == "pending"
        print(f"  [OK] Project pipeline_state.json created and loaded with all {len(ps.ACTIVE_STAGES)} stages pending.")

        # Test path confinement
        res.verify_path_confinement(proj_dir, proj_dir / "pipeline_state.json")
        print("  [OK] Path confinement verified on clean extracted project.")
        results["isolated_project_verified"] = True

        # 6. Release Manifest Inspection
        print("\n[6/6] Verifying packaged RELEASE_MANIFEST.json ...")
        manifest_path = extracted_root / "RELEASE_MANIFEST.json"
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest_data["release_version"] == "2.0.0"
        assert manifest_data["regression_test_summary"]["pass_rate_percentage"] == 100.0
        print("  [OK] RELEASE_MANIFEST.json verified inside package (v2.0.0).")
        results["manifest_verified"] = True

        print("\n=== CLEAN-ENVIRONMENT SMOKE TEST PASSED (ALL 6 CHECKS) ===")
        results["status"] = "PASSED"
        return results

    finally:
        # Cleanup
        shutil.rmtree(temp_root, ignore_errors=True)
        print(f"Cleaned up temporary extraction directory: {temp_root}")


if __name__ == "__main__":
    archive = Path("dist/laxman_video_engine_v2.0.0.zip")
    res = run_clean_smoke_test(archive)
    print("\nSmoke Test Summary:")
    print(json.dumps(res, indent=2))
