"""Unit tests for RequirementParser."""
from __future__ import annotations

from SYSTEM.agents.capability_finder.discovery.requirement_parser import RequirementParser


def test_parse_chart_prompt():
    parser = RequirementParser()
    prompt = "Create an animated stacked bar chart for a 9:16 video with Telugu labels, smooth transitions, and deterministic rendering."
    req = parser.parse(prompt)

    assert req.domain == "motion"
    assert req.primary_capability == "data_visualization"
    assert req.constraints.get("aspect_ratio") == "9:16"
    assert req.constraints.get("language") == "telugu"
    assert req.constraints.get("chart_type") == "stacked_bar_chart"
    assert req.constraints.get("smooth_transitions") is True
    assert req.constraints.get("deterministic_rendering") is True
    assert "ffmpeg" in req.runtime_dependencies


def test_parse_audio_transcription_prompt():
    parser = RequirementParser()
    prompt = "Transcribe the Telugu audio lecture with word timestamps using faster-whisper."
    req = parser.parse(prompt)

    assert req.domain == "audio"
    assert req.primary_capability == "speech_to_text"
    assert req.constraints.get("language") == "telugu"
    assert "faster_whisper" in req.runtime_dependencies
    assert "audio_file" in req.required_inputs
    assert "transcript_json" in req.expected_outputs


def test_parse_kinetic_typography_prompt():
    parser = RequirementParser()
    prompt = "Render kinetic typography with spring easing in 16:9 widescreen format."
    req = parser.parse(prompt)

    assert req.domain == "motion"
    assert req.primary_capability == "kinetic_typography"
    assert req.constraints.get("aspect_ratio") == "16:9"
    assert req.constraints.get("motion_curve") == "spring"


def test_parse_ambiguities_flagged():
    parser = RequirementParser()
    prompt = "Generate a chart for data."
    req = parser.parse(prompt)

    assert req.primary_capability == "data_visualization"
    assert len(req.ambiguities) > 0
    assert any("Chart type not specified" in a for a in req.ambiguities)
