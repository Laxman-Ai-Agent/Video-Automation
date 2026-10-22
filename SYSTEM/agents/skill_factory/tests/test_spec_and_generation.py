"""Test Suite A: Skill Specifications, Decisions, and Generation."""
import pytest
from SYSTEM.agents.skill_factory.decision_engine import decision_engine
from SYSTEM.agents.skill_factory.generator import (
    GenerationProviderUnavailableError,
    SkillGenerator,
)
from SYSTEM.agents.skill_factory.specification import (
    SkillSpecification,
    validate_specification,
)
from SYSTEM.registries.skill_registry import get_skill_registry


def test_valid_specification():
    spec = SkillSpecification(
        skill_id="motion.particle_flow",
        name="Particle Flow Animation",
        purpose="Procedural particle physics for background motion.",
        domain="motion",
        version="1.0.0",
        capabilities=["particle-physics", "fluid-motion"],
        tags=["particles", "motion", "remotion"],
        inputs={"particle_count": "int"},
        outputs={"rendered_frames": "list"},
        risk_level="low",
    )
    errors = validate_specification(spec)
    assert errors == []


def test_invalid_specification_rejected():
    # Empty skill_id
    spec_bad_id = SkillSpecification(
        skill_id="",
        name="Bad",
        purpose="Test",
        domain="motion",
        capabilities=["cap1"],
    )
    errs = validate_specification(spec_bad_id)
    assert any("skill_id is required" in e for e in errs)

    # Illegal characters / path traversal in skill_id
    spec_traversal = SkillSpecification(
        skill_id="../../escape",
        name="Escape",
        purpose="Test",
        domain="motion",
        capabilities=["cap1"],
    )
    errs = validate_specification(spec_traversal)
    assert any("invalid" in e.lower() or "traversal" in e.lower() for e in errs)

    # Missing capabilities
    spec_no_caps = SkillSpecification(
        skill_id="motion.empty_caps",
        name="Empty Caps",
        purpose="Test",
        domain="motion",
        capabilities=[],
    )
    errs = validate_specification(spec_no_caps)
    assert any("at least one capability" in e for e in errs)

    # Invalid semver
    spec_bad_ver = SkillSpecification(
        skill_id="motion.bad_ver",
        name="Bad Ver",
        purpose="Test",
        domain="motion",
        version="v1.0-alpha",
        capabilities=["cap1"],
    )
    errs = validate_specification(spec_bad_ver)
    assert any("Semantic Version" in e for e in errs)


def test_yaml_manifest_roundtrip():
    spec = SkillSpecification(
        skill_id="audio.voice_clarity",
        name="Voice Clarity Optimizer",
        purpose="Spectral subtraction for high-clarity voice track.",
        domain="audio",
        version="1.2.0",
        capabilities=["noise-reduction", "clarity-boost"],
        tags=["audio", "dsp"],
        risk_level="medium",
    )
    yaml_md = spec.to_yaml_manifest()
    assert yaml_md.startswith("---")
    assert "audio.voice_clarity" in yaml_md

    parsed_spec = SkillSpecification.from_yaml_manifest(yaml_md)
    assert parsed_spec.skill_id == "audio.voice_clarity"
    assert parsed_spec.domain == "audio"
    assert parsed_spec.version == "1.2.0"
    assert "noise-reduction" in parsed_spec.capabilities
    assert parsed_spec.risk_level == "medium"


def test_reuse_decision_for_existing_approved_skill():
    # 'motion.kinetic_typography' is a canonical seed skill in the registry
    reg = get_skill_registry()
    reg.initialize()

    spec = SkillSpecification(
        skill_id="motion.kinetic_typography",
        name="Kinetic Typography Specialist",
        purpose="Telugu narration kinetic typography layout and readability.",
        domain="motion",
        capabilities=["typography-layout", "readability-optimization"],
    )
    decision = decision_engine.evaluate(spec)
    assert decision.action == "REUSE"
    assert decision.skill_id == "motion.kinetic_typography"
    assert "Approved compatible skill" in decision.reason


def test_adapt_decision_preserves_base_version():
    reg = get_skill_registry()
    reg.initialize()

    # Request new capability in motion domain that partially matches
    spec = SkillSpecification(
        skill_id="motion.kinetic_typography.smooth_fade",
        name="Kinetic Typography Smooth Fade",
        purpose="Telugu kinetic typography with extended smooth fading curves.",
        domain="motion",
        capabilities=["typography-layout", "smooth-fading-curves"],
    )
    decision = decision_engine.evaluate(spec, allow_adapt=True)
    assert decision.action == "ADAPT"
    assert decision.base_skill_id is not None
    # Ensure suggested version does not overwrite base version
    assert decision.version != decision.base_version
    assert "Adapting as version" in decision.reason


def test_generation_fails_when_provider_unavailable():
    generator = SkillGenerator()
    spec = SkillSpecification(
        skill_id="validation.strict_aspect",
        name="Strict Aspect Ratio Guard",
        purpose="Ensures composition strictly conforms to aspect bounds.",
        domain="validation",
        capabilities=["aspect-ratio-check"],
    )
    # When allow_template_fallback is False, must raise GenerationProviderUnavailableError
    # if live provider cannot connect
    with pytest.raises(GenerationProviderUnavailableError):
        generator.generate(spec, allow_template_fallback=False)


def test_structured_template_fallback_generation():
    generator = SkillGenerator()
    spec = SkillSpecification(
        skill_id="validation.strict_aspect",
        name="Strict Aspect Ratio Guard",
        purpose="Ensures composition strictly conforms to aspect bounds.",
        domain="validation",
        version="1.0.0",
        capabilities=["aspect-ratio-check", "overflow-guard"],
        inputs={"width": "int", "height": "int"},
        outputs={"valid": "bool"},
    )
    draft = generator.generate(spec, allow_template_fallback=True)
    assert draft.skill_id == "validation.strict_aspect"
    assert draft.version == "1.0.0"
    assert "---" in draft.content
    assert "Strict Aspect Ratio Guard" in draft.content
    assert "aspect-ratio-check" in draft.content
    assert "## Purpose" in draft.content
    assert "## Core Rules" in draft.content
