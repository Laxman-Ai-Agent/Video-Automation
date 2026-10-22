# Scene Segmentation: audit and decisions (2026-10-13)

Roadmap: `improvements/Scene_Segmentation_Complete_Roadmap`. Written before the implementation, kept short.

## What existed
- Audio Analyzer output: `transcript.json` / `transcript_corrected.json` (words with start/end, `timing`, `edit`), `audio_analysis.json` (utterances, words, measured pauses, stages), `cuts.json` (candidate cut points).
- Scene splitting was done INSIDE Visual Planning: `backend/autoplan.py` asks Claude to merge the cut points of `cuts.json` into scenes (`plan_input.txt`), checked by `backend/plan_checks.py` (scene length 2-20 s, boundaries should be cut points).
- Consumers of the scenes: `scene_plan.json` (Visual Planning), `prompts_map.json`, motion branch, composition.
- LLM client: `promptgen.run_claude` (Claude CLI, no API key, JSON answers, `GenError`). Caching/resume: step fingerprints (`.build_state.json`), `jobs.start` (one job per project).
- Automatic execution: `jobs._run` started Visual Planning after the transcribe job, and `usePipeline` called `/pipeline/advance` when the plan was ready.

## Decisions
- New separate step `segment` (`backend/scene_segmentation.py`), NOT part of the `transcribe` chain, started only by `POST /projects/{id}/segmentation/run`. Output `scene_segmentation.json` (contract of the roadmap, additive; `source_fingerprint` ties it to the transcript it was made from).
- 7 logical stages in one module; stages 3-5 are ONE Claude call (validated, one retry, cached in `scene_llm_cache.json`); no LLM = deterministic fallback from sentence ends, measured pauses and discourse markers, marked `needs_review` / reduced semantic confidence.
- Start/end come from the first/last word of the scene; the narration is the exact join of the words; a corrected word with estimated time is reported (`timing_source`).
- Visual Planning consumes it: `plan_input.build` lists the segmentation scenes (S1, S2, ...) instead of the cut candidates when the segmentation is fresh; `plan_checks` accepts their boundaries. A stale or missing segmentation changes nothing for existing projects.
- Invalidation: the transcript (any layer), audio analysis, config or prompt change -> `segment` re-runs; `plan-input` fingerprint includes `scene_segmentation.json`.

## Verified
See `PROJECT_STATUS.md`, section "Manual stages and Scene Segmentation".
