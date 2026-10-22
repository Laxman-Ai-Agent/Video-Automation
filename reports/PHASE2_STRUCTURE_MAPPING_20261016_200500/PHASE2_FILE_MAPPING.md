# Phase 2 — Comprehensive File-by-File Mapping Report

- **Date/Time**: 2026-10-16 20:05:00 UTC+5:30
- **Repository Root**: `E:\audio-to-video`
- **Branch / HEAD**: `agents-building` / `f6989b17372e3cdb42b4c92ab1783b3122a401ae`
- **Machine-Readable CSV**: [`reports/PHASE2_STRUCTURE_MAPPING_20261016_200500/PHASE2_FILE_MAPPING.csv`](file:///e:/audio-to-video/reports/PHASE2_STRUCTURE_MAPPING_20261016_200500/PHASE2_FILE_MAPPING.csv)
- **Total Inventoried Items**: 441

---

## 1. Executive Summary & Inventory Statistics

This report establishes the complete, verified file-by-file migration mapping for all relevant files and directories in `E:\audio-to-video`. Every file has been cataloged with verified current paths, recommended target locations in the approved target structure, action type (`MOVE`, `REUSE`, `REWRITE`, `MERGE`, `REMOVE`, `KEEP`), callers/dependencies, data sensitivity, and risk severity.

### Mapping Breakdown by Action
| Action | Count | Meaning in Phase 2A |
|---|---|---|
| `KEEP` | 113 | Preserved in place at canonical root/location |
| `MERGE` | 4 | Recommended for consolidation into canonical owner |
| `MOVE` | 318 | Recommended for physical relocation during Phase 2B (no moves occurred now) |
| `REMOVE` | 5 | Candidate for deletion after caller migration (no deletions occurred now) |
| `REWRITE` | 1 | Recommended for decomposition/rewrite |

### Target Subsystem Allocation
| Subsystem Target | Mapped Items | Notes |
|---|---|---|
| **`SYSTEM/`** | 33 | Agents, registries, skills, approvals, memory, policies, core runtime |
| **`UI/`** | 116 | Frontend React app, UI-facing FastAPI routes, response schemas |
| **`VIDEO_ENGINE/`** | 174 | Pipeline orchestrator, video stages (including frozen logic), Remotion, FFmpeg |
| **`ROOT/CANONICAL`** | 113 | Resource library, user projects, tests, root docs, operational scripts |
| **`REMOVE` (Dead Code)** | 5 | Obsolete image gate, slot filling, and background removal candidates |

---

## 2. Core Architecture & Backend Mapping

| Mapping ID | Current Path | Target Path | Action | Risk | Frozen? | Responsibility |
|---|---|---|---|---|---|---|
| MAP-0001 | `backend/agents/adapters/stage_adapters.py` | `SYSTEM/agents/video_generation_agents/stage_adapters.py` | `MOVE` | `HIGH` | No | Video generation domain agent adapters for pipeline stages |
| MAP-0002 | `backend/agents/base_agent.py` | `SYSTEM/agents/shared/base_agent.py` | `MOVE` | `MEDIUM` | No | Abstract BaseAgent lifecycle and task interface |
| MAP-0003 | `backend/agents/communication.py` | `SYSTEM/agents/shared/communication.py` | `MOVE` | `MEDIUM` | No | Agent communication bus and message log |
| MAP-0004 | `backend/agents/contracts.py` | `SYSTEM/agents/shared/contracts.py` | `MOVE` | `LOW` | No | Agent task, response, and message schemas |
| MAP-0005 | `backend/agents/registry.py` | `SYSTEM/registries/agent_registry.py` | `MOVE` | `HIGH` | No | Central agent registry and lifecycle manager |
| MAP-0006 | `backend/analysis_autofix.py` | `VIDEO_ENGINE/stages/analysis_autofix.py` | `MOVE` | `MEDIUM` | No | Audio analysis autofix with contextual LLM review |
| MAP-0007 | `backend/api_models.py` | `UI/backend/schemas/api_models.py` | `MOVE` | `LOW` | No | API request and response schemas |
| MAP-0008 | `backend/api_status.py` | `UI/backend/schemas/api_status.py` | `MOVE` | `MEDIUM` | No | API project status calculation and blocker checks |
| MAP-0009 | `backend/approvals/adapters/eval_adapter.py` | `SYSTEM/approvals/adapters/eval_adapter.py` | `MOVE` | `MEDIUM` | Yes | Approval adapter for eval_adapter |
| MAP-0010 | `backend/approvals/adapters/qc_adapter.py` | `SYSTEM/approvals/adapters/qc_adapter.py` | `MOVE` | `MEDIUM` | Yes | Approval adapter for qc_adapter |
| MAP-0011 | `backend/approvals/adapters/timeline_adapter.py` | `SYSTEM/approvals/adapters/timeline_adapter.py` | `MOVE` | `MEDIUM` | Yes | Approval adapter for timeline_adapter |
| MAP-0012 | `backend/approvals/approval_engine.py` | `SYSTEM/approvals/approval_engine.py` | `MOVE` | `HIGH` | Yes | Laxman approval engine: queue, decisions, and audit trail |
| MAP-0013 | `backend/approvals/guard.py` | `SYSTEM/approvals/guard.py` | `MOVE` | `HIGH` | Yes | Action execution guard enforcing human sign-off |
| MAP-0014 | `backend/approvals/pin_service.py` | `SYSTEM/approvals/pin_service.py` | `MOVE` | `HIGH` | Yes | PBKDF2-HMAC-SHA256 constant-time PIN verification service |
| MAP-0015 | `backend/artifact_contracts.py` | `SYSTEM/core/artifact_contracts.py` | `MOVE` | `LOW` | No | Stage input/output artifact validation contracts |
| MAP-0016 | `backend/audio_analysis.py` | `VIDEO_ENGINE/stages/audio_analysis.py` | `MOVE` | `MEDIUM` | No | Librosa audio beat, onset, and energy extraction |
| MAP-0017 | `backend/audio_utils.py` | `VIDEO_ENGINE/stages/audio_utils.py` | `MOVE` | `LOW` | No | Audio format conversion and duration probing |
| MAP-0018 | `backend/autoplan.py` | `VIDEO_ENGINE/stages/autoplan.py` | `MOVE` | `HIGH` | No | Automated visual and motion scene planning stage |
| MAP-0019 | `backend/bg_remove.py` | `NO_MOVE` | `REMOVE` | `LOW` | No | Background removal for static image slot filling |
| MAP-0020 | `backend/browser_profiles.py` | `VIDEO_ENGINE/pipeline/browser_profiles.py` | `MOVE` | `LOW` | No | Chrome temporary profile cleaner for headless render |
| MAP-0021 | `backend/checks.py` | `SYSTEM/core/checks.py` | `MOVE` | `LOW` | No | System prerequisites and environmental check utilities |
| MAP-0022 | `backend/cli.py` | `SYSTEM/core/cli.py` | `MOVE` | `LOW` | No | Developer CLI utilities |
| MAP-0023 | `backend/config.py` | `SYSTEM/core/config.py` | `MOVE` | `HIGH` | No | Environment configuration and paths resolver |
| MAP-0024 | `backend/contracts.py` | `SYSTEM/core/contracts.py` | `MOVE` | `LOW` | No | Pipeline contract definitions and validation |
| MAP-0025 | `backend/diagnose.py` | `SYSTEM/observability/diagnose.py` | `MOVE` | `LOW` | No | Pipeline diagnostic reporter |
| MAP-0026 | `backend/errors.py` | `SYSTEM/core/errors.py` | `MOVE` | `LOW` | No | Standardized ApiError and pipeline error hierarchy |
| MAP-0027 | `backend/evaluation.py` | `SYSTEM/observability/evaluation.py` | `MOVE` | `MEDIUM` | No | Automated evaluation suites, baselines, and self-learning |
| MAP-0028 | `backend/fill_slots.py` | `NO_MOVE` | `REMOVE` | `LOW` | No | Legacy static image slot filler stage |
| MAP-0029 | `backend/final_qc.py` | `VIDEO_ENGINE/stages/final_qc.py` | `MOVE` | `HIGH` | No | Final QC automated quality check and rule evaluation |
| MAP-0030 | `backend/image_gate.py` | `NO_MOVE` | `REMOVE` | `LOW` | No | Legacy image approval gate (0 callers in production) |
| MAP-0031 | `backend/jobs.py` | `VIDEO_ENGINE/pipeline/jobs_adapter.py` | `MERGE` | `MEDIUM` | No | Legacy jobs adapter delegating to PipelineOrchestrator |
| MAP-0032 | `backend/llm_client.py` | `SYSTEM/core/llm_client.py` | `MERGE` | `MEDIUM` | No | Direct LLM client wrapper |
| MAP-0033 | `backend/llm_gateway.py` | `SYSTEM/core/llm_gateway.py` | `MOVE` | `HIGH` | No | Canonical LLM Gateway with retry, fallback, and review gate |
| MAP-0034 | `backend/llm_review.py` | `SYSTEM/policies/llm_review.py` | `MOVE` | `MEDIUM` | No | Mandatory LLM review gates and schema validator |
| MAP-0035 | `backend/llm_usage.py` | `SYSTEM/observability/llm_usage.py` | `MOVE` | `LOW` | No | LLM token usage tracking ledger and cost calculation |
| MAP-0036 | `backend/main.py` | `UI/backend/main.py` | `MOVE` | `HIGH` | No | FastAPI application entry point and middleware config |
| MAP-0037 | `backend/media_probe.py` | `VIDEO_ENGINE/ffmpeg/media_probe.py` | `MOVE` | `LOW` | No | FFprobe media duration and stream inspection |
| MAP-0038 | `backend/models.py` | `UI/backend/schemas/models.py` | `MOVE` | `LOW` | No | Domain entity models and database schemas |
| MAP-0039 | `backend/motion_animation.py` | `VIDEO_ENGINE/stages/motion_animation.py` | `MOVE` | `MEDIUM` | No | Motion animation timing, spring curves, and easing |
| MAP-0040 | `backend/motion_autofix.py` | `VIDEO_ENGINE/stages/motion_autofix.py` | `MOVE` | `MEDIUM` | No | Motion validation syntax and layout auto-repair |
| MAP-0041 | `backend/motion_branch.py` | `VIDEO_ENGINE/stages/motion_branch.py` | `MOVE` | `MEDIUM` | No | Motion branching and aspect ratio variant selection |
| MAP-0042 | `backend/motion_checks.py` | `VIDEO_ENGINE/stages/motion_checks.py` | `MOVE` | `LOW` | No | Motion TSX AST syntax and import sanity checks |
| MAP-0043 | `backend/motion_gen_report.py` | `VIDEO_ENGINE/stages/motion_gen_report.py` | `MOVE` | `LOW` | No | Motion generation audit report builder |
| MAP-0044 | `backend/motion_gen_rules.py` | `VIDEO_ENGINE/stages/motion_gen_rules.py` | `MOVE` | `LOW` | No | Motion generation styling and layout rules |
| MAP-0045 | `backend/motion_generation.py` | `VIDEO_ENGINE/stages/motion_generation.py` | `MOVE` | `HIGH` | No | Motion code generation stage for Remotion components |
| MAP-0046 | `backend/motion_planning.py` | `VIDEO_ENGINE/stages/motion_planning.py` | `MOVE` | `HIGH` | No | Motion planning stage: template and layout assignment |
| MAP-0047 | `backend/motion_scenes.py` | `VIDEO_ENGINE/stages/motion_scenes.py` | `MOVE` | `MEDIUM` | No | Motion scene structuring and timing computation |
| MAP-0048 | `backend/motion_template_selection.py` | `NO_MOVE` | `REMOVE` | `LOW` | No | Legacy motion template selection helper |
| MAP-0049 | `backend/motion_validation.py` | `VIDEO_ENGINE/stages/motion_validation.py` | `MOVE` | `HIGH` | No | Motion validation stage: rule enforcement and preview |
| MAP-0050 | `backend/motion_validation_preview.py` | `VIDEO_ENGINE/stages/motion_validation_preview.py` | `MOVE` | `LOW` | No | Motion validation preview generator for frontend |
| MAP-0051 | `backend/motion_validation_rules.py` | `VIDEO_ENGINE/stages/motion_validation_rules.py` | `MOVE` | `LOW` | No | Motion validation deterministic rule suite |
| MAP-0052 | `backend/orchestrator.py` | `VIDEO_ENGINE/pipeline/orchestrator.py` | `MOVE` | `HIGH` | No | Canonical Pipeline Orchestrator engine |
| MAP-0053 | `backend/pipeline.py` | `VIDEO_ENGINE/pipeline/legacy_pipeline_adapter.py` | `REWRITE` | `HIGH` | No | Legacy 14-stage monolithic pipeline script |
| MAP-0054 | `backend/pipeline_state.py` | `SYSTEM/core/pipeline_state.py` | `MOVE` | `HIGH` | No | Pipeline state, checkpoints, and contracts |
| MAP-0055 | `backend/pipeline_view.py` | `UI/backend/pipeline_view.py` | `MOVE` | `MEDIUM` | No | Pipeline gate visualization & stage status adapter |
| MAP-0056 | `backend/plan_checks.py` | `VIDEO_ENGINE/stages/plan_checks.py` | `MOVE` | `LOW` | No | Pre-plan validation and sanity checks |
| MAP-0057 | `backend/plan_input.py` | `VIDEO_ENGINE/stages/plan_input.py` | `MOVE` | `LOW` | No | Plan input preparation from transcript |
| MAP-0058 | `backend/plan_preview.py` | `VIDEO_ENGINE/stages/plan_preview.py` | `MOVE` | `LOW` | No | Plan preview generation and layout checks |
| MAP-0059 | `backend/prerender_checks.py` | `VIDEO_ENGINE/stages/prerender_checks.py` | `MOVE` | `LOW` | No | Pre-render asset and syntax verification checks |
| MAP-0060 | `backend/procs.py` | `VIDEO_ENGINE/pipeline/procs.py` | `MOVE` | `MEDIUM` | No | Subprocess execution and lifecycle manager |
| MAP-0061 | `backend/prompts_writer.py` | `NO_MOVE` | `REMOVE` | `LOW` | No | Image prompt generator for Midjourney/Flux |
| MAP-0062 | `backend/quality.py` | `VIDEO_ENGINE/stages/quality.py` | `MOVE` | `LOW` | No | Audio and video quality metric computation |
| MAP-0063 | `backend/render.py` | `VIDEO_ENGINE/stages/render.py` | `MOVE` | `HIGH` | No | Remotion bundle and render invocation controller |
| MAP-0064 | `backend/render_video.py` | `VIDEO_ENGINE/stages/render_video.py` | `MERGE` | `MEDIUM` | No | Render video stage coordinator and progress monitor |
| MAP-0065 | `backend/resume.py` | `VIDEO_ENGINE/pipeline/resume.py` | `MOVE` | `MEDIUM` | No | Pipeline resume analysis and artifact validation |
| MAP-0066 | `backend/routes/agents.py` | `UI/backend/routes/agents.py` | `MOVE` | `HIGH` | No | HTTP route handler for agents |
| MAP-0067 | `backend/routes/approvals.py` | `UI/backend/routes/approvals.py` | `MOVE` | `HIGH` | Yes | HTTP route handler for approvals |
| MAP-0068 | `backend/routes/evaluation.py` | `UI/backend/routes/evaluation.py` | `MOVE` | `HIGH` | No | HTTP route handler for evaluation |
| MAP-0069 | `backend/routes/llm.py` | `UI/backend/routes/llm.py` | `MOVE` | `HIGH` | No | HTTP route handler for llm |
| MAP-0070 | `backend/routes/memory.py` | `UI/backend/routes/memory.py` | `MOVE` | `HIGH` | No | HTTP route handler for memory |
| MAP-0071 | `backend/routes/orchestrator.py` | `UI/backend/routes/orchestrator.py` | `MOVE` | `HIGH` | No | HTTP route handler for orchestrator |
| MAP-0072 | `backend/routes/pipeline.py` | `UI/backend/routes/pipeline.py` | `MOVE` | `HIGH` | No | HTTP route handler for pipeline |
| MAP-0073 | `backend/routes/projects.py` | `UI/backend/routes/projects.py` | `MOVE` | `HIGH` | No | HTTP route handler for projects |
| MAP-0074 | `backend/routes/resources.py` | `UI/backend/routes/resources.py` | `MOVE` | `HIGH` | No | HTTP route handler for resources |
| MAP-0075 | `backend/routes/results.py` | `UI/backend/routes/results.py` | `MOVE` | `HIGH` | No | HTTP route handler for results |
| MAP-0076 | `backend/routes/review.py` | `UI/backend/routes/review.py` | `MOVE` | `HIGH` | No | HTTP route handler for review |
| MAP-0077 | `backend/routes/run.py` | `UI/backend/routes/run.py` | `MOVE` | `HIGH` | No | HTTP route handler for run |
| MAP-0078 | `backend/routes/skills.py` | `UI/backend/routes/skills.py` | `MOVE` | `HIGH` | No | HTTP route handler for skills |
| MAP-0079 | `backend/routes/uploads.py` | `UI/backend/routes/uploads.py` | `MOVE` | `HIGH` | No | HTTP route handler for uploads |
| MAP-0080 | `backend/routes/visual.py` | `UI/backend/routes/visual.py` | `MOVE` | `HIGH` | No | HTTP route handler for visual |
| MAP-0081 | `backend/scene_segmentation.py` | `VIDEO_ENGINE/stages/scene_segmentation.py` | `MOVE` | `BLOCKER` | **YES (FROZEN)** | Transcript scene boundary segmentation (FROZEN) |
| MAP-0082 | `backend/shared_memory.py` | `SYSTEM/memory/shared_memory.py` | `MOVE` | `MEDIUM` | No | Cross-project shared memory and episodic memory bank |
| MAP-0083 | `backend/skill_registry.py` | `SYSTEM/registries/skill_registry.py` | `MOVE` | `MEDIUM` | No | Central registry for procedural execution skills |
| MAP-0084 | `backend/store.py` | `SYSTEM/memory/store.py` | `MOVE` | `HIGH` | No | Project metadata, directory resolver, and info.json state |
| MAP-0085 | `backend/timeline_approval.py` | `VIDEO_ENGINE/stages/timeline_approval.py` | `MOVE` | `MEDIUM` | No | Timeline approval decision processor and diff recorder |
| MAP-0086 | `backend/timeline_build.py` | `VIDEO_ENGINE/stages/timeline_build.py` | `MOVE` | `HIGH` | No | Timeline composition builder: tracks, transitions, audio |
| MAP-0087 | `backend/timeline_gate.py` | `VIDEO_ENGINE/stages/timeline_gate.py` | `MOVE` | `MEDIUM` | No | Timeline approval gate and review prerequisites |
| MAP-0088 | `backend/timeline_media.py` | `VIDEO_ENGINE/stages/timeline_media.py` | `MOVE` | `MEDIUM` | No | Timeline media asset resolver and path linker |
| MAP-0089 | `backend/transcribe.py` | `VIDEO_ENGINE/stages/transcribe.py` | `MOVE` | `BLOCKER` | **YES (FROZEN)** | Audio Whisper transcription (FROZEN) |
| MAP-0090 | `backend/transcript_review.py` | `VIDEO_ENGINE/stages/transcript_review.py` | `MOVE` | `BLOCKER` | **YES (FROZEN)** | Transcript correction & review logic (FROZEN) |
| MAP-0091 | `backend/video_qc.py` | `VIDEO_ENGINE/stages/video_qc.py` | `MERGE` | `MEDIUM` | No | Video QC metric extractor and ffmpeg validator |
| MAP-0092 | `backend/visual_plan.py` | `VIDEO_ENGINE/stages/visual_plan.py` | `MOVE` | `MEDIUM` | No | Visual plan generation and scene alignment |
| MAP-0093 | `backend/visual_planning.py` | `VIDEO_ENGINE/stages/visual_planning.py` | `MOVE` | `HIGH` | No | Visual planning stage controller and validator |
| MAP-0094 | `backend/assets.py` | `VIDEO_ENGINE/stages/assets.py` | `MOVE` | `MEDIUM` | No | Backend component assets.py |
| MAP-0095 | `backend/cues.py` | `VIDEO_ENGINE/stages/cues.py` | `MOVE` | `MEDIUM` | No | Backend component cues.py |
| MAP-0096 | `backend/cuts.py` | `VIDEO_ENGINE/stages/cuts.py` | `MOVE` | `MEDIUM` | No | Backend component cuts.py |
| MAP-0097 | `backend/fingerprint.py` | `VIDEO_ENGINE/stages/fingerprint.py` | `MOVE` | `MEDIUM` | No | Backend component fingerprint.py |
| MAP-0098 | `backend/focus.py` | `VIDEO_ENGINE/stages/focus.py` | `MOVE` | `MEDIUM` | No | Backend component focus.py |
| MAP-0099 | `backend/graphics.py` | `VIDEO_ENGINE/stages/graphics.py` | `MOVE` | `MEDIUM` | No | Backend component graphics.py |
| MAP-0100 | `backend/highlights.py` | `VIDEO_ENGINE/stages/highlights.py` | `MOVE` | `MEDIUM` | No | Backend component highlights.py |
| MAP-0101 | `backend/matcher.py` | `VIDEO_ENGINE/stages/matcher.py` | `MOVE` | `MEDIUM` | No | Backend component matcher.py |
| MAP-0102 | `backend/match_detail.py` | `VIDEO_ENGINE/stages/match_detail.py` | `MOVE` | `MEDIUM` | No | Backend component match_detail.py |
| MAP-0103 | `backend/palette.py` | `VIDEO_ENGINE/stages/palette.py` | `MOVE` | `MEDIUM` | No | Backend component palette.py |
| MAP-0104 | `backend/promptgen.py` | `VIDEO_ENGINE/stages/promptgen.py` | `MOVE` | `MEDIUM` | No | Backend component promptgen.py |
| MAP-0105 | `backend/prompt_review.py` | `VIDEO_ENGINE/stages/prompt_review.py` | `MOVE` | `MEDIUM` | No | Backend component prompt_review.py |
| MAP-0106 | `backend/resource_audit.py` | `VIDEO_ENGINE/stages/resource_audit.py` | `MOVE` | `MEDIUM` | No | Backend component resource_audit.py |
| MAP-0107 | `backend/resource_jobs.py` | `VIDEO_ENGINE/stages/resource_jobs.py` | `MOVE` | `MEDIUM` | No | Backend component resource_jobs.py |
| MAP-0108 | `backend/resource_library.py` | `VIDEO_ENGINE/stages/resource_library.py` | `MOVE` | `MEDIUM` | No | Backend component resource_library.py |
| MAP-0109 | `backend/resource_local.py` | `VIDEO_ENGINE/stages/resource_local.py` | `MOVE` | `MEDIUM` | No | Backend component resource_local.py |
| MAP-0110 | `backend/resource_verify.py` | `VIDEO_ENGINE/stages/resource_verify.py` | `MOVE` | `MEDIUM` | No | Backend component resource_verify.py |
| MAP-0111 | `backend/review.py` | `VIDEO_ENGINE/stages/review.py` | `MOVE` | `MEDIUM` | No | Backend component review.py |
| MAP-0112 | `backend/shots.py` | `VIDEO_ENGINE/stages/shots.py` | `MOVE` | `MEDIUM` | No | Backend component shots.py |
| MAP-0113 | `backend/show_transcript.py` | `VIDEO_ENGINE/stages/show_transcript.py` | `MOVE` | `MEDIUM` | No | Backend component show_transcript.py |
| MAP-0114 | `backend/stock.py` | `VIDEO_ENGINE/stages/stock.py` | `MOVE` | `MEDIUM` | No | Backend component stock.py |
| MAP-0115 | `backend/telugu.py` | `VIDEO_ENGINE/stages/telugu.py` | `MOVE` | `MEDIUM` | No | Backend component telugu.py |
| MAP-0116 | `backend/theme.py` | `VIDEO_ENGINE/stages/theme.py` | `MOVE` | `MEDIUM` | No | Backend component theme.py |
| MAP-0117 | `backend/transition_audit.py` | `VIDEO_ENGINE/stages/transition_audit.py` | `MOVE` | `MEDIUM` | No | Backend component transition_audit.py |
| MAP-0118 | `backend/translate_io.py` | `VIDEO_ENGINE/stages/translate_io.py` | `MOVE` | `MEDIUM` | No | Backend component translate_io.py |
| MAP-0119 | `backend/validate.py` | `VIDEO_ENGINE/stages/validate.py` | `MOVE` | `MEDIUM` | No | Backend component validate.py |
| MAP-0120 | `backend/__init__.py` | `VIDEO_ENGINE/stages/__init__.py` | `MOVE` | `MEDIUM` | No | Backend component __init__.py |
| MAP-0121 | `backend/agents/__init__.py` | `VIDEO_ENGINE/stages/__init__.py` | `MOVE` | `MEDIUM` | No | Backend component __init__.py |
| MAP-0122 | `backend/agents/adapters/__init__.py` | `VIDEO_ENGINE/stages/__init__.py` | `MOVE` | `MEDIUM` | No | Backend component __init__.py |
| MAP-0123 | `backend/approvals/adapters/__init__.py` | `VIDEO_ENGINE/stages/__init__.py` | `MOVE` | `MEDIUM` | No | Backend component __init__.py |
| MAP-0124 | `backend/routes/__init__.py` | `UI/backend/routes/__init__.py` | `MOVE` | `MEDIUM` | No | Backend component __init__.py |

---

## 3. Frontend Subsystem Mapping (`UI/frontend/`)

| Mapping ID | Current Path | Target Path | Action | Risk | Responsibility |
|---|---|---|---|---|---|
| MAP-0125 | `frontend/.gitignore` | `UI/frontend/.gitignore` | `MOVE` | `LOW` | Frontend React/Vite component .gitignore |
| MAP-0126 | `frontend/.oxlintrc.json` | `UI/frontend/.oxlintrc.json` | `MOVE` | `LOW` | Frontend React/Vite component .oxlintrc.json |
| MAP-0127 | `frontend/index.html` | `UI/frontend/index.html` | `MOVE` | `LOW` | Frontend React/Vite component index.html |
| MAP-0128 | `frontend/package-lock.json` | `UI/frontend/package-lock.json` | `MOVE` | `LOW` | Frontend React/Vite component package-lock.json |
| MAP-0129 | `frontend/package.json` | `UI/frontend/package.json` | `MOVE` | `LOW` | Frontend React/Vite component package.json |
| MAP-0130 | `frontend/tsconfig.app.json` | `UI/frontend/tsconfig.app.json` | `MOVE` | `LOW` | Frontend React/Vite component tsconfig.app.json |
| MAP-0131 | `frontend/tsconfig.json` | `UI/frontend/tsconfig.json` | `MOVE` | `LOW` | Frontend React/Vite component tsconfig.json |
| MAP-0132 | `frontend/tsconfig.node.json` | `UI/frontend/tsconfig.node.json` | `MOVE` | `LOW` | Frontend React/Vite component tsconfig.node.json |
| MAP-0133 | `frontend/vite.config.ts` | `UI/frontend/vite.config.ts` | `MOVE` | `LOW` | Frontend React/Vite component vite.config.ts |
| MAP-0134 | `frontend/public/favicon.svg` | `UI/frontend/public/favicon.svg` | `MOVE` | `LOW` | Frontend React/Vite component favicon.svg |
| MAP-0135 | `frontend/scripts/dump_openapi.py` | `UI/frontend/scripts/dump_openapi.py` | `MOVE` | `MEDIUM` | Frontend React/Vite component dump_openapi.py |
| MAP-0136 | `frontend/src/App.tsx` | `UI/frontend/src/App.tsx` | `MOVE` | `LOW` | Frontend React/Vite component App.tsx |
| MAP-0137 | `frontend/src/index.css` | `UI/frontend/src/index.css` | `MOVE` | `LOW` | Frontend React/Vite component index.css |
| MAP-0138 | `frontend/src/main.tsx` | `UI/frontend/src/main.tsx` | `MOVE` | `LOW` | Frontend React/Vite component main.tsx |
| MAP-0139 | `frontend/src/api/agentTypes.ts` | `UI/frontend/src/api/agentTypes.ts` | `MOVE` | `MEDIUM` | Frontend React/Vite component agentTypes.ts |
| MAP-0140 | `frontend/src/api/approvalTypes.ts` | `UI/frontend/src/api/approvalTypes.ts` | `MOVE` | `MEDIUM` | Frontend React/Vite component approvalTypes.ts |
| MAP-0141 | `frontend/src/api/autofixTypes.ts` | `UI/frontend/src/api/autofixTypes.ts` | `MOVE` | `MEDIUM` | Frontend React/Vite component autofixTypes.ts |
| MAP-0142 | `frontend/src/api/client.ts` | `UI/frontend/src/api/client.ts` | `MOVE` | `MEDIUM` | Frontend React/Vite component client.ts |
| MAP-0143 | `frontend/src/api/llmTypes.ts` | `UI/frontend/src/api/llmTypes.ts` | `MOVE` | `MEDIUM` | Frontend React/Vite component llmTypes.ts |
| MAP-0144 | `frontend/src/api/pipelineTypes.ts` | `UI/frontend/src/api/pipelineTypes.ts` | `MOVE` | `MEDIUM` | Frontend React/Vite component pipelineTypes.ts |
| MAP-0145 | `frontend/src/api/resourceTypes.ts` | `UI/frontend/src/api/resourceTypes.ts` | `MOVE` | `MEDIUM` | Frontend React/Vite component resourceTypes.ts |
| MAP-0146 | `frontend/src/api/skillTypes.ts` | `UI/frontend/src/api/skillTypes.ts` | `MOVE` | `MEDIUM` | Frontend React/Vite component skillTypes.ts |
| MAP-0147 | `frontend/src/api/types.ts` | `UI/frontend/src/api/types.ts` | `MOVE` | `MEDIUM` | Frontend React/Vite component types.ts |
| MAP-0148 | `frontend/src/components/AgentCommunicationDrawer.tsx` | `UI/frontend/src/components/AgentCommunicationDrawer.tsx` | `MOVE` | `LOW` | Frontend React/Vite component AgentCommunicationDrawer.tsx |
| MAP-0149 | `frontend/src/components/LlmSettingsModal.tsx` | `UI/frontend/src/components/LlmSettingsModal.tsx` | `MOVE` | `LOW` | Frontend React/Vite component LlmSettingsModal.tsx |
| MAP-0150 | `frontend/src/components/LlmUsageCard.tsx` | `UI/frontend/src/components/LlmUsageCard.tsx` | `MOVE` | `LOW` | Frontend React/Vite component LlmUsageCard.tsx |
| MAP-0151 | `frontend/src/pages/AgentsPage.tsx` | `UI/frontend/src/pages/AgentsPage.tsx` | `MOVE` | `LOW` | Frontend React/Vite component AgentsPage.tsx |
| MAP-0152 | `frontend/src/pages/AnalyzerPage.tsx` | `UI/frontend/src/pages/AnalyzerPage.tsx` | `MOVE` | `LOW` | Frontend React/Vite component AnalyzerPage.tsx |
| MAP-0153 | `frontend/src/pages/AudioInputPage.tsx` | `UI/frontend/src/pages/AudioInputPage.tsx` | `MOVE` | `LOW` | Frontend React/Vite component AudioInputPage.tsx |
| MAP-0154 | `frontend/src/pages/FinalQcPage.tsx` | `UI/frontend/src/pages/FinalQcPage.tsx` | `MOVE` | `LOW` | Frontend React/Vite component FinalQcPage.tsx |
| MAP-0155 | `frontend/src/pages/JsonPage.tsx` | `UI/frontend/src/pages/JsonPage.tsx` | `MOVE` | `LOW` | Frontend React/Vite component JsonPage.tsx |
| MAP-0156 | `frontend/src/pages/LaxmanApprovalPage.tsx` | `UI/frontend/src/pages/LaxmanApprovalPage.tsx` | `MOVE` | `LOW` | Frontend React/Vite component LaxmanApprovalPage.tsx |
| MAP-0157 | `frontend/src/pages/LlmUsagePage.tsx` | `UI/frontend/src/pages/LlmUsagePage.tsx` | `MOVE` | `LOW` | Frontend React/Vite component LlmUsagePage.tsx |
| MAP-0158 | `frontend/src/pages/MotionGenerationPage.tsx` | `UI/frontend/src/pages/MotionGenerationPage.tsx` | `MOVE` | `LOW` | Frontend React/Vite component MotionGenerationPage.tsx |
| MAP-0159 | `frontend/src/pages/MotionOutputPage.tsx` | `UI/frontend/src/pages/MotionOutputPage.tsx` | `MOVE` | `LOW` | Frontend React/Vite component MotionOutputPage.tsx |
| MAP-0160 | `frontend/src/pages/MotionOutputScenePage.tsx` | `UI/frontend/src/pages/MotionOutputScenePage.tsx` | `MOVE` | `LOW` | Frontend React/Vite component MotionOutputScenePage.tsx |
| MAP-0161 | `frontend/src/pages/MotionPlanningPage.tsx` | `UI/frontend/src/pages/MotionPlanningPage.tsx` | `MOVE` | `LOW` | Frontend React/Vite component MotionPlanningPage.tsx |
| MAP-0162 | `frontend/src/pages/MotionPlanPage.tsx` | `UI/frontend/src/pages/MotionPlanPage.tsx` | `MOVE` | `LOW` | Frontend React/Vite component MotionPlanPage.tsx |
| MAP-0163 | `frontend/src/pages/MotionPlanScenePage.tsx` | `UI/frontend/src/pages/MotionPlanScenePage.tsx` | `MOVE` | `LOW` | Frontend React/Vite component MotionPlanScenePage.tsx |
| MAP-0164 | `frontend/src/pages/MotionValidationDetailsPage.tsx` | `UI/frontend/src/pages/MotionValidationDetailsPage.tsx` | `MOVE` | `LOW` | Frontend React/Vite component MotionValidationDetailsPage.tsx |
| MAP-0165 | `frontend/src/pages/MotionValidationPage.tsx` | `UI/frontend/src/pages/MotionValidationPage.tsx` | `MOVE` | `LOW` | Frontend React/Vite component MotionValidationPage.tsx |
| MAP-0166 | `frontend/src/pages/ProjectsPage.tsx` | `UI/frontend/src/pages/ProjectsPage.tsx` | `MOVE` | `LOW` | Frontend React/Vite component ProjectsPage.tsx |
| MAP-0167 | `frontend/src/pages/RenderVideoPage.tsx` | `UI/frontend/src/pages/RenderVideoPage.tsx` | `MOVE` | `LOW` | Frontend React/Vite component RenderVideoPage.tsx |
| MAP-0168 | `frontend/src/pages/ResourcesPage.tsx` | `UI/frontend/src/pages/ResourcesPage.tsx` | `MOVE` | `LOW` | Frontend React/Vite component ResourcesPage.tsx |
| MAP-0169 | `frontend/src/pages/SceneDetailPage.tsx` | `UI/frontend/src/pages/SceneDetailPage.tsx` | `MOVE` | `LOW` | Frontend React/Vite component SceneDetailPage.tsx |
| MAP-0170 | `frontend/src/pages/ScenesPage.tsx` | `UI/frontend/src/pages/ScenesPage.tsx` | `MOVE` | `LOW` | Frontend React/Vite component ScenesPage.tsx |
| MAP-0171 | `frontend/src/pages/SegmentationPage.tsx` | `UI/frontend/src/pages/SegmentationPage.tsx` | `MOVE` | `LOW` | Frontend React/Vite component SegmentationPage.tsx |
| MAP-0172 | `frontend/src/pages/TimelineApprovalPage.tsx` | `UI/frontend/src/pages/TimelineApprovalPage.tsx` | `MOVE` | `LOW` | Frontend React/Vite component TimelineApprovalPage.tsx |
| MAP-0173 | `frontend/src/pages/TimelineBuildDetailsPage.tsx` | `UI/frontend/src/pages/TimelineBuildDetailsPage.tsx` | `MOVE` | `LOW` | Frontend React/Vite component TimelineBuildDetailsPage.tsx |
| MAP-0174 | `frontend/src/pages/TimelineBuildPage.tsx` | `UI/frontend/src/pages/TimelineBuildPage.tsx` | `MOVE` | `LOW` | Frontend React/Vite component TimelineBuildPage.tsx |
| MAP-0175 | `frontend/src/pages/TimelineParts.tsx` | `UI/frontend/src/pages/TimelineParts.tsx` | `MOVE` | `LOW` | Frontend React/Vite component TimelineParts.tsx |
| MAP-0176 | `frontend/src/pages/TimelineProps.tsx` | `UI/frontend/src/pages/TimelineProps.tsx` | `MOVE` | `LOW` | Frontend React/Vite component TimelineProps.tsx |
| MAP-0177 | `frontend/src/pages/TimelineTracks.tsx` | `UI/frontend/src/pages/TimelineTracks.tsx` | `MOVE` | `LOW` | Frontend React/Vite component TimelineTracks.tsx |
| MAP-0178 | `frontend/src/pages/VisualPlanningPage.tsx` | `UI/frontend/src/pages/VisualPlanningPage.tsx` | `MOVE` | `LOW` | Frontend React/Vite component VisualPlanningPage.tsx |
| MAP-0179 | `frontend/src/pages/VisualPlanPage.tsx` | `UI/frontend/src/pages/VisualPlanPage.tsx` | `MOVE` | `LOW` | Frontend React/Vite component VisualPlanPage.tsx |
| MAP-0180 | `frontend/src/pages/VisualPlanScenePage.tsx` | `UI/frontend/src/pages/VisualPlanScenePage.tsx` | `MOVE` | `LOW` | Frontend React/Vite component VisualPlanScenePage.tsx |
| MAP-0181 | `frontend/src/pipeline/analyzerSteps.ts` | `UI/frontend/src/pipeline/analyzerSteps.ts` | `MOVE` | `MEDIUM` | Frontend React/Vite component analyzerSteps.ts |
| MAP-0182 | `frontend/src/pipeline/layout.ts` | `UI/frontend/src/pipeline/layout.ts` | `MOVE` | `MEDIUM` | Frontend React/Vite component layout.ts |
| MAP-0183 | `frontend/src/pipeline/motionGenerationSteps.ts` | `UI/frontend/src/pipeline/motionGenerationSteps.ts` | `MOVE` | `MEDIUM` | Frontend React/Vite component motionGenerationSteps.ts |
| MAP-0184 | `frontend/src/pipeline/motionPlanningSteps.ts` | `UI/frontend/src/pipeline/motionPlanningSteps.ts` | `MOVE` | `MEDIUM` | Frontend React/Vite component motionPlanningSteps.ts |
| MAP-0185 | `frontend/src/pipeline/motionValidationSteps.ts` | `UI/frontend/src/pipeline/motionValidationSteps.ts` | `MOVE` | `MEDIUM` | Frontend React/Vite component motionValidationSteps.ts |
| MAP-0186 | `frontend/src/pipeline/PipelineChart.tsx` | `UI/frontend/src/pipeline/PipelineChart.tsx` | `MOVE` | `MEDIUM` | Frontend React/Vite component PipelineChart.tsx |
| MAP-0187 | `frontend/src/pipeline/PipelinePage.tsx` | `UI/frontend/src/pipeline/PipelinePage.tsx` | `MOVE` | `MEDIUM` | Frontend React/Vite component PipelinePage.tsx |
| MAP-0188 | `frontend/src/pipeline/segmentationSteps.ts` | `UI/frontend/src/pipeline/segmentationSteps.ts` | `MOVE` | `MEDIUM` | Frontend React/Vite component segmentationSteps.ts |
| MAP-0189 | `frontend/src/pipeline/stageAboutData.ts` | `UI/frontend/src/pipeline/stageAboutData.ts` | `MOVE` | `MEDIUM` | Frontend React/Vite component stageAboutData.ts |
| MAP-0190 | `frontend/src/pipeline/StageAboutModal.tsx` | `UI/frontend/src/pipeline/StageAboutModal.tsx` | `MOVE` | `MEDIUM` | Frontend React/Vite component StageAboutModal.tsx |
| MAP-0191 | `frontend/src/pipeline/StageBoxes.tsx` | `UI/frontend/src/pipeline/StageBoxes.tsx` | `MOVE` | `MEDIUM` | Frontend React/Vite component StageBoxes.tsx |
| MAP-0192 | `frontend/src/pipeline/StageFailureAlert.tsx` | `UI/frontend/src/pipeline/StageFailureAlert.tsx` | `MOVE` | `MEDIUM` | Frontend React/Vite component StageFailureAlert.tsx |
| MAP-0193 | `frontend/src/pipeline/StepPage.tsx` | `UI/frontend/src/pipeline/StepPage.tsx` | `MOVE` | `MEDIUM` | Frontend React/Vite component StepPage.tsx |
| MAP-0194 | `frontend/src/pipeline/timelineBuildSteps.ts` | `UI/frontend/src/pipeline/timelineBuildSteps.ts` | `MOVE` | `MEDIUM` | Frontend React/Vite component timelineBuildSteps.ts |
| MAP-0195 | `frontend/src/pipeline/timelineLanes.ts` | `UI/frontend/src/pipeline/timelineLanes.ts` | `MOVE` | `MEDIUM` | Frontend React/Vite component timelineLanes.ts |
| MAP-0196 | `frontend/src/pipeline/useAutoAdvance.ts` | `UI/frontend/src/pipeline/useAutoAdvance.ts` | `MOVE` | `MEDIUM` | Frontend React/Vite component useAutoAdvance.ts |
| MAP-0197 | `frontend/src/pipeline/usePipeline.ts` | `UI/frontend/src/pipeline/usePipeline.ts` | `MOVE` | `MEDIUM` | Frontend React/Vite component usePipeline.ts |
| MAP-0198 | `frontend/src/pipeline/useTimelinePlayer.ts` | `UI/frontend/src/pipeline/useTimelinePlayer.ts` | `MOVE` | `MEDIUM` | Frontend React/Vite component useTimelinePlayer.ts |
| MAP-0199 | `frontend/src/pipeline/visualPlanningSteps.ts` | `UI/frontend/src/pipeline/visualPlanningSteps.ts` | `MOVE` | `MEDIUM` | Frontend React/Vite component visualPlanningSteps.ts |
| MAP-0200 | `frontend/tests/agents_page.test.tsx` | `UI/frontend/tests/agents_page.test.tsx` | `MOVE` | `LOW` | Frontend React/Vite component agents_page.test.tsx |
| MAP-0201 | `frontend/tests/autoadvance.test.tsx` | `UI/frontend/tests/autoadvance.test.tsx` | `MOVE` | `LOW` | Frontend React/Vite component autoadvance.test.tsx |
| MAP-0202 | `frontend/tests/auto_advance.test.tsx` | `UI/frontend/tests/auto_advance.test.tsx` | `MOVE` | `LOW` | Frontend React/Vite component auto_advance.test.tsx |
| MAP-0203 | `frontend/tests/client.test.ts` | `UI/frontend/tests/client.test.ts` | `MOVE` | `LOW` | Frontend React/Vite component client.test.ts |
| MAP-0204 | `frontend/tests/contract.test.ts` | `UI/frontend/tests/contract.test.ts` | `MOVE` | `LOW` | Frontend React/Vite component contract.test.ts |
| MAP-0205 | `frontend/tests/json_page.test.tsx` | `UI/frontend/tests/json_page.test.tsx` | `MOVE` | `LOW` | Frontend React/Vite component json_page.test.tsx |
| MAP-0206 | `frontend/tests/laxman_approval_page.test.tsx` | `UI/frontend/tests/laxman_approval_page.test.tsx` | `MOVE` | `LOW` | Frontend React/Vite component laxman_approval_page.test.tsx |
| MAP-0207 | `frontend/tests/llm_usage_card.test.tsx` | `UI/frontend/tests/llm_usage_card.test.tsx` | `MOVE` | `LOW` | Frontend React/Vite component llm_usage_card.test.tsx |
| MAP-0208 | `frontend/tests/llm_usage_page.test.tsx` | `UI/frontend/tests/llm_usage_page.test.tsx` | `MOVE` | `LOW` | Frontend React/Vite component llm_usage_page.test.tsx |
| MAP-0209 | `frontend/tests/pipeline_llm_badge.test.tsx` | `UI/frontend/tests/pipeline_llm_badge.test.tsx` | `MOVE` | `MEDIUM` | Frontend React/Vite component pipeline_llm_badge.test.tsx |
| MAP-0210 | `frontend/tests/pipeline_ui.test.tsx` | `UI/frontend/tests/pipeline_ui.test.tsx` | `MOVE` | `MEDIUM` | Frontend React/Vite component pipeline_ui.test.tsx |
| MAP-0211 | `frontend/tests/projects.test.tsx` | `UI/frontend/tests/projects.test.tsx` | `MOVE` | `LOW` | Frontend React/Vite component projects.test.tsx |
| MAP-0212 | `frontend/tests/resources.test.tsx` | `UI/frontend/tests/resources.test.tsx` | `MOVE` | `LOW` | Frontend React/Vite component resources.test.tsx |
| MAP-0213 | `frontend/tests/server.ts` | `UI/frontend/tests/server.ts` | `MOVE` | `LOW` | Frontend React/Vite component server.ts |
| MAP-0214 | `frontend/tests/setup.ts` | `UI/frontend/tests/setup.ts` | `MOVE` | `LOW` | Frontend React/Vite component setup.ts |
| MAP-0215 | `frontend/tests/stage_about.test.tsx` | `UI/frontend/tests/stage_about.test.tsx` | `MOVE` | `LOW` | Frontend React/Vite component stage_about.test.tsx |
| MAP-0216 | `frontend/tests/stage_failure_alert.test.tsx` | `UI/frontend/tests/stage_failure_alert.test.tsx` | `MOVE` | `LOW` | Frontend React/Vite component stage_failure_alert.test.tsx |
| MAP-0217 | `frontend/tests/timeline_lanes.test.ts` | `UI/frontend/tests/timeline_lanes.test.ts` | `MOVE` | `LOW` | Frontend React/Vite component timeline_lanes.test.ts |
| MAP-0218 | `frontend/tests/fixtures/openapi.json` | `UI/frontend/tests/fixtures/openapi.json` | `MOVE` | `MEDIUM` | Frontend React/Vite component openapi.json |
| MAP-0219 | `frontend/tests/fixtures/prompts.sample.txt` | `UI/frontend/tests/fixtures/prompts.sample.txt` | `MOVE` | `LOW` | Frontend React/Vite component prompts.sample.txt |

---

## 4. Video Engine & Remotion Mapping (`VIDEO_ENGINE/remotion/`)

| Mapping ID | Current Path | Target Path | Action | Risk | Responsibility |
|---|---|---|---|---|---|
| MAP-0220 | `remotion/package-lock.json` | `VIDEO_ENGINE/remotion/package-lock.json` | `MOVE` | `MEDIUM` | Remotion motion graphics code package-lock.json |
| MAP-0221 | `remotion/package.json` | `VIDEO_ENGINE/remotion/package.json` | `MOVE` | `MEDIUM` | Remotion motion graphics code package.json |
| MAP-0222 | `remotion/remotion.config.ts` | `VIDEO_ENGINE/remotion/remotion.config.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code remotion.config.ts |
| MAP-0223 | `remotion/test_frame1880.png` | `VIDEO_ENGINE/remotion/test_frame1880.png` | `MOVE` | `MEDIUM` | Remotion motion graphics code test_frame1880.png |
| MAP-0224 | `remotion/test_frame45.png` | `VIDEO_ENGINE/remotion/test_frame45.png` | `MOVE` | `MEDIUM` | Remotion motion graphics code test_frame45.png |
| MAP-0225 | `remotion/test_frame_100.png` | `VIDEO_ENGINE/remotion/test_frame_100.png` | `MOVE` | `MEDIUM` | Remotion motion graphics code test_frame_100.png |
| MAP-0226 | `remotion/test_frame_130.png` | `VIDEO_ENGINE/remotion/test_frame_130.png` | `MOVE` | `MEDIUM` | Remotion motion graphics code test_frame_130.png |
| MAP-0227 | `remotion/test_frame_300.png` | `VIDEO_ENGINE/remotion/test_frame_300.png` | `MOVE` | `MEDIUM` | Remotion motion graphics code test_frame_300.png |
| MAP-0228 | `remotion/tsconfig.json` | `VIDEO_ENGINE/remotion/tsconfig.json` | `MOVE` | `MEDIUM` | Remotion motion graphics code tsconfig.json |
| MAP-0229 | `remotion/public/audio.mp3` | `VIDEO_ENGINE/remotion/public/audio.mp3` | `MOVE` | `MEDIUM` | Remotion motion graphics code audio.mp3 |
| MAP-0230 | `remotion/public/audio.wav` | `VIDEO_ENGINE/remotion/public/audio.wav` | `MOVE` | `MEDIUM` | Remotion motion graphics code audio.wav |
| MAP-0231 | `remotion/public/audio_test.wav` | `VIDEO_ENGINE/remotion/public/audio_test.wav` | `MOVE` | `MEDIUM` | Remotion motion graphics code audio_test.wav |
| MAP-0232 | `remotion/public/composition.json` | `VIDEO_ENGINE/remotion/public/composition.json` | `MOVE` | `MEDIUM` | Remotion motion graphics code composition.json |
| MAP-0233 | `remotion/public/gallery.json` | `VIDEO_ENGINE/remotion/public/gallery.json` | `MOVE` | `MEDIUM` | Remotion motion graphics code gallery.json |
| MAP-0234 | `remotion/public/img_01.png` | `VIDEO_ENGINE/remotion/public/img_01.png` | `MOVE` | `MEDIUM` | Remotion motion graphics code img_01.png |
| MAP-0235 | `remotion/public/img_02.png` | `VIDEO_ENGINE/remotion/public/img_02.png` | `MOVE` | `MEDIUM` | Remotion motion graphics code img_02.png |
| MAP-0236 | `remotion/public/img_03.png` | `VIDEO_ENGINE/remotion/public/img_03.png` | `MOVE` | `MEDIUM` | Remotion motion graphics code img_03.png |
| MAP-0237 | `remotion/public/layers_test.json` | `VIDEO_ENGINE/remotion/public/layers_test.json` | `MOVE` | `MEDIUM` | Remotion motion graphics code layers_test.json |
| MAP-0238 | `remotion/public/motion_preview.wav` | `VIDEO_ENGINE/remotion/public/motion_preview.wav` | `MOVE` | `MEDIUM` | Remotion motion graphics code motion_preview.wav |
| MAP-0239 | `remotion/public/resource-gallery-silence.wav` | `VIDEO_ENGINE/remotion/public/resource-gallery-silence.wav` | `MOVE` | `MEDIUM` | Remotion motion graphics code resource-gallery-silence.wav |
| MAP-0240 | `remotion/public/transitions_test.json` | `VIDEO_ENGINE/remotion/public/transitions_test.json` | `MOVE` | `MEDIUM` | Remotion motion graphics code transitions_test.json |
| MAP-0241 | `remotion/public/geo/countries-110m.json` | `VIDEO_ENGINE/remotion/public/geo/countries-110m.json` | `MOVE` | `MEDIUM` | Remotion motion graphics code countries-110m.json |
| MAP-0242 | `remotion/public/resource-fonts/HindGuntur-Bold.ttf` | `VIDEO_ENGINE/remotion/public/resource-fonts/HindGuntur-Bold.ttf` | `MOVE` | `MEDIUM` | Remotion motion graphics code HindGuntur-Bold.ttf |
| MAP-0243 | `remotion/public/resource-fonts/HindGuntur-Regular.ttf` | `VIDEO_ENGINE/remotion/public/resource-fonts/HindGuntur-Regular.ttf` | `MOVE` | `MEDIUM` | Remotion motion graphics code HindGuntur-Regular.ttf |
| MAP-0244 | `remotion/scripts/build_composition.ts` | `VIDEO_ENGINE/remotion/scripts/build_composition.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code build_composition.ts |
| MAP-0245 | `remotion/scripts/caption_probe.ts` | `VIDEO_ENGINE/remotion/scripts/caption_probe.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code caption_probe.ts |
| MAP-0246 | `remotion/scripts/check_composition.ts` | `VIDEO_ENGINE/remotion/scripts/check_composition.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code check_composition.ts |
| MAP-0247 | `remotion/scripts/gen_gallery.ts` | `VIDEO_ENGINE/remotion/scripts/gen_gallery.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code gen_gallery.ts |
| MAP-0248 | `remotion/scripts/gen_gallery_cases.ts` | `VIDEO_ENGINE/remotion/scripts/gen_gallery_cases.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code gen_gallery_cases.ts |
| MAP-0249 | `remotion/scripts/gsap_determinism.ts` | `VIDEO_ENGINE/remotion/scripts/gsap_determinism.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code gsap_determinism.ts |
| MAP-0250 | `remotion/scripts/motion_checks.ts` | `VIDEO_ENGINE/remotion/scripts/motion_checks.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code motion_checks.ts |
| MAP-0251 | `remotion/scripts/motion_list.ts` | `VIDEO_ENGINE/remotion/scripts/motion_list.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code motion_list.ts |
| MAP-0252 | `remotion/scripts/motion_validate.ts` | `VIDEO_ENGINE/remotion/scripts/motion_validate.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code motion_validate.ts |
| MAP-0253 | `remotion/scripts/print_layout.ts` | `VIDEO_ENGINE/remotion/scripts/print_layout.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code print_layout.ts |
| MAP-0254 | `remotion/scripts/print_motion.ts` | `VIDEO_ENGINE/remotion/scripts/print_motion.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code print_motion.ts |
| MAP-0255 | `remotion/scripts/print_theme.ts` | `VIDEO_ENGINE/remotion/scripts/print_theme.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code print_theme.ts |
| MAP-0256 | `remotion/scripts/style_gallery.ts` | `VIDEO_ENGINE/remotion/scripts/style_gallery.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code style_gallery.ts |
| MAP-0257 | `remotion/scripts/_dbg2.ts` | `VIDEO_ENGINE/remotion/scripts/_dbg2.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code _dbg2.ts |
| MAP-0258 | `remotion/scripts/_dbg_diagram.ts` | `VIDEO_ENGINE/remotion/scripts/_dbg_diagram.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code _dbg_diagram.ts |
| MAP-0259 | `remotion/src/accent.ts` | `VIDEO_ENGINE/remotion/src/accent.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code accent.ts |
| MAP-0260 | `remotion/src/anim.ts` | `VIDEO_ENGINE/remotion/src/anim.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code anim.ts |
| MAP-0261 | `remotion/src/camera.ts` | `VIDEO_ENGINE/remotion/src/camera.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code camera.ts |
| MAP-0262 | `remotion/src/config.ts` | `VIDEO_ENGINE/remotion/src/config.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code config.ts |
| MAP-0263 | `remotion/src/fonts.ts` | `VIDEO_ENGINE/remotion/src/fonts.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code fonts.ts |
| MAP-0264 | `remotion/src/gsapTimeline.ts` | `VIDEO_ENGINE/remotion/src/gsapTimeline.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code gsapTimeline.ts |
| MAP-0265 | `remotion/src/index.ts` | `VIDEO_ENGINE/remotion/src/index.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code index.ts |
| MAP-0266 | `remotion/src/Main.tsx` | `VIDEO_ENGINE/remotion/src/Main.tsx` | `MOVE` | `MEDIUM` | Remotion motion graphics code Main.tsx |
| MAP-0267 | `remotion/src/registry.tsx` | `VIDEO_ENGINE/remotion/src/registry.tsx` | `MOVE` | `MEDIUM` | Remotion motion graphics code registry.tsx |
| MAP-0268 | `remotion/src/Root.tsx` | `VIDEO_ENGINE/remotion/src/Root.tsx` | `MOVE` | `MEDIUM` | Remotion motion graphics code Root.tsx |
| MAP-0269 | `remotion/src/sceneContext.ts` | `VIDEO_ENGINE/remotion/src/sceneContext.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code sceneContext.ts |
| MAP-0270 | `remotion/src/SceneRoot.tsx` | `VIDEO_ENGINE/remotion/src/SceneRoot.tsx` | `MOVE` | `MEDIUM` | Remotion motion graphics code SceneRoot.tsx |
| MAP-0271 | `remotion/src/schema.ts` | `VIDEO_ENGINE/remotion/src/schema.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code schema.ts |
| MAP-0272 | `remotion/src/styleKit.ts` | `VIDEO_ENGINE/remotion/src/styleKit.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code styleKit.ts |
| MAP-0273 | `remotion/src/textfit.ts` | `VIDEO_ENGINE/remotion/src/textfit.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code textfit.ts |
| MAP-0274 | `remotion/src/theme.json` | `VIDEO_ENGINE/remotion/src/theme.json` | `MOVE` | `MEDIUM` | Remotion motion graphics code theme.json |
| MAP-0275 | `remotion/src/theme.ts` | `VIDEO_ENGINE/remotion/src/theme.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code theme.ts |
| MAP-0276 | `remotion/src/components/Background.tsx` | `VIDEO_ENGINE/remotion/src/components/Background.tsx` | `MOVE` | `MEDIUM` | Remotion motion graphics code Background.tsx |
| MAP-0277 | `remotion/src/components/Callout.tsx` | `VIDEO_ENGINE/remotion/src/components/Callout.tsx` | `MOVE` | `MEDIUM` | Remotion motion graphics code Callout.tsx |
| MAP-0278 | `remotion/src/components/Camera.tsx` | `VIDEO_ENGINE/remotion/src/components/Camera.tsx` | `MOVE` | `MEDIUM` | Remotion motion graphics code Camera.tsx |
| MAP-0279 | `remotion/src/components/Chart.tsx` | `VIDEO_ENGINE/remotion/src/components/Chart.tsx` | `MOVE` | `MEDIUM` | Remotion motion graphics code Chart.tsx |
| MAP-0280 | `remotion/src/components/checkmarkTimeline.ts` | `VIDEO_ENGINE/remotion/src/components/checkmarkTimeline.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code checkmarkTimeline.ts |
| MAP-0281 | `remotion/src/components/Counter.tsx` | `VIDEO_ENGINE/remotion/src/components/Counter.tsx` | `MOVE` | `MEDIUM` | Remotion motion graphics code Counter.tsx |
| MAP-0282 | `remotion/src/components/domeGeometry.ts` | `VIDEO_ENGINE/remotion/src/components/domeGeometry.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code domeGeometry.ts |
| MAP-0283 | `remotion/src/components/Effect.tsx` | `VIDEO_ENGINE/remotion/src/components/Effect.tsx` | `MOVE` | `MEDIUM` | Remotion motion graphics code Effect.tsx |
| MAP-0284 | `remotion/src/components/FilmLook.tsx` | `VIDEO_ENGINE/remotion/src/components/FilmLook.tsx` | `MOVE` | `MEDIUM` | Remotion motion graphics code FilmLook.tsx |
| MAP-0285 | `remotion/src/components/Grade.tsx` | `VIDEO_ENGINE/remotion/src/components/Grade.tsx` | `MOVE` | `MEDIUM` | Remotion motion graphics code Grade.tsx |
| MAP-0286 | `remotion/src/components/HighlightText.tsx` | `VIDEO_ENGINE/remotion/src/components/HighlightText.tsx` | `MOVE` | `MEDIUM` | Remotion motion graphics code HighlightText.tsx |
| MAP-0287 | `remotion/src/components/IconPop.tsx` | `VIDEO_ENGINE/remotion/src/components/IconPop.tsx` | `MOVE` | `MEDIUM` | Remotion motion graphics code IconPop.tsx |
| MAP-0288 | `remotion/src/components/ImageLayer.tsx` | `VIDEO_ENGINE/remotion/src/components/ImageLayer.tsx` | `MOVE` | `MEDIUM` | Remotion motion graphics code ImageLayer.tsx |
| MAP-0289 | `remotion/src/components/LightLeak.tsx` | `VIDEO_ENGINE/remotion/src/components/LightLeak.tsx` | `MOVE` | `MEDIUM` | Remotion motion graphics code LightLeak.tsx |
| MAP-0290 | `remotion/src/components/MapLayer.tsx` | `VIDEO_ENGINE/remotion/src/components/MapLayer.tsx` | `MOVE` | `MEDIUM` | Remotion motion graphics code MapLayer.tsx |
| MAP-0291 | `remotion/src/components/ShapeAnim.tsx` | `VIDEO_ENGINE/remotion/src/components/ShapeAnim.tsx` | `MOVE` | `MEDIUM` | Remotion motion graphics code ShapeAnim.tsx |
| MAP-0292 | `remotion/src/components/StockVideo.tsx` | `VIDEO_ENGINE/remotion/src/components/StockVideo.tsx` | `MOVE` | `MEDIUM` | Remotion motion graphics code StockVideo.tsx |
| MAP-0293 | `remotion/src/components/Subtitles.tsx` | `VIDEO_ENGINE/remotion/src/components/Subtitles.tsx` | `MOVE` | `MEDIUM` | Remotion motion graphics code Subtitles.tsx |
| MAP-0294 | `remotion/src/generated/index.ts` | `VIDEO_ENGINE/remotion/src/generated/index.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code index.ts |
| MAP-0295 | `remotion/src/generated/scene_1.tsx` | `VIDEO_ENGINE/remotion/src/generated/scene_1.tsx` | `MOVE` | `MEDIUM` | Remotion motion graphics code scene_1.tsx |
| MAP-0296 | `remotion/src/generated/scene_2.tsx` | `VIDEO_ENGINE/remotion/src/generated/scene_2.tsx` | `MOVE` | `MEDIUM` | Remotion motion graphics code scene_2.tsx |
| MAP-0297 | `remotion/src/generated/scene_3.tsx` | `VIDEO_ENGINE/remotion/src/generated/scene_3.tsx` | `MOVE` | `MEDIUM` | Remotion motion graphics code scene_3.tsx |
| MAP-0298 | `remotion/src/generated/scene_4.tsx` | `VIDEO_ENGINE/remotion/src/generated/scene_4.tsx` | `MOVE` | `MEDIUM` | Remotion motion graphics code scene_4.tsx |
| MAP-0299 | `remotion/src/generated/scene_5.tsx` | `VIDEO_ENGINE/remotion/src/generated/scene_5.tsx` | `MOVE` | `MEDIUM` | Remotion motion graphics code scene_5.tsx |
| MAP-0300 | `remotion/src/generated/scene_6.tsx` | `VIDEO_ENGINE/remotion/src/generated/scene_6.tsx` | `MOVE` | `MEDIUM` | Remotion motion graphics code scene_6.tsx |
| MAP-0301 | `remotion/src/generated/scene_7.tsx` | `VIDEO_ENGINE/remotion/src/generated/scene_7.tsx` | `MOVE` | `MEDIUM` | Remotion motion graphics code scene_7.tsx |
| MAP-0302 | `remotion/src/generated/scene_8.tsx` | `VIDEO_ENGINE/remotion/src/generated/scene_8.tsx` | `MOVE` | `MEDIUM` | Remotion motion graphics code scene_8.tsx |
| MAP-0303 | `remotion/src/generated/scene_9.tsx` | `VIDEO_ENGINE/remotion/src/generated/scene_9.tsx` | `MOVE` | `MEDIUM` | Remotion motion graphics code scene_9.tsx |
| MAP-0304 | `remotion/src/library/registry.ts` | `VIDEO_ENGINE/remotion/src/library/registry.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code registry.ts |
| MAP-0305 | `remotion/src/library/resources.tsx` | `VIDEO_ENGINE/remotion/src/library/resources.tsx` | `MOVE` | `MEDIUM` | Remotion motion graphics code resources.tsx |
| MAP-0306 | `remotion/src/motion/compose.tsx` | `VIDEO_ENGINE/remotion/src/motion/compose.tsx` | `MOVE` | `MEDIUM` | Remotion motion graphics code compose.tsx |
| MAP-0307 | `remotion/src/motion/core.ts` | `VIDEO_ENGINE/remotion/src/motion/core.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code core.ts |
| MAP-0308 | `remotion/src/motion/diagram.ts` | `VIDEO_ENGINE/remotion/src/motion/diagram.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code diagram.ts |
| MAP-0309 | `remotion/src/motion/graphics.tsx` | `VIDEO_ENGINE/remotion/src/motion/graphics.tsx` | `MOVE` | `MEDIUM` | Remotion motion graphics code graphics.tsx |
| MAP-0310 | `remotion/src/motion/integrate.ts` | `VIDEO_ENGINE/remotion/src/motion/integrate.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code integrate.ts |
| MAP-0311 | `remotion/src/motion/layout.ts` | `VIDEO_ENGINE/remotion/src/motion/layout.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code layout.ts |
| MAP-0312 | `remotion/src/motion/masks.ts` | `VIDEO_ENGINE/remotion/src/motion/masks.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code masks.ts |
| MAP-0313 | `remotion/src/motion/phrase.ts` | `VIDEO_ENGINE/remotion/src/motion/phrase.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code phrase.ts |
| MAP-0314 | `remotion/src/motion/select.ts` | `VIDEO_ENGINE/remotion/src/motion/select.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code select.ts |
| MAP-0315 | `remotion/src/motion/text.tsx` | `VIDEO_ENGINE/remotion/src/motion/text.tsx` | `MOVE` | `MEDIUM` | Remotion motion graphics code text.tsx |
| MAP-0316 | `remotion/src/motion/textFrame.ts` | `VIDEO_ENGINE/remotion/src/motion/textFrame.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code textFrame.ts |
| MAP-0317 | `remotion/src/motion/textPresets.ts` | `VIDEO_ENGINE/remotion/src/motion/textPresets.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code textPresets.ts |
| MAP-0318 | `remotion/src/patterns/images.json` | `VIDEO_ENGINE/remotion/src/patterns/images.json` | `MOVE` | `MEDIUM` | Remotion motion graphics code images.json |
| MAP-0319 | `remotion/src/patterns/index.ts` | `VIDEO_ENGINE/remotion/src/patterns/index.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code index.ts |
| MAP-0320 | `remotion/src/transitions/by_mood.json` | `VIDEO_ENGINE/remotion/src/transitions/by_mood.json` | `MOVE` | `MEDIUM` | Remotion motion graphics code by_mood.json |
| MAP-0321 | `remotion/src/transitions/custom.tsx` | `VIDEO_ENGINE/remotion/src/transitions/custom.tsx` | `MOVE` | `MEDIUM` | Remotion motion graphics code custom.tsx |
| MAP-0322 | `remotion/src/transitions/index.ts` | `VIDEO_ENGINE/remotion/src/transitions/index.ts` | `MOVE` | `MEDIUM` | Remotion motion graphics code index.ts |
| MAP-0323 | `remotion/public/projects/` | `projects/` | `KEEP` | `LOW` | Generated video preview frames & project media outputs |

---

## 5. Skills, Config, Scripts, Tests & Canonical Stores

| Mapping ID | Current Path | Target Path | Action | Risk | Sensitivity | Responsibility |
|---|---|---|---|---|---|---|
| MAP-0324 | `config/.laxman_pin_hash` | `config/.laxman_pin_hash` | `KEEP` | `HIGH` | `SECRET_OR_CREDENTIAL` | Configuration file .laxman_pin_hash |
| MAP-0325 | `config/approvals_audit.jsonl` | `config/approvals_audit.jsonl` | `KEEP` | `LOW` | `USER_DATA` | Configuration file approvals_audit.jsonl |
| MAP-0326 | `config/approvals_queue.json` | `config/approvals_queue.json` | `KEEP` | `LOW` | `USER_DATA` | Configuration file approvals_queue.json |
| MAP-0327 | `config/eval_baselines.json` | `config/eval_baselines.json` | `KEEP` | `LOW` | `USER_DATA` | Configuration file eval_baselines.json |
| MAP-0328 | `config/eval_candidates.json` | `config/eval_candidates.json` | `KEEP` | `LOW` | `USER_DATA` | Configuration file eval_candidates.json |
| MAP-0329 | `config/eval_suites.json` | `config/eval_suites.json` | `KEEP` | `LOW` | `USER_DATA` | Configuration file eval_suites.json |
| MAP-0330 | `config/llm_settings.json` | `config/llm_settings.json` | `KEEP` | `HIGH` | `SECRET_OR_CREDENTIAL` | Configuration file llm_settings.json |
| MAP-0331 | `config/llm_status.json` | `config/llm_status.json` | `KEEP` | `LOW` | `USER_DATA` | Configuration file llm_status.json |
| MAP-0332 | `config/llm_usage.json` | `config/llm_usage.json` | `KEEP` | `LOW` | `USER_DATA` | Configuration file llm_usage.json |
| MAP-0333 | `config/shared_memory.json` | `config/shared_memory.json` | `KEEP` | `LOW` | `USER_DATA` | Configuration file shared_memory.json |
| MAP-0334 | `scripts/set_laxman_pin.py` | `scripts/set_laxman_pin.py` | `KEEP` | `MEDIUM` | `SOURCE` | Operational utility script set_laxman_pin.py |
| MAP-0335 | `scripts/update_status.py` | `scripts/update_status.py` | `KEEP` | `LOW` | `SOURCE` | Operational utility script update_status.py |
| MAP-0336 | `skills/catalog.json` | `SYSTEM/skills/catalog.json` | `MOVE` | `LOW` | `SOURCE` | Skill definition catalog.json |
| MAP-0337 | `skills/audio/bilingual_preservation/SKILL.md` | `SYSTEM/skills/audio/bilingual_preservation/SKILL.md` | `MOVE` | `LOW` | `SOURCE` | Skill definition SKILL.md |
| MAP-0338 | `skills/motion/kinetic_typography/SKILL.md` | `SYSTEM/skills/motion/kinetic_typography/SKILL.md` | `MOVE` | `LOW` | `SOURCE` | Skill definition SKILL.md |
| MAP-0339 | `skills/motion/remotion_spring_curves/SKILL.md` | `SYSTEM/skills/motion/remotion_spring_curves/SKILL.md` | `MOVE` | `LOW` | `SOURCE` | Skill definition SKILL.md |
| MAP-0340 | `skills/staging/README.md` | `SYSTEM/skills/staging/README.md` | `MOVE` | `LOW` | `SOURCE` | Skill definition README.md |
| MAP-0341 | `skills/validation/layout_safe_zones/SKILL.md` | `SYSTEM/skills/validation/layout_safe_zones/SKILL.md` | `MOVE` | `LOW` | `SOURCE` | Skill definition SKILL.md |
| MAP-0342 | `tests/conftest.py` | `tests/conftest.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture conftest.py |
| MAP-0343 | `tests/test_agent_routes.py` | `tests/test_agent_routes.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_agent_routes.py |
| MAP-0344 | `tests/test_agent_runtime_and_communication.py` | `tests/test_agent_runtime_and_communication.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_agent_runtime_and_communication.py |
| MAP-0345 | `tests/test_analysis_autofix.py` | `tests/test_analysis_autofix.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_analysis_autofix.py |
| MAP-0346 | `tests/test_audio_analysis.py` | `tests/test_audio_analysis.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_audio_analysis.py |
| MAP-0347 | `tests/test_audio_visual_agents_integration.py` | `tests/test_audio_visual_agents_integration.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_audio_visual_agents_integration.py |
| MAP-0348 | `tests/test_browser_profiles.py` | `tests/test_browser_profiles.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_browser_profiles.py |
| MAP-0349 | `tests/test_dome_render.py` | `tests/test_dome_render.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_dome_render.py |
| MAP-0350 | `tests/test_e2e_production_readiness.py` | `tests/test_e2e_production_readiness.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_e2e_production_readiness.py |
| MAP-0351 | `tests/test_emphasis_alignment.py` | `tests/test_emphasis_alignment.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_emphasis_alignment.py |
| MAP-0352 | `tests/test_evaluation_and_self_learning.py` | `tests/test_evaluation_and_self_learning.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_evaluation_and_self_learning.py |
| MAP-0353 | `tests/test_final_qc.py` | `tests/test_final_qc.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_final_qc.py |
| MAP-0354 | `tests/test_gsap_adapter.py` | `tests/test_gsap_adapter.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_gsap_adapter.py |
| MAP-0355 | `tests/test_improve_p05.py` | `tests/test_improve_p05.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_improve_p05.py |
| MAP-0356 | `tests/test_improve_p1.py` | `tests/test_improve_p1.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_improve_p1.py |
| MAP-0357 | `tests/test_improve_p2.py` | `tests/test_improve_p2.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_improve_p2.py |
| MAP-0358 | `tests/test_improve_p3.py` | `tests/test_improve_p3.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_improve_p3.py |
| MAP-0359 | `tests/test_improve_p5.py` | `tests/test_improve_p5.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_improve_p5.py |
| MAP-0360 | `tests/test_improve_p6.py` | `tests/test_improve_p6.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_improve_p6.py |
| MAP-0361 | `tests/test_improve_p7.py` | `tests/test_improve_p7.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_improve_p7.py |
| MAP-0362 | `tests/test_improve_p8.py` | `tests/test_improve_p8.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_improve_p8.py |
| MAP-0363 | `tests/test_improve_p8_render.py` | `tests/test_improve_p8_render.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_improve_p8_render.py |
| MAP-0364 | `tests/test_laxman_approval.py` | `tests/test_laxman_approval.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_laxman_approval.py |
| MAP-0365 | `tests/test_llm_client.py` | `tests/test_llm_client.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_llm_client.py |
| MAP-0366 | `tests/test_llm_gateway.py` | `tests/test_llm_gateway.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_llm_gateway.py |
| MAP-0367 | `tests/test_llm_usage.py` | `tests/test_llm_usage.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_llm_usage.py |
| MAP-0368 | `tests/test_m5.py` | `tests/test_m5.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_m5.py |
| MAP-0369 | `tests/test_m6.py` | `tests/test_m6.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_m6.py |
| MAP-0370 | `tests/test_m7.py` | `tests/test_m7.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_m7.py |
| MAP-0371 | `tests/test_m9.py` | `tests/test_m9.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_m9.py |
| MAP-0372 | `tests/test_m9_autoplan.py` | `tests/test_m9_autoplan.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_m9_autoplan.py |
| MAP-0373 | `tests/test_m9_edits.py` | `tests/test_m9_edits.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_m9_edits.py |
| MAP-0374 | `tests/test_m9_errors.py` | `tests/test_m9_errors.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_m9_errors.py |
| MAP-0375 | `tests/test_m9_input.py` | `tests/test_m9_input.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_m9_input.py |
| MAP-0376 | `tests/test_m9_portrait.py` | `tests/test_m9_portrait.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_m9_portrait.py |
| MAP-0377 | `tests/test_m9_prerender.py` | `tests/test_m9_prerender.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_m9_prerender.py |
| MAP-0378 | `tests/test_m9_promptgen.py` | `tests/test_m9_promptgen.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_m9_promptgen.py |
| MAP-0379 | `tests/test_m9_qc.py` | `tests/test_m9_qc.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_m9_qc.py |
| MAP-0380 | `tests/test_m9_review.py` | `tests/test_m9_review.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_m9_review.py |
| MAP-0381 | `tests/test_m9_ui_inbox.py` | `tests/test_m9_ui_inbox.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_m9_ui_inbox.py |
| MAP-0382 | `tests/test_m9_visual.py` | `tests/test_m9_visual.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_m9_visual.py |
| MAP-0383 | `tests/test_mandatory_llm_gate.py` | `tests/test_mandatory_llm_gate.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_mandatory_llm_gate.py |
| MAP-0384 | `tests/test_motion_codegen.py` | `tests/test_motion_codegen.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_motion_codegen.py |
| MAP-0385 | `tests/test_motion_codegen_and_concurrency.py` | `tests/test_motion_codegen_and_concurrency.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_motion_codegen_and_concurrency.py |
| MAP-0386 | `tests/test_motion_generation.py` | `tests/test_motion_generation.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_motion_generation.py |
| MAP-0387 | `tests/test_motion_library.py` | `tests/test_motion_library.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_motion_library.py |
| MAP-0388 | `tests/test_motion_only_mode.py` | `tests/test_motion_only_mode.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_motion_only_mode.py |
| MAP-0389 | `tests/test_motion_planning.py` | `tests/test_motion_planning.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_motion_planning.py |
| MAP-0390 | `tests/test_motion_validation.py` | `tests/test_motion_validation.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_motion_validation.py |
| MAP-0391 | `tests/test_orchestrator_and_monitoring.py` | `tests/test_orchestrator_and_monitoring.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_orchestrator_and_monitoring.py |
| MAP-0392 | `tests/test_pipeline_gate.py` | `tests/test_pipeline_gate.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_pipeline_gate.py |
| MAP-0393 | `tests/test_pipeline_state_and_checkpoint.py` | `tests/test_pipeline_state_and_checkpoint.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_pipeline_state_and_checkpoint.py |
| MAP-0394 | `tests/test_playwright_e2e.py` | `tests/test_playwright_e2e.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_playwright_e2e.py |
| MAP-0395 | `tests/test_render_port.py` | `tests/test_render_port.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_render_port.py |
| MAP-0396 | `tests/test_render_smoke.py` | `tests/test_render_smoke.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_render_smoke.py |
| MAP-0397 | `tests/test_render_video.py` | `tests/test_render_video.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_render_video.py |
| MAP-0398 | `tests/test_resource_library.py` | `tests/test_resource_library.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_resource_library.py |
| MAP-0399 | `tests/test_scene_segmentation.py` | `tests/test_scene_segmentation.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_scene_segmentation.py |
| MAP-0400 | `tests/test_skills_and_shared_memory.py` | `tests/test_skills_and_shared_memory.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_skills_and_shared_memory.py |
| MAP-0401 | `tests/test_status.py` | `tests/test_status.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_status.py |
| MAP-0402 | `tests/test_stock.py` | `tests/test_stock.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_stock.py |
| MAP-0403 | `tests/test_store_race.py` | `tests/test_store_race.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_store_race.py |
| MAP-0404 | `tests/test_timeline_approval.py` | `tests/test_timeline_approval.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_timeline_approval.py |
| MAP-0405 | `tests/test_timeline_build.py` | `tests/test_timeline_build.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_timeline_build.py |
| MAP-0406 | `tests/test_timeline_media.py` | `tests/test_timeline_media.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_timeline_media.py |
| MAP-0407 | `tests/test_timeline_render_qc_delivery.py` | `tests/test_timeline_render_qc_delivery.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_timeline_render_qc_delivery.py |
| MAP-0408 | `tests/test_transcript_endpoint.py` | `tests/test_transcript_endpoint.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_transcript_endpoint.py |
| MAP-0409 | `tests/test_transcript_review.py` | `tests/test_transcript_review.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_transcript_review.py |
| MAP-0410 | `tests/test_visual_planning.py` | `tests/test_visual_planning.py` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture test_visual_planning.py |
| MAP-0411 | `tests/fixtures/audio_test.wav` | `tests/fixtures/audio_test.wav` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture audio_test.wav |
| MAP-0412 | `tests/fixtures/composition.sample.json` | `tests/fixtures/composition.sample.json` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture composition.sample.json |
| MAP-0413 | `tests/fixtures/gallery.json` | `tests/fixtures/gallery.json` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture gallery.json |
| MAP-0414 | `tests/fixtures/img_01.png` | `tests/fixtures/img_01.png` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture img_01.png |
| MAP-0415 | `tests/fixtures/img_02.png` | `tests/fixtures/img_02.png` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture img_02.png |
| MAP-0416 | `tests/fixtures/img_03.png` | `tests/fixtures/img_03.png` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture img_03.png |
| MAP-0417 | `tests/fixtures/layers_test.json` | `tests/fixtures/layers_test.json` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture layers_test.json |
| MAP-0418 | `tests/fixtures/golden/expected_plan_preview.json` | `tests/fixtures/golden/expected_plan_preview.json` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture expected_plan_preview.json |
| MAP-0419 | `tests/fixtures/golden/expected_plan_preview_all_flags.json` | `tests/fixtures/golden/expected_plan_preview_all_flags.json` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture expected_plan_preview_all_flags.json |
| MAP-0420 | `tests/fixtures/golden/match_report.json` | `tests/fixtures/golden/match_report.json` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture match_report.json |
| MAP-0421 | `tests/fixtures/plan_sample/composition.json` | `tests/fixtures/plan_sample/composition.json` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture composition.json |
| MAP-0422 | `tests/fixtures/plan_sample/cuts.json` | `tests/fixtures/plan_sample/cuts.json` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture cuts.json |
| MAP-0423 | `tests/fixtures/plan_sample/plan_input.txt` | `tests/fixtures/plan_sample/plan_input.txt` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture plan_input.txt |
| MAP-0424 | `tests/fixtures/plan_sample/prompts.txt` | `tests/fixtures/plan_sample/prompts.txt` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture prompts.txt |
| MAP-0425 | `tests/fixtures/plan_sample/prompts_map.json` | `tests/fixtures/plan_sample/prompts_map.json` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture prompts_map.json |
| MAP-0426 | `tests/fixtures/plan_sample/scene_plan.json` | `tests/fixtures/plan_sample/scene_plan.json` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture scene_plan.json |
| MAP-0427 | `tests/fixtures/plan_sample/transcript.json` | `tests/fixtures/plan_sample/transcript.json` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture transcript.json |
| MAP-0428 | `tests/fixtures/plan_sample/transcript_en.json` | `tests/fixtures/plan_sample/transcript_en.json` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture transcript_en.json |
| MAP-0429 | `tests/fixtures/plan_sample/translation.json` | `tests/fixtures/plan_sample/translation.json` | `KEEP` | `MEDIUM` | `SOURCE` | Test suite / fixture translation.json |
| MAP-0430 | `resource-library/` | `NO_MOVE` | `KEEP` | `LOW` | `ASSET` | Canonical resource library (fonts, stock clips, audio) |
| MAP-0431 | `projects/` | `NO_MOVE` | `KEEP` | `LOW` | `USER_DATA` | Canonical user project storage (audio, plans, checkpoints, renders) |
| MAP-0432 | `README.md` | `NO_MOVE` | `KEEP` | `LOW` | `SOURCE` | Project documentation |
| MAP-0433 | `PROJECT_OVERVIEW.md` | `NO_MOVE` | `KEEP` | `LOW` | `SOURCE` | Architecture and operational overview |
| MAP-0434 | `PROJECT_STATUS.md` | `NO_MOVE` | `KEEP` | `LOW` | `SOURCE` | Project state tracker |
| MAP-0435 | `CLAUDE.md` | `NO_MOVE` | `KEEP` | `LOW` | `SOURCE` | Agent instructions and operational rules |
| MAP-0436 | `package.json` | `NO_MOVE` | `KEEP` | `LOW` | `SOURCE` | Root npm workspace scripts |
| MAP-0437 | `requirements.txt` | `NO_MOVE` | `KEEP` | `LOW` | `SOURCE` | Python dependencies manifest |
| MAP-0438 | `runproject.bat` | `NO_MOVE` | `KEEP` | `LOW` | `SOURCE` | Server launch script |
| MAP-0439 | `start.bat` | `NO_MOVE` | `KEEP` | `LOW` | `SOURCE` | Development startup script |
| MAP-0440 | `.gitignore` | `NO_MOVE` | `KEEP` | `LOW` | `SOURCE` | Git tracking exclusion rules |
| MAP-0441 | `.env.example` | `NO_MOVE` | `KEEP` | `LOW` | `SOURCE` | Environment configuration template |

---

## 6. Motion-Only Inventory & Image Mode Deprecation Candidates

The following files are verified candidates for removal in Phase 2B / Phase 3 after callers have been migrated to the Motion-Only architecture. **None have been modified or deleted during Phase 2A**:

| Mapping ID | Candidate Path | Proposed Action | Current Direct Callers | Verification & Safety Plan |
|---|---|---|---|---|
| MAP-0056 | `backend/image_gate.py` | `REMOVE` | Legacy tests only (`test_m7.py`, `test_pipeline_gate.py`, `test_stock.py`); 0 callers in backend | Remove after updating tests to validate motion gates. |
| MAP-0057 | `backend/bg_remove.py` | `REMOVE` | `backend/fill_slots.py` only | Remove alongside `fill_slots.py`. |
| MAP-0058 | `backend/fill_slots.py` | `REMOVE` | Monolithic legacy chain in `pipeline.py` | Decommission when pipeline stages are migrated to Remotion motion generation. |
| MAP-0059 | `backend/prompts_writer.py` | `REMOVE` | Monolithic legacy chain in `pipeline.py` | Remove after visual planning generates motion parameters directly. |
| MAP-0060 | `backend/motion_template_selection.py` | `REMOVE` | None (UI page deleted in Phase A3) | Remove dead helper. |

---

## 7. Migration Gate & Safety Reassurance
- **Planning Only**: All mappings in this report represent the approved target layout. No files have been physically moved, renamed, or deleted.
- **Frozen Files Protection**: All 3 frozen files (`transcribe.py`, `transcript_review.py`, `scene_segmentation.py`) will require strict SHA-256 baseline validation before and after any future relocation.
- **Data Safety**: Canonical directories (`resource-library/` and `projects/`) remain at root and are 100% preserved.