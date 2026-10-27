# Audio-to-Video Studio — Autonomous Motion-Only Pipeline Guide

Read this file first every session. Details live in `docs/`. Read ONLY the docs you need. **Latest handoff (what is done, open, next, how the user works): `docs/SESSION_STATUS.md`: read it second. Assessment, phases and every pending task: `docs/ROADMAP.md`: read it third.**

## System Purpose & Core Identity
Dark World Video Generation Agent is an autonomous, LLM-driven Motion-Only video generation system.
It converts a Telugu spoken audio narration into a broadcast-ready MP4 video using custom code-generated motion animation, kinetic typography, dynamic charts/maps, and Remotion composition.

- **Motion + Media Mix**: User image/video upload workflows and CLIP matching are permanently removed. Every video is 100% motion graphics with animation; real photographs and clips are drawn INSIDE the animated scenes (in cards, frames, bento grids, device mockups) in any amount the narration calls for: there is NO share of the video to reach and no limit on how much real media is used. The only media choice at upload is whether AI-picture prompts are wanted (`project.json` key `media` = `{"ai_images": bool}`, locked after upload; `SYSTEM/core/media_kinds.py`; shares stored by older projects are ignored). Visual Planning decides which scenes show real media; real photographs and clips enter ONLY through Stage 5 Asset Collection (licensed, with provenance) and are drawn inside generated motion scenes, with a motion fallback for every one.
- **Custom Code Mode**: Reusable motion template selections and fallbacks are permanently removed. The system unconditionally generates original, scene-specific React/TSX animation code using Remotion primitives.
- **Mandatory Quality Gates**: Every active pipeline stage is guarded by a mandatory fail-closed LLM review gate and deterministic technical checks.

## Input & Output Specifications
- **Input**: One Telugu audio narration file (`.mp3`, `.wav`, `.m4a`, `.flac`, `.ogg`, `.aac`, max 500 MB).
- **Canvas / Aspect Ratios**:
  - `9:16` Portrait (1080 × 1920) for YouTube Shorts, Instagram Reels, TikTok.
  - `16:9` Landscape (1920 × 1080) for YouTube Landscape and standard displays.
- **Framerate**: Exactly 30 fps across all compositions and rendering.
- **Duration**: Master timeline duration is mathematically locked to the spoken audio duration.

## Language Architecture
- **Spoken Narration**: Telugu (sole authority for semantic meaning, narrative pacing, emotion, and cut points).
- **Audio Analyzer & Review**: Stage 2 LLM review strictly preserves genuine Telugu vocabulary in Telugu script while converting phonetic English technical terms into standard English orthography.
- **Visual & Motion Planning**: ALL visual concepts, motion plans, kinetic typography on screen, metadata, and generated React/TSX code must be in English.
- **Subtitles**: Optional Telugu subtitles rendered with Google Font Noto Sans Telugu.

