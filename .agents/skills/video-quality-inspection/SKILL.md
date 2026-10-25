---
name: video-quality-inspection
description: Inspect rendered video files, extract keyframes, verify visual quality, check Telugu text rendering and clipping, and diagnose frame drops or audio-sync drift in Remotion and FFmpeg exports.
---

# Video Quality Inspection & Multimodal QC

Use this skill when verifying rendered video output, debugging visual artifacts, checking audio-video synchronization, or evaluating final release quality in Stage 11 (Final QC).

## 1. Video Stream & Metadata Verification

Before playing or previewing, verify stream integrity using `ffprobe`:

```bash
ffprobe -v error -show_entries stream=width,height,r_frame_rate,duration,codec_name -of json "path/to/output.mp4"
```

### Critical Checks:
1. **Aspect Ratio & Resolution**:
   - 16:9 Landscape: `1920x1080` (or `1280x720`)
   - 9:16 Portrait / Shorts: `1080x1920` (or `720x1280`)
2. **Frame Rate**: Confirm constant `30/1` (30 fps) or `24/1` (24 fps). Variable frame rates cause audio drift.
3. **Stream Duration Match**:
   - Video stream duration vs Audio stream duration must not differ by more than `0.25s`.
   - If audio is shorter, the video freezes at the end; if audio is longer, audio cuts off abruptly.

---

## 2. Keyframe Extraction for Visual Inspection

Extract representative frames across the video to verify layout, motion graphics, and text rendering:

```bash
# Extract frame at 2 seconds
ffmpeg -ss 00:00:02.000 -i "path/to/output.mp4" -vframes 1 -q:v 2 "scratch/frame_02s.png"

# Extract 1 frame every 5 seconds across the entire video
ffmpeg -i "path/to/output.mp4" -vf "fps=1/5" "scratch/frame_%03d.png"
```

### Visual Inspection Checklist:
- **Telugu Typography**: Verify that Telugu Unicode fonts (`Hind Guntur`) render full conjuncts and vowel signs properly without box characters ("tofu" `□` or broken glyphs).
- **Text Safe Zones**: Ensure titles and subtitles stay at least 5% away from frame edges (critical for 9:16 Shorts where UI overlays cover top and bottom).
- **Visual Asset Contrast**: Ensure text overlays are legible against background media (confirm presence of dark gradient scrims or background boxes).
- **Aspect Ratio Distortion**: Ensure stock images and video assets maintain their native aspect ratio with `object-fit: cover` and are not stretched horizontally or vertically.

---

## 3. Audio & Subtitle Alignment Check

To verify subtitle / text alignment with spoken voice:
1. Extract audio track:
   ```bash
   ffmpeg -i "path/to/output.mp4" -vn -acodec copy "scratch/extracted_audio.aac"
   ```
2. Compare speech timestamps from Stage 01 (`audio_analysis.json`) utterances against the composition JSON (`VIDEO_ENGINE/remotion/public/composition.json`).
3. Confirm that kinetic typography words enter within `±50ms` of spoken syllable onset.
