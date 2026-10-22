"""Production Verification Test Suite for Phase 1: System Agent Directory Restructuring.

Validates:
1. Canonical imports for CapabilityFinderAgent and SkillFactoryAgent.
2. Legacy imports for CapabilityFinderAgent and SkillFactoryAgent via system_agents facade.
3. Strict class identity across canonical and compatibility paths.
4. Agent initialization with real project configuration.
5. Registry discovery and duplicate prevention (exact single registration).
6. Main Architecture Agent selection and invocation through supported interfaces.
7. Scoped memory and history integration.
8. Robust error handling for invalid requests and configurations.
9. Package initialization without circular imports.
10. Functional behavior of discovery, prerequisites, security audit, and staging.
"""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest

# 1. Canonical imports
from SYSTEM.agents.capability_finder import CapabilityFinderAgent as CanonicalCFA_Pkg
from SYSTEM.agents.capability_finder.agent import CapabilityFinderAgent as CanonicalCFA_Mod
from SYSTEM.agents.skill_factory import SkillFactoryAgent as CanonicalSFA_Pkg
from SYSTEM.agents.skill_factory.agent import SkillFactoryAgent as CanonicalSFA_Mod
from SYSTEM.agents.architecture_validator.agent import ArchitectureValidatorAgent as CanonicalAVA_Mod
from SYSTEM.agents.verification_and_test.agent import VerificationAndTestAgent as CanonicalVTA_Mod
from SYSTEM.agents.security_policy.agent import SecurityPolicyAgent as CanonicalSPA_Mod
from SYSTEM.agents.autonomous_execution.agent import AutonomousExecutionAgent as CanonicalAEA_Mod

# 2. Legacy imports
from SYSTEM.agents.system_agents.capability_finder import CapabilityFinderAgent as LegacyCFA_Pkg
from SYSTEM.agents.system_agents.capability_finder.agent import CapabilityFinderAgent as LegacyCFA_Mod
from SYSTEM.agents.system_agents.skill_factory import SkillFactoryAgent as LegacySFA_Pkg
from SYSTEM.agents.system_agents.skill_factory.agent import SkillFactoryAgent as LegacySFA_Mod
from SYSTEM.agents.system_agents import (
    CapabilityFinderAgent as LegacyRootCFA,
    SkillFactoryAgent as LegacyRootSFA,
)

# Shared and Registry imports
from SYSTEM.agents.main_architecture_agent.agent import MainArchitectureAgent
from SYSTEM.agents.shared.contracts import (
    AgentCategory,
    AgentMetadata,
    AgentRequest,
    AgentResult,
    AgentStatus,
)
from SYSTEM.memory.memory_scoping import ScopedMemoryManager
from SYSTEM.memory.shared_memory import MemoryItem
from SYSTEM.registries.agent_registry import AgentRegistry, get_agent_registry


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestImportAndClassIdentity:
    """Verifies that canonical and legacy imports resolve to identical class objects."""

    def test_canonical_imports_resolve(self):
        assert CanonicalCFA_Pkg is not None
        assert CanonicalCFA_Mod is not None
        assert CanonicalSFA_Pkg is not None
        assert CanonicalSFA_Mod is not None
        assert CanonicalCFA_Pkg is CanonicalCFA_Mod
        assert CanonicalSFA_Pkg is CanonicalSFA_Mod

    def test_legacy_imports_resolve(self):
        assert LegacyCFA_Pkg is not None
        assert LegacyCFA_Mod is not None
        assert LegacySFA_Pkg is not None
        assert LegacySFA_Mod is not None
        assert LegacyRootCFA is not None
        assert LegacyRootSFA is not None

    def test_class_identity_between_canonical_and_legacy(self):
        """Strict class identity guarantees no divergent or competing implementations exist."""
        assert CanonicalCFA_Mod is LegacyCFA_Mod
        assert CanonicalCFA_Mod is LegacyCFA_Pkg
        assert CanonicalCFA_Mod is LegacyRootCFA

        assert CanonicalSFA_Mod is LegacySFA_Mod
        assert CanonicalSFA_Mod is LegacySFA_Pkg
        assert CanonicalSFA_Mod is LegacyRootSFA


