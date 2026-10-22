# Dedicated Agent Modules Report

**Date:** 2026-10-17  
**Repository:** `E:\audio-to-video`  
**Scope:** Architectural breakdown of the 14 dedicated video generation agent packages under `SYSTEM/agents/video_generation_agents/`.

---

## 1. Directory Structure Standard

Each dedicated agent package strictly implements the approved modular standard:

```text
SYSTEM/agents/video_generation_agents/<agent_id>/
├── __init__.py                # Package export
├── agent.py                   # Dedicated Agent class inheriting from BaseAgent
├── README.md                  # Comprehensive agent specification
├── config/
│   └── agent_config.json      # Runtime timeouts, retries, tools, and capabilities
├── memory/
│   └── memory_policy.json     # Isolation policy, default scope, sharing flags
├── prompts/                   # System prompt definitions and variants
├── history/                   # Agent-specific durable history records
├── tools/                     # Tool wrappers and schema bindings
└── tests/
    └── test_agent.py          # Package unit test suite
```

---

## 2. Agent-by-Agent Detailed Breakdown

### 1. Main Orchestrator Agent (`main_orchestrator`)
- **Location:** `SYSTEM/agents/video_generation_agents/main_orchestrator/`
- **Class:** `MainOrchestratorAgent`
- **Stage:** `pipeline`
- **Role:** High-level coordinator for pipeline execution flow, auto-advancement rules, checkpoint recovery, and error escalation.
- **Allowed Tools:** `job_queue`, `step_graph`, `pipeline_view`
- **Memory Policy:** `scope="agent"`, `isolation_level="strict"`, `allow_project_share=true`.

### 2. Audio Input Agent (`audio_input`)
- **Location:** `SYSTEM/agents/video_generation_agents/audio_input/`
- **Class:** `AudioInputAgent`
- **Stage:** `audio`
- **Role:** Ingests user narration audio, downsamples to 16kHz mono WAV via FFmpeg, and extracts stream duration parameters via FFprobe.
- **Allowed Tools:** `ffmpeg`, `ffprobe`, `store`
- **Memory Policy:** `scope="agent"`, `isolation_level="strict"`, `allow_project_share=true`.

### 3. Audio Analyzer Agent (`audio_analyzer`)
- **Location:** `SYSTEM/agents/video_generation_agents/audio_analyzer/`
- **Class:** `AudioAnalyzerAgent`
- **Stage:** `analyzer`
- **Role:** Performs neural ASR transcription with faster-whisper, phonetics review, bilingual token preservation, and silence detection.
- **Allowed Tools:** `faster-whisper`, `silencedetect`, `llm_client`
- **Skills Bound:** `audio.bilingual_preservation`
- **Frozen Invariants:** Interacts with `VIDEO_ENGINE/stages/transcribe.py` and `transcript_review.py` without modifying code.

### 4. Scene Segmentation Agent (`scene_segmentation`)
- **Location:** `SYSTEM/agents/video_generation_agents/scene_segmentation/`
- **Class:** `SceneSegmentationAgent`
- **Stage:** `segmentation`
- **Role:** Partitions the narration transcript into semantic scenes obeying strict 3-7 second duration constraints, natural sentence pauses, and word boundary timestamps.
- **Allowed Tools:** `llm_client`, `regex_validator`
- **Frozen Invariants:** Strict compatibility with `VIDEO_ENGINE/stages/scene_segmentation.py`.

### 5. Visual Planning Agent (`visual_planning`)
- **Location:** `SYSTEM/agents/video_generation_agents/visual_planning/`
- **Class:** `VisualPlanningAgent`
- **Stage:** `planning`
- **Role:** Generates visual storytelling concepts, background color palettes, bilingual Telugu-to-English translations, and kinetic typography emphasis keywords.
- **Allowed Tools:** `llm_client`, `pydantic_schemas`
- **Skills Bound:** `audio.bilingual_preservation`

