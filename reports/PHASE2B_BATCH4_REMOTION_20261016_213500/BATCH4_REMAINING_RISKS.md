# Phase 2B — Batch 4: Remaining Risks and Technical Debt Report

- **Date/Time**: 2026-10-16 21:35:00 UTC+5:30
- **Repository Root**: `E:\audio-to-video`
- **Branch / HEAD**: `agents-building` / `f6989b17372e3cdb42b4c92ab1783b3122a401ae`
- **Scope**: Batch 4 Risk Analysis for Subsequent Batches (Batch 5 UI, Batch 6 Dead Code, Batch 7 Root Cleanup)
- **Status**: ALL BATCH 4 RISKS MITIGATED; REMAINING RISKS IDENTIFIED AND SCOPED

---

## 1. Batch 4 Resolved Risks

| Identified Risk | Mitigation Implemented | Validation |
|---|---|---|
| **Relative Import Drift in Remotion** | TypeScript import of `render_bundle.json` adjusted from 3 to 4 directory levels. | `npx tsc --noEmit` returns code 0. |
| **Node Modules Disk Duplication** | Created NTFS Directory Junction instead of running `npm install`. | 0 MB disk growth, native module resolution. |
| **Python Path Resolution Divergence** | Added `REMOTION_DIR` and `FFMPEG_DIR` in `backend/config.py` with fallback. | Validated in `render.py`, `orchestrator.py`, and `legacy_pipeline_adapter.py`. |
| **Media Probe Import Breakage** | Created backward compatibility shim at `backend/media_probe.py` using `sys.modules`. | Unit assertion confirms exact object identity. |
| **Frozen File Hash Invalidation** | Relocated files byte-for-byte; verified SHA-256 baseline before and after. | Exact 100% hash match verified. |

---

## 2. Remaining Risks for Batch 5 (UI Backend and Frontend Migration)

1. **Frontend Vite Asset Resolution**:
   - The Vite frontend (`frontend/`) contains proxy rules, mock servers, and static asset routes.
   - When UI backend routes and frontend files are migrated to `UI/`, proxy configurations in `frontend/vite.config.ts` must maintain accurate endpoints pointing to the FastAPI backend.
   - *Mitigation Plan*: Update and test frontend TypeScript contracts and mock servers prior to any file movement.

2. **UI Route Namespace Consistency**:
   - The FastAPI application in `backend/main.py` mounts `/projects`, `/pipeline`, `/api/agents`, `/api/approvals`, etc.
   - In Batch 5, UI-specific routes will migrate to `UI/backend/routes/`.
   - *Mitigation Plan*: Use the established `sys.modules` shimming pattern to ensure seamless backward compatibility.

---

## 3. Remaining Risks for Batch 6 (Dead Image Mode Code Removal)

1. **Hidden Imports of Dead Modules**:
   - Five obsolete image mode modules remain in `backend/` and `VIDEO_ENGINE/stages/`: `image_gate.py`, `bg_remove.py`, `fill_slots.py`, `prompts_writer.py`, and `motion_template_selection.py`.
   - In Batch 6, these will be removed cleanly.
   - *Mitigation Plan*: Conduct an exhaustive codebase grep across all remaining callers and tests to ensure no lingering imports remain before deletion.

---

## 4. Remaining Risks for Batch 7 (Root Cleanup and Directory Finalization)

1. **Root Remotion Directory Deletion**:
   - The root `remotion/` directory currently hosts the physical `node_modules/` targeted by the `VIDEO_ENGINE/remotion/node_modules` junction.
   - *Mitigation Plan*: In Batch 7, when root cleanup is performed, the physical `node_modules` can be moved cleanly into `VIDEO_ENGINE/remotion/` before unlinking the root `remotion/` folder.