class TestAgentInitializationAndContracts:
    """Verifies agent lifecycle, metadata, contracts, and configuration loading."""

    def test_capability_finder_initialization(self):
        agent = CanonicalCFA_Mod()
        assert agent.agent_id == "capability_finder"
        assert agent.metadata.name == "Capability Finder Agent"
        assert agent.metadata.category == AgentCategory.SYSTEM_SUBAGENT
        assert agent.metadata.status == AgentStatus.IMPLEMENTED
        assert "capability-query" in agent.metadata.capabilities
        assert "agent_registry" in agent.metadata.allowed_tools
        assert hasattr(agent, "memory")

    def test_skill_factory_initialization(self):
        agent = CanonicalSFA_Mod()
        assert agent.agent_id == "skill_factory"
        assert agent.metadata.name == "Skill Factory Agent"
        assert agent.metadata.category == AgentCategory.SYSTEM_SUBAGENT
        assert agent.metadata.status == AgentStatus.IMPLEMENTED
        assert "skill-authoring" in agent.metadata.capabilities
        assert "security-audit" in agent.metadata.capabilities
        assert hasattr(agent, "memory")

    def test_config_files_present_and_valid(self):
        cf_cfg = PROJECT_ROOT / "SYSTEM" / "agents" / "capability_finder" / "config" / "agent_config.json"
        sf_cfg = PROJECT_ROOT / "SYSTEM" / "agents" / "skill_factory" / "config" / "agent_config.json"
        assert cf_cfg.exists(), "capability_finder config missing"
        assert sf_cfg.exists(), "skill_factory config missing"

        import json
        with open(cf_cfg, "r", encoding="utf-8") as f:
            cf_data = json.load(f)
        assert cf_data["agent_id"] == "capability_finder"

        with open(sf_cfg, "r", encoding="utf-8") as f:
            sf_data = json.load(f)
        assert sf_data["agent_id"] == "skill_factory"


