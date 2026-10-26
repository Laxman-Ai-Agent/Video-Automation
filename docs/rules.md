# Rules of the stages

341 deterministic rules. Each one has an ON / OFF switch on the **Rules** page of the app (`config/rule_switches.json`): a rule that is OFF is never evaluated by its stage, so it cannot block or warn, and the stage's LLM reviewer is told it is off.
This list is generated from the stages' own source by `SYSTEM/policies/rule_catalog.py`; the Rules page is always current, this file is a snapshot (2026-10-26).

| Stage | Rules |
|---|---|
| Visual Planning (`planning`) | 45 |
| Motion Planning (`motion_plan`) | 41 |
| Motion Generation (`motion_gen`) | 51 |
| Motion & Timeline Validation (`motion_validation`) | 69 |
| Timeline Build (`timeline`) | 73 |
| Render Video (`render`) | 11 |
| Final QC (`qc`) | 46 |
| Asset Collection (`assets`) | 5 |

## Visual Planning (`planning`) - 45 rules

| Rule | Severity | What it checks |
|---|---|---|
| `beats_inside_parent` | error | …: beat … (…-… s) is not inside its scene (…-… s) |
| `beats_on_words` | warning | …: beat … (…-… s) does not start and end on spoken words |
| `beats_ordered` | error | …: the beats are not in order or repeat an id |
| `concept_consistent` | warning | …: the concept speaks of ONE figure but … elements show figures (…): the concept and the elements must describe the same picture |
| `element_count` | warning | … has … elements: clutter |
| `element_ids_unique` | error | element ids repeat in …: … |
| `gap_after` | error | …: gap_after_seconds is … but Scene Segmentation has … s between … and the next scene |
| `gaps_preserved` | error | …: the pause before the scene is … s but Scene Segmentation has … s |
| `hierarchy` | warning | …: a supporting element has a higher priority than the primary one |
| `layout_overlap` | warning | …: … share an area of the frame |
| `media_query_brand` | warning | …: a search query of … holds '…', a brand or a word made from one: name only what is visible |
| `media_query_english` | error | …: the search query '…' of … must be 2 to 6 plain English words |
| `motion_not_presets` | warning | …: a motion hint names presets or timing |
| `mover_on_path` | warning | …: … is not related (follows) to the path it moves along |
| `narration_present` | warning | … has no narration text from the source |
| `no_conflicting_intervals` | error | … starts before the scene before it ends |
| `no_overlapping_timeline` | error | …: its timeline interval starts before the scene before it ends |
| `no_placeholders` | error | …: an element still holds a placeholder value (placement, id, text or description) |
| `numbers_grounded` | - | …: '…' has a number that is not in the narration |
| `ordered` | error | … starts before the scene before it |
| `palette` | warning | …: an element uses a colour that is not in the project palette |
| `path_connected` | warning | …: the path … joins … element(s): a path connects at least two places |
| `path_element` | warning | …: … travels across the frame but the scene has no path element to travel along |
| `plan_interval` | error | …: plan_start/plan_end …-… s are not the canonical …-… s of … (the pause after a scene is not part of it) |
| `primary_element` | error | … has no primary element |
| `real_media_count` | warning | … has … real pictures or clips (at most …) |
| `real_media_with_meaning` | warning | …: a real picture or clip is the primary element and nothing drawn (text, graphic, diagram, chart) says what the narration means |
| `references_valid` | error | …: a relationship, motion hint or beat names an element that the scene does not have |
| `regions` | error | …: placement regions … are not supported regions |
| `required_element` | warning | … has no required element |
| `scene_count` | error | the plan has … scenes, the scene plan … |
| `source_mapping_unique` | error | two planned scenes map to the same Scene Segmentation scene |
| `source_scene_count` | error | source scene count |
| `text_capacity` | error | … has … on-screen text elements (…) but its pattern '…' draws …: keep the … most important and put the other words into the description of the graphic they belong to |
| `text_content` | error | …: text element … has no content |
| `text_grounded` | warning | …: '…' is mostly not from the narration |
| `text_not_narration` | warning | …: the on-screen text repeats the narration |
| `text_over_primary` | warning | …: the text … shares its area of the frame with the primary visual |
| `text_safe_area` | warning | …: text is placed over the whole frame instead of a safe area |
| `text_short` | warning | …: '…' is too long for an on-screen label |
| `timeline_interval` | error | …: the timeline interval …-… s is not the canonical scene plus the pause up to the next scene (…) |
| `timing` | error | …: the times …-… s differ from the source …-… s |
| `variety` | warning | … repeats the concept of the scene before it |
| `word_events_inside_scene` | error | …: word animation event … (…-… s) is outside scene (…-… s) |
| `word_events_target_valid` | error | …: word animation event … targets unknown element '…' |

