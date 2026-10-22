# A1 Verified Current Architecture — Ground-Truth Baseline

**Audit ID:** A1-VERIF-01  
**Timestamp:** 2026-10-16T14:40:00+05:30  
**Repository Root:** `E:\audio-to-video`  
**Current Branch / HEAD:** `agents-building` / `f6989b17372e3cdb42b4c92ab1783b3122a401ae`  

---

## 1. Verification of A0 Findings against Live Repository

Every finding from Phase A0 has been re-audited against the live filesystem, configuration files, and test definitions.

| Finding ID | Claim Summary | Source Evidence Paths | Re-verification Result | Status | Confidence |
|---|---|---|---|---|---|
| **A1-V-001** | Flat 14-Agent Registry mixing Orchestrator with Stage Adapters | `backend/agents/registry.py:35-246`, `backend/agents/contracts.py:93-112` | Confirmed `AgentMetadata` lacks `category` field; `main_orchestrator` is registered in same list as 13 stage adapters. Zero System Subagents exist. | **VERIFIED** | High |
| **A1-V-002** | Dual Execution Engines (`JobRunner` vs `PipelineOrchestrator`) | `backend/jobs.py:1-120`, `backend/pipeline.py:1-750`, `backend/orchestrator.py:1-400` | Confirmed `jobs.py` runs step chains for UI routes (`/step/{name}/run`); `orchestrator.py` runs 12-stage DAG with Phase 3 checkpoints. | **VERIFIED** | High |
| **A1-V-003** | Fragmented Human Approvals without Laxman Approval Engine | `backend/timeline_approval.py:1-50`, `backend/final_qc.py:1-100`, `config/eval_candidates.json` | Approvals exist across separate stage files (`timeline_approval_history.json`, `final_qc_review.json`). No central queue or UI named "Laxman Approval" exists. Approvers are unauthenticated `self_declared`. | **VERIFIED** | High |
| **A1-V-004** | Authoritative Skill Registry exists; Autonomous Skill Subagents do not | `backend/skill_registry.py:1-150`, `skills/catalog.json`, `skills/` | Found versioned `SkillRecord`, static security scan (`audit_skill_content`), reuse decision logic. Remote connectors are deferred; no `SkillFinder` or `SkillFactory` agents exist. | **VERIFIED** | High |
| **A1-V-005** | Shared Remotion Staging Mutex Protection | `backend/motion_animation.py:39-45`, `backend/motion_animation.py:658` | Generated TSX is stored in `projects/<pid>/generated_motion/` but copied to shared `remotion/src/generated/` under `_remotion_staging_lock` during tsc and render. | **VERIFIED** | High |
| **A1-V-006** | Canonical Resource Library Integrity | `resource-library/catalog/registry.json`, `backend/resource_library.py:1-50` | Untouched, authoritative font/icon/license registry and render bundle. Deeply integrated with Remotion. | **VERIFIED** | High |
| **A1-V-007** | Frozen Stages Integrity (100% SHA-256 Match) | `backend/transcribe.py`, `backend/transcript_review.py`, `backend/scene_segmentation.py` | Hashes re-verified via SHA-256 script: all 3 match original baseline bit-for-bit. | **VERIFIED** | High |
| **A1-V-008** | Legacy `dashboard/` is 175 MB of Untracked Node Modules | `dashboard/node_modules/`, `dashboard/public/status.json` | Untracked by Git (`git ls-files dashboard` is empty); 11,654 files totaling 175.7 MB; no source code or package.json remains. | **VERIFIED** | High |
| **A1-V-009** | Deep Relative Imports in Stage Adapters | `backend/agents/adapters/stage_adapters.py:1013-1014` | Extensive `from ... import` and `from ...artifact_contracts import` constructs present throughout. | **VERIFIED** | High |

---

## 2. Actual Repository Runtime Roots

```
E:\audio-to-video\
├── backend/                           # Python 3.12 (venv) - Core Application, API & Pipeline
├── frontend/                          # Node.js 20 - Vite + React 19 UI
├── remotion/                          # Node.js 20 - Remotion 4.0 Composition Engine
├── skills/                            # Canonical Markdown Skill Packages & catalog.json
├── resource-library/                  # Canonical Static Font, Icon, and License Registry
├── config/                            # Persistent System-Wide JSON State & Telemetry
├── projects/                          # Per-Project Isolated Workspaces
└── tests/                             # Root Pytest Suite (121 passing tests)
```

---

## 3. Runtime Processes & Communication Boundaries

1. **Backend Web Process (`uvicorn`):**
   - Host: `127.0.0.1:8000`
   - Framework: FastAPI / Starlette
   - Boundaries: Accepts HTTP/REST requests and SSE streams from frontend (`http://localhost:5173`). Interacts with filesystem and spawns subprocesses.
2. **Frontend UI Process (`vite dev`):**
   - Host: `127.0.0.1:5173`
   - Framework: React 19, React Router 8, Tailwind CSS, TanStack Query
   - Boundaries: Runs exclusively in browser sandbox; communicates with backend via typed HTTP client (`frontend/src/api/client.ts`).
3. **Headless Remotion Render Process (`npx remotion render`):**
   - Execution: Subprocess spawned on-demand by `backend/render.py`
   - Runtimes: Node.js 20, Remotion CLI 4.0, headless Google Chrome (`C:\Program Files\Google\Chrome\Application\chrome.exe`)
   - Boundaries: Consumes staged TSX scenes and `timeline.json`; encodes and writes output MP4.
4. **Media Probe Process (`ffprobe`):**
   - Execution: Synchronous subprocess spawned by `backend/media_probe.py`
   - Boundaries: Reads candidate MP4; returns container and stream metadata JSON.

---

## 4. Current State & Artifact Lineage

The active Motion-Only pipeline produces an unbroken cryptographic lineage of artifacts:

```
[audio.wav] (Duration: 1.0s, 44.1kHz PCM mono)
  │ sha256: 7f76...
  ▼
[transcript.json] & [audio_analysis.json] (Stage 2 - Frozen)
  │ sha256: 1888...
  ▼
[scene_segmentation.json] (Stage 3 - Frozen)
  │ sha256: 8aa9...
  ▼
[visual_planning.json] (Stage 4 - Visual Concepts)
  │ [Passed mandatory LLM review]
  ▼
[motion_planning.json] (Stage 5 - Typography & Spring Math)
  │ [Layout safe zone enforcement]
  ▼
[scenes/scene_*.tsx] & [motion_manifest.json] (Stage 6 - Custom React TSX)
  │ [Security AST passed, tsc typecheck passed]
  ▼
[motion_validation_report.json] (Stage 7 - 12 Deterministic Rules)
  │ [0 errors, font availability verified]
  ▼
[timeline.json] (Stage 8 - Frame-Exact Arithmetic)
  │ [15 frames @ 30fps]
  ▼
[timeline_approval_history.json] (Stage 9 - Human Approval Gate)
  │ [Fingerprint locked; render locked without approval]
  ▼
[out.mp4] & [render_report.json] (Stage 10 - Remotion Render)
  │ [Probed via ffprobe: h264, 1920x1080 @ 30fps, aac audio]
  ▼
[final_qc_report.json] & [final_qc_review.json] (Stage 11 - Final QC)
  │ [Playback review approved]
  ▼
[delivery_manifest.json] (Stage 12 - Final Delivery)
  │ [All 4 gates sealed; end-to-end delivery manifest published]
```
