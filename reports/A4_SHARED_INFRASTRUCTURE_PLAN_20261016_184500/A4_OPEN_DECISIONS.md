# A4 Open Decisions and Recommendations for Operator

**Date:** October 16, 2026  
**Repository:** `E:\audio-to-video`  
**Phase:** A4 — Shared Infrastructure Integration Planning  
**Status:** OPEN DECISIONS FOR OPERATOR REVIEW  

---

## 1. Overview

During A4 planning, all structural facts and code realities were reconciled against actual source files. To prepare for the subsequent implementation phase, the following **three genuine architectural decisions** are submitted for explicit operator direction.

---

## 2. Open Decision Items

### Decision 1: Feature-Gated vs Direct Wrapper Convergence for Legacy Routes

- **Context:** `backend/routes/pipeline.py` currently executes steps via `jobs.start()`, whereas the canonical engine is `PipelineOrchestrator`.
- **Option 1A (Recommended): Feature-Gated Wrapper with Instant Fallback**
  - Implement wrapper delegation in `backend/routes/pipeline.py` gated by `config.improve("orchestrator_wrapper")` (environment variable `A2V_ORCHESTRATOR_WRAPPER=1`, default `True`).
  - *Pros:* Zero risk; allows immediate runtime fallback to `jobs.start()` without code deployment if an edge case arises.
  - *Cons:* Maintains a temporary dual branch in the route wrapper.
- **Option 1B: Direct Permanent Replacement**
  - Replace `jobs.start()` invocations in `/motion/run`, `/timeline-build/run`, and `/final-qc/run` directly with `PipelineOrchestrator.start_run()`.
  - *Pros:* Cleanest codebase; eliminates legacy branch immediately.
  - *Cons:* Requires a code change/revert if unforeseen legacy test expectations fail.
- **Recommendation:** **Option 1A** for Phase A4 implementation.

---

### Decision 2: State Synchronization Model for `info.json`

- **Context:** Existing frontend headers and project list views read `projects/{pid}/info.json` to display project status (`"idle"`, `"building"`, `"ready"`, `"error"`). Canonical stage state is stored in `projects/{pid}/.pipeline_state.json`.
- **Option 2A (Recommended): Synchronous State Mirroring**
  - Whenever `pipeline_state.py` transitions a stage, it automatically syncs high-level status to `info.json["status"]`.
  - *Pros:* Existing lightweight UI polling components continue working without modifying frontend polling loops.
  - *Cons:* Two files touched on state change (mitigated by unified lock).
- **Option 2B: Strict Decoupling**
  - `info.json` stores only static project metadata (`name`, `aspect`, `use_images`, `created_at`). All status polling must query `/orchestrator/status`.
  - *Pros:* Strict single-file state on disk.
  - *Cons:* Requires updating frontend project cards and list polling logic.
- **Recommendation:** **Option 2A** for Phase A4 implementation.

---

### Decision 3: Image Mode (Use Images = ON) Scope Boundary

- **Context:** The production target is the **Motion-Only Video Generation Pipeline** (custom React/TSX Remotion animations without stock pictures). However, legacy routes retain support for `use_images = True` (`promptgen`, stock picture matching, image cropping).
- **Option 3A (Recommended): Preserve Image Mode Exclusively in Legacy Adapter**
  - Keep `PipelineOrchestrator` strictly focused on the 12-stage Motion-Only pipeline dependency graph. Route image-mode actions through legacy `jobs.py`.
  - *Pros:* Keeps canonical orchestrator minimal, hardened, and free of obsolete image-cropping logic.
  - *Cons:* Legacy image mode does not benefit from Phase 3 checkpoint recovery.
- **Option 3B: Expand Orchestrator Dependency Graph for Image Branches**
  - Add optional branches (`promptgen`, `image_match`, `crop`) into `PipelineOrchestrator.STAGE_DEPENDENCIES`.
  - *Pros:* Single engine for both modes.
  - *Cons:* Significantly increases orchestrator complexity for a secondary mode slated for deprecation.
- **Recommendation:** **Option 3A**.
