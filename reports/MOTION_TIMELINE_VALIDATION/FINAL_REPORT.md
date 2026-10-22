# Motion & Timeline Validation (Stage 10) Implementation Report (2026-10-14)

Roadmap `improvements/Motion_Timeline_Validation_Complete_Roadmap`. Design and rules: `docs/motion.md` ("Motion & Timeline Validation"), status: `PROJECT_STATUS.md`.

## 1. Summary
- **Implemented:** Stage 10 between Motion Generation and the Timeline Build. A read-only validator with the roadmap's 12 internal checks, a versioned rule catalog, stable findings with evidence and owner stage,
  fingerprints of every input, a per-check cache, explicit fingerprint-bound exceptions, optional preview stills, a strict readiness gate, an API and a page like Motion Generation (`/p/<id>/step/motion_validation`).
- **Existing functionality reused:** `motion_generation.descriptors` / `rect_of_layer` / `validate_composition` (the renderer's own zod contract), `motion_gen_rules` geometry helpers, `motion_planning.fr` (the ONE frame rule),
  `registry()`, `reading_end/need`, the job runner and step machinery, `motion_gen_report.load` and `motion_planning.load` (their own staleness), `StageBoxes` and the Motion Generation page layout. No second pipeline,
  renderer, agent or preset library; no Claude call; no plan code is executed.
- **Not implemented (stated, not hidden):** a separate `timeline_validation.json` for the BUILT timeline with the roadmap's `timeline.*` rule ids and read-back digest (section 6), an immutable approval snapshot, a Stage 10
  fingerprint inside the approval version.

## 2. Phase status
| Phase | Status | Evidence | Blocker |
|---|---|---|---|
| 0 Audit | done | section 6; real artifacts of `my-video-project-c2e8` read; existing gates and tests found before any change | none |
| 1 Report core | done | `motion_validation.py`: fingerprints, versioned findings, atomic write + read-back, summary, readiness; tests: stale / failed / crash / commit race | none |
| 2 Structural validators | done | `motion_validation_rules.py` stages 1-10 (about 60 rule ids of the catalog); tests with a negative fixture per family | none |
| 3 Preview evidence | done (stills only) | `motion_validation_preview.py`; deterministic frames; levels kept apart; real run on the real project (section 5) | motion playback not generated |
| 4 Gate, UI, API | done | motion-only `motion-validate` step, `motion_branch.blockers`, `render_blockers`; 7 routes; page, steps, tests | none |
| 5 Timeline Build post-build contract | audited, partly existing | section 6 | no `timeline_validation.json` / `timeline.*` ids |
| 6 Approval / Render / Final QC contracts | audited, existing | section 6 | no immutable snapshot; approval does not name the Stage 10 fingerprint |
| 7 Hardening | done for Stage 10 | writers refuse while a job runs (`_idle`), atomic report with read-back, cache invalidation, duplicate requests (`_same_job`), a crash leaves a `failed` report | a restart mid-run: section 7 |

## 3. Files
- **Created:** `backend/motion_validation.py`, `motion_validation_rules.py`, `motion_validation_preview.py`; `tests/test_motion_validation.py`; `frontend/src/pipeline/motionValidationSteps.ts`,
  `frontend/src/pages/MotionValidationPage.tsx`; this report.
- **Modified:** `backend/pipeline.py` (4 steps, 4 chains, the gate in the motion `motion-validate`), `backend/motion_branch.py` (`blockers`, `validation_stage`), `backend/pipeline_view.py` (stage 10),
  `backend/routes/pipeline.py` (7 routes), `frontend/src/App.tsx`, `src/api/client.ts`, `src/api/types.ts`, `src/api/pipelineTypes.ts`, `src/pipeline/layout.ts`, `PipelineChart.tsx`, `MotionGenerationPage.tsx` (Next opens Stage 10),
  `frontend/tests/pipeline_ui.test.tsx`, `contract.test.ts`, `fixtures/openapi.json` (65 paths), `tests/test_m6.py`, `tests/test_motion_only_mode.py`, `tests/test_pipeline_gate.py`, `docs/motion.md`, `PROJECT_STATUS.md`.
- **Preserved:** every upstream artifact of the real project (byte-identical hashes before and after the real run), `motion_fixes.json`, backups, user data.

## 4. Decisions
- **`accepted` in Solve warnings is not an exception.** `habitat_domes` stays a BLOCKER; only an authorized, reasoned, fingerprint-bound exception (a name, a reason of >= 10 characters, ending when any input changes)
  can let the build through, and the finding then reads `accepted_for_version`, never resolved, and `required_not_drawn` still counts it. An error or another blocker can never be accepted.
- **Review rules** (collision, safe margin, readability, audio length, continuity notes) make an unresolved warning `needs_review`; emphasis-inside-a-word, unknown geometry, stand-ins and the missing preview are
  permitted warnings (`ready_with_warnings`). A check that could not be verified is counted as skipped, never as passed.
- **Emphasis tolerance 60 ms** is the project's own existing policy (Motion Generation stage 8), not a new default.
- **Legacy projects** (no Scene Segmentation / stored Visual Plan) are validated against their scene plan and say so as warnings; modern projects get blockers for the same.
- **No dry build:** determinism is the repeat build Motion Generation recorded (a dry build would overwrite `composition.json`).

## 5. Real project `my-video-project-c2e8` (16:9, motion-only)
- Run once through the page (job `motion-validation`, 22 s, 0 stages reused): **blocked**, 1 blocker (scene_08 `habitat_domes` required, not drawn), 0 errors, 5 warnings (4 emphasis times inside the spoken words
  of scene 1, 2, 6, 9 with the exact seconds; no preview yet), 7 info (3 optional elements not drawn: mind_icon, silence_icon, triad_emblem; 4 texts whose drawn position the planner did not measure), 933 of 938 checks passed,
  8 not verifiable, 9 of 9 scenes. No exception was recorded: that is the user's decision.
- Upstream artifacts byte-identical before and after (sha256 of every file except the report, job and log files).
- Preview: see `PROJECT_STATUS.md` ("Motion & Timeline Validation phase") for the result of the one Generate Preview run.
- **Update (same day):** the blocker was fixed by a real `dome` primitive (see `PROJECT_STATUS.md`, "Habitat dome primitive"): after Motion Planning and Motion Generation were run again, Stage 10 reads **ready_with_warnings**
  (0 blockers, 0 errors, the same 4 emphasis warnings, `habitat_domes` drawn, no exception). The numbers above are those of the first run, kept as the record of what the gate caught; the backup of that state is in
  `real_project_backup_before_dome_2026-10-14/`.

## 6. Audit of Stages 11-14 against the roadmap (what exists, what does not)
| Roadmap contract | Existing component | Status |
|---|---|---|
| 11 Timeline Build from current inputs only; structural post-build validation | chain `timeline`; `motion-validate` (`prerender_checks.check`): timeline timing, media, text | exists; Stage 10 now gates it. No `timeline_validation.json` with `timeline.*` ids and read-back digest |
| 12 Approval of the exact timeline fingerprint | `timeline_gate.current_version` (digest of composition + referenced files), `approve`, `stale` | exists |
| 13 Render only the approved snapshot | `require_approved`, `render_blockers` (now also Stage 10) | exists; the composition on disk is rendered, not an immutable copy |
| 14 Final QC of the real file | `video_qc.check` / approval, needs `out.mp4` | exists |

## 7. Limits
- Stills only: motion playback and transitions have not been watched; a still is not proof. "Reviewed by a person" is a recorded statement, not a check.
- `layout.renderer_geometry_known`: where the planner did not measure a text's drawn box (scenes 1 and 6) the collisions are NOT verified; this is said, per text.
- A backend restart while a validation job runs leaves the old report (stale or failed), never a new green one; the job must be run again.
- `habitat_domes` still has no dome primitive; this work did not change that.
- 9:16: the validator uses the portrait safe area and the `_9x16` files, but no genuine 9:16 Visual Planning run exists, so no 9:16 claim is made.
