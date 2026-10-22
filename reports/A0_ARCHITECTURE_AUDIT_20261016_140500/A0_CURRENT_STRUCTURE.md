# A0 Current Structure — Repository Layout & Runtime Boundaries

**Audit ID:** A0-STRUCT-01  
**Timestamp:** 2026-10-16T14:15:00+05:30  
**Repository Root:** `E:\audio-to-video`  

---

## 1. Top-Level Directory Tree

The following represents the observed filesystem structure at the repository root. Bulky build artifacts, node modules, virtual environments, and temporary caches are explicitly summarized and excluded from raw file listings.

```
E:\audio-to-video\
├── .claude/                           # Claude tooling artifacts & historical worktree (intelligent-hellman-80f23f)
├── .venv/                             # [EXCLUDED] Python 3.12 virtual environment (dependencies)
├── backend/                           # Core Python application: API, agents, orchestrator, pipeline stages
│   ├── agents/                        # Agent runtime, base class, contracts, communication, registry
│   │   └── adapters/                  # Stage-specific adapters bridging logical agents to pipeline modules
│   ├── routes/                        # FastAPI endpoint routers (14 routers)
│   └── *.py                           # 93 Python service, stage, gate, and infrastructure modules
├── config/                            # Persistent system-wide JSON configuration and state
│   ├── eval_results/                  # Output benchmark evaluation records
│   ├── eval_baselines.json            # Approved evaluation quality baselines
│   ├── eval_candidates.json           # Quarantined candidate memory/skill proposals
│   ├── eval_suites.json               # Test case suites for deterministic evaluation
│   ├── llm_settings.json              # Active LLM provider and model configurations
│   ├── llm_status.json                # Runtime health and provider availability telemetry
│   ├── llm_usage.json                 # Persistent token consumption and INR cost tracking
│   └── shared_memory.json             # Central verified technical memory & proposed items
├── dashboard/                         # Legacy read-only monitoring dashboard artifacts
├── docs/                              # Project documentation, architecture specs, operator runbooks
├── frontend/                          # Vite + React 19 + TypeScript single-page application
│   ├── node_modules/                  # [EXCLUDED] Frontend npm package dependencies
│   ├── src/                           # Frontend source code (api/, components/, pages/, pipeline/)
│   ├── tests/                         # Vitest unit and integration test suite
│   ├── package.json                   # Frontend npm package configuration
│   └── tsconfig.app.json              # TypeScript compilation configuration
├── improvements/                      # Phase specifications and complete architecture plans (Phases 0–10, A0)
├── models/                            # Local Whisper and AI model weights
├── node_modules/                      # [EXCLUDED] Root npm package dependencies
├── out/                               # Global video output exports
├── projects/                          # Per-project runtime workspace storage (isolated project dirs)
├── remotion/                          # Remotion video composition engine (independent Node.js project)
│   ├── node_modules/                  # [EXCLUDED] Remotion npm package dependencies
│   ├── public/                        # Render assets (fonts, audio, gallery JSON)
│   ├── src/                           # Remotion composition code, motion library, transitions
│   │   └── generated/                 # Shared staging directory for generated scene TSX components
│   └── package.json                   # Remotion npm package configuration & render scripts
├── reports/                           # Historical completion reports, audit findings, and A0 reports
├── resource-library/                  # Canonical resource library (fonts, icons, license texts, render bundle)
├── scripts/                           # Maintenance and tooling utility scripts
├── skills/                            # Canonical Markdown-based skill packages & catalog
│   ├── audio/                         # Audio domain skills (bilingual_preservation)
│   ├── motion/                        # Motion domain skills (kinetic_typography, remotion_spring_curves)
│   ├── staging/                       # Quarantine directory for unverified candidate skills
│   ├── validation/                    # Validation domain skills (layout_safe_zones)
│   └── catalog.json                   # Authoritative atomic skill catalog manifest
├── testing_audio_files/               # Sample audio files used for local testing
├── tests/                             # Root pytest suite (68 Python test modules)
├── CLAUDE.md                          # Active project governing guide and system rules
├── package.json                       # Root convenience script forwarder
├── PROJECT_OVERVIEW.md                # High-level architecture and user journey guide
├── PROJECT_STATUS.md                  # Historical tracking of phases and milestone completions
├── README.md                          # Quickstart developer guide
├── requirements.txt                   # Python package dependencies
├── runproject.bat                     # Launch script for backend and frontend services
└── start.bat                          # Wrapper startup batch script
```

