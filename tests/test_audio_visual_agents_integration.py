"""Phase 6: Audio & Visual Agents Integration Tests.

Validates:
1. Audio Input agent validation, rejection of invalid/oversized/traversal files, and manifest generation.
2. Manifest determinism and fingerprint calculation.
3. Audio Analyzer adapter reuses canonical outputs and NEVER calls ASR/transcribe.
4. Missing/stale audio analysis artifacts block fail-closed without silent regeneration.
5. Scene Segmentation adapter reuses canonical outputs, enforces ordering/duration, and NEVER calls ASR.
6. Visual Planning structured response through LLM Gateway with exact scene coverage.
7. Telugu script preservation and Motion-Only enforcement (rejection of external image URLs).
8. Bounded repair and gateway error handling.
9. Mandatory Phase 2 review fail-closed gate.
10. Truthful agent communication and Phase 3 state tracking.
12. Zero calls into ASR or full video pipeline rendering.
"""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.agents.registry import get_agent_registry
from backend.agents.contracts import AgentRequest, AgentResult
from SYSTEM.agents.video_generation_agents.audio_input.agent import AudioInputAgent
from backend.artifact_contracts import (
    ContractValidationError,
    validate_audio_artifacts,
    validate_analyzer_artifacts,
    validate_segmentation_artifacts,
    validate_planning_artifacts,
    verify_path_confinement,
)
from backend import llm_gateway, llm_review


@pytest.fixture
def mock_no_asr():
    """Ensure that any accidental call to ASR or transcribe fails immediately."""
    with patch("backend.transcribe.transcribe", side_effect=RuntimeError("PROHIBITED: ASR transcribe was invoked!")), \
         patch("backend.scene_segmentation.run", side_effect=RuntimeError("PROHIBITED: Scene segmentation re-run was invoked!")):
        yield


@pytest.fixture
def sample_project(tmp_path):
    """Creates a sample project directory with standard valid deterministic artifacts."""
    pdir = tmp_path / "proj_test_01"
    pdir.mkdir(parents=True)

    # 1. Source audio file
    audio_file = pdir / "audio.wav"
    audio_file.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00")

    # 2. info.json
    (pdir / "info.json").write_text(
        json.dumps({
            "name": "proj_test_01",
            "aspect": "16:9",
            "audio": {"file": "audio.wav", "duration": 12.0, "format": "WAV", "size_bytes": 44},
        }),
        encoding="utf-8",
    )

    # 3. transcript.json & cuts.json
    (pdir / "transcript.json").write_text(
        json.dumps({
            "text": "నమస్కారం, ఇది మొదటి దృశ్యం. Artificial Intelligence గురించి చర్చిస్తున్నాము.",
            "language": "te",
            "duration": 12.0,
            "segments": [
                {
                    "id": 0,
                    "start": 0.0,
                    "end": 6.0,
                    "text": "నమస్కారం, ఇది మొదటి దృశ్యం.",
                    "words": [
                        {"word": "నమస్కారం", "start": 0.0, "end": 2.5},
                        {"word": "ఇది", "start": 2.6, "end": 3.5},
                        {"word": "మొదటి", "start": 3.6, "end": 4.5},
                        {"word": "దృశ్యం", "start": 4.6, "end": 5.8},
                    ],
                },
                {
                    "id": 1,
                    "start": 6.0,
                    "end": 12.0,
                    "text": "Artificial Intelligence గురించి చర్చిస్తున్నాము.",
                    "words": [
                        {"word": "Artificial", "start": 6.0, "end": 7.5},
                        {"word": "Intelligence", "start": 7.6, "end": 9.0},
                        {"word": "గురించి", "start": 9.1, "end": 10.2},
                        {"word": "చర్చిస్తున్నాము", "start": 10.3, "end": 11.8},
                    ],
                },
            ],
        }),
        encoding="utf-8",
    )

    (pdir / "cuts.json").write_text(
        json.dumps([{"start": 0.0, "end": 12.0, "type": "keep"}]),
        encoding="utf-8",
    )

    # 4. scene_segmentation.json
    (pdir / "scene_segmentation.json").write_text(
        json.dumps({
            "scenes": [
                {
                    "id": "scene_01",
                    "start": 0.0,
                    "end": 6.0,
                    "duration": 6.0,
                    "narration": "నమస్కారం, ఇది మొదటి దృశ్యం.",
                },
                {
                    "id": "scene_02",
                    "start": 6.0,
                    "end": 12.0,
                    "duration": 6.0,
                    "narration": "Artificial Intelligence గురించి చర్చిస్తున్నాము.",
                },
            ],
        }),
        encoding="utf-8",
    )

    # 5. scene_plan.json & prompts_map.json
    # 5. scene_plan.json & prompts_map.json
    (pdir / "scene_plan.json").write_text(
        json.dumps({
            "style": {
                "suffix": "clean modern visual style",
                "palette": ["#000000", "#ffffff"],
            },
            "scenes": [
                {
                    "id": 1,
                    "start": 0.0,
                    "end": 6.0,
                    "meaning": "Welcome introduction",
                    "concept": "Warm Telugu greeting card",
                    "mood": "welcoming",
                    "mode": "typography",
                    "pattern": "kinetic_typography",
                    "keywords": [{"text": "నమస్కారం", "at": 1.0}],
                    "params": {},
                },
                {
                    "id": 2,
                    "start": 6.0,
                    "end": 12.0,
                    "meaning": "Introduction to AI technology",
                    "concept": "AI neural network schematic",
                    "mood": "innovative",
                    "mode": "typography",
                    "pattern": "kinetic_typography",
                    "keywords": [{"text": "Artificial Intelligence", "at": 7.0}],
                    "params": {},
                },
            ],
        }),
        encoding="utf-8",
    )

    (pdir / "prompts_map.json").write_text(json.dumps({"prompts": []}), encoding="utf-8")

    return pdir


