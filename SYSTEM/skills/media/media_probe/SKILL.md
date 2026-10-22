---
skill_id: media_probe
name: Media Probe & Quality Verification
domain: qc
version: 1.0.0
summary: Performs deterministic video probing, codec verification, audio track analysis, and frame integrity checks using ffprobe.
status: approved
source: local
license: Apache-2.0
license_evidence: Authored internally for Dark World Video Generation Agent.
risk_level: low
capabilities:
  - media-probing
  - stream-probing
  - audio-stream-verification
  - resolution-audit
  - freeze-frame-detection
dependencies:
  - ffmpeg
  - ffprobe
compatible_agents:
  - final_qc
  - render_video
  - video_rendering
  - video_generator
  - architecture_validator
compatible_project_modes:
  - motion_only
---

# Media Probe & Quality Verification Skill

## Purpose
Performs deterministic inspection, container validation, video/audio stream probing, and freeze-frame defect detection on rendered video outputs using ffprobe.

## Core Rules
1. **Container & Stream Validation**:
   - Inspect video format, duration, container validity, bit rate, and profile.
   - Verify presence and parameters of primary audio and video streams (AAC / H.264).
2. **Resolution & Aspect Ratio Audit**:
   - Confirm target dimensions (1080x1920 for 9:16 vertical, 1920x1080 for 16:9 landscape).
   - Reject frame dimensions deviating from expected aspect ratio standard.
3. **Freeze Frame & Audio Sync Inspection**:
   - Detect repeated identical frames exceeding acceptable thresholds (freeze detection).
   - Ensure audio stream duration matches or safely wraps video duration within 250ms tolerance.
4. **Deterministic Exit**:
   - Return structured validation report with exact metric properties and pass/fail verdict.
