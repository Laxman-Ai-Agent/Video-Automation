# Phase 0 — Current Architecture Audit Report

- **Audit Date / Time:** 2026-10-16T06:26:00+05:30
- **Repository Root:** `E:\audio-to-video`
- **Branch / HEAD:** `agents-building` / `f6989b1` (`feat(pipeline): implement mandatory LLM review gate, motion codegen, and solver fix`)
- **Initial Git Status Summary:** Working tree clean on branch `agents-building`
- **Project ID / State Inspected:** `projects/test-02-510e` (Motion-only, aspect 16:9, `reusable_motion_templates: false`, 56.3s audio, reached Motion Planning with 0 warnings & LLM review passed)
- **Audit Mode:** Strict Read-Only (no source code modified, no pipeline executed, no test rerun)

---

## 1. Executive Summary

- **Current Architecture:**
  The Dark World Video Generation Agent is a hybrid Python/FastAPI backend paired with a React/Vite dashboard and a frame-accurate Remotion TypeScript video rendering engine. The pipeline operates in two modes: **Image Mode** (parallel Image and Motion branches) and **Motion-Only Mode** (bypasses Asset Collection and Image Generation).
  Recent enhancements have established a **13-stage sequential dashboard workflow**, implemented a **mandatory structured LLM review gate** across all stages (`backend/llm_review.py`), split Motion Generation into **Motion Template Selection** (`backend/motion_template_selection.py`) and **Motion Animation** (`backend/motion_animation.py`) with support for custom React/TSX code generation, and resolved layout solver collision bugs in Motion Planning (`backend/motion_planning.py`).

- **Main Verified Gap:**
  While stage execution, data contracts, and LLM review gates are fully implemented in procedural backend modules, they are not yet unified under a centralized **Common Agent Runtime & Registry**. The 14 logical agents exist as backend Python functions, route handlers, and CLI steps rather than standardized, isolated Agent abstractions with formal tool definitions, shared memory, and explicit lifecycle hooks.

- **Highest Risks:**
  1. *Staging Area Contention in Custom Code Mode:* `backend/motion_animation.py` stages generated TSX components to `remotion/src/generated/`. Concurrent project renders could overwrite active scene files if multiple renders run simultaneously.
  2. *Unverified LLM Hallucinations on Edge Prompts:* In custom code mode, complex LLM-generated React components could introduce runtime render exceptions if typecheck passes but visual logic contains division-by-zero or NaN frame math.
  3. *Audio Analyzer & Scene Segmentation Modification Risk:* Strict user instructions freeze Audio Analyzer and Scene Segmentation. Future orchestration changes must avoid touching these frozen stages.

- **Recommended Phase 1:**
  Implement the **Common Agent Runtime & Registry** (`Phase 1`) by wrapping existing backend stage handlers and review gates into standardized Agent classes without rewriting working pipeline code.

---

## 2. Current Dashboard Pipeline Table

The active Dashboard displays a sequential flowchart of **13 stages** (defined in `frontend/src/pipeline/layout.ts` and rendered via `frontend/src/pipeline/PipelineChart.tsx`). When `use_images: false` (Motion-Only mode), `collection` and `images` are skipped and hidden from the canvas.

