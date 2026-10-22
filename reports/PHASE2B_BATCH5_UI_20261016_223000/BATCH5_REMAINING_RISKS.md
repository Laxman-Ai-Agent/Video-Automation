# Phase 2B — Batch 5: Remaining Risks and Technical Debt Report

- **Date/Time**: 2026-10-16 22:30:00 UTC+5:30
- **Repository Root**: `E:\audio-to-video`
- **Branch / HEAD**: `agents-building` / `f6989b17372e3cdb42b4c92ab1783b3122a401ae`
- **Scope**: Risk Analysis for Batch 6 (Motion-Only Dead Code Removal) and Batch 7 (Root Cleanup)
- **Status**: ALL BATCH 5 RISKS MITIGATED; REMAINING TASKS SCOPED

---

## 1. Resolved Batch 5 Risks

| Risk Area | Mitigation Implemented | Validation |
|---|---|---|
| **Circular Imports in UI Backend** | Implemented PEP 562 dynamic delegation in `UI/backend/__init__.py`. | Both `UI.backend.main` and `backend.main` load cleanly with 0 circular imports. |
| **Node Modules Duplication** | Created NTFS Directory Junction (`UI\frontend\node_modules` -> `frontend\node_modules`). | Native package resolution, 0 bytes duplicated. |
| **Frontend Path Breakages** | Reconciled relative script paths in `package.json` and `dump_openapi.py`. | Vitest and TypeScript compilation passed cleanly. |
| **Backward Compatibility for Legacy Routes** | Installed `sys.modules` identity shims in all 15 files under `backend/routes/`. | 46/46 route unit tests passed with 100%. |
| **Frozen File Hash Invalidation** | Untouched baseline files verified before and after migration. | 100% SHA-256 match confirmed. |

---

## 2. Scoped Technical Debt for Batch 6 (Motion-Only Dead Code Removal)

1. **Obsolete Image Mode Modules**:
   - The repository still contains 5 dead image mode modules:
     1. `backend/image_gate.py` / `VIDEO_ENGINE/stages/image_gate.py`
     2. `backend/bg_remove.py` / `VIDEO_ENGINE/stages/bg_remove.py`
     3. `backend/fill_slots.py` / `VIDEO_ENGINE/stages/fill_slots.py`
     4. `backend/prompts_writer.py` / `VIDEO_ENGINE/stages/prompts_writer.py`
     5. `backend/motion_template_selection.py` / `VIDEO_ENGINE/stages/motion_template_selection.py`
   - *Plan for Batch 6*: Perform clean deletion of these 5 dead files and eliminate their legacy imports across stages and routes.

2. **Frontend Obsolete Route Cleanup**:
   - `frontend/src/pages/MotionTemplateSelectionPage.tsx` was already deleted in earlier partial work, but references in router tables or imports must be verified.

---

## 3. Scoped Technical Debt for Batch 7 (Root Cleanup and Directory Finalization)

1. **Root Legacy Directory Retirement**:
   - Root `frontend/` and root `remotion/` currently host the physical `node_modules/` targeted by the junctions in `UI/frontend/` and `VIDEO_ENGINE/remotion/`.
   - *Plan for Batch 7*: Move the physical `node_modules` cleanly into canonical folders before unlinking/retiring root directories.
2. **Root Import References in Tests**:
   - Update any remaining `tests/` imports referencing `backend.` to use `SYSTEM.`, `VIDEO_ENGINE.`, or `UI.backend.` as appropriate.
