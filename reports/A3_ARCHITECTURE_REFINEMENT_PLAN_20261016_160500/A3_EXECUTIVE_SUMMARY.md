# A3 — Executive Summary: Architecture Refinement & Cleanup Plan

**Document ID:** A3-EXEC-01  
**Date:** 2026-10-16 16:05:00 UTC  
**Repository:** `E:\audio-to-video`  
**Git Branch / HEAD:** `agents-building` / `f6989b17372e3cdb42b4c92ab1783b3122a401ae`  
**Authorization State:** **A3 PLANNING ONLY** (Zero source code changed, zero files deleted, zero tests executed).

---

## 1. Context & Purpose

Following the successful completion and security review of **Phase A2 (Central Laxman Approval System)**, Phase A3 establishes an evidence-based, low-risk plan to refine system architecture and prepare cleanup candidates without disrupting working video-production capabilities.

The core objectives of Phase A3 Planning are:
1. **Preserve Established Physical Package Roots**: Keep `backend/`, `frontend/`, `remotion/`, `skills/`, `resource-library/`, `config/`, and `projects/` intact. Avoid mass-relocation into newly invented root directories (`SYSTEM/`, `UI/`, `VIDEO_ENGINE/`).
2. **Clarify Logical Agent Ownership**: Classify all 14 registered agents into three unambiguous logical categories (`orchestrator`, `video_engine_agent`, `system_subagent`) without mutating existing stable agent IDs.
3. **Plan Clean UI & Registry Separation**: Separate active 12-stage Video Engine Agents from cross-project System Subagents (planned for Phases A5/A6) and the Main Orchestrator.
4. **Distinguish Canonical Implementations from Compatibility Layers**: Map duplicate or overlapping execution paths (e.g. `PipelineOrchestrator` vs `JobRunner` / `pipeline.py`), confirming canonical owners while preserving backward compatibility.
5. **Inventory Cleanup Candidates**: Rigorously analyze untracked and legacy files (`.claude/worktrees/`, `out/`, `STATUS.json`), classifying them as `KEEP`, `REMOVE_CANDIDATE`, `REFACTOR_CANDIDATE`, or `PROTECTED`.
6. **Ensure Zero Disruptions During Planning**: Strictly adhere to non-negotiables: no source file edits, no deletions, no dependency changes, no test execution, no video rendering, and no destructive Git commands.

---

## 2. Key Architectural Findings & Recommendations

### 2.1 Physical Roots vs. Logical Classification
- **Finding**: The repository's build system (Vite, TypeScript `tsconfig.app.json`, Remotion bundling, Uvicorn/FastAPI imports) is deeply coupled to current root directories. Moving code to new root directories would invalidate path aliases, break external scripts, and produce severe regression risks with zero runtime advantage.
- **Recommendation**: Maintain current physical directory roots. Enforce separation logically through metadata properties, clear module boundaries, and UI grouping.

### 2.2 Agent Registry Enhancement
- **Finding**: `backend/agents/registry.py` registers 14 agents:
  - 1 coordinator: `main_orchestrator`
  - 12 active video pipeline agents: `audio_input`, `audio_analyzer`, `scene_segmentation`, `visual_planning`, `motion_planning`, `motion_animation`, `motion_timeline_validation`, `timeline_build`, `timeline_approval`, `render_video`, `final_qc`, `final_video_delivery`
  - 1 deprecated adapter: `motion_template_selection` (`status=AgentStatus.DEPRECATED`)
  - 0 System Subagents currently exist in code. Capability & Skill Finder and Skill Factory are planned for Phases A5 and A6.
- **Recommendation**: Add `category: AgentCategory = AgentCategory.VIDEO_ENGINE_AGENT` to `AgentMetadata` (`contracts.py`), classifying `main_orchestrator` as `orchestrator`, the 12 active stages + 1 deprecated as `video_engine_agent`, and future background subagents as `system_subagent`. Preserve all 14 agent IDs and stage IDs intact.

