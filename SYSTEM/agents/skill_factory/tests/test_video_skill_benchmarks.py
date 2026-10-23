"""Evidence-Based Benchmark Suite for Video-Generation Specialized Skill Factory.

Validates:
1. Audio & transcript contract quality (timestamps, monotonicity, Telugu/English bilingual vocabulary).
2. Audio & transcript failure detection (timing regressions, inverted bounds).
3. Visual planning contract quality (scene objectives, element hierarchy, motion-only mode).
4. Visual planning violation detection (rejection of prohibited image/stock prompts).
5. Motion graphics contract quality (Remotion primitives, spring curves, 30 fps math).
6. Motion graphics prohibited preset detection (rejection of legacy presets).
7. Telugu typography contract quality (Unicode preservation, Noto Sans Telugu font cascade).
8. Telugu caption safe-zone enforcement (9:16 vertical exclusion zones).
9. Rendering & FFmpeg QA contract quality (resolution, framerate, zero freeze frames).
10. Rendering & FFmpeg A/V desynchronization detection.
11. Content-hash evaluation caching (instant cache hit, content-tamper invalidation).
12. Parameterized multi-variant reuse decisions (bar/donut charts, timeline transitions).
13. Discoverability of all 5 foundational video skills in SkillRegistry & CapabilityRegistry.
14. End-to-end SkillFactoryAgent 'evaluate_quality' action integration.
"""
from __future__ import annotations

from pathlib import Path
import copy

import pytest

from SYSTEM.agents.capability_finder.learning.authorization import AuthenticatedOperator
from SYSTEM.agents.shared.contracts import AgentRequest
from SYSTEM.agents.skill_factory.agent import SkillFactoryAgent
from SYSTEM.agents.skill_factory.decision_engine import decision_engine
from SYSTEM.agents.skill_factory.evaluation_cache import evaluation_cache
from SYSTEM.agents.skill_factory.fixtures.sample_video_fixtures import (
    SAMPLE_BILINGUAL_TRANSCRIPT,
    SAMPLE_FFMPEG_AUDIT_DATA,
    SAMPLE_REMOTION_MOTION_CODE,
    SAMPLE_TELUGU_CAPTION_SPEC,
    SAMPLE_VISUAL_PLAN,
)
from SYSTEM.agents.skill_factory.specification import SkillSpecification
from SYSTEM.agents.skill_factory.test_runner import skill_test_runner
from SYSTEM.agents.skill_factory.video_quality_evaluator import video_quality_evaluator
from SYSTEM.registries.capability_registry import get_capability_registry
from SYSTEM.registries.skill_registry import get_skill_registry



@pytest.fixture
def mock_operator() -> AuthenticatedOperator:
    return AuthenticatedOperator(
        operator_id="benchmark_lead",
        role="operator",
        auth_method="trusted_context",
        verified_at="2026-10-17T00:00:00Z",
    )


# 1. Audio & Transcript Contract Success
def test_audio_transcript_contract_success():
    res = video_quality_evaluator.evaluate_audio_transcript_contract(
        transcript_data=SAMPLE_BILINGUAL_TRANSCRIPT,
        audio_duration_seconds=5.12,
    )
    assert res.passed is True
    assert res.domain == "audio_transcript"
    assert res.checks_passed == res.checks_run
    assert res.metrics["telugu_chars"] > 10
    assert res.metrics["english_words"] >= 3
    assert len(res.findings) == 0


# 2. Audio & Transcript Contract Catches Timing Regressions
def test_audio_transcript_contract_catches_timing_regression():
    bad_transcript = {
        "segments": [
            {"id": 0, "start": 3.0, "end": 2.0, "text": "Inverted start end."},
            {"id": 1, "start": 1.0, "end": 4.0, "text": "Regressed timing."},
        ]
    }
    res = video_quality_evaluator.evaluate_audio_transcript_contract(bad_transcript)
    assert res.passed is False
    assert any("invalid bounds" in f.lower() for f in res.findings)
    assert any("timing regression" in f.lower() for f in res.findings)


