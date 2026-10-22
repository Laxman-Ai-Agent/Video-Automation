# Motion Generation Implementation Report (2026-10-14)

Roadmap `improvements/Motion_Generation_Complete_Roadmap`. Design and rules: `docs/motion.md` ("Motion Generation"), status: `PROJECT_STATUS.md`.

## 1. Summary
- **Scope implemented:** the existing step `motion-build` now builds the composition from the checked motion plan (`motion_planning.json`) and checks it with the 13 stages of the roadmap
  (Plan Reader, Element Resolver, Preset Registry, Effect Reuse, Animation Builder, Engine Adapter, Composition Builder, Audio Sync, Layout Validation, Code Validation, Motion Testing, Error Repair,
  Remotion Adapter). It writes `motion_generation[_9x16].json` (one descriptor per layer with component, preset, props, seconds and frames, the stages, validation, repairs, tests, output). New page
  `/p/<id>/step/motion_gen` (13 boxes in one row, same design as Motion Planning), `/output` (table, one row per scene), `/output/<scene_id>` (all JSON of a scene, Copy JSON).
  API `GET /motion-generation`, `POST /motion-generation/run` (Motion Generation only).
- **Existing functionality reused:** the motion library and its registry (`motion_list.ts`), `build_composition.ts` (the composition is what it always was), the checked plan, `motion_planning.Run`, the one
  seconds-to-frames rule, the job runner, the step fingerprints, the Motion Planning page components. No second pipeline, renderer, agent or preset library; no Claude call; no code from a plan is executed.
- **Known limitations:** see section 7.

## 2. Phase status
| Phase | Status | Evidence / report | Blocker |
|---|---|---|---|
| 0 Audit | done | `motion_branch.py`, `pipeline._build`, `build_composition.ts`, registry, composition schema read; plan and composition contract mapped | none |
| 1 Input normalization | done | stage 1: plan current, no errors, same mode / aspect / fps, scene counts equal (tests: stale plan, wrong mode) | none |
| 2 Element resolution | done | stage 2: every planned element has a layer in the composition; recorded fallbacks stay "NOT drawn" (habitat_domes) | none |
| 3 Preset registry | done | stage 3 + `motion_validate.ts`: text, exit, emphasis, graphic, primitive, transition ids and lucide names against the real registry; unknown = error (test) | none |
| 4 Reuse-first | done | stage 4: no preset outside the registry, 0 new presets, fallbacks carried from the plan | none |
| 5 Descriptors | done | stage 5: 66 descriptors for the real project (copy), each linked to its planned action; planned but not built = error (test) | none |
| 6 Choreography | done | stage 7: scene intervals as planned, unique ids, no element drawn twice, transitions known / not repeated / fit | none |
| 7 Timing / audio sync | done | stage 8: frames by one rule inside the scene, emphasis on a spoken word (4 real warnings: the library's emphasis time is the entrance + 0.25 s, not a word), audio file, duration | none |
| 8 Layout | done | stage 9: safe area per aspect, graphics and drawn nodes clear of the drawn text, nodes apart | none |
| 9 Repair / fallback | done | stage 12: a time outside its scene and a box outside the safe area are repaired, at most 2 passes, each recorded (test) | none |
| 10 Motion QA / preview | done | motion checks (147), repeat build identical, 1 s quarter-size previews in both aspects decoded and measured (section 5) | no eye review |
| 11 Timeline handoff | done | same `composition[_9x16].json` the Timeline Build reads; `motion_branch.complete` also needs a current report without errors | none |
| 12 Docs | done | this report, `docs/motion.md`, `PROJECT_STATUS.md` | none |

## 3. Files changed
- **Created:** `backend/motion_generation.py`, `backend/motion_gen_rules.py`, `backend/motion_gen_report.py`, `remotion/scripts/motion_validate.ts`, `tests/test_motion_generation.py`,
  `frontend/src/pipeline/motionGenerationSteps.ts`, `frontend/src/pages/MotionGenerationPage.tsx`, `MotionOutputPage.tsx`, `MotionOutputScenePage.tsx`, this report.
- **Modified:** `backend/pipeline.py` (`motion-build` step, `CHAINS["motion-gen"]`, `_generation_inputs`), `backend/routes/pipeline.py` (2 routes), `backend/motion_branch.py` (gate), `backend/pipeline_view.py`
  (percent of the running stage), `frontend/src/App.tsx`, `src/api/client.ts`, `src/api/types.ts`, `tests/pipeline_ui.test.tsx`, `tests/contract.test.ts`, `tests/fixtures/openapi.json`, `docs/motion.md`,
  `PROJECT_STATUS.md`.
- **Preserved:** the real project `my-video-project-c2e8` (not run: Motion Planning shows "queued" there until it is run again, see section 7), all unrelated dirty and untracked files.

## 4. Tests actually run
See `PROJECT_STATUS.md` ("Motion Generation") for the numbers of the last runs; this report lists them there once, to keep one source.

## 5. Preview renders (scratch, copies of the real project; not full size)
- **16:9:** `scratchpad/preview_gen/gen_16x9.mp4`: 480x270, h264, 30 fps, 30 frames (frames 1330-1359 of the composition), muted. Frame 0 std 47.6, frame 29 std 49.3, mean difference 11.65: not blank, it moves.
- **9:16:** `gen_9x16.mp4`: 270x480, same settings. std 43.2 / 46.1, mean difference 9.16.
- **Motion-only:** the real project copy (above) and the fixture project (tests). **Image-enabled:** the fixture with picture slots (test): slots kept, 0 errors. No image preview was rendered.

## 6. Visual verification
- **Automated technical checks:** decode, size, fps, frame count, non-blank, change over time, the validator, determinism (two builds byte-identical), 147 library checks.
- **Human visual review:** not by a person. The stills of the diagram elements were looked at earlier in this session (see `PROJECT_STATUS.md`); the preview videos were measured, not watched.

## 7. Remaining blockers and limits
- The real project has not been run through Motion Generation (the user's decision): Motion Planning has to be run again first because the Remotion source changed after its last run.
- 4 emphasis times per project are "not on a spoken word": the library emphasises a marked word 0.25 s / pace after its entrance (not from a transcript word); reported, not changed.
- The plan gives one element id to a text and to the graphic chosen for its hint (Motion Planning); descriptors therefore carry their own `descriptor_id`.
- 9:16 was generated on a copy whose Visual Plan was re-stamped to portrait (no real 9:16 Visual Planning run).
- Only still frames and 1 s quarter-size previews; no full render was made.
