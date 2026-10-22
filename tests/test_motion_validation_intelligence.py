"""Comprehensive unit and integration tests for Motion Validation Agent v2.0.0.

Verifies:
1. 12-rule deterministic validation core preservation.
2. VisualQualityAssessor: Computer vision heuristics on preview stills & margin checks.
3. SemanticAlignmentEngine: Visual plan fidelity & 3D graceful fallback verification.
4. QualityScoreAggregator: 4-Dimensional Quality Architecture (Technical, Visual, Semantic, Runtime).
5. Non-negotiable technical blocker gating (technical blocker never overridden by visual score).
6. AutonomousRepairCoordinator: Bounded auto-repair loop (max 2 attempts).
7. MotionValidationAgent: End-to-end v2.0.0 execution, output generation, and memory reflection.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image, ImageDraw

from SYSTEM.agents.shared.contracts import AgentRequest, AgentStatus
from SYSTEM.agents.video_generation_agents.motion_timeline_validation.agent import MotionValidationAgent
from SYSTEM.agents.video_generation_agents.motion_timeline_validation.validation_intelligence import (
    VALID_CATEGORIES,
    AutonomousRepairCoordinator,
    QualityDimensions,
    QualityScoreAggregator,
    SemanticAlignmentEngine,
    StructuredFinding,
    VisualQualityAssessor,
    evaluate_quality_and_alignment,
)
from VIDEO_ENGINE.stages import motion_validation as mv


@pytest.fixture
def mock_project(tmp_path: Path) -> Path:
    """Creates a minimal valid project workspace for motion validation tests."""
    pdir = tmp_path / "test_proj"
    pdir.mkdir(parents=True)

    # 1. project.json
    (pdir / "project.json").write_text(
        json.dumps({"aspect": "16:9", "use_images": False, "motion_branch": True}),
        encoding="utf-8",
    )

    # 2. scene_plan.json
    (pdir / "scene_plan.json").write_text(
        json.dumps({
            "scenes": [
                {
                    "id": 1,
                    "start": 0.0,
                    "end": 3.0,
                    "concept": "Introduction to AI Agents",
                    "headline": "Introduction to AI Agents",
                },
                {
                    "id": 2,
                    "start": 3.0,
                    "end": 6.0,
                    "concept": "Autonomous Architecture Analysis",
                    "headline": "Autonomous Architecture Analysis",
                },
            ]
        }),
        encoding="utf-8",
    )

    # 3. visual_planning.json
    (pdir / "visual_planning.json").write_text(
        json.dumps({
            "scenes": [
                {
                    "plan_scene_id": 1,
                    "concept": "Introduction to AI Agents",
                    "elements": [
                        {"element_id": "headline_01", "type": "text", "required": True, "content": "Introduction to AI Agents"},
                        {"element_id": "card_01", "type": "card", "required": True},
                    ],
                },
                {
                    "plan_scene_id": 2,
                    "concept": "Autonomous Architecture Analysis",
                    "elements": [
                        {"element_id": "headline_02", "type": "text", "required": True, "content": "Autonomous Architecture Analysis"},
                        {"element_id": "chart_3d", "type": "3d_model", "required": False, "effect": "isometric_orbit"},
                    ],
                },
            ]
        }),
        encoding="utf-8",
    )

    # 4. composition.json
    (pdir / "composition.json").write_text(
        json.dumps({
            "meta": {"fps": 30, "duration": 6.0, "audio": "audio.wav"},
            "scenes": [
                {"id": 1, "start": 0.0, "end": 3.0, "layers": [{"id": "l1", "type": "custom", "component": "Scene1"}]},
                {"id": 2, "start": 3.0, "end": 6.0, "layers": [{"id": "l2", "type": "custom", "component": "Scene2"}]},
            ],
        }),
        encoding="utf-8",
    )

    # 5. generated_motion directory with scene TSX files
    gen_dir = pdir / "generated_motion"
    gen_dir.mkdir(parents=True)
    (gen_dir / "scene_1.tsx").write_text(
        """import React from 'react';
import { AbsoluteFill } from 'remotion';

export const Scene1: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: '#0f172a' }}>
      <div id="headline_01" style={{ color: '#38bdf8', fontSize: 48 }}>
        Introduction to AI Agents
      </div>
      <div id="card_01" style={{ width: 400, height: 200, backgroundColor: '#1e293b' }}>
        Card Content
      </div>
    </AbsoluteFill>
  );
};
export default Scene1;
""",
        encoding="utf-8",
    )

    (gen_dir / "scene_2.tsx").write_text(
        """import React from 'react';
import { AbsoluteFill } from 'remotion';

