import hashlib
import json
from pathlib import Path

import pytest

from SYSTEM.agents.video_generation_agents.visual_planning.agent import VisualPlanningAgent
from SYSTEM.registries.agent_registry import AgentRegistry
from SYSTEM.skills import get_category_taxonomy
from VIDEO_ENGINE.stages import visual_planning, motion_planning

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_skills_installed_and_discoverable_in_skill_factory():
    """Verify that all 4 new visual skills are registered in the Skill Factory and agent directories."""
    lib_root = PROJECT_ROOT / "SYSTEM" / "skills" / "library"
    agent_skills_root = PROJECT_ROOT / "SYSTEM" / "agents" / "video_generation_agents" / "visual_planning" / "skills"

    expected_skills = [
        ("layouts", "visual-cinematic-composition", "cinematic_composition"),
        ("science_visuals", "visual-narrative-semantic-mapping", "narrative_semantic_mapping"),
        ("motion_animation", "visual-word-semantic-animation", "word_semantic_animation"),
        ("video_editing", "visual-scene-variety-pacing", "scene_variety_pacing"),
    ]

    taxonomy = get_category_taxonomy()
    cat_ids = {c.category_id for c in taxonomy.list_categories()}
    for cat, lib_folder, agent_folder in expected_skills:
        assert cat in cat_ids, f"Category {cat} missing from 25-category taxonomy"
        central_skill_md = lib_root / cat / lib_folder / "SKILL.md"
        assert central_skill_md.exists(), f"Skill missing from library: {central_skill_md}"
        agent_skill_md = agent_skills_root / agent_folder / "SKILL.md"
        assert agent_skill_md.exists(), f"Skill missing from agent: {agent_skill_md}"

        content = agent_skill_md.read_text(encoding="utf-8")
        assert "name:" in content
        assert "description:" in content

    registry = AgentRegistry()
    agent = registry.get_agent("visual_planning")
    assert agent is not None
    for _, _, agent_folder in expected_skills:
        skill_identifier = f"visual.{agent_folder}"
        assert skill_identifier in agent.metadata.skills, f"Skill {skill_identifier} not in VisualPlanningAgent metadata"


def test_visual_planning_depth_layers_and_word_events_on_project(tmp_path):
    """Verify that a visual plan has depth layers and synchronized word animation events across all scenes."""
    import importlib
    _v = importlib.import_module("test_visual_planning")
    pdir, sp = _v.project(tmp_path)
    plan, problems = visual_planning.assemble(pdir, sp, _v.raw_for(sp))
    assert problems == []
    vp = plan
    scenes = vp.get("scenes", [])
    assert len(scenes) == len(sp["scenes"]), f"Expected {len(sp['scenes'])} scenes, got {len(scenes)}"

    total_we = 0
    valid_depths = {"foreground", "midground", "background"}

    for sc in scenes:
        sid = sc["scene_id"]
        nar = sc["narration"]
        start_s = nar["start_seconds"]
        end_s = nar["end_seconds"]

        # Check element depth layers
        elements = sc.get("elements", [])
        assert len(elements) >= 2, f"{sid} has fewer than 2 elements"
        element_ids = {e["element_id"] for e in elements}

        for el in elements:
            assert el.get("depth_layer") in valid_depths, f"Invalid or missing depth_layer in {sid} element {el['element_id']}"
            if el["role"] == "primary":
                assert el["depth_layer"] == "foreground", f"Primary element in {sid} should be foreground"
            if el["type"] == "background":
                assert el["depth_layer"] == "background", f"Background element in {sid} should be background"

        # Check word animation events
        events = sc.get("word_animation_events", [])
        assert len(events) >= 2, f"{sid} should have at least 2 word animation events, found {len(events)}"
        total_we += len(events)

        for we in events:
            assert we["target_element_id"] in element_ids, f"Word event targets non-existent element in {sid}: {we['target_element_id']}"
            assert start_s - 0.05 <= we["start_seconds"] < we["end_seconds"] <= end_s + 0.05, (
                f"Word event {we['event_id']} timing [{we['start_seconds']}, {we['end_seconds']}] outside scene bounds [{start_s}, {end_s}]"
            )
            assert we.get("semantic_intent"), f"Word event in {sid} missing semantic_intent"
            assert we.get("visual_treatment"), f"Word event in {sid} missing visual_treatment"

    assert total_we >= 2 * len(scenes), f"Expected at least 2 word animation events per scene (the planner contract: 2 to 4), found {total_we}"


def test_semantic_lexicon_keyword_matching():
    """Verify semantic lexicon correctly categorizes key action verbs and narrative terms."""
    from VIDEO_ENGINE.stages.visual_planning_rules import SEMANTIC_LEXICON

    test_words = [
        ("పుడుతోంది", "ignite_birth"),
        ("వేగం", "velocity_pulse"),
        ("వ్యవస్థను", "network_connect"),
        ("కొత్త", "staggered_cascade"),
        ("ప్రమాదం", "danger_alert_pulse"),
        ("ముగింపు", "dissolve_fade"),
        ("భూమి", "global_orbit"),
        ("super", "scale_expand"),
    ]

    for word, expected_intent in test_words:
        matched_intent = None
        for keywords, intent, _ in SEMANTIC_LEXICON:
            if word in keywords or word.lower() in keywords:
                matched_intent = intent
                break
        assert matched_intent == expected_intent, f"Word '{word}' mapped to {matched_intent}, expected {expected_intent}"


def test_downstream_motion_planning_compatibility(tmp_path):
    """Verify that downstream Motion Planning accepts the Visual Plan (with real elements) without blocking errors."""
    import importlib
    pdir, sp, *_ = importlib.import_module("test_motion_planning").make(tmp_path / "proj", real={1: "image", 7: "video"})
    plan = motion_planning.build(pdir, "16:9", run_tests=False)
    assert plan is not None
    assert len(plan["validation"]["errors"]) == 0, f"Motion Planning encountered blocking errors: {plan['validation']['errors']}"
    assert len(plan["scenes"]) == len(sp["scenes"]), f"Expected {len(sp['scenes'])} scenes in motion plan, got {len(plan['scenes'])}"
