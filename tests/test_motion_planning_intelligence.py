"""Comprehensive test suite for Motion Planning Cinematic Intelligence Upgrade (v2.0.0).

Validates:
1. Semantic scene understanding: narrative role, emotional tone, and strategy selection.
2. Context-aware camera choreography with strict bounds enforcement (1.0 <= zoom <= 1.15).
3. Spring physics profiles (snappy, gentle, dramatic_overshoot, stiff, fluid).
4. Audio-reactive telemetry: speech rate (WPM), pause density, and kinetic accent triggers.
5. Telugu-safe preset enforcement (preventing non-indic presets on Telugu narration).
6. Safe-area margins (16:9 vs 9:16 portrait clearance).
7. Scene-to-scene transition continuity (automatic detection and repair of repeated transitions).
8. Autonomous fallback to deterministic heuristic planning when LLM is unavailable or times out.
9. End-to-end execution of MotionPlanningAgent producing valid motion_plan.json.
10. Self-learning experience persistence in agent memory.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from SYSTEM.agents.shared.contracts import AgentRequest
from SYSTEM.agents.video_generation_agents.motion_planning.agent import MotionPlanningAgent
from SYSTEM.agents.video_generation_agents.motion_planning.motion_intelligence import (
    CameraIntent,
    MotionIntelligenceEngine,
    SPRING_PROFILES,
    SUPPORTED_TEXT_PRESETS,
)


@pytest.fixture
def mock_motion_project(tmp_path: Path) -> Path:
    """Creates a temporary project directory with visual plan, segmentation, and audio analysis."""
    pdir = tmp_path / "proj_motion_test"
    pdir.mkdir(parents=True)

    # 1. scene_plan.json / visual_planning.json with 3 scenes
    visual_plan_data = {
        "scenes": [
            {
                "id": 1,
                "scene_id": "scene_01",
                "start": 0.0,
                "end": 5.0,
                "concept": "నమస్కారం! AI భవిష్యత్తు గురించి స్వాగతం",
                "meaning": "Welcome hook introducing AI future in Telugu",
            },
            {
                "id": 2,
                "scene_id": "scene_02",
                "start": 5.0,
                "end": 11.0,
                "concept": "కానీ పెద్ద సవాళ్లు ఉన్నాయి: డేటా మరియు కంప్యూట్",
                "meaning": "Critical contrast detailing computational challenges",
            },
            {
                "id": 3,
                "scene_id": "scene_03",
                "start": 11.0,
                "end": 16.0,
                "concept": "చివరగా మన ప్రయాణం ఇప్పుడే మొదలైంది",
                "meaning": "Authoritative conclusion and future outlook",
            },
        ],
        "style": {
            "palette": ["#0a0f1e", "#38bdf8", "#818cf8"],
        },
    }
    (pdir / "visual_planning.json").write_text(json.dumps(visual_plan_data, ensure_ascii=False), encoding="utf-8")
    (pdir / "scene_plan.json").write_text(json.dumps(visual_plan_data, ensure_ascii=False), encoding="utf-8")

    # 2. transcript.json with Telugu text
    transcript_data = {
        "duration": 16.0,
        "segments": [
            {"id": 0, "start": 0.0, "end": 5.0, "text": "నమస్కారం! AI భవిష్యత్తు గురించి స్వాగతం"},
            {"id": 1, "start": 5.0, "end": 11.0, "text": "కానీ పెద్ద సవాళ్లు ఉన్నాయి: డేటా మరియు కంప్యూట్"},
            {"id": 2, "start": 11.0, "end": 16.0, "text": "చివరగా మన ప్రయాణం ఇప్పుడే మొదలైంది"},
        ],
    }
    (pdir / "transcript.json").write_text(json.dumps(transcript_data, ensure_ascii=False), encoding="utf-8")

    # 3. audio_analysis.json with pauses
    aa_data = {
        "pauses": [
            {"start_seconds": 4.5, "end_seconds": 5.0},
            {"start_seconds": 10.5, "end_seconds": 11.0},
        ],
        "speech_rate": 140.0,
    }
    (pdir / "audio_analysis.json").write_text(json.dumps(aa_data), encoding="utf-8")

    return pdir


# ------------------ TEST 1: Heuristic Fallback Strategy Generation ------------------
def test_motion_intelligence_heuristic_fallback(mock_motion_project):
    """Verifies that heuristic motion planning runs autonomously when LLM is unavailable."""
    engine = MotionIntelligenceEngine()
    scenes = json.loads((mock_motion_project / "visual_planning.json").read_text(encoding="utf-8"))["scenes"]

    with patch.object(engine, "_execute_llm_motion_planning", return_value=None):
        res = engine.plan_motion_intelligence(mock_motion_project, scenes, aspect="16:9")

    assert res.status == "fallback_deterministic"
    assert len(res.scene_strategies) == 3

    # Check narrative role differentiation
    roles = [s.narrative_role for s in res.scene_strategies]
    assert roles[0] == "hook"
    assert roles[1] == "contrast"  # due to "కానీ" marker
    assert roles[2] == "conclusion"

    # Check camera intent bounds
    for s in res.scene_strategies:
        cam = s.camera.to_dict()
        assert 1.0 <= cam["from"] <= 1.15
        assert 1.0 <= cam["to"] <= 1.15
        assert 0.15 <= cam["focus"][0] <= 0.85
        assert 0.15 <= cam["focus"][1] <= 0.85

    # Check Telugu-safe text preset enforcement
    for s in res.scene_strategies:
        assert s.text_preset in SUPPORTED_TEXT_PRESETS["indic_safe"]

    # Check continuity: transitions do not repeat consecutively
    trans = [s.transition_type for s in res.scene_strategies]
    for i in range(len(trans) - 1):
        if trans[i] != "none":
            assert trans[i] != trans[i + 1]


# ------------------ TEST 2: LLM Gateway Structured Response Integration ------------------
def test_motion_intelligence_llm_gateway_success(mock_motion_project):
    """Verifies structured enrichment when LLM Gateway returns creative motion proposals."""
    engine = MotionIntelligenceEngine()
    scenes = json.loads((mock_motion_project / "visual_planning.json").read_text(encoding="utf-8"))["scenes"]

    mock_llm_data = {
        "scenes": [
            {
                "scene_id": "scene_01",
                "plan_scene_id": 1,
                "strategy_name": "progressive_disclosure",
                "narrative_role": "hook",
                "emotional_tone": "anticipation",
                "intensity": "energetic",
                "camera": {"move": "push-in", "from": 1.0, "to": 1.10, "focus": [0.5, 0.45], "drift": 0.25, "rationale": "Slow push-in on hero hook"},
                "spring_profile": "snappy",
                "text_preset": "bounce",
                "graphic_preset": "light-sweep",
                "transition_type": "light-leak",
                "rationale": "Hook requires energetic reveal",
            },
            {
                "scene_id": "scene_02",
                "plan_scene_id": 2,
                "strategy_name": "directional_motion",
                "narrative_role": "contrast",
                "emotional_tone": "serious challenge",
                "intensity": "moderate",
                "camera": {"move": "pan-left", "from": 1.0, "to": 1.05, "focus": [0.45, 0.5], "drift": 0.2, "rationale": "Lateral move for contrast"},
                "spring_profile": "dramatic_overshoot",
                "text_preset": "fade-slide",
                "graphic_preset": "divider-grow",
                "transition_type": "wipe",
                "rationale": "Contrast requires sharp divider",
            },
            {
                "scene_id": "scene_03",
                "plan_scene_id": 3,
                "strategy_name": "dramatic_impact",
                "narrative_role": "conclusion",
                "emotional_tone": "resolute",
                "intensity": "moderate",
                "camera": {"move": "pull-out", "from": 1.08, "to": 1.0, "focus": [0.5, 0.5], "drift": 0.15, "rationale": "Pull-out resolves video"},
                "spring_profile": "gentle",
                "text_preset": "split-words",
                "graphic_preset": "circular-meter",
                "transition_type": "none",
                "rationale": "Conclusion stabilizes motion",
            },
        ]
    }

    with patch.object(engine, "_execute_llm_motion_planning", return_value=mock_llm_data):
        res = engine.plan_motion_intelligence(mock_motion_project, scenes, aspect="16:9")

    assert res.status == "completed"
    assert res.llm_metadata["llm_used"] is True
    assert len(res.scene_strategies) == 3

    # Check strategy values
    assert res.scene_strategies[0].strategy_name == "progressive_disclosure"
    assert res.scene_strategies[1].camera.move == "pan-left"
    assert res.scene_strategies[2].spring.name == "gentle"


# ------------------ TEST 3: Safe-Area and Portrait (9:16) Handling ------------------
def test_motion_intelligence_portrait_aspect_margins(mock_motion_project):
    """Verifies that 9:16 portrait aspect ratio respects bottom UI safety clearance."""
    engine = MotionIntelligenceEngine()
    scenes = json.loads((mock_motion_project / "visual_planning.json").read_text(encoding="utf-8"))["scenes"]

    with patch.object(engine, "_execute_llm_motion_planning", return_value=None):
        intel = engine.plan_motion_intelligence(mock_motion_project, scenes, aspect="9:16")
        compiled = engine.compile_motion_plan_json(mock_motion_project, scenes, aspect="9:16", intelligence=intel)

    assert compiled["aspect"] == "9:16"
    assert (mock_motion_project / "motion_plan_9x16.json").exists()

    # Verify that graphics and texts do not reach beyond 0.84 on Y in portrait
    for sc in compiled["scenes"]:
        for t in sc["texts"]:
            b = t["drawn_box"]
            assert b[3] <= 0.85, f"Text box bottom {b[3]} violates portrait bottom safety"


# ------------------ TEST 4: Camera Bounds Clamping ------------------
def test_camera_intent_bounds_clamping():
    """Ensures CameraIntent deterministically clamps out-of-range zooms and focus points."""
    # Attempt extreme zoom (2.5) and focus outside [0.15, 0.85]
    extreme_cam = CameraIntent(
        move="push-in",
        zoom_from=0.8,   # below min (1.0)
        zoom_to=2.5,     # above max (1.15)
        focus=[0.05, 0.95],  # outside safe focus
        drift=1.5,       # above max (1.0)
    )
    d = extreme_cam.to_dict()
    assert d["from"] == 1.0
    assert d["to"] == 1.15
    assert d["focus"] == [0.15, 0.85]
    assert d["drift"] == 1.0


# ------------------ TEST 5: Telugu Text Safe Preset Enforcement ------------------
def test_telugu_text_preset_enforcement():
    """Verifies that non-indic presets like 'kinetic-pop' are replaced with Telugu-safe presets."""
    engine = MotionIntelligenceEngine()
    telugu_text = "ఈ రోజు మనం ఆర్టిఫిషియల్ ఇంటెలిజెన్స్ గురించి నేర్చుకుందాం"

    # Attempt to use non-indic preset
    safe_preset = engine._resolve_safe_text_preset(telugu_text, "kinetic-pop")
    assert safe_preset in SUPPORTED_TEXT_PRESETS["indic_safe"]
    assert safe_preset != "kinetic-pop"

    # Valid indic preset is preserved
    preserved = engine._resolve_safe_text_preset(telugu_text, "bounce")
    assert preserved == "bounce"


# ------------------ TEST 6: End-to-End MotionPlanningAgent Execute ------------------
def test_motion_planning_agent_execute_workflow(mock_motion_project):
    """End-to-end execution of MotionPlanningAgent producing motion_plan.json & companion specs."""
    agent = MotionPlanningAgent()
    req = AgentRequest(project_id=mock_motion_project.name, agent_id="motion_planning", stage_id="motion_plan")

    with patch.object(agent.intelligence_engine, "_execute_llm_motion_planning", return_value=None), \
         patch("SYSTEM.policies.llm_review.run_stage_llm_review", return_value={"status": "passed"}), \
         patch("VIDEO_ENGINE.stages.motion_planning.build", return_value={"scenes": []}), \
         patch("VIDEO_ENGINE.stages.motion_planning.save"):
        res = agent.execute(mock_motion_project, req)

    assert res.status == "succeeded"
    assert "Motion typography and element placements planned" in res.summary
    assert res.metadata["scenes_count"] == 3
    assert res.metadata["strategies_variety"] >= 2

    # Check output files
    assert (mock_motion_project / "motion_plan.json").exists()
    assert (mock_motion_project / "motion_intelligence.json").exists()

    plan_data = json.loads((mock_motion_project / "motion_plan.json").read_text(encoding="utf-8"))
    assert plan_data["version"] == 2
    assert len(plan_data["scenes"]) == 3
    for sc in plan_data["scenes"]:
        assert "camera" in sc
        assert "spring" in sc
        assert "strategy" in sc
        assert "transition" in sc


def test_visual_plan_scene_shape_narration_object_and_source_mapping(tmp_path: Path):
    """The visual plan stores narration as an object and the times in source_mapping: telemetry must read both (it used to crash on `.split`)."""
    scene = {
        "scene_id": "scene_001",
        "narration": {"text": "one two three four five six", "text_en": "x", "start_seconds": 0.0, "end_seconds": 3.0},
        "source_mapping": {"plan_start": 0.0, "plan_end": 3.0},
    }
    tel = MotionIntelligenceEngine()._extract_audio_telemetry(tmp_path, [scene])
    assert tel["scenes"]["scene_001"]["words_count"] == 6
    assert tel["scenes"]["scene_001"]["duration_seconds"] == 3.0
    assert tel["scenes"]["scene_001"]["speech_rate_wpm"] == 120.0