### 2.3 UI & Navigation Plan
- **Finding**: The frontend currently renders the 12 active pipeline stages on a 2-row canvas (`PipelineChart.tsx`). Agents are only directly queried in `AgentCommunicationDrawer.tsx`. There is no dedicated agent overview page.
- **Recommendation**: Introduce a dedicated Agents view (or tab within the dashboard) displaying:
  1. **Video Engine Agents**: The 12 active pipeline stages with capabilities, status, and frozen badges.
  2. **System Subagents**: Cross-project capabilities (Skill Finder, Skill Factory) clearly flagged as planned/on-demand, not sequential pipeline steps.
  3. **Main Orchestrator**: Coordinator overview with health status and run telemetry.
  - The existing `Laxman Approval` navigation button remains separate and distinct.

### 2.4 Cleanup Candidate Audit
- **`dashboard/`**: Confirmed **REMOVED** during Phase A2 following verified external backup at `E:\a2v_tmp\backups\dashboard_backup_20261016_150000.zip`. Re-verified that `dashboard/` does not exist on disk.
- **`.claude/worktrees/intelligent-hellman-80f23f/`** (32.0 MB / 339 files): Untracked legacy worktree from 2026-10-14. Classified as **`REMOVE_CANDIDATE`** for future authorized cleanup.
- **`out/`** (~30 MB / 5 mp4 files): Untracked legacy standalone renders from early October. Zero code references in `backend/`. Classified as **`REMOVE_CANDIDATE`** for future authorized cleanup.
- **`STATUS.json` & `STATUS.md`**: Tracked in Git, but loaded directly by `tests/test_status.py`. Classified as **`REFACTOR_CANDIDATE`** (requires test decoupling before removal).
- **`models/hf/`** (~1.5 GB Whisper weights) & **`projects/`** (user project artifacts): Strictly **`PROTECTED`**.

### 2.5 Duplicate & Overlapping Systems
- **Orchestration**: `backend/orchestrator.py` (`PipelineOrchestrator`) is the canonical Phase 8 orchestrator. `backend/jobs.py` and `backend/pipeline.py` (`JobRunner`) serve legacy `/projects/{pid}/run` endpoints. Maintain both during gradual migration; do not delete legacy endpoints prematurely.
- **Visual Planning**: `visual_planning.py` (Claude semantic plan) and `visual_plan.py` (user-editable layout layer) serve complementary roles for different artifacts (`visual_planning.json` vs `visual_plan.json`). Both must be kept.
- **Video Rendering**: `render_video.py` (Stage 13 verification and reporting) wraps and reuses `render.py` (low-level Remotion runner). Both must be kept.

---

## 3. Plan Deliverables Summary

The complete A3 planning package comprises 12 interconnected reports in `reports/A3_ARCHITECTURE_REFINEMENT_PLAN_20261016_160500/`:
1. `A3_EXECUTIVE_SUMMARY.md` (This document)
2. `A3_CURRENT_STATE_RECONCILIATION.md`
3. `A3_AGENT_OWNERSHIP_MATRIX.md`
4. `A3_UI_AND_REGISTRY_PLAN.md`
5. `A3_PHYSICAL_AND_LOGICAL_BOUNDARIES.md`
6. `A3_CLEANUP_CANDIDATES.md`
7. `A3_DUPLICATE_AND_DEPENDENCY_MATRIX.md`
8. `A3_IMPLEMENTATION_SEQUENCE.md`
9. `A3_TEST_VALIDATION_MATRIX.md`
10. `A3_RISK_AND_ROLLBACK.md`
11. `A3_OPEN_DECISIONS.md`
12. `A3_COMPLETION_REPORT.md`

---

## 4. Execution Statement

> **A3 planning completed; no source files changed and no files deleted. Awaiting user review and explicit approval before implementation.**