## Motion Planning (`motion_plan`) - 41 rules

| Rule | Severity | What it checks |
|---|---|---|
| `action_in_scene` | error | …: … runs …-… s, outside the scene …-… s |
| `adapter_fields` | error | an action lacks the fields the Remotion layer needs |
| `aspect_matches` | error | the motion plan is for …, not … |
| `composition_current` | info | the composition on disk was built from an earlier plan: Motion Generation has to run again |
| `dependencies_exist` | error | …: an action depends on an action that does not exist |
| `dependency_acyclic` | error | …: the actions depend on each other in a circle |
| `dependency_order` | warning | …: an action starts before the action it depends on |
| `diagram_clear_of_drawn_text` | warning | …: … (…) lies on the text '…' where the renderer draws it |
| `diagram_element_exists` | error | …: … is drawn but is not an element of the Visual Plan |
| `diagram_in_safe_area` | warning | …: … (…) reaches outside the safe area |
| `emphasis_inside_text` | error | …: the emphasis of '…' at … s is outside its visible time |
| `frames_valid` | error | …: … has frames …-… |
| `graphic_clear_of_drawn_text` | warning | …: '…' lies on the text '…' where the renderer draws it |
| `graphic_clear_of_text` | warning | …: '…' overlaps the area planned for the text '…' |
| `graphic_in_safe_area` | warning | …: the box of '…' reaches outside the safe area |
| `ids_unique` | error | action ids are not unique |
| `intensity_range` | warning | …: the intensity … of '…' is outside 0.3-2.0 |
| `min_duration` | warning | …: the exit of '…' lasts … s (shortest … s) |
| `mode_matches` | error | the motion plan was made for '…' but Use Images is … |
| `mode_requirement` | error | …: a Motion-Only plan has a picture |
| `motion_checks` | error | the motion library's own checks failed: … |
| `motion_checks_ran` | warning | the motion library's checks could not run: … |
| `no_code` | error | the plan contains code-like text: … |
| `registry_id` | error | …: '…' is not a … preset of the installed registry |
| `repeat_graphic` | warning | …: the placed graphic repeats the previous scene's |
| `repeat_text_preset` | warning | …: the main text uses '…' again, as the previous scene did |
| `scene_animated` | error | …: the scene has nothing that moves (no text, no graphic and no picture) |
| `scenes_linked` | error | scenes linked |
| `scenes_present` | error | the motion plan has no scenes |
| `speed_range` | warning | …: the pace … of '…' is outside 0.5-2 |
| `telugu_safe_preset` | error | …: the preset '…' cannot draw Telugu text ('…') |
| `text_count` | warning | …: … animated texts (at most 2 keep a scene readable) |
| `text_readable` | warning | …: '…' is on screen … s before it starts to leave but needs about … s to be read |
| `text_style` | error | …: the text style '…' is not one of … |
| `transition_fits` | error | …: the transition lasts … s but must be …-… s to fit between the scenes |
| `transition_known` | error | …: the transition '…' is not in the transition library |
| `transition_not_repeated` | error | …: the transition '…' repeats the previous scene's |
| `transition_present` | warning | …: no transition into the next scene (hard cut) |
| `variety` | warning | only … different text presets in … scenes |
| `visual_plan_current` | error | the Visual Plan is not current: … |
| `visual_plan_present` | warning | this project has no Visual Plan: the elements of the scenes cannot be traced to it |

## Motion Generation (`motion_gen`) - 51 rules

