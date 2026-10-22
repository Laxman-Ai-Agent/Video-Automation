# A3 — Physical & Logical Boundaries Report

**Document ID:** A3-PLB-01  
**Date:** 2026-10-16 16:05:00 UTC  
**Repository:** `E:\audio-to-video`  
**Git Branch / HEAD:** `agents-building` / `f6989b17372e3cdb42b4c92ab1783b3122a401ae`  

---

## 1. Physical Layout Decision: Zero Mass-Relocation

### 1.1 Rationale for Preserving Established Package Roots
A central design decision verified across Phases A0, A1, and A2 is that **code must NOT be mass-relocated into newly invented physical root folders** (such as `SYSTEM/`, `UI/`, or `VIDEO_ENGINE/`).

The rationale is backed by concrete technical evidence:
1. **TypeScript & Bundling Invariants**:
   - `frontend/tsconfig.app.json` defines root-relative path mappings and alias resolutions. Moving `frontend/` to `UI/` would require cascading modifications across `vite.config.ts`, `index.html`, PostCSS, and test harnesses (`vitest.config.ts`).
   - `remotion/` is structured as a standalone NPM package root with Remotion CLI entry points (`remotion/src/index.ts`, `remotion/src/Root.tsx`). Relocating it breaks Remotion's CLI discovery and Chrome Puppeteer bundling paths.
2. **Python Namespace & Import Stability**:
   - `backend` is the canonical top-level package namespace referenced in hundreds of absolute and relative imports across the codebase (`from backend import ...`, `from ..approvals import ...`).
   - Mass-moving to `VIDEO_ENGINE/` or `SYSTEM/` would introduce high-risk churn, merge conflicts, broken dynamic imports in Uvicorn (`backend.main:app`), and invalidation of frozen test baselines.
3. **Operational & Tooling Boundaries**:
   - Scripts (`runproject.bat`, `start.bat`, `scripts/set_laxman_pin.py`) and development workflows expect the current top-level layout.
   - Retaining physical roots while enforcing strict logical boundaries eliminates 100% of these relocation risks without sacrificing architectural clarity.

---

## 2. Path-by-Path Boundary & Responsibility Table

| Physical Root / Path | Functional Responsibility | Canonical Owner | Primary Consumers | Change Planned in A3? | Architectural Rationale |
|---|---|---|---|---|---|
| `backend/` | FastAPI server, video pipeline engines, approval engine, agent runtime, LLM gateway. | Backend Platform & Video Agents | Frontend UI, external API callers, background workers | **NO** (Preserve root) | Core server package. Contains all execution engines and API route definitions. |
| `backend/agents/` | Agent Registry, stage adapters, lifecycle contracts, inter-agent communication. | Agent Runtime System | Orchestrator, Stage Engines, Frontend Drawer | **YES (Minimal)** | Add `category` field to contracts and registry. Keep files in place. |
| `backend/approvals/` | Central Laxman Approval Engine, PIN service, execution guard, stage adapters. | Security & Governance | Orchestrator, Video Stages, API routes | **NO** | Canonical Phase A2 approval system. Fully tested and verified. |
| `frontend/` | React / Vite SPA, pipeline visualization, operator screens, Laxman Approval UI. | Frontend Platform | Human Operator / Browser | **NO** (Preserve root) | Keep standard SPA root. Update types and add Agent view without folder moving. |
| `remotion/` | Remotion video composition bundle, dynamic Scene components, audio stager. | Remotion Rendering Engine | `motion_animation`, `motion_validation`, `render_video` | **NO** | Standalone Remotion root required by `@remotion/renderer` and headless Chromium. |
| `skills/` | Versioned skill packages (`audio`, `motion`, `staging`, `validation`) and `catalog.json`. | Central Skills Registry | `motion_animation`, `motion_planning`, System Subagents | **NO** | Canonical Phase 4 skill store. External and new skills stage here. |
| `resource-library/` | Canonical fonts, color palettes, motion presets, SVG assets, and preview stills. | Resource Manager | `motion_planning`, `motion_validation`, Remotion bundle | **NO** | Single source of truth for visual design assets. No competing asset stores allowed. |
| `config/` | System configuration, state stores, approval queues, audit trails, memory stores. | Infrastructure & Persistence | Backend services, Orchestrator, Approval Engine | **NO** | Centralized configuration root. Sensitive hash ignored in `.gitignore`. |
| `projects/` | Per-project narration audio, transcripts, plans, composition TSX, checkpoints, final MP4s. | User Project Data Store | Pipeline Orchestrator, Video Stages, Human Operator | **NO** | Contains durable user data, run histories, and checkpoints. Strictly protected. |
| `testing_audio_files/` | Static sample narration audio (`02.wav`, JSON transcripts) for manual testing. | Quality Assurance | QA Engineers, manual tests | **NO** | Useful test fixtures for local testing. |
| `models/` | Local weights for `faster-whisper-medium` (`models/hf/`). | Audio Analyzer (FROZEN) | `backend/transcribe.py` | **NO** | Required binary model assets. Never delete or relocate. |
| `tests/` | Pytest suites covering approvals, agents, pipeline, rendering, QC, and contracts. | Quality Assurance | CI / Development verification | **NO** | Canonical backend test root. |
| `reports/` | Immutable completion reports, architectural audits, and security review packages. | Engineering Governance | Developers, Auditors, AI Agents | **NO** | Append-only documentation records. Do not overwrite past reports. |
| `improvements/` | High-level phase roadmaps, specifications, master prompts, and reference media. | Architecture Team | Planners, Autonomous Agents | **NO** | Authoritative roadmaps and plans. |
| `scripts/` | Operator CLI scripts (`set_laxman_pin.py`, `update_status.py`, etc.). | DevOps & Operations | System Administrators, Operators | **NO** | Standard tooling directory. |
| `.claude/` | Claude Code configuration and legacy worktrees. | Tooling | Claude CLI | **NO (Review candidates)** | Worktrees folder contains obsolete branch candidates for cleanup. |
| `out/` | Legacy manual renders from Oct 8-12 (`gallery.mp4`, `layers.mp4`, etc.). | Ephemeral / Historical | None | **NO (Review candidates)** | Untracked legacy renders. Classified as cleanup candidate. |