| Order | UI Stage Name | Internal ID | Trigger / Endpoint | Handler / Function | Inputs | Outputs | LLM Role | Deterministic Checks | Next Consumer | Status / Evidence |
|:---:|---|---|---|---|---|---|---|---|---|---|
| **1** | Audio Input | `audio` | Upload `/audio-input` or `POST /projects` | `backend/routes/uploads.py:receive`, `store.py:new_project` | Source audio (.mp3, .wav) | `audio.mp3`, `audio_16k.wav`, `project.json`, `.audio.sha1` | **Review Gate**: verifies file presence, size & narration feasibility | FFmpeg downsampling to 16kHz mono WAV; FFprobe duration check; SHA-1 hash | Audio Analyzer | `Verified Fact` (`routes/uploads.py`) |
| **2** | Audio Analyzer | `analyzer` | Auto-advance or `POST /projects/{id}/transcribe` | `backend/pipeline.py:_transcribe`, `_refine`, `_cuts`, `audio_analysis.py` | `audio_16k.wav`, `vocabulary.txt` | `transcript.json`, `cuts.json`, `audio_analysis.json`, `transcript_review.json` | **Decision**: Claude loanword & vocabulary check; **Review Gate**: transcript accuracy | Whisper monotonicity, silence detection (-32dB, 0.4s), 14 audio metrics probe | Scene Segmentation | `Verified Fact` (Frozen, `transcribe.py`) |
| **3** | Scene Segmentation | `segmentation` | Auto-advance or `POST /projects/{id}/segmentation/run` | `backend/scene_segmentation.py:run` | `transcript.json`, `audio_analysis.json` | `scene_segmentation.json`, `scene_llm_cache.json` | **Decision**: Claude proposes scene boundaries; **Review Gate**: narrative coherence | 7-stage validation: word-boundary snapping, 3.0–12.0s duration, 0 gaps/overlaps | Visual Planning | `Verified Fact` (Frozen, `scene_segmentation.py`) |
| **4** | Visual Planning | `planning` | Auto-advance or `POST /projects/{id}/visual-planning/run` | `backend/autoplan.py:_plan`, `backend/visual_planning.py:assemble` | `scene_segmentation.json`, `transcript.json`, `cuts.json` | `visual_planning.json`, `scene_plan.json`, `prompts_map.json`, `translation.json` | **Decision**: Narration translation (Telugu -> English), visual concepts & prompts; **Review Gate**: prompt coverage | 8-pass schema validation, safe area region validation (`REGION_BOX`), link checks | Motion Planning | `Verified Fact` (`visual_planning.py`) |
| **5** | Motion Planning | `motion_plan` | Auto-advance or `POST /projects/{id}/motion-planning/run` | `remotion/scripts/build_composition.ts --plan-only`, `backend/motion_planning.py:build`, `solve()` | `scene_plan.json`, `visual_planning.json`, `motion_fixes.json`, `audio.mp3` | `motion_plan.json`, `motion_planning.json`, `.motion_checks.json` | **Review Gate**: evaluates typography rhythm, reading duration, transitions & emphasis alignment | 13-stage validation, safe area bounds, text overlap detection, solver repositioning | Motion Template Selection | `Verified Fact` (`motion_planning.py`) |
| **6** | Motion Template Selection | `motion_template` | Auto-advance or `POST /projects/{id}/motion-template/run` | `backend/motion_template_selection.py:build_selection` | `motion_planning.json`, `scene_plan.json`, `project.json` | `motion_template_selection.json` | **Decision**: ON evaluates & selects templates; OFF establishes custom code route; **Review Gate**: routing audit | Template verification against repository code references (`TEMPLATE_IMPLEMENTATION_REFS`) | Motion Animation | `Verified Fact` (`motion_template_selection.py`) |
| **7** | Motion Animation | `motion_gen` | Auto-advance or `POST /projects/{id}/motion-animation/run` | `backend/motion_animation.py:generate_custom_motion_code` (OFF) or `build_composition.ts` (ON) | `motion_template_selection.json`, `visual_planning.json`, `scene_plan.json` | `motion_animation.json`, `composition.json`, `projects/<pid>/generated_motion/scene_*.tsx`, `remotion/src/generated/*` | **Review Gate**: evaluates TSX code quality, element coverage & compile diagnostics | AST/regex check against prohibited presets, TypeScript typecheck (`tsc --noEmit`), SHA-256 source hashing | Motion & Timeline Validation | `Verified Fact` (`motion_animation.py`) |
| **8** | Motion & Timeline Validation | `motion_validation` | Auto-advance or `POST /projects/{id}/motion-validation/run` | `backend/motion_validation.py:run`, `backend/motion_gen_rules.py` | `composition.json`, `motion_animation.json`, `motion_planning.json`, `resource-library` | `motion_timeline_validation.json`, `motion_preview_report.json`, preview stills | **Review Gate**: synthesizes 12 validation check findings | 12 technical check rules, offline resource resolution against `resource-library/catalog/registry.json` | Timeline Build | `Verified Fact` (`motion_validation.py`) |
| **9** | Timeline Build | `timeline` | Auto-advance or `POST /projects/{id}/timeline-build/run` | `backend/timeline_build.py:run` | `composition.json`, `motion_timeline_validation.json`, `audio_16k.wav` | `timeline.json`, `timeline_build_report.json` | **Review Gate**: reviews timeline track assembly, frame accounting & audio tail | Total frame duration equals audio duration, zero transition frame gaps, digest matching | Timeline Approval | `Verified Fact` (`timeline_build.py`) |
| **10** | Timeline Approval | `approval` | Explicit Human Action (`POST /projects/{id}/timeline-approval/decision`) | `backend/timeline_approval.py:decide` | `timeline.json`, `timeline_build_report.json`, human decision payload | `timeline_approval_history.json`, updated `project.json` | **Pre-Approval Audit**: executive quality audit; cannot substitute for human approval | Approval tied to exact timeline SHA-256 fingerprint; invalidated on upstream changes | Render Video | `Verified Fact` (Mandatory Human Gate, `timeline_approval.py`) |
| **11** | Render Video | `render` | Auto-advance after human approval or `POST /projects/{id}/render-video/run` | `backend/render_video.py:run`, `backend/render.py:render` | `composition.json`, `timeline.json`, `timeline_approval_history.json`, audio file | `out.mp4`, `render_manifest.json`, `render_report.json` | **Review Gate**: verifies render telemetry, media profile & duration consistency | Headless Chrome render on dynamically assigned free port; FFprobe validation (H.264/AAC streams) | Final QC | `Verified Fact` (`render_video.py`, `render.py`) |
| **12** | Final QC | `qc` | Auto-advance from Render or `POST /projects/{id}/final-qc/run`, `POST .../confirm` | `backend/final_qc.py:run`, `backend/final_qc.py:confirm` | `out.mp4`, `render_report.json`, `timeline.json` | `final_qc_report.json`, `qc_frames/*.jpg` | **Review Gate**: technical synthesis of probe and human confirmation | Automated probe (black frames, freeze frames, audio clipping, A/V sync) + human playback sign-off | Final Video Delivery | `Verified Fact` (`final_qc.py`) |
| **13** | Final Video | `final` | Derived State upon QC pass | `backend/pipeline_view.py:build`, `backend/final_qc.py:gate` | `out.mp4`, `final_qc_report.json` | Verified `out.mp4` download delivery | **Review Gate**: delivery provenance audit confirming complete upstream approval trail | Output file exists, matches SHA-256 hash in QC report, zero blocking QC defects | End User / Delivery | `Verified Fact` (`pipeline_view.py`) |

