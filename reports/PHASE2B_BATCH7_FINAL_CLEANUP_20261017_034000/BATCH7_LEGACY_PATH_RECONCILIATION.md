# Phase 2B — Batch 7: Legacy Path Reconciliation Table

- **Date/Time**: 2026-10-17 03:40:00 UTC+5:30
- **Repository Root**: `E:\audio-to-video`
- **Scope**: File-by-file reconciliation of legacy paths, compatibility bridges, and physical storage

---

## 1. Reconciliation Table

| Legacy Path | Canonical Target Path | Status in Batch 7 | Action Taken | Rationale & Evidence |
|---|---|---|---|---|
| `backend/config.py` | `SYSTEM/core/config.py` | **MIGRATED & BRIDGED** | Created canonical module; bridged legacy path | Canonical config in `SYSTEM.core.config`; bridge retained for legacy CLI scripts. |
| `backend/checks.py` | `SYSTEM/core/checks.py` | **MIGRATED & BRIDGED** | Created canonical module; bridged legacy path | Quality checks migrated to `SYSTEM.core.checks`; bridge retained for compatibility. |
| `backend/cli.py` | `SYSTEM/core/cli.py` | **MIGRATED & BRIDGED** | Created canonical module; bridged legacy path | Developer CLI moved to `SYSTEM.core.cli`; `python -m backend.cli` supported via bridge. |
| `backend/contracts.py` | `SYSTEM/core/contracts.py` | **MIGRATED & BRIDGED** | Created canonical module; bridged legacy path | Sidecar pydantic contract models moved to `SYSTEM.core.contracts`. |
| `backend/diagnose.py` | `SYSTEM/observability/diagnose.py` | **MIGRATED & BRIDGED** | Created canonical module; bridged legacy path | Diagnostic reporter moved to `SYSTEM.observability.diagnose`. |
| `backend/llm_client.py` | `SYSTEM/core/llm_client.py` | **MIGRATED & BRIDGED** | Created canonical module; bridged legacy path | LLM API client moved to `SYSTEM.core.llm_client`; bridge retained for existing tools. |
| `backend/motion_template_selection.py` | `VIDEO_ENGINE/stages/motion_template_selection.py` | **MIGRATED & BRIDGED** | Updated stage with full code; bridged legacy path | Real 324-line Stage 5 selection moved to `VIDEO_ENGINE/stages/`; legacy bridge created. |
| `skills/` | `SYSTEM/skills/` | **MIGRATED & MIRRORED** | Mirrored catalog and skills to `SYSTEM/skills/` | Skill catalog lives canonically in `SYSTEM/skills/`; root `skills/` preserved for test fixtures. |
| `backend/image_gate.py` | None | **DELETED** | Removed in Batch 6 | Dead Image Mode requirement gate. Verified 0 remaining imports. |
| `backend/bg_remove.py` | None | **DELETED** | Removed in Batch 6 | Dead raster image cutout code (`rembg`). Verified 0 remaining imports. |
| `backend/fill_slots.py` | None | **DELETED** | Removed in Batch 6 | Dead image slot filling code. Verified 0 remaining imports. |
| `backend/prompts_writer.py` | None | **DELETED** | Removed in Batch 6 | Dead text prompt generator for image models. Verified 0 remaining imports. |
| `UI/backend/fill_slots.py` | None | **DELETED** | Removed in Batch 6 | Temporary bridge removed. |
| `frontend/node_modules` | `UI/frontend/node_modules` | **RETAINED VIA JUNCTION** | Verified junction link | NTFS junction `UI/frontend/node_modules -> frontend/node_modules` verified functional (0 TS errors). |
| `remotion/node_modules` | `VIDEO_ENGINE/remotion/node_modules` | **RETAINED VIA JUNCTION** | Verified junction link | NTFS junction `VIDEO_ENGINE/remotion/node_modules -> remotion/node_modules` verified functional (0 TS errors). |
| `frontend/` (tracked git files) | `UI/frontend/` | **RETAINED IN GIT** | Tracked files preserved | `frontend/src/`, `frontend/tests/` tracked in git; preserved to avoid destructive `git clean/reset`. |
| `remotion/` (tracked git files) | `VIDEO_ENGINE/remotion/` | **RETAINED IN GIT** | Tracked files preserved | `remotion/src/` tracked in git; preserved to avoid destructive `git clean/reset`. |

---

## 2. Directory Disposition Summary

- **`SYSTEM/`**: Fully active, authoritative home for system infrastructure, 14 agents, registries, and shared services.
- **`UI/`**: Fully active, authoritative home for `UI/frontend/` and `UI/backend/`.
- **`VIDEO_ENGINE/`**: Fully active, authoritative home for execution pipeline, stages, Remotion, and FFmpeg.
- **`backend/`**: Retained strictly as a lightweight backward-compatibility facade containing `sys.modules` identity shims for older development commands and un-migrated test scripts.
- **`frontend/` & `remotion/`**: Retained as physical storage for `node_modules` and git-tracked files, preventing data loss or package reinstallation on Windows.
