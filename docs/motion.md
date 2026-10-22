# Motion library (text animation + motion graphics)

Code: `VIDEO_ENGINE/remotion/src/motion/`. Frame-driven (no GSAP, no Framer Motion, no clock, no `Math.random`): the same frame always gives the same picture.
Off by default. Turn it on for new compositions with `A2V_MOTION=1` (or `build_composition.ts --motion rich`); the flag is part of the cache fingerprint
(`config.FLAG_NAMES`), so switching it never reuses the other mode's composition. Without it the composition is byte-identical to before.

## Use Images OFF (Motion-Only mode) and the pace
- Every project is Motion-Only (`project.json` `use_images` is always false; the Use Images switch, `POST /projects/{id}/mode` and the image routes `/match`, `/match/fix`, `/submit`,
  `/prompts/*` were removed 2026-10-21). Nothing about images can block Continue / Approve / Render.
- The timeline is built straight from the scene plan: `build_composition.ts --no-images` (env `A2V_USE_IMAGES=0`) removes the picture layers, always uses the motion library,
  makes a headline from the scene's text / keyword / meaning when a scene has none, and gives every scene an atmosphere graphic (particles, light, network ...), a placed graphic
  that fits the topic and, from 2.5 s, a self-drawing frame or line (`select.ts` `chooseMotionOnlyDecor`; never the previous scene's graphics). `meta.motionOnly = true`.
  Pipeline steps: `motion-build[-9x16]`, `motion-validate[-9x16]` (`pipeline.CHAINS`, `pipeline.chain_for`); the render steps are the normal ones. Both formats, 30 fps.
- **Pace** (`A2V_MOTION_SPEED`, default 1.4 without pictures and 1.3 with the library otherwise, clamped to 0.5-2, `1` = the preset durations as designed): text entrances, stagger
  and exits are divided by it (never below 0.25 s), graphics play `speed` times faster, scene transitions are `0.6 s / speed` (min 0.25 s). The frame rate is never changed.
  Written as `meta.motionSpeed`. Layout (no overlap, safe area, Telugu width) is unchanged by the pace.
- Switching back to Use Images ON rebuilds the picture-slot compositions; a motion-only approval can never render an image video (`timeline_gate.built_for_mode`).

## The motion branch of the Pipeline flowchart
Two steps split the build: **Motion Planning** (`motion-plan[-9x16]`: `build_composition.ts --plan-only` writes `motion_plan.json`: per scene the text preset, exit, emphasis, graphics, pace and transition) and **Motion Generation**
(`motion-build[-9x16]`: builds the composition and fails if it does not contain exactly what was planned). They run in both modes (`pipeline.CHAINS["motion"]`, started by `POST /pipeline/advance` when the plan is ready;
`POST /motion/run` retries) next to the image branch; `GET /motion` feeds the node pages. With Use Images ON the composition keeps its picture slots; Continue / Render Video refuse (`motion_incomplete`, `render_blockers`) until
both branches are complete. Projects made before the branch existed (no `motion_branch` in `project.json`) keep their old flow and show both nodes as Skipped.

## Motion Planning: the checked plan `motion_planning.json` (13 stages)
Roadmap `improvements/Motion_Planning_Complete_Roadmap`. The `motion-plan` step now does two things in one place (no second pipeline, no Claude call): the motion library's selector writes `motion_plan.json`
(as before; with a current Visual Plan it takes the on-screen TEXT and the MOTION HINTS from `visual_planning.json`: `build_composition.ts --visual-plan`, set by `pipeline._motion_flags`), then
`backend/motion_planning.py` checks it and writes `motion_planning[_9x16].json`. A plan with an error stops the step before Motion Generation (`StepError`). Same inputs = the same plan.
- **Contract** (`PlanM`, `extra=forbid`): `project` (mode, aspect, size, fps), `timing_policy` (seconds; frame = floor(seconds x fps + 0.5), the end frame is exclusive and after the start), `visual_plan` (file, fingerprint),
  `scenes[]` (`scene_id` = the Visual Plan's, `timing` in seconds + frames + source, `motion_intent`, `elements[]` (source element id, registry id, `resolved | fallback | unresolved`), `sequence[]` (actions: phase
  establish -> reveal -> enter -> emphasis -> exit, preset + registry entry, start/end, frames, `depends_on` = "starts no earlier than", timing source, reason), `transition_out`, `continuity`, notes), `reuse`, `output`,
  `stages[13]`, `validation` (errors block, warnings do not), `repairs`, `tests`. Old projects (no Visual Plan) still plan and say so (warning `visual_plan_missing`).
