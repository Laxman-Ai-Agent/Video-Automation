# LAXMAN-AUTONOMOUS MASTER SYSTEM: Production Operator Guide

**Version:** 1.0.0 Production Release  
**Target Environment:** Windows 10/11 Enterprise / Pro (64-bit)  
**Classification:** Core System Documentation  

---

## 1. System Overview

The **LAXMAN-AUTONOMOUS MASTER SYSTEM** is a specialized, autonomous video generation platform. It transforms Telugu narration audio into broadcast-quality, kinetic-typography cinematic videos through a 12-stage specialist agent architecture powered by Remotion, React/TSX codegen, and deterministic verification rules.

### Core Capabilities
- **Bilingual Visual Planning:** Automatic Telugu transcript analysis with English kinetic typography concept generation.
- **Remotion Kinetic Codegen:** High-performance, frame-accurate animation synthesized as executable TSX components.
- **Cryptographic Approval Gates:** Hardened fingerprint locking at Timeline Approval, and a Final QC decision by the Final QC LLM review (no human gate).
- **Autonomous Task Execution & Recovery:** Self-healing workflow execution with atomic checkpoints, exponential backoff, and state resumption.
- **Multi-Agent Coordination:** Hierarchical orchestration across 14 specialist video generation agents and 7 autonomous system agents.

---

## 2. Supported Environment & Prerequisites

### 2.1 Hardware Requirements
- **CPU:** 4+ Cores (x86_64 / amd64). Whisper and CLIP inference run locally on CPU; no dedicated GPU is strictly required.
- **RAM:** Minimum 8 GB (16 GB recommended for live Chrome Remotion rendering).
- **Disk Storage:** Minimum 10 GB free space for models, node dependencies, audio assets, and video frame buffers.

### 2.2 Software Prerequisites
| Component | Supported Version | Purpose | Verification Command |
|-----------|-------------------|---------|----------------------|
| **Operating System** | Windows 10 / 11 (64-bit) | Host OS | `[System.Environment]::OSVersion` |
| **Python** | 3.12.x (Tested on 3.12.10) | Backend, Agents, AI Inference | `python --version` |
| **Node.js** | v20.x – v24.x (Tested on v24.19) | Remotion & Frontend Toolchain | `node -v` |
| **npm** | v10.x – v11.x (Tested on 11.17) | Package Management | `npm -v` |
| **Google Chrome** | Current Stable (Host Installed) | Headless Browser for Remotion | Check `C:\Program Files\Google\Chrome\Application\chrome.exe` |
| **FFmpeg / ffprobe** | v6.0+ (Tested on v9.0.2) | Audio conversion & Media Probing | `ffmpeg -version`, `ffprobe -version` |

---

## 3. Installation & Configuration

### 3.1 Python Environment Setup
1. Create a dedicated virtual environment in the project root:
   ```powershell
   python -m venv .venv
   ```
2. Activate and install production dependencies:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

### 3.2 Frontend & Remotion Dependencies Setup
Install Node modules across both Remotion and frontend workspaces:
```powershell
npm run install:all
```
*(Alternatively: `npm --prefix remotion install` and `npm --prefix frontend install`)*

### 3.3 Environment Configuration
1. Copy the production template `.env.example` to `.env`:
   ```powershell
   Copy-Item .env.example .env
   ```
2. Open `.env` and configure operational parameters:
   - `WHISPER_MODEL`: Set to `medium` (recommended CPU inference) or `large-v3`.
   - `LLM_PROVIDER`: Set to `auto`, `gemini`, `anthropic`, or `openai`.
   - `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`: Provide valid API key for your chosen model.

---

## 4. Startup, Health Checks & Shutdown

### 4.1 Quick Launch
To launch both the backend API and frontend UI simultaneously:
- **Using PowerShell (Recommended):**
  ```powershell
  .\scripts\start_production.ps1
  ```
- **Using Batch Script:**
  ```cmd
  start.bat
  ```

### 4.2 Manual Launch (Individual Services)
If running services in dedicated terminals:
1. **Backend Server (FastAPI on Port 8000):**
   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn UI.backend.main:app --host 127.0.0.1 --port 8000
   ```
2. **Frontend UI (Vite on Port 5173):**
   ```powershell
   cd frontend
   npm run dev
   ```

### 4.3 Health Check & Connectivity Verification
- **Backend API Health:**
  ```powershell
  Invoke-RestMethod http://127.0.0.1:8000/health
  # Expected Response: {"ok": true}
  ```
- **Orchestrator Capability Check:**
  ```powershell
  Invoke-RestMethod http://127.0.0.1:8000/projects/system/orchestrator/capabilities
  # Verifies browser_ready, ffmpeg_ready, and llm_ready status.
  ```

### 4.4 Graceful Shutdown
- Press `Ctrl+C` in the respective terminal windows.
- Background Chrome render profiles older than 1 hour are automatically swept by the application lifespan context manager.

---

## 5. Submitting & Monitoring Video Generation Work

### 5.1 Via Web UI
1. Navigate to `http://localhost:5173` in any modern browser.
2. Click **Create Project** and upload your input narration audio (`.wav` or `.mp3`).
3. Select desired aspect ratio (`16:9` widescreen or `9:16` vertical).
4. Monitor progression through the visual pipeline stages: Audio Analysis $\to$ Scene Segmentation $\to$ Visual Planning $\to$ Motion Planning $\to$ Motion Codegen $\to$ Motion Validation $\to$ Timeline Assembly.
5. Review generated previews at the **Timeline Approval** gate and submit your review decision.
6. Upon approval, the video encodes automatically and advances to **Final QC**.

