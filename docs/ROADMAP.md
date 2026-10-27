# Roadmap: from today's output to professional cinematic videos (2026-10-27)

Read after `CLAUDE.md` and `docs/SESSION_STATUS.md`. This file holds the evidence-based assessment of the whole system, the phased plan, and every pending task. Update the "Status" column when a phase moves.

## 1. Assessment (evidence, 2026-10-27)
Evidence: the real render of the test project `my-first-project-01-df7f` (one frame per second in `timeline_thumbs.jpg`, the frames around every cut in `final_qc_frames/`), `visual_planning.json`, `timeline.json`, the 8 generated scenes (`generated_motion/scene_*.tsx`, 2,991 lines), the render profile, the Final QC report, and the stage code.

- **What works:** the autonomous 13-stage run (all stages completed, render verified frame for frame, A/V lengths equal), Telugu transcription + LLM correction, scene segmentation on sentence boundaries, a genuinely good semantic Visual Plan (meaning, takeaway, concept, accuracy limits, beats, elements per scene), generated TSX compiles (0 tsc errors, 449/449 validation checks), provenance/licences, fingerprint reuse.
- **Overall:** the engineering is solid; the videos are ~30-35 % of the goal (a judgment): calm, slow, card-based explainers, not fast cinematic videos.
- **Biggest gaps:**
  1. Pacing: 8 scenes in 59.5 s = one layout per 7.4 s (up to 12.2 s); inside a scene the composition never changes (elements only appear). Pro target: a visual change every 1.5-3 s.
  2. No narration sync: the code generator gets the scene length, not the word times; elements appear on a fixed schedule (`frame - base - i*14`).
  3. Sameness: every scene dark navy gradient, rounded cards, small centred title, content in 40-50 % of the frame; the only "camera" is scale 1 -> 1.04.
  4. The motion library is cut off: `SYSTEM/skills/motion` (16 categories, 35 KB) reaches the code generator as one-line summaries; imports from `components/`, `motion/`, `patterns/` are forbidden, so every scene is reinvented.
  5. Real media ~0: no video clips, 4 small photos in cards (Pexels/Pixabay/Unsplash keys not set; asset ranking never looks at the pictures: a black-and-white historical photo was chosen for "Instagram ad for a clothing store").
  6. No sound design: narration + composition tracks only; no music, SFX or loudness normalisation.
  7. No captions in the video (`@remotion/captions` + Noto Sans Telugu are installed, unused).
  8. Nothing looks at the pixels: the six LLM reviews read JSON reports.
  9. Speed: render 792 s for 59 s of video (13.3x), Whisper 807 s; a 10-minute video = about 2.2 h + 2.2 h on this CPU.
  10. Weight: `SYSTEM/` (agent framework, registries, approvals, skill factory, mock agents) 48k lines vs `VIDEO_ENGINE/` 26k; tests 33k.