---

## 3. Logical Agent Inventory (14 Target Agents)

| Target Agent | Existing Implementation / Handler | Actual LLM Duties | Tools / Services | Input / Output Contracts | Status | Gaps |
|---|---|---|---|---|---|---|
| **A01: Main Orchestrator** | `backend/pipeline.py`, `backend/routes/pipeline.py`, `backend/pipeline_view.py` | None directly; orchestrates LLM review invocations across steps | Job queue, step graph, auto-advance rules, safe stop guard | Reads project state; writes job status & step checkpoints | `Partial` | Procedural code in routes/pipeline rather than an isolated Agent class. |
| **A02: Audio Input Agent** | `backend/routes/uploads.py`, `backend/store.py`, `backend/llm_review.py` | Narration feasibility and audio parameter review | FFmpeg, FFprobe | Audio stream -> `audio.mp3`, `audio_16k.wav`, `project.json` | `Implemented` | Operates as route handler rather than Agent instance. |
| **A03: Audio Analyzer Agent** | `backend/transcribe.py`, `backend/transcript_review.py`, `backend/cuts.py`, `backend/audio_analysis.py`, `backend/llm_review.py` | Phonetic loanword detection, transcript review | Faster-Whisper, FFmpeg silencedetect, Claude CLI | `audio_16k.wav` -> `transcript.json`, `cuts.json`, `audio_analysis.json` | `Implemented` (Frozen) | None (Frozen by policy). |
| **A04: Scene Segmentation Agent** | `backend/scene_segmentation.py`, `backend/llm_review.py` | Semantic chunking and boundary proposition | Claude CLI / LLM client, regex | `transcript.json`, `audio_analysis.json` -> `scene_segmentation.json` | `Implemented` (Frozen) | None (Frozen by policy). |
| **A05: Visual Planning Agent** | `backend/autoplan.py`, `backend/visual_planning.py`, `backend/llm_review.py` | Telugu-to-English translation, visual concepts, prompt generation, review | Claude CLI / LLM client, Pydantic schemas | `scene_segmentation.json` -> `scene_plan.json`, `visual_planning.json`, `prompts_map.json` | `Implemented` | Needs wrapping into formal Agent interface. |
| **A06: Motion Planning Agent** | `backend/motion_planning.py`, `remotion/scripts/build_composition.ts --plan-only`, `backend/llm_review.py` | Kinetic typography and timing review | TypeScript Remotion selector, heuristic collision solver | `visual_planning.json`, `scene_plan.json` -> `motion_plan.json`, `motion_planning.json` | `Implemented` | Code lives in procedural module. |
| **A07: Motion Template Selection Agent** | `backend/motion_template_selection.py`, `backend/llm_review.py` | Template recommendation in ON mode; custom code routing in OFF mode; review | LLM client, registry cross-referencer | `motion_planning.json`, `project.json` -> `motion_template_selection.json` | `Implemented` | Standalone module; ready for Agent interface. |
| **A08: Motion Animation Agent** | `backend/motion_animation.py`, `remotion/src/generated/*`, `backend/llm_review.py` | Custom code review, TSX source generation audit | Remotion AST builder, `tsc --noEmit`, TypeScript compiler | `motion_template_selection.json` -> `scene_*.tsx`, `composition.json`, `motion_animation.json` | `Implemented` | Staging concurrency isolation needs hardening. |
| **A09: Motion & Timeline Validation Agent** | `backend/motion_validation.py`, `backend/motion_gen_rules.py`, `backend/llm_review.py` | Synthesis of 12 validation check rules | Resource Library validator, Remotion probe | `composition.json` -> `motion_timeline_validation.json` | `Implemented` | Standalone module. |
| **A10: Timeline Build Agent** | `backend/timeline_build.py`, `backend/llm_review.py` | Structural track assembly and transition integrity review | Python timeline compiler | `composition.json`, validation report -> `timeline.json`, `timeline_build_report.json` | `Implemented` | Standalone module. |
| **A11: Timeline Approval Agent** | `backend/timeline_approval.py`, `backend/timeline_gate.py`, `backend/llm_review.py` | Pre-approval executive quality audit | Human gate validator, SHA-256 fingerprint checker | `timeline.json` -> `timeline_approval_history.json` | `Implemented` | Human approval gate is strictly enforced. |
| **A12: Render Video Agent** | `backend/render_video.py`, `backend/render.py`, `backend/llm_review.py` | Post-render media profile and telemetry review | Remotion renderer, headless Chrome, FFprobe | `timeline.json`, `composition.json` -> `out.mp4`, `render_report.json` | `Implemented` | Standalone module. |
| **A13: Final QC Agent** | `backend/final_qc.py`, `backend/llm_review.py` | Technical QC review synthesis | FFprobe filtergraph, OpenCV frame sampling, Human sign-off | `out.mp4` -> `final_qc_report.json`, `qc_frames/*.jpg` | `Implemented` | Dual automated + human gate enforced. |
| **A14: Final Video Delivery Agent** | `backend/pipeline_view.py`, `backend/final_qc.py`, `backend/llm_review.py` | Delivery provenance and integrity audit | File streamer, SHA-256 verification | `out.mp4`, `final_qc_report.json` -> verified video delivery | `Implemented` | Integrated into pipeline view and final gate. |

