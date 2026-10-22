# Phase 2B — Batch 5 Preflight: Frontend Baseline and Migration Readiness Report

- **Date/Time**: 2026-10-16 22:15:00 UTC+5:30
- **Repository Root**: `E:\audio-to-video`
- **Branch / HEAD**: `agents-building` / `f6989b17372e3cdb42b4c92ab1783b3122a401ae`
- **Scope**: Batch 5 Preflight Baseline Inspection of `frontend/` (Dependencies, Vitest, TypeScript, Oxlint)
- **Status**: PREFLIGHT COMPLETE — 250/268 TESTS PASSING (15/16 TEST FILES PASSING, 0 TS ERRORS)

---

## 1. Executive Summary

Prior to initiating **Batch 5: UI Backend Routes & UI Frontend Migration**, this preflight audit evaluated the existing `frontend/` application to record its package scripts, dependency status, compiler health, test suite baseline, and migration readiness.

**Key Findings:**
1. **Dependencies**: `frontend/node_modules/` is already fully installed and operational. Zero package installation (`npm install`) was performed.
2. **TypeScript Compilation**: `npm run typecheck` (`tsc --noEmit -p tsconfig.app.json`) exited with **code 0 and 0 errors**.
3. **Vitest Test Suite**: `npm test` (`vitest run`) ran 16 test files (268 total tests).
   - **15 of 16 test files PASSED completely** (250 tests passed).
   - **1 test file** (`tests/pipeline_ui.test.tsx`) had 18 failures out of 182 tests due to pre-existing MSW mock coverage gaps and header link additions from Phase 1.
   - Total execution duration: 187.55s.
   - Exit code: 1.
4. **Linter Baseline (`oxlint`)**: Found 1 error (`react-hooks/rules-of-hooks` in `src/pipeline/useAutoAdvance.ts:21` where `useQueryClient` was placed in a try-catch) and 7 warnings.
5. **Preservation**: No application code, UI routes, or configurations were modified during this preflight. No media rendering, ASR, or live pipeline runs were executed.

---

## 2. Package Scripts and Dependency Inspection

### A. Documented Package Scripts (`frontend/package.json`)
```json
"scripts": {
  "dev": "vite",
  "build": "tsc -b && vite build",
  "lint": "oxlint",
  "preview": "vite preview",
  "typecheck": "tsc --noEmit -p tsconfig.app.json",
  "test": "vitest run",
  "test:watch": "vitest",
  "openapi:snapshot": "..\\.venv\\Scripts\\python.exe scripts/dump_openapi.py"
}
```

### B. Dependency State
- **Directory**: `frontend/node_modules` exists and is populated.
- **Key Frameworks**: React 19.2.8, React Router 8.4.0, Vite 8.3.0, Vitest 5.0.3, TanStack Query 5.104.1, TailwindCSS 4.3.3, Framer Motion 14.0.0, Lucide React 1.53.0.
- **Testing Libraries**: `@testing-library/react` 16.3.3, `@testing-library/jest-dom` 7.0.1, `msw` 2.15.0, `jsdom` 30.1.2.

---

## 3. Vitest Baseline Test Execution Results

**Executed Command**:
```powershell
npm test
```
(Working Directory: `E:\audio-to-video\frontend`, executing `vitest run`)

### Suite Breakdown (16 Test Files, 268 Tests Total)

| Test File | Tests | Passed | Failed | Status | Notes |
|---|---|---|---|---|---|
| `tests/pipeline_llm_badge.test.tsx` | 5 | 5 | 0 | **PASS** | Dashboard LLM status badges on cards |
| `tests/json_page.test.tsx` | 1 | 1 | 0 | **PASS** | Run LLM button & JSON inspect |
| `tests/stage_about.test.tsx` | 4 | 4 | 0 | **PASS** | Stage about modal & navigation |
| `tests/stage_failure_alert.test.tsx` | 2 | 2 | 0 | **PASS** | Auto-fix alert & button states |
| `tests/llm_usage_card.test.tsx` | 3 | 3 | 0 | **PASS** | INR/USD token metrics & tables |
| `tests/llm_usage_page.test.tsx` | 4 | 4 | 0 | **PASS** | Live usage polling & currency setting |
| `tests/laxman_approval_page.test.tsx` | 8 | 8 | 0 | **PASS** | Approval queue, PIN modal, reason gating |
| `tests/timeline_lanes.test.ts` | 4 | 4 | 0 | **PASS** | Lane calculation math |
| `tests/client.test.ts` | 15 | 15 | 0 | **PASS** | API client routes & query builders |
| `tests/autoadvance.test.tsx` | 4 | 4 | 0 | **PASS** | State propagation in auto-advance |
| `tests/contract.test.ts` | 12 | 12 | 0 | **PASS** | OpenAPI schemas and TypeScript types |
| `tests/agents_page.test.tsx` | 6 | 6 | 0 | **PASS** | Agent cards, category filters, drawers |
| `tests/resources.test.tsx` | 4 | 4 | 0 | **PASS** | Resource catalog & search filters |
| `tests/projects.test.tsx` | 6 | 6 | 0 | **PASS** | Project list, deletion, rename dialogs |
| `tests/auto_advance.test.tsx` | 8 | 8 | 0 | **PASS** | useAutoAdvance hook integration |
| `tests/pipeline_ui.test.tsx` | 182 | 164 | 18 | **FAIL (18)** | Pre-existing MSW gaps & header link diffs |
| **TOTAL** | **268** | **250** | **18** | **93.3% PASS** | **Exit Code: 1, Duration: 187.55s** |

