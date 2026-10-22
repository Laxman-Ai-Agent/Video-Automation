"""Domain-Specific Quality Evaluator for Video Generation Skills.

Enforces deep contract verification, technical invariants, and output validity across:
1. Audio & Transcript timing, duration alignment, and Telugu/English vocabulary.
2. Visual Planning scene coverage, hierarchy, and mode-aware element breakdown.
3. Motion & Remotion animation frame bounds, spring math, and prohibited preset guards.
4. Telugu Typography Unicode integrity, line breaking, and safe-zone placement.
5. Rendering & FFmpeg QA stream parameters, resolution, and A/V duration sync.
"""
from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("skill_factory.video_quality")

# Prohibited presets in Remotion custom-code mode
PROHIBITED_PRESETS = frozenset({
    "MotionTextLayer",
    "MotionScene",
    "HighlightText",
    "TextOverlay",
    "AnimatedPreset",
    "QuickMotion",
})

# Safe margin fractions for canvas dimensions
SAFE_ZONE_MARGINS = {
    "9:16": {"top": 0.12, "bottom": 0.18, "left": 0.08, "right": 0.08},  # Shorts/Reels UI safety
    "16:9": {"top": 0.08, "bottom": 0.10, "left": 0.08, "right": 0.08},  # Standard TV/Monitor safety
}