---

## 4. LLM Decision / Review Matrix

All 13 stages implement a mandatory structured review gate via `backend/llm_review.py`. If the LLM review fails, times out, or returns blockers, the stage fails closed (`status="blocked"` or `"failed"`), preventing progression.

| Stage | LLM Decision Role | LLM Review Role | Persisted Review Evidence | Technical Validator | Failure Behavior | Verification Status |
|---|---|---|---|---|---|---|
| `audio` | None (Deterministic upload) | Evaluates narration feasibility and acoustic parameters | `llm_review_audio.json` | FFprobe, FFmpeg conversion | Fails closed (`status="blocked"`), disables downstream advance | `Verified Fact` |
| `analyzer` | Corrects vocabulary & loanwords without altering timestamps | Audits Telugu vs English phonetic spelling & cut continuity | `llm_review_analyzer.json` | Whisper timestamps, FFmpeg silencedetect | Fails closed; displays review retry button in UI | `Verified Fact` |
| `segmentation` | Proposes semantic scene boundary groupings | Audits narrative coherence, scene balance, duration limits | `llm_review_segmentation.json` | 7-stage validator: word boundary snapping, 0 gap/overlap | Fails closed; halts automatic progression | `Verified Fact` |
| `planning` | Translates narration, creates visual concepts & prompts | Audits thematic diversity, prompt coverage, hierarchy | `llm_review_planning.json` | 8-pass schema validation, safe area region validation | Fails closed; blocks planning approval | `Verified Fact` |
| `motion_plan` | None (Deterministic Remotion plan selector) | Evaluates kinetic typography pacing, reading duration & layout | `llm_review_motion_plan.json` | 13-stage validator, collision solver (`solve()`) | Fails closed; safe stop triggered after 5 failed autofixes | `Verified Fact` |
| `motion_template` | Recommends compatible existing templates (ON mode) | Audits template compatibility (ON) or custom code routing (OFF) | `llm_review_motion_template.json` | Code reference cross-check against repository files | Fails closed; rejects invalid template fallback in OFF mode | `Verified Fact` |
| `motion_gen` | None (Generates AST/TSX programmatically) | Audits generated React/TSX source code quality & element coverage | `llm_review_motion_gen.json` | Regex scan for prohibited presets, `tsc --noEmit` check | Fails closed; compilation error stops pipeline | `Verified Fact` |
| `motion_validation` | None (Deterministic technical validation) | Synthesizes 12 validation check results into safety verdict | `llm_review_motion_validation.json` | 12 technical check rules, offline Resource Library resolution | Fails closed; blocks timeline build if blockers exist | `Verified Fact` |
| `timeline` | None (Deterministic frame-timeline assembly) | Audits composition assembly, frame accounting & audio tail | `llm_review_timeline.json` | Frame duration equality check, gap/overlap zeroing | Fails closed; blocks opening Timeline Approval | `Verified Fact` |
| `approval` | None (Mandatory Human Approval) | Pre-approval executive quality audit for human reviewer | `llm_review_approval.json` | SHA-256 timeline fingerprint check; human signature | LLM audit informs human; human approval remains mandatory | `Verified Fact` |
| `render` | None (Remotion headless Chrome render) | Evaluates render telemetry, media profile & duration matching | `llm_review_render.json` | FFprobe video/audio stream verification, exit code check | Fails closed; blocks Final QC if render fails | `Verified Fact` |
| `qc` | None (Automated probe + human confirmation) | Synthesizes automated probe metrics & human playback notes | `llm_review_qc.json` | Automated black/freeze/clipping probe + human sign-off | Fails closed; blocks final video delivery if QC rejected | `Verified Fact` |
| `final` | None (Delivery verification) | Audits end-to-end delivery provenance and approval trail | `llm_review_final.json` | SHA-256 hash match against QC report, file presence | Fails closed; download refused if provenance incomplete | `Verified Fact` |