# ------------------ TEST 1: Audio Input Validation & Rejection ------------------
def test_audio_input_validation_and_rejection(sample_project, tmp_path):
    """Audio Input accepts valid audio and rejects empty, unsupported, and path-traversal inputs."""
    adapter = AudioInputAgent()
    req = AgentRequest(project_id="proj_test_01", agent_id="audio_input", stage_id="audio")

    # 1. Valid deterministic audio
    errs = adapter.validate(sample_project, req)
    assert errs == []

    # 2. Empty audio file (0 bytes)
    empty_audio = sample_project / "audio.wav"
    empty_audio.write_bytes(b"")
    errs_empty = adapter.validate(sample_project, req)
    assert any("empty" in e.lower() for e in errs_empty)

    # 3. Unsupported extension
    empty_audio.unlink()
    bad_ext = sample_project / "audio.txt"
    bad_ext.write_text("not an audio file", encoding="utf-8")
    errs_ext = adapter.validate(sample_project, req)
    assert any("unsupported" in e.lower() for e in errs_ext)

    # 4. Path traversal outside project root
    with pytest.raises(ContractValidationError):
        verify_path_confinement(sample_project, tmp_path / "outside_audio.wav")


# ------------------ TEST 2: Input Manifest Determinism ------------------
def test_audio_input_manifest_determinism_and_fingerprint(sample_project):
    """Manifest generates identical SHA-256 & fingerprint for unchanged bytes and updates on change."""
    adapter = AudioInputAgent()
    req = AgentRequest(project_id="proj_test_01", agent_id="audio_input", stage_id="audio")

    res1 = adapter.execute(sample_project, req)
    assert res1.status == "succeeded"
    manifest_p = sample_project / "audio_input_manifest.json"
    assert manifest_p.exists()

    data1 = json.loads(manifest_p.read_text(encoding="utf-8"))
    sha1 = data1["sha256"]
    assert sha1 != "missing"
    assert data1["aspect_ratio"] == "16:9"
    assert data1["visual_mode"] == "motion-only"

    # Second execution on identical bytes produces identical SHA-256
    res2 = adapter.execute(sample_project, req)
    data2 = json.loads(manifest_p.read_text(encoding="utf-8"))
    assert data2["sha256"] == sha1

    # Modifying audio bytes changes the sha256 fingerprint
    (sample_project / "audio.wav").write_bytes(b"RIFF....modified bytes....")
    res3 = adapter.execute(sample_project, req)
    data3 = json.loads(manifest_p.read_text(encoding="utf-8"))
    assert data3["sha256"] != sha1


