# Phase 2B — Batch 7: Compatibility Shim and Bridge Audit Report

- **Date/Time**: 2026-10-17 03:40:00 UTC+5:30
- **Repository Root**: `E:\audio-to-video`
- **Scope**: Documentation of compatibility shims, bridges removed, and bridges retained for supported workflows

---

## 1. Principles Governing Compatibility Shims

Per the Batch 7 charter:
> **"Do not remove a compatibility shim simply because its implementation is small or its path is old. If a bridge is still required by a documented launch command, tool, or supported integration, either update that entry point safely or retain the minimal bridge and document why it remains."**

In accordance with this rule:
1. Obsolete bridges pointing to deleted dead code were permanently removed.
2. Shims required by existing tests (`tests/test_*.py`), developer CLI tools (`python -m backend.cli`), or FastAPI legacy launch commands (`python -m backend.main`) were standardized as lightweight `sys.modules` identity delegates.
3. In-repository callers in `SYSTEM/`, `VIDEO_ENGINE/`, and `UI/` were updated to prioritize canonical imports first, falling back to shims only if necessary.

---

## 2. Removed Compatibility Bridges

The following bridges were permanently eliminated in Batches 6 and 7:

| Bridge Path | Former Target | Rationale for Permanent Deletion |
|---|---|---|
| `backend/image_gate.py` | `VIDEO_ENGINE.stages.image_gate` | Dead Image Mode requirement gate. |
| `VIDEO_ENGINE/stages/image_gate.py` | `backend.image_gate` | Dead Image Mode requirement gate duplicate. |
| `backend/bg_remove.py` | `VIDEO_ENGINE.stages.bg_remove` | Dead `rembg` background cutout utility. |
| `VIDEO_ENGINE/stages/bg_remove.py` | `backend.bg_remove` | Dead `rembg` background cutout utility duplicate. |
| `backend/fill_slots.py` | `VIDEO_ENGINE.stages.fill_slots` | Dead image slot filling module. |
| `VIDEO_ENGINE/stages/fill_slots.py` | `backend.fill_slots` | Dead image slot filling module duplicate. |
| `UI/backend/fill_slots.py` | `VIDEO_ENGINE.stages.fill_slots` | Temporary UI bridge created in Batch 5. |
| `backend/prompts_writer.py` | `VIDEO_ENGINE.stages.prompts_writer` | Dead image prompt formatter. |
| `VIDEO_ENGINE/stages/prompts_writer.py` | `backend.prompts_writer` | Dead image prompt formatter duplicate. |

---

## 3. Retained Compatibility Bridges (Documented Rationale)

The following bridge categories remain in `backend/` to guarantee zero disruptions to external callers, batch scripts, and historical test suites:

### 3.1 SYSTEM Infrastructure Bridges
- `backend/config.py` -> `SYSTEM.core.config`
  - *Rationale*: CLI scripts, historical tests, and tools import `from backend import config`. Standardized via `sys.modules[__name__] = _canonical`.
- `backend/llm_gateway.py` -> `SYSTEM.core.llm_gateway`
- `backend/pipeline_state.py` -> `SYSTEM.core.pipeline_state`
- `backend/artifact_contracts.py` -> `SYSTEM.core.artifact_contracts`
- `backend/errors.py` -> `SYSTEM.core.errors`
- `backend/checks.py` -> `SYSTEM.core.checks`
- `backend/contracts.py` -> `SYSTEM.core.contracts`
- `backend/cli.py` -> `SYSTEM.core.cli`
  - *Rationale*: Supports running developer commands via `python -m backend.cli`.
- `backend/llm_client.py` -> `SYSTEM.core.llm_client`
- `backend/shared_memory.py` -> `SYSTEM.memory.shared_memory`
- `backend/store.py` -> `SYSTEM.memory.store`
- `backend/skill_registry.py` -> `SYSTEM.registries.skill_registry`
- `backend/llm_review.py` -> `SYSTEM.policies.llm_review`
- `backend/evaluation.py` -> `SYSTEM.observability.evaluation`
- `backend/llm_usage.py` -> `SYSTEM.observability.llm_usage`
- `backend/diagnose.py` -> `SYSTEM.observability.diagnose`
- `backend/approvals/` -> `SYSTEM.approvals`

### 3.2 Autonomous Agent Bridges
- `backend/agents/` -> `SYSTEM.agents`
  - *Rationale*: Historical tests in `tests/` and legacy adapters test `backend.agents.contracts` and `backend.agents.registry`.

### 3.3 UI Backend & Presentation Bridges
- `backend/main.py` -> `UI.backend.main`
  - *Rationale*: Allows `python -m backend.main` or `uvicorn backend.main:app` to resolve to the canonical 139-endpoint FastAPI application.
- `backend/models.py` -> `UI.backend.models`
- `backend/api_models.py` -> `UI.backend.api_models`
- `backend/api_status.py` -> `UI.backend.api_status`
- `backend/pipeline_view.py` -> `UI.backend.pipeline_view`
- `backend/routes/` (15 routers) -> `UI.backend.routes.*`

### 3.4 VIDEO_ENGINE Execution Bridges
- `backend/orchestrator.py` -> `VIDEO_ENGINE.pipeline.orchestrator`
- `backend/jobs.py` -> `VIDEO_ENGINE.pipeline.jobs_adapter`
- `backend/pipeline.py` -> `VIDEO_ENGINE.pipeline.legacy_pipeline_adapter`
- `backend/motion_template_selection.py` -> `VIDEO_ENGINE.stages.motion_template_selection`
- `backend/<stage_name>.py` -> `VIDEO_ENGINE.stages.<stage_name>`