---

## 5. Motion Pipeline Code Generation Trace

| Step | Actual Artifact | Creator Function | Consumer | Executable TSX? | Evidence / Status |
|---|---|---|---|:---:|---|
| **Visual Planning** | `visual_planning.json`, `scene_plan.json` | `backend/autoplan.py`, `backend/visual_planning.py:assemble` | Motion Planning | No | `Verified Fact` (`visual_planning.py`) |
| **Motion Planning** | `motion_plan.json`, `motion_planning.json` | `backend/motion_planning.py:build`, `solve()` | Motion Template Selection | No | `Verified Fact` (`motion_planning.py`) |
| **Motion Template Selection** | `motion_template_selection.json` | `backend/motion_template_selection.py:build_selection` | Motion Animation | No | `Verified Fact` (`motion_template_selection.py`) |
| **Motion Animation** | `motion_animation.json`, `composition.json`, `scene_*.tsx` | `backend/motion_animation.py:generate_custom_motion_code` (OFF) or `build_composition.ts` (ON) | Motion Validation, Remotion engine | **Yes (in OFF mode)** | `Verified Fact` (`backend/motion_animation.py`) |
| **Motion Validation** | `motion_timeline_validation.json`, `motion_preview_report.json` | `backend/motion_validation.py:run` | Timeline Build | Validates TSX / composition | `Verified Fact` (`motion_validation.py`) |
| **Timeline Build** | `timeline.json`, `timeline_build_report.json` | `backend/timeline_build.py:run` | Timeline Approval | Mounts TSX layers in timeline | `Verified Fact` (`timeline_build.py`) |
| **Timeline Approval** | `timeline_approval_history.json` | `backend/timeline_approval.py:decide` (Human gate) | Render Video | Locks fingerprint of TSX/timeline | `Verified Fact` (`timeline_approval.py`) |
| **Render Video** | `out.mp4`, `render_manifest.json`, `render_report.json` | `backend/render_video.py:run`, `backend/render.py` | Final QC | Chrome executes TSX in Remotion | `Verified Fact` (`render_video.py`, `render.py`) |
| **Final QC** | `final_qc_report.json`, `qc_frames/*.jpg` | `backend/final_qc.py:run`, `confirm()` (Human gate) | Final Video Delivery | Validates final rendered MP4 | `Verified Fact` (`final_qc.py`) |