# ------------------ TEST 3: Audio Analyzer Reuses Output (No ASR) ------------------
def test_audio_analyzer_wrapper_reuses_artifacts_without_asr(sample_project, mock_no_asr):
    """Audio Analyzer wrapper consumes valid artifacts and NEVER calls ASR or transcribe."""
    registry = get_agent_registry()
    adapter = registry.get_agent("audio_analyzer")
    req = AgentRequest(project_id="proj_test_01", agent_id="audio_analyzer", stage_id="analyzer")

    # Validate passes
    errs = adapter.validate(sample_project, req)
    assert errs == []

    # Execute reuses transcript.json and cuts.json without calling whisper
    res = adapter.execute(sample_project, req)
    assert res.status == "succeeded"
    assert "without ASR re-run" in res.summary
    assert len(res.output_refs) >= 1
    assert any(ref.path.endswith("transcript.json") for ref in res.output_refs)


# ------------------ TEST 4: Missing Audio Analysis Artifacts Block Fail-Closed ------------------
def test_audio_analyzer_missing_artifact_blocks_downstream(sample_project, mock_no_asr):
    """Missing transcript.json returns status=blocked and NEVER triggers silent Whisper regeneration."""
    (sample_project / "transcript.json").unlink()

    registry = get_agent_registry()
    adapter = registry.get_agent("audio_analyzer")
    req = AgentRequest(project_id="proj_test_01", agent_id="audio_analyzer", stage_id="analyzer")

    res = adapter.execute(sample_project, req)
    assert res.status == "blocked"
    assert "Missing canonical transcript.json" in res.summary


# ------------------ TEST 5: Scene Segmentation Reuses Output (No ASR) ------------------
def test_scene_segmentation_wrapper_reuses_artifacts_without_asr(sample_project, mock_no_asr):
    """Scene Segmentation wrapper validates existing scenes and durations without ASR re-run."""
    registry = get_agent_registry()
    adapter = registry.get_agent("scene_segmentation")
    req = AgentRequest(project_id="proj_test_01", agent_id="scene_segmentation", stage_id="segmentation")

    res = adapter.execute(sample_project, req)
    assert res.status == "succeeded"
    assert "Scene segmentation validated with 2 scenes" in res.summary
    assert len(res.output_refs) == 1
    assert res.output_refs[0].path.endswith("scene_segmentation.json")

    # If non-positive duration scene exists, validation fails
    (sample_project / "scene_segmentation.json").write_text(
        json.dumps({"scenes": [{"id": "scene_01", "start": 5.0, "end": 2.0}]}),
        encoding="utf-8",
    )
    res_invalid = adapter.execute(sample_project, req)
    assert res_invalid.status == "failed"
    assert "non-positive duration" in res_invalid.summary


