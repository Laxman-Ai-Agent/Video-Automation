# Motion Planning, Phase 0: audit and baseline (2026-10-14)

Roadmap: `improvements/Motion_Planning_Complete_Roadmap/`. Branch `improvement/audio-visual`, last commit `555c326` (Visual Planning). Working tree: unrelated dirty files (deleted old docs, project data) left alone.

## What exists (reuse, do not rebuild)
| Piece | Where | Notes |
|---|---|---|
| Motion Planning step | `backend/pipeline.py` `_motion_steps`: `motion-plan[-9x16]` | runs `remotion/scripts/build_composition.ts --plan-only`, writes `motion_plan[_9x16].json` (version 1: per scene `texts[]`, `graphics[]`, `transition`, `pictures`, `pattern`, mode, speed), then attaches `visual_plan` (handoff) and checks `visual_planning.link_errors`. Blocked by `visual_planning.blockers()` |
| Motion Generation step | `motion-build[-9x16]` | builds `composition[_9x16].json`; fails if `_planned(plan) != _built(comp)` |
| Validation of the composition | `motion-validate`, `motion_checks.py`, `plan_checks.py` | transitions audit (`transition_audit.py`), pre-render checks |
| Branch state | `backend/motion_branch.py`, `GET /motion`, `POST /motion/run`, `pipeline_view.py` | stage ids `motion_plan`, `motion_gen`; `A2V_MOTION` flag (`config.FLAG_NAMES`), `use_images` per project |
| Registry | `remotion/src/motion/` (`textPresets.ts`, `graphics.tsx`, `masks.ts`), `npx tsx scripts/motion_list.ts` | re-verified today: **41** text, **8** exits, **8** emphasis, **52** graphics, **12** masks (matches the roadmap); transitions list `remotion/src/transitions/index.ts` (`transition_audit.KNOWN`) |
| Selection | `remotion/src/motion/select.ts`, `integrate.ts` | deterministic (seeded hash of the plan), never the previous scene's text preset, fallbacks for Telugu / long text; 25 graphics have a placement (`SLOT`) |
| Layout | `remotion/src/motion/layout.ts` | safe margin (9:16: bottom 16%), overlap prevention, applied when the composition is built |
| Visual Plan | `visual_planning.json` (`backend/visual_planning.py`) | scene_id `scene_NN`, elements (type, role, content, placement, registry_requirements), relationships, `motion_hints`, narration times + `timestamp_source`, `source_mapping` (plan/timeline intervals) |
| UI | `frontend/src/pages/VisualPlanningPage.tsx` (8 cards), `pipeline/StageBoxes.tsx`, `visualPlanningSteps.ts` | Motion Planning is only the generic `StepPage` `Motion` block (no cards) |
| Time rule | seconds everywhere; frame = seconds x 30 (composition `meta.fps` 30) | the plan has no frame values yet |

## Findings (the real gaps, evidence from `projects/my-video-project-c2e8`)
1. **The motion plan does not follow the Visual Plan's on-screen text.** Text comes from the legacy `scene_plan.json` (`params.text`, keyword, or the scene's meaning as a fallback headline). Scene 4: Visual Plan "A test of the mind" vs motion plan "A silent red desert and few"; scene 8: "A new chapter" vs "Successful settlement on Mars would be"; scene 2: "About eight months" vs "Eight months"; scene 5: "Knowledge ... Training ... Trust" vs "Mutual trust". (Scenes 1, 3, 7, 9 match.)
2. **Graphics are chosen by topic and mood only** (`chooseMotionOnlyDecor`), never from the Visual Plan's elements or `motion_hints` (e.g. `show_flow_direction`, `travel_along_path`). Scene 2 has a route/spacecraft in the Visual Plan and gets `floating-dots`, `divider-grow`, `bracket-frame`.
3. The plan has **no absolute times, no frames, no timing provenance and no choreography/dependency data** (only `enter_s`); an element is not linked to its Visual Plan element.
4. There is **no validation layer for the motion plan itself** (registry ids, timing bounds, dependency cycles, mode rules, safe areas): it is only compared with the built composition afterwards (`_planned == _built`).
5. No motion planning LLM prompt exists (selection is code); the roadmap's prompt spec therefore applies to the deterministic selector (semantic match first, determinism, no invented ids), not to a new Claude call. **Decision:** no new AI call; this keeps planning free and deterministic. Limit recorded in the final report.
6. The stored `motion_plan.json` of the sample project predates the latest Visual Plan (written 23:56, Visual Plan revised 07:03) but its recorded fingerprint matches; the plan is not "stale" by the existing rule.

## Baseline (before any change)
| Check | Result |
|---|---|
| `npx tsx scripts/motion_checks.ts` | 113 checks pass (21 s) |
| `tests/test_motion_only_mode.py` | 19 passed (247 s) |
| `tests/test_visual_planning.py` | 91 passed |
| frontend `vitest` / `tsc` | 110 passed / clean |
| Full backend suite | not run as a baseline (31 min); the last recorded full run (2026-10-12): 410 passed. Known flakes: `test_m7::test_full_flow`, `test_m9_review::test_run_match_imports...` (pass alone) |

## Plan (13 boxes of the UI -> roadmap stages)
The page shows 13 boxes (user's list). They are logical stages of ONE planner (no new agents):
1 Motion Plan Reader (roadmap 1-2) | 2 Element Resolver (4) | 3 Preset Registry Lookup (4-5) | 4 Effect Reuse Engine (5, variety) | 5 Animation Builder (3, 5-7 choreography) | 6 Animation Engine Adapter (11) | 7 Composition & Transition Builder (9) | 8 Timing & Audio Sync (8) | 9 Layout Validator (10) | 10 Code & Plan Validator (12) | 11 Motion Test Runner (tests) | 12 Error Repair Handler (12 repair) | 13 Remotion Output Adapter (11 output).
Implementation: extend the existing `motion-plan` step (no second pipeline): TS planner reads the Visual Plan (text, hints) -> richer `motion_plan.json` -> new `backend/motion_planning.py` produces `motion_planning.json` (per scene context, intent, element resolution, action sequence with times/frames, continuity, validation, the 13 stage results, repairs) -> Motion Planning page, table page, scene JSON page.

## Baseline update: full backend suite (run before the Motion Planning changes, commit 555c326)
`pytest tests -x`: 495 passed, then it stopped at `test_transcript_review.py::test_estimated_timestamps_keep_the_step_unfinished_until_the_alignment_succeeds` (1778 s, machine busy). Re-run alone: `tests/test_transcript_review.py` 25 passed. So it is a load-dependent flake, not a regression; because of `-x` the tests after it did not run in that pass. Frontend vitest 110 passed. Pre-existing flakes list: `test_m7::test_full_flow`, `test_m9_review::test_run_match_imports_and_matches_without_a_composition_or_a_render`, `test_transcript_review::test_estimated_timestamps_keep_the_step_unfinished_until_the_alignment_succeeds` (all pass alone).