### Answers to Mandatory Motion Pipeline Questions:

1. **Does Motion Generation emit descriptor JSON, executable source, or both?**
   - **Both (`Verified Fact`).**
   - When `reusable_motion_templates: true` (ON mode), it emits descriptor JSON (`composition.json`, `motion_animation.json`) utilizing pre-existing Remotion motion components.
   - When `reusable_motion_templates: false` (OFF mode / Custom Code Mode), it generates **real, executable React/TSX source code** (`scene_*.tsx`) for every scene and emits a normalized `composition.json` manifest registering them.

2. **Where is generated source saved?**
   - In two locations (`Verified Fact` in `backend/motion_animation.py` lines 358–365):
     a) Per-project directory: `projects/<pid>/generated_motion/scene_<id>.tsx`
     b) Remotion build tree: `remotion/src/generated/scene_<id>.tsx` and `remotion/src/generated/index.ts`

3. **How does Timeline Build / Remotion load it?**
   - `remotion/src/generated/index.ts` exports `customSceneRegistry` and a wrapper component `CustomSceneLayer` (`Verified Fact` in lines 385–409).
   - In `remotion/src/Composition.tsx`, when a scene layer has `type: "custom_scene"`, Remotion dynamically instantiates `CustomSceneLayer`, which looks up the scene component by ID and mounts the generated React TSX component into the composition.

4. **What is proven for template ON and OFF modes?**
   - **ON Mode (`Verified Fact`):** `backend/motion_template_selection.py` invokes LLM to evaluate scene concepts and maps them to verified registry entries (`TEMPLATE_IMPLEMENTATION_REFS`). Emits `status="selected"`, `mode="template"`.
   - **OFF Mode (`Verified Fact`):** `backend/motion_template_selection.py` emits `status="skipped_by_configuration"`, `mode="custom_code"`, `routing_decision="custom_code_generation"`. Hands off to `backend/motion_animation.py:generate_custom_motion_code()`, which generates scene TSX, scans for and strictly rejects prohibited preset imports (`scan_prohibited_presets()`), stages files, runs `npm run tsc` (`tsc --noEmit`), and writes `motion_animation.json`. Unit tests in `tests/test_mandatory_llm_gate.py` pass 100%.

5. **What remains unknown?**
   - Performance and memory limits for rendering >50 concurrent custom TSX scenes on low-spec CPU environments remain unmeasured.

---

## 6. Skills, Shared Data, Memory, Registry, Runtime & Resources

