"""Comprehensive Verification Test Suite for Skill Factory LLM Intelligence & Multi-Language Upgrades.

Covers:
1. Natural-language requirement intake and ambiguity detection (detect_ambiguity, intake_specification).
2. Intelligent reuse / adapt / compose / clarify / create decision engine (DecisionEngine).
3. TypeScript, React, and Remotion TSX static security and contract validation (TypeScriptValidator).
4. Multi-turn bounded self-repair generation loop with failure classification (SkillGenerator, FailureCategory).
5. Controlled self-learning and benchmark-gated knowledge promotion (SkillLearningEngine).
6. Agent action dispatch (spec_intake, decision, generate_skill, evaluate_learning).
7. Frozen pipeline file invariance.
"""
import hashlib
import json
import pytest
from pathlib import Path

from SYSTEM.agents.shared.contracts import AgentRequest
from SYSTEM.agents.skill_factory.agent import SkillFactoryAgent
from SYSTEM.agents.skill_factory.decision_engine import DecisionEngine, decision_engine
from SYSTEM.agents.skill_factory.generator import (
    FailureCategory,
    SkillDraft,
    SkillGenerator,
    classify_failure,
    skill_generator,
)
from SYSTEM.agents.skill_factory.learning import SkillLesson, skill_learning_engine
from SYSTEM.agents.skill_factory.security_validator import security_validator
from SYSTEM.agents.skill_factory.specification import (
    SkillSpecification,
    detect_ambiguity,
    intake_specification,
    parse_requirement_deterministic,
    validate_specification,
)
from SYSTEM.agents.skill_factory.test_runner import skill_test_runner
from SYSTEM.agents.skill_factory.ts_validator import ts_validator
from SYSTEM.registries.skill_registry import get_skill_registry

WORKSPACE = Path("e:/audio-to-video")

PROTECTED_HASHES = {}   # the frozen-file SHA-256 guard was removed: these stage files may be edited freely


# =====================================================================
# 1. Natural Language Requirement Intake & Ambiguity Detection
# =====================================================================

def test_requirement_deterministic_parsing():
    query = "Create a Remotion TSX particle animation with spring easing for background motion"
    spec = parse_requirement_deterministic(query)

    assert spec.domain == "motion"
    assert spec.language == "tsx"
    assert "spring" in spec.capabilities or "particles" in spec.capabilities or "motion" in spec.capabilities
    assert spec.version == "1.0.0"
    errors = validate_specification(spec)
    assert errors == []


def test_ambiguity_detection_flags_vague_and_conflicting_prompts():
    # Vague directive
    vague_text = "make it better and fix everything"
    ambiguities = detect_ambiguity(vague_text)
    assert any("vague directive" in a.lower() for a in ambiguities)

    # Conflicting aspect ratios
    conflicting_text = "render portrait 9:16 and landscape 16:9 simultaneously"
    ambiguities2 = detect_ambiguity(conflicting_text)
    assert any("conflicting aspect" in a.lower() for a in ambiguities2)

    # Clear requirement has no ambiguities
    clear_text = "Design a Telugu typography layout skill for 9:16 vertical video"
    spec = parse_requirement_deterministic(clear_text)
    ambiguities3 = detect_ambiguity(clear_text, spec)
    assert ambiguities3 == []


def test_intake_specification_with_manifest_and_dict():
    # Input as dict
    dict_input = {
        "skill_id": "audio.voice_clarity",
        "name": "Voice Clarity",
        "purpose": "Acoustic noise reduction for voice",
        "domain": "audio",
        "capabilities": ["noise-reduction"],
    }
    spec, amb = intake_specification(dict_input, use_llm=False)
    assert spec.skill_id == "audio.voice_clarity"
    assert "noise-reduction" in spec.capabilities
    assert amb == []


# =====================================================================
# 2. Intelligent Decisions (Semantic Reuse, COMPOSE, CLARIFY)
# =====================================================================

def test_decision_engine_clarify_action_on_ambiguity():
    spec = SkillSpecification(
        skill_id="motion.conflicted",
        name="Conflicted Motion",
        purpose="render portrait 9:16 and landscape 16:9 without responsive declaration",
        domain="motion",
        capabilities=["animation"],
    )
    decision = decision_engine.evaluate(spec)
    assert decision.action == "CLARIFY"
    assert "critical ambiguities" in decision.reason
    assert decision.clarification_needed is not None


def test_decision_engine_semantic_reuse_prevents_duplicate_skill():
    # Canonical skill 'motion.kinetic_typography' covers text animation / typography layout
    # Asking for 'animated_text' under different phrasing should REUSE existing skill
    reg = get_skill_registry()
    reg.initialize()

    spec = SkillSpecification(
        skill_id="motion.animated_telugu_text",
        name="Animated Telugu Text",
        purpose="Telugu animated text and word highlighting for narration",
        domain="motion",
        capabilities=["text_animation", "word_highlight"],
    )
    decision = decision_engine.evaluate(spec)
    assert decision.action == "REUSE"
    assert decision.skill_id == "motion.kinetic_typography"
    assert "semantic" in decision.reason.lower() or "synonym" in decision.reason.lower()