## Active 13-Stage Autonomous Pipeline
Execution sequence (strictly ordered):
1. **Audio Input** (`audio`): Audio intake, format probing, project descriptor creation.
2. **Audio Analyzer** (`analyzer`): Local faster-whisper transcription (`transcript.json`, never edited), sentence/silence cuts, and the LLM transcript review: `transcript_review.json` (vocabulary, uncertain words, corrections, alignment record) and `transcript_corrected.json` (the ONE final transcript: written whenever the LLM check succeeded, with the same words when nothing needed fixing; Telugu kept in Telugu script, English technical terms in English, corrected words re-aligned against the audio and validated). The LLM sees Whisper's word probabilities and word times as its audio evidence (it cannot hear). The stage LLM review (`llm_review_analyzer.json`) approves the final transcript automatically (no human step). The Audio Analyzer page shows raw Whisper and the final transcript side by side (`GET /projects/{id}/transcript?view=compare`). Steps `transcribe` -> `refine` -> `cuts` -> LLM approval; a finished step is reused, Whisper is never re-run for a project that has `transcript.json`.
3. **Scene Segmentation** (`segmentation`): Semantic scene boundary grouping, duration constraints (a scene shorter than the minimum, first, middle or last, joins the neighbour that gives the shorter merged scene while it stays within the maximum), narrative coherence. It consumes `transcript_corrected.json` and uses its LLM only for scene boundaries and grouping, never to correct the transcript again.
4. **Visual Planning** (`planning`): scene-by-scene design: what every scene shows and why. `autoplan.run` writes the translation and `scene_plan.json`, then `visual_planning.run` (one planner call, one repair retry, nothing derived when it fails: the stage fails with the cause) writes `visual_planning.json` 2.0: per scene the primary element (`hero`: motion / image / video), the elements (kinds are defined only in `SYSTEM/core/media_kinds.py`: text, label, icon, graphic, diagram, chart, data_visualization, background, image, video, reference; a `reference` is a screenshot of one infobox/table of a Wikipedia article for the facts and figures the narration states, its `media.query` is the article title and `media.section` is `infobox` or `table`; it is part of the image family), counts per kind, and for every real element its search queries, its motion fallback and (when AI pictures are wanted) its AI prompt (`media_requirements`); plus `media_mix` (what the plan really carries, information only: no target, no tolerance) and `totals`. Every family is always available. A plan that does not follow the current segmentation is made again (the old one is kept in `plan_backups/`). `tests/test_media_kinds.py` fails when a kind is added without its handler in every consumer.
5. **Asset Collection** (`assets`): the real photographs and video clips the Visual Plan asked for (requirements are written from `visual_planning.json`, no planner call of its own; licensed sources via `VIDEO_ENGINE/stages/stock.py`, one ranking call, ffmpeg clip preparation). The page (`GET /projects/{pid}/assets`) shows every request with its file, source and licence, or why it fell back. Writes `asset_requirements.json`, `assets_manifest.json`, `credits.json`, `assets/collected/*`. A video where no scene needs real media completes this stage with zero requirements. Rights classes: A (known free) is used; C (rights not established) is collected but listed in the Final QC report (`QC_ASSET_RIGHTS_REVIEW`) for the Final QC LLM review to judge; D (no licence) is never downloaded. Every asset keeps source URL, licence, hash and `authenticity: real`; a requirement that cannot be met falls back to the scene's generated motion graphics (recorded), and one marked `must_be_real` fails the stage with the exact cause. A requirement of kind `page` (from a Visual Plan `reference` element) is a screenshot of one infobox/table of a Wikipedia or official reference page (`VIDEO_ENGINE/stages/web_capture.py`: https only, host allowlist re-checked on every redirect hop, robots.txt honoured, no login/CAPTCHA; always rights class C). General web or news search and news-site screenshots are NOT part of this stage (they need a search API).
6. **Motion Planning** (`motion_plan`): Kinetic typography pacing, visual hierarchy, spring curve timing math, transition scheduling.
7. **Motion Animation** (`motion_gen`): Autonomous LLM synthesis of executable React/TSX animation code (`scene_*.tsx`) with Remotion primitives; collected assets are required elements the scene draws (`real_media`, skill `motion.real_media`).
8. **Motion & Timeline Validation** (`motion_validation`): 12-check deterministic validation suite (timing, layout safety, readability, prohibited presets, source hashes).
9. **Timeline Build** (`timeline`): Multi-track timeline composition assembly, transition windows, audio synchronization, frame alignment.
10. **Timeline Approval** (`approval`) [LLM-DECIDED, NO HUMAN GATE]: the LLM approval review checks the exact timeline version (timing, scenes, transitions, overlays, audio sync); only `passed` (score >= 0.80, no blockers) is recorded through the fail-closed `decide()`, then audited; a rejection rebuilds the timeline once, then fails the stage with the exact cause. Rendering starts automatically after approval (`timeline_approval.auto_approve`, step `timeline-approve`).
11. **Render Video** (`render`): Remotion multi-process video rendering, frame progress tracking, audio muxing.
12. **Final QC** (`qc`) [LLM-DECIDED, NO HUMAN GATE]: Comprehensive technical QC (ffprobe, black/freeze frames, A/V sync, audio clipping, real-asset provenance), then `final_qc.llm_decide`: the Final QC LLM review decides about the exact file (its hash) from the report and its measurements. Only `passed` (score >= 0.80, no blocker/error) approves; every open warning is named in the decision; a failed or blocked QC is never approved; an unavailable LLM records `cannot_determine` (the QC stays `needs_review`). The decision is audited by the same review (an audit that does not pass voids it). Nobody watches the video; the report says so.
13. **Final Video Delivery** (`final`): End-to-end delivery verification, provenance auditing, artifact publishing.

