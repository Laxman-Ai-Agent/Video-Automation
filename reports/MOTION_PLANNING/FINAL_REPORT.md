# Motion Planning: final report (2026-10-14)

Roadmap `improvements/Motion_Planning_Complete_Roadmap/`, audit in `PHASE_0_AUDIT.md`. Branch `improvement/audio-visual`. Nothing committed yet (see "State of the tree").

## What was built (phase by phase)
| Roadmap phase | What was done | Where |
|---|---|---|
| 0 Audit and baseline | consumers, registry counts re-verified (41/8/8/52/12), baselines recorded, gaps found with evidence | `PHASE_0_AUDIT.md` |
| 1 Contract | `motion_planning.json` (`PlanM`, strict): scene ids = Visual Plan ids, seconds + frames (one rule: floor(s x fps + 0.5), end exclusive), timing source, element source ids, mode, fingerprint, repairs; legacy projects (no Visual Plan) plan with a warning | `backend/motion_planning.py`, `docs/motion.md` |
| 2 Semantic intent | narrative role, takeaway, attention goal, hints and intensity copied from the Visual Plan / selector (nothing invented) | `motion_intent` per scene |
| 3 Element planning | every Visual Plan element is `resolved` (registry id), `fallback` (named carrier + reason) or `unresolved`; planned text that is not a Visual Plan element is reported | `backend/motion_scenes.py` `resolve` |
| 4 Timing and sync | absolute start/end per action, frames, timing source (`keyword_time`, `plan`, `scene_interval`), emphasis only at the spoken keyword time, nothing outside its scene | `actions`, rules in `_rules` |
| 5 Variety and preset selection | only registry ids, never the previous scene's text preset or placed graphic (reported if it happens), variety rule, `reuse` metrics (8 of 41 text presets, 16 of 52 graphics on the sample, 0 added); the selector now takes the Visual Plan's motion hints (`select.ts` `intentPool`, first hint wins) | `remotion/src/motion/select.ts` |
| 6 Choreography | per-scene action sequence establish -> reveal -> enter -> emphasis -> exit with `depends_on`, cycle and missing-dependency checks | `actions`, `acyclic` |
| 7 Continuity | bounded history (last 3 scenes), repeats, motifs from the Visual Plan, previous/next ids | `continuity` |
| 8 Layout and legibility | safe-area box check (9:16 phone strip), graphic vs planned text region overlap, reading time, at most 2 texts, Telugu-safe presets (registry `indic` flag) | stage 6 and 9 rules |
| 9 Validation, repair, fallback | 13-stage checks; error classes per the roadmap; mechanical repairs only (clamp, shortest length, unknown id -> calm preset), each recorded; a plan with an error stops the step before Motion Generation | `sc.repair`, `pipeline.py` `_plan` |
| 10 Tests and integration | see below | `tests/test_motion_planning.py`, `frontend/tests/pipeline_ui.test.tsx` |

