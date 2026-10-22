---
skill_id: timeline.composition_assembly
name: Multi-Track Timeline Composition and Frame Alignment
domain: timeline
version: 1.0.0
summary: Mathematical frame alignment, audio-locked timeline assembly, transition scheduling, and gap/overlap prevention at 30 fps.
status: approved
source: local
license: Apache-2.0
license_evidence: Authored internally for Dark World Video Generation Agent.
risk_level: low
capabilities:
  - timeline-assembly
  - frame-alignment
  - transition-scheduling
  - audio-locked-duration
  - gap-overlap-prevention
tags:
  - timeline
  - assembly
  - framerate
  - transitions
  - remotion
dependencies: []
compatible_agents:
  - timeline_assembly
  - timeline_approval_gatekeeper
compatible_project_modes:
  - motion_only
input_contracts:
  scenes:
    type: list
    description: Ordered list of scene objects with scene_id and duration_seconds
  audio_duration_seconds:
    type: float
    description: Ground-truth narration duration in seconds
  fps:
    type: integer
    default: 30
  transition_type:
    type: string
    options:
      - cut
      - crossfade
      - wipe
      - slide
    default: cut
  aspect_ratio:
    type: string
    options:
      - "9:16"
      - "16:9"
    default: "9:16"
output_contracts:
  total_frames:
    type: integer
    description: Exact duration in frames locked to audio (audio_duration_seconds * fps rounded)
  scene_tracks:
    type: list
    description: Computed tracks with start_frame, end_frame, and durationInFrames per scene
  transition_windows:
    type: list
    description: Overlap transition frames between adjacent scenes
  is_duration_locked:
    type: bool
    description: True if total_frames strictly equals round(audio_duration_seconds * fps)
---

# Multi-Track Timeline Composition and Frame Alignment

## Purpose
Guarantees mathematical precision for Remotion timeline composition. Assembles individual
scene motion components into a contiguous, multi-track sequence strictly locked to the
spoken narration duration at 30 fps, preventing black frame gaps and desynchronization.

## Core Rules

1. **Audio-Locked Master Duration**:
   - Master timeline duration is mathematically locked to spoken narration audio:
     `total_frames = int(round(audio_duration_seconds * 30.0))`
   - Video duration must never float, stretch, or compress arbitrarily.

2. **Frame-Accurate Scene Alignment**:
   - For any scene `i`:
     - `start_frame[i] = end_frame[i - 1]` (for cuts)
     - `duration_frames[i] = int(round(scene_duration_seconds[i] * 30.0))`
   - Sum of scene durations must reconcile with `total_frames` within ±1 frame rounding tolerance.
   - Any residual rounding frame must be absorbed into the final scene's tail hold.

3. **Transition Overlap Scheduling**:
   - `cut`: 0 overlapping frames (`transition_duration = 0`).
   - `crossfade`: 8 frames (266ms) overlap window.
   - `wipe` / `slide`: 10 frames (333ms) overlap window.
   - When transitions are scheduled, adjacent scenes overlap within `<Sequence>` offsets without shifting global timeline alignment.

4. **Zero Gap & Zero Desync Invariant**:
   - There must be 0 empty or unassigned frames between scene components.
   - Audio track starts at frame 0 and runs unshifted alongside Remotion sequences.