### 5.2 Via Autonomous Execution Agent (API / CLI)
Autonomous jobs can be submitted via FastAPI or executed directly using `TaskRunner`:
```python
from SYSTEM.agents.autonomous_execution.task_runner import TaskRunner
from SYSTEM.agents.autonomous_execution.contracts import TaskRequirementSpec, StepExecutionRecord
from backend import config

runner = TaskRunner(project_root=config.PROJECT_ROOT)
# Spec and steps define the required goal and dependencies
report = runner.execute_task(spec, steps, project_dir=project_path)
print(f"Task status: {report.final_state} | Success: {report.success}")
```

### 5.3 Monitoring Endpoints
- **Operational Status:** `GET /projects/{project_id}/orchestrator/status?aspect=16:9`
- **Gate Status:** `GET /projects/{project_id}/orchestrator/gates?aspect=16:9`
- **Audit Logs:** `GET /projects/{project_id}/orchestrator/runs`

---

## 6. Output Storage, Checkpoints & Artifact Directory Layout

```
E:\audio-to-video\
├── projects\
│   └── <project_id>\
│       ├── audio.wav                           # Ingested source audio
│       ├── audio_input_manifest.json           # Audio technical manifest
│       ├── transcript.json                     # Narration transcript & timings
│       ├── scene_segmentation.json             # Scene partition boundaries
│       ├── visual_planning.json                # Bilingual concepts & prompts
│       ├── motion_plan.json                    # Safe zones & typography layouts
│       ├── scenes\                             # Synthesized TSX Remotion components
│       │   └── scene_1.tsx
│       ├── composition.json                    # Full composition manifest
│       ├── timeline.json                       # 30fps multi-track frame timeline
│       ├── timeline_approval.json              # LLM approval decision
│       ├── out.mp4                             # Final encoded video output
│       ├── final_qc_report.json                # ffprobe media analysis
│       ├── delivery_manifest.json              # Signed delivery manifest with SHA-256
│       └── tasks\
│           └── <task_id>\
│               ├── locked_spec.json            # Immutable requirement spec
│               └── checkpoint.json             # Atomic task state checkpoint
```

---

## 7. Approval Gates (decided by LLM reviews)

### 7.1 Stage 10: Timeline Approval Gate
- **Enforcement:** The video rendering agent strictly refuses to encode video unless `timeline_approval.json` contains a matching cryptographic fingerprint.
- **Decision:** The LLM approval review checks the exact timeline version and records its decision (`timeline_approval.auto_approve`); nobody approves by hand. A rejection fails the stage with the exact cause.

### 7.2 Stage 12: Final QC
- **Enforcement:** `ffprobe` and the other checks validate container, codecs, durations, frames and audio deterministically; delivery then requires the Final QC LLM review to approve the exact file (`final_qc.llm_decide`, recorded in `final_qc_review.json`).
- **Decision:** Nobody watches the video. If the decision is `changes_required` or `cannot_determine`, fix the cause in the owning stage (or retry when the LLM was unavailable) and run Final QC again: `POST /projects/{project_id}/final-qc/run`.

---

## 8. Checkpoint Recovery & Task Resumption

If a task is interrupted due to system shutdown, network drop, or pending approval:
1. State is automatically preserved in `tasks/<task_id>/checkpoint.json`.
2. Resume the task by passing `resume=True` to `TaskRunner.execute_task()` or submitting `POST /projects/{pid}/orchestrator/run?resume=true`.
3. The checkpoint manager verifies that completed steps remain unmutated, checks that dependencies are met, and resumes execution from the exact point of interruption without re-running completed work.

---

## 9. Backup, Restore & Disaster Recovery

### 9.1 Essential Data to Back Up
To safeguard project history, templates, and models:
- `projects/`: User project assets, transcripts, and delivered videos.
- `config/`: System configurations, evaluation suites, and shared memory.
- `.env`: Environment variables and credentials.

### 9.2 Restore Procedure
1. Re-install code and dependencies on target machine following Section 3.
2. Restore the backed-up `projects/` and `config/` directories into the project root.
3. Verify directory integrity by running:
   ```powershell
   .venv\Scripts\python.exe scripts/verify_production_release_render.py
   ```

---

## 10. Verification Checks & Regression Testing

Execute the authoritative test suite to verify pipeline integrity:
```powershell
.venv\Scripts\python.exe -m pytest `
  SYSTEM/agents/autonomous_execution/tests/ `
  tests/test_phase8_autonomous_execution.py `
  tests/test_phase7_security_policy.py `
  tests/test_phase6_verification_and_test.py `
  tests/test_phase1_system_agents_restructuring.py `
  tests/test_agent_architecture_reorg.py `
  tests/test_phase5_architecture_validator.py `
  tests/test_phase9_e2e_integration.py `
  -v
```
**Expected Result:** 180 passed, 0 failed.

---

## 11. Known Limitations & Service Boundaries

1. **Local-Only Whisper Audio Ingestion:** Models are read from local Hugging Face cache (`~/.cache/huggingface/hub`). First-time model download requires internet connectivity or a pre-seeded model folder.
2. **Stock Media Search:** Real stock image downloading requires valid `PEXELS_API_KEY` or `PIXABAY_API_KEY`. Without keys, the engine functions exclusively in synthetic kinetic motion typography mode.
3. **LLM Reviews:** In offline or air-gapped environments without LLM provider keys, automated review gates operate using heuristic rule validators.
4. **Remotion Headless Chrome:** Relies on host-installed Google Chrome or Chromium. Ensure Chrome is installed in the default location (`C:\Program Files\Google\Chrome\Application\chrome.exe`) or export `PUPPETEER_EXECUTABLE_PATH`.