| Area | Existing Path | Actual Behavior | Recommendation | Evidence / Status |
|---|---|---|---|---|
| **Skills** | `.claude/` (worktree only) | No runtime agent skills directory exists; contains only an old git worktree (`.claude/worktrees/`). | Create runtime `skills/` directory in Phase 4 for standardized agent procedures. | `Verified Fact` (No runtime skills folder exists) |
| **Shared Data** | `projects/*/` | Project-specific data is kept isolated in `projects/<pid>`. No global shared input directory exists. | Maintain strict project isolation; introduce read-only global shared prompts/style-kits in Phase 4. | `Verified Fact` |
| **Memory** | `projects/*/asr_llm_cache.json`, `scene_llm_cache.json` | Stage-specific caching for LLM requests (ASR corrections, scene chunking). No cross-project memory. | Introduce structured, verified learning promotion in Phase 9. | `Verified Fact` |
| **Registry** | `backend/motion_planning.py:registry()`, `remotion/scripts/motion_list.ts` | Programmatic in-memory dictionaries of motion graphics, typography presets, transitions, and Tabler icons. | Consolidate into unified `registry/` in Phase 1. | `Verified Fact` |
| **Runtime** | `backend/pipeline.py` (Job runner, `@step` decorators) | In-process Python background threads and subprocess execution. | Wrap into formal Agent Runtime in Phase 1. | `Verified Fact` |
| **Resource Library** | `resource-library/` (`catalog/registry.json`, `assets/`, `licenses/`), `backend/resource_library.py` | Extensive production module with SHA-256 hash validation, offline resolution, and license tracking. | **Preserve and reuse as-is.** Do not duplicate. | `Verified Fact` (`backend/resource_library.py`) |

---

## 7. Current Project State (`test-02-510e`)

- **Last Completed Stage:** Motion Planning (`motion_plan`) with 0 warnings and LLM review passed (`status="passed"`, score 0.88).
- **First Pending Stage:** Motion Template Selection (`motion_template`).
- **Current Fingerprints / Stale Outputs:** `motion_timeline_validation.json` in `test-02-510e` is stale (it reflects an older run prior to the solver fix).
- **Exact Missing Artifacts:** `timeline.json`, `timeline_build_report.json`, `timeline_approval_history.json`, `out.mp4`, `final_qc_report.json`.
- **Root Cause of Historical Safe Stop:**
  In `scene_04`, `'grid-lines'` collided with the planned area for `'Final testing'`. The solver's `crowded()` obstacle check failed to exclude the full-screen decorative border `'frame-in'`, falsely treating the entire canvas as occupied. This bug was fixed in commit `f6989b1` by excluding framing elements ($\text{area} \ge 0.5$ or `category == "frame"`).
- **No Pipeline Rerun Performed:** **Yes.** Audit was conducted in 100% read-only mode.

---

## 8. Existing Tests & Verification History

| Test Suite | File Path | Existing Evidence / Results | Rerun Required? | Reason |
|---|---|---|:---:|---|
| **Mandatory LLM Gate** | `tests/test_mandatory_llm_gate.py` | **7 / 7 passed** (2026-10-16T06:07:19) | No | Verified fail-closed gates, fingerprint invalidation, and custom TSX codegen. |
| **Pipeline Gate** | `tests/test_pipeline_gate.py` | **13 / 13 passed** (2026-10-16T06:07:19) | No | Verified image gates, approval idempotency, and restart survival. |
| **Motion Planning** | `tests/test_motion_planning.py` | **33 / 33 passed** (2026-10-16T06:10:23) | No | Verified 13 motion stages, collision solver, and autofix loop ceiling. |
| **Frontend Typecheck** | `frontend/` (`npm run typecheck`) | **0 errors** (2026-10-16T06:10:33) | No | Clean TypeScript compilation for all dashboard cards and LLM badges. |

---

## 9. Gap & Risk Register

| ID | Gap / Risk | Evidence | Impact | Proposed Phase | Priority | Confidence |
|:---:|---|---|---|:---:|:---:|:---:|
| **G01** | Agent abstractions exist only as procedural backend functions | `backend/pipeline.py`, `backend/routes/pipeline.py` | High maintenance overhead, lacks standard agent lifecycle & interfaces | Phase 1 | High | Verified Fact |
| **G02** | Staging contention for custom TSX code in Remotion build directory | `remotion/src/generated/scene_*.tsx` is shared across projects | Multiple concurrent renders could overwrite active scene components | Phase 5 | Medium | Verified Fact |
| **G03** | Frozen Audio Analyzer and Scene Segmentation stages | User non-negotiable instruction | Accidental edits to frozen files would violate user constraints | All Phases | Critical | Verified Fact |
| **G04** | Centralized skills, memory, and policy directories do not exist | Directory inspection of root | Agents cannot discover modular skills or shared cross-project rules | Phase 4 | Medium | Verified Fact |
| **G05** | Complex custom TSX code could experience Remotion runtime frame errors | Remotion Chrome execution | Syntactically valid TSX might crash during render if math is invalid | Phase 5 | High | Inference |