| Rule | Severity | What it checks |
|---|---|---|
| `action_built` | error | …: the planned action … (…) is not in the composition |
| `aspect_matches` | error | plan …, composition …x…, project … |
| `audio_file` | - | the composition refers to audio '…' which is not in the project |
| `box_matches_plan` | error | …: … sits at … but the plan says … |
| `component_registered` | error | the renderer has no component for the layer type(s) …: they would be skipped |
| `descriptor_ids_unique` | error | …: two descriptors have the same id |
| `deterministic` | error | a second build of the same plan gave a different composition |
| `deterministic_ran` | warning | the repeat build was not run |
| `duration_is_audio` | warning | the last scene ends at … s, the audio is … s |
| `element_drawn` | warning | …: … (…) is planned as drawn but the composition has no layer for it |
| `emphasis_on_a_word` | warning | …: the emphasis of '…' at … s is not on a spoken word |
| `fallback_recorded` | warning | …: the fallback of … has no reason |
| `fps_matches` | error | the plan is … fps, the composition … fps |
| `frame_driven` | error | animation code that depends on a clock or Math.random: … |
| `frames_in_scene` | error | …: … runs frames …-…, outside the scene …-… |
| `graphic_clear_of_text` | warning | …: '…' lies on the text '…' |
| `graphic_in_safe_area` | warning | …: '…' reaches outside the safe area |
| `icon_exists` | error | the icon '…' does not exist in lucide: the renderer would draw nothing |
| `intensity_range` | warning | …: the intensity … of '…' is outside 0.3-2.0 |
| `min_duration` | warning | …: … … s of '…' is shorter than … s |
| `mode_flags` | error | the composition says motion=…, motionOnly=… but Use Images is … |
| `mode_matches` | error | the plan is for '…' but Use Images is … |
| `motion_checks` | error | the motion library's own checks failed: … |
| `motion_checks_ran` | warning | the motion library's checks could not run: … |
| `no_code` | error | the composition contains code-like text: … |
| `no_new_presets` | error | presets that are not in the registry were used: … |
| `no_pictures_in_motion_only` | error | … picture layer(s) in a Motion-Only composition |
| `node_clear_of_text` | warning | …: … lies on the text '…' |
| `node_in_safe_area` | warning | …: … reaches outside the safe area |
| `nodes_apart` | warning | …: … and … overlap |
| `one_owner` | error | …: … is drawn by two layers |
| `plan_current` | error | the checked motion plan is out of date: run Motion Planning again |
| `plan_present` | error | motion_planning.json is missing: run Motion Planning first |
| `plan_without_errors` | error | the motion plan has … blocking error(s) |
| `registry_id` | error | …: '…' is not a … preset of the installed registry |
| `renderer_schema` | error | the composition does not satisfy the renderer's schema: … |
| `resource_resolves` | error | resource resolves |
| `scene_count` | error | … planned scenes, … in motion_plan.json, … in the composition |
| `scene_ids_unique` | error | two scenes have the same id |
| `scene_interval` | error | …: the composition has …-… s but the plan has …-… s |
| `scenes_in_order` | error | …: starts before the previous scene ends |
| `scenes_present` | error | the composition has no scenes |
| `speed_range` | warning | …: the pace … of '…' is outside 0.5-2 |
| `text_in_safe_area` | warning | …: the text '…' is drawn outside the safe area |
| `timing_matches_plan` | error | …: … starts at … s but the plan says … s |
| `transition_as_planned` | error | …: the plan says '…', the composition '…' |
| `transition_fits` | error | …: the transition lasts … s, it must be …-… s |
| `transition_known` | error | …: the transition '…' is not in the transition library |
| `transition_not_repeated` | error | …: the transition '…' repeats the previous scene's |
| `validator_ran` | warning | validator ran |
| `z_order_defined` | error | …: a layer has no numeric z-order |

## Motion & Timeline Validation (`motion_validation`) - 69 rules

