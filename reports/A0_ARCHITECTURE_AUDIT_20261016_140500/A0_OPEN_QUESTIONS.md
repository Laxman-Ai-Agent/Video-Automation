# A0 Open Questions — Decisions Requiring Human Alignment

**Audit ID:** A0-QUES-01  
**Timestamp:** 2026-10-16T14:15:00+05:30  
**Repository Root:** `E:\audio-to-video`  

---

The following questions represent design trade-offs and user preferences that cannot be determined solely from static code evidence. They are presented here for human review prior to initiating Phase A1:

### 1. Laxman Approval Operator Authentication
- **Current State:** The system runs locally without user accounts; reviewer names are recorded as `self_declared` text strings in JSON files.
- **Decision Needed:** For the centralized **Laxman Approval** system (Phase A2), should we:
  - **Option A (Simpler):** Keep an unauthenticated local operator workflow where anyone interacting with the local UI acts as "Laxman" with recorded action timestamps?
  - **Option B (Secure / Auditable):** Introduce a simple local PIN, password, or environment token (`LAXMAN_APPROVAL_SECRET`) to ensure only authorized human input can release render/delivery/skill gates?

### 2. Convergence of Pipeline Execution Engines
- **Current State:** Two execution paths coexist in `backend/`: the legacy `JobRunner` (`backend/jobs.py` + `backend/pipeline.py`) used by existing stage pages, and the canonical 12-stage `PipelineOrchestrator` (`backend/orchestrator.py`) built in Phase 8.
- **Decision Needed:**
  - **Option A (Recommended):** In Phase A3/A4, transition the frontend UI to dispatch directly via `PipelineOrchestrator`, deprecating `jobs.py` while keeping legacy endpoints as wrappers to prevent breaking older tests.
  - **Option B:** Keep both engines permanently separated, reserving `PipelineOrchestrator` for automated batch runs and `JobRunner` for manual stage-by-stage UI stepping.

### 3. Remote Skill Discovery Scope & Network Access
- **Current State:** In Phase 4, remote discovery connectors (GitHub, npm, PyPI) were explicitly marked `DEFERRED & UNTRUSTED`. Skills are currently curated locally in `skills/`.
- **Decision Needed:** When implementing the **Capability & Skill Finder Agent** in Phase A5:
  - **Option A (Offline / Staged Only):** Keep the agent strictly local/offline. The agent can only inspect the project and stage candidate skills manually dropped into `skills/staging/` by the user.
  - **Option B (Connected Discovery with Sandbox):** Allow the agent to query the GitHub API and official documentation for skills, but require all discovered material to be quarantined in `skills/staging/` with mandatory Laxman approval before any local build or execution.

### 4. Legacy `dashboard/` Directory Cleanup
- **Current State:** An unused `dashboard/` directory exists with 14 MB of old node modules (`@reduxjs/toolkit`). It is not referenced by backend or frontend.
- **Decision Needed:**
  - Should `dashboard/` be safely removed in Phase A1 to clean the repository tree, or preserved indefinitely as historical archive?