## Target 15-Agent Architecture
All agents inherit from `BaseAgent` and register in the central `AgentRegistry`:
1. `audio_intake`: Audio Intake & Processing Agent
2. `audio_analyzer`: Audio Analysis Agent
3. `scene_segmentation`: Scene Segmentation Agent
4. `visual_concept`: Visual Concept Agent
5. `asset_collection`: Asset Collection Agent (one agent for the whole stage; its search, capture and validation are modules, not agents)
6. `motion_architect`: Motion Architecture Agent
7. `kinetic_typography`: Kinetic Typography Specialist Agent
8. `motion_template_selection`: Motion Template Selection Agent [DEPRECATED / DEFERRED]
9. `motion_generation`: Motion Generation Agent
10. `motion_validation`: Motion & Timeline Validation Agent
11. `timeline_assembly`: Timeline Assembly Agent
12. `timeline_approval_gatekeeper`: Timeline Approval Gatekeeper Agent
13. `video_rendering`: Video Rendering Engine Agent
14. `final_qc`: Final QC Specialist Agent
15. `final_delivery`: Final Delivery & Packaging Agent

All agent handoffs, decisions, reviews, and events are persistently logged in `projects/<pid>/agent_communications.jsonl`.

## Mandatory LLM Review Gates (Fail-Closed)
No pipeline stage may be marked `completed` until:
1. Technical execution and deterministic outputs are generated.
2. Deterministic validation checks pass with 0 blocking errors and 0 unhandled warnings.
3. Stage-specific LLM review runs and returns structured JSON with `status="passed"` and score >= 0.80.
4. If LLM review fails, times out, or reports blockers, the stage is marked `failed` or `waiting_for_approval`. Silently bypassing LLM review is strictly prohibited.

## Motion Animation & Codegen Rules
- Generates scene-specific TSX components (`projects/<pid>/generated_motion/scene_*.tsx`).
- Uses Remotion primitives: `spring()`, `interpolate()`, `useCurrentFrame()`, `useVideoConfig()`, `AbsoluteFill`.
- Prohibited presets (`MotionTextLayer`, `MotionScene`, `HighlightText`, etc.) are strictly rejected.
- All generated code is verified with TypeScript compiler (`npm run tsc` in `VIDEO_ENGINE/remotion/`) with 0 errors required.
- Source files are SHA-256 hashed and verified in `motion_animation.json`.
- Generated scenes may import ONLY the approved, installed, frame-safe libraries (`APPROVED_IMPORTS` in `VIDEO_ENGINE/stages/motion_animation.py`: Nivo, ECharts SVG, Phosphor, simple-icons, flubber, Lottie, d3, dagre, Radix colors...). Anything else fails the audit. Their usage rules live in the `motion.*` skills (`SYSTEM/skills/motion/`).
- NO 3D, WebGL, shaders or canvas (CPU-only machine): every animation is driven by the current frame (library animation off), icons/fonts never loaded over the network. A new library needs: license check, a CPU render test, an `APPROVED_IMPORTS` entry and a skill.
- The TypeScript check runs in `config.REMOTION_DIR` (`VIDEO_ENGINE/remotion`), the folder the scenes are staged into.

## Canonical Architecture & Folder Ownership
```text
audio-to-video/
├── SYSTEM/               # Shared system infrastructure, agents, memory, policies, approvals
│   ├── core/            # Config, LLM gateway, pipeline state, contracts, errors
│   ├── agents/          # Autonomous agents (system_agents, video_generation_agents, shared)
│   ├── skills/          # Central skill catalog and specialized capabilities
│   ├── registries/      # Central agent and skill registries
│   ├── memory/          # Project store and global cross-agent shared memory
│   ├── policies/        # LLM review gates and governance policies
│   ├── approvals/       # Approval engine (requests decided by an LLM review) and adapters
│   └── observability/   # LLM usage accounting, evaluations, diagnostics
├── UI/
│   ├── frontend/        # React + Vite + Tailwind + Vitest web application
│   └── backend/         # FastAPI presentation layer, API routes, schemas
├── VIDEO_ENGINE/
│   ├── pipeline/        # PipelineOrchestrator (sole canonical video execution engine)
│   ├── stages/          # 13 pipeline stages (transcribe, scene_segmentation, asset_collection, motion, etc.)
│   ├── remotion/        # Remotion video composition and rendering engine
│   └── ffmpeg/          # FFmpeg media probing and video processing integrations
├── resource-library/    # Audio-visual assets and reference materials
├── projects/            # Project artifacts, audio, transcripts, plans, renders
└── tests/               # Multi-suite test coverage
```