**The Visual Plan is now actually followed (root cause of the biggest gap):** the old planner took the text from the legacy scene plan (scene 4: "A silent red desert and few" instead of the Visual Plan's "A test of the mind"). With `--visual-plan` the on-screen text and the motion hints come from `visual_planning.json`; on the sample project all 9 scenes now match (4 did not before).

**UI (same design as Visual Planning):** `/p/<id>/step/motion_plan` with the 13 boxes in ONE row (Motion Plan Reader, Element Resolver, Preset Registry Lookup, Effect Reuse Engine, Animation Builder, Animation Engine Adapter, Composition & Transition Builder, Timing & Audio Sync, Layout Validator, Code & Plan Validator, Motion Test Runner, Error Repair Handler, Remotion Output Adapter), ring, Run / Next buttons; `/plan` table (click a row: `/plan/<scene_id>` all JSON of the scene, Copy JSON). Nothing starts by itself. API: `GET /motion-planning`, `POST /motion-planning/run` (planning only).

## Real result on `my-video-project-c2e8` (run on a COPY; the real project was not touched)
`motion-plan` step 11.4 s: 9 scenes, 473 checks, 448 passed, 0 errors, 11 warnings (all real):
- 6 x `element_fallback`: required Visual Plan elements (nodes, spacecraft, domes ...) are not drawn one by one: the library draws ONE placed graphic per scene (route-line, node-network ...), not a diagram. Recorded as fallback, not hidden.
- 4 x `layout_overlap`: a placed graphic's box overlaps the area planned for the text (scenes 2, 7, 9).
- 1 x `text_too_short`: scene 5's text is visible 1.5 s but needs about 2.8 s (it enters at the keyword time, late in the scene).

## Tests and checks (evidence)
| Check | Result |
|---|---|
| `tests/test_motion_planning.py` (new) | 19 passed (stages, frame rule, determinism, registry, repairs, Telugu, mode, transitions, code in plan, element fallback, legacy, stale, the real step incl. resume, API) |
| `tests/test_motion_only_mode.py`, `tests/test_visual_planning.py` | 125 passed, 2 skipped (before the last fixes: 1 regression found and fixed, see below); motion_only again 19 passed after |
| frontend `vitest` | 120 passed (was 110; new Motion Planning page / table / scene / steps tests); `tsc`, `oxlint`, `vite build` clean |
| remotion `tsc`, `scripts/motion_checks.ts` | clean, 113 checks pass |
| Regression found by the existing suite and fixed | "nothing moves" was an error also for a picture scene (a picture is moved by the camera); a test stub swapped the project root and broke the transition list import (now read from the Remotion source) |
| Preview (12 real stills, 3 scenes x 2 aspects x 2 moments, real renderer) | all non-blank (std 44-65), every before/after pair differs (mean diff 11-16). NOT shown: a text safe-area measurement (my bright-pixel box includes the full-frame atmosphere layers, so it proves nothing); text safe area is covered by the existing layout tests, not re-measured. **Not judged by eye** (project rule: no image viewing) |
| Full backend suite (`pytest`, run at the end, all files) | **611 passed**, 0 failed, 2 library deprecation warnings, 21 min 04 s |

## Behaviour changes to know
- The `motion-plan` step has a new output (`motion_planning.json`) and its fingerprint includes the new modules, so a project planned before shows Motion Planning (and Motion Generation) as not finished until it is run again from the page; Continue / Render wait for it (`motion_incomplete`) as before.
- A Visual Plan that is current is now required to give its text to the motion plan (flag set automatically); projects without a Visual Plan behave as before.
- The backend has no `--reload`: restart uvicorn to get the new routes.

## Limits (honest)
- No Claude call in Motion Planning: the "planner" is the deterministic selector. It cannot draw a Visual Plan diagram element by element (see `element_fallback`); that needs new graphics in the library, which was not added (roadmap: add presets only for a missing required capability, and none was shown to be required for correctness).
- Word-level sync only where the scene plan has keyword times; otherwise scene intervals (recorded in `timing_source`).
- 9:16 and 16:9 both build and validate; the page itself was only tested with vitest, not opened in a browser with the new backend (the running server has the old code).
- Not run: full-size renders, Playwright e2e, paid/live providers.

## Update 2026-10-14: Solve warnings, drawn elements, divider (real project `my-video-project-c2e8`, 16:9, motion-only)
Details and numbers are in `PROJECT_STATUS.md` ("Applied to the real project" and "Diagram elements, layout and divider"); design in `docs/motion.md`.
- **Solve warnings** (button, `motion_fixes.json`): 11 warnings -> 2 on the first apply; backup `real_project_backup_before_solve_2026-10-14/`. Audit findings fixed: the first version moved graphics onto the drawn headline (plans now carry `drawn_box`), the reading time was counted to the end of the scene instead of the start of the exit, an accepted fallback is never "solved", Motion Generation refuses a stale or failing checked plan.
- **The 15 undrawn required elements** (`remotion/src/motion/diagram.ts`): 12 drawn, 2 drawn as a stand-in ("approximate": crew_team, help_line), 1 not drawn (habitat_domes: no dome primitive). Optional elements not drawn: mind_icon, silence_icon, triad_emblem. Elements carry their Visual Plan id in the composition layers.
- **grid-lines / node-network:** the overlap warnings are gone because the diagram builder gave them a function and a free place (timeline of three stops; link between two worlds), not because a geometric move was forced.
- **Scene 5 divider:** fixed at the root (`split_two` picture divider dropped in motion-only), regression-checked in `motion_checks.ts`. Scene 5 text timing unchanged (31.88 s, 2.81 s before the exit).
- **Final counts (real project, plan v2):** warnings 0, errors 0, accepted-but-not-drawn 1 (scene 8 habitat_domes), approximate required elements 3 (crew_team, help_line, small_crew_group).
- **Tests:** `motion_checks.ts` 147, `test_motion_planning.py` 32, vitest 123, tsc/oxlint clean; full backend suite: see `PROJECT_STATUS.md`.
- **Limits:** the rocket does not travel, discs are plain, dashed links are thin, 9:16 only on a copy with a re-stamped Visual Plan (no real 9:16 Visual Planning run), the existing `shape` circle is drawn with an offset of its radius (compensated by the builder). Motion Generation and rendering were not started.
