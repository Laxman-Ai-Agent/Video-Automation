# Final implementation report: Pipeline UI + Image Generation gate (2026-10-12)

Status table, decisions and test results: `PROJECT_STATUS.md`. Change log and the list of edits inside the user's own files: `reports/IMPLEMENTATION_STATUS.md`.

## 1. Phase completion
Phases 0-10 DONE; not verified: a browser walk-through (the running API has the old code), a real Remotion render of the changed checkmark effect, the Playwright E2E and live provider calls.

## 2. Files changed and why
- New backend: `image_gate.py` (requirements, counts, blockers, per-slot upload), `stock.py` (four providers, rights metadata, credits), `timeline_gate.py` (approval per timeline version, final-render guard), `pipeline_view.py` (stage list), `routes/pipeline.py` (endpoints).
- New frontend: `src/features/pipeline/{types.ts, hooks.ts, StageCard.tsx, PipelinePage.tsx, ImageGenerationPage.tsx, ImageRequirementCard.tsx}`.
- New Remotion: `src/gsapTimeline.ts`, `src/components/checkmarkTimeline.ts`, `scripts/gsap_determinism.ts`.
- New tests: `tests/test_pipeline_gate.py` (13), `tests/test_stock.py` (8), `tests/test_gsap_adapter.py` (1), `frontend/tests/pipeline_page.test.tsx` (9).
- Edited (user's files, uncommitted): listed in `reports/IMPLEMENTATION_STATUS.md`.
- Note: `pipeline_view.py` imports `backend/video_qc.py`, which is an untracked file of the user (it exists in the working tree; a clean checkout of my commits alone would not have it).

## 3. Reused versus added
Reused: matcher + `apply_fix` (assignments), review gates, `jobs.start` (one job per project), the build chains, `promptgen` (Regenerate Prompt), upload validation (`receive`, `check_ext`), `CopyButton`, `ConfirmDialog`, `Button`, `Notice`, react-query polling, `MotionConfig`. Added: only what is listed in section 2. No new agent, renderer or pipeline.

## 4. Packages
None installed. `gsap 3.15` (remotion) and `framer-motion 14` (frontend) were already present and unused; both are now used. `motion` is not installed and not needed (framer-motion is the same library).

## 5. Environment variable names
`PEXELS_API_KEY`, `PIXABAY_API_KEY` (optional), `WHISPER_MODEL`. NASA Images and Wikimedia Commons need no key.

## 6. Commands run and results
`pytest --ignore=tests/test_playwright_e2e.py`: 391 passed, 0 failed (final run; the 2 test_m7 review-gate tests asserted `waiting_for == "review"` / "review needed", which the current gate no longer produces, so they now assert the current behaviour: unclear matches are held back at Continue). `vitest run`: 272 passed. frontend `tsc` and `vite build`: pass. remotion `tsc` and `tsx scripts/gsap_determinism.ts`: pass. Baseline before the work: 365 passed, 4 failed.

## 7. Limitations and manual steps
- Restart the API (`runproject.bat`) so the new routes load; then open `/p/<id>` and `/p/<id>/images`.
- Opening the Pipeline page of a project whose plan is ready approves its analysis gate once (this starts the prompt writer), by design.
- Stock rights: `commercial_use_known` is null when unclear (NASA); the user must check the licence before using such a result.
- Final renders are refused with 409 until the timeline is approved (`/render`, `/run final`, `/submit` without preview).
- `playwright==1.63.0` was added to `requirements.txt` (already installed in `.venv`; known failing test KF-3 now passes).
