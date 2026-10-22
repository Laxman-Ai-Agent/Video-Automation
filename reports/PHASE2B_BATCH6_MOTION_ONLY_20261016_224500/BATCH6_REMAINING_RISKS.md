# Phase 2B — Batch 6: Remaining Risks and Mitigations

- **Date/Time**: 2026-10-16 22:45:00 UTC+5:30
- **Repository Root**: `E:\audio-to-video`
- **Scope**: Risk assessment following Batch 6 dead code removal, prior to Batch 7 root cleanup

---

## 1. Risk Assessment Matrix

| # | Risk Description | Severity | Likelihood | Impact Area | Mitigation Applied in Batch 6 | Status |
|---|---|---|---|---|---|---|
| 1 | Accidental removal of motion engine routing | **HIGH** | LOW | Motion Codegen | Identified that `motion_template_selection.py` is required by Stage 5; strictly preserved. | **RESOLVED** |
| 2 | Import errors in legacy pipeline steps | **MEDIUM** | LOW | Pipeline Runner | Wrapped calls in `legacy_pipeline_adapter.py` with safe deprecation messages instead of hard imports. | **RESOLVED** |
| 3 | Frontend type errors from stale interfaces | **LOW** | LOW | Frontend TypeScript | `npm run typecheck` verified with 0 errors. | **RESOLVED** |
| 4 | Test regression in historical milestone tests | **MEDIUM** | LOW | `tests/` directory | Preserved all historical test files without destructive editing; 12 core suites pass 100%. | **RESOLVED** |
| 5 | Frozen stage drift | **CRITICAL**| NONE | Core Stage Algorithms | Exact SHA-256 baseline matches maintained for all 3 frozen files. | **RESOLVED** |

---

## 2. Outstanding Pre-Batch 7 Risks

### 2.1 Backward-Compatibility Shims in `backend/`
- **Context**: 70+ identity shims currently reside in `backend/` pointing to `SYSTEM/`, `VIDEO_ENGINE/`, and `UI/backend/`.
- **Batch 7 Impact**: Batch 7 must determine whether to retain shims for non-migrated scripts or complete their relocation to canonical root paths.
- **Recommendation**: Maintain shims wherever third-party scripts, CLI tools, or tests reference `backend.<module>`.

### 2.2 Node Modules NTFS Junctions
- **Context**: `UI/frontend/node_modules` and `VIDEO_ENGINE/remotion/node_modules` use NTFS junction links pointing to root packages.
- **Batch 7 Impact**: Do not perform recursive deletions (`rm -rf`) on root `node_modules` without unlinking junctions, or Windows junctions may inadvertently cascade deletions.

### 2.3 Legacy Milestone Tests in `tests/`
- **Context**: Several files in `tests/` (e.g., `test_m5.py`, `test_m7.py`) test obsolete image slot filling.
- **Batch 7 Recommendation**: Migrate or quarantine outdated tests cleanly in Batch 7 as defined by the overall migration plan, with operator approval.
