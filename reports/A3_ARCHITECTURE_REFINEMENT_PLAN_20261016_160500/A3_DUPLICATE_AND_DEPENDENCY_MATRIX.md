# A3 — Duplicate & Dependency Audit Matrix

**Document ID:** A3-DUP-01  
**Date:** 2026-10-16 16:05:00 UTC  
**Repository:** `E:\audio-to-video`  
**Git Branch / HEAD:** `agents-building` / `f6989b17372e3cdb42b4c92ab1783b3122a401ae`  

---

## 1. Architectural Principles: Intentional Layers vs. Duplicate Systems

A common anti-pattern in architecture audits is mistaking **intentional compatibility layers** or **specialized complementary modules** for redundant duplication. In `E:\audio-to-video`, the core mission is to establish one authoritative canonical owner for each critical capability while safely preserving backward-compatibility adapters.

---

## 2. Capability Overlap & Canonical System Matrix

| Functional Capability | Current Implementations | Nature of Overlap | Canonical Implementation | Compatibility & Migration Guidance |
|---|---|---|---|---|
| **Pipeline Orchestration & Monitoring** | 1. `backend/orchestrator.py` (`PipelineOrchestrator`)<br>2. `backend/jobs.py` + `backend/pipeline.py` (`JobRunner`) | **Two execution engines.** `orchestrator.py` was built in Phase 8 as the canonical, state-aware, checkpoint-driven, event-emitting coordinator. `jobs.py` + `pipeline.py` is the earlier thread-pool runner serving legacy `/projects/{pid}/run`. | **`backend/orchestrator.py`** | Maintain `jobs.py` and `pipeline.py` as compatibility wrappers for legacy endpoints. Do not remove them until all frontend calls are fully migrated and tested against `/projects/{pid}/orchestrator/run`. |
| **Human & Governance Approval** | 1. `backend/approvals/approval_engine.py`<br>2. `backend/timeline_gate.py`<br>3. `backend/video_qc.py` | **Central governance vs Stage gates.** `approval_engine.py` (Phase A2) provides universal PIN authorization, single-use consumption, and audit trails. `timeline_gate.py` and `video_qc.py` are the stage-specific gates. | **`backend/approvals/approval_engine.py`** | Fully reconciled via A2 adapters (`timeline_adapter.py`, `qc_adapter.py`). Stage gates now sync through the canonical central engine. Zero duplication remains. |
| **Visual Planning** | 1. `backend/visual_planning.py`<br>2. `backend/visual_plan.py` | **Complementary artifacts (NOT duplicates).**<br>- `visual_planning.py` generates `visual_planning.json` (Claude semantic plan).<br>- `visual_plan.py` manages `visual_plan.json` (user-editable layout layer). | **Both are canonical for their respective artifacts.** | Keep both files. Clarify their distinct artifact ownership in documentation to avoid accidental deletion. |
| **Video Rendering** | 1. `backend/render_video.py`<br>2. `backend/render.py` | **Stage engine vs Low-level runner.**<br>- `render_video.py` enforces Stage 13 approval gates, generates reports, and manages manifests.<br>- `render.py` wraps Remotion CLI/Chromium subprocesses. | **Complementary layer.** `render_video.py` is the stage engine; `render.py` is the execution utility. | Both must be retained. `render_video.py` calls `render.py`. |
| **Agent Registry & Metadata** | 1. `backend/agents/registry.py`<br>2. `backend/pipeline_state.py` (Stage mapping) | **Registry vs Pipeline state constants.** `registry.py` is the authoritative 14-agent registry. `pipeline_state.py` maps active stage IDs to agent IDs. | **`backend/agents/registry.py`** | Keep `pipeline_state.py` as the state-machine constant module. Registry imports from or aligns with it. |
| **Skills Catalog & Staging** | 1. `backend/skill_registry.py`<br>2. `skills/catalog.json`<br>3. `skills/staging/` | **Single unified system.** Phase 4 established the central Skill Registry managing versioned packages and quarantined staging. | **`backend/skill_registry.py`** | Exactly one skill catalog exists (`skills/catalog.json`). No competing skill registries allowed. |
| **Shared Memory System** | 1. `backend/shared_memory.py`<br>2. `config/shared_memory.json` | **Single unified system.** Phase 4 established the centralized Shared Memory store with audit logging. | **`backend/shared_memory.py`** | Authoritative singleton. Used across all agents. |
| **LLM Gateway & Review** | 1. `backend/llm_gateway.py`<br>2. `backend/llm_review.py`<br>3. `backend/llm_client.py` | **Gateway vs Review vs Client.**<br>- `llm_gateway.py`: Canonical provider routing, fallback, and usage tracking.<br>- `llm_review.py`: Mandatory schema, prompt-injection, and quality review gates.<br>- `llm_client.py`: Low-level Anthropic SDK wrapper. | **`backend/llm_gateway.py`** | `llm_review.py` calls `llm_gateway.py`. All LLM calls route through the Gateway. Retain this layered design. |

---

## 3. Dependency & Package Manifest Audit

### 3.1 Python Dependencies (`pyproject.toml` & `requirements.txt`)
- Inspected `requirements.txt`:
  - `fastapi`, `uvicorn`, `pydantic`: Web framework and data contracts (Active).
  - `faster-whisper`: Frozen Stage 2 Whisper transcription (Active).
  - `anthropic`: Canonical LLM provider SDK (Active).
  - `pytest`, `pytest-asyncio`, `httpx`: Testing harnesses (Active).
  - `python-multipart`: Audio file upload handling in `routes/uploads.py` (Active).
- **Finding**: Zero unused or redundant Python dependencies were found in `requirements.txt`. All packages correspond to active pipeline stages or core platform services.

### 3.2 Frontend NPM Dependencies (`frontend/package.json`)
- Inspected `frontend/package.json`:
  - `react`, `react-dom`, `react-router`: Core SPA runtime (Active).
  - `@tanstack/react-query`: Data fetching and cache synchronization (Active).
  - `lucide-react`: UI iconography (Active).
  - `vitest`, `@testing-library/react`: Frontend unit/contract testing (Active).
  - `tailwindcss`, `vite`: Bundling and CSS styling (Active).
- **Finding**: All frontend dependencies are actively imported across `frontend/src/`. No orphaned libraries detected.

### 3.3 Remotion NPM Dependencies (`remotion/package.json`)
- Standalone package root configured for Remotion video bundling:
  - `remotion`, `@remotion/cli`, `@remotion/renderer`: Remotion animation engine and headless Chrome rendering (Active).
- **Finding**: Strictly scoped to video generation and headless rendering.

---

## 4. Convergence & Deprecation Roadmap

1. **Phase A3 (Current)**:
   - Formally document canonical ownership.
   - Do NOT delete compatibility wrappers (`jobs.py`, `pipeline.py`).
2. **Future Phase A4 (Shared Infrastructure Convergence)**:
   - Provide an optional backend flag `USE_CANONICAL_ORCHESTRATOR` to route legacy pipeline endpoints to `PipelineOrchestrator`.
   - Run end-to-end integration tests to verify complete parity before deprecating legacy execution loops.
3. **Future Phase A7 (Cleanup & Retirement)**:
   - Once all clients exclusively consume `/projects/{pid}/orchestrator/*`, safely retire the legacy `jobs.py` runner with full test verification.