---

## 10. Recommended Phases 1–10 Implementation Order

1. **Phase 1: Common Agent Runtime & Registry (`Recommended Next`)**
   - Wrap existing backend modules into 14 formal Agent classes inheriting from a `BaseAgent` interface.
   - Create `agent-system/registry/` to register agent capabilities, schemas, and tools without rewriting backend pipeline logic.
   - *Exit Gate:* 14 agents instantiated, mapped to existing endpoints, 100% existing tests passing.
2. **Phase 2: LLM Gateway & Mandatory Review Consolidation**
   - Formalize `backend/llm_review.py` into a unified `agent-system/llm_gateway/` with configurable model routing and fail-closed gates.
3. **Phase 3: State, Artifact Contracts & Recovery**
   - Standardize JSON schemas under `agent-system/schemas/` and unify fingerprinting logic.
4. **Phase 4: Central Skills & Shared Memory**
   - Establish `agent-system/skills/` for procedural stage workflows and structured memory caching.
5. **Phase 5: Motion Agents & Multi-Project Staging Hardening**
   - Isolate custom TSX build staging so concurrent project builds do not clash in `remotion/src/generated/`.
6. **Phase 6: Audio & Visual Agents Integration**
   - Wire Audio Input and Visual Planning agents into the new runtime (keeping Audio Analyzer and Scene Segmentation strictly frozen).
7. **Phase 7: Timeline, Render & QC Agents Integration**
   - Wire Timeline Build, Approval, Render, and QC agents into the new runtime, maintaining mandatory human approval gates.
8. **Phase 8: Main Orchestrator & Monitoring**
   - Replace procedural route advancement with an event-driven `MainOrchestratorAgent`.
9. **Phase 9: Evaluation & Verified Self-Learning**
   - Add regression evaluation benchmarks and supervised knowledge promotion.
10. **Phase 10: E2E & Production Hardening**
    - Run complete end-to-end integration tests across both Image Mode and Motion-Only Mode.

---

## 11. Unknowns & Decisions Requiring User Input

1. **Agent Directory Location:**
   Should the new Agent system live under `backend/agents/` (extending the existing FastAPI backend) or under a root `agent-system/` directory? *(Recommendation: `backend/agents/` to maintain clean Python package imports without altering build paths).*
2. **Remotion Staging Strategy:**
   Should custom TSX code be dynamically imported from project directories or staged into project-namespaced subdirectories in `remotion/src/generated/<pid>/`? *(Recommendation: Namespaced subdirectories to support concurrent builds).*

---

## 12. Phase 0 Safety Confirmation

- **Source code modified:** **No** (0 source files altered during Phase 0)
- **Runtime config modified:** **No**
- **Pipeline run / restarted:** **No** (No pipeline step was triggered)
- **Generated project artifacts modified:** **No** (`projects/` remained untouched)
- **Dependencies installed:** **No**
- **Tests rerun:** **No** (Existing test logs and recorded results were inspected)
- **Commit / reset / checkout / stash / clean performed:** **No**

---

## 13. Phase 1 Recommendation

- **Proposed Scope:**
  Define the `BaseAgent` class, implement the 14 logical Agent wrappers around existing backend stage handlers, and establish the agent registry under `backend/agents/`.
- **Explicit Exclusions:**
  Do NOT modify Audio Analyzer (`backend/transcribe.py`, `backend/transcript_review.py`) or Scene Segmentation (`backend/scene_segmentation.py`). Do NOT alter Remotion render components or existing frontend UI.
- **Acceptance Criteria:**
  1. Base agent contract defines `execute()`, `validate()`, and `review()` methods.
  2. All 14 logical agents are registered with declared tools, inputs, and outputs.
  3. Existing pipeline execution remains 100% backward compatible.
  4. All existing tests (33 motion planning, 7 LLM gate, 13 pipeline gate) continue to pass.
- **Rollback / Safety Plan:**
  All Phase 1 code will be additive within the new `backend/agents/` package, allowing immediate fallback to direct route handlers if any issue arises.
