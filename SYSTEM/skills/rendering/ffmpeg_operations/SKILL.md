---
skill_id: media.ffmpeg_operations
name: FFmpeg Media Probing, Sync Verification, and Stream Operations
domain: rendering
version: 1.0.0
summary: Standardized FFmpeg operations for video/audio stream probing, duration sync verification, freeze-frame detection, and audio muxing.
status: approved
source: local
license: Apache-2.0
license_evidence: Authored internally for Dark World Video Generation Agent.
risk_level: low
capabilities:
  - stream-probing
  - audio-video-sync
  - freeze-frame-detection
  - audio-muxing
  - ffprobe-metadata
tags:
  - ffmpeg
  - media
  - probing
  - qc
  - sync
dependencies: []
compatible_agents:
  - video_rendering
  - final_qc
compatible_project_modes:
  - motion_only
input_contracts:
  media_path:
    type: string
    description: Absolute or project-relative file path to the audio or video container
  operation:
    type: string
    options:
      - probe_streams
      - verify_sync
      - check_freeze_frames
      - mux_audio
    default: probe_streams
  tolerance_seconds:
    type: float
    default: 0.1
output_contracts:
  is_valid:
    type: bool
    description: True if stream parameters and sync tolerances pass verification
  stream_metadata:
    type: dict
    description: Codec, resolution, duration, bitrate, and pixel format metadata
  sync_delta_ms:
    type: float
    description: Discrepancy between video and audio stream duration in milliseconds
  diagnostics:
    type: list
    description: Detailed warnings or failure reasons
---

# FFmpeg Media Probing, Sync Verification, and Stream Operations

## Purpose
Governs media container validation, stream metadata extraction, audio-video synchronization
tolerances, and lossless remuxing for the rendering and final QC pipeline stages.

## Core Rules

1. **Deterministic Stream Probing (`probe_streams`)**:
   - Utilize `ffprobe` in JSON reporting mode (`-v quiet -print_format json -show_format -show_streams`).
   - Extract exact container duration, stream codec (`h264`, `aac`), resolution, pixel format (`yuv420p`), and framerate (`30/1`).

2. **Audio-Video Duration Synchronization (`verify_sync`)**:
   - Spoken audio duration is the absolute ground truth.
   - The rendered video stream duration must not diverge from the audio stream duration by more than `tolerance_seconds` (default 100ms).
   - If `abs(video_duration - audio_duration) > tolerance_seconds`, flag `is_valid = false` and report actionable desync diagnostics.

3. **Defect & Black Frame Detection (`check_freeze_frames`)**:
   - Scan container using `freezedetect` and `blackdetect` filters.
   - Any contiguous black or frozen frames exceeding 15 frames (0.5s at 30 fps) inside active scene boundaries must fail automated QC.

4. **Audio Muxing Pipeline (`mux_audio`)**:
   - When combining Remotion rendered video with master narration:
     `ffmpeg -y -i input_video.mp4 -i master_audio.wav -c:v copy -c:a aac -b:a 192k -shortest output.mp4`
   - Zero video re-encoding allowed (`-c:v copy`) to preserve Remotion render bitstream purity.