class TestRegistryDiscoveryAndNoDuplicates:
    """Verifies that AgentRegistry registers agents from canonical paths without duplicate records."""

    MANDATORY_SYSTEM_AGENT_IDS = {
        "main_architecture_agent",
        "capability_finder",
        "skill_factory",
        "architecture_validator",
        "verification_and_test",
        "security_policy",
        "autonomous_execution",
    }

    def test_agent_registry_single_registration(self):
        reg = AgentRegistry()
        all_agents = reg.list_all_agents()
        agent_ids = [a.agent_id for a in all_agents]

        # Verify strict uniqueness of agent IDs: duplicate registrations are rejected
        assert len(agent_ids) == len(set(agent_ids)), f"Duplicate agent IDs found in AgentRegistry: {[x for x in agent_ids if agent_ids.count(x) > 1]}"
        for mandatory_id in self.MANDATORY_SYSTEM_AGENT_IDS:
            assert mandatory_id in agent_ids, f"Mandatory system agent '{mandatory_id}' missing from AgentRegistry"

    def test_system_agents_count_and_retrieval(self):
        reg = get_agent_registry()
        sys_agents = reg.list_system_agents()
        sys_ids = {a.agent_id for a in sys_agents}

        # 1. Uniqueness check: no duplicate system agent IDs
        raw_sys_ids = [a.agent_id for a in sys_agents]
        assert len(raw_sys_ids) == len(sys_ids), f"Duplicate system agent IDs detected: {raw_sys_ids}"

        # 2. Strict identity verification: all currently mandatory system agents must be present
        missing = self.MANDATORY_SYSTEM_AGENT_IDS - sys_ids
        assert not missing, f"Missing required system agents in registry: {sorted(missing)}"

        # 3. Structural validation for all registered system agents:
        # Ensures legitimate system agents (including future additions like Phase 8 autonomous_execution)
        # adhere to category, status, and adapter contract rules without hardcoded count limits.
        for sa in sys_agents:
            assert sa.category == AgentCategory.SYSTEM_SUBAGENT or sa.agent_id == "main_architecture_agent", (
                f"Agent '{sa.agent_id}' has unexpected category '{sa.category}' in system agents"
            )
            assert sa.status == AgentStatus.IMPLEMENTED, f"Agent '{sa.agent_id}' status is not IMPLEMENTED"
            assert sa.name and sa.purpose, f"System agent '{sa.agent_id}' missing name or purpose"
            assert reg.get_agent(sa.agent_id) is not None, f"System agent '{sa.agent_id}' missing adapter instance"

        # 4. Mandatory canonical system agents must instantiate canonical classes
        cf_inst = reg.get_agent("capability_finder")
        sf_inst = reg.get_agent("skill_factory")
        av_inst = reg.get_agent("architecture_validator")
        vt_inst = reg.get_agent("verification_and_test")
        sp_inst = reg.get_agent("security_policy")
        ae_inst = reg.get_agent("autonomous_execution")
        maa_inst = reg.get_agent("main_architecture_agent")

        assert isinstance(cf_inst, CanonicalCFA_Mod)
        assert isinstance(sf_inst, CanonicalSFA_Mod)
        assert isinstance(av_inst, CanonicalAVA_Mod)
        assert isinstance(vt_inst, CanonicalVTA_Mod)
        assert isinstance(sp_inst, CanonicalSPA_Mod)
        assert isinstance(ae_inst, CanonicalAEA_Mod)
        assert isinstance(maa_inst, MainArchitectureAgent)

        # 5. Metadata integrity: agent ID in metadata matches dictionary key and has valid non-empty fields
        for aid in self.MANDATORY_SYSTEM_AGENT_IDS:
            meta = reg.get(aid)
            assert meta is not None, f"Metadata missing for required agent '{aid}'"
            assert meta.agent_id == aid, f"Metadata agent_id mismatch for '{aid}'"
            assert meta.name and meta.purpose, f"Incomplete metadata for '{aid}'"

    def test_registry_zero_validation_errors(self):
        reg = get_agent_registry()
        issues = reg.validate_registry()
        assert issues == [], f"Validation issues detected in AgentRegistry: {issues}"

    def test_duplicate_registration_rejected(self):
        """Negative test: Attempting to register an already-registered agent ID must fail."""
        reg = AgentRegistry()
        dup_meta = AgentMetadata(
            agent_id="capability_finder",
            name="Duplicate Capability Finder",
            category=AgentCategory.SYSTEM_SUBAGENT,
        )
        with pytest.raises(ValueError, match="already registered"):
            reg.register(dup_meta, CanonicalCFA_Mod)

    def test_missing_mandatory_agent_causes_test_failure(self):
        """Negative test: An isolated registry missing a mandatory agent fails explicit verification."""
        reg = AgentRegistry()
        del reg._metadata["capability_finder"]
        del reg._adapters["capability_finder"]

        sys_ids = {a.agent_id for a in reg.list_system_agents()}
        assert "capability_finder" not in sys_ids
        missing = self.MANDATORY_SYSTEM_AGENT_IDS - sys_ids
        assert "capability_finder" in missing

        issues = reg.validate_registry()
        assert any("capability_finder" in iss for iss in issues), "Registry validation failed to report missing mandatory agent"

    def test_registry_accepts_authorized_additional_agent(self):
        """Positive test: An isolated registry can safely register legitimate additional canonical system agents
        (such as future Phase 10 E2E Production Readiness Agent) without failing solely because total agent count increases,
        while invalid registrations are still rejected."""
        reg = AgentRegistry()
        new_meta = AgentMetadata(
            agent_id="e2e_production_readiness",
            name="E2E Production Readiness Agent",
            version="1.0.0",
            category=AgentCategory.SYSTEM_SUBAGENT,
            status=AgentStatus.IMPLEMENTED,
            purpose="Enforces end-to-end production readiness gates.",
            owner="system",
        )
        reg.register(new_meta, CanonicalCFA_Mod)
        assert reg.get("e2e_production_readiness") is not None
        assert reg.get_agent("e2e_production_readiness") is not None
        assert reg.get("e2e_production_readiness").agent_id == "e2e_production_readiness"

        # Verify that legitimate additional agent passes registry validation cleanly
        issues = reg.validate_registry()
        assert issues == [], f"Legitimate additional agent produced validation issues: {issues}"

        # Verify that an invalid additional agent (e.g., missing purpose) IS caught by validation
        invalid_meta = AgentMetadata(
            agent_id="invalid_empty_purpose_agent",
            name="Invalid Agent",
            purpose="",
            category=AgentCategory.SYSTEM_SUBAGENT,
            status=AgentStatus.IMPLEMENTED,
        )
        reg.register(invalid_meta, CanonicalCFA_Mod)
        invalid_issues = reg.validate_registry()
        assert any("invalid_empty_purpose_agent" in iss for iss in invalid_issues), (
            "Registry failed to detect missing purpose for invalid agent"
        )

    def test_invalid_adapter_class_rejected(self):
        """Negative test: Registering an adapter that does not inherit from BaseAgent must fail."""
        reg = AgentRegistry()
        meta = AgentMetadata(
            agent_id="invalid_adapter_agent",
            name="Invalid Adapter Agent",
            purpose="Testing non-BaseAgent adapter rejection",
            category=AgentCategory.SYSTEM_SUBAGENT,
        )
        class NotAnAgent:
            pass
        with pytest.raises(TypeError, match="must inherit from BaseAgent"):
            reg.register(meta, NotAnAgent)

    def test_legacy_imports_do_not_create_duplicate_registrations(self):
        """Verifies that importing legacy facades does not duplicate registry entries."""
        import SYSTEM.agents.system_agents as legacy_pkg

        reg = get_agent_registry()
        all_ids = [a.agent_id for a in reg.list_all_agents()]
        assert len(all_ids) == len(set(all_ids)), "Legacy facade imports caused duplicate registrations!"


