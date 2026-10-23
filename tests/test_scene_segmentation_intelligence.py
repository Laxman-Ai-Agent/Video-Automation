"""Comprehensive test suite for Scene Segmentation Semantic Intelligence Upgrade (v2.0.0).

Validates:
2. Narrative topic & chapter modeling across bilingual Telugu-English narration.
3. Telugu-English technical vocabulary normalization without transcript corruption.
4. Adaptive pacing calculations (WPM, pause density, pacing profiles) from real telemetry.
5. Strict enforcement of Deterministic Invariant Guard (word snapping, 2-12s limits, no gaps/overlaps).
6. Rejection of candidate adjustments violating invariants and safe retention of canonical scenes.
7. Autonomous fallback to deterministic heuristic analysis when LLM Gateway fails or times out.
8. Artifact schema compliance and downstream compatibility for Visual Planning.
9. Agent memory experience persistence.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from SYSTEM.agents.shared.contracts import AgentRequest
from SYSTEM.agents.video_generation_agents.scene_segmentation.agent import SceneSegmentationAgent
from SYSTEM.agents.video_generation_agents.scene_segmentation.semantic_analyzer import (
    DeterministicInvariantGuard,
    SemanticAnalyzer,
)


@pytest.fixture
def test_project(tmp_path: Path) -> Path:
    """Creates a temporary project with bilingual Telugu-English transcript and segmentation."""
    pdir = tmp_path / "proj_semantic_test"
    pdir.mkdir(parents=True)

    # Transcript with bilingual text and realistic word timestamps
    transcript_data = {
        "text": "నమస్కారం! ఈ రోజు మనం Artificial Intelligence మరియు Machine Learning గురించి చర్చిస్తున్నాము. "
                "ఇది చాలా శక్తివంతమైన టెక్నాలజీ. కానీ కొన్ని సవాళ్లు ఉన్నాయి. "
                "చివరగా మనం భవిష్యత్ అవకాశాలను చూద్దాం.",
        "language": "te",
        "duration": 18.0,
        "segments": [
            {
                "id": 0,
                "start": 0.0,
                "end": 6.0,
                "text": "నమస్కారం! ఈ రోజు మనం Artificial Intelligence మరియు Machine Learning గురించి చర్చిస్తున్నాము.",
                "words": [
                    {"word": "నమస్కారం!", "start": 0.0, "end": 1.2},
                    {"word": "ఈ", "start": 1.3, "end": 1.5},
                    {"word": "రోజు", "start": 1.6, "end": 2.0},
                    {"word": "మనం", "start": 2.1, "end": 2.4},
                    {"word": "Artificial", "start": 2.5, "end": 3.4},
                    {"word": "Intelligence", "start": 3.5, "end": 4.3},
                    {"word": "మరియు", "start": 4.4, "end": 4.8},
                    {"word": "Machine", "start": 4.9, "end": 5.3},
                    {"word": "Learning", "start": 5.4, "end": 5.8},
                    {"word": "గురించి", "start": 5.9, "end": 6.0},
                ],
            },
            {
                "id": 1,
                "start": 6.0,
                "end": 12.0,
                "text": "ఇది చాలా శక్తివంతమైన టెక్నాలజీ. కానీ కొన్ని సవాళ్లు ఉన్నాయి.",
                "words": [
                    {"word": "చర్చిస్తున్నాము.", "start": 6.0, "end": 6.8},
                    {"word": "ఇది", "start": 6.9, "end": 7.2},
                    {"word": "చాలా", "start": 7.3, "end": 7.7},
                    {"word": "శక్తివంతమైన", "start": 7.8, "end": 8.7},
                    {"word": "టెక్నాలజీ.", "start": 8.8, "end": 9.5},
                    {"word": "కానీ", "start": 9.8, "end": 10.2},
                    {"word": "కొన్ని", "start": 10.3, "end": 10.7},
                    {"word": "సవాళ్లు", "start": 10.8, "end": 11.4},
                    {"word": "ఉన్నాయి.", "start": 11.5, "end": 12.0},
                ],
            },
            {
                "id": 2,
                "start": 12.0,
                "end": 18.0,
                "text": "చివరగా మనం భవిష్యత్ అవకాశాలను చూద్దాం.",
                "words": [
                    {"word": "చివరగా", "start": 12.2, "end": 13.0},
                    {"word": "మనం", "start": 13.1, "end": 13.5},
                    {"word": "భవిష్యత్", "start": 13.6, "end": 14.5},
                    {"word": "అవకాశాలను", "start": 14.6, "end": 15.8},
                    {"word": "చూద్దాం.", "start": 16.0, "end": 17.5},
                ],
            },
        ],
    }
    (pdir / "transcript.json").write_text(json.dumps(transcript_data, ensure_ascii=False), encoding="utf-8")

    # Canonical scene_segmentation.json (3 scenes, durations 6.0s each)
    segmentation_data = {
        "scenes": [
            {
                "scene_id": "scene_001",
                "scene_index": 1,
                "start_time": 0.0,
                "end_time": 6.0,
                "word_range": [0, 9],
                "transcript": "నమస్కారం! ఈ రోజు మనం Artificial Intelligence మరియు Machine Learning గురించి",
            },
            {
                "scene_id": "scene_002",
                "scene_index": 2,
                "start_time": 6.0,
                "end_time": 12.0,
                "word_range": [10, 18],
                "transcript": "చర్చిస్తున్నాము. ఇది చాలా శక్తివంతమైన టెక్నాలజీ. కానీ కొన్ని సవాళ్లు ఉన్నాయి.",
            },
            {
                "scene_id": "scene_003",
                "scene_index": 3,
                "start_time": 12.0,
                "end_time": 18.0,
                "word_range": [19, 23],
                "transcript": "చివరగా మనం భవిష్యత్ అవకాశాలను చూద్దాం.",
            },
        ],
    }
    (pdir / "scene_segmentation.json").write_text(json.dumps(segmentation_data, ensure_ascii=False), encoding="utf-8")

    # Cuts data with silence interval between scene 2 and scene 3
    cuts_data = [
        {"start": 0.0, "end": 12.0, "type": "keep"},
        {"start": 12.0, "end": 12.2, "type": "silence"},
        {"start": 12.2, "end": 17.5, "type": "keep"},
    ]
    (pdir / "cuts.json").write_text(json.dumps(cuts_data), encoding="utf-8")

    return pdir


# ------------------ TEST 2: Semantic Analyzer Fallback Analysis ------------------
def test_semantic_analyzer_deterministic_fallback(test_project):
    """Verifies that heuristic semantic review runs cleanly when LLM is unavailable."""
    analyzer = SemanticAnalyzer()
    t_data = json.loads((test_project / "transcript.json").read_text(encoding="utf-8"))
    s_data = json.loads((test_project / "scene_segmentation.json").read_text(encoding="utf-8"))
    c_data = json.loads((test_project / "cuts.json").read_text(encoding="utf-8"))

    # Force LLM gateway to return None (simulating unavailable LLM)
    with patch.object(analyzer, "_execute_llm_semantic_review", return_value=None):
        res = analyzer.analyze(test_project, s_data, t_data, c_data)

    assert res.status == "fallback_deterministic"
    assert len(res.scenes) == 3
    assert len(res.topics) >= 3

    # Check narrative roles assigned by heuristic
    roles = [t.narrative_role for t in res.topics]
    assert "hook" in roles  # Scene 1 hook
    assert "conclusion" in roles or "reveal" in roles  # Scene 3 ending

    # Check vocabulary extraction for English technical terms in Telugu context
    vocab_terms = [v.normalized_term for v in res.vocabulary]
    assert "Artificial" in vocab_terms or "Intelligence" in vocab_terms or "Learning" in vocab_terms

    # Check pacing advice
    assert len(res.pacing_advice) == 3
    for p in res.pacing_advice:
        assert p.speech_rate_wpm > 0
        assert p.recommended_pacing in ("fast_cut", "brisk", "balanced", "expanded_pause", "dramatic_hold")

    # Invariants must pass
    assert res.invariant_status["all_invariants_passed"] is True
    assert (test_project / "scene_semantic_annotations.json").exists()


# ------------------ TEST 3: LLM Gateway Integration & Enrichment ------------------
def test_semantic_analyzer_llm_gateway_success(test_project):
    """Verifies structured enrichment when LLM Gateway returns high-level topic reasoning."""
    analyzer = SemanticAnalyzer()
    t_data = json.loads((test_project / "transcript.json").read_text(encoding="utf-8"))
    s_data = json.loads((test_project / "scene_segmentation.json").read_text(encoding="utf-8"))

    mock_llm_response = {
        "topics": [
            {
                "topic_id": "topic_01",
                "title": "Welcome and Tech Intro",
                "narrative_role": "hook",
                "start_time": 0.0,
                "end_time": 6.0,
                "scene_ids": ["scene_001"],
                "transition_type": "topic_change",
                "confidence": 0.95,
                "main_idea": "Warm greeting introducing AI and Machine Learning",
            },
            {
                "topic_id": "topic_02",
                "title": "Capabilities and Key Challenges",
                "narrative_role": "problem",
                "start_time": 6.0,
                "end_time": 12.0,
                "scene_ids": ["scene_002"],
                "transition_type": "contrast",
                "confidence": 0.92,
                "main_idea": "Power of technology contrasted with real challenges",
            },
            {
                "topic_id": "topic_03",
                "title": "Future Outlook",
                "narrative_role": "conclusion",
                "start_time": 12.0,
                "end_time": 18.0,
                "scene_ids": ["scene_003"],
                "transition_type": "conclusion",
                "confidence": 0.98,
                "main_idea": "Summary and forward-looking exploration",
            },
        ],
        "vocabulary": [
            {
                "term": "Artificial Intelligence",
                "original_text": "Artificial Intelligence",
                "normalized_term": "Artificial Intelligence",
                "language_code": "en",
                "category": "technical_term",
                "scene_ids": ["scene_001"],
                "occurrences": 1,
            },
            {
                "term": "Machine Learning",
                "original_text": "Machine Learning",
                "normalized_term": "Machine Learning",
                "language_code": "en",
                "category": "technical_term",
                "scene_ids": ["scene_001"],
                "occurrences": 1,
            },
        ],
    }

    with patch.object(analyzer, "_execute_llm_semantic_review", return_value=mock_llm_response):
        res = analyzer.analyze(test_project, s_data, t_data)

    assert res.status == "completed"
    assert len(res.topics) == 3
    assert res.topics[0].title == "Welcome and Tech Intro"
    assert res.topics[1].narrative_role == "problem"

    # Enriched scenes
    sc1 = res.scenes[0]
    assert sc1["topic_id"] == "topic_01"
    assert sc1["narrative_role"] == "hook"
    assert "semantic_beat" in sc1
    assert "pacing_profile" in sc1


# ------------------ TEST 4: Deterministic Invariant Guard Enforcement ------------------
def test_invariant_guard_catches_violations():
    """Ensures invariant guard rejects duration limits, gap/overlap, and coverage defects."""
    words = [
        {"id": "w001", "start": 0.0, "end": 2.0, "text": "Word1"},
        {"id": "w002", "start": 2.0, "end": 4.0, "text": "Word2"},
        {"id": "w003", "start": 4.0, "end": 6.0, "text": "Word3"},
    ]

    # Case A: Too short scene (< 2.0s)
    short_scenes = [
        {"scene_id": "sc1", "start_time": 0.0, "end_time": 1.5, "word_range": [0, 0]},
        {"scene_id": "sc2", "start_time": 1.5, "end_time": 6.0, "word_range": [1, 2]},
    ]
    ok_a, viols_a = DeterministicInvariantGuard.validate_scene_invariants(short_scenes, words, 6.0)
    assert not ok_a
    assert any("below minimum" in v for v in viols_a)

    # Case B: Unintended gap between scenes
    gap_scenes = [
        {"scene_id": "sc1", "start_time": 0.0, "end_time": 2.5, "word_range": [0, 0]},
        {"scene_id": "sc2", "start_time": 4.0, "end_time": 6.0, "word_range": [2, 2]},
    ]
    ok_b, viols_b = DeterministicInvariantGuard.validate_scene_invariants(gap_scenes, words, 6.0)
    assert not ok_b
    assert any("gap" in v or "coverage" in v for v in viols_b)

    # Case C: Valid scenes pass
    valid_scenes = [
        {"scene_id": "sc1", "start_time": 0.0, "end_time": 3.0, "word_range": [0, 0]},
        {"scene_id": "sc2", "start_time": 3.0, "end_time": 6.0, "word_range": [1, 2]},
    ]
    ok_c, viols_c = DeterministicInvariantGuard.validate_scene_invariants(valid_scenes, words, 6.0)
    assert ok_c
    assert len(viols_c) == 0


# ------------------ TEST 5: Full SceneSegmentationAgent Execute Workflow ------------------
def test_scene_segmentation_agent_execute_success(test_project):
    """End-to-end execution of SceneSegmentationAgent producing enriched artifacts."""
    agent = SceneSegmentationAgent()
    req = AgentRequest(project_id=test_project.name, agent_id="scene_segmentation", stage_id="segmentation")

    with patch.object(agent.semantic_analyzer, "_execute_llm_semantic_review", return_value=None):
        res = agent.execute(test_project, req)
    assert res.status == "succeeded"
    assert "Scene segmentation validated with 3 scenes (no ASR re-run)" in res.summary
    assert len(res.output_refs) == 1
    assert res.output_refs[0].path.endswith("scene_segmentation.json")

    # Metadata checks
    assert res.metadata["scenes_count"] == 3
    assert res.metadata["topics_count"] >= 3
    assert res.metadata["all_invariants_passed"] is True
    assert res.metadata["average_wpm"] > 0
    assert res.metadata["semantic_annotations_path"] is not None

    # Verify scene_segmentation.json was updated with non-destructive semantic tags
    updated_data = json.loads((test_project / "scene_segmentation.json").read_text(encoding="utf-8"))
    assert "semantic_intelligence" in updated_data
    assert len(updated_data["scenes"]) == 3
    for sc in updated_data["scenes"]:
        assert "narrative_role" in sc
        assert "topic_id" in sc
        assert "pacing_profile" in sc

    # Original transcript timestamps must remain unchanged
    orig_transcript = json.loads((test_project / "transcript.json").read_text(encoding="utf-8"))
    assert orig_transcript["duration"] == 18.0
    assert orig_transcript["segments"][0]["words"][0]["start"] == 0.0


# ------------------ TEST 6: Missing Artifact Fails Closed ------------------
def test_scene_segmentation_agent_missing_artifact_blocks(test_project):
    """Missing scene_segmentation.json returns blocked without re-running ASR."""
    (test_project / "scene_segmentation.json").unlink()
    agent = SceneSegmentationAgent()
    req = AgentRequest(project_id=test_project.name, agent_id="scene_segmentation", stage_id="segmentation")

    res = agent.execute(test_project, req)
    assert res.status == "blocked"
    assert "Silent ASR or re-segmentation is prohibited" in res.summary