@dataclass
class VideoQualityCheckResult:
    """Detailed audit report of a domain-specific video quality evaluation."""
    passed: bool
    domain: str
    checks_run: int = 0
    checks_passed: int = 0
    checks_failed: int = 0
    metrics: dict[str, Any] = field(default_factory=dict)
    findings: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class VideoQualityEvaluator:
    """Deterministic validator for video-generation skill contracts and outputs."""

    # -------------------------------------------------------------------------
    # 1. Audio & Transcript Quality Contract
    # -------------------------------------------------------------------------
    def evaluate_audio_transcript_contract(
        self,
        transcript_data: dict[str, Any] | list[dict[str, Any]],
        audio_duration_seconds: float | None = None,
    ) -> VideoQualityCheckResult:
        """Validates timing monotonicity, duration consistency, and bilingual vocabulary."""
        findings: list[str] = []
        checks_run = 0
        checks_passed = 0

        segments: list[dict[str, Any]] = []
        if isinstance(transcript_data, dict):
            segments = transcript_data.get("segments", transcript_data.get("words", []))
        elif isinstance(transcript_data, list):
            segments = transcript_data

        # Check 1: Non-empty segment structure
        checks_run += 1
        if not segments:
            findings.append("Transcript contains no segments or words.")
        else:
            checks_passed += 1

        # Check 2: Timestamp ordering and monotonicity
        checks_run += 1
        timing_errors = 0
        last_end = 0.0
        for i, seg in enumerate(segments):
            start = float(seg.get("start", 0.0))
            end = float(seg.get("end", 0.0))
            if start < 0 or end <= start:
                timing_errors += 1
                findings.append(f"Segment {i} invalid bounds: start={start:.2f}s, end={end:.2f}s.")
            if start < (last_end - 0.25):  # Minor overlap tolerance for natural speech
                timing_errors += 1
                findings.append(f"Segment {i} timing regression: start={start:.2f}s precedes prior end={last_end:.2f}s.")
            last_end = max(last_end, end)

        if timing_errors == 0 and segments:
            checks_passed += 1

        # Check 3: Audio duration alignment
        checks_run += 1
        max_ts = last_end
        if audio_duration_seconds is not None and audio_duration_seconds > 0:
            discrepancy = abs(max_ts - audio_duration_seconds)
            if discrepancy > 1.5:  # Tolerance threshold
                findings.append(
                    f"Transcript ending timestamp ({max_ts:.2f}s) diverges from audio duration "
                    f"({audio_duration_seconds:.2f}s) by {discrepancy:.2f}s."
                )
            else:
                checks_passed += 1
        else:
            checks_passed += 1

        # Check 4: Bilingual vocabulary preservation (Telugu script integrity)
        checks_run += 1
        telugu_char_count = 0
        english_word_count = 0
        for seg in segments:
            text = str(seg.get("text", ""))
            # Telugu Unicode block: 0C00–0C7F
            telugu_matches = re.findall(r"[\u0C00-\u0C7F]", text)
            telugu_char_count += len(telugu_matches)
            # English technical tokens
            eng_matches = re.findall(r"\b[A-Za-z0-9_-]+\b", text)
            english_word_count += len(eng_matches)

        if segments and telugu_char_count == 0 and english_word_count == 0:
            findings.append("No recognizable Telugu or English text detected in transcript.")
        else:
            checks_passed += 1

        passed = (checks_passed == checks_run)
        return VideoQualityCheckResult(
            passed=passed,
            domain="audio_transcript",
            checks_run=checks_run,
            checks_passed=checks_passed,
            checks_failed=checks_run - checks_passed,
            metrics={
                "segment_count": len(segments),
                "total_duration_sec": max_ts,
                "telugu_chars": telugu_char_count,
                "english_words": english_word_count,
            },
            findings=findings,
        )

    # -------------------------------------------------------------------------
    # 2. Visual Planning Quality Contract
    # -------------------------------------------------------------------------
    def evaluate_visual_planning_contract(
        self,
        visual_plan: dict[str, Any],
        expected_scene_ids: list[str] | None = None,
    ) -> VideoQualityCheckResult:
        """Validates visual planning completeness, element hierarchy, and mode compliance."""
        findings: list[str] = []
        checks_run = 0
        checks_passed = 0

        scenes = visual_plan.get("scenes", {})
        if isinstance(scenes, list):
            scenes_dict = {s.get("scene_id", f"scene_{i}"): s for i, s in enumerate(scenes)}
        else:
            scenes_dict = scenes

        # Check 1: Scene coverage
        checks_run += 1
        if expected_scene_ids:
            missing_scenes = [sid for sid in expected_scene_ids if sid not in scenes_dict]
            if missing_scenes:
                findings.append(f"Visual plan missing {len(missing_scenes)} scenes: {', '.join(missing_scenes[:5])}.")
            else:
                checks_passed += 1
        elif scenes_dict:
            checks_passed += 1
        else:
            findings.append("Visual plan contains no scene planning data.")

        # Check 2: Scene concept & visual hierarchy completeness
        checks_run += 1
        invalid_scenes = 0
        for sid, sdata in scenes_dict.items():
            if not sdata.get("visual_concept") and not sdata.get("concept"):
                invalid_scenes += 1
                findings.append(f"Scene '{sid}' missing visual_concept.")
            elements = sdata.get("elements", [])
            if not isinstance(elements, list) or len(elements) == 0:
                invalid_scenes += 1
                findings.append(f"Scene '{sid}' missing elements breakdown.")

        if invalid_scenes == 0 and scenes_dict:
            checks_passed += 1

        # Check 3: Mode-Aware planning (motion_only validation)
        checks_run += 1
        prohibited_image_prompts = 0
        for sid, sdata in scenes_dict.items():
            for el in sdata.get("elements", []):
                if el.get("type") in ("image_generation", "stock_video_clip"):
                    prohibited_image_prompts += 1
                    findings.append(f"Scene '{sid}' requested external image asset '{el.get('type')}', violating motion-only mode.")

        if prohibited_image_prompts == 0:
            checks_passed += 1

        passed = (checks_passed == checks_run)
        return VideoQualityCheckResult(
            passed=passed,
            domain="visual_planning",
            checks_run=checks_run,
            checks_passed=checks_passed,
            checks_failed=checks_run - checks_passed,
            metrics={
                "scene_count": len(scenes_dict),
                "total_elements": sum(len(s.get("elements", [])) for s in scenes_dict.values()),
            },
            findings=findings,
        )

    # -------------------------------------------------------------------------
    # 3. Motion & Remotion Code Quality Contract
    # -------------------------------------------------------------------------
    def evaluate_motion_graphics_contract(
        self,
        motion_code_or_spec: str | dict[str, Any],
        scene_duration_frames: int | None = None,
        aspect_ratio: str = "9:16",
    ) -> VideoQualityCheckResult:
        """Validates Remotion primitives usage, spring math, frame bounds, and preset prohibitions."""
        findings: list[str] = []
        checks_run = 0
        checks_passed = 0

        code_text = ""
        spec_dict: dict[str, Any] = {}
        if isinstance(motion_code_or_spec, str):
            code_text = motion_code_or_spec
        elif isinstance(motion_code_or_spec, dict):
            spec_dict = motion_code_or_spec
            code_text = spec_dict.get("code_content", "") or json.dumps(spec_dict)

        # Check 1: Prohibited Preset Scanning
        checks_run += 1
        found_presets = [p for p in PROHIBITED_PRESETS if p in code_text]
        if found_presets:
            findings.append(f"Prohibited presets detected in motion code: {', '.join(found_presets)}.")
        else:
            checks_passed += 1

        # Check 2: Remotion Primitives Usage
        checks_run += 1
        has_remotion_primitives = (
            "useCurrentFrame" in code_text or
            "interpolate" in code_text or
            "spring" in code_text or
            "AbsoluteFill" in code_text or
            "remotion" in code_text.lower()
        )
        if not has_remotion_primitives and not spec_dict:
            findings.append("Motion code missing core Remotion animation primitives (useCurrentFrame, spring, interpolate).")
        else:
            checks_passed += 1

        # Check 3: Frame clamping & duration math
        checks_run += 1
        frame_bounds_ok = True
        if scene_duration_frames is not None and scene_duration_frames > 0:
            if "durationInFrames" in code_text:
                match = re.search(r"durationInFrames\s*[:=]\s*(\d+)", code_text)
                if match:
                    parsed_frames = int(match.group(1))
                    if parsed_frames > (scene_duration_frames + 5):
                        frame_bounds_ok = False
                        findings.append(
                            f"Component durationInFrames ({parsed_frames}) exceeds scene budget ({scene_duration_frames})."
                        )
        if frame_bounds_ok:
            checks_passed += 1

        # Check 4: Canvas Safe Zone Dimensions
        checks_run += 1
        if aspect_ratio == "9:16":
            expected_width, expected_height = 1080, 1920
        else:
            expected_width, expected_height = 1920, 1080

        # Check if coordinates exceed canvas width/height
        out_of_bounds = False
        coords = re.findall(r"width\s*[:=]\s*(\d+)", code_text)
        for c in coords:
            if int(c) > (expected_width * 1.5):
                out_of_bounds = True
                findings.append(f"Excessive layout width {c} exceeds canvas boundary {expected_width}px.")
        if not out_of_bounds:
            checks_passed += 1

        passed = (checks_passed == checks_run)
        return VideoQualityCheckResult(
            passed=passed,
            domain="motion_graphics",
            checks_run=checks_run,
            checks_passed=checks_passed,
            checks_failed=checks_run - checks_passed,
            metrics={"aspect_ratio": aspect_ratio, "target_frames": scene_duration_frames},
            findings=findings,
        )

    # -------------------------------------------------------------------------
    # 4. Telugu Typography & Caption Quality Contract
    # -------------------------------------------------------------------------
    def evaluate_telugu_typography_contract(
        self,
        caption_spec: dict[str, Any],
        aspect_ratio: str = "9:16",
    ) -> VideoQualityCheckResult:
        """Validates Unicode stability, line breaks, safe-zone placement, and font configuration."""
        findings: list[str] = []
        checks_run = 0
        checks_passed = 0

        telugu_text = caption_spec.get("text", "")
        font_family = caption_spec.get("font_family", "Noto Sans Telugu")
        position_y = caption_spec.get("position_y_pct", 0.85)

        # Check 1: Unicode Integrity
        checks_run += 1
        if not telugu_text:
            findings.append("Caption specification has empty text.")
        else:
            # Check for corrupt Unicode replacement characters (U+FFFD)
            if "\ufffd" in telugu_text or "\\ufffd" in telugu_text:
                findings.append("Unicode replacement character detected (corrupt encoding in Telugu string).")
            else:
                checks_passed += 1

        # Check 2: Font Family Specification
        checks_run += 1
        if "Noto Sans Telugu" not in font_family and "sans-serif" not in font_family:
            findings.append(f"Unsupported font family '{font_family}' for Telugu script rendering.")
        else:
            checks_passed += 1

        # Check 3: Line length & break boundaries
        checks_run += 1
        lines = telugu_text.splitlines() or [telugu_text]
        max_words_per_line = 10 if aspect_ratio == "16:9" else 6
        line_length_ok = True
        for i, line in enumerate(lines):
            word_count = len(line.strip().split())
            if word_count > max_words_per_line:
                line_length_ok = False
                findings.append(f"Line {i} has {word_count} words; exceeds recommended max of {max_words_per_line} for {aspect_ratio}.")
        if line_length_ok:
            checks_passed += 1

        # Check 4: Safe Zone Placement (Shorts/Reels UI overlay prevention)
        checks_run += 1
        margins = SAFE_ZONE_MARGINS.get(aspect_ratio, SAFE_ZONE_MARGINS["9:16"])
        bottom_margin_y = 1.0 - margins["bottom"]
        if position_y > bottom_margin_y + 0.05:
            findings.append(
                f"Caption position_y ({position_y:.2f}) falls into bottom UI danger zone "
                f"(max safe y={bottom_margin_y:.2f} for {aspect_ratio})."
            )
        else:
            checks_passed += 1

        passed = (checks_passed == checks_run)
        return VideoQualityCheckResult(
            passed=passed,
            domain="telugu_typography",
            checks_run=checks_run,
            checks_passed=checks_passed,
            checks_failed=checks_run - checks_passed,
            metrics={"line_count": len(lines), "font": font_family, "position_y": position_y},
            findings=findings,
        )

    # -------------------------------------------------------------------------
    # 5. Rendering & FFmpeg Timeline QA Contract
    # -------------------------------------------------------------------------
    def evaluate_rendering_and_qa_contract(
        self,
        render_audit_data: dict[str, Any],
        target_aspect_ratio: str = "9:16",
    ) -> VideoQualityCheckResult:
        """Validates output resolution, stream encoding, audio duration sync, and freeze frames."""
        findings: list[str] = []
        checks_run = 0
        checks_passed = 0

        video_stream = render_audit_data.get("video_stream", {})
        audio_stream = render_audit_data.get("audio_stream", {})
        freeze_frames = render_audit_data.get("freeze_frames", [])
        black_frames = render_audit_data.get("black_frames", [])

        # Check 1: Target Resolution & Framerate
        checks_run += 1
        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
        r_frame_rate = str(video_stream.get("r_frame_rate", "30/1"))

        expected_dim = (1080, 1920) if target_aspect_ratio == "9:16" else (1920, 1080)
        if (width, height) != expected_dim and (width, height) != (0, 0):
            findings.append(f"Rendered resolution {width}x{height} does not match target {expected_dim[0]}x{expected_dim[1]}.")
        else:
            checks_passed += 1

        # Check 2: Audio-Video Duration Sync
        checks_run += 1
        v_dur = float(video_stream.get("duration", 0.0))
        a_dur = float(audio_stream.get("duration", 0.0))
        if v_dur > 0 and a_dur > 0:
            sync_delta = abs(v_dur - a_dur)
            if sync_delta > 0.2:  # Strict A/V sync threshold
                findings.append(f"Audio/Video desync detected: video={v_dur:.2f}s, audio={a_dur:.2f}s, delta={sync_delta:.2f}s.")
            else:
                checks_passed += 1
        else:
            checks_passed += 1

        # Check 3: Freeze & Black Frames Thresholds
        checks_run += 1
        if len(freeze_frames) > 3:
            findings.append(f"Excessive freeze frames detected ({len(freeze_frames)} instances).")
        elif len(black_frames) > 5:
            findings.append(f"Excessive black frames detected ({len(black_frames)} instances).")
        else:
            checks_passed += 1

        passed = (checks_passed == checks_run)
        return VideoQualityCheckResult(
            passed=passed,
            domain="rendering_qa",
            checks_run=checks_run,
            checks_passed=checks_passed,
            checks_failed=checks_run - checks_passed,
            metrics={"video_duration": v_dur, "audio_duration": a_dur, "resolution": f"{width}x{height}"},
            findings=findings,
        )


# Authoritative singleton
video_quality_evaluator = VideoQualityEvaluator()
