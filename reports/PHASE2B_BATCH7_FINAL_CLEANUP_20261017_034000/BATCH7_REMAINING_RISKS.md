# Phase 2B — Batch 7: Remaining Risks and Mitigations Report

- **Date/Time**: 2026-10-17 03:40:00 UTC+5:30
- **Repository Root**: `E:\audio-to-video`
- **Scope**: Final risk analysis, limitations, and operational runbook guidance

---

## 1. Risk Analysis Matrix

| # | Risk / Operational Area | Severity | Likelihood | Impact Area | Mitigation & Architecture Guarantee | Status |
|---|---|---|---|---|---|---|
| 1 | File locks on physical `node_modules` during Windows directory moves | **MEDIUM** | HIGH | Frontend / Remotion | Preserved `node_modules` in physical locations with verified NTFS junction links. Avoided risky file move. | **RESOLVED & SAFE** |
| 2 | Legacy tests referencing `backend.*` imports | **LOW** | LOW | Historical test suites | Maintained thin `sys.modules` identity shims in `backend/` ensuring all tests pass seamlessly. | **RESOLVED & SAFE** |
| 3 | Circular dependency between UI routers and SYSTEM memory | **MEDIUM** | LOW | FastAPI startup | Dynamic attribute delegation (`__getattr__` PEP 562) prevents circular references during import time. | **RESOLVED & SAFE** |
| 4 | Accidental deletion of Git-tracked files in `frontend/` or `remotion/` | **HIGH** | NONE | Repository integrity | Strict prohibition of `git clean` or recursive folder deletion. Tracked files remain intact. | **RESOLVED & SAFE** |
| 5 | Frozen algorithm drift in stage transcribe/review/segmentation | **CRITICAL**| NONE | Audio & Scene stages | Zero drift maintained; SHA-256 hashes verified 100% byte-for-byte identical. | **RESOLVED & SAFE** |

---

## 2. Operational Limitations & Runbook Guidance

1. **Junction Preservation**:
   - `UI/frontend/node_modules` and `VIDEO_ENGINE/remotion/node_modules` are NTFS junctions.
   - Do NOT run recursive folder deletion (`rmdir /s /q` or `rm -rf`) directly on `UI/frontend/node_modules` or `VIDEO_ENGINE/remotion/node_modules`, as Windows command prompts may delete the target contents.
   - To unlink a junction in Windows, use `cmd /c rmdir <junction_path>` without `/s`.

2. **Python Environment**:
   - Always run Python commands with `$env:PYTHONPATH="."` using the virtual environment `.venv\Scripts\python.exe`.

3. **FastAPI Server Launch**:
   - Canonical launch command:
     ```powershell
     $env:PYTHONPATH="."; .venv\Scripts\python.exe -m uvicorn UI.backend.main:app --host 0.0.0.0 --port 8000 --reload
     ```
   - Legacy launch command (`python -m backend.main`) continues to work via the backward-compatibility bridge.