| Rule | Severity | What it checks |
|---|---|---|
| `animation.loop_valid` | error | …: … has a duration of … s |
| `animation.no_untrusted_execution` | blocker | the plan or composition contains code-like text, which is never executed: … |
| `animation.order_deterministic` | error | …: the order of its animations changes between two reads |
| `animation.preset_supported` | blocker | the preset registry could not be read: … |
| `animation.properties_supported` | warning | …: the text '…' has a style, intensity or duration the animation engine does not support |
| `animation.resource_resolves` | blocker | animation: resource resolves |
| `audio.duration_compatible` | warning | the last scene ends at … s, the audio is … s |
| `audio.required_present` | blocker | the composition refers to the audio '…', which is not in the project |
| `audio.sync_associations_valid` | error | the pace is not the same everywhere (it would be applied twice or not at all): … |
| `codegen.hash_valid` | blocker | …: source SHA-256 mismatch (modified on disk) |
| `codegen.manifest_valid` | blocker | Motion Animation manifest is missing or not generated |
| `codegen.source_exists` | blocker | …: generated TSX source does not exist at … |
| `composition.assets_resolve` | error | …: a Motion-Only composition has … picture layer(s) |
| `composition.descriptors_complete` | error | …: its animations are not those Motion Generation reported, or a planned action is not built |
| `composition.deterministic` | error | two builds of the same plan gave different compositions (recorded by Motion Generation) |
| `composition.inputs_current` | blocker | composition.json is not the composition Motion Generation validated and wrote |
| `continuity.motif_notes_valid` | warning | …: its continuity notes refer to a scene, graphic or text preset that does not exist |
| `element.approximation_disclosed` | warning | …: … is drawn as a stand-in and the plan does not say so |
| `element.id_unique` | error | …: two animations have the same id |
| `element.no_orphan_required` | blocker | …: the required element … is in the Visual Plan but not in the motion plan |
| `element.reference_resolves` | error | …: the planned action … points at … or at an action that does not exist |
| `element.required_has_drawable` | blocker | element: required has drawable |
| `input.approved_source` | blocker | the Visual Plan has … blocking error(s) |
| `input.exists` | blocker | the project has no audio file |
| `input.fingerprint_current` | blocker | the Visual Plan is out of date (its sources changed): run Visual Planning again |
| `input.parseable` | blocker | the … has schema …, which this validator does not support |
| `input.project_match` | blocker | the composition is …x… but the project is … |
| `layout.aspect_compatible` | error | the composition is …x…, not … |
| `layout.generated_code_contrast` | warning | …: the generated code sets no high-contrast text colour or shadow |
| `layout.generated_code_present` | error | …: the generated scene code file is missing |
| `layout.generated_code_safe_zone` | warning | …: the generated code has no safe-zone padding or centering |
| `layout.generated_code_typography` | warning | …: the generated code uses text smaller than the minimum size |
| `layout.graphic_graphic_collision` | warning | …: … and … overlap |
| `layout.inside_frame` | error | …: the text '…' is drawn partly outside the frame |
| `layout.overflow_clip` | warning | …: the text '…' is wider than the safe width and may be clipped |
| `layout.safe_margins` | warning | …: '…' reaches outside the safe area |
| `layout.text_graphic_collision` | warning | …: '…' lies on the text '…' |
| `layout.z_order_valid` | error | …: a layer has no numeric z-order |
| `policy.no_prohibited_presets` | blocker | …: prohibited reusable preset(s) imported or referenced: … |
| `preview.evidence_current` | warning | the preview was made from another composition or renderer than the current one: generate it again |
| `preview.frames_decode` | warning | …: the preview frame … is missing, changed or did not decode |
| `preview.not_blank` | warning | …: the preview frame … is blank (std …) |
| `preview.scene_sampled` | warning | …: no preview frame was made for it |
| `renderer.layer_type_registered` | blocker | the renderer has no component for the layer type(s) …: they would be skipped |
| `renderer.readback_equal` | error | the composition on disk is not its own canonical serialization |
| `renderer.schema_valid` | blocker | the composition does not satisfy the renderer's schema: … |
| `scene.count_match` | error | scene counts differ: … |
| `scene.coverage_complete` | error | Scene Segmentation scene … has no planned scene |
| `scene.id_unique` | error | two scenes of the … have the same id |
| `scene.narration_mapped` | error | …: its times …-… s are not the canonical …-… s of its narration |
| `scene.order_preserved` | error | the scene order differs between the Visual Plan, the motion plan and the composition |
| `scene.pause_policy` | error | …: the pause after the scene (…) is not held on the timeline as planned |
| `scene.source_map_unique` | error | …: its Scene Segmentation scene … is missing or used by two scenes |
| `text.content_grounded` | error | …: the text '…' is not in the approved plan |
| `text.planned_text_drawn` | - | …: the planned text '…' is not in the generated code |
| `text.safe_area` | warning | …: the text '…' is drawn outside the safe area |
| `timing.duration_valid` | error | …: it ends (… s) before it starts (… s) |
| `timing.emphasis_alignment` | warning | …: the emphasis of '…' at … s is …, not on a word boundary |
| `timing.exit_exists` | error | …: the plan gives '…' the exit '…' but the composition has '…' |
| `timing.gaps_preserved` | error | …: the planned pause (…) is not held at the end of the scene |
| `timing.no_prohibited_overlap` | error | …: the composition has …-… s, the plan …-… s |
| `timing.non_negative` | error | the composition has no valid duration or frame rate |
| `timing.readability_before_exit` | warning | …: '…' is on screen … s before it starts to leave, it needs … s |
| `timing.seconds_frames_consistent` | error | the frame rates differ: composition …, plan …, generation … |
| `timing.within_parent` | error | …: … runs frames …-…, outside its scene …-… |
| `transition.duration_feasible` | error | …: the transition lasts … s, it must be …-… s |
| `transition.first_last_defined` | error | …: the last scene has an outgoing transition and nothing to go to |
| `transition.references_valid` | error | …: it has an outgoing transition but no next scene |
| `transition.type_supported` | blocker | …: the transition '…' is not in the transition library |