- **Sole Execution Engine**: `VIDEO_ENGINE.pipeline.orchestrator.PipelineOrchestrator`
- **Application Launch**:
  - API: `uvicorn UI.backend.main:app --host 0.0.0.0 --port 8000` (or `python -m backend.main` via backward-compatibility bridge)
  - Frontend: `cd UI/frontend && npm run dev`
- **Verification Commands**:
  - Python tests: `$env:PYTHONPATH="."; .venv\Scripts\python.exe -m pytest tests/... -q`
  - Frontend tests: `cd UI/frontend && npm test`
  - Frontend typecheck: `cd UI/frontend && npx tsc --noEmit` (there is no `typecheck` or `test` npm script)
  - Remotion typecheck: `cd VIDEO_ENGINE/remotion && npx tsc --noEmit`

## Working Rules (permanent)
- No stage is frozen. Any stage may be changed when the work needs it; keep its output contract (file names and schemas that later stages read) or update every reader and test together.
- Inspect the existing implementation, `CLAUDE.md`, the docs and the existing test results before working. Do not rebuild what works.
- Never repeat completed work or a successful test without a reason. Re-run tests only when the code they cover changed, to investigate a regression, or when extra verification is needed; run the tests of the changed code and its integrations, not the whole suite by default.
- Reuse existing outputs and validation results while they are valid (fingerprints, caches, finished steps). Never re-run Whisper or a finished stage for a project that already has valid outputs.
- No duplicate implementations, no unnecessary LLM calls, no token waste, no repeated processing. One job, one implementation; callers use it.
- On an error, keep going: fix it yourself and report only the result. Never stop just to inform, and never ask questions or permission (commit and push are pre-authorized by the user); stop only when truly blocked.
- A problem that does not clear where it shows has its cause upstream (an earlier scene or stage in the chain): look there and fix it there.
- Code too tangled to fix is deleted completely and rewritten cleanly, never patched on top. Keep the folder structure clean and the code small and simple.
- Work incrementally: validate the current stage, then move to the next. Never create a copy of a project or a new test project: modify and test directly in the existing project; never delete user data or assets (audio, transcripts).

## Approvals & Pipeline Automation (no human gates)
- **One autonomous run** (`POST /projects/{pid}/orchestrator/run`, the "Run Video" button; RUN / Retry of a stage = the same run from that stage): every stage starts by itself when the one before it completed with nothing unresolved. A stage with an unresolved issue stops the run THERE with the exact cause; nothing downstream starts and no half result flows on. There is no "mode" (`auto_pilot` is gone) and no manual execution mode.
- **Unresolved** (`VIDEO_ENGINE/pipeline/stage_gate.py`): a failed / blocked / warning step of the stage's own report (warnings only where the stage's own rules permit them, `POLICY_VERDICTS`), or a stage LLM review that is missing, out of date or not `passed`. Only the stage's own fixer clears a warning (bounded rounds). Nobody can accept a warning.
- **LLM review only where it matters** (`llm_review.LLM_STAGES`): Audio Analyzer, Scene Segmentation, Visual Planning, Motion Generation, Timeline Approval, Final QC. Every other stage (audio, assets, motion plan, motion validation, timeline build, render, delivery) is decided by its own deterministic checks. The first four can be switched off on the Rules page (`<stage>:llm_review`, recorded and told to the other reviewers); Approval and Final QC cannot (they ARE the decision).
- **Strict reviews:** only `status="passed"` with score >= 0.80 and no blocker/error approves. `needs_review` is not a pass, an unavailable LLM never approves, a high score does not turn a failed review green (the card says "LLM Verified" only for a passed review, "Checked by rules" for a stage without one).
- **No person approves anything:** no route, button or function chain exists for a person to approve a timeline, accept warnings or findings, or say they looked. Timeline Approval and Final QC are decided by their LLM reviews and audited by the same review.
- **Approval engine** (`SYSTEM/approvals/approval_engine.py`): consequential actions (skill/lesson promotion, rollback, strategy activation) are `ApprovalRequest`s bound to an action fingerprint. `ApprovalEngine.llm_decide` asks the LLM reviewer (`llm_review.ask_reviewer`) and records approved / rejected / changes_requested; agents then pass the `approval_request_id`, which is consumed once. There is no PIN and no route for a person to decide.

