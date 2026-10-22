# A0 Executive Summary — Architecture & Ownership Audit

**Audit Date:** 2026-10-16T14:15:00+05:30  
**Target Repository:** `E:\audio-to-video`  
**Current Branch / HEAD:** `agents-building` / `f6989b17372e3cdb42b4c92ab1783b3122a401ae`  
**Audit Mode:** Read-Only Static Architecture Inspection (zero file moves, zero code modifications, zero execution of frozen stages or pipelines)  
**Assigned Report Root:** `reports/A0_ARCHITECTURE_AUDIT_20261016_140500/`

---

## 1. Current Architecture in One Paragraph

The Dark World Video Generation Agent system is an autonomous, Motion-Only video generation platform converting Telugu audio narration into broadcast-ready 16:9 / 9:16 MP4 videos using Remotion and React/TSX animation code. The active pipeline executes a 12-stage sequential Directed Acyclic Graph (DAG) coordinated by a central orchestrator (`backend/orchestrator.py`), governed by Phase 3 artifact contracts and checkpoints (`backend/artifact_contracts.py`), Phase 2 LLM review gates (`backend/llm_review.py`), and independent human approval gates. The codebase comprises a Python 3.12 FastAPI backend (`backend/`), a Vite + React 19 frontend (`frontend/`), an independent Node.js Remotion composition engine (`remotion/`), a central Markdown-based skill catalog (`skills/`), a font/icon resource library (`resource-library/`), and per-project isolated runtime directories (`projects/<pid>/`).

---

## 2. Major Verified Components & Canonical Owners

| Component Layer | Primary Location | Canonical Owner / Module | Verification Status |
|---|---|---|---|
| **Agent Runtime & Registry** | `backend/agents/` | `backend/agents/registry.py` (singleton `AgentRegistry`) | `verified_in_current_source` |
| **Inter-Agent Communication** | `backend/agents/` | `backend/agents/communication.py` (`projects/<pid>/communications.jsonl`) | `verified_in_current_source` |
| **Canonical Orchestrator** | `backend/` | `backend/orchestrator.py` (`PipelineOrchestrator`) | `verified_in_current_source` |
| **Pipeline State & Checkpoints** | `backend/` | `backend/pipeline_state.py` & `backend/artifact_contracts.py` | `verified_in_current_source` |
| **LLM Gateway & Review Gates** | `backend/` | `backend/llm_gateway.py` & `backend/llm_review.py` | `verified_in_current_source` |
| **Skill Catalog & Governance** | `backend/`, `skills/` | `backend/skill_registry.py` (`skills/catalog.json`) | `verified_in_current_source` |
| **Shared Memory Service** | `backend/`, `config/` | `backend/shared_memory.py` (`config/shared_memory.json`) | `verified_in_current_source` |
| **Evaluation & Self-Learning** | `backend/`, `config/` | `backend/evaluation.py` (`config/eval_suites.json`) | `verified_in_current_source` |
| **Frozen Pipeline Stages** | `backend/` | `transcribe.py`, `transcript_review.py`, `scene_segmentation.py` | `verified_in_current_source` (Strictly Frozen) |
| **Motion & TSX Codegen** | `backend/` | `motion_animation.py`, `motion_planning.py`, `motion_validation.py` | `verified_in_current_source` |
| **Render & Media Verification** | `backend/`, `remotion/` | `render.py`, `render_video.py`, `media_probe.py`, `remotion/` | `verified_in_current_source` |
| **Resource Library** | `resource-library/` | `backend/resource_library.py` (`resource-library/catalog/registry.json`) | `verified_in_current_source` |
| **User Interface** | `frontend/` | React 19 / Vite single-page app (`frontend/src/`) | `verified_in_current_source` |

---

## 3. Key Findings

### Finding A0-F-001: Video Engine Agents vs. System Subagents Classification Gap
- **Status:** `verified_in_current_source`
- **Details:** `backend/agents/registry.py` currently contains a flat registry of 14 agents. It mixes the `main_orchestrator` with 13 stage-specific video adapters (`audio_input`, `audio_analyzer`, `scene_segmentation`, `visual_planning`, `motion_planning`, `motion_template_selection` [deprecated], `motion_animation`, `motion_timeline_validation`, `timeline_build`, `timeline_approval`, `render_video`, `final_qc`, `final_video_delivery`).
- **Gap:** The `AgentMetadata` dataclass lacks a `category` field (`video_engine_agent` vs `system_subagent` vs `orchestrator`). There are currently zero System Subagents (such as the planned Capability & Skill Finder Agent or Skill Factory Agent) registered in the codebase.
- **Recommendation for A1:** Add a strongly-typed `category` enum to `AgentMetadata` without altering existing agent IDs. Expose separate query parameters and UI sections for Video Engine Agents and System Subagents.