## Timeline Build (`timeline`) - 73 rules

| Rule | Severity | What it checks |
|---|---|---|
| `assembly.ids_unique` | blocker | a track or item id appears twice |
| `asset.exists` | blocker | …: the picture … does not exist |
| `asset.inside_public` | blocker | …: the picture path leaves the public folder |
| `audio.composition_reference` | blocker | the composition names the audio …, the project audio is … |
| `audio.covers_video` | blocker | the audio clip does not cover the audio's own length at normal speed |
| `audio.matches_composition` | warning | the audio is … s, the composition … s |
| `audio.not_duplicated` | blocker | the audio is placed more than once |
| `audio.not_truncated` | blocker | the renderer would cut … s of the audio (more than one frame) |
| `audio.readable` | blocker | audio: readable |
| `audio.single_clip` | blocker | there is no audio clip |
| `audio.tail_quantization` | warning | the renderer's frame count (… frames = … s) is … s shorter than the audio (… s): less than one frame is cut off the end of the audio |
| `cover.every_scene_once` | blocker | a scene is dropped, duplicated or out of order |
| `cover.source_map` | blocker | the source map does not follow the scenes |
| `cover.source_times` | blocker | a scene's source times differ from the approved input |
| `freshness.motion_generation_current` | blocker | Motion Generation is not current: … |
| `freshness.motion_plan_current` | blocker | Motion Planning is not current: … |
| `freshness.required_visuals_drawn` | blocker | … required element(s) are not drawn and no exception was recorded |
| `freshness.stage10_ready` | blocker | freshness: stage10 ready |
| `gap.covered_by_policy` | blocker | …: the pause after it is not covered by the hold of the scene |
| `gap.last_scene_reaches_end` | blocker | the last scene ends … frame(s) before the end of the video |
| `gap.matches_source` | blocker | …: the pause after it is … s but the source says … |
| `gap.scenes_adjacent` | blocker | … ends at … s but the next scene starts at … s: the video has a hole or an overlap |
| `gap.starts_at_zero` | blocker | the first scene starts at frame …, not 0: the start of the video is uncovered |
| `input.audio_exists` | blocker | the project audio is missing or outside the project |
| `input.composition_shape` | blocker | the composition has no meta or no scenes |
| `input.exists` | blocker | … (…) is missing |
| `input.inside_project` | blocker | … is outside the project folder |
| `input.parses` | blocker | … is not a JSON object |
| `layer.descriptors_inside_scene` | blocker | …: … descriptor(s) lie outside the scene's frames |
| `layer.starts_inside_scene` | blocker | …: it starts at … s, outside … |
| `layer.types_registered` | blocker | the renderer has no component for the layer type(s) … |
| `mode.no_pictures` | blocker | …: a picture layer in a motion-only timeline |
| `mode.respected` | blocker | the timeline's visual mode is not the project's |
| `narration.words_inside_audio` | blocker | … word timing(s) lie outside the audio |
| `prov.fingerprint_current` | blocker | an input changed while the timeline was built |
| `prov.manifest` | blocker | the timeline does not name its policy / builder versions |
| `prov.project` | blocker | the timeline names another project |
| `ref.audio_resolves` | blocker | the audio reference does not resolve inside the project |
| `ref.composition_scene_resolves` | blocker | a composition reference does not resolve |
| `ref.descriptors_resolve` | blocker | a scene has no or duplicated Motion Generation descriptors |
| `ref.layer_counts` | blocker | a scene lost or gained a layer |
| `ref.layer_ids_unique` | blocker | a layer id appears twice |
| `scene.canonical_times_agree` | blocker | …: the motion plan's canonical times differ from Scene Segmentation |
| `scene.count_matches` | blocker | … has … scenes, the composition … |
| `scene.ids_sequential` | blocker | the composition scene ids are not 1..… in order: … |
| `scene.in_generation` | blocker | … is not in the Motion Generation report |
| `scene.in_motion_plan` | blocker | … is not in the motion plan |
| `scene.unique` | blocker | a scene appears twice |
| `settings.aspect_matches` | blocker | the composition is …x…, not … |
| `settings.consistent_with_plan` | blocker | the motion plan and the composition disagree on width, height or fps |
| `settings.mode_matches` | blocker | the composition was built for the other Use Images setting |
| `settings.valid` | blocker | the composition has no valid size/fps (…x… at …) |
| `time.contiguous_no_overlap` | blocker | the scene clips overlap, leave a hole or do not cover the video |
| `time.duration_positive` | blocker | the composition has no duration |
| `time.frames_from_seconds` | blocker | …: the frames are not the ones of the shared rule |
| `time.frames_match_generation` | blocker | …: the frames of Motion Generation and the one rule differ |
| `time.frames_match_plan` | blocker | …: the frames of the plan and the one rule differ |
| `time.gaps_preserved` | blocker | a gap lost its policy or moved a source interval |
| `time.integer_frames` | blocker | a frame value is not an integer |
| `time.interval_valid` | blocker | …: […, …) is not inside [0, …) |
| `time.layers_inside_clip` | blocker | …: a layer lies outside its scene |
| `time.narration_inside_clip` | blocker | …: the narration lies outside the scene's timeline interval |
| `time.positive_duration` | blocker | …: its interval is empty after rounding to frames |
| `trans.one_per_boundary` | blocker | two transitions at one boundary |
| `trans.scene_times_unchanged` | blocker | a transition moves a scene boundary |
| `trans.window_valid` | blocker | a transition window is invalid |
| `transition.fits_next_scene` | blocker | …: its window of … frames does not fit the next scene (… frames) |
| `transition.inside_audio` | blocker | …: its window ends after the end of the video |
| `transition.not_clamped` | warning | …: the renderer shortens it from … to … frames (the scene is only … frames long) |
| `transition.not_repeated` | warning | …: the same transition ('…') as the previous boundary |
| `transition.positive` | blocker | …: its duration … s is less than one frame |
| `transition.supported` | blocker | …: '…' is not a transition of the library (the renderer would draw a fade) |
| `visual.required_not_hidden` | blocker | a required visual is not drawn and no exception exists |

