"""Comprehensive test suite for Motion Animation Agent v2.0.0 and Animation Intelligence Subsystem.
Verifies:
1. 3D Graceful Fallback Engine (supported vs unsupported 3D classification and approximation).
2. Element skipping for unapproximable elements without failing the scene or pipeline.
3. Retry Storm Prevention on known capability limitations (Three.js, WebGL shaders).
4. Visual Preview Verification (safe-area margins, typography hierarchy, contrast).
5. Structured generation reporting (motion_generation_report.json schema and metrics).
6. Failure isolation across multiple scenes.
7. MotionAnimationAgent v2.0.0 execution, artifacts, and memory reflection.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

pytestmark = pytest.mark.usefixtures("llm_codegen_stub")

from SYSTEM.agents.shared.contracts import AgentMetadata, AgentRequest, AgentResult
from SYSTEM.agents.video_generation_agents.motion_animation.agent import (
    MotionAnimationAdapter,
    MotionAnimationAgent,
)
from SYSTEM.agents.video_generation_agents.motion_animation.animation_intelligence import (
    StructuredGenerationReporter,
    ThreeDFallbackEngine,
    VisualPreviewVerifier,
)
from VIDEO_ENGINE.stages import motion_animation


def test_threed_fallback_engine_classification():
    """Verify that native/simple 3D is supported while complex 3D is classified as unsupported with fallbacks."""
    engine = ThreeDFallbackEngine()

    # 1. Native / Simple Remotion 3D
    simple_el = {
        "element_id": "card_1",
        "type": "perspective_card",
        "visual_description": "Card flip with perspective transform",
    }
    cls_simple = engine.classify_element(simple_el)
    assert cls_simple.is_3d is True
    assert cls_simple.is_supported is True
    assert cls_simple.fallback_strategy == "native"
    assert cls_simple.retry_prevented is False

    # 2. Complex Three.js / WebGL 3D
    complex_el = {
        "element_id": "vortex_1",
        "type": "webgl_shader",
        "visual_description": "Three.js volumetric particle vortex in 3D space",
    }
    cls_complex = engine.classify_element(complex_el)
    assert cls_complex.is_3d is True
    assert cls_complex.is_supported is False
    assert cls_complex.fallback_strategy == "2d_particles"
    assert cls_complex.retry_prevented is True
    assert "threejs" in cls_complex.capability_limitation or "webgl" in cls_complex.capability_limitation

    # 3. GLTF 3D Mesh
    mesh_el = {
        "element_id": "model_1",
        "type": "3d_model",
        "visual_description": "GLTF 3D animated character mesh",
    }
    cls_mesh = engine.classify_element(mesh_el)
    assert cls_mesh.is_3d is True
    assert cls_mesh.is_supported is False
    assert cls_mesh.fallback_strategy == "svg_isometric"

    # 4. Explicitly unapproximable 3D element
    unapprox_el = {
        "element_id": "unapprox_1",
        "type": "raymarching_volumetric",
        "visual_description": "Unapproximable real-time raymarched fractal fog",
        "unapproximable": True,
    }
    cls_unapprox = engine.classify_element(unapprox_el)
    assert cls_unapprox.is_3d is True
    assert cls_unapprox.is_supported is False
    assert cls_unapprox.fallback_strategy == "skip"
    assert cls_unapprox.retry_prevented is True


def test_threed_fallback_transformation_and_skipping():
    """Verify element transformation approximates unsupported 3D and gracefully skips unapproximable ones."""
    engine = ThreeDFallbackEngine()

    raw_elements = [
        {"element_id": "el_2d", "type": "chart", "visual_description": "2D bar chart"},
        {"element_id": "el_vortex", "type": "threejs", "visual_description": "3D particle vortex"},
        {"element_id": "el_mesh", "type": "mesh", "visual_description": "3D GLTF robot mesh"},
        {"element_id": "el_skip", "type": "raymarching", "unapproximable": True},
    ]

    transformed, classifications = engine.transform_elements_for_codegen(raw_elements)

    assert len(classifications) == 4
    # The unapproximable element should be skipped from transformed list
    assert len(transformed) == 3

    # Check 2D element untouched
    assert transformed[0]["element_id"] == "el_2d"
    assert transformed[0]["type"] == "chart"

    # Check particle approximation
    assert transformed[1]["element_id"] == "el_vortex"
    assert transformed[1]["fallback_applied"] is True
    assert transformed[1]["fallback_strategy"] == "2d_particles"
    assert transformed[1]["type"] == "particle_field_2d"

    # Check isometric approximation
    assert transformed[2]["element_id"] == "el_mesh"
    assert transformed[2]["fallback_applied"] is True
    assert transformed[2]["fallback_strategy"] == "svg_isometric"


def test_retry_prevention_on_capability_limitations():
    """Verify known capability limitations are detected to abort wasteful LLM retry loops."""
    engine = ThreeDFallbackEngine()

    # Known limitation errors
    assert engine.is_known_limitation_error("Error: Cannot find module 'three'") is True
    assert engine.is_known_limitation_error("Error: Cannot find module '@react-three/fiber'") is True
    assert engine.is_known_limitation_error("WebGLRenderingContext is not supported in SSR environment") is True
    assert engine.is_known_limitation_error("Failed to compile shader program") is True

    # Standard fixable syntax errors should NOT trigger retry prevention
    assert engine.is_known_limitation_error("SyntaxError: Unexpected token '}'") is False
    assert engine.is_known_limitation_error("TypeError: Cannot read properties of undefined") is False


def test_visual_preview_verifier():
    """Verify lightweight static layout, safe-area margin, typography, and contrast verification."""
    verifier = VisualPreviewVerifier()

    # Passing code
    good_code = """
    import React from "react";
    import { AbsoluteFill } from "remotion";
    export const Scene1 = () => (
      <AbsoluteFill style={{
        padding: "8%",
        justifyContent: "center",
        alignItems: "center",
        background: "radial-gradient(#1e293b, #0f172a)",
        color: "#f8fafc",
      }}>
        <div style={{ fontSize: 56, fontWeight: 800, textShadow: "0 4px 10px rgba(0,0,0,0.5)" }}>
          Valid Cinematic Headline
        </div>
        <div style={{ fontSize: 28, color: "#38bdf8" }}>
          Valid Subtext
        </div>
      </AbsoluteFill>
    );
    """
    res = verifier.verify(good_code)
    assert res.passed is True
    assert res.score >= 0.8
    assert res.safe_zone_passed is True
    assert res.typography_passed is True
    assert res.contrast_passed is True

    # Code violating safe zone and typography
    bad_code = """
    export const Scene2 = () => (
      <div>
        <span style={{ fontSize: 18 }}>Too Small Text</span>
      </div>
    );
    """
    res_bad = verifier.verify(bad_bad_code := bad_code)
    assert res_bad.passed is False
    assert res_bad.score < 0.8
    assert res_bad.safe_zone_passed is False
    assert res_bad.typography_passed is False


def test_structured_generation_reporter(tmp_path: Path):
    """Verify motion_generation_report.json schema, element statuses, and persistence."""
    reporter = StructuredGenerationReporter()

    scenes_data = [
        {
            "scene_id": 1,
            "element_classifications": [
                {
                    "element_id": "txt_1",
                    "requested_effect": "text",
                    "is_3d": False,
                    "is_supported": True,
                    "fallback_strategy": "native",
                },
                {
                    "element_id": "mesh_1",
                    "requested_effect": "3d_model",
                    "is_3d": True,
                    "is_supported": False,
                    "fallback_strategy": "svg_isometric",
                    "capability_limitation": "gltf_pipeline_unconfigured",
                },
                {
                    "element_id": "skip_1",
                    "requested_effect": "raymarching",
                    "is_3d": True,
                    "is_supported": False,
                    "fallback_strategy": "skip",
                    "capability_limitation": "hardware_unsupported",
                },
            ],
            "preview_result": {"passed": True, "score": 1.0},
            "compile_status": "passed",
            "repair_attempts": 1,
        }
    ]

    report = reporter.build_report(
        project_id="test_proj",
        aspect="16:9",
        scenes_data=scenes_data,
        overall_compile_status="passed",
        retries_prevented_total=1,
    )

    assert report["schema_version"] == "2.0.0"
    assert report["status"] == "completed"
    assert report["retries_prevented"] == 1
    assert report["aggregate_metrics"]["total_elements"] == 3
    assert report["aggregate_metrics"]["elements_generated"] == 1
    assert report["aggregate_metrics"]["fallbacks_applied"] == 1
    assert report["aggregate_metrics"]["elements_skipped"] == 1
    assert report["aggregate_metrics"]["downstream_readiness_pct"] == 100.0

    p = reporter.save_report(tmp_path, "16:9", report)
    assert p.exists()
    loaded = json.loads(p.read_text(encoding="utf-8"))
    assert loaded["aggregate_metrics"]["fallbacks_applied"] == 1


def test_failure_isolation_multi_scene_generation(tmp_path: Path):
    """Verify an unsupported or unapproximable element in one scene does NOT fail the entire video pipeline."""
    pdir = tmp_path / "proj_iso"
    pdir.mkdir(parents=True, exist_ok=True)

    # 3 Scenes: Scene 1 standard 2D, Scene 2 complex 3D (approximated), Scene 3 unapproximable 3D (skipped)
    (pdir / "project.json").write_text(json.dumps({"id": "proj_iso", "aspect": "16:9"}), encoding="utf-8")
    (pdir / "scene_plan.json").write_text(
        json.dumps({
            "scenes": [
                {"id": 1, "start": 0.0, "end": 2.0, "concept": "Scene 1 - Standard 2D"},
                {"id": 2, "start": 2.0, "end": 4.0, "concept": "Scene 2 - Complex 3D particle vortex"},
                {"id": 3, "start": 4.0, "end": 6.0, "concept": "Scene 3 - Unapproximable raymarching"},
            ],
            "style": {"palette": ["#0f172a", "#38bdf8", "#818cf8"]},
        }),
        encoding="utf-8",
    )
    (pdir / "visual_planning.json").write_text(
        json.dumps({
            "scenes": [
                {
                    "scene_id": 1,
                    "elements": [
                        {"element_id": "txt_1", "type": "text", "content": "Scene 1 Title", "required": True},
                    ],
                },
                {
                    "scene_id": 2,
                    "elements": [
                        {"element_id": "txt_2", "type": "text", "content": "Scene 2 Title", "required": True},
                        {"element_id": "vortex_3d", "type": "threejs", "visual_description": "Particle vortex", "required": False},
                    ],
                },
                {
                    "scene_id": 3,
                    "elements": [
                        {"element_id": "txt_3", "type": "text", "content": "Scene 3 Title", "required": True},
                        {"element_id": "skip_3d", "type": "raymarching", "visual_description": "Unapproximable", "unapproximable": True, "required": False},
                    ],
                },
            ]
        }),
        encoding="utf-8",
    )
    (pdir / "motion_plan.json").write_text(
        json.dumps({
            "scenes": [
                {"plan_scene_id": 1, "timing": {"start": 0.0, "end": 2.0}},
                {"plan_scene_id": 2, "timing": {"start": 2.0, "end": 4.0}},
                {"plan_scene_id": 3, "timing": {"start": 4.0, "end": 6.0}},
            ]
        }),
        encoding="utf-8",
    )

    manifest = motion_animation.generate_custom_motion_code(pdir, aspect="16:9")

    assert manifest["status"] == "generated"
    assert len(manifest["scenes"]) == 3

    # Verify all 3 TSX files were produced
    gen_dir = pdir / "generated_motion"
    assert (gen_dir / "scene_1.tsx").exists()
    assert (gen_dir / "scene_2.tsx").exists()
    assert (gen_dir / "scene_3.tsx").exists()

    # Verify scene 2 TSX contains particle fallback code
    sc2_code = (gen_dir / "scene_2.tsx").read_text(encoding="utf-8")
    assert "Particle Drift" in sc2_code or "particle" in sc2_code.lower()

    # Verify motion_generation_report.json
    rep_file = pdir / "motion_generation_report.json"
    assert rep_file.exists()
    rep = json.loads(rep_file.read_text(encoding="utf-8"))
    assert rep["aggregate_metrics"]["total_scenes"] == 3
    assert rep["aggregate_metrics"]["fallbacks_applied"] >= 1
    assert rep["aggregate_metrics"]["elements_skipped"] >= 1
    assert rep["aggregate_metrics"]["downstream_readiness_pct"] == 100.0


def test_motion_animation_agent_v2_execution(tmp_path: Path, monkeypatch):
    """Verify MotionAnimationAgent v2.0.0 lifecycle, validation, execution, and memory reflection. The hand-made project has no checked motion plan, so the
    canonical motion-build step (which refuses such a plan: tests/test_motion_codegen.py) is stood in for by its code generation and report."""
    from VIDEO_ENGINE.pipeline import legacy_pipeline_adapter
    from VIDEO_ENGINE.stages import motion_animation

    def build_step(project_dir, name, ctx):
        motion_animation.generate_custom_motion_code(project_dir, "16:9")      # writes the scenes, composition.json and motion_generation_report.json
    monkeypatch.setattr(legacy_pipeline_adapter, "execute", build_step)
    pdir = tmp_path / "proj_agent_v2"
    pdir.mkdir(parents=True, exist_ok=True)

    (pdir / "project.json").write_text(json.dumps({"id": "proj_agent_v2", "aspect": "16:9"}), encoding="utf-8")
    (pdir / "scene_plan.json").write_text(
        json.dumps({
            "scenes": [{"id": 1, "start": 0.0, "end": 3.0, "concept": "Test Agent V2"}],
            "style": {"palette": ["#0f172a", "#38bdf8", "#818cf8"]},
        }),
        encoding="utf-8",
    )
    (pdir / "visual_planning.json").write_text(
        json.dumps({
            "scenes": [
                {
                    "scene_id": 1,
                    "elements": [
                        {"element_id": "txt_1", "type": "text", "content": "Agent V2 Test", "required": True},
                        {"element_id": "3d_globe", "type": "3d_model", "visual_description": "Spinning 3D wireframe globe", "required": False},
                    ],
                }
            ]
        }),
        encoding="utf-8",
    )
    (pdir / "motion_plan.json").write_text(
        json.dumps({"scenes": [{"plan_scene_id": 1, "timing": {"start": 0.0, "end": 3.0}}]}),
        encoding="utf-8",
    )

    agent = MotionAnimationAgent()
    assert agent.metadata.version == "2.0.0"

    req = AgentRequest(agent_id="motion_animation", stage_id="motion_gen", project_id=pdir.name, parameters={"aspect": "16:9"})
    validation_errors = agent.validate(pdir, req)
    assert len(validation_errors) == 0

    result = agent.execute(pdir, req)
    assert result.status == "succeeded"
    assert result.error is None
    assert any("motion_generation_report.json" in r.path for r in result.output_refs)
    assert any("scene_1.tsx" in r.path for r in result.output_refs)
    assert any("composition.json" in r.path for r in result.output_refs)

    # Verify memory reflection and experience recording
    experiences = agent.memory.retrieve_experiences(task_type="motion_animation_codegen")
    assert len(experiences) >= 1
    assert experiences[0]["outcome"] == "succeeded"
    assert experiences[0]["metrics"]["downstream_readiness_pct"] == 100.0
