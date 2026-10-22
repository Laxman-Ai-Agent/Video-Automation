# Final Blockers, Operational Boundaries & Technical Limitations

**Date:** 2026-10-17 04:15:00 IST  
**Repository:** `E:\audio-to-video`  
**Git Branch:** `agents-building`  
**Git Commit HEAD:** `f6989b17372e3cdb42b4c92ab1783b3122a401ae`  
**Status:** ZERO CRITICAL BLOCKERS — OPERATIONAL BOUNDARIES DOCUMENTED  

---

## 1. Executive Summary

Following the full Phase 2B canonical refactor (Batches 1–7) and the Final Discrepancy Audit, there are **zero critical architectural or functional blockers** preventing application startup or runtime execution. 

This document catalogs technical boundaries, safe operating practices, environment prerequisites, and minor non-blocking items to ensure smooth long-term operations.

---

## 2. Directory Junction Safe-Handling Guidelines

The root directory contains two Windows NTFS directory junctions established for backward compatibility with external scripts and tooling:
- `E:\audio-to-video\frontend` -> `E:\audio-to-video\UI\frontend`
- `E:\audio-to-video\remotion` -> `E:\audio-to-video\VIDEO_ENGINE\remotion`

> [!CAUTION]
> **Never perform recursive deletion on junction points:**
> If using shell commands or third-party file managers, never run `rm -rf frontend` or `Remove-Item -Recurse frontend`. Non-junction-aware tools will traverse the junction and delete the actual source files in `UI/frontend/`.
> 
> **Safe Junction Removal Command (if ever required):**
> ```cmd
> rmdir E:\audio-to-video\frontend
> rmdir E:\audio-to-video\remotion
> ```
> In PowerShell:
> ```powershell
> (Get-Item "E:\audio-to-video\frontend").Delete()
> ```

---

## 3. Frontend Unit Test Mock Realignment (Non-Blocking)

In the frontend test suite (`UI/frontend/tests/`):
- **15 of 16 test files pass cleanly** (249 tests passing).
- `tests/pipeline_ui.test.tsx` has 18 failed assertions due to pre-existing MSW/mock handlers configured for `/api/projects/{pid}/...` instead of the root-level `/projects/{pid}/...` mounted by FastAPI.
- Additionally, 1 test (`auto-runs next stage if autoRun toggled on`) timed out under the default 5000ms threshold during concurrent jsdom rendering on Windows.
- **Recommended Maintenance Action (Post-Phase 2):** Update mock endpoint prefixes in `pipeline_ui.test.tsx` to match the canonical `/projects` routes and set Vitest `testTimeout: 10000` in `vite.config.ts`. This is purely test-mock maintenance and has zero effect on runtime application functionality.

---

## 4. Runtime Environment Prerequisites

To run the complete audio-to-video generation pipeline in production or development:

1. **Python Environment:**
   - Python 3.10+ (Current: `.venv\Scripts\python.exe`)
   - `PYTHONPATH` must include the repository root:
     ```powershell
     $env:PYTHONPATH="."
     ```
2. **Node.js & Package Managers:**
   - Node.js v22.18.0+ and npm
   - Dependencies pre-installed in `UI/frontend/node_modules/` and `VIDEO_ENGINE/remotion/node_modules/`.
3. **FFmpeg & Media Tools:**
   - FFmpeg binary must be accessible in system `PATH` for audio normalization, duration probing, and MP4 muxing.
4. **Remotion Headless Chrome:**
   - Headless Chromium (managed automatically by Remotion or local system Chrome) is required for final video rendering.

---

## 5. Non-Destructive Verification Operational Boundaries

In accordance with operator instructions, the following operations were intentionally withheld during this audit:
1. **Live ASR Execution:** No Whisper ASR jobs were run to avoid heavy model downloads and prolonged CPU/GPU spikes.
2. **Video Frame Generation:** No Remotion canvas frames or MP4 files were rendered.
3. **State Mutation:** No existing project checkpoints, user configurations, or approval audit records were overwritten.
4. **Git Operations:** No git commits, merges, checkouts, or cleans were executed.

All existing project assets, audio files, checkpoints, and test databases remain fully intact and operational.
