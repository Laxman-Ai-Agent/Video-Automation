# Remaining Gaps and Risks Report

**Date:** 2026-10-17  
**Repository:** `E:\audio-to-video`  
**Scope:** Identification of remaining technical debt, operational risks, and runtime prerequisites.

---

## 1. Residual Architectural Items

### 1. Deprecated Status of `motion_template_selection`
- **Current State:** `motion_template_selection` remains registered in `AgentRegistry` with status `DEPRECATED` and has a dedicated package in `SYSTEM/agents/video_generation_agents/motion_template_selection/`.
- **Reason:** Preserves the formal 14-agent logical target architecture established in Phase 2B while maintaining compliance with the operator-approved Motion-Only architecture (Batch 6).
- **Risk Level:** Low.
- **Mitigation:** The agent raises a structured informational notice if invoked directly and is bypassed during normal end-to-end pipeline execution.

### 2. Root Directory `skills/` Residual Directory
- **Current State:** A seed skills directory exists at `E:\audio-to-video\skills/` alongside `SYSTEM/skills/`.
- **Reason:** Legacy tests (e.g. `tests/test_skills_and_shared_memory.py`) check `PROJECT_ROOT / "skills"` if present.
- **Risk Level:** Very Low.
- **Mitigation:** `SYSTEM/registries/skill_registry.py` explicitly prioritizes `SYSTEM/skills/` if `SYSTEM/skills/catalog.json` exists, ensuring the canonical location is always preferred for active agent operations.

---

## 2. External Runtime Dependencies & Environmental Risks

### 1. FFmpeg & FFprobe System Binaries
- **Risk:** `AudioInputAgent` and `FinalQcAgent` require `ffmpeg` and `ffprobe` to be available in the system `PATH`.
- **Severity:** Medium.
- **Mitigation:** `CapabilityFinderAgent` performs preflight environment checks via `shutil.which("ffmpeg")` and reports missing prerequisites before pipeline execution is scheduled.

### 2. Local Faster-Whisper Model Checkpoints
- **Risk:** `AudioAnalyzerAgent` uses faster-whisper for speech transcription. If local model checkpoints in `models/` are missing in a fresh environment, runtime downloads or latency may occur.
- **Severity:** Low.
- **Mitigation:** The pipeline uses cached local checkpoints under `models/` where available.

### 3. Headless Chrome Remotion Port Conflicts
- **Risk:** Concurrent Remotion renders might attempt to bind to port 3000 if hardcoded.
- **Severity:** Low.
- **Mitigation:** `RenderVideoAgent` incorporates dynamic ephemeral port allocation (`test_render_port.py`), isolating each rendering job to an available port.

---

## 3. Summary Risk Matrix

| Risk Item | Impact | Likelihood | Mitigation Strategy | Status |
|:---|:---|:---|:---|:---|
| **Cross-Agent Memory Leakage** | High | Low | Enforced via `ScopedMemoryManager` | **RESOLVED** |
| **Pipeline Interruption by Architecture Agent** | High | Low | Decoupled from `PipelineOrchestrator` | **RESOLVED** |
| **Legacy Test Regressions** | High | Low | Backward-compatibility facades & dual list | **RESOLVED** |
| **Frozen Code Tampering** | Critical | None | Cryptographic SHA-256 verification (100% match) | **RESOLVED** |
| **Skill Injection / Token Leakage** | High | Low | Static AST & regex audits in `SkillFactoryAgent` | **RESOLVED** |
