# File and Directory Counts & Statistical Analysis

**Date:** 2026-10-17 04:22:00 IST  
**Repository Root:** `E:\audio-to-video`  
**Git Branch:** `agents-building` | **HEAD:** `f6989b17372e3cdb42b4c92ab1783b3122a401ae`  
**Status:** 100% AUDITED AND QUANTIFIED  

---

## 1. Counting Rules & Methodology

To avoid ambiguities in counting files, the following explicit counting rules are applied:
1. **Physical Files:** Every unique inode/file stored on disk.
2. **Reparse Points / Junctions:** NTFS directory junctions (`UI/frontend/node_modules` and `VIDEO_ENGINE/remotion/node_modules`) are counted once as **Junctions** and are **never recursively traversed** during repository file counts to eliminate double-counting physical storage.
3. **Vendor Dependencies (`node_modules` and `.venv`):** Counted in global physical totals, but separated out in application-level breakdowns.
4. **Git Metadata (`.git`):** Git packfiles and internal tree objects are counted in full physical scans but excluded from source file distributions.

---

## 2. Global Repository Counts

| Scope | Directories | Files | Junctions | Total Items |
| :--- | :--- | :--- | :--- | :--- |
| **Complete Repository (including `.git`, `.venv`, `node_modules`)** | **6,014** | **76,327** | **2** | **82,343** |
| **Excluding `.git` VCS metadata** | **3,788** | **42,497** | **2** | **46,287** |
| **Application & User Code (Excluding `.venv` and all `node_modules`)** | **526** | **4,874** | **2** | **5,402** |

---

## 3. Top-Level Area Breakdown

Physical file and directory counts across every top-level area:

| Top-Level Area | Physical Files | Direct Subdirectories | Area Classification |
| :--- | :--- | :--- | :--- |
| `.venv/` | 33,830 | 2,226 | Python Virtual Environment |
| `remotion/` (root physical store) | 26,722 | 1,842 | Node Store (`node_modules` + project) |
| `frontend/` (root physical store) | 12,950 | 1,120 | Node Store (`node_modules` + SPA) |
| `VIDEO_ENGINE/` | 443 | 18 | Canonical Video Engine (excluding junction) |
| `reports/` | 381 | 24 | Migration & Audit Reports |
| `projects/` | 319 | 42 | User Projects & Checkpoints |
| `improvements/` | 291 | 18 | Improvement Plans (A0–A4, Phase 1–10) |
| `tests/` | 167 | 6 | Python Test Suite & Fixtures |
| `UI/` | 159 | 14 | Canonical UI (excluding junction) |
| `backend/` | 135 | 8 | Legacy Flat Backend Repository |
| `SYSTEM/` | 85 | 12 | Canonical System Services & Agents |
| `resource-library/` | 80 | 12 | Fonts, Audio SFX, Motion Graphics |
| `docs/` | 16 | 1 | Architecture Specifications |
| `models/` | 8 | 1 | faster-whisper Model Weights |
| `skills/` | 7 | 1 | Agent Skills Markdown Instructions |
| `config/` | 7 | 1 | Persistent JSON State Stores |
| `scripts/` | 2 | 1 | Maintenance Utility Scripts |
| Root Regular Files | 13 | 0 | Configuration, Batches, READMEs |

---

## 4. Subsystem Detailed Counts

### A. Canonical Architecture Core
- **`SYSTEM/` Subsystem:** **85 files**
  - `agents/video_generation_agents/`: 16 files
  - `agents/shared/`: 3 files (`base_agent.py`, `communication.py`, `contracts.py`)
  - `agents/system_agents/`: 4 files
  - `approvals/`: 4 files (`approval_engine.py`, `pin_service.py`, `approval_models.py`, `__init__.py`)
  - `llm/`: 4 files (`llm_gateway.py`, `usage_tracker.py`, `llm_usage.py`, `client.py`)
  - `memory/`: 3 files (`shared_memory.py`, `store.py`, `__init__.py`)
  - `observability/`: 2 files (`evaluation.py`, `__init__.py`)
  - `registries/`: 3 files (`agent_registry.py`, `skill_registry.py`, `__init__.py`)
  - `core/`: 3 files (`errors.py`, `logging.py`, `__init__.py`)
- **`UI/` Subsystem:** **159 files** (excluding junctioned `node_modules`)
  - `UI/backend/`: 30 files (15 route modules, `main.py`, `api_models.py`, `llm_client.py`, `store.py`)
  - `UI/frontend/`: 129 files (React 19 source, pages, components, tests, configurations)
- **`VIDEO_ENGINE/` Subsystem:** **443 files** (excluding junctioned `node_modules`)
  - `stages/`: 14 files (12 canonical stages + 1 helper + `__init__.py`)
  - `pipeline/`: 6 files (`orchestrator.py`, `stage_adapters.py`, `state_manager.py`, etc.)
  - `ffmpeg/`: 4 files (`audio_processing.py`, `media_probe.py`, `video_assembly.py`, `__init__.py`)
  - `remotion/`: 419 files (motion compositions, public fonts, scripts, test frames)

### B. Test Suite File Counts
- **Python Multi-Suite Tests:** **68 test files** in `tests/`
- **Frontend Vitest Suites:** **16 test files** in `UI/frontend/tests/`

---

## 5. File Distribution by Extension (Top 20)

| Extension | Total Files in Repo | Application Code Files (excl. dependencies) | Description |
| :--- | :--- | :--- | :--- |
| `.js` / `.mjs` | 19,643 | 12 | JavaScript modules (vendor vs tooling) |
| `.py` | 11,014 | 412 | Python modules (venv vs codebase) |
| `.pyc` | 11,049 | 0 | Compiled Python bytecode |
| `.ts` / `.tsx` | 9,115 | 185 | TypeScript application source |
| `.h` / `.hpp` / `.cpp` | 9,581 | 0 | C/C++ native Python extensions in venv |
| `.json` | 1,336 | 114 | JSON schemas, configs, and baselines |
| `.md` | 1,187 | 182 | Documentation and reports |
| `.png` | 782 | 48 | Motion test frames and icons |
| `.dll` / `.pyd` / `.so` | 349 | 0 | Binary shared libraries in venv |
| `.txt` | 279 | 15 | Logs and text audit files |
| `.wav` | 37 | 37 | Narration audio files & SFX |
| `.csv` | 36 | 4 | CSV data tables and inventories |
| `.onnx` | 4 | 4 | Local neural network model weights |