## 2. Phases (ordered by impact)
| Phase | What | Status |
|---|---|---|
| 0 | Reliability fixes | **DONE 2026-10-27** |
| 1 | Shots + narration sync | **code DONE 2026-10-27** (not yet proven on a real run) |
| 2 | Motion kit + art direction | pending (needs the user's decision) |
| 3 | Real footage + images, chosen by looking at them | pending (needs API keys) |
| 4 | Sound design | pending |
| 5 | QC that sees the frames | pending |
| 6 | Captions + retention | pending |
| 7 | Performance | pending |

### Phase 0 - reliability (DONE)
Empty frames at cuts fixed in the code generator (rule 8, `motion_animation.scene_self_fades`, `CODEGEN_VERSION` 2); Final QC sees empty cuts (`final_qc.measure().detail`, `RULES_VERSION` 2); tests isolated from repository state (conftest `isolate_repo_state`, one approvals-audit writer `ApprovalEngine.record_event`); one `/video` route; `slow` / `live_ui` test markers (fast suite `pytest tests -m "not slow and not live_ui"`, ~8 min, target 5 min not reached). Plus: analyzer correction prompt restored (cut by accident in `31b2f3e`), `is_verified` needs the current rules version, a failed LLM check keeps `refine` unfinished, test leftovers removed from the skill catalog.

### Phase 1 - shots and narration sync (largest visual impact) - CODE DONE 2026-10-27
What was built (not yet proven on a real render: the test project must run the pipeline again):
- `visual_planning_rules.shots()` cuts every scene into shots of 1.5-3.5 s (`SHOT_MIN`/`SHOT_MAX`/`SHOT_TARGET`) that cover the whole interval the scene holds on the timeline. Every cut falls on the END of a spoken word; the ends of the beats the planner wrote are the preferred cut points; a tail shorter than the minimum joins the shot before it. Derived deterministically: the planner is NOT asked for shots and no extra LLM call is made. Each shot carries `start_frame`/`end_frame` relative to the scene's own frame 0 and the words spoken in it with their frames. A scene whose words allow no cut stays one shot and records the info note `shot_uncuttable` (never a warning nobody can clear).
- Every scene of `visual_planning.json` now has `shots`; `visual_planning.VERSION` is 3 (the plan of an existing project is made again on the next run). New checks (`rules.check_shots`): `shots_present`, `shots_contiguous`, `shots_min_length` (all errors: a failure is a bug in the splitter).
- The code generator receives the shots (`motion_animation.generate_scene_tsx_via_llm(shots=...)`), with system rules 10 and 11: one `<Sequence from=... durationInFrames=...>` per shot, a DIFFERENT composition per shot (not one more element on an unchanged layout), and a word drawn on screen appears at its own `start_frame`. `missing_shot_sequences()` flags a scene whose code has no Sequence for a shot, inside the existing bounded quality-repair pass; the shots are part of `scene_input_fingerprint`, and `CODEGEN_VERSION` is 3 (every scene is written again).
- The preview samples the middle of EVERY shot (`motion_validation_preview.sample_plan(comp, shots)`, `RULE_VERSION` 2; a scene with fewer than two shots keeps entry/mid/pre-exit, so the number of stills stays about the same) and keeps a 16x16 grey thumbnail per still. `picture_change()` is the mean absolute difference of two thumbnails; `motion_validation_rules` checks `preview.shots_sampled` and `preview.shot_changes` (warning below `SHOT_CHANGE_MIN` = 6.0: the scene shows one layout instead of separate shots). `RULE_SET` is 1.2.
- Tests: `tests/test_scene_shots.py` (11 tests: lengths, word-boundary cuts, frames and word times, beat-preferred cuts, short tail, no words, the three checks, the Sequence check, the fingerprint, the sampling, the difference measure).
- Open for Phase 1: nothing is proven on a real render yet. The next pipeline run of the test project writes all scenes again and the shot checks then say whether the LLM really changes the composition per shot.

### Phase 1 - the original plan
- **Why:** the picture must change every 2-3 s and words must appear when they are spoken.
- **How:** Visual Planning splits every scene into shots of 1.5-3.5 s whose times are snapped to word timestamps (beats already exist in all scenes; `visual_planning.rules.snap_beats` snaps them). The code generator (`motion_animation.generate_scene_tsx_via_llm`) receives each shot's frame range and the word timestamps of the key terms, and builds the scene as one `<Sequence>` per shot with a real layout change per shot. New validation rules: maximum shot length; minimum visual change per 3 s, measured on the preview stills (frame difference).
- **Expected:** a visual change every ~2.5 s; on-screen words land on the spoken word.

### Phase 2 - professional motion kit + art direction (USER DECIDES)
- **Why:** reinventing every scene from scratch gives generic, inconsistent motion.
- **How:** a small vetted kit in `VIDEO_ENGINE/remotion/src/kit/`: camera rig (pan, push, parallax, rack focus, motion blur), kinetic typography engine (word by word, masks, emphasis, driven by timestamps), transitions chosen by narrative role (whip-pan, match cut, zoom-through, light leak), maps (`public/geo`), charts (Nivo/ECharts), lower thirds, several background style families. Generated scenes may import ONLY from the kit (change `PROHIBITED_IMPORT_REGEX` into an allowlist); the LLM composes. Each video picks one of several art directions (palette, typography, grain, texture), so not every video is dark navy.
- **Note:** this partly reverses the "no reusable templates" rule in CLAUDE.md, so the user must approve it first.
- **Expected:** consistent professional motion, fewer tokens, fewer compile retries.

### Phase 3 - real footage and images, chosen intelligently
- **Needs:** `PEXELS_API_KEY`, `PIXABAY_API_KEY`, `UNSPLASH_ACCESS_KEY` (set by the user).
- **How:** video clips as full-frame B-roll shots with typography over them (not thumbnails in cards); asset ranking (`asset_collection.choose`) sends a contact sheet of the candidate pictures to a vision-capable model (one call per batch) instead of titles only; plan rule: footage-led shots when the narration is about the real world.
- **Expected:** a real mix of footage, images and graphics; relevant pictures.

### Phase 4 - sound design
Licensed music bed ducked under the narration, SFX on transitions/reveals, loudness normalised to -14 LUFS. The biggest jump in perceived "cinematic" quality per unit of work.

### Phase 5 - QC that sees
The Final QC LLM review receives the thumbnail sheet and the cut frames (they already exist) plus measured metrics: shot-change rate, motion energy, text size at mobile scale, frame usage. Its findings go back as "regenerate scene N because X".

### Phase 6 - captions and retention
Word-timed animated Telugu captions (Noto Sans Telugu), a hook in the first 3 s, emphasis on key terms as they are spoken.

### Phase 7 - performance
Render scene by scene with a cache (only changed scenes re-render, then join), half-resolution preview renders, tuned render concurrency, finish the Whisper benchmark (chunk size, beam, with an accuracy check). Test suite: the fast suite to 5 min (the per-test Remotion/npx spawns are the lever).

## 3. Pending tasks (outside the phases)
1. **Analyzer of the test project has 2 errors** after the re-run with the restored rules: step 10 "Word Timestamp Integrity" (1 error in 130 word timestamps) and step 13 "Final Audio Analysis Validation" (1 error). They block Scene Segmentation. Find the word at its root (the re-alignment of a corrected word) and fix it there.
2. Then the full run of the test project from Scene Segmentation (`POST /projects/{pid}/orchestrator/run`): every later stage is stale (new transcript), Motion Generation writes all scenes again (no whole-scene fades), Final QC runs with the new empty-cut check. Then ONE fast-suite run.
3. The transcript re-run has one wrong word: segment 3 "Instagram ad caption" became "add caption" (homophone). The LLM decides the transcript (no hand edits); it may be worth an instruction example.
4. Two e2e tests (`test_phase9_e2e_integration`, `test_e2e_production_readiness`) still write `synthetic_test_p*_e2e_*.wav` into `VIDEO_ENGINE/remotion/public`, and tests write the real agents' `memory/experiences.json`.
5. The timeline assessor's deterministic fallback (`approval_intelligence.LLMTimelineAssessor._deterministic_assessment`) returns `approved` (0.95) when the LLM is unavailable, against the rule "an unavailable LLM never approves" (advisory component; `test_llm_timeline_assessor_fallback` fails on it).
6. The 16 live-UI browser tests are stale (they look for old texts like "20 Registered", "11 stages").
7. Decide about the 5 `remotion-animated-bar-chart_v1.2.0_*` copies in `SYSTEM/skills/archive/library_history/charts/` (made within 100 s; probably test reinstalls, not proven).
8. Prove the autonomous run on a NEW project from an audio upload (not done: the user asked to wait).
9. `TimelineTrackCanvas` / `TimelineTrackHeaderColumn` still carry inline styles (rule 11 debt).