## Render Video (`render`) - 11 rules

| Rule | Severity | What it checks |
|---|---|---|
| `audio_duration` | error | the audio lasts as long as the audio file (cut at the end of the picture), within … s |
| `audio_stream` | error | the audio stream the timeline requires exists |
| `codec` | error | the video codec is as configured |
| `container` | error | the container is mp4 |
| `dimensions` | error | width and height are exactly as approved |
| `duration` | error | the duration is within … s of the frames asked for |
| `fps` | error | the frame rate is exactly as approved |
| `frame_count` | error | the frame count is what the composition asks for (the renderer's rounding, +-1) |
| `readable` | error | the container can be read |
| `size_plausible` | error | the file is not trivially small for its length |
| `video_stream` | error | a video stream exists |

## Final QC (`qc`) - 46 rules

| Rule | Severity | What it checks |
|---|---|---|
| `QC_APPROVAL_CURRENT` | - | QC APPROVAL CURRENT |
| `QC_APPROVAL_REVIEW_COVERAGE` | - | the timeline approval recorded its review coverage: stills …, motion playback … |
| `QC_ASSETS_PROVENANCE` | - | QC ASSETS PROVENANCE |
| `QC_ASSET_RIGHTS_REVIEW` | review | QC ASSET RIGHTS REVIEW |
| `QC_AUDIO_ANALYSIS` | - | no audio stream to analyse |
| `QC_AUDIO_DECODES` | - | QC AUDIO DECODES |
| `QC_AUDIO_LEVEL` | error | the loudness could not be measured |
| `QC_AUDIO_NOT_BEYOND_VIDEO` | - | audio … s, video … s (… s) |
| `QC_AUDIO_SILENCE` | warning | silence …-… s is after the last spoken word (… s) |
| `QC_AUDIO_STREAM` | - | audio stream … (… by the render manifest) |
| `QC_AV_CONTENT_SYNC` | review | whether the narration lands on its scene cannot be measured automatically (no reliable detector): the Final QC LLM review judges it from the evidence |
| `QC_BLACK_RUN` | warning | black from … s to … s (at least … s) |
| `QC_CANDIDATE_RESOLVED` | blocker | …, … bytes |
| `QC_CANDIDATE_STABLE` | - | QC CANDIDATE STABLE |
| `QC_CONSTANT_FRAME_RATE` | - | QC CONSTANT FRAME RATE |
| `QC_DIMENSIONS` | - | …x… (expected …x…), aspect … |
| `QC_DURATION` | review | the duration could not be read |
| `QC_EMPHASIS_ON_WORD` | review | the rendered emphasis moments were not measured against the spoken words (no pixel/audio detector); the planned emphasis times were aligned to words upstream |
| `QC_FILE_HASH_MATCHES_RENDER` | - | QC FILE HASH MATCHES RENDER |
| `QC_FILE_NONEMPTY` | - | … bytes, sha256 … |
| `QC_FIRST_FRAME` | - | QC FIRST FRAME |
| `QC_FRAMES_EXTRACTED` | - | … of … sampled frames decoded (frame sampling, not playback) |
| `QC_FRAME_GEOMETRY` | - | QC FRAME GEOMETRY |
| `QC_FRAME_RATE` | - | … fps (expected …/1) |
| `QC_FROZEN_RUN` | warning | the picture does not change from … s to … s (at least … s) |
| `QC_LLM_REVIEW` | review | QC LLM REVIEW |
| `QC_MANIFEST_MATCHES_RENDER` | - | QC MANIFEST MATCHES RENDER |
| `QC_MANIFEST_PRESENT` | blocker | the render manifest is missing: the expected settings are unknown and are not guessed |
| `QC_PROBE_READABLE` | blocker | the file cannot be probed: … |
| `QC_RESOURCE_LINEAGE` | blocker | this render predates the resource manifest: resource lineage cannot be checked |
| `QC_RUN_STARTED` | - | profile …, rules version … |
| `QC_SCENE_NOT_BLANK` | error | …: every sampled frame is flat (std < …): the scene looks blank |
| `QC_SCENE_ORDER_AND_COVERAGE` | review | all … scenes were sampled in timeline order; that the right content is in the right scene is judged by the Final QC LLM review (frames below) |
| `QC_SCENE_SHOWS_CHANGE` | review | …: the first and last sampled frames of this … s scene are identical (difference …): a static scene or a frozen animation? |
| `QC_SPEECH_NOT_CUT` | - | QC SPEECH NOT CUT |
| `QC_STREAM_START_OFFSET` | review | the audio stream starts … ms from the video stream (container timestamps) |
| `QC_TRANSITION_NOT_BLANK` | warning | … -> … (…): the middle of the transition is flat: blank content during the transition? |
| `QC_TRANSITION_SAMPLED` | review | … -> …: … of the 3 transition frames could not be sampled |
| `QC_TRANSITION_SMOOTHNESS` | review | how smooth each transition looks is subjective and cannot be established from stills |
| `QC_UPSTREAM_ELEMENTS_COUNTED` | - | … of … planned elements were drawn exactly as planned according to Motion Generation (a plan fact, not measured on this video) |
| `QC_UPSTREAM_EMPHASIS` | - | Stage 10 reports … warning(s); … emphasis time(s) were aligned to spoken words by recorded decisions (not measured in the rendered video) |
| `QC_UPSTREAM_OPTIONAL_NOT_DRAWN` | info | … (…) is optional and was not drawn: … |
| `QC_UPSTREAM_REQUIRED_NOT_DRAWN` | blocker | … is REQUIRED and was not drawn (…): … |
| `QC_VIDEO_CODEC` | - | … (configured …), pixel format … |
| `QC_VIDEO_DECODES` | - | QC VIDEO DECODES |
| `QC_VIDEO_STREAM` | blocker | no video stream |

## Asset Collection (`assets`) - 5 rules

| Rule | Severity | What it checks |
|---|---|---|
| `asset_file` | error | a collected file is missing or changed since it was collected |
| `asset_provenance` | error | an asset has no source or no licence (a hand upload counts the user as its source) |
| `asset_rights` | error | an asset has rights class D: no licence information, it must not be used |
| `asset_rights_review` | review | an asset's rights are not established (class C): a person must confirm the use |
| `asset_authenticity` | error | an asset's authenticity is neither real nor user_provided |