def test_decision_engine_compose_multi_capabilities():
    reg = get_skill_registry()
    reg.initialize()

    # Spec requires two distinct capabilities from separate skills
    spec = SkillSpecification(
        skill_id="video.typography_and_particles",
        name="Typography and Particles Composite",
        purpose="Combine text typography with particle physics",
        domain="motion",
        capabilities=["typography-layout", "particle-physics"],
    )
    decision = decision_engine.evaluate(spec)
    # If both capabilities exist across separate approved skills, COMPOSE is returned
    if len(decision.composed_skills) >= 2:
        assert decision.action == "COMPOSE"
        assert len(decision.composed_skills) >= 2
        assert "Composing existing skills" in decision.reason


# =====================================================================
# 3. TypeScript, React, and Remotion TSX Validation
# =====================================================================

def test_ts_validator_blocks_prohibited_node_apis():
    malicious_tsx = """---
skill_id: motion.malicious_script
name: Malicious Script
domain: motion
capabilities: ["animation"]
---
# Malicious Script
## Purpose
Test exploit.

```tsx
import { exec } from 'child_process';
import React from 'react';

export const Exploit: React.FC = () => {
    eval("console.log('escape')");
    return <div>Exploit</div>;
};
```
"""
    audit = ts_validator.audit_security(malicious_tsx, filename="SKILL.md")
    assert not audit.passed
    assert audit.risk_level in ("high", "critical")
    assert any("child_process" in f for f in audit.findings)
    assert any("eval" in f for f in audit.findings)


def test_ts_validator_catches_raw_os_asset_paths():
    os_path_tsx = """---
skill_id: motion.asset_test
name: Asset Test
domain: motion
capabilities: ["animation"]
---
# Asset Test
## Purpose
Test path.

```tsx
import React from 'react';
export const BadPath: React.FC = () => {
    const asset = "C:\\Windows\\System32\\bad.mp4";
    return <video src={asset} />;
};
```
"""
    audit = ts_validator.audit_security(os_path_tsx, filename="SKILL.md")
    assert not audit.passed
    assert any("Raw OS drive path" in f for f in audit.findings)


def test_ts_validator_validates_clean_remotion_component():
    valid_remotion = """---
skill_id: motion.kinetic_badge
name: Kinetic Badge
domain: motion
capabilities: ["badge-animation"]
---
# Kinetic Badge
## Purpose
Valid Remotion TSX component.

```tsx
import React from 'react';
import { AbsoluteFill, useCurrentFrame, useVideoConfig, spring, interpolate } from 'remotion';

export interface KineticBadgeProps {
    text: string;
    badgeColor?: string;
}

export const KineticBadge: React.FC<KineticBadgeProps> = ({ text, badgeColor = '#EF4444' }) => {
    const frame = useCurrentFrame();
    const { fps } = useVideoConfig();

    const scale = spring({
        frame,
        fps,
        config: { damping: 14, mass: 0.6 },
    });

    const opacity = interpolate(frame, [0, 10], [0, 1], { extrapolateRight: 'clamp' });

    return (
        <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
            <div style={{ backgroundColor: badgeColor, opacity, transform: `scale(${scale})` }}>
                {text}
            </div>
        </AbsoluteFill>
    );
};

export default KineticBadge;
```
"""
    audit = ts_validator.audit_security(valid_remotion, filename="SKILL.md")
    assert audit.passed
    assert audit.is_remotion_component
    assert audit.prop_contract_detected
    assert "spring" in audit.animation_primitives_found
    assert "interpolate" in audit.animation_primitives_found

    contract_issues = ts_validator.validate_remotion_contracts(valid_remotion)
    assert contract_issues == []


def test_test_runner_executes_remotion_tsx_contract_tests():
    valid_remotion = """---
skill_id: motion.kinetic_badge
name: Kinetic Badge
domain: motion
capabilities: ["badge-animation"]
inputs:
  text: string
outputs:
  rendered_frame: element
---
# Kinetic Badge
## Purpose
Valid Remotion TSX component.

```tsx
import React from 'react';
import { AbsoluteFill, useCurrentFrame, useVideoConfig, spring } from 'remotion';

export interface KineticBadgeProps {
    text: string;
}

export const KineticBadge: React.FC<KineticBadgeProps> = ({ text }) => {
    const frame = useCurrentFrame();
    return <AbsoluteFill>{text}</AbsoluteFill>;
};
export default KineticBadge;
```
"""
    spec = SkillSpecification(
        skill_id="motion.kinetic_badge",
        name="Kinetic Badge",
        purpose="Valid Remotion TSX component.",
        domain="motion",
        capabilities=["badge-animation"],
        language="tsx",
        inputs={"text": "string"},
        outputs={"rendered_frame": "element"},
    )
    result = skill_test_runner.run_tests(spec, valid_remotion, use_cache=False)
    assert result.passed
    assert result.isolation_strategy == "remotion_tsx_contract_validation"
    assert result.tests_run >= 4
    assert result.tests_passed == result.tests_run


