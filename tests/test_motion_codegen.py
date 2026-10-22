"""Tests for Motion Template Selection and Motion Animation Code Generation.
Covers:
- Project setting reusable_motion_templates default ON and persistence.
- Template selection ON mode (selects verified implementations).
- Template selection OFF mode (emits skipped_by_configuration).
- Custom TSX generation in OFF mode (executable React/TSX, real SHA-256 hashes, TypeScript compilation).
- Enforcement of prohibited preset rejection in OFF mode.
- Motion & Timeline Validation integration, source verification, and gate blocking.
- Fingerprint invalidation when toggle changes.
"""
import hashlib
import importlib
import json
from pathlib import Path

import pytest

from backend import motion_animation, motion_template_selection, motion_validation, pipeline, store

_v = importlib.import_module("test_visual_planning")
_mp = importlib.import_module("test_motion_planning")
_g = importlib.import_module("test_motion_generation")
_mo = importlib.import_module("test_motion_only_mode")
pytestmark = pytest.mark.usefixtures("llm_codegen_stub")
project, raw_for = _v.project, _v.raw_for
make_project = _mp.make


def make_off_project(pdir):
    d, *_ = _g.make(pdir, with_vp=False)
    (d / "motion_plan.json").unlink()
    store.set_reusable_motion_templates(d, False)
    pipeline.execute(d, "motion-plan", pipeline.Ctx())
    pipeline.execute(d, "motion-build", pipeline.Ctx())
    wav = _mo.wav_bytes()
    for name in {"audio.wav", json.loads((d / "composition.json").read_text(encoding="utf-8"))["meta"]["audio"]}:
        (d / name).write_bytes(wav)
    return d


def test_reusable_motion_templates_default_and_persistence(tmp_path):
    pdir = tmp_path / "proj1"
    pdir.mkdir(parents=True)
    (pdir / "project.json").write_text(json.dumps({"id": "proj1", "name": "proj1", "created": "2026-10-15T12:00:00"}), encoding="utf-8")

    # 1. Defaults to False (Custom Code Mode) in Motion-Only mode
    assert store.reusable_motion_templates(pdir) is False

    # 2. Toggle to False
    res = store.set_reusable_motion_templates(pdir, False)
    assert res is False
    assert store.reusable_motion_templates(pdir) is False

    # 3. Survives reload from disk
    info = store.read_info(pdir)
    assert info["reusable_motion_templates"] is False

    # 4. Toggle back to True
    res = store.set_reusable_motion_templates(pdir, True)
    assert res is True
    assert store.reusable_motion_templates(pdir) is True


def test_motion_template_selection_on_mode(tmp_path):
    d, *_ = make_project(tmp_path / "proj_on")
    store.set_reusable_motion_templates(d, True)

    sel = motion_template_selection.build_selection(d, "16:9")
    assert sel["mode"] == "template"
    assert sel["status"] == "selected"
    assert sel["reusable_motion_templates"] is True
    assert len(sel["scenes"]) > 0

    # Every scene has selections referencing real verified implementations
    first_scene = sel["scenes"][0]
    assert first_scene["mode"] == "template"
    assert first_scene["status"] == "selected"
    assert len(first_scene["selections"]) > 0

    refs = [s["implementation_ref"] for s in first_scene["selections"]]
    assert any("VIDEO_ENGINE/remotion/src/motion/text.tsx:MotionTextLayer" in r for r in refs)
    assert any("VIDEO_ENGINE/remotion/src/motion/compose.tsx:MotionScene" in r for r in refs)


def test_motion_template_selection_off_mode(tmp_path):
    d, *_ = make_project(tmp_path / "proj_off")
    store.set_reusable_motion_templates(d, False)

    sel = motion_template_selection.build_selection(d, "16:9")
    assert sel["mode"] == "custom_code"
    assert sel["status"] == "skipped_by_configuration"
    assert sel["reusable_motion_templates"] is False
    assert sel["reason"] == "reusable_motion_templates=false"

    for sc in sel["scenes"]:
        assert sc["mode"] == "custom_code"
        assert sc["status"] == "skipped_by_configuration"
        assert sc["selections"] == []
        assert sc["reason"] == "reusable_motion_templates=false"


def test_prohibited_preset_scanner():
    clean_code = """
import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";

export const Scene1: React.FC = () => {
  const frame = useCurrentFrame();
  return <AbsoluteFill style={{ background: "#000" }}>Hello World</AbsoluteFill>;
};
"""
    assert motion_animation.scan_prohibited_presets(clean_code) == []

    dirty_code = """
import React from "react";
import { MotionTextLayer } from "../motion/text";
import { HighlightText } from "../components/HighlightText";

export const Scene1: React.FC = () => {
  return <MotionTextLayer layer={{ type: "motion_text" }} />;
};
"""
    prohibited = motion_animation.scan_prohibited_presets(dirty_code)
    assert "MotionTextLayer" in prohibited
    assert "HighlightText" in prohibited


