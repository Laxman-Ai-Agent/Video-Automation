# A3 — Agent Ownership Matrix

**Document ID:** A3-AOM-01  
**Date:** 2026-10-16 16:05:00 UTC  
**Repository:** `E:\audio-to-video`  
**Git Branch / HEAD:** `agents-building` / `f6989b17372e3cdb42b4c92ab1783b3122a401ae`  

---

## 1. Classification Architecture

In accordance with confirmed architectural decisions, all agents are classified into three distinct logical groups without altering existing, stable agent IDs:

1. **`orchestrator`**:
   - The central coordinator that schedules, serializes, and monitors pipeline execution.
   - It is not a sequential stage in the video production sequence; it oversees all stages.
2. **`video_engine_agent`**:
   - Agents that execute specific sequential stages of the video production pipeline.
   - Aligned with the 12 active stages (+ 1 deprecated stage preserved for backward compatibility).
3. **`system_subagent`**:
   - Cross-project, reusable background capabilities that operate outside the sequential video pipeline.
   - Invoked on-demand by human operators or orchestrator tasks (planned for Phases A5 and A6).

---

## 2. Complete Logical Agent Matrix

| Agent ID | Display Name | Logical Category | Implementation Status | Stage ID | Canonical Module / Adapter | Primary Inputs | Produced Artifacts | Consumers | Evidence Path |
|---|---|---|---|---|---|---|---|---|---|
| `main_orchestrator` | Main Orchestrator Agent | `orchestrator` | `implemented` | `pipeline` | `backend/orchestrator.py`<br>`MainOrchestratorAdapter` | Pipeline config, project ID, run parameters, approval states | `runs/<run_id>.json`, run state, monitoring telemetry | Operator UI, all pipeline stages, event log | `backend/agents/registry.py:38` |
| `audio_input` | Audio Input Agent | `video_engine_agent` | `implemented` | `audio` | `backend/assets.py`<br>`AudioInputAdapter` | Raw user narration audio (`audio.mp3`, `audio.wav`) | Downsampled mono audio (`audio_16k.wav`), duration | `audio_analyzer`, `timeline_build` | `backend/agents/registry.py:52` |
| `audio_analyzer` | Audio Analyzer Agent | `video_engine_agent` | `implemented` (FROZEN) | `analyzer` | `backend/transcribe.py`<br>`AudioAnalyzerAdapter` | `audio_16k.wav`, Whisper medium model | `transcript.json`, silence markers, phonetics review | `scene_segmentation`, `visual_planning` | `backend/agents/registry.py:66` |
| `scene_segmentation` | Scene Segmentation Agent | `video_engine_agent` | `implemented` (FROZEN) | `segmentation` | `backend/scene_segmentation.py`<br>`SceneSegmentationAdapter` | `transcript.json`, audio duration | `scenes.json` (semantic scene boundaries) | `visual_planning`, `motion_planning` | `backend/agents/registry.py:82` |
| `visual_planning` | Visual Planning Agent | `video_engine_agent` | `implemented` | `planning` | `backend/visual_planning.py`<br>`VisualPlanningAdapter` | `scenes.json`, `transcript.json`, LLM Gateway | `visual_planning.json`, `visual_plan.json` | `motion_planning`, `visual` routes | `backend/agents/registry.py:97` |
| `motion_planning` | Motion Planning Agent | `video_engine_agent` | `implemented` | `motion_plan` | `backend/motion_planning.py`<br>`MotionPlanningAdapter` | `visual_planning.json`, safe area rules, typography metrics | `motion_plan.json`, kinetic typography rhythm | `motion_animation`, `motion_validation` | `backend/agents/registry.py:112` |
| `motion_template_selection` | Motion Template Selection Agent | `video_engine_agent` | `deprecated` | `motion_template` | `backend/motion_template_selection.py`<br>`MotionTemplateSelectionAdapter` | N/A (bypassed in Motion-Only mode) | Preserved schema metadata only | None (historical adapter compatibility) | `backend/agents/registry.py:131` |
| `motion_animation` | Motion Animation Agent | `video_engine_agent` | `implemented` | `motion_gen` | `backend/motion_animation.py`<br>`MotionAnimationAdapter` | `motion_plan.json`, custom TSX code generator | Executable `scene_NN.tsx` components, Remotion bundle | `motion_validation`, `remotion` compiler | `backend/agents/registry.py:145` |
| `motion_timeline_validation` | Motion & Timeline Validation Agent | `video_engine_agent` | `implemented` | `motion_validation` | `backend/motion_validation.py`<br>`MotionValidationAdapter` | Generated `scene_NN.tsx`, 12 validation rules, resource library | `validation_report.json`, preview stills | `timeline_build`, `timeline_approval` | `backend/agents/registry.py:163` |
| `timeline_build` | Timeline Build Agent | `video_engine_agent` | `implemented` | `timeline` | `backend/timeline_build.py`<br>`TimelineBuildAdapter` | Validated scenes, audio timing, composition config | `timeline.json`, Remotion root composition | `timeline_approval`, `render_video` | `backend/agents/registry.py:178` |
| `timeline_approval` | Timeline Approval Agent | `video_engine_agent` | `implemented` | `approval` | `backend/approvals/adapters/timeline_adapter.py`<br>`TimelineApprovalAdapter` | `timeline.json`, action fingerprint, verified Laxman PIN | Cryptographic approval state, `approvals_audit.jsonl` | `render_video`, execution guard | `backend/agents/registry.py:192` |
| `render_video` | Render Video Agent | `video_engine_agent` | `implemented` | `render` | `backend/render_video.py`<br>`RenderVideoAdapter` | Approved timeline, Remotion headless runner (`render.py`) | Staged render `out.mp4`, `render_report.json` | `final_qc`, pipeline monitor | `backend/agents/registry.py:207` |
| `final_qc` | Final QC Agent | `video_engine_agent` | `implemented` | `qc` | `backend/final_qc.py`<br>`FinalQcAdapter` | `out.mp4`, `render_report.json`, media probe, human sign-off | Dual-gate QC record (`qc_report.json`), delivery authorization | `final_video_delivery` | `backend/agents/registry.py:221` |
| `final_video_delivery` | Final Video Delivery Agent | `video_engine_agent` | `implemented` | `final` | `backend/routes/results.py`<br>`FinalVideoDeliveryAdapter` | Authorized `qc_report.json`, `out.mp4` | Final delivery manifest, SHA-256 verification hash | User download, public presentation | `backend/agents/registry.py:234` |
| `capability_finder` | Capability & Skill Finder Agent | `system_subagent` | `planned` (Phase A5) | `system_skills` | `backend/agents/system/skill_finder.py` (Planned) | User capability requests, repository skills catalog, external repo | Staged discovery results, candidate skill proposals | `skill_factory`, Laxman Approval | `improvements/A1_.../06_...md` |
| `skill_factory` | Skill Factory Agent | `system_subagent` | `planned` (Phase A6) | `system_factory` | `backend/agents/system/skill_factory.py` (Planned) | Skill proposals, Remotion test environment, evaluation suites | Author canonical `SKILL.md`, test renders, promotion requests | Central Skills Registry, Evaluation system | `improvements/A1_.../06_...md` |

---

## 3. Subsystem Invariants & Guarantees

1. **Zero Agent ID Mutations**:
   - All 14 existing agent IDs (`main_orchestrator`, `audio_input`, ..., `final_video_delivery`) are preserved verbatim.
   - Historical records in `projects/<pid>/agents/communications.jsonl` remain 100% valid.
2. **Sequential Pipeline Isolation**:
   - Only `video_engine_agent` instances with active stage IDs participate in the 12-stage sequential video pipeline graph.
   - `main_orchestrator` coordinates the graph but does not appear as a stage box.
   - `system_subagent` instances are strictly asynchronous and on-demand; they never appear in the sequential stage layout.
3. **Deprecation Handling**:
   - `motion_template_selection` is retained in the registry with `status=AgentStatus.DEPRECATED`. It is filtered out from active pipeline displays while remaining queryable via `/agents/motion_template_selection`.