## Environment & Development Constraints
- OS: Windows 11, CPU-only (Intel i5-1235U, 16 GB RAM, no NVIDIA GPU).
- Python 3.12 (`.venv\Scripts\python.exe`), Node.js for Remotion and frontend.
- Never run destructive Git commands (`git reset --hard`, `git clean -fd`, `git checkout .`).
- Start the API (8000) and frontend (5173) only from this repository's root. If the machine holds another copy of the project, a server started there shows stale UI and old routes. When a UI change does not appear, first check which folder the servers run from: `Get-NetTCPConnection -LocalPort 5173,8000` + the process command line. Keep one copy per machine.
- Develop stage-by-stage following the approved roadmap.

## Permanent Engineering Rules (mandatory for every agent, stage, module, API, UI component)
Principle: Detect → Diagnose → Deduplicate → Consolidate → Simplify/Rewrite → Repair → Test → Verify → Prevent recurrence.

0. **One functionality = one authoritative implementation. One issue = one permanent root-cause fix**, made in the existing code of the existing project, never in a copy.
1. **Fix root causes.** On any error, warning, failed validation or blockage: investigate logs, states, inputs/outputs, dependencies and source; fix the real implementation (in the upstream stage/module if that is where it originates); verify before calling it fixed. Never hide it, work around it, or silently bypass validation. No temporary fixes (code changed only to get the app running or a test passing) and no fallback or suppressed failure that merely conceals the cause. Never modify an upstream module blindly to force a downstream stage to pass — show evidence it contributes to the cause.
2. **No duplicate code.** Before adding or repairing, search the whole dependency chain for existing implementations (functions, validators, state logic, API handlers). Reuse, extend or refactor; do not add a second implementation without a documented technical reason. Replace duplicates with calls to the shared one; keep legitimate differences as explicit parameters/config. Remove dead code, unused imports, redundant wrappers and duplicate files once verified unused.
3. **Merge divergent implementations of the same job.** List them, compare behavior/edge cases/callers, pick the canonical one on verified behavior (not newest/shortest), migrate all callers, remove the rest, add regression tests. Do not merge code that merely looks similar: keep distinct responsibilities, security boundaries and stage-specific rules.
4. **Simplify or rewrite only when justified.** Try a focused refactor first; when the existing code is too complex or confusing to fix, remove the obsolete implementation completely and rewrite it cleanly in the same place (never keep old and new side by side); replace the architecture only if it is the root cause, after identifying callers/contracts. Keep interfaces compatible or update all callers and tests together. Don't rewrite stable code without demonstrable benefit.
5. **Keep it simple and reusable:** small functions, explicit inputs/outputs/state transitions, consistent error handling and logging, config instead of duplicated conditionals. No abstraction more complex than the code it replaces.
6. **Safe removal.** Check imports, callers, dynamic loading, config and user data first. Preserve assets, checkpoints, history and protected components. Migrate callers, test, then delete.
7. **Bounded autonomous repair.** Classify from real execution data → root cause → smallest reliable fix → reuse existing code → consult specialist agents/LLMs for cross-module reasoning → fix → test → reassess if it fails → record in tests/docs. Bounded retries; never fabricate success. If a repair can't be validated safely, preserve the working state and report the blocker.
8. **Test what you change.** Reproduce the original failure, test the canonical implementation and all callers, edge/failure paths, previously supported behavior, and stage order. Compiling or a good-looking UI is not verification; if something can't be run, say what is unverified.
9. **Prevent recurrence:** regression tests, shared validators, type/lint/duplicate checks, consistent error reporting; update docs/rules. Don't add frameworks or special cases for a single incident.
10. **Done means:** root cause fixed, duplicates consolidated, old code removed safely, behavior preserved, tests and actual execution verified, remaining warnings/limits reported. Never claim "permanently resolved" without verification.
11. **Frontend Architecture & CSS Modules:** All React UI components must use scoped CSS Modules (`*.module.css`). Never write layout, typography, box shadows, borders, or hover handlers as inline JSX styles. Inline `style` is strictly reserved for runtime dynamic values (e.g. dynamic width calculation, progress stroke offsets). Every interactive element must preserve its `data-testid`. Any UI change must compile cleanly (`npm --prefix UI/frontend run build`) with zero TypeScript errors. Full guidelines live in `GEMINI.md` and `docs/rules.md`.
