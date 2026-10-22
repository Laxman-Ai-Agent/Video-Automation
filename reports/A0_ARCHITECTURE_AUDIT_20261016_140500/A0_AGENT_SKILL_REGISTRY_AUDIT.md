# A0 Agent, Skill & Registry Audit — Classification & Governance

**Audit ID:** A0-REG-01  
**Timestamp:** 2026-10-16T14:15:00+05:30  
**Repository Root:** `E:\audio-to-video`  

---

## 1. Core Distinction: Agent vs. Skill vs. Service vs. Tool

To establish unambiguous architecture boundaries, components are classified according to strict semantic criteria:

- **Agent:** An autonomous, task-oriented software actor that is invoked with a defined objective, executes multi-step logic or decisions, interacts with other agents via structured messages, and can request tools or skills.
- **Skill:** A versioned, declarative package of procedures, guidelines, domain rules, or layout algorithms (stored as `SKILL.md`). A skill is **not** an autonomous execution process.
- **Service:** An executable, deterministically invoked software subsystem (e.g., `LLMGateway`, `SkillRegistry`, `PipelineStateService`) called by agents, routes, or stages.
- **Tool / Adapter:** A bounded integration component that interfaces directly with an external runtime, executable CLI, or protocol (e.g., `RemotionCLI`, `FFprobe`, `OpenCVSampler`).
- **Registry:** An authoritative, centralized catalog maintaining metadata, versions, checksums, and lifecycle states for system entities (e.g., `AgentRegistry`, `SkillRegistry`, `EvaluationRegistry`).

---

## 2. Video Engine Agents Audit

All Video Engine Agents are registered in `backend/agents/registry.py` and implement `BaseAgent`:

| Agent ID | Registered Name | Adapter Class | Associated Skills | Tools / Permissions | Status in Motion-Only | Verification Evidence |
|---|---|---|---|---|---|---|
| `audio_input` | Audio Input Agent | `AudioInputAdapter` | None | `ffmpeg`, `ffprobe`, `store` | Active | Verified in `stage_adapters.py:65` |
| `audio_analyzer` | Audio Analyzer Agent | `AudioAnalyzerAdapter` | `audio.bilingual_preservation` | `faster-whisper`, `silencedetect`, `llm_client` | Active (FROZEN) | Verified in `stage_adapters.py:115` |
| `scene_segmentation` | Scene Segmentation Agent | `SceneSegmentationAdapter` | None | `llm_client`, `regex_validator` | Active (FROZEN) | Verified in `stage_adapters.py:205` |
| `visual_planning` | Visual Planning Agent | `VisualPlanningAdapter` | `audio.bilingual_preservation` | `llm_client`, `pydantic_schemas` | Active | Verified in `stage_adapters.py:310` |
| `motion_planning` | Motion Planning Agent | `MotionPlanningAdapter` | `motion.kinetic_typography`, `motion.remotion_spring_curves`, `validation.layout_safe_zones` | `remotion_planner`, `heuristic_solver` | Active | Verified in `stage_adapters.py:440` |
| `motion_template_selection` | Motion Template Selection Agent | `MotionTemplateSelectionAdapter` | None | `template_registry` | **Deprecated / Deferred** | Verified in `stage_adapters.py:530` |
| `motion_animation` | Motion Animation Agent | `MotionAnimationAdapter` | `motion.kinetic_typography`, `motion.remotion_spring_curves` | `ast_builder`, `tsc`, `remotion_stager` | Active | Verified in `stage_adapters.py:560` |
| `motion_timeline_validation` | Motion & Timeline Validation Agent | `MotionValidationAdapter` | `validation.layout_safe_zones` | `rule_engine`, `resource_library`, `preview_renderer` | Active | Verified in `stage_adapters.py:690` |
| `timeline_build` | Timeline Build Agent | `TimelineBuildAdapter` | None | `timeline_compiler` | Active | Verified in `stage_adapters.py:760` |
| `timeline_approval` | Timeline Approval Agent | `TimelineApprovalAdapter` | None | `sha256_verifier`, `store` | Active (Human Gate) | Verified in `stage_adapters.py:820` |
| `render_video` | Render Video Agent | `RenderVideoAdapter` | None | `remotion_renderer`, `ffprobe` | Active | Verified in `stage_adapters.py:860` |
| `final_qc` | Final QC Agent | `FinalQcAdapter` | None | `ffprobe_qc`, `opencv_sampler` | Active (Dual Gate) | Verified in `stage_adapters.py:898` |
| `final_video_delivery` | Final Video Delivery Agent | `FinalVideoDeliveryAdapter` | None | `hash_verifier`, `file_streamer` | Active | Verified in `stage_adapters.py:996` |