# 3. Visual Planning Contract Success
def test_visual_planning_contract_success():
    res = video_quality_evaluator.evaluate_visual_planning_contract(
        visual_plan=SAMPLE_VISUAL_PLAN,
        expected_scene_ids=["scene_01", "scene_02"],
    )
    assert res.passed is True
    assert res.domain == "visual_planning"
    assert res.metrics["scene_count"] == 2
    assert res.metrics["total_elements"] == 6
    assert len(res.findings) == 0


# 4. Visual Planning Contract Rejects External Image Mode
def test_visual_planning_contract_rejects_external_image_mode():
    plan_with_images = copy.deepcopy(SAMPLE_VISUAL_PLAN)
    plan_with_images["scenes"]["scene_01"]["elements"].append(
        {"name": "photo_bg", "type": "image_generation", "z_index": 0}
    )
    res = video_quality_evaluator.evaluate_visual_planning_contract(plan_with_images)
    assert res.passed is False
    assert any("violating motion-only mode" in f.lower() for f in res.findings)


# 5. Motion Graphics Contract Success
def test_motion_graphics_contract_success():
    res = video_quality_evaluator.evaluate_motion_graphics_contract(
        motion_code_or_spec=SAMPLE_REMOTION_MOTION_CODE,
        scene_duration_frames=150,
        aspect_ratio="9:16",
    )
    assert res.passed is True
    assert res.domain == "motion_graphics"
    assert len(res.findings) == 0


# 6. Motion Graphics Contract Detects Prohibited Presets
def test_motion_graphics_contract_detects_prohibited_presets():
    bad_code = SAMPLE_REMOTION_MOTION_CODE + "\n<MotionTextLayer text='Hello' />\n"
    res = video_quality_evaluator.evaluate_motion_graphics_contract(bad_code)
    assert res.passed is False
    assert any("prohibited presets" in f.lower() for f in res.findings)
    assert any("MotionTextLayer" in f for f in res.findings)


# 7. Telugu Typography Contract Success
def test_telugu_typography_contract_success():
    res = video_quality_evaluator.evaluate_telugu_typography_contract(
        caption_spec=SAMPLE_TELUGU_CAPTION_SPEC,
        aspect_ratio="9:16",
    )
    assert res.passed is True
    assert res.domain == "telugu_typography"
    assert res.metrics["font"] == "Noto Sans Telugu, sans-serif"
    assert len(res.findings) == 0


# 8. Telugu Typography Contract Enforces Safe Zone Placement
def test_telugu_typography_contract_enforces_safe_zone():
    bad_spec = copy.deepcopy(SAMPLE_TELUGU_CAPTION_SPEC)
    bad_spec["position_y_pct"] = 0.92  # Dangerous bottom overlay zone
    res = video_quality_evaluator.evaluate_telugu_typography_contract(bad_spec, aspect_ratio="9:16")
    assert res.passed is False
    assert any("bottom ui danger zone" in f.lower() for f in res.findings)


# 9. Rendering & FFmpeg QA Contract Success
def test_rendering_and_qa_contract_success():
    res = video_quality_evaluator.evaluate_rendering_and_qa_contract(
        render_audit_data=SAMPLE_FFMPEG_AUDIT_DATA,
        target_aspect_ratio="9:16",
    )
    assert res.passed is True
    assert res.domain == "rendering_qa"
    assert res.metrics["resolution"] == "1080x1920"
    assert len(res.findings) == 0


# 10. Rendering & FFmpeg QA Detects Audio-Video Desync
def test_rendering_and_qa_detects_av_desync():
    desynced_data = copy.deepcopy(SAMPLE_FFMPEG_AUDIT_DATA)
    desynced_data["video_stream"]["duration"] = 5.80  # 700ms delta from 5.10s audio
    res = video_quality_evaluator.evaluate_rendering_and_qa_contract(desynced_data)
    assert res.passed is False
    assert any("desync detected" in f.lower() for f in res.findings)