### Failure Root-Cause Analysis (`tests/pipeline_ui.test.tsx`)
1. **Header Link Count Assertion** (`header > has the logo, Dashboard, New Project, All Projects and Resources (and nothing else)`):
   - The test asserts exactly 4 navigation links exist in `<header>`.
   - In earlier Phase 1 work, navigation items for `Agents`, `Approvals` (Laxman), and `LLM Usage` were added to `src/App.tsx`, causing this strict count assertion to fail.
2. **Missing MSW Interceptors for Newly Added Endpoints**:
   - `GET /api/projects/p9/monitor`
   - `GET /api/projects/p1/analysis`
   - `GET /api/projects/p1/motion-planning`
   - `POST /api/projects/p1/motion-generation/run`
   - `GET /api/projects/p1/motion-timeline-validation`
   When `pipeline_ui.test.tsx` mounts pages making these requests, MSW reports unhandled requests and queries time out (`waitForWrapper` after 5000-9000ms).

---

## 4. TypeScript & Linter Health Check

### A. TypeScript Typecheck
```powershell
npm run typecheck
```
- **Exit Code**: `0`
- **Output**: Clean (0 type errors). All 82 source files typecheck cleanly against `tsconfig.app.json`.

### B. Oxlint Linter
```powershell
npm run lint
```
- **Exit Code**: `1`
- **Errors**: 1
  - `src/pipeline/useAutoAdvance.ts:21`: `react-hooks/rules-of-hooks` — `useQueryClient` is called inside a `try/catch` block.
- **Warnings**: 7 (synchronous `setState` inside `useEffect` in `LlmSettingsModal.tsx`, `StageAboutModal.tsx`, `AgentCommunicationDrawer.tsx`; missing dependency in `useAutoAdvance.ts`; audio ref access during render in `TimelineParts.tsx`).

---

## 5. Batch 5 Migration Scope & Mapping Reference

Per `reports/PHASE2_STRUCTURE_MAPPING_20261016_200500/PHASE2_FILE_MAPPING.md`, Batch 5 entails relocating:

1. **Frontend App (`frontend/` -> `UI/frontend/`)**:
   - 82 React/TypeScript source files (`src/`, `public/`, `scripts/`, `tests/`)
   - Config files: `package.json`, `tsconfig*.json`, `vite.config.ts`, `.oxlintrc.json`, `.gitignore`
   - Dependencies: `node_modules` (NTFS junction or direct move)
2. **UI Backend Routes (`backend/` -> `UI/backend/`)**:
   - `backend/main.py`
   - `backend/models.py`, `backend/api_models.py`, `backend/api_status.py`
   - `backend/pipeline_view.py`
   - `backend/routes/` (`projects.py`, `pipeline.py`, `uploads.py`, `results.py`, `llm.py`, `agents.py`, `approvals.py`, `skills.py`, `memory.py`, `evaluation.py`, `orchestrator.py`)
   - Compatibility shims maintained at `backend/` for any legacy callers.

---

## 6. Preflight Checklist and Stop Gate

- [x] Package scripts and installed dependencies identified.
- [x] Full Vitest test suite executed and documented (250 passed, 18 failed in 1 suite, duration 187.55s).
- [x] TypeScript typecheck executed (0 errors).
- [x] Git status verified and unchanged (`git status --short`).
- [x] Zero application or test files modified.
- [x] Zero media rendering, ASR, or live pipeline runs executed.
- [x] Report authored and ready for review.

**Stop Condition Met**: Standing by for operator instruction before initiating Batch 5.