---

## 3. System Subagents Audit (Planned Candidates)

| Subagent ID | Planned Name | Target Category | Planned Role & Responsibility | Implementation Status | Current Source Evidence |
|---|---|---|---|---|---|
| `skill_finder` | Capability & Skill Finder Agent | `system_subagent` | Autonomous intake of capability gaps, internal skill search first, discovery connector auditing, license & security checks, reuse decisions | **Documented Only** (Not Implemented) | Referenced in Phase 4 plans and A0 instructions; 0 source lines in `backend/` |
| `skill_factory` | Skill Factory Agent | `system_subagent` | Authoring canonical skill packages, structural validation, Remotion test render verification, versioning, changelog, and staging promotion | **Documented Only** (Not Implemented) | Referenced in Phase 4 plans and A0 instructions; 0 source lines in `backend/` |

---

## 4. Current Registry Schema & Classification Gap

### 4.1 `AgentMetadata` Schema Inspection
In `backend/agents/contracts.py`:
```python
@dataclass
class AgentMetadata:
    agent_id: str
    name: str
    version: str = "1.0.0"
    status: AgentStatus = AgentStatus.IMPLEMENTED
    purpose: str = ""
    capabilities: list[str] = field(default_factory=list)
    inputs_schema: str | None = None
    outputs_schema: str | None = None
    stage_id: str | None = None
    allowed_tools: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    owner: str = "agent-system"
    is_frozen: bool = False
```

### 4.2 Deficiencies Identified
1. **Missing `category` field:** Currently, there is no field distinguishing a `video_engine_agent`, a `system_subagent`, or an `orchestrator`.
2. **Orchestrator registered as a Stage Agent:** `main_orchestrator` is placed directly in the agent registry list alongside pipeline adapters, which confuses the relationship between coordinator and workers.
3. **Flat UI Mapping:** The frontend currently queries `GET /agents` and receives all 14 entries without categorization.

---

## 5. Skills Registry Audit

### 5.1 Storage & Schema
- **Catalog File:** `skills/catalog.json`
- **Managed By:** `backend/skill_registry.py` (`SkillRegistry`)
- **Canonical Skill Format:** `skills/<domain>/<name>/SKILL.md`
- **Current Canonical Skills (4 Approved):**
  1. `audio.bilingual_preservation` (Domain: `audio`) - Telugu script preservation rules.
  2. `motion.kinetic_typography` (Domain: `motion`) - Kinetic typography pacing and scale limits.
  3. `motion.remotion_spring_curves` (Domain: `motion`) - Remotion spring damping and physics curves.
  4. `validation.layout_safe_zones` (Domain: `validation`) - 9:16 and 16:9 safe zone margins.

### 5.2 Reuse Decision Engine
- `SkillRegistry.resolve_skill_decision()` provides an automated decision algorithm:
  - If approved skill covers objective -> **`reuse`**
  - If similar skill in domain has permissive license (`Apache-2.0`, `MIT`, `BSD`, `CC-BY`) -> **`adapt`**
  - If no approved skill covers objective -> **`create`** or **`block`**

---

## 6. Duplicates, Overlaps & Canonical Owner Recommendations

| Subsystem | Existing Implementations | Assessment | Canonical Recommendation for A1 |
|---|---|---|---|
| **Agent Registry** | `backend/agents/registry.py` (authoritative) vs hardcoded lists in `CLAUDE.md` and `PROJECT_OVERVIEW.md` | Minor documentation drift | Retain `backend/agents/registry.py` as sole single source of truth |
| **Skill Registry** | `backend/skill_registry.py` (`skills/catalog.json`) vs `resource-library/` | Distinct domains (skills = agent procedures; resource-library = fonts/icons) | Keep separate; do NOT merge |
| **Pipeline Runner** | `backend/jobs.py` (`JobRunner`) vs `backend/orchestrator.py` (`PipelineOrchestrator`) | Functional duplication; two execution engines | Converge on `PipelineOrchestrator` as canonical engine |
| **State Persistence** | `backend/pipeline_state.py` vs per-stage JSON files | Complementary; `pipeline_state.py` indexes stage JSONs | Keep `pipeline_state.py` as state orchestrator |
