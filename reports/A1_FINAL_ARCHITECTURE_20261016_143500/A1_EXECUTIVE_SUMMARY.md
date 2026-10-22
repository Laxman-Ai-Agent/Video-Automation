# A1 Executive Summary — Final Architecture & Ownership Plan

**Planning Date:** 2026-10-16T14:40:00+05:30  
**Target Repository:** `E:\audio-to-video`  
**Current Branch / HEAD:** `agents-building` / `f6989b17372e3cdb42b4c92ab1783b3122a401ae`  
**Phase:** A1 — Final Architecture & Ownership Planning (Strictly Planning & Recommendation Only)  
**Report Location:** `reports/A1_FINAL_ARCHITECTURE_20261016_143500/`  

---

## 1. Statement of Non-Implementation

**Zero code, configuration, dependency, or filesystem changes were made during Phase A1.**  
No files were moved, renamed, deleted, or reformatted. No packages were installed or updated. No ASR, Audio Analyzer, Transcript Review, Scene Segmentation, real project pipeline, media generation, Remotion render, or FFmpeg render was executed. This phase establishes the definitive, evidence-backed architectural blueprint, ownership boundaries, and phased roadmap for human review and explicit authorization prior to any implementation.

---

## 2. Key Architecture Decisions Applied

1. **PIN-Protected Laxman Approval:**
   - As directed by the user, **Laxman Approval requires a PIN** for all protected actions (rendering, final delivery, skill promotion, memory promotion).
   - Actions fail closed if the PIN is missing or invalid.
   - The secret is strictly managed outside Git (via `LAXMAN_APPROVAL_PIN` environment variable or local salted hash in `config/.laxman_pin_hash`), verified using constant-time comparison, and never printed to logs or responses.
2. **Simple, Permanent, Maintainable Architecture:**
   - **No mass physical file relocation.** The stable top-level roots (`backend/`, `frontend/`, `remotion/`, `skills/`, `resource-library/`, `config/`, `projects/`, `tests/`, `docs/`) remain intact.
   - Architectural separation is achieved through clear logical namespaces, typed registry categories, and dedicated UI sections rather than risky directory moves that would break 121 passing tests and deep relative imports.
3. **Strict Tripartite Agent Separation:**
   - **`orchestrator`**: `main_orchestrator` coordinates tasks and stage progression; it is a coordinator, **not** a video pipeline stage.
   - **`video_engine_agent`**: 12 active stage adapters + 1 deprecated adapter executing sequential video transformation.
   - **`system_subagent`**: Reusable project-wide background capabilities (Capability & Skill Finder Agent, Skill Factory Agent). They are **never** placed into the sequential 12-stage video pipeline.
4. **Gradual Execution Engine Convergence:**
   - The codebase currently has two execution pathways: legacy `JobRunner` (`backend/jobs.py` / `pipeline.py`) and canonical `PipelineOrchestrator` (`backend/orchestrator.py`).
   - A gradual, 5-step reversible migration plan is defined to transition frontend stage triggers to the canonical Orchestrator while keeping legacy endpoints as wrappers to protect existing test suites.
5. **Evidence-Based Cleanup Candidate Policy:**
   - No files are deleted during A1.
   - All candidate files are categorized as `KEEP`, `REMOVE-CANDIDATE`, `REFACTOR`, or `VERIFY` based on static references, build/test scripts, and Git tracking.
   - Legacy `dashboard/` is confirmed as 175 MB of untracked, orphaned node modules and designated `REMOVE-CANDIDATE` for later approved cleanup. `STATUS.json` is linked to `tests/test_status.py` and designated `VERIFY` / `REFACTOR` to avoid breaking test suites.

---

## 3. High-Level Target Architecture Overview

```
E:\audio-to-video\
├── backend/                           # Core Python application
│   ├── agents/                        # Agent runtime & registry
│   │   ├── base_agent.py              # BaseAgent contract & memory/skill access
│   │   ├── registry.py                # Central AgentRegistry (enhanced with category enum)
│   │   ├── communication.py           # Durable JSONL inter-agent messaging
│   │   ├── adapters/                  # Video Engine Stage Adapters (12 active + 1 deprecated)
│   │   └── system/                    # [Planned A5-A6] System Subagents (SkillFinder, SkillFactory)
│   ├── orchestrator.py                # Canonical Pipeline Orchestrator (PipelineOrchestrator)
│   ├── approvals/                     # [Planned A2] Central Laxman Approval Engine & PIN Verification
│   ├── pipeline_state.py              # Canonical atomic state & checkpoint service
│   ├── artifact_contracts.py          # Strict artifact schema validation & path confinement
│   ├── llm_gateway.py                 # Central LLM Gateway (Claude, OpenAI, Gemini)
│   ├── llm_review.py                  # Fail-closed stage review gates
│   ├── skill_registry.py              # Authoritative Skill Catalog manager
│   ├── shared_memory.py               # 3-tier shared technical memory service
│   ├── evaluation.py                  # Benchmarking, candidate proposals & rollback
│   ├── routes/                        # FastAPI REST API routers (UI-facing BFF layer)
│   └── [stage modules]                # Video engine stages (audio, visual, motion, render, qc)
├── frontend/                          # Vite + React 19 UI
│   ├── src/
│   │   ├── api/                       # Typed backend client (client.ts, agentTypes, skillTypes)
│   │   ├── components/                # Reusable UI components & drawers
│   │   ├── pages/                     # Application screens
│   │   │   ├── LaxmanApprovalPage.tsx # [Planned A2] Central Operator Approval Inbox
│   │   │   ├── AgentsDirectoryPage.tsx# [Planned A1] Dual-section Directory (Video Engine vs System)
│   │   │   └── ...                    # Existing stage pages
│   │   └── pipeline/                  # Flowchart & auto-advance hooks
├── remotion/                          # Remotion video engine (independent Node.js project)
├── skills/                            # Canonical Markdown skill packages & catalog
├── resource-library/                  # Canonical font/icon/asset library
├── config/                            # Persistent system configuration (eval, llm, memory)
├── projects/                          # Per-project isolated workspaces
└── tests/                             # Pytest test suites (Phases 1-10, A1+)
```

---

## 4. Implementation Roadmap Summary (Phases A1–A7)

- **A1: Final Architecture & Ownership Planning** (Current Phase: Complete blueprints, zero code changes).
- **A2: Laxman Approval Engine & Dedicated UI** (Build PIN-protected authorization service, central request queue, and `/approvals` inbox screen).
- **A3: Orchestrator Engine Convergence & Backend Wrappers** (Route pipeline stage triggers to canonical Orchestrator; wrap legacy `jobs.py`).
- **A4: Frontend Orchestrator Integration & UI Alignment** (Connect frontend flowchart and stage pages to orchestrator monitoring endpoints).
- **A5: Capability & Skill Finder Agent** (Implement internal-first lookup, sandboxed discovery connectors, license/security auditing).
- **A6: Skill Factory Agent** (Implement canonical skill authoring, Remotion test render verification, and Laxman approval promotion).
- **A7: Repository Cleanup & Production Hardening** (Execute approved deletions for `REMOVE-CANDIDATE` items; run full regression test suites).

---

## 5. Next Action

**Execution is stopped.** Please review the reports in `reports/A1_FINAL_ARCHITECTURE_20261016_143500/`. Await explicit user authorization before initiating Phase A2 implementation.