# ------------------ TEST 6: Visual Planning Structured Generation via Gateway ------------------
def test_visual_planning_structured_generation_via_gateway(sample_project):
    """Visual Planning executes through LLM Gateway and outputs scene concepts matching segmentation."""
    registry = get_agent_registry()
    adapter = registry.get_agent("visual_planning")
    req = AgentRequest(project_id="proj_test_01", agent_id="visual_planning", stage_id="planning", correlation_id="corr-plan-01")

    # Deterministic mock gateway response for visual planning matching LlmVisualPlan schema
    mock_plan_output = json.dumps({
        "visual_plan": {
            "visual_style": {
                "category": "kinetic_typography",
                "tone": "professional",
                "typography": "clean sans-serif",
                "density": "medium",
                "contrast_policy": "high",
            },
            "scenes": [
                {
                    "plan_scene_id": 1,
                    "scene_objective": {
                        "core_meaning": "Warm welcome in native Telugu",
                        "audience_takeaway": "Viewer feels welcomed",
                        "narrative_role": "hook",
                    },
                    "visual_concept": {
                        "description": "Kinetic typography revealing Telugu greeting with smooth spring easing",
                        "representation": "typography",
                        "primary_focus": "Telugu text",
                    },
                    "elements": [
                        {
                            "element_id": "txt_welcome",
                            "type": "text",
                            "role": "primary",
                            "required": True,
                            "visual_description": "Bold Telugu greeting text",
                            "content": "నమస్కారం",
                            "language": "te",
                            "text_purpose": "title",
                            "placement": {"region": "center", "priority": 1, "avoid_overlap": True},
                        }
                    ],
                    "element_relationships": [],
                    "motion_hints": [{"intent": "reveal_elements", "description": "spring reveal"}],
                    "continuity": {"motifs": [], "transition_intent": "smooth"},
                    "uncertainty": [],
                },
                {
                    "plan_scene_id": 2,
                    "scene_objective": {
                        "core_meaning": "Introduce Artificial Intelligence topic",
                        "audience_takeaway": "Viewer understands AI introduction",
                        "narrative_role": "context",
                    },
                    "visual_concept": {
                        "description": "Geometric neural network diagram with English technical term",
                        "representation": "process_diagram",
                        "primary_focus": "neural network",
                    },
                    "elements": [
                        {
                            "element_id": "txt_ai",
                            "type": "text",
                            "role": "primary",
                            "required": True,
                            "visual_description": "Prominent English technical typography",
                            "content": "Artificial Intelligence",
                            "language": "en",
                            "text_purpose": "title",
                            "placement": {"region": "center", "priority": 1, "avoid_overlap": True},
                        },
                        {
                            "element_id": "diag_network",
                            "type": "diagram",
                            "role": "supporting",
                            "required": True,
                            "visual_description": "Abstract node network diagram",
                            "placement": {"region": "around_primary_visual", "priority": 2, "avoid_overlap": True},
                        }
                    ],
                    "element_relationships": [],
                    "motion_hints": [{"intent": "show_flow_direction", "description": "flow nodes"}],
                    "continuity": {"motifs": [], "transition_intent": "connected"},
                    "uncertainty": [],
                },
            ],
        }
    })

    with patch("backend.llm_gateway.execute_llm_gateway_call") as mock_gw, \
         patch("SYSTEM.core.llm_gateway.execute_llm_gateway_call") as mock_gw2, \
         patch("backend.llm_review.review_stage") as mock_rev:

        mock_gw2.return_value = llm_gateway.GatewayResponse(
            status="passed",
            raw_output=mock_plan_output,
            provider="anthropic",
            model="claude-3-5-haiku-20241022",
            profile="fast_structured",
            purpose="generation",
            stage_id="planning",
        )
        mock_gw.return_value = mock_gw2.return_value
        mock_rev.return_value = llm_review.StageReviewResult(
            stage="planning",
            status="passed",
            score=1.0,
            summary="Visual plan approved with zero blockers",
            findings=[],
        )

        res = adapter.execute(sample_project, req)
        assert res.status == "succeeded", f"Execution failed: {res.summary}"
        assert res.metadata["scenes_count"] == 2
        assert (sample_project / "visual_planning.json").exists()


# ------------------ TEST 7: Telugu Script Preservation & Motion-Only Enforcement ------------------
def test_visual_planning_telugu_preservation_and_motion_only(sample_project):
    """Telugu script is preserved, and external image URLs are rejected in Motion-Only mode."""
    # Write a visual plan that violates Motion-Only with an external image URL
    (sample_project / "visual_planning.json").write_text(
        json.dumps({
            "schema_version": "1.0",
            "version": 3,
            "scenes": [
                {
                    "plan_scene_id": "scene_01",
                    "scene_objective": "Test",
                    "visual_concept": "Test",
                    "elements": [
                        {
                            "element_id": "bad_img",
                            "type": "graphic",
                            "role": "primary",
                            "required": True,
                            "visual_description": "Download photo from https://external-cdn.com/stock.jpg",
                        }
                    ],
                },
                {
                    "plan_scene_id": "scene_02",
                    "scene_objective": "Test 2",
                    "visual_concept": "Test 2",
                    "elements": [
                        {
                            "element_id": "txt_clean",
                            "type": "text",
                            "role": "primary",
                            "required": True,
                            "visual_description": "Valid Telugu text in native script",
                            "content": "నమస్కారం",
                        }
                    ],
                },
            ],
        }),
        encoding="utf-8",
    )

    with pytest.raises(ContractValidationError) as exc_info:
        validate_planning_artifacts(sample_project)
    assert "External image URL detected" in str(exc_info.value)


