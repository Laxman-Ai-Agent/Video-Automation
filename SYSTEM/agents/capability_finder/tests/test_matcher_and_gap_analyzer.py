"""Unit tests for CapabilityMatcher and GapAnalyzer."""
from __future__ import annotations

from SYSTEM.agents.capability_finder.discovery.gap_analyzer import GapAnalyzer
from SYSTEM.agents.capability_finder.discovery.matcher import CapabilityMatcher
from SYSTEM.agents.capability_finder.discovery.requirement_parser import ParsedRequirement
from SYSTEM.registries.capability_registry import CapabilityRecord


def test_matcher_exact_match():
    matcher = CapabilityMatcher()
    req = ParsedRequirement(
        raw_query="Render kinetic typography with spring easing in 16:9",
        primary_capability="kinetic_typography",
        domain="motion",
        tags=["motion", "typography", "16:9"],
        keywords=["typography", "kinetic", "spring"],
        constraints={"aspect_ratio": "16:9", "motion_curve": "spring"},
    )
    candidate = CapabilityRecord(
        capability_id="skill.motion.kinetic_typography",
        name="Kinetic Typography",
        description="Renders kinetic typography with spring easing curves in 16:9 and 9:16.",
        source_type="skill",
        source_id="motion.kinetic_typography",
        domain="motion",
        tags=["motion", "typography", "spring", "16:9"],
        keywords=["typography", "kinetic", "spring"],
    )

    matches = matcher.match(req, [candidate])
    assert len(matches) == 1
    assert matches[0].score >= 0.80
    assert matches[0].match_type == "exact"
    assert "aspect_ratio=16:9" in matches[0].constraints_satisfied


def test_gap_analysis_reuse_recommendation():
    analyzer = GapAnalyzer()
    req = ParsedRequirement(
        raw_query="Transcribe audio",
        primary_capability="speech_to_text",
        domain="audio",
        runtime_dependencies=[],
    )
    candidate = CapabilityRecord(
        capability_id="agent.audio_input.speech_to_text",
        name="Audio Input Speech To Text",
        description="Transcribes audio speech to text.",
        source_type="agent",
        source_id="audio_input",
        domain="audio",
        tags=["audio", "speech_to_text"],
    )

    matches = CapabilityMatcher().match(req, [candidate])
    report = analyzer.analyze(req, matches)

    assert report.overall_status == "satisfied"
    assert report.recommended_action == "REUSE"
    assert report.suggested_delegate_id == "audio_input"


def test_gap_analysis_create_skill_recommendation():
    analyzer = GapAnalyzer()
    req = ParsedRequirement(
        raw_query="Generate a customized 3D neon bar chart with particle glow",
        primary_capability="particle_glow_chart",
        domain="motion",
        tags=["motion", "particle_glow_chart", "chart"],
        keywords=["neon", "glow", "particle"],
        constraints={"style": "neon_glow"},
    )

    # Empty candidate list simulates missing capability
    matches = CapabilityMatcher().match(req, [])
    report = analyzer.analyze(req, matches)

    assert report.overall_status == "missing"
    assert report.recommended_action == "CREATE_SKILL"
    assert report.suggested_delegate_id == "skill_factory"
    assert "SkillFactoryAgent" in report.action_rationale