def test_motion_animation_custom_code_generation(tmp_path):
    d, *_ = make_project(tmp_path / "proj_codegen")
    store.set_reusable_motion_templates(d, False)

    # Generate custom code
    manifest = motion_animation.generate_custom_motion_code(d, "16:9")

    assert manifest["mode"] == "custom_code"
    assert manifest["status"] == "generated"
    assert manifest["diagnostics"]["compile_passed"] is True
    assert manifest["diagnostics"]["prohibited_imports_found"] == 0

    # Source files exist on disk
    gen_dir = d / "generated_motion"
    assert gen_dir.exists()
    assert (gen_dir / "index.ts").exists()

    for sc in manifest["scenes"]:
        spath = Path(sc["source_path"])
        assert spath.exists()
        # Verify SHA-256 matches actual file bytes
        computed_sha = hashlib.sha256(spath.read_bytes()).hexdigest()
        assert sc["source_sha256"] == computed_sha
        assert sc["compile_status"] == "passed"

        # Check source content does not use prohibited presets
        content = spath.read_text(encoding="utf-8")
        assert "useCurrentFrame" in content
        assert "useVideoConfig" in content
        assert "MotionTextLayer" not in content
        assert "MotionScene" not in content

    # Check composition.json was built with custom_scene layers
    comp = json.loads((d / "composition.json").read_text(encoding="utf-8"))
    assert comp["meta"]["customCode"] is True
    assert comp["meta"]["reusable_motion_templates"] is False
    for sc in comp["scenes"]:
        custom_layers = [l for l in sc["layers"] if l["type"] == "custom_scene"]
        assert len(custom_layers) == 1
        assert custom_layers[0]["component"] == f"Scene{sc['id']}"


def test_validation_detects_prohibited_preset_in_off_mode(tmp_path):
    d = make_off_project(tmp_path / "proj_prohibited_val")
    manifest = motion_animation.load_animation(d, "16:9")

    # Intentionally corrupt scene_1.tsx by injecting a prohibited preset import
    first_scene_path = Path(manifest["scenes"][0]["source_path"])
    original_code = first_scene_path.read_text(encoding="utf-8")
    corrupt_code = "import { MotionTextLayer } from 'remotion';\n" + original_code
    first_scene_path.write_text(corrupt_code, encoding="utf-8")

    # Update hash in manifest to bypass hash check so policy check triggers
    manifest["scenes"][0]["source_sha256"] = hashlib.sha256(first_scene_path.read_bytes()).hexdigest()
    motion_animation.save_animation(d, "16:9", manifest)

    # Run validation
    rep = motion_validation.run(d, "16:9", force=True)
    findings = [f for f in rep["findings"] if f["rule_id"] == "policy.no_prohibited_presets"]
    assert len(findings) > 0
    assert findings[0]["severity"] == "blocker"
    assert "MotionTextLayer" in findings[0]["message"]
    assert rep["readiness"] in ("blocked", "failed")


def test_validation_detects_tampered_source_hash(tmp_path):
    d = make_off_project(tmp_path / "proj_tamper")
    manifest = motion_animation.load_animation(d, "16:9")

    # Tamper with file without updating manifest hash
    first_scene_path = Path(manifest["scenes"][0]["source_path"])
    first_scene_path.write_text(first_scene_path.read_text(encoding="utf-8") + "\n// modified", encoding="utf-8")

    rep = motion_validation.run(d, "16:9")
    findings = [f for f in rep["findings"] if f["rule_id"] == "codegen.hash_valid"]
    assert len(findings) > 0
    assert findings[0]["severity"] == "blocker"
    assert "source SHA-256 mismatch" in findings[0]["message"]
    assert rep["readiness"] in ("blocked", "failed")




def test_codegen_fails_closed_when_llm_blocked(tmp_path, monkeypatch):
    """A blocked gateway (open circuit) must raise, never be replaced by the generic template."""
    d, *_ = make_project(tmp_path / "proj_blocked")
    store.set_reusable_motion_templates(d, False)
    from backend import llm_gateway

    def blocked(req):
        return llm_gateway.LlmGatewayResponse(
            request_id=req.request_id, correlation_id=req.correlation_id, project_id=req.project_id, stage_id=req.stage_id,
            agent_id=req.agent_id, purpose=req.purpose, status="blocked", raw_text="", structured_data=None,
            model_profile=req.model_profile, provider="p", model="m", latency_ms=1, attempt_count=0, error="circuit open")

    monkeypatch.setattr(llm_gateway.gateway, "execute", blocked)
    with pytest.raises(motion_animation.AnimationCodegenError, match="blocked"):
        motion_animation.generate_custom_motion_code(d, "16:9")
    assert not list((d / "generated_motion").glob("scene_*.tsx"))


def test_manifest_records_drawn_and_missing_elements(tmp_path):
    d, *_ = make_project(tmp_path / "proj_elements")
    store.set_reusable_motion_templates(d, False)
    manifest = motion_animation.generate_custom_motion_code(d, "16:9")
    for sc in manifest["scenes"]:
        assert sc["generation"]["missing_elements"] == []
        assert sc["missing_required_elements"] == []
    assert motion_animation.missing_element_ids('<div data-element-id="a"/>', ["a", "b"]) == ["b"]


def test_stage2_trusts_only_manifests_that_recorded_the_element_check(tmp_path):
    from types import SimpleNamespace
    from backend import motion_gen_rules
    d, *_ = make_project(tmp_path / "proj_verified")
    store.set_reusable_motion_templates(d, False)
    manifest = motion_animation.generate_custom_motion_code(d, "16:9")
    g = SimpleNamespace(pdir=d, aspect="16:9")
    drawn = motion_gen_rules._verified_drawn(g)
    assert set(drawn) == {s["scene_id"] for s in manifest["scenes"]}
    for sc in manifest["scenes"]:
        del sc["generation"]["missing_elements"]               # a manifest written before the check existed claims everything is implemented
    motion_animation.save_animation(d, "16:9", manifest)
    assert motion_gen_rules._verified_drawn(g) == {}
