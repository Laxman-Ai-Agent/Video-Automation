# Remaining Cleanup Candidates & Future Deprecation Roadmap

**Date:** 2026-10-17 04:30:00 IST  
**Repository Root:** `E:\audio-to-video`  
**Git Branch:** `agents-building` | **HEAD:** `f6989b17372e3cdb42b4c92ab1783b3122a401ae`  
**Status:** FUTURE DEPRECATION CANDIDATES DOCUMENTED  

---

## 1. Executive Summary

This report documents legacy candidates that were intentionally preserved during the safe cleanup because their immediate removal would require changing launch scripts, updating test fixtures, or relocating physical dependency stores.

These candidates pose zero risk to the canonical architecture and can be addressed during future planned maintenance cycles.

---

## 2. Itemized Candidate Analysis

| Candidate Path | Physical Size | Current Status | Blocker / Dependency Preventing Immediate Removal | Recommended Future Action |
| :--- | :--- | :--- | :--- | :--- |
| `backend/` | 1.50 MB (120 files) | `REQUIRED_COMPATIBILITY` | Test fixtures in `tests/conftest.py` and `tests/test_skills_and_shared_memory.py` import `backend.autoplan`, `backend.llm_client`, and `backend.shared_memory`. Root `runproject.bat` also calls `backend.main`. | Update remaining test fixtures to import directly from `SYSTEM` and `UI.backend`, update batch scripts, then archive `backend/`. |
| `frontend/` (root) | 213.1 MB | `LEGACY_BUT_IN_USE` | Hosts the physical `frontend/node_modules/` store (~210 MB) targeted by the canonical junction `UI/frontend/node_modules`. | Invert the junction: move physical `node_modules` into `UI/frontend/node_modules`, and place a junction at root pointing inward. |
| `remotion/` (root) | 1.52 GB | `LEGACY_BUT_IN_USE` | Hosts the physical `remotion/node_modules/` store (~1.52 GB) and Chromium shell targeted by `VIDEO_ENGINE/remotion/node_modules`. | Invert the junction: move physical `node_modules` into `VIDEO_ENGINE/remotion/node_modules`, and place a junction at root pointing inward. |
| `skills/` (root) | 17.6 KB (7 files) | `MIGRATE_THEN_REASSESS` | `tests/test_skills_and_shared_memory.py:27` explicitly copies seed skills from `config.PROJECT_ROOT / "skills"`. | Update test fixture to check `SYSTEM/skills/` first, then safely remove root `skills/`. |
| `.pytest_tmp/` | 146.26 MB (261 files) | `EMPTY_OR_UNUSED_CANDIDATE` | Ephemeral test render artifacts from Pytest. Regenerated on test runs. | Can be purged safely during pre-release packaging. |

---

## 3. Step-by-Step Deprecation Plan for Next Maintenance Cycle

### Phase 1: Test Fixture Import Realignment
1. Update `tests/conftest.py` lines 5, 17, 28:
   - Change `from backend import autoplan` to `from VIDEO_ENGINE.pipeline import autoplan` (or stub).
   - Change `from backend import llm_client` to `from SYSTEM.llm import client as llm_client`.
   - Change `from backend import browser_profiles` to `from VIDEO_ENGINE.pipeline import browser_profiles`.
2. Update `tests/test_skills_and_shared_memory.py` line 27:
   - Change `(config.PROJECT_ROOT / "skills")` to `(config.PROJECT_ROOT / "SYSTEM" / "skills")`.

### Phase 2: Invert Dependency Junctions
1. Move physical `E:\audio-to-video\frontend\node_modules` into `E:\audio-to-video\UI\frontend\node_modules`.
2. Move physical `E:\audio-to-video\remotion\node_modules` into `E:\audio-to-video\VIDEO_ENGINE\remotion\node_modules`.
3. If root compatibility is still needed, create root junctions pointing inward:
   ```cmd
   mklink /J "E:\audio-to-video\frontend\node_modules" "E:\audio-to-video\UI\frontend\node_modules"
   mklink /J "E:\audio-to-video\remotion\node_modules" "E:\audio-to-video\VIDEO_ENGINE\remotion\node_modules"
   ```

### Phase 3: Archive Legacy `backend/`
Once Phases 1 and 2 are validated with a complete test pass, rename or archive `backend/` to `legacy_archive/backend_deprecated/`.
