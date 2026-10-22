# A3 — Implementation Sequence Plan (For Future Authorization)

**Document ID:** A3-SEQ-01  
**Date:** 2026-10-16 16:05:00 UTC  
**Repository:** `E:\audio-to-video`  
**Git Branch / HEAD:** `agents-building` / `f6989b17372e3cdb42b4c92ab1783b3122a401ae`  
**Execution Status:** **PLANNING ONLY. NO CHANGES TO BE EXECUTED DURING A3.**

---

## 1. Sequence Design Principles

When implementation is explicitly approved by the user, changes must be applied in small, reviewable, dependency-ordered batches. Each batch is isolated, test-verified, and reversible:

- **Batch 1**: Backend Data Contract & Registry Categorization (Zero breaking changes, backward-compatible default).
- **Batch 2**: Frontend Contract Update & Type Safety (`frontend/src/api/agentTypes.ts`).
- **Batch 3**: Frontend UI Agent Separation (Rendering distinct groups for Orchestrator, Video Engine Agents, and System Subagents).
- **Batch 4**: Cleanup Step 1 — Untracked Ephemeral Cleanup (`.claude/worktrees/`, `out/`).
- **Batch 5**: Cleanup Step 2 — Decouple & Refactor Legacy Status Files (`STATUS.json` & `STATUS.md`).

---

## 2. Step-by-Step Batch Specifications

### Batch 1: Backend Agent Contracts & Registry Categorization
- **Objective**: Add `AgentCategory` enum and classify all 14 existing agents in the backend registry.
- **Files to Modify**:
  1. `backend/agents/contracts.py`:
     - Define `AgentCategory(str, Enum)` with values `"orchestrator"`, `"video_engine_agent"`, `"system_subagent"`.
     - Add `category: AgentCategory = AgentCategory.VIDEO_ENGINE_AGENT` to `AgentMetadata`.
     - Update `AgentMetadata.to_dict()` to serialize `category`.
  2. `backend/agents/registry.py`:
     - In `_init_defaults()`, explicitly pass `category=AgentCategory.ORCHESTRATOR` for `main_orchestrator`.
     - Ensure `motion_template_selection` retains `status=AgentStatus.DEPRECATED`.
- **Pre-Conditions**: Git status clean of untracked changes in `backend/agents/`.
- **Acceptance Verification**:
  - Run `pytest -v tests/test_agent_routes.py tests/test_agent_runtime_and_communication.py`.
  - Assert that `GET /agents` returns 14 agents with valid `"category"` attributes and existing agent IDs unchanged.
- **Rollback**: Revert `contracts.py` and `registry.py` edits.

---

### Batch 2: Frontend Contract & Typecheck Synchronization
- **Objective**: Synchronize frontend TypeScript contracts with backend category metadata.
- **Files to Modify**:
  1. `frontend/src/api/agentTypes.ts`:
     - Add `export type AgentCategory = "orchestrator" | "video_engine_agent" | "system_subagent"`.
     - Add `category: AgentCategory` to `AgentMetadata`.
  2. `frontend/src/components/AgentCommunicationDrawer.tsx`:
     - Optionally group or display the category badge in the agent filter dropdown.
- **Pre-Conditions**: Batch 1 completed and verified.
- **Acceptance Verification**:
  - Run `npm --prefix frontend run typecheck` (must pass with 0 errors).
  - Run `npm --prefix frontend test -- tests/client.test.ts`.
- **Rollback**: Revert TypeScript interface additions.

---

### Batch 3: Dedicated UI Agent Separation Display
- **Objective**: Provide an operator view visually separating Video Engine Agents, System Subagents, and the Main Orchestrator.
- **Files to Modify**:
  1. `frontend/src/pages/AgentsPage.tsx` (New file) or enhance `PipelinePage.tsx` / `DashboardPage`:
     - Render Main Orchestrator card at top.
     - Render 12 Video Engine Agents in a responsive grid with status, capabilities, and frozen indicators.
     - Render System Subagents (Capability & Skill Finder, Skill Factory) in a separate section with `PLANNED` badges.
  2. `frontend/src/App.tsx`:
     - Wire navigation and route if standalone page is chosen.
     - Ensure `Laxman Approval` button and existing routes remain untouched.
- **Pre-Conditions**: Batch 2 completed.
- **Acceptance Verification**:
  - Run `npm --prefix frontend run typecheck`.
  - Write and execute component unit tests in `frontend/tests/agents_page.test.tsx` verifying category grouping and empty/error states.
- **Rollback**: Remove `AgentsPage.tsx` and revert route in `App.tsx`.

---

### Batch 4: Cleanup Step 1 — Untracked Legacy File Removal
- **Objective**: Reclaim ~62 MB of untracked obsolete disk space.
- **Paths to Target**:
  1. `.claude/worktrees/intelligent-hellman-80f23f/` (32.0 MB / 339 files).
  2. `out/` (30.1 MB / 5 mp4 files).
- **Pre-Removal Protocol**:
  1. Create external zip backup: `E:\a2v_tmp\backups\a3_cleanup_step1_backup_<timestamp>.zip`.
  2. Verify zip integrity with `zipfile.testzip()`.
  3. Remove only the exact target paths.
- **Acceptance Verification**:
  - Verify `Test-Path .claude/worktrees/intelligent-hellman-80f23f` returns `False`.
  - Verify `Test-Path out` returns `False`.
  - Run `pytest -q tests/test_timeline_render_qc_delivery.py`.
- **Rollback**: Extract backup zip back to repository root.

---

### Batch 5: Cleanup Step 2 — Decouple & Refactor Legacy Status Files
- **Objective**: Clean obsolete static root files (`STATUS.json` & `STATUS.md`).
- **Files to Modify**:
  1. `tests/test_status.py`:
     - Refactor assertions to query `backend/agents/registry.py` and `pipeline_state.py` rather than reading static root JSON.
  2. Remove or archive `STATUS.json` and `STATUS.md` to `docs/archive/`.
- **Acceptance Verification**:
  - Run `pytest -v tests/test_status.py`.
  - Full pytest regression suite across all tests.
- **Rollback**: `git checkout HEAD -- STATUS.json STATUS.md tests/test_status.py`.

---

## 3. Strict Boundary Reminder

**Do not execute any of the above batches during A3.** Execution is blocked pending user review and explicit authorization.