- **Registry**: only ids of `npx tsx scripts/motion_list.ts` (41 text, 8 exits, 8 emphasis, 52 graphics, 12 masks) and the transition list; nothing is invented. A Visual Plan element the library cannot draw on its own is a recorded
  fallback (`element_fallback`), a required text that is not in the plan is an error (`required_text_missing`).
- **Hints**: `select.ts` `intentPool` maps the Visual Plan's motion hints (flow/route, connect, emphasize, locate, data) to placed graphics; the FIRST hint that has a graphic wins.
- **The 13 boxes** (page `/p/<id>/step/motion_plan`, table `/plan`, scene JSON `/plan/<scene_id>`): Motion Plan Reader, Element Resolver, Preset Registry Lookup, Effect Reuse Engine, Animation Builder,
  Animation Engine Adapter, Composition & Transition Builder, Timing & Audio Sync, Layout Validator, Code & Plan Validator, Motion Test Runner (`motion_checks.ts`, cached by the library source), Error Repair Handler
  (only mechanical repairs: clamp a time, replace an unknown id by a calm one; each recorded), Remotion Output Adapter. API: `GET /motion-planning`, `POST /motion-planning/run` (planning only).
- **Solve warnings** (button on the Motion Planning page when the plan has warnings; `POST /motion-planning/fix-warnings`; no Claude call): `motion_planning.solve`
  - moves a placed graphic that lies on a text to the nearest place (same size, inside the margin) that touches NO text (neither the Visual Plan's planned area nor `drawn_box`, where the renderer really draws it, computed by
    `build_composition.ts` with the same rules as `MotionTextLayer`; the width is the library's estimate, an upper bound) and NO other placed graphic. No such place = the graphic stays and the warning stays (`kept`);
  - starts a text that is on screen too briefly earlier: the reading time (`reading_need`) must be on screen BEFORE its exit starts (`reading_end`, not the end of the scene), never before the scene starts or while the previous transition runs;
    no room = reported (`kept`), the scene boundaries are never broken;
  - accepts the recorded fallbacks (the library has no diagram graphic): they stay in the scene JSON as `info` "still NOT drawn", `warning_fix.not_drawn` counts them, and the plan is never reported as "solved" while any is left.
  The decisions are in `motion_fixes.json`; `build_composition.ts --fixes` applies them to the plan AND the composition; `warning_fix` in the plan lists the changes. Other warnings (repeated preset, text missing from the Visual Plan) are untouched.
  A text without `until` has no rendered exit: its exit action only marks the latest time the reading may run (the scene transition removes the text). `motion-build` refuses a checked plan that is out of date or has errors.
  Reverse it by moving `motion_fixes.json` away and running Motion Planning again (the fingerprint includes the file; without it `motion_plan.json` is exactly the selector's own plan).
- **Positioned texts and emphasis time:** every text has a `drawn_box`, also a text with its own `pos` (the quote_type pattern: `pos` is its top-left corner, `center` puts it in the middle); measured against the real renderer
  (ink of the frame with and without the text) the estimate is the same width or wider, never narrower. The emphasis of a marked word is, by default, a placeholder (the text's start + 0.25 s / pace): the library does not know the
  transcript, and the English text has no word timings. `motion_planning.align_emphasis(pdir, aspect, [{scene, text, word}])` records the decision that the marked word is spoken as the transcript word `word`: the time becomes the
  start of that word if it lies inside the scene, after the text has entered and early enough (0.4 s) to be seen before the text leaves, else `MotionError` and nothing is written. It goes to `motion_fixes.json`
  (`scenes[id].emphasisAt[text index]` + a `changes` record of kind `emphasis_aligned`), applied by `build_composition.ts --fixes`; Motion Planning has to run again. "Solve warnings" keeps the entry.
- **Drawn elements** (`VIDEO_ENGINE/remotion/src/motion/diagram.ts`, run by `build_composition.ts` in motion-only mode with a Visual Plan; plan v2): the elements the placed graphic cannot draw are built from existing primitives: a disc (`shape` layer, `shape:circle`), habitat domes (`shape` layer kind `dome`, `shape:dome`: 1 to 5 half-discs on one base line, the tallest in the middle, each with a lit window arch, `count` / `window` / `fill`; geometry in `src/components/domeGeometry.ts`, repeated by `motion_generation.rect_of_layer`; stands as low in the safe area as the free space allows, in the element's own `appearance` colours), a lucide icon (`icon:rocket`, `icon:users`, `icon:book-open`) and the link graphics (`dashed-flow`, `route-line`, `timeline-dots`, `node-network`). Every layer carries the element id (`elementId`); `motion_plan.json` has `diagram` per scene (`placed`, `skipped` with the reason, `moved`, `replaced`) and each text its `drawn_box`. Statuses: `resolved`, `approximate` (a stand-in: a generic people icon for astronaut silhouettes, a dashed line without its fade; shown as "Drawn as a stand-in"), `fallback` (not drawn: no primitive draws it, or no free place was found; the reason is recorded), `unresolved`. The nodes sit in a free strip next to the text (planned area, `drawn_box`, frames, pattern icons avoided; portrait safe area in 9:16), on the ends of a `route-line`, or on the dots of a `timeline-dots` (three or more stops replace the planner's grid-lines, recorded). A box decided by "Solve warnings" is kept. Nothing free = nothing drawn, with the reason. `motion_list.ts` lists `primitives` and `region_boxes` (equal to `visual_planning.REGION_BOX`, tested). Known: the `shape` circle is drawn with its centre at `from + (r, r)`; the builder compensates.
- **Picture divider:** `split_two` marks its divider `role: "picture-divider"`; the motion-only build drops it (it only separates two pictures).
- Error classes: `schema_invalid`, `unknown_registry_id`, `invalid_timing`, `dependency_cycle`, `required_text_missing`, `mode_asset_conflict`, `unsupported_parameter`, `no_safe_fallback`, `visual_plan_not_current`.
- Tests: `python -m pytest tests/test_motion_planning.py` (19), frontend `pipeline_ui.test.tsx` (Motion Planning page / steps).

## Motion Generation: the checked composition `motion_generation.json` (13 stages)
Roadmap `improvements/Motion_Generation_Complete_Roadmap`. The step `motion-build[-9x16]` builds the composition from the checked plan (`build_composition.ts`, as before), builds it a second time (must be
byte-identical) and checks it with `backend/motion_generation.py` (descriptors), `motion_gen_rules.py` (the rules), `motion_gen_report.py` (build / finish / load / blockers). Input: `motion_planning.json` (the plan
must be current and without errors) and `motion_plan.json`. No Claude call, no code from the plan is executed, presets only from the real registry. The report is `motion_generation[_9x16].json`.
- **Stages** (page `/p/<id>/step/motion_gen`, table `/output`, scene JSON `/output/<scene_id>`): 1 Plan Reader (plan current, mode / aspect / fps, scene counts), 2 Element Resolver (every planned element has a layer; recorded
  fallbacks stay "NOT drawn"), 3 Preset Registry (text, exit, emphasis, graphic, primitive, transition ids; lucide icon names), 4 Effect Reuse (nothing outside the registry), 5 Animation Builder (one descriptor per layer with
  component, preset, props, seconds and frames, linked to the planned action; a planned action that is not built = error; start and box as planned), 6 Engine Adapter (a registered component per layer type; no clock or
  `Math.random` in the animation code: `scripts/motion_validate.ts`), 7 Composition Builder (scene intervals as planned, unique ids, no element drawn twice, transitions known / not repeated / fit), 8 Audio Sync (frames by the one
  rule inside the scene, emphasis on a spoken word = warning, audio file, duration), 9 Layout Validation (safe area of the aspect, no graphic or node on a drawn text, nodes apart), 10 Code Validation (the renderer's zod schema, no
  code-like text, parameter ranges), 11 Motion Testing (`motion_checks.ts`, the repeat build), 12 Error Repair (a time outside its scene is clamped, a box outside the safe area is moved inside, same size; at most 2 passes, each recorded),
  13 Remotion Adapter (the composition is written, read back and compared; motion-only has no pictures). A box is complete only after its output is persisted.
- **Gate:** `motion_branch.complete` needs a current report without errors (a project without a report is not blocked). `motion-build` refuses a plan that is stale or has errors.
- **API:** `GET /motion-generation` (409 `motion_generation_missing`), `POST /motion-generation/run` (409 `motion_plan_missing` / `motion_plan_not_current`; only the build, label `motion-gen[-9x16]`).
- **Descriptor ids:** the plan may give one element id to a text and to the graphic chosen for its hint, so every descriptor has its own `descriptor_id`.
- Tests: `python -m pytest tests/test_motion_generation.py` (9), frontend `pipeline_ui.test.tsx` (Motion Generation page / table / steps).

## Motion & Timeline Validation: Stage 10 (`motion_timeline_validation.json`, 12 checks)
Roadmap `improvements/Motion_Timeline_Validation_Complete_Roadmap`. Between Motion Generation and the Timeline Build: "is this motion output valid, current and safe to build a timeline from?" **Read-only**
(`backend/motion_validation.py` core and gate, `motion_validation_rules.py` the 12 checks, `motion_validation_preview.py` the optional stills); it writes only its own report and never edits, repairs or moves an
upstream artifact, never calls a model and never executes plan code. It does NOT validate a timeline that is not built: it says "timeline readiness" (the pre-render check after the build is the post-build validation).
- **Checks** (page `/p/<id>/step/motion_validation`): 1 Input Reader & Provenance, 2 Fingerprint & Freshness (Visual Plan, Scene Segmentation, motion plan, generation report, composition digest, renderer), 3 Scene Mapping &
  Coverage (one planned scene per canonical scene, canonical times, pauses), 4 Timing & Frames (the one rule `floor(s x fps + 0.5)`, parents, gaps, exits, text readable before its exit), 5 Element Completeness (per element:
  `drawn`, `approximate`, `accepted_not_drawn`, `missing`, `optional_missing`), 6 Animation & Preset Validity, 7 Layout & Collision (the renderer's drawn boxes where known, "unknown" says so), 8 Audio & Text Sync (emphasis
  vs spoken words in ms, 60 ms as the project's own tolerance), 9 Transition & Continuity Readiness, 10 Buildability & Determinism (renderer schema, read-back, the repeat build Motion Generation recorded; no dry build, it would
  overwrite the composition), 11 Preview Validation, 12 Readiness Gate.
- **Readiness:** `ready` / `ready_with_warnings` / `needs_review` / `blocked` / `stale` / `failed`. Any error or blocker = blocked; a required visual that is not drawn is a BLOCKER (accepted in Solve warnings is NOT a
  decision about it); an unresolved review warning (collision, safe margin, readability, audio length) = needs_review; other warnings or a check that could not be verified = ready_with_warnings. A report made from other
  inputs reads `stale`; a validator that crashed leaves a `failed` report, never the old green one; an input that changes while it runs gives `stale`.
- **Exceptions** (`motion_validation_exceptions[_9x16].json`): only for a missing required visual or a review warning, never for an error or another blocker. Name, reason (>= 10 characters), and the exact fingerprint of
  the report; it ends when any input changes; the finding stays in the report as `accepted_for_version` (not fixed); withdrawing keeps the record.
- **Cache:** every check has a fingerprint of ITS inputs (invalidation map in `STAGE_INPUTS`); an unchanged check keeps its result (recorded as a cache hit); `force` redoes all; a new rule set version invalidates all.
- **Preview** (explicit `Generate Preview`, never part of a run): quarter-size Remotion stills at entry / mid / pre-exit of every scene and mid-transition, decoded and measured; four separate facts: generated, technical
  checks passed, stills looked at by a person, motion watched by a person (recorded with name, time, composition).
- **Gate:** the motion-only `motion-validate` step runs it (a missing or stale report is made first) and stops on blocked / needs_review / failed; `motion_branch.blockers` (image-mode Continue, Render Video) needs a
  current ready report. Projects without the motion branch are not gated. Projects without Scene Segmentation / a stored Visual Plan (made before they existed) are checked against their scene plan and say so as warnings.
- **API:** `GET /motion-timeline-validation` (409 `motion_validation_missing`), `POST .../run?force=`, `POST .../preview`, `GET .../preview/<png>`, `POST .../preview/review`, `POST .../findings/<id>/exception`,
  `DELETE .../exceptions/<id>`. Tests: `python -m pytest tests/test_motion_validation.py` (27), frontend `pipeline_ui.test.tsx` (Motion & Timeline Validation page / steps).

## Find a preset
`cd remotion && npx tsx scripts/motion_list.ts` prints every preset as JSON: id, label, category, description (text, graphics, masks, exits, emphasis).

| Group | Count | Categories |
|---|---|---|
| Text entrances / typography (`textPresets.ts`) | 41 | entrance, reveal (mask / clip / wipe / split / directional), typography (char / word / line, typewriter, tracking), kinetic (scatter, split and reassemble), depth (layered, outline to solid, gradient sweep, underline) |
| Text exits | 8 | fade, slide, blur, scale, grow, wipe, tracking, drop |
| Keyword emphasis | 8 | scale, colour, underline, glow, colour fill, tracking, pulse, highlighter stroke |
| Graphics (`graphics.tsx`) | 50+ | line, shape, frame, connect (nodes, arrows, callouts), hud (targeting, scan, radar), cinematic (light, particles, dust, vignette), data (bars, rings, donut, counters, charts), map (pin, route, location) |
| Masks / transitions (`masks.ts`) | 12 | shape wipes (iris, blinds, stripes, corner), directional, split screen, layered strips, spotlight |

## Layers (composition JSON)
- `motion_text`: `text, style (headline | caption | label | quote), preset, exitPreset, emphasis, mark, emphasisAt[], at, until, dir, k, seed, pos?`
- `motion_gfx`: `preset, at, dur, box [x,y,w,h] (fractions), label, value, data[], color, dir, k, seed`
- `motion_scene`: `items[]`, several independent layers in one scene. Item: `kind (text | gfx | reveal), preset, start, end, enterDur, exitDur, delay, group, z, box, boxTall, bleed, pulseAt[]` plus the fields above. `reveal` shows a layer (`content`) through a mask transition.
- `background`: `colors [a, b]`, optional `look` (`gradient` default | `aurora` | `mesh` | `spotlight`), `seed`, `k` (light strength, default 1). The look comes from the scene mood (`lookFor` in `src/patterns/index.ts`: dramatic/tense = spotlight, hopeful/majestic = mesh, calm/sad = aurora; other or no mood = plain gradient, no field written). CSS radial gradients only; lights are derived from the secondary colour (the accent stays for highlights). Add a look: extend `BACKGROUND_LOOKS` and `Background.tsx`, then `lookFor`.
Times are seconds on the audio timeline (frame = seconds x fps). Boxes are fractions of the frame, so one description works for 16:9 and 9:16 (`boxTall` overrides in a tall frame).

## Rules the code enforces
- Every word of the script is always drawn and in order; presets only change HOW it is revealed. After its entrance a text is fully visible (tested for every preset, English and Telugu).
- Telugu is never split inside a cluster. Per-letter presets are not used on Telugu: the preset falls back to its word-level fallback (`TextPreset.fallback`).
- Keyword emphasis starts at the spoken time (`emphasisAt`, from the scene's keyword times); before that the word is plain.
- Layout (`layout.ts`): items stay inside the safe margin (and, in 9:16, above the bottom 16% that phone apps cover); readable items that are visible at the same time are moved apart; a text is never dropped.
- Variety (`select.ts`): the preset depends on role, importance, mood, pattern and the text; never the previous scene's preset; unsuitable presets (long text, Telugu) fall back to a calm one. The "random" choices come from a seeded hash of the plan, so they are reproducible.
- Decorations (`motion_scene` added by `integrate.ts`): at most two per scene, none on busy patterns (grids, collages, timelines, charts) or scenes under 2.4 s.

## Add a preset
Text: add a `P(...)` entry in `textPresets.ts` (pure function of `p`, the eased progress). Graphic: add a `G(...)` entry in `graphics.tsx` (draws SVG in a w x h box from `p`, `f`, `t`, `seed`). Add its place to `SLOT` in `select.ts` if it is a decoration. Run the checks below.

## Tests
- `npx tsx scripts/motion_checks.ts`: 90+ pure checks (timing, visibility, Telugu, determinism, bounds, selection, integration).
- `python -m pytest tests/test_motion_library.py`: the switch, the schema, and real renders of every preset at 1920x1080 and 1080x1920 (ink inside the safe area, nothing before the start frame, identical pixels for the same frame).

## Timeline Build (Stage 11, `backend/timeline_build.py`)
Builds `timeline[_9x16].json` + `timeline_build_report[_9x16].json` from the current composition, Scene Segmentation, motion plan, Motion Generation report and audio, then validates the BUILT object (not the plan). Never approves, never renders.
- **Gate:** Motion Planning and Motion Generation current, Stage 10 `ready` / `ready_with_warnings` (read now). A blocked build is a stopped job; the last good pair is kept; the attempt is in `timeline_build_attempt.json`.
- **Time:** one rule `motion_planning.fr` = floor(s x fps + 0.5) (= the renderer's Math.round); half-open `[start_frame, end_frame)`; the duration is what the renderer produces (`round(duration x fps)`), an audio tail it cuts off (< 1 frame) is a disclosed warning, more is a blocker.
- **Gaps:** source seconds kept; policy `hold_previous_scene` (the scene holds through the pause, Motion Planning's rule); a hole nothing covers is a blocker. **Transitions:** explicit window `[next scene start, + applied frames)`; the renderer's silent clamp and its fallback to `fade` are warnings / blockers here.
- **Publish:** temp write -> read back -> same canonical digest -> inputs fingerprinted again -> backup of the last good pair (`timeline_backup/`) -> atomic replace under the store's per-project lock. Fingerprint = every input + Stage 10 verdict + policies + this module.
- Chains: Motion-Only `timeline` ends with `timeline-build`; `POST /timeline-build/run` = `motion-validate` + `timeline-build` (with pictures only this route builds it: the image chain is unchanged). API: `GET /timeline-build`, `GET /timeline-build/timeline`, `POST /timeline-build/run`. Page: `/p/<id>/step/timeline`.
- Not done here: Timeline Approval (it does not yet name the timeline fingerprint), rendering, watching the motion.

## Timeline Approval (Stage 12, `backend/timeline_approval.py`)
An explicit human decision about ONE exact timeline version (Motion-Only projects; with pictures the earlier version-hash approval of `timeline_gate.py` stays). It never builds, repairs, edits or renders anything and never approves by itself.
- **Version:** `fingerprint` = the published timeline's digest + Stage 11's source fingerprint + render flags / remotion config. The status (not_ready / ready_for_review / changes_requested / approved / stale / approval_error) is recomputed from the stored record and the CURRENT inputs every time; any change makes an approval `stale` (kept in the history).
- **Ready for review needs:** Stage 11 current and coherent, Stage 10 ready, Motion Generation current, the pre-render check passed, and review stills PROVEN to depict this composition (manifest composition identity, renderer, sampling rule, every still's hash / decode / non-blank, every scene covered).
- **Decision** (`POST /timeline-approval/decision`): approved / changes_requested / withdrawn, with the reviewed `expected_fingerprint` + `review_id`, the person's name (recorded as `self_declared`: no accounts), an idempotency key and an acknowledgement of EVERY material limitation (warnings, drawn-as-stand-in approximations, required visuals not drawn, accepted exceptions, and the review coverage nobody has). Written, read back and verified; voided if the version moves during the write; refused (nothing recorded) when the version changed, a job runs, or an acknowledgement is missing. Changes requested blocks that version until a new build.
- **Review coverage** (what a PERSON did) comes only from the Stage 10 review route; the page shows stills (quarter size, a proxy), no motion playback exists for review. Acknowledging removes no warning from any report.
- **Audio tail** is measured on the wav (cut seconds, whether the cut part holds signal, where speech ends), not assumed.
- **Render gate:** `timeline_gate.render_blockers` / `require_approved` use it; the final render step checks again at its start and right before rendering (`pipeline._approval_still_holds`; preview renders are exempt). Files: `timeline_approval_history[_9x16].json` (append-only events), `timeline_review[_9x16].json` (review manifest). API: `GET /timeline-approval`, `POST /timeline-approval/review|decision|notes`. Page: `/p/<id>/step/approval`.

## Render Video (Stage 13, `backend/render_video.py`)
Renders EXACTLY the approved timeline version into a verified final video (Motion-Only projects; with pictures the earlier render path is unchanged). It reuses the Remotion renderer (`render.render(..., out=)`); it never edits the timeline, never approves anything, never declares the video acceptable.
- **Gate:** the Stage 12 approval is checked at the route (`timeline_gate.render_blockers`), at the start of the step, immediately before the job reserves its input (check + reservation are one guarded step), after the renderer finishes and before publishing. A stale approval, a changed input during the render, an unsupported setting (profile, size, fps, missing audio, tool, disk) stops it by name.
- **Lifecycle:** manifest (`render_manifest[_9x16].json`: approval id / version, timeline fingerprint, settings, expected frames = the renderer's own rule, renderer version, the limitations the approver acknowledged) -> render to `out.rendering-<job>.mp4` -> verify the encoded file (readable, mp4 / h264, exact size and fps, frame count, duration within 0.15 s, audio stream present and as long as the audio file) -> publish atomically (the previous good video is kept as `out.previous.mp4`; a failed publish puts it back and keeps the verified temp file) -> read the published file back -> `render_report[_9x16].json` (expected vs observed, sha256, `final_qc_status: pending`).
- **Honest state** (`GET /render-video`): not_ready / ready / running (phase, frames) / completed / stale / failed / cancelled / interrupted / unverified_output; a job file that says "rendering" while nothing runs is `interrupted`; a video without a report is never a candidate; a newer failed attempt is shown next to the still-current last good video. The step's progress is at most 90 % while frames render; verification and publishing come after.
- **Cancel** (`POST /render-video/cancel`): cooperative; `cancel_requested` until the job ends; nothing is published. The Remotion process itself is only killed with `A2V_CANCEL=1` (existing switch); otherwise the render finishes and its output is discarded.
- No resume: Remotion has no checkpoints that bind to identical inputs, so a retry renders again to a fresh temp file (the log and the failure of the earlier attempt are kept in the job file).

## Final QC (Stage 14, `backend/final_qc.py`)
Judges the ACTUAL rendered file (the verified candidate of Stage 13). Read-only; no LLM; it never renders, edits the video or approves a timeline. 14 internal stages: run initialization, artifact and manifest, provenance and approval, file integrity, stream and metadata, video decode (full decode of the video stream with black / frozen detection), duration and frame accounting, audio integrity (decode, peak / clipping, silence inside the narration, speech not cut off), A/V sync (container start offsets; content sync and emphasis moments are `requires_review` / `not_run`, never passed), frame quality (first, last, every scene at 12 / 50 / 90 %, around every cut, every transition start / middle / end), scenes and transitions, upstream reconciliation (stand-ins, elements not drawn, accepted limitations carried from the approved timeline: shown, not judged from pixels), human review, report and delivery gate.
- **Statuses:** blocked > failed > needs_review > passed_with_warnings > passed. `passed*` only after a person records a decision about THIS file's sha256 and states they watched it with sound; frames are evidence, not playback. `approved_with_accepted_risks` must name every open warning with a reason (kept visible, `accepted_with_reason`). A new video, a changed approval or a new rules version makes the report stale; a decision on an old hash is refused.
- **Cache:** the media evidence is kept in the report per stage, keyed by candidate hash + rules version + profile + tool versions + manifest; the same file is not decoded twice. Files: `final_qc_report[_9x16].json`, `final_qc_review[_9x16].json` (append-only), `final_qc_frames[_9x16]/`. API: `GET /final-qc`, `POST /final-qc/run|cancel|review`, `GET /final-qc/findings/{id}`, `GET /final-qc/frame/{name}`. Only the `standard` profile is implemented (the roadmap's quick / release are not).
- The delivery gate (`final_qc.gate`) is what a later delivery stage must ask; Stage 15 is not started.