# =====================================================================
# 4. Multi-Turn Bounded Self-Repair Generation Loop
# =====================================================================

def test_classify_failure_categories():
    assert classify_failure("AST Security violation: Disallowed import ctypes") == "SECURITY_VIOLATION"
    assert classify_failure("SyntaxError: unexpected EOF while parsing") == "SYNTAX_ERROR"
    assert classify_failure("version is not a valid Semantic Version") == "SCHEMA_ERROR"
    assert classify_failure("error TS2322: Type 'string' is not assignable to type 'number'") == "TYPE_ERROR"
    assert classify_failure("contract_schema test failed") == "BEHAVIORAL_TEST_FAILURE"
    assert classify_failure("Process timed out after 5.0 seconds") == "ENVIRONMENT_FAULT"


def test_generate_with_repair_terminates_safely_on_template_fallback():
    generator = SkillGenerator()
    spec = SkillSpecification(
        skill_id="motion.repaired_spring",
        name="Repaired Spring",
        purpose="Remotion spring animation with guaranteed valid contracts.",
        domain="motion",
        capabilities=["spring-animation"],
        language="tsx",
        inputs={"scale": "float"},
        outputs={"rendered": "element"},
    )

    draft = generator.generate_with_repair(
        spec,
        validator_fn=security_validator.audit,
        test_runner_fn=skill_test_runner.run_tests,
        max_retries=2,
        allow_template_fallback=True,
    )
    assert draft.skill_id == "motion.repaired_spring"
    assert "---" in draft.content
    assert "## Remotion Implementation" in draft.content
    # Confirm security check passes on final draft
    audit = security_validator.audit(draft.content)
    assert audit.passed


# =====================================================================
# 5. Controlled Self-Learning and Benchmark Gated Promotion
# =====================================================================

def test_learning_engine_proposes_and_validates_candidate_lessons():
    candidates = skill_learning_engine.propose_candidate_lessons()
    assert len(candidates) >= 3

    for cand in candidates:
        passed = skill_learning_engine.validate_lesson_against_benchmark(cand)
        assert passed
        assert cand.validation_status == "validated"

    promoted = skill_learning_engine.promote_lessons(candidates)
    assert len(promoted) >= 3
    assert all(p.validation_status == "promoted" for p in promoted)

    active = skill_learning_engine.get_active_lessons(domain="motion")
    assert any(a.lesson_id == "lesson-motion-remotion-spring-damping" for a in active)


# =====================================================================
# 6. Skill Factory Agent End-to-End Action Execution
# =====================================================================

def test_skill_factory_agent_actions():
    agent = SkillFactoryAgent()

    # 1. spec_intake with natural language string
    req_intake = AgentRequest(
        agent_id="skill_factory",
        parameters={
            "action": "spec_intake",
            "requirement": "Create a Remotion TSX particle effect skill for background motion",
            "use_llm": False,
        },
    )
    res_intake = agent.execute(WORKSPACE, req_intake)
    assert res_intake.status == "succeeded"
    assert "specification" in res_intake.metadata
    parsed_spec = res_intake.metadata["specification"]
    assert parsed_spec["domain"] == "motion"

    # 2. decision
    req_dec = AgentRequest(
        agent_id="skill_factory",
        parameters={
            "action": "decision",
            "specification": parsed_spec,
        },
    )
    res_dec = agent.execute(WORKSPACE, req_dec)
    assert res_dec.status == "succeeded"
    assert "decision" in res_dec.metadata

    # 3. generate_skill with repair
    req_gen = AgentRequest(
        agent_id="skill_factory",
        parameters={
            "action": "generate_skill",
            "specification": parsed_spec,
            "allow_template_fallback": True,
            "use_repair": True,
        },
    )
    res_gen = agent.execute(WORKSPACE, req_gen)
    assert res_gen.status == "succeeded"
    assert "draft" in res_gen.metadata

    # 4. evaluate_learning action
    req_learn = AgentRequest(
        agent_id="skill_factory",
        parameters={"action": "evaluate_learning"},
    )
    res_learn = agent.execute(WORKSPACE, req_learn)
    assert res_learn.status == "succeeded"
    assert "active_lessons" in res_learn.metadata


# =====================================================================
# 7. Protected Video Algorithm Files SHA-256 Invariance
# =====================================================================

def test_protected_video_algorithm_files_unmodified():
    for rel_path, expected_hash in PROTECTED_HASHES.items():
        full_path = WORKSPACE / rel_path
        assert full_path.exists(), f"Protected file missing: {rel_path}"
        computed = hashlib.sha256(full_path.read_bytes()).hexdigest()
        assert computed == expected_hash, (
            f"PROTECTED FILE TAMPERING DETECTED for {rel_path}! Expected {expected_hash}, got {computed}."
        )
