# A3 — Open Decisions (Requiring User Input)

**Document ID:** A3-DEC-01  
**Date:** 2026-10-16 16:05:00 UTC  
**Repository:** `E:\audio-to-video`  
**Git Branch / HEAD:** `agents-building` / `f6989b17372e3cdb42b4c92ab1783b3122a401ae`  

---

## 1. Overview

To maintain strict alignment with user preferences, only genuinely unresolved architectural choices are presented below. No default assumptions have been made on these questions.

---

## 2. Decision Items

### Decision 1: Frontend Navigation Placement for Agents Overview
- **Context**: The proposed A3 plan specifies separating `Main Orchestrator`, `Video Engine Agents`, and `System Subagents` in the UI.
- **Options**:
  - **Option 1A (Dedicated Navigation Button)**: Add an `Agents` button (`<Bot size={18} /> Agents`) in the main header of `frontend/src/App.tsx` navigating to `/agents`. Keeps agents prominently accessible alongside `Dashboard`, `All Projects`, `Laxman Approval`, and `Resources`.
  - **Option 1B (Integrated Dashboard View)**: Render the categorized Agents view as a tab or expandable section inside the existing `DashboardPage` (`/dashboard`). Keeps the top navigation bar at 5 buttons.
- **Recommended**: **Option 1A**, as it mirrors the clean separation of `Laxman Approval` and provides direct, unhindered visibility into system subagents and orchestrator health.

---

### Decision 2: Legacy Execution Route Convergence Strategy
- **Context**: The repository currently contains both the canonical `PipelineOrchestrator` (`backend/orchestrator.py`) and the legacy `JobRunner` (`backend/jobs.py` / `pipeline.py`).
- **Options**:
  - **Option 2A (Gradual Forwarding Wrapper)**: Keep legacy `/projects/{pid}/run` endpoints permanently mapped, but internally wrap them to call `PipelineOrchestrator(pid).start_run()`. Never break older curl/script callers.
  - **Option 2B (Phased Deprecation & Eventual Removal)**: Deprecate `/projects/{pid}/run` in Phase A4, log deprecation notices, and remove `backend/jobs.py` / `backend/pipeline.py` in Phase A7 cleanup once all callers use `/orchestrator/run`.
- **Recommended**: **Option 2A** for Phase A3/A4, deferring physical removal decisions until all external workflows are verified.

---

### Decision 3: Untracked Cleanup Scope for Next Phase
- **Context**: Two untracked legacy directories totaling ~62 MB were identified:
  1. `.claude/worktrees/intelligent-hellman-80f23f/` (32.0 MB / 339 files from 2026-10-14).
  2. `out/` (30.1 MB / 5 standalone mp4 video renders from Oct 8–12).
- **Options**:
  - **Option 3A (Clean Both with External Backup)**: Create external backup archives in `E:\a2v_tmp\backups\` for both, verify integrity, and remove both paths to reclaim ~62 MB.
  - **Option 3B (Clean Worktrees Only)**: Back up and remove only `.claude/worktrees/`, keeping `out/` as historical reference media.
- **Recommended**: **Option 3A**, following the proven pattern established in Phase A2 for `dashboard/`.