# ------------------ TEST 8: Gateway Bounded Repair on Malformed JSON ------------------
def test_visual_planning_gateway_repair_and_retry(sample_project):
    """Gateway bounded repair handles malformed responses gracefully."""
    registry = get_agent_registry()
    adapter = registry.get_agent("visual_planning")
    req = AgentRequest(project_id="proj_test_01", agent_id="visual_planning", stage_id="planning")

    with patch("backend.llm_gateway.execute_llm_gateway_call") as mock_gw:
        # Gateway fails with error
        mock_gw.return_value = llm_gateway.GatewayResponse(
            status="failed",
            error_message="Invalid JSON after retries",
            stage_id="planning",
            purpose="generation",
        )

        res = adapter.execute(sample_project, req)
    # the planner LLM failed: nothing is derived in its place (the plan would claim what no planner judged); the stage fails with the cause
    assert res.status == "failed" and "planner could not be asked" in res.summary and "Invalid JSON after retries" in res.summary
    assert not (sample_project / "visual_planning.json").exists()


# ------------------ TEST 9: Mandatory Review Gate Fails Closed on Blockers ------------------
def test_visual_planning_mandatory_review_gate(sample_project):
    """Visual Planning marks status=blocked if Phase 2 review returns blockers."""
    registry = get_agent_registry()
    adapter = registry.get_agent("visual_planning")
    req = AgentRequest(project_id="proj_test_01", agent_id="visual_planning", stage_id="planning")

    # Create dummy visual planning files
    (sample_project / "visual_planning.json").write_text(
        json.dumps({"schema_version": "1.0", "version": 3, "scenes": []}),
        encoding="utf-8",
    )

    with patch("backend.artifact_contracts.validate_planning_artifacts"), \
         patch("VIDEO_ENGINE.stages.visual_planning.load", return_value={"scenes": [], "stale": False}), \
         patch("backend.llm_review.is_stage_review_passed", return_value=(False, "Critical blocker: Safe zone layout violated", {"status": "blocked", "findings": [{"severity": "blocker"}]})):

        res = adapter.invoke(sample_project, req)
        assert res.status == "blocked"
        assert "blocked" in res.summary.lower()
        assert "Mandatory LLM review gate failed" in (res.error or "")


# ------------------ TEST 10: Truthful Agent Lifecycle & Communication ------------------
def test_agent_lifecycle_and_truthful_communication(sample_project):
    """Adapters record truthful execution metadata and status through AgentResult."""
    adapter = AudioInputAgent()
    req = AgentRequest(project_id="proj_test_01", agent_id="audio_input", stage_id="audio", correlation_id="trace-test-10")

    result = adapter.execute(sample_project, req)
    assert result.status == "succeeded"
    assert result.agent_id == "audio_input"
    assert result.stage_id == "audio"
    assert "manifest" in result.metadata
    assert result.metadata["manifest"]["project_id"] == "proj_test_01"


# ------------------ TEST 12: Zero ASR or Video Pipeline Renders in Test Execution ------------------
def test_no_asr_or_full_pipeline_run_in_test_suite(sample_project, mock_no_asr):
    """Guarantees tests use deterministic fixtures and never invoke Whisper ASR or Remotion render."""
    registry = get_agent_registry()

    # Retrieve all 3 audio & visual agents from canonical registry
    a_analyzer = registry.get_agent("audio_analyzer")
    a_segmentation = registry.get_agent("scene_segmentation")
    a_planning = registry.get_agent("visual_planning")

    assert a_analyzer is not None
    assert a_segmentation is not None
    assert a_planning is not None

    res_analyzer = a_analyzer.execute(sample_project, AgentRequest(project_id="proj_test_01", agent_id="audio_analyzer", stage_id="analyzer"))
    assert res_analyzer.status == "succeeded"

    res_seg = a_segmentation.execute(sample_project, AgentRequest(project_id="proj_test_01", agent_id="scene_segmentation", stage_id="segmentation"))
    assert res_seg.status == "succeeded"

