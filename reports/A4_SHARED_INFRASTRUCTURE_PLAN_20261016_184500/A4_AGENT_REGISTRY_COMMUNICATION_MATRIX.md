# A4 Agent Registry and Communication Integration Matrix

**Date:** October 16, 2026  
**Repository:** `E:\audio-to-video`  
**Phase:** A4 — Shared Infrastructure Integration Planning  
**Status:** COMPLETE  

---

## 1. Registry Architecture & Category Model

The system defines 14 stable, canonical agents registered in `backend/agents/registry.py` and categorized according to the Phase A3 schema (`backend/agents/contracts.py`).

### 1.1 Category Enum
```python
class AgentCategory(str, Enum):
    ORCHESTRATOR = "orchestrator"
    VIDEO_ENGINE_AGENT = "video_engine_agent"
    SYSTEM_SUBAGENT = "system_subagent"
```

### 1.2 Authoritative Agent Registration Table

| Agent ID | Name | Category | Pipeline Stage | Frozen? | Status | Purpose / Role |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `main_orchestrator` | Main Orchestrator Agent | `orchestrator` | `pipeline` | No | `IMPLEMENTED` | Top-level coordinator for stage sequencing, concurrency, checkpoints, and recovery. |
| `audio_input` | Audio Input Agent | `video_engine_agent` | `audio` | No | `IMPLEMENTED` | Ingests narration audio, downsamples to 16kHz mono, extracts ffprobe metadata. |
| `audio_analyzer` | Audio Analyzer Agent | `video_engine_agent` | `analyzer` | **YES** | `IMPLEMENTED` | Speech-to-text with faster-whisper, bilingual review, silence detection. |
| `scene_segmentation`| Scene Segmentation Agent | `video_engine_agent` | `segmentation` | **YES** | `IMPLEMENTED` | Partitions transcript into scenes obeying 3-8s duration and word boundaries. |
| `visual_planning` | Visual Planning Agent | `video_engine_agent` | `planning` | No | `IMPLEMENTED` | Generates visual plan, mood, colors, and camera motion per scene. |
| `motion_planning` | Motion Planning Agent | `video_engine_agent` | `motion_plan` | No | `IMPLEMENTED` | Determines animation choreography, easing curves, and composition layers. |
| `motion_animation` | Motion Animation Agent | `video_engine_agent` | `motion_gen` | No | `IMPLEMENTED` | Generates custom executable React/TSX Remotion components. |
| `motion_timeline_validation` | Motion & Timeline Validation Agent | `video_engine_agent` | `motion_validation` | No | `IMPLEMENTED` | Sandboxed TSX compilation check, security AST scan, layout validation. |
| `timeline_build` | Timeline Build Agent | `video_engine_agent` | `timeline` | No | `IMPLEMENTED` | Assembles Remotion timeline composition, snaps audio waveforms, renders stills. |
| `timeline_approval` | Timeline Approval Agent | `video_engine_agent` | `approval` | No | `IMPLEMENTED` | Manages human timeline review, notes, and PIN-authorized sign-off gate. |
| `render_video` | Render Video Agent | `video_engine_agent` | `render` | No | `IMPLEMENTED` | Coordinates Remotion CLI headless Chromium render to MP4. |
| `final_qc` | Final QC Agent | `video_engine_agent` | `qc` | No | `IMPLEMENTED` | Runs deterministic QC checks, LLM review, and playback sign-off gate. |
| `final_video_delivery`| Final Video Delivery Agent | `video_engine_agent` | `final` | No | `IMPLEMENTED` | Produces delivery package, release manifest, and SHA-256 checksums. |
| `motion_template_selection`| Motion Template Selection Agent | `video_engine_agent` | `template` | No | `DEPRECATED` | Legacy reusable template adapter superseded by custom TSX animation. |

---

## 2. Planned System Subagents (Phases A5 & A6)

To prevent phantom agent executions and ensure strict architectural truthfulness, the two cross-project subagents are:
1. **NOT registered as active agents in `registry.py`**:
   `AgentRegistry.validate_registry()` strictly validates that exactly 14 agents exist. Registering unbuilt agents would violate registry invariants and break Phase 1 tests.
2. **Explicitly modeled in `frontend/src/pages/AgentsPage.tsx`**:
   Rendered under a dedicated "System Subagents" tab with prominent `PLANNED` badges, target phase metadata, and descriptions:
   - `capability_finder` (Phase A5): Cross-project semantic matching of visual concepts against Central Skills Registry.
   - `skill_factory` (Phase A6): Safe synthesis, sandboxed Remotion validation, and quarantined staging of new skills.

---

## 3. Durable Agent Communication Protocol

### 3.1 Persistence & Location
All inter-agent messages, handoffs, lifecycle milestones, and gate events are durably recorded in:
`projects/{pid}/agent-communications/communications.jsonl`
- Format: JSON Lines (one UTF-8 JSON object per line).
- Thread-Safety: Protected by per-project mutexes (`communication._PROJECT_LOCKS`).
- Secret Redaction: Automatically masks API keys, bearer tokens, and passwords.

### 3.2 Message Schema
```typescript
interface AgentMessage {
  message_id: string          // UUID hex
  correlation_id: string      // Cross-agent tracing ID (corr_...)
  timestamp: string           // ISO-8601 UTC
  sender: string              // Agent ID
  recipient: string           // Agent ID or "broadcast"
  message_type: "handoff" | "request" | "response" | "event" | "error"
  content: string             // Human-readable summary
  payload: Record<string, any>// Structured data
  input_artifacts: Array<{ name: string; path: string; fingerprint: string }>
  output_artifacts: Array<{ name: string; path: string; fingerprint: string }>
  redactions_applied: string[]
}
```

### 3.3 Real-Time Streaming
Backend provides an SSE streaming endpoint:
`GET /projects/{pid}/agent-communications/stream`
Frontend subscribes via `AgentCommunicationDrawer.tsx` to visualize agent collaborations, review passes, and handoff flows live.

---

## 4. Architectural Answers to Core Questions

1. **Stability of Agent IDs:** All 14 IDs have remained identical since Phase 1. External routes (`/agents/{agent_id}`), adapters, and tests depend on them verbatim.
2. **Category Population:** In `backend/agents/contracts.py`, `category` defaults to `AgentCategory.VIDEO_ENGINE_AGENT`. `main_orchestrator` explicitly sets `AgentCategory.ORCHESTRATOR`. All serialized dictionaries include the `category` field.
3. **Frontend Tolerance:** In `frontend/src/api/agentTypes.ts`, `category?: AgentCategory` is optional. UI defaults to `"video_engine_agent"` if `category` is undefined, guaranteeing backward compatibility.
4. **Single Authoritative Registry:** Exactly ONE agent registry exists (`backend/agents/registry.py`). There are no competing registries.