### Finding A0-F-002: Dual Pipeline Execution Pathways (Legacy JobRunner vs. Canonical Orchestrator)
- **Status:** `verified_in_current_source`
- **Details:** Two parallel execution engines coexist in `backend/`:
  1. The legacy step-graph runner: `backend/pipeline.py` + `backend/jobs.py` (`JobRunner`), which is currently called by stage routes (`/projects/{pid}/step/{name}/run`) and polled by the frontend (`/projects/{pid}/pipeline`).
  2. The canonical 12-stage DAG orchestrator: `backend/orchestrator.py` (`PipelineOrchestrator`) + `backend/agents/adapters/stage_adapters.py`, which supports Phase 3 checkpoints, bounded retries, and correlation IDs.
- **Impact:** Frontend stage pages currently trigger the legacy job runner directly, while the canonical orchestrator runs via `/projects/{pid}/orchestrator/run`.
- **Recommendation for A1:** Plan a phased convergence where the frontend routes route directly to the canonical Orchestrator while maintaining legacy route backward compatibility.

### Finding A0-F-003: Laxman Approval Readiness & Fragmentation
- **Status:** `verified_in_current_source`
- **Details:** Human approvals exist in the codebase but are fragmented across stage-specific files:
  1. Timeline Approval: `timeline_approval_history.json` (enforced before Remotion rendering in `backend/timeline_gate.py`).
  2. Final QC Playback Sign-off: `final_qc_review.json` (enforced before final delivery in `stage_adapters.py`).
  3. Evaluation Candidate Promotion: `config/eval_candidates.json` (enforced in `backend/evaluation.py`).
- **Gap:** There is **no central approval UI or engine named "Laxman Approval"**. There is no unified inbox, no common request schema (`request_id`, `requester`, `risk_level`, `action_fingerprint`, `reversibility`), and approvers are currently self-declared text strings without cryptographic authentication.
- **Recommendation for A1:** Define the architecture for a central **Laxman Approval Engine** and unified UI inbox in Phase A2, unifying all pipeline and system approval requests without building it prematurely in A0.

### Finding A0-F-004: Autonomous Skill Finder & Skill Factory Readiness
- **Status:** `partially_present`
- **Details:** Phase 4 built an authoritative central skill registry (`backend/skill_registry.py`), a persistent catalog (`skills/catalog.json`), lifecycle states (`quarantined -> draft -> review_required -> approved`), static security auditing (`audit_skill_content`), and a deterministic `resolve_skill_decision()` engine.
- **Gap:**
  - Neither `Capability & Skill Finder Agent` nor `Skill Factory Agent` exists in code.
  - Remote discovery connectors (GitHub, npm, PyPI) were intentionally deferred for security.
  - Automated skill synthesis, code generation, sandboxed test execution, and dedicated frontend UI are missing.
- **Recommendation for A1:** Design the Capability & Skill Finder and Skill Factory as genuine System Subagents that invoke the existing `SkillRegistry` and `EvaluationRegistry`, keeping them strictly off the sequential 12-stage video pipeline.

### Finding A0-F-005: Shared Staging Directory Mutex in Remotion
- **Status:** `verified_in_current_source`
- **Details:** While TSX generation is isolated per project in `projects/<pid>/generated_motion/`, Remotion compilation and rendering require staging into a shared directory `remotion/src/generated/`.
- **Risk:** Concurrency is protected via an in-process mutex (`_remotion_staging_lock` in `backend/motion_animation.py`), but multi-process or multi-worker deployments could experience race conditions if Remotion is scaled horizontally.
- **Recommendation for A1:** Retain the working mutex for single-instance operation and design dynamic composition entry points or isolated temporary remotion workspaces for future multi-instance scaling.

---

## 4. Proposed Target Architecture Focus for A1

1. **Preserve Stable Top-Level Roots:** Do **not** execute a mass physical refactoring into `SYSTEM/`, `UI/`, or `VIDEO_ENGINE/` root directories. The current top-level layout (`backend/`, `frontend/`, `remotion/`, `skills/`, `resource-library/`, `config/`, `projects/`, `tests/`, `docs/`) is well-understood, reliable, and deeply embedded across 121 passing tests.
2. **Logical Classification over Physical Relocation:** Introduce explicit logical taxonomy (`category` in Agent Registry, modular backend namespaces) rather than breaking imports.
3. **Dedicated System Subagents Layer:** Position future System Subagents (`skill_finder`, `skill_factory`) as on-demand background services managed by the Main Orchestrator, completely decoupled from the 12-stage sequential video pipeline.
4. **Central Laxman Approval Architecture:** Unify the 3 fragmented human approval gates (Timeline, QC Playback, Candidate Promotion) into a single central approval queue with an immutable audit log.

---

## 5. Safety Confirmation

- **ASR / Transcription executed:** No (0 Whisper calls).
- **Scene segmentation executed:** No.
- **Video pipeline / Remotion render executed:** No.
- **Files moved, edited, reformatted, or deleted:** No.
- **Dependencies installed or updated:** No.
- **Git operations performed:** 0 commits, 0 checkouts, 0 resets.
- **Frozen baseline integrity:** 100% SHA-256 match on `transcribe.py`, `transcript_review.py`, and `scene_segmentation.py`.