---

## 2. Important Files & Package Roots

| Package Root | Runtime Environment | Manifest File | Primary Entry Point |
|---|---|---|---|
| **Root Forwarder** | Node.js | `package.json` | `start.bat` / `runproject.bat` |
| **Backend API / Core** | Python 3.12 (venv) | `requirements.txt` | `backend/main.py:app` |
| **Frontend UI** | Node v20 / Vite | `frontend/package.json` | `frontend/src/main.tsx` |
| **Remotion Renderer** | Node v20 / Remotion 4.0 | `remotion/package.json` | `remotion/src/index.ts` |
| **Skill Catalog** | Markdown / JSON | `skills/catalog.json` | `backend/skill_registry.py` |
| **Resource Library** | JSON / Assets | `resource-library/catalog/registry.json` | `backend/resource_library.py` |

---

## 3. Current Entry Points & Process Boundaries

1. **Backend Web Server Process:**
   - Command: `.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`
   - Purpose: Serves all REST APIs, orchestrates pipeline stages, runs background threads for render/eval jobs.
   - Boundaries: Communicates with frontend over HTTP/SSE (port 8000 -> 5173); executes subprocess calls to Remotion, FFmpeg, and FFprobe.
2. **Frontend Development Server Process:**
   - Command: `npm --prefix frontend run dev` (Vite on `http://localhost:5173`)
   - Purpose: Serves the single-page application.
   - Boundaries: Fully isolated browser environment; communicates with backend via typed client in `frontend/src/api/client.ts`.
3. **Headless Remotion Render Process:**
   - Command: Launched on demand via `subprocess.Popen` in `backend/render.py` calling `npx remotion render src/index.ts Main ... --browser-executable=<path>`
   - Purpose: Renders video frames using headless Chrome and muxes audio into MP4.
   - Boundaries: Isolated child process; monitored via stdout telemetry parsers.
4. **Media Inspection Subprocesses:**
   - Invokes `ffprobe` synchronously via `backend/media_probe.py` to inspect containers, codecs, bitrates, audio channels, and duration.

---

## 4. Data & Output Roots

| Directory Path | Isolation Scope | Mutability | Contents & Responsibility |
|---|---|---|---|
| `projects/<pid>/` | Per-Project | Read/Write | Audio files, transcripts, segmentation, plans, TSX scenes, timeline, approvals, QC reports, delivery manifests. |
| `projects/<pid>/generated_motion/` | Per-Project | Read/Write | Generated React/TSX scene files (`scene_*.tsx`) and index.ts for the specific project. |
| `remotion/src/generated/` | **Global Shared** | Read/Write (Mutex) | Staging area where Remotion reads active TSX scenes during render. Protected by `_remotion_staging_lock`. |
| `resource-library/` | Global Shared | Read-Only (Runtime) | Reusable static assets: Noto Sans Telugu, Hind Guntur fonts, SVG icons, SPDX licenses. |
| `config/` | Global Shared | Read/Write (Mutex) | System settings, token usage logs, evaluation baselines, shared memory items. |
| `out/` | Global Shared | Read/Write | Final rendered MP4 output exports. |

---

## 5. Reported vs. Observed Structure Differences

1. **`dashboard/` Directory:**
   - *Reported:* `PROJECT_OVERVIEW.md` reported that `dashboard/` was removed on 2026-10-13.
   - *Observed:* A `dashboard/` folder still exists on disk, containing legacy node modules (`@reduxjs/toolkit`). It is not imported by `backend` or `frontend/src`.
2. **`.claude/worktrees/`:**
   - *Reported:* Not referenced in active documentation.
   - *Observed:* Contains an old worktree `intelligent-hellman-80f23f` with duplicate historical files from an earlier migration.
3. **`skills/` vs `.claude/skills/`:**
   - *Reported in A0 plan:* Plan mentions checking for `.claude/skills/`.
   - *Observed:* `.claude/skills/` does **not** exist. All skills reside canonically in root `skills/` managed by `backend/skill_registry.py`.
4. **Agent Definitions:**
   - *Reported:* Some earlier documents mention a target 14-agent system.
   - *Observed:* `backend/agents/registry.py` implements exactly 14 agents via adapters, but 1 is deprecated (`motion_template_selection`), 1 is the orchestrator (`main_orchestrator`), and 12 are sequential video pipeline stages. System subagents are zero.