class TestMainArchitectureAgentIntegration:
    """Verifies that MainArchitectureAgent discovers, selects, and invokes both agents via supported interfaces."""

    def test_maa_can_delegate_to_capability_finder(self, tmp_path: Path):
        maa = MainArchitectureAgent()
        req = AgentRequest(
            project_id="test_reorg",
            agent_id="main_architecture_agent",
            stage_id="system",
            parameters={
                "target_agent_id": "capability_finder",
                "sub_parameters": {"query": "motion", "check_prerequisites": True},
            },
        )
        res = maa._handle_delegate(tmp_path, req)
        assert res.status == "succeeded", f"Delegation to capability_finder failed: {res.error}"
        delegated_res = res.metadata.get("delegated_result", {})
        assert "matching_agents" in delegated_res.get("metadata", {})
        assert "prerequisites" in delegated_res.get("metadata", {})

    def test_maa_can_delegate_to_skill_factory(self, tmp_path: Path):
        maa = MainArchitectureAgent()
        safe_skill_md = "---\nname: test_safe\nversion: 1.0.0\n---\n# Safe skill\nInstructions."
        req = AgentRequest(
            project_id="test_reorg",
            agent_id="main_architecture_agent",
            stage_id="system",
            parameters={
                "target_agent_id": "skill_factory",
                "sub_parameters": {"action": "audit", "content": safe_skill_md, "filename": "safe.md"},
            },
        )
        res = maa._handle_delegate(tmp_path, req)
        assert res.status == "succeeded", f"Delegation to skill_factory failed: {res.error}"
        delegated_res = res.metadata.get("delegated_result", {})
        assert delegated_res.get("metadata", {}).get("is_safe") is True

    def test_maa_delegation_missing_target_fails_cleanly(self, tmp_path: Path):
        maa = MainArchitectureAgent()
        req = AgentRequest(
            project_id="test_reorg",
            agent_id="main_architecture_agent",
            stage_id="system",
            parameters={"target_agent_id": "nonexistent_agent"},
        )
        res = maa._handle_delegate(tmp_path, req)
        assert res.status == "failed"
        assert "not found in registry" in (res.error or "")


class TestMemoryAndErrorHandling:
    """Verifies memory isolation policy and error reporting."""

    def test_scoped_memory_isolation(self):
        item_cf = MemoryItem(
            memory_id="mem_cf_1",
            title="CF Private Fact",
            content="Discovered 5 agents",
            kind="fact",
            owner="capability_finder",
            scope="agent",
            permitted_readers=["capability_finder"],
        )
        assert ScopedMemoryManager.is_access_allowed(item_cf, "capability_finder") is True
        assert ScopedMemoryManager.is_access_allowed(item_cf, "skill_factory") is False
        assert ScopedMemoryManager.is_access_allowed(item_cf, "motion_animation") is False
        assert ScopedMemoryManager.is_access_allowed(item_cf, "main_architecture_agent") is True  # MAA supervisory read

        item_sf = MemoryItem(
            memory_id="mem_sf_1",
            title="SF Private Fact",
            content="Audited skill sha256",
            kind="fact",
            owner="skill_factory",
            scope="agent",
            permitted_readers=["skill_factory"],
        )
        assert ScopedMemoryManager.is_access_allowed(item_sf, "skill_factory") is True
        assert ScopedMemoryManager.is_access_allowed(item_sf, "capability_finder") is False
        assert ScopedMemoryManager.is_access_allowed(item_sf, "render_video") is False

    def test_skill_factory_unsupported_action_validation(self, tmp_path: Path):
        factory = CanonicalSFA_Mod()
        req = AgentRequest(
            project_id="test",
            agent_id="skill_factory",
            parameters={"action": "unsupported_action"},
        )
        validation_errors = factory.validate(tmp_path, req)
        assert len(validation_errors) == 1
        assert "Unsupported action" in validation_errors[0]

    def test_no_circular_imports(self):
        """Re-importing packages dynamically must succeed cleanly with no circular import cycles."""
        mod1 = importlib.import_module("SYSTEM.agents.capability_finder")
        mod2 = importlib.import_module("SYSTEM.agents.skill_factory")
        mod3 = importlib.import_module("SYSTEM.agents.system_agents")
        mod4 = importlib.import_module("SYSTEM.registries.agent_registry")

        assert hasattr(mod1, "CapabilityFinderAgent")
        assert hasattr(mod2, "SkillFactoryAgent")
        assert hasattr(mod3, "CapabilityFinderAgent")
        assert hasattr(mod4, "AgentRegistry")