### 6. Motion Planning Agent (`motion_planning`)
- **Location:** `SYSTEM/agents/video_generation_agents/motion_planning/`
- **Class:** `MotionPlanningAgent`
- **Stage:** `motion_plan`
- **Role:** Plans kinetic typography layout rhythm, safe area bounding margins, and calculates bounding box collision avoidance.
- **Allowed Tools:** `remotion_planner`, `heuristic_solver`
- **Skills Bound:** `motion.kinetic_typography`, `motion.remotion_spring_curves`, `validation.layout_safe_zones`

### 7. Motion Template Selection Agent (`motion_template_selection`)
- **Location:** `SYSTEM/agents/video_generation_agents/motion_template_selection/`
- **Class:** `MotionTemplateSelectionAgent`
- **Stage:** `motion_template`
- **Role:** Preserved in the 14-agent logical target architecture as `DEPRECATED`. Bypassed in the active Motion-Only workflow.

### 8. Motion Animation Agent (`motion_animation`)
- **Location:** `SYSTEM/agents/video_generation_agents/motion_animation/`
- **Class:** `MotionAnimationAgent`
- **Stage:** `motion_gen`
- **Role:** Generates standalone executable React/TSX animation source code and stages Remotion components.
- **Allowed Tools:** `ast_builder`, `tsc`, `remotion_stager`
- **Skills Bound:** `motion.kinetic_typography`, `motion.remotion_spring_curves`

### 9. Motion & Timeline Validation Agent (`motion_timeline_validation`)
- **Location:** `SYSTEM/agents/video_generation_agents/motion_timeline_validation/`
- **Class:** `MotionValidationAgent`
- **Stage:** `motion_validation`
- **Role:** Applies 12 technical validation rules across the composition, checks resource library integrity, and renders preview still frames.
- **Allowed Tools:** `rule_engine`, `resource_library`, `preview_renderer`
- **Skills Bound:** `validation.layout_safe_zones`

### 10. Timeline Build Agent (`timeline_build`)
- **Location:** `SYSTEM/agents/video_generation_agents/timeline_build/`
- **Class:** `TimelineBuildAgent`
- **Stage:** `timeline`
- **Role:** Compiles multi-track composition layers into a frame-accurate timeline matching audio duration within $\pm 1$ frame at 30 fps.
- **Allowed Tools:** `timeline_compiler`

### 11. Timeline Approval Agent (`timeline_approval`)
- **Location:** `SYSTEM/agents/video_generation_agents/timeline_approval/`
- **Class:** `TimelineApprovalAgent`
- **Stage:** `approval`
- **Role:** Mandatory Human Approval Gate. Enforces cryptographic fingerprint lock (SHA-256) before video rendering is authorized.
- **Allowed Tools:** `sha256_verifier`, `store`

### 12. Render Video Agent (`render_video`)
- **Location:** `SYSTEM/agents/video_generation_agents/render_video/`
- **Class:** `RenderVideoAgent`
- **Stage:** `render`
- **Role:** Executes Remotion rendering in headless Chrome using dynamic ephemeral ports and captures render telemetry.
- **Allowed Tools:** `remotion_renderer`, `ffprobe`

### 13. Final QC Agent (`final_qc`)
- **Location:** `SYSTEM/agents/video_generation_agents/final_qc/`
- **Class:** `FinalQcAgent`
- **Stage:** `qc`
- **Role:** Dual-gate quality control: automated media probe (black frames, freeze, clipping) + mandatory human playback sign-off.
- **Allowed Tools:** `ffprobe_qc`, `opencv_sampler`

### 14. Final Video Delivery Agent (`final_video_delivery`)
- **Location:** `SYSTEM/agents/video_generation_agents/final_video_delivery/`
- **Class:** `FinalVideoDeliveryAgent`
- **Stage:** `final`
- **Role:** Verifies end-to-end provenance, checks SHA-256 integrity match, and serves final video file delivery.
- **Allowed Tools:** `hash_verifier`, `file_streamer`

---

## 3. Package Verification Status

All 14 dedicated agent packages have been validated via automated tests:
- Directory existence and standard file layout: **14/14 PASSED**
- JSON configuration schema validity: **14/14 PASSED**
- Memory policy schema validity: **14/14 PASSED**
- Dedicated unit test execution: **14/14 PASSED**
