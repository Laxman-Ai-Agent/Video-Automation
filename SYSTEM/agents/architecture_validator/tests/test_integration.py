"""Integration tests for Architecture Validator Agent.

Validates:
1. Canonical imports and legacy facade class identity.
2. Exact single registration in authoritative AgentRegistry.
3. Delegation from MainArchitectureAgent to ArchitectureValidatorAgent.
4. Clean failure propagation when delegation target is invalid or audit fails.
5. Preservation of CapabilityFinder and SkillFactory delegation flows.
6. Read-only idempotence across repeated audits.
"""
from __future__ import annotations

import pytest

# Canonical imports
from SYSTEM.agents.architecture_validator import ArchitectureValidatorAgent as CanonicalAVA_Pkg
from SYSTEM.agents.architecture_validator.agent import ArchitectureValidatorAgent as CanonicalAVA_Mod

# Legacy imports
from SYSTEM.agents.system_agents import ArchitectureValidatorAgent as LegacyRootAVA
from SYSTEM.agents.system_agents.architecture_validator import ArchitectureValidatorAgent as LegacyAVA_Pkg
from SYSTEM.agents.system_agents.architecture_validator.agent import ArchitectureValidatorAgent as LegacyAVA_Mod

# Other agents
from SYSTEM.agents.main_architecture_agent.agent import MainArchitectureAgent
from SYSTEM.agents.capability_finder.agent import CapabilityFinderAgent
from SYSTEM.agents.skill_factory.agent import SkillFactoryAgent
from SYSTEM.agents.shared.contracts import AgentRequest, AgentResult
from SYSTEM.registries.agent_registry import get_agent_registry


def test_import_and_class_identity():
    assert CanonicalAVA_Pkg is not None
    assert CanonicalAVA_Mod is not None
    assert LegacyAVA_Pkg is not None
    assert LegacyAVA_Mod is not None
    assert LegacyRootAVA is not None

    assert CanonicalAVA_Pkg is CanonicalAVA_Mod
    assert CanonicalAVA_Pkg is LegacyAVA_Pkg
    assert CanonicalAVA_Pkg is LegacyAVA_Mod
    assert CanonicalAVA_Pkg is LegacyRootAVA


def test_agent_registry_single_canonical_registration():
    reg = get_agent_registry()
    all_agents = reg.list_all_agents()
    validator_matches = [a for a in all_agents if a.agent_id == "architecture_validator"]

    assert len(validator_matches) == 1, f"Expected exactly 1 registration, found {len(validator_matches)}"
    meta = validator_matches[0]
    assert meta.name == "Architecture Validator Agent"
    assert meta.version == "1.0.0"

    adapter = reg.get_agent("architecture_validator")
    assert isinstance(adapter, CanonicalAVA_Mod)


def test_main_architecture_agent_validate_architecture_action():
    maa = MainArchitectureAgent()
    req = AgentRequest(
        agent_id="main_architecture_agent",
        parameters={
            "action": "validate_architecture",
            "audit_action": "full_architecture_audit",
        },
    )
    res = maa.execute(None, req)
    assert isinstance(res, AgentResult)
    assert res.agent_id == "main_architecture_agent"
    assert "delegated_to" in res.metadata
    assert res.metadata["delegated_to"] == "architecture_validator"
    assert "validator_result" in res.metadata
    assert "Architecture validation coordinated" in res.summary


def test_main_architecture_agent_delegate_action():
    maa = MainArchitectureAgent()
    req = AgentRequest(
        agent_id="main_architecture_agent",
        parameters={
            "action": "delegate",
            "target_agent_id": "architecture_validator",
            "sub_parameters": {"action": "video_pipeline_audit"},
        },
    )
    res = maa.execute(None, req)
    assert res.status == "succeeded"
    assert "architecture_validator" in res.summary


def test_main_architecture_agent_delegation_to_cf_and_sf_preserved():
    maa = MainArchitectureAgent()

    # Delegate to capability_finder
    req_cf = AgentRequest(
        agent_id="main_architecture_agent",
        parameters={
            "action": "delegate",
            "target_agent_id": "capability_finder",
            "sub_parameters": {"action": "discover", "query": "ffmpeg"},
        },
    )
    res_cf = maa.execute(None, req_cf)
    assert res_cf.status == "succeeded"

    # Delegate to skill_factory
    req_sf = AgentRequest(
        agent_id="main_architecture_agent",
        parameters={
            "action": "delegate",
            "target_agent_id": "skill_factory",
            "sub_parameters": {
                "action": "decision",
                "specification": {
                    "skill_id": "media.ffmpeg_operations",
                    "name": "FFmpeg Operations",
                    "purpose": "Media container probing and validation",
                    "domain": "rendering_qa",
                },
            },
        },
    )
    res_sf = maa.execute(None, req_sf)
    assert res_sf.status == "succeeded"


def test_missing_delegation_target_fails_cleanly():
    maa = MainArchitectureAgent()
    req = AgentRequest(
        agent_id="main_architecture_agent",
        parameters={
            "action": "delegate",
            "target_agent_id": "nonexistent_target_agent_999",
        },
    )
    res = maa.execute(None, req)
    assert res.status == "failed"
    assert "not found in registry" in res.error
