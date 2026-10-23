"""Production Verification Test Suite for Phase 5: Architecture Validator Agent.

Validates:
1. Canonical imports and legacy facade class identity.
2. Exact single registration in authoritative AgentRegistry.
3. Agent initialization, metadata, capabilities, and contracts.
4. Full architecture audit execution producing structured findings and metrics.
5. Detection of missing mandatory video pipeline stages and approval gates.
6. Detection of forbidden cycles in dependency graphs.
7. Detection of path traversal in skill entrypoint configurations.
8. Detection of missing physical artifacts for active approved production skills.
10. MainArchitectureAgent delegation via validate_architecture action.
11. MainArchitectureAgent delegation via general delegate action.
12. Read-only validation execution preserving catalogs and registries unmutated.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# 1. Imports
from SYSTEM.agents.architecture_validator import (
    ArchitectureFinding,
    ArchitectureValidatorAgent as CanonicalAVA_Pkg,
    AuditResult,
    FindingCategory,
    FindingSeverity,
)
from SYSTEM.agents.architecture_validator.agent import ArchitectureValidatorAgent as CanonicalAVA_Mod
from SYSTEM.agents.system_agents.architecture_validator import ArchitectureValidatorAgent as LegacyAVA_Pkg
from SYSTEM.agents.system_agents.architecture_validator.agent import ArchitectureValidatorAgent as LegacyAVA_Mod
from SYSTEM.agents.system_agents import ArchitectureValidatorAgent as LegacyRootAVA

from SYSTEM.agents.main_architecture_agent.agent import MainArchitectureAgent
from SYSTEM.agents.shared.contracts import (
    AgentCategory,
    AgentMetadata,
    AgentRequest,
    AgentResult,
    AgentStatus,
)
from SYSTEM.registries.agent_registry import AgentRegistry, get_agent_registry
from SYSTEM.agents.architecture_validator.validators import (
    AgentRegistryValidator,
    CapabilityRegistryValidator,
    ContractValidator,
    DependencyGraphValidator,
    SecurityBoundaryValidator,
    VideoPipelineValidator,
)


class TestArchitectureValidatorClassAndRegistration:
    """Verifies import resolution, class identity, and single registration."""

    def test_class_identity_across_all_paths(self):
        assert CanonicalAVA_Pkg is CanonicalAVA_Mod
        assert CanonicalAVA_Pkg is LegacyAVA_Pkg
        assert CanonicalAVA_Pkg is LegacyAVA_Mod
        assert CanonicalAVA_Pkg is LegacyRootAVA

    def test_single_canonical_registration_in_agent_registry(self):
        reg = get_agent_registry()
        matches = [m for m in reg.list_all_agents() if m.agent_id == "architecture_validator"]
        assert len(matches) == 1, f"Expected 1 registration for architecture_validator, found {len(matches)}"
        meta = matches[0]
        assert meta.agent_id == "architecture_validator"
        assert meta.category == AgentCategory.SYSTEM_SUBAGENT
        assert meta.status == AgentStatus.IMPLEMENTED

        adapter = reg.get_agent("architecture_validator")
        assert isinstance(adapter, CanonicalAVA_Mod)


class TestArchitectureValidatorAudits:
    """Verifies audit execution, finding generation, and fail-closed detection."""

    def test_full_architecture_audit_execution(self):
        agent = CanonicalAVA_Mod()
        req = AgentRequest(
            agent_id="architecture_validator",
            parameters={"action": "full_architecture_audit"},
        )
        res = agent.execute(None, req)
        assert isinstance(res, AgentResult)
        assert res.agent_id == "architecture_validator"
        assert "audit_result" in res.metadata
        audit_data = res.metadata["audit_result"]
        assert audit_data["action"] == "full_architecture_audit"
        assert audit_data["status"] in ("passed", "warning", "failed")
        assert isinstance(audit_data["findings"], list)

    def test_detects_missing_mandatory_pipeline_stages(self):
        validator = VideoPipelineValidator()
        incomplete_stages = ("audio", "analyzer", "segmentation")
        findings = validator.validate(active_stages=incomplete_stages)
        blocking = [f for f in findings if f.severity == FindingSeverity.BLOCKING_ERROR]
        assert any("do not match canonical 13-stage architecture" in f.message for f in blocking)
        assert any("Mandatory approval gate stage 'approval' is missing" in f.message for f in blocking)
        assert any("Mandatory approval gate stage 'qc' is missing" in f.message for f in blocking)

    def test_detects_forbidden_dependency_cycle(self):
        validator = DependencyGraphValidator()
        cycle_graph = {
            "planning": ("final",),
            "render": ("planning",),
            "final": ("render",),
        }
        findings = validator.validate(
            agent_registry_instance=MagicMock(_metadata={}),
            custom_pipeline_deps=cycle_graph,
        )
        blocking = [f for f in findings if f.severity == FindingSeverity.BLOCKING_ERROR]
        assert any("Forbidden cycle detected in video pipeline stage dependency graph" in f.message for f in blocking)

    def test_detects_path_traversal_in_skill_entrypoint(self, tmp_path):
        skills_dir = tmp_path / "SYSTEM" / "skills"
        skills_dir.mkdir(parents=True)
        catalog = {
            "version": 1,
            "skills": {
                "evil.traversal": {
                    "skill_id": "evil.traversal",
                    "status": "approved",
                    "domain": "video",
                    "entrypoint": "../../escape.py",
                }
            },
        }
        (skills_dir / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")

        validator = CapabilityRegistryValidator(project_root=tmp_path)
        mock_cap = MagicMock()
        mock_cap.list_all.return_value = []
        findings = validator.validate(capability_registry_instance=mock_cap)
        blocking = [f for f in findings if f.severity == FindingSeverity.BLOCKING_ERROR]
        assert any("Path traversal detected" in f.message for f in blocking)

    def test_detects_missing_artifact_for_approved_production_skill(self, tmp_path):
        skills_dir = tmp_path / "SYSTEM" / "skills"
        skills_dir.mkdir(parents=True)
        catalog = {
            "version": 1,
            "skills": {
                "motion.missing": {
                    "skill_id": "motion.missing",
                    "status": "approved",
                    "domain": "motion",
                    "entrypoint": "ghost/SKILL.md",
                }
            },
        }
        (skills_dir / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")

        validator = CapabilityRegistryValidator(project_root=tmp_path)
        mock_cap = MagicMock()
        mock_cap.list_all.return_value = []
        findings = validator.validate(capability_registry_instance=mock_cap)
        blocking = [f for f in findings if f.severity == FindingSeverity.BLOCKING_ERROR]
        assert any("missing its physical artifact file on disk" in f.message for f in blocking)

    def test_security_boundary_has_no_blocking_findings(self):
        validator = SecurityBoundaryValidator()
        findings = validator.validate()
        blocking = [f for f in findings if f.severity == FindingSeverity.BLOCKING_ERROR]
        assert len(blocking) == 0, f"Security boundary violation: {[f.message for f in blocking]}"


class TestMainArchitectureAgentIntegration:
    """Verifies coordination and delegation between MainArchitectureAgent and ArchitectureValidator."""

    def test_maa_validate_architecture_coordination(self):
        maa = MainArchitectureAgent()
        req = AgentRequest(
            agent_id="main_architecture_agent",
            parameters={
                "action": "validate_architecture",
                "audit_action": "contract_audit",
            },
        )
        res = maa.execute(None, req)
        assert res.status == "succeeded"
        assert "Architecture validation coordinated" in res.summary
        assert res.metadata["delegated_to"] == "architecture_validator"

    def test_maa_general_delegation_to_validator(self):
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

    def test_audit_preserves_catalogs_read_only(self):
        from SYSTEM.registries.skill_registry import CATALOG_FILE
        before_bytes = CATALOG_FILE.read_bytes() if CATALOG_FILE.exists() else b""

        agent = CanonicalAVA_Mod()
        agent.execute(None, AgentRequest(agent_id="architecture_validator", parameters={"action": "full_architecture_audit"}))

        after_bytes = CATALOG_FILE.read_bytes() if CATALOG_FILE.exists() else b""
        assert before_bytes == after_bytes, "Audit modified skills catalog file!"
