# Visual Planning redesign: status and pending work (2026-10-23)

This file records the state of the Visual Planning redesign and what is still open.

## What was built
| Area | What | Where |
|---|---|---|
| Media registry | The ONE definition of what a scene element can be: families motion / image / video, kinds text, label, icon, graphic, diagram, chart, data_visualization, background, image, video, reference. Every video is 100% motion graphics with real pictures/clips drawn inside it in any amount (no shares); the only per-project choice is the AI-pictures flag, chosen at upload and locked. | `SYSTEM/core/media_kinds.py`, `SYSTEM/memory/store.py` (`create(media=...)`, `media()`) |
| Visual Planning (rewritten) | One planner call + one repair retry, nothing derived when it fails. Per scene: `hero`, `counts`, elements, `media_requirements`; plan: `media_mix` (what it carries, information only), `totals`. `max_texts` per scene pattern is told to the planner and checked. | `VIDEO_ENGINE/stages/visual_planning.py`, `visual_planning_rules.py`, `autoplan.py`, `SYSTEM/agents/video_generation_agents/visual_planning/agent.py` |
| Asset Collection | Requirements are written from the Visual Plan (no planner of its own). `reference` -> Wikipedia infobox/table screenshot. Keyless providers: Openverse (photos), Internet Archive (videos), plus Wikimedia/NASA; Pexels/Pixabay only with keys. Search cache key includes the available providers. | `VIDEO_ENGINE/stages/asset_collection.py`, `stock.py`, `web_capture.py` |
| Downstream | Motion Planning resolves real elements (collected file or the plan's motion fallback); Motion Generation draws collected files and the fallback otherwise; validation treats a plan without Scene Segmentation as stated. | `motion_scenes.py`, `motion_planning.py`, `motion_animation.py`, `motion_validation_rules.py` |
| API | Upload takes `media_motion`, `media_image`, `media_video`, `ai_images`; `GET /projects/{pid}/assets`, `GET /projects/{pid}/assets/file/{name}`. | `UI/backend/routes/projects.py`, `routes/assets.py`, `api_models.py` |
| UI | Media-mix picker on New Project; Visual Planning scene table (text/icons/graphics/images/videos/pages per scene, chosen vs reached mix); "Collected Media" tab on Asset Collection. | `UI/frontend/src/components/{MediaMixPicker,VisualPlanningView,AssetsView}.tsx`, `services/mediaMix.ts`, `StageDrawer.tsx`, `AudioInputPage.tsx` |
| Tests | New: `test_media_kinds.py` (fails when a kind has no handler), `test_visual_planning.py` (rewritten), `test_assets_api.py`; adapted: asset, stock, motion, autoplan, validation, render fixtures. | `tests/` |

## Verified with real runs
- Stages 1-5 on the user's audio: plan errors 0, mix 59/25/16 (then a 60/30/10 target; the shares were removed afterwards); Motion Planning completed on that plan.
- Wikipedia infobox capture (344x999 PNG), photos from Wikimedia and Openverse (CC0 / CC BY), a clip request that honestly fell back.
- Related tests: about 190 pass. Full suite on the first run: 1172 pass; failures left are old ones (below).

## Pending
1. **Run the whole pipeline** (stages 6-13) on a project that has a real photo, a reference page and a video, to prove the scenes draw `real_media` of kinds photo / video / page. Only stages 1-6 were exercised for real.
2. **Re-run the full Python suite** once: the last full run was before the `reference` kind and the keyless providers.
3. **Restart the backend on :8000** (it still runs the old code). Vite on :5173 reloads by itself.
4. Committed and pushed to `origin main` (922f0a4).
5. Optional: Pexels/Pixabay keys (`PEXELS_API_KEY`, `PIXABAY_API_KEY` in `.env`) for better video B-roll; keyless sources have few office/people clips.
6. AI pictures: only the ready prompt (`media.ai_prompt`) is written; no image generator is connected.
7. Frontend has no unit tests in this copy (no vitest script); only `npx tsc --noEmit` was run. Docs besides `CLAUDE.md` (`docs/architecture.md`, `schemas.md`) were not updated. The old visual_planning agent skills and memory files were left as they were.
8. **Fix the 7 failing tests that are not from this work** (a separate task): `tests/test_scene_segmentation.py` 4 tests (job step labels: they expect ('transcribe','refine','cuts') but get ('audio','analyzer'), and one hits KeyError 'scenes'); `test_phase9_e2e_integration.py::TestLiveRemotionRenderAndMediaProbe` (live Remotion render, fails on a clean HEAD export); two stale human-approval expectations: `test_motion_only_mode.py::test_timeline_is_built_approved_and_rendered_without_pictures` (expects `waiting_for_approval`, approval is LLM-decided now) and `test_render_video.py::test_the_final_render_step_runs_the_stage_for_motion_only_projects` (expects the words "playback decision is pending"). Decide for each: update the test to the current rule, or fix the code if the test is right.

## Failing tests that are not from this work
- `tests/test_scene_segmentation.py`: 4 tests (they fail on HEAD too).
- `tests/test_phase9_e2e_integration.py::TestLiveRemotionRenderAndMediaProbe` (fails on a clean HEAD export).
- Old human-approval expectations: `test_motion_only_mode.py::test_timeline_is_built_approved_and_rendered_without_pictures` (expects `waiting_for_approval`) and `test_render_video.py::test_the_final_render_step_runs_the_stage_for_motion_only_projects` (expects "playback decision is pending"); approval is LLM-decided now.

## Notes
- `E:\audio-to-video` is abandoned by the user's decision; do not use it.
- Old projects in `projects/` were removed by the user; `projects/` is empty.
