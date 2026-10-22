# Complete Folder Tree & Directory Layout

**Date:** 2026-10-17 04:22:00 IST  
**Repository Root:** `E:\audio-to-video`  
**Git Branch:** `agents-building` | **HEAD:** `f6989b17372e3cdb42b4c92ab1783b3122a401ae`  
**Status:** 100% VERIFIED READABLE TREE  

---

## 1. Documentation of Excluded Directories in the Printed Tree

To ensure readability and prevent a massive 70,000-line output, the following high-density directories are summarized at the folder boundary in this readable tree:
1. **`.venv/`**: (33,830 files, 2.81 GB) — Excluded deep internal site-packages hierarchy.
2. **`node_modules/`** (in root, `frontend/`, `remotion/`, `UI/frontend/`, `VIDEO_ENGINE/remotion/`): (38,000+ files, 1.74 GB) — Excluded vendor dependency files.
3. **`.git/`**: (1,100+ files, ~48 MB) — Excluded internal git objects and packfiles.
4. **`projects/` subdirectories**: (30 individual project folders with cached audio chunks, intermediate frames, and render logs) — Represented by sample project structure.

*Note: Every individual excluded file is cataloged in [`FILE_INVENTORY.csv`](file:///E:/audio-to-video/reports/FINAL_FOLDER_STRUCTURE_INVENTORY_20261017_042000/FILE_INVENTORY.csv).*

---

## 2. Complete Repository Folder Tree

```text
E:\audio-to-video\
├── .claude/                               # Claude assistant project configuration
├── .venv/                                 # [EXCLUDED DEEP DUMP] Python 3.10 virtualenv (33,830 files)
├── SYSTEM/                                # CANONICAL SYSTEM SHARED SERVICES
│   ├── agents/
│   │   ├── shared/                        # Shared agent contracts, communication, base agent
│   │   │   ├── base_agent.py
│   │   │   ├── communication.py
│   │   │   └── contracts.py
│   │   ├── system_agents/                 # Capability finder and Skill factory subagents
│   │   │   ├── capability_finder/
│   │   │   └── skill_factory/
│   │   └── video_generation_agents/       # 14 Canonical Video Generation Agents
│   │       ├── audio_analyzer.py
│   │       ├── audio_intake.py
│   │       ├── final_delivery.py
│   │       ├── final_qc.py
│   │       ├── kinetic_typography.py
│   │       ├── main_orchestrator.py
│   │       ├── motion_animation.py
│   │       ├── motion_architect.py
│   │       ├── motion_planning.py
│   │       ├── motion_template_selection.py
│   │       ├── motion_validation.py
│   │       ├── scene_segmentation.py
│   │       ├── timeline_approval.py
│   │       ├── timeline_assembly.py
│   │       ├── video_rendering.py
│   │       └── visual_concept.py
│   ├── approvals/                         # Laxman Approval Engine & Security PIN Service
│   │   ├── approval_engine.py
│   │   ├── approval_models.py
│   │   └── pin_service.py
│   ├── core/                              # Central error handling, logging, and core types
│   │   ├── errors.py
│   │   └── logging.py
│   ├── llm/                               # Central LLM Gateway & Token Usage Telemetry
│   │   ├── client.py
│   │   ├── llm_gateway.py
│   │   ├── llm_usage.py
│   │   └── usage_tracker.py
│   ├── memory/                            # Central Shared Memory Store & Service
│   │   ├── shared_memory.py
│   │   └── store.py
│   ├── observability/                     # Evaluation Engine, Self-Learning, Metrics
│   │   └── evaluation.py
│   └── registries/                        # Canonical Central Registries
│       ├── agent_registry.py
│       └── skill_registry.py
├── UI/                                    # CANONICAL PRESENTATION LAYER
│   ├── backend/                           # FastAPI Backend Services
│   │   ├── main.py                        # Canonical Application Entry Point
│   │   ├── api_models.py
│   │   ├── llm_client.py
│   │   ├── store.py
│   │   └── routes/                        # 15 Domain Routers
│   │       ├── agents.py
│   │       ├── approvals.py
│   │       ├── evaluation.py
│   │       ├── llm.py
│   │       ├── memory.py
│   │       ├── orchestrator.py
│   │       ├── pipeline.py
│   │       ├── projects.py
│   │       ├── resources.py
│   │       ├── results.py
│   │       ├── review.py
│   │       ├── run.py
│   │       ├── skills.py
│   │       ├── uploads.py
│   │       └── visual.py
│   └── frontend/                          # Canonical React 19 Frontend SPA
│       ├── package.json                   # React 19.3.0 manifest
│       ├── vite.config.ts
│       ├── tsconfig.app.json
│       ├── node_modules/                  # [JUNCTION -> E:\audio-to-video\frontend\node_modules]
│       ├── public/
│       ├── src/
│       │   ├── api/                       # Typed backend client adapters
│       │   ├── components/                # Reusable UI widgets & Agent drawers
│       │   ├── features/                  # Flowchart & pipeline visualization
│       │   ├── pages/                     # Agents, Approvals, LLM Usage, Pipeline pages
│       │   ├── stores/                    # Zustand client state management
│       │   └── App.tsx
│       └── tests/                         # Vitest unit & integration tests (16 test files)
├── VIDEO_ENGINE/                          # CANONICAL VIDEO GENERATION & COMPOSITION ENGINE
│   ├── ffmpeg/                            # FFmpeg Audio Normalization & Concat Integrations
│   │   ├── audio_processing.py
│   │   ├── media_probe.py
│   │   └── video_assembly.py
│   ├── pipeline/                          # Pipeline Orchestrator & Execution Engine
│   │   ├── orchestrator.py                # Sole Canonical PipelineOrchestrator
│   │   ├── stage_adapters.py              # Adapter registry for pipeline progression
│   │   ├── state_manager.py               # State contracts and checkpoints
│   │   └── browser_profiles.py            # Headless browser session manager
│   ├── remotion/                          # Remotion Video Rendering Project
│   │   ├── package.json
│   │   ├── remotion.config.ts
│   │   ├── node_modules/                  # [JUNCTION -> E:\audio-to-video\remotion\node_modules]
│   │   ├── public/                        # Render fonts and preview assets
│   │   └── src/                           # Motion compositions, templates, layouts
│   └── stages/                            # 12 Active Stages + 1 Helper Module
│       ├── transcribe.py                  # [FROZEN] Audio Intake & Transcription
│       ├── audio_analyzer.py              # Audio Analysis & LLM Review
│       ├── scene_segmentation.py          # [FROZEN] Scene Slicing Heuristics
│       ├── transcript_review.py           # [FROZEN] Interactive Review Gate
│       ├── visual_planning.py             # Visual Concept & Design
│       ├── motion_planning.py             # Motion Pacing & Layout Math
│       ├── motion_template_selection.py   # [HELPER] Internal Template Evaluation
│       ├── motion_animation.py            # Remotion TSX Codegen
│       ├── motion_timeline_validation.py  # 12-Check Deterministic Safety
│       ├── timeline_build.py              # Composition Assembly
│       ├── timeline_approval.py           # Pre-Render Approval Gate
│       ├── render_video.py                # Remotion Execution
│       ├── final_qc.py                    # Technical QC & Checks
│       └── final_video_delivery.py        # Artifact Packaging
├── backend/                               # [LEGACY_BUT_IN_USE] 120 legacy Python modules
├── config/                                # Persistent Runtime Configurations
│   ├── approvals_audit.jsonl
│   ├── approvals_queue.json
│   ├── eval_baselines.json
│   ├── eval_candidates.json
│   ├── eval_suites.json
│   ├── llm_usage.json
│   └── shared_memory.json
├── docs/                                  # Architectural Design & Specs (motion.md, etc.)
├── frontend/                              # [LEGACY_STORE] Physical directory hosting node_modules
├── improvements/                          # Improvement Plans (A0-A4, Phase 1-10)
├── models/                                # faster-whisper neural network weights (1.53 GB)
├── projects/                              # User project storage (30 video projects)
├── remotion/                              # [LEGACY_STORE] Physical directory hosting node_modules
├── reports/                               # Migration Reports & Verification Audits
├── resource-library/                      # Shared fonts, music, audio SFX, motion assets
├── scripts/                               # Maintenance & CLI tools (set_laxman_pin.py)
├── skills/                                # Central Agent Skill instruction files
├── tests/                                 # Multi-Suite Python Tests (68 test files)
├── CLAUDE.md                              # Main operator instructions
├── PROJECT_OVERVIEW.md                    # System architecture overview
├── PROJECT_STATUS.md                      # Milestone log
└── requirements.txt                       # Python dependencies
```