# 11. Content-Hash Evaluation Caching
def test_evaluation_caching_hit_and_tamper_invalidation():
    spec = SkillSpecification(
        skill_id="test.cache_verification",
        name="Cache Verification Skill",
        purpose="Testing evaluation cache hits and tamper invalidation.",
        domain="testing",
        capabilities=["cache-test"],
        inputs={"data": "string"},
        outputs={"res": "string"},
    )
    content_v1 = spec.to_yaml_manifest()

    # Clear cache entry to start fresh
    evaluation_cache.invalidate_skill(spec.skill_id)

    # First execution: Cache miss, executed and stored
    res1 = skill_test_runner.run_tests(spec, content=content_v1, use_cache=True)
    assert res1.passed is True
    assert not any("cryptographic evaluation cache" in d.lower() for d in res1.diagnostics)

    # Second execution with exact same content: Cache hit
    res2 = skill_test_runner.run_tests(spec, content=content_v1, use_cache=True)
    assert res2.passed is True
    assert any("cryptographic evaluation cache" in d.lower() for d in res2.diagnostics)

    # Third execution with altered content: Cache miss
    content_v2 = content_v1 + "\n\n## Altered Addendum\nModified content."
    res3 = skill_test_runner.run_tests(spec, content=content_v2, use_cache=True)
    assert res3.passed is True
    assert not any("cryptographic evaluation cache" in d.lower() for d in res3.diagnostics)


# 12. Parameterized Multi-Variant Reuse Decision
def test_parameterized_multi_variant_reuse_decision():
    # 1. Bar Chart variant reuse
    bar_spec = SkillSpecification(
        skill_id="custom.bar_chart",
        name="Custom Bar Chart Requirement",
        purpose="Render animated bar charts for documentary stats.",
        domain="graphics",
        capabilities=["bar_chart"],
        inputs={"chart_type": "bar_chart"},
    )
    bar_dec = decision_engine.evaluate(bar_spec)
    assert bar_dec.action == "REUSE"
    assert bar_dec.skill_id == "graphics.data_visualization"
    assert "natively supports requested variant(s)" in bar_dec.reason

    # 2. Donut Chart variant reuse
    donut_spec = SkillSpecification(
        skill_id="custom.donut_chart",
        name="Custom Donut Chart Requirement",
        purpose="Render percentage breakdown donut chart.",
        domain="graphics",
        capabilities=["donut_chart"],
        inputs={"chart_type": "donut_chart"},
    )
    donut_dec = decision_engine.evaluate(donut_spec)
    assert donut_dec.action == "REUSE"
    assert donut_dec.skill_id == "graphics.data_visualization"


# 13. Discoverability of All 5 Foundational Video Skills
def test_foundational_skills_discoverable():
    skill_reg = get_skill_registry()
    cap_reg = get_capability_registry()
    skill_reg.initialize()
    cap_reg.sync_with_registries()

    foundational_ids = [
        "visual.scene_planning",
        "graphics.data_visualization",
        "media.ffmpeg_operations",
        "typography.telugu_rendering",
        "timeline.composition_assembly",
    ]

    for sid in foundational_ids:
        rec, content = skill_reg.get_skill(sid, load_content=True)
        assert rec is not None, f"Skill '{sid}' missing from SkillRegistry!"
        assert rec.status == "approved"
        assert len(content) > 100

        # Check in CapabilityRegistry
        matching = cap_reg.search_capabilities(domain=rec.domain)
        assert any(c.source_id == sid for c in matching), f"Skill '{sid}' missing from CapabilityRegistry!"


# 14. SkillFactoryAgent 'evaluate_quality' Action Integration
def test_agent_evaluate_quality_action(tmp_path: Path):
    agent = SkillFactoryAgent()
    spec = SkillSpecification(
        skill_id="visual.scene_planning",
        name="Visual Scene Planning",
        purpose="Visual concept breakdown.",
        domain="visual_planning",
        capabilities=["scene-concept-generation"],
    )

    req = AgentRequest(
        agent_id="skill_factory",
        parameters={
            "action": "evaluate_quality",
            "specification": spec.to_dict(),
            "output_data": SAMPLE_VISUAL_PLAN,
        },
    )
    res = agent.execute(tmp_path, req)
    assert res.status == "succeeded"
    report = res.metadata.get("quality_report", {})
    assert report.get("passed") is True
    assert report.get("domain") == "visual_planning"
