# Pipeline UI + Image Generation gate: implementation status (saved 2026-10-12)

Plan: `Video_Generation_Agent_Complete_Phasewise_Plan/`. Branch `improvement/audio-visual`. This file is the log of what is done, what is verified and what is open.
Nothing here is claimed done unless a command was run this session (results at the bottom).

## Phase checklist
All phases DONE except the live browser / render checks listed in `PROJECT_STATUS.md` (that file has the current table, decisions and test results; this file is the log of changes).

## What exists now (backend, all additive)
- `GET /projects/{id}/pipeline`: stage list (audio, analyzer, planning, collection, images, timeline, approval, render, qc). `percent` is only set where the pipeline reports one; otherwise null.
- `GET /images`, `POST /images/match` (Set All Images to Prompt), `POST /images/{slot}/upload`, `POST /images/collect`, `POST /images/{slot}/use-asset`, `POST /continue`, `POST /pipeline/advance`.
- `GET|POST|DELETE /timeline/approval|approve`, `POST /render`.
- Rules proven by tests: Continue 409 while any required image is missing or needs review; an upload for one slot changes only that slot; a second "Set All Images" keeps manual assignments; ambiguous matches stay `review`; approval never starts a job; approval goes stale when the timeline changes; `/render` needs the current approval AND every image; a repeated Continue / Render returns the same job; state survives a restart (derived from files).
- Stock results keep source, author, licence and attribution (`candidates.json`, `credits.json`); unclear rights are `commercial_use_known = null`; downloads only from https provider hosts, only images.

## Edits inside YOUR modified files (left uncommitted on purpose)
- Backend: `backend/main.py` (router include), `backend/routes/review.py` and `backend/routes/run.py` (final-render approval guard).
- Frontend: `src/api/client.ts` (routes + methods), `src/App.tsx` (2 routes), `src/ui/StudioLayout.tsx` (Live Pipeline link, `/p/:id` match), `src/features/upload/useSubmitAnalysis.ts` (navigate to `/p/:id`), `tests/upload.test.tsx`, `tests/contract.test.ts`, `tests/fixtures/openapi.json` (regenerated; old copy in `reports/openapi.snapshot.before.json`).
- Remotion: `src/components/Effect.tsx` (checkmark uses the GSAP timeline).
- `.env.example` (+`PIXABAY_API_KEY`), `CLAUDE.md` (stock providers rule).
New files of mine are committed; these edits are not, because the files also hold your own uncommitted work.

## Decisions
1. API change is additive (new router file + include line); one behaviour change: final renders need an approved timeline (preview does not).
2. Image workflow is manual upload (no image-generation API); `Regenerate Prompt` is the existing prompt regeneration.
3. Providers use only the standard library; keys by name only (`PEXELS_API_KEY`, `PIXABAY_API_KEY`); missing key = "unavailable".
4. Old pages stay (nothing deleted); the new Pipeline page becomes the landing page.
5. I did not open the reference image (project rule: Claude does not view images); the written spec drives the layout.

## Test results
See `PROJECT_STATUS.md`. Latest full backend run (after the render-port fix): 410 passed, 0 failed.

## Motion library: flag and preview (2026-10-12)
- Flag: `A2V_MOTION=1` when the composition is built (build_composition.ts / API process env); off = unchanged output. Renderer needs nothing.
- Preview clips (13 s, real narration, new motion library on): `projects/_motion_preview/preview/motion_preview_16_9.mp4`, `projects/_motion_preview/preview/motion_preview_9_16.mp4`.
- Checked: non-blank, moves every 0.1 s in the entrance, audio length and lag 0.00 s, Telugu text inside the safe area (text alone). Details: `PROJECT_STATUS.md`.
- Remaining: visual quality not judged by eye (needs the user); no full-size render with the flag; the clips use 2 of 41 text presets; the Telugu check has no pictures or decor behind the text.

## Use Images, Motion-Only mode, flowchart (2026-10-13)
- Per-project `use_images` toggle (Audio Input), enforced by the server (chains, gates, image endpoints); `A2V_MOTION_SPEED` pace; two-branch animated flowchart with a page per node; motion branch (Motion Planning / Motion Generation) runs in both modes and both branches must finish before the Timeline Build.
- Tests: backend full run 427 passed + 2 fixed after it; frontend 294 passed. Preview videos: `projects/_motiononly_preview/preview/motion_only_16_9.mp4`, `motion_only_9_16.mp4`. Details and caveats: `PROJECT_STATUS.md`, `docs/motion.md`.

## Audio Analyzer 14 stages (2026-10-13)
Files: `backend/transcript_review.py` (new: vocabulary, confidence, checked Claude corrections, forced re-alignment + audio-energy check), `backend/audio_analysis.py` (14 stages, audio-analysis-2), `backend/transcribe.py` (Word.p/timing/edit, `load_transcript` order, `transcript_inputs`), `backend/pipeline.py` (step `refine`, chain, fingerprints), `backend/pipeline_view.py`, `backend/review.py`, `backend/autoplan.py`, `backend/routes/projects.py` (`GET /analysis`), `remotion/scripts/build_composition.ts` (reads `transcript_corrected.json`), `frontend/src/pipeline/analyzerSteps.ts`, `frontend/src/pages/AnalyzerPage.tsx`, `frontend/src/pages/JsonPage.tsx`, tests (test_transcript_review.py, test_audio_analysis.py, pipeline_ui.test.tsx). Details and open risks: `PROJECT_STATUS.md`, section "Audio Analyzer: 14 stages".