---

## 3. Logical Responsibility Boundaries

```
+-----------------------------------------------------------------------------------+
|                              OPERATIONAL BOUNDARIES                               |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  [ HUMAN OPERATOR LAYER ]                                                         |
|  - Laxman Approval UI (/approvals) [PIN Authenticated]                            |
|  - Pipeline Dashboard (/dashboard) & Stage Inspection (/p/:id/step/:stage)        |
|  - Resource Library Explorer (/resources)                                         |
|                                                                                   |
|  [ COORDINATION LAYER ]                                                           |
|  - Main Orchestrator (backend/orchestrator.py)                                    |
|    * Run Serialization & Checkpoint Evaluation                                    |
|    * Event Logging & State Machine (backend/agents/communication.py)              |
|                                                                                   |
|  [ GOVERNANCE & SECURITY LAYER ]                                                  |
|  - Central Approval Engine (backend/approvals/)                                   |
|    * Mandatory PIN Verification & Single-Use Consumption Guard                    |
|    * Append-Only Redacted Audit Log (config/approvals_audit.jsonl)                |
|                                                                                   |
|  [ VIDEO ENGINE PRODUCTION LAYER ] (12 Sequential Active Stages)                  |
|  - Audio Input -> Audio Analyzer [FROZEN] -> Scene Segmentation [FROZEN]          |
|  - Visual Planning -> Motion Planning -> Motion Animation (Custom TSX)            |
|  - Motion Validation -> Timeline Build -> Timeline Approval [HUMAN GATE]          |
|  - Render Video (Remotion Headless) -> Final QC [DUAL GATE] -> Delivery           |
|                                                                                   |
|  [ ASYNCHRONOUS SYSTEM CAPABILITY LAYER ]                                         |
|  - Central Skills Registry (backend/skill_registry.py, skills/catalog.json)       |
|  - Shared Memory Knowledge Store (backend/shared_memory.py)                       |
|  - [PLANNED A5] Capability & Skill Finder Subagent                                |
|  - [PLANNED A6] Skill Factory Subagent                                            |
|                                                                                   |
+-----------------------------------------------------------------------------------+
```

---

## 4. Architectural Invariant Summary

1. **No Duplication of Canonical Facilities**:
   - Exactly one Approval Engine (`backend/approvals/`).
   - Exactly one Skill Registry (`backend/skill_registry.py`).
   - Exactly one Resource Library (`resource-library/`).
   - Exactly one Shared Memory Store (`backend/shared_memory.py`).
   - Exactly one Canonical Orchestrator (`backend/orchestrator.py`).
2. **Stable File Paths**:
   - All established physical paths are maintained. Logical separation is achieved purely through metadata and modular decoupling.
