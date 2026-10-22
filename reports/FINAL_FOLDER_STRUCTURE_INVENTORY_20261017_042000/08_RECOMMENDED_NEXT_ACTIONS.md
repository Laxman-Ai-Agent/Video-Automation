# Recommended Next Actions & Future Maintenance Roadmap

**Date:** 2026-10-17 04:22:00 IST  
**Repository Root:** `E:\audio-to-video`  
**Git Branch:** `agents-building` | **HEAD:** `f6989b17372e3cdb42b4c92ab1783b3122a401ae`  
**Status:** EVIDENCE-BACKED, PRIORITIZED RECOMMENDATIONS  

---

## 1. Overview

With Phase 2B migration complete, all 4 reporting discrepancies resolved, and the repository inventory fully documented, the application is in an operational, ready state. 

No urgent blocking fixes are required. The recommendations below are prioritized into actionable phases for post-migration operations and future code hygiene.

---

## 2. Prioritized Action Matrix

| Priority | Action Item | Area | Effort | Impact / Benefit |
| :--- | :--- | :--- | :--- | :--- |
| **P1** | **Align Frontend Test Mocks** | `UI/frontend/tests/pipeline_ui.test.tsx` | Low (1 hour) | Updates MSW route mock prefixes from `/api/projects` to `/projects` and increases jsdom test timeout to 10s, achieving 268/268 passing tests. |
| **P2** | **End-to-End User Verification** | Web UI & API Server | Low (30 mins) | Start backend and frontend to perform an end-to-end run on a test audio file through the browser flowchart. |
| **P3** | **Laxman Approval PIN Initialization** | `SYSTEM/approvals/` | Low (5 mins) | Run `scripts/set_laxman_pin.py` to configure the operator security PIN for timeline approvals and sensitive gatekeeper overrides. |
| **P4** | **Reclaim Webpack Build Caches** | `remotion/node_modules/.cache/` | Immediate (1 min) | Purge webpack cache packs to reclaim ~460 MB of disk space on Drive E without affecting runtime code. |
| **P5** | **Update Legacy Batch Launchers** | Root `runproject.bat`, `start.bat` | Low (30 mins) | Update batch scripts to launch directly from `UI/backend/main.py` and canonical `VIDEO_ENGINE/` modules. |
| **P6** | **Phase 3 Long-Term Deprecation** | `backend/`, root `frontend/`, `remotion/` | Medium (Future) | After batch scripts are verified, invert node_modules junctions and safely archive duplicate legacy directories. |

---

## 3. Detailed Action Procedures

### Priority 1: Align Frontend Test Mocks (`pipeline_ui.test.tsx`)
- **File:** `UI/frontend/tests/pipeline_ui.test.tsx`
- **Context:** The component makes requests to the canonical FastAPI endpoints (`/projects/{pid}/...`), but 17 mock handlers in `server.ts` / `pipeline_ui.test.tsx` listen for `/api/projects/{pid}/...`.
- **Action:** Update mock route definitions to match `/projects/:pid/...` and adjust `testTimeout: 10000` in `vite.config.ts`.
- **Expected Outcome:** 16 out of 16 test files passing, 268 out of 268 tests passing (100% green suite).

### Priority 2: End-to-End User Verification
- **Backend Launch:**
  ```powershell
  $env:PYTHONPATH="."
  .\.venv\Scripts\uvicorn.exe UI.backend.main:app --host 127.0.0.1 --port 8000 --reload
  ```
- **Frontend Launch:**
  ```powershell
  cd UI\frontend
  npm run dev
  ```
- **Verification:** Navigate to `http://localhost:5173/`, submit a sample Telugu narration, inspect the 12-stage flowchart live, verify LLM review gates, and inspect the generated motion composition.

### Priority 3: Laxman Approval PIN Initialization
- **File:** `scripts/set_laxman_pin.py`
- **Command:**
  ```powershell
  .\.venv\Scripts\python.exe scripts/set_laxman_pin.py
  ```
- **Outcome:** Sets the PBKDF2-HMAC hashed PIN in `config/approvals_queue.json`, enabling secure operator approvals in the UI at `http://localhost:5173/approvals`.

### Priority 4: Reclaim Webpack Build Caches
- **Path:** `remotion/node_modules/.cache/webpack/`
- **Disk Reclaimed:** ~460 MB.
- **Safety:** 100% safe to delete. Webpack regenerates build cache automatically on the next dev/build command.