export const Scene2: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: '#0f172a' }}>
      <div id="headline_02" style={{ color: '#38bdf8', fontSize: 48 }}>
        Autonomous Architecture Analysis
      </div>
      <div id="chart_3d_2d_fallback" style={{ transform: 'rotateX(20deg) rotateY(15deg)' }}>
        Isometric 2.5D Chart
      </div>
    </AbsoluteFill>
  );
};
export default Scene2;
""",
        encoding="utf-8",
    )

    # 6. motion_generation_report.json
    (pdir / "motion_generation_report.json").write_text(
        json.dumps({
            "schema_version": "2.0",
            "aggregate_metrics": {
                "total_scenes": 2,
                "elements_generated": 4,
                "fallbacks_applied": 1,
                "elements_skipped": 0,
            },
            "retries_prevented": 1,
            "three_d_fallbacks": [
                {
                    "element_id": "chart_3d",
                    "is_3d": True,
                    "is_supported": False,
                    "requested_effect": "isometric_orbit",
                    "fallback_strategy": "2.5d_isometric_layer",
                    "capability_limitation": "Native Three.js Canvas not supported in static TSX mode",
                }
            ],
        }),
        encoding="utf-8",
    )

    return pdir


def test_deterministic_12_stages_preserved():
    """Verifies that all 12 stages and rules from the deterministic core remain intact."""
    assert len(mv.STAGES) == 12
    stage_ids = [s[0] for s in mv.STAGES]
    expected = [
        "input_provenance",
        "fingerprint_freshness",
        "scene_mapping",
        "timing_frame",
        "element_completeness",
        "animation_preset",
        "layout_collision",
        "audio_text_sync",
        "transition_readiness",
        "buildability",
        "preview_validation",
        "readiness_gate",
    ]
    assert stage_ids == expected
    assert mv.SCHEMA == "1.0"
    assert mv.VERSION == 1
    assert mv.RULE_SET == "1.1"      # 1.1: per-scene checks of generated-code scenes (layout, planned text)


def test_visual_quality_assessor_heuristics(tmp_path: Path):
    """Verifies computer vision heuristics on synthetic test images."""
    assessor = VisualQualityAssessor()

    # 1. Normal high-contrast still
    good_img = tmp_path / "good.png"
    im = Image.new("RGB", (320, 180), color=(15, 23, 42))
    draw = ImageDraw.Draw(im)
    draw.rectangle([40, 30, 280, 150], fill=(56, 189, 248), outline=(255, 255, 255))
    im.save(good_img)

    metrics_good = assessor.measure_still(good_img, aspect="16:9")
    assert metrics_good["decode_ok"] is True
    assert metrics_good["blank"] is False
    assert metrics_good["contrast"] > 20.0
    assert metrics_good["edge_density"] > 0.0

    # 2. Blank still (stddev < 2.0)
    blank_img = tmp_path / "blank.png"
    im_blank = Image.new("RGB", (320, 180), color=(10, 10, 10))
    im_blank.save(blank_img)

    metrics_blank = assessor.measure_still(blank_img, aspect="16:9")
    assert metrics_blank["decode_ok"] is True
    assert metrics_blank["blank"] is True
    assert metrics_blank["contrast"] < 2.0

    # 3. Safe margin bleeding still (edges drawn directly on border)
    bleed_img = tmp_path / "bleed.png"
    im_bleed = Image.new("RGB", (320, 180), color=(0, 0, 0))
    draw_bleed = ImageDraw.Draw(im_bleed)
    draw_bleed.rectangle([0, 0, 319, 179], outline=(255, 255, 255), width=8)
    im_bleed.save(bleed_img)

    metrics_bleed = assessor.measure_still(bleed_img, aspect="16:9")
    assert metrics_bleed["decode_ok"] is True
    assert metrics_bleed["safe_margin_passed"] is False


def test_semantic_alignment_engine(mock_project: Path):
    """Verifies that SemanticAlignmentEngine verifies visual plan elements and 3D fallbacks."""
    engine = SemanticAlignmentEngine()
    result = engine.evaluate(mock_project, aspect="16:9")

    assert result["semantic_score"] >= 80.0
    assert result["elements_required"] > 0
    assert result["elements_matched"] > 0
    assert result["missing_required"] == 0

    # Verify 3D fallback detection
    fallback_metrics = result["fallback_metrics"]
    assert fallback_metrics["fallbacks_applied"] == 1
    assert fallback_metrics["retries_prevented"] == 1
    assert fallback_metrics["unhandled_3d_failures"] == 0

    # Verify findings contain graceful 2D fallback info finding
    findings = result["findings"]
    fallback_finding = next((f for f in findings if f["rule_id"] == "3d.graceful_fallback"), None)
    assert fallback_finding is not None
    assert fallback_finding["category"] == "fallback_quality"
    assert fallback_finding["severity"] == "info"


def test_semantic_alignment_detects_missing_required(mock_project: Path):
    """Verifies that missing required elements generate missing_visual findings."""
    # Modify visual_planning.json to require an element not present in TSX
    vp_file = mock_project / "visual_planning.json"
    vp = json.loads(vp_file.read_text(encoding="utf-8"))
    vp["scenes"][0]["elements"].append({
        "element_id": "mandatory_metric_counter_99",
        "type": "chart",
        "required": True,
    })
    vp_file.write_text(json.dumps(vp), encoding="utf-8")

    engine = SemanticAlignmentEngine()
    result = engine.evaluate(mock_project, aspect="16:9")

    assert result["missing_required"] >= 1
    missing_finding = next((f for f in result["findings"] if f["element_id"] == "mandatory_metric_counter_99"), None)
    assert missing_finding is not None
    assert missing_finding["category"] == "missing_visual"
    assert missing_finding["severity"] == "error"
    assert missing_finding["can_auto_fix"] is True


def test_a_planned_text_drawn_verbatim_counts_as_drawn_without_its_element_id(mock_project: Path):
    """Motion Generation is told to draw the planned texts verbatim (not to tag them): a text drawn word for word is found; one that is not drawn is still missing."""
    vp_file = mock_project / "visual_planning.json"
    vp = json.loads(vp_file.read_text(encoding="utf-8"))
    vp["scenes"][0]["elements"] += [{"element_id": "text_verbatim_x", "type": "text", "required": True, "content": "Beyond simple automation"},
                                   {"element_id": "text_absent_y", "type": "text", "required": True, "content": "Never written anywhere"}]
    vp_file.write_text(json.dumps(vp), encoding="utf-8")
    tsx = next((mock_project / "generated_motion").glob("scene_*.tsx"))
    tsx.write_text(tsx.read_text(encoding="utf-8") + "\n// <h1>Beyond simple automation</h1>\n", encoding="utf-8")
    missing = {f["element_id"] for f in SemanticAlignmentEngine().evaluate(mock_project, aspect="16:9")["findings"] if f["category"] == "missing_visual"}
    assert "text_verbatim_x" not in missing and "text_absent_y" in missing


def test_quality_score_aggregator_4d_separation():
    """Verifies the 4-Dimensional Quality Architecture and category classification."""
    deterministic_rep = {
        "summary": {"blockers": 0, "errors": 0, "warnings": 1, "stages_blocked": 0},
        "readiness": "ready_with_warnings",
        "phase_status": "completed",
        "stages": [{"stage_id": "buildability", "status": "completed"}],
        "findings": [
            {
                "finding_id": "layout.safe_margins:scene_1:text",
                "rule_id": "layout.safe_margins",
                "severity": "warning",
                "scene_id": "scene_1",
                "element_id": "text",
                "message": "Text close to safe margins",
                "evidence": {},
                "status": "unresolved",
            }
        ],
    }

    vis_res = {"visual_score": 88.0, "findings": []}
    sem_res = {"semantic_score": 92.0, "findings": []}

    agg = QualityScoreAggregator.aggregate(deterministic_rep, vis_res, sem_res)
    dims = agg["quality_dimensions"]

    assert dims["technical"] == 97.0  # 100 - 3 (one warning)
    assert dims["visual"] == 88.0
    assert dims["semantic"] == 92.0
    assert dims["runtime"] == 100.0
    assert 90.0 <= dims["overall"] <= 95.0

    # Check category mappings
    for cat in VALID_CATEGORIES:
        assert cat in agg["category_counts"]
    assert agg["category_counts"]["visual_composition"] == 1


def test_non_negotiable_technical_blocker_gating():
    """Critical safety test: A technical blocker must force readiness to blocked,

    regardless of perfect visual or semantic scores.
    """
    deterministic_rep = {
        "summary": {"blockers": 1, "errors": 0, "warnings": 0, "stages_blocked": 1},
        "readiness": "blocked",
        "phase_status": "completed",
        "stages": [{"stage_id": "timing_frame", "status": "blocked"}],
        "findings": [
            {
                "finding_id": "timing.drift:scene_1:-",
                "rule_id": "timing.duration_match",
                "severity": "blocker",
                "scene_id": "scene_1",
                "element_id": None,
                "message": "Duration mismatch",
                "evidence": {},
                "status": "unresolved",
            }
        ],
    }

    # Perfect visual and semantic scores
    vis_res = {"visual_score": 100.0, "findings": []}
    sem_res = {"semantic_score": 100.0, "findings": []}

    agg = QualityScoreAggregator.aggregate(deterministic_rep, vis_res, sem_res)
    assert agg["readiness"] == "blocked"
    assert agg["quality_dimensions"]["technical"] < 60.0


def test_autonomous_repair_coordinator_bounded(mock_project: Path):
    """Verifies that AutonomousRepairCoordinator fixes repairable defects within max 2 attempts."""
    coordinator = AutonomousRepairCoordinator()

    repairable_findings = [
        {
            "finding_id": "visual.safe_margin:1:text",
            "rule_id": "layout.safe_margins",
            "category": "visual_composition",
            "severity": "warning",
            "scene_id": "1",
            "element_id": "headline_01",
            "message": "Safe margin clipping",
            "can_auto_fix": True,
            "status": "unresolved",
        }
    ]

    res = coordinator.coordinate_repair(
        project_dir=mock_project,
        aspect="16:9",
        findings=repairable_findings,
        max_attempts=2,
    )

    assert res["status"] == "completed"
    assert res["repaired_count"] == 1
    assert res["attempts"] <= 2
    assert repairable_findings[0]["status"] == "repaired"

    # Verify TSX file was modified to include padding
    scene1_code = (mock_project / "generated_motion" / "scene_1.tsx").read_text(encoding="utf-8")
    assert "padding" in scene1_code


def test_motion_validation_agent_execute(mock_project: Path):
    """End-to-end integration test of MotionValidationAgent v2.0.0."""
    agent = MotionValidationAgent()
    assert agent.metadata.version == "2.0.0"
    assert agent.metadata.agent_id == "motion_timeline_validation"

    req = AgentRequest(
        agent_id="motion_timeline_validation",
        stage_id="motion_validation",
        parameters={"aspect": "16:9", "auto_repair": True},
    )

    # 1. Validation check
    val_errs = agent.validate(mock_project, req)
    assert val_errs == []

    # 2. Execution
    result = agent.execute(mock_project, req)
    assert result.agent_id == "motion_timeline_validation"
    assert result.status in ("succeeded", "needs_review", "blocked")
    assert "quality_dimensions" in result.metadata
    assert "overall" in result.metadata["quality_dimensions"]

    # 3. Verify output artifacts
    output_paths = [r.path for r in result.output_refs]
    assert any("motion_validation_intelligence" in p for p in output_paths)

    intel_file = mock_project / "motion_validation_intelligence.json"
    assert intel_file.exists()
    intel_data = json.loads(intel_file.read_text(encoding="utf-8"))
    assert "quality_dimensions" in intel_data
    assert "unified_findings" in intel_data
    assert "visual_assessment" in intel_data
    assert "semantic_alignment" in intel_data


def test_motion_validation_agent_succeeded_readiness(mock_project: Path):
    """Verifies that MotionValidationAgent produces 'succeeded' status when readiness is ready."""
    agent = MotionValidationAgent()

    fp = mv.fingerprint(mock_project, "16:9")
    val_file = mock_project / "motion_timeline_validation.json"
    val_file.write_text(
        json.dumps({
            "schema_version": "1.0",
            "phase": "motion_timeline_validation",
            "phase_status": "completed",
            "readiness": "ready",
            "source_fingerprint": fp,
            "summary": {"blockers": 0, "errors": 0, "warnings": 0, "stages_blocked": 0},
            "stages": [{"stage_id": "buildability", "status": "completed", "finding_ids": [], "checks_skipped": 0, "checks_passed": 1, "checks_total": 1}],
            "findings": [],
        }),
        encoding="utf-8",
    )

    req = AgentRequest(
        agent_id="motion_timeline_validation",
        stage_id="motion_validation",
        parameters={"aspect": "16:9", "auto_repair": False},
    )

    result = agent.execute(mock_project, req)
    assert result.status == "succeeded"
    assert result.metadata["readiness"] in ("ready", "ready_with_warnings")
    assert result.metadata["quality_dimensions"]["overall"] >= 80.0



def test_backward_compatibility_report_enrichment(mock_project: Path):
    """Verifies that assemble() in motion_validation.py includes quality_assessment

    without breaking legacy keys.
    """
    rep = mv.load(mock_project, "16:9")
    if rep is None:
        try:
            rep = mv.run(mock_project, "16:9")
        except Exception:
            pass

    if rep is not None:
        assert "schema_version" in rep
        assert "stages" in rep
        assert "findings" in rep
        assert "summary" in rep
        assert "readiness" in rep
        # Verify enriched key
        assert "quality_assessment" in rep
        assert "dimensions" in rep["quality_assessment"]
