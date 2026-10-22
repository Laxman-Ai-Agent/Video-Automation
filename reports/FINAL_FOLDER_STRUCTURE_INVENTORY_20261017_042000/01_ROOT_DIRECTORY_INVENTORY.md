# Root Directory Inventory

**Date:** 2026-10-17 04:22:00 IST  
**Repository Root:** `E:\audio-to-video`  
**Total Root Items:** 35 items (22 Directories, 13 Regular Files)  
**Status:** 100% VERIFIED ON DISK  

---

## 1. Itemized Root Directory Matrix

Every file and folder located in the immediate repository root is documented below:

| # | Item Name | Item Type | Size / Items | Purpose & Functional Description | Canonical Ownership | Status / Verification |
|---|---|---|---|---|---|---|
| 1 | `.claude/` | Directory | 0 B (config) | Claude Code assistant project-level settings and commands | INFRASTRUCTURE | VERIFIED |
| 2 | `.env.example` | File | 54 B | Example environment variable template (`PEXELS_API_KEY`, etc.) | INFRASTRUCTURE | VERIFIED |
| 3 | `.git/` | Directory | ~48 MB | Local Git version control database, refs, and objects | VCS | VERIFIED |
| 4 | `.gitignore` | File | 529 B | Git exclusion patterns for Python, Node, media, and caches | VCS | VERIFIED |
| 5 | `.pytest_cache/` | Directory | Caches | Pytest test execution cache and failure memory | CACHE | VERIFIED |
| 6 | `.pytest_tmp/` | Directory | Temp files | Temporary files generated during test runs | CACHE | VERIFIED |
| 7 | `.venv/` | Directory | 2.81 GB | Python 3.10 virtual environment and installed pip wheels | INFRASTRUCTURE | VERIFIED |
| 8 | `CLAUDE.md` | File | 9.17 KB | Primary operator instructions, pipeline rules, and coding guide | DOCS_AND_REPORTS | VERIFIED |
| 9 | `PIPELINE_AUDIT_REPORT.txt` | File | 24.73 KB | Legacy pipeline audit summary from early development | DOCS_AND_REPORTS | HISTORICAL |
| 10 | `PROJECT_OVERVIEW.md` | File | 6.51 KB | High-level system architecture and user journey guide | DOCS_AND_REPORTS | VERIFIED |
| 11 | `PROJECT_STATUS.md` | File | 160.14 KB | Chronological project milestone log and previous test results | DOCS_AND_REPORTS | HISTORICAL |
| 12 | `README.md` | File | 6.18 KB | Repository entry point documentation and run commands | DOCS_AND_REPORTS | VERIFIED |
| 13 | `STATUS.json` | File | 8.52 KB | Machine-readable milestone status from earlier phases | DOCS_AND_REPORTS | HISTORICAL |
| 14 | `STATUS.md` | File | 15.64 KB | Human-readable milestone log from earlier development phases | DOCS_AND_REPORTS | HISTORICAL |
| 15 | `SYSTEM/` | Directory | 848.6 KB | **Canonical system shared infrastructure**: Agents, Registries, Approvals, LLM Gateway, Shared Memory, Observability | **CANONICAL (SYSTEM)** | **CANONICAL** |
| 16 | `UI/` | Directory | 2.41 MB | **Canonical UI layer**: React 19 Frontend SPA and FastAPI Backend routes | **CANONICAL (UI)** | **CANONICAL** |
| 17 | `VIDEO_ENGINE/` | Directory | 197.3 MB | **Canonical execution engine**: Pipeline Orchestrator, 12 Stages, Remotion, FFmpeg | **CANONICAL (VIDEO_ENGINE)** | **CANONICAL** |
| 18 | `backend/` | Directory | ~1.5 MB | Legacy flat backend folder containing 120 original Python modules | LEGACY (REQUIRED_COMPATIBILITY) | PRESERVED |
| 19 | `config/` | Directory | ~15 KB | Runtime persistent JSON configuration: LLM usage, Approvals, Memory | SYSTEM | VERIFIED |
| 20 | `docs/` | Directory | ~250 KB | Technical architecture specifications, schemas, and design docs | DOCS_AND_REPORTS | VERIFIED |
| 21 | `frontend/` | Directory | 213.1 MB | Original physical frontend folder hosting the primary `node_modules` store | LEGACY_BUT_IN_USE | PRESERVED |
| 22 | `improvements/` | Directory | 74.3 MB | Detailed improvement plans (A0–A4, Phase 1–10) and implementation notes | DOCS_AND_REPORTS | VERIFIED |
| 23 | `models/` | Directory | 1.53 GB | Local Whisper ASR neural network weights (`faster-whisper-medium`) | USER_DATA / MEDIA | VERIFIED |
| 24 | `node_modules/` | Directory | 276 KB | Root Node dependencies (minimal tooling wrappers) | INFRASTRUCTURE | VERIFIED |
| 25 | `package.json` | File | 487 B | Root Node package manifest for workspace-level scripts | INFRASTRUCTURE | VERIFIED |
| 26 | `projects/` | Directory | 333 MB | User video project storage: audio, transcripts, scenes, artifacts | USER_DATA | PRESERVED |
| 27 | `remotion/` | Directory | 1.53 GB | Original physical Remotion folder hosting primary `node_modules` store | LEGACY_BUT_IN_USE | PRESERVED |
| 28 | `reports/` | Directory | 56.8 MB | Historical and active phase reports, test audits, and inventories | DOCS_AND_REPORTS | VERIFIED |
| 29 | `requirements.txt` | File | 1.05 KB | Python virtual environment package dependencies | INFRASTRUCTURE | VERIFIED |
| 30 | `resource-library/` | Directory | 1.65 MB | Font assets, licenses, motion graphic presets, audio sound effects | SHARED ASSETS | VERIFIED |
| 31 | `runproject.bat` | File | 1.95 KB | Windows batch launcher for standalone pipeline runs | SCRIPTS | VERIFIED |
| 32 | `scripts/` | Directory | 3.55 KB | Utility scripts (e.g. `set_laxman_pin.py`) | SCRIPTS | VERIFIED |
| 33 | `skills/` | Directory | 17.6 KB | Central skill Markdown instruction documents | SYSTEM | VERIFIED |
| 34 | `start.bat` | File | 179 B | Convenience Windows batch script to launch the application | SCRIPTS | VERIFIED |
| 35 | `tests/` | Directory | 9.69 MB | Centralized Python multi-suite test files and fixtures | TEST_SUITE | VERIFIED |

---

## 2. Summary by Classification

- **Canonical Architecture Roots (3):** `SYSTEM/`, `UI/`, `VIDEO_ENGINE/`
- **Legacy / Preserved Repositories (3):** `backend/`, `frontend/`, `remotion/`
- **Infrastructure & Environment (6):** `.venv/`, `node_modules/`, `package.json`, `requirements.txt`, `.env.example`, `.claude/`
- **User Data & Assets (4):** `projects/`, `models/`, `resource-library/`, `config/`
- **Documentation & Reports (12):** `docs/`, `reports/`, `improvements/`, and root Markdown/text files
- **Testing & Tooling (5):** `tests/`, `scripts/`, `start.bat`, `runproject.bat`, `.pytest_cache/`
| Total: 35 root items.
