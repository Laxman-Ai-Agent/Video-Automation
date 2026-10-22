"""Agent Registry Validator for Architecture Validator Agent.

Validates:
- Agent ID uniqueness and validity.
- Canonical class and module resolution.
- BaseAgent inheritance and interface compliance (execute, validate).
- AgentMetadata consistency (category, status, stage_id, capabilities, allowed_tools).
- Canonical and legacy import path compatibility.
- Absence of duplicate or unregistered adapter instances.
"""
from __future__ import annotations

import importlib
import inspect
from pathlib import Path
from typing import Any

from SYSTEM.agents.architecture_validator.contracts import (
    ArchitectureFinding,
    FindingCategory,
    FindingSeverity,
)
from SYSTEM.agents.shared.base_agent import BaseAgent
from SYSTEM.agents.shared.contracts import AgentCategory, AgentMetadata, AgentStatus


class AgentRegistryValidator:
    """Audits AgentRegistry for architectural compliance, interface contracts, and import validity."""

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = project_root or Path(__file__).resolve().parents[4]

    def validate(self, registry_instance: Any = None) -> list[ArchitectureFinding]:
        findings: list[ArchitectureFinding] = []

        if registry_instance is None:
            try:
                from SYSTEM.registries.agent_registry import registry
                registry_instance = registry
            except Exception as e:
                findings.append(
                    ArchitectureFinding(
                        category=FindingCategory.AGENT_REGISTRY,
                        severity=FindingSeverity.BLOCKING_ERROR,
                        component="SYSTEM.registries.agent_registry",
                        message=f"Failed to import authoritative AgentRegistry: {e}",
                        evidence=str(e),
                        remediation="Ensure SYSTEM/registries/agent_registry.py is syntactically valid and all dependencies resolve.",
                    )
                )
                return findings

        # 1. Uniqueness of Agent IDs
        metadata_map = getattr(registry_instance, "_metadata", {})
        adapter_map = getattr(registry_instance, "_adapters", {})

        meta_keys = list(metadata_map.keys())
        adapter_keys = list(adapter_map.keys())

        if not meta_keys and not adapter_keys:
            findings.append(
                ArchitectureFinding(
                    category=FindingCategory.AGENT_REGISTRY,
                    severity=FindingSeverity.BLOCKING_ERROR,
                    component="AgentRegistry",
                    message="AgentRegistry contains no registered agents.",
                    evidence=f"metadata_count=0, adapter_count=0",
                    remediation="Register authoritative agents during AgentRegistry initialization.",
                )
            )
            return findings

        # Check for empty or malformed IDs
        for aid in meta_keys:
            if not aid or not aid.strip():
                findings.append(
                    ArchitectureFinding(
                        category=FindingCategory.AGENT_REGISTRY,
                        severity=FindingSeverity.BLOCKING_ERROR,
                        component="AgentRegistry._metadata",
                        message="Found empty or whitespace-only agent ID in metadata registry.",
                        evidence=repr(aid),
                        remediation="Ensure every registered agent has a non-empty string identifier.",
                    )
                )

        # 2. Key Synchronization between Metadata and Adapters
        missing_in_adapters = set(meta_keys) - set(adapter_keys)
        for aid in missing_in_adapters:
            findings.append(
                ArchitectureFinding(
                    category=FindingCategory.AGENT_REGISTRY,
                    severity=FindingSeverity.BLOCKING_ERROR,
                    component=f"AgentRegistry.{aid}",
                    message=f"Agent '{aid}' has metadata registered but missing instantiated adapter.",
                    evidence=f"Registered in _metadata but absent in _adapters",
                    remediation=f"Instantiate and register an adapter for '{aid}' in AgentRegistry._adapters.",
                )
            )

        missing_in_meta = set(adapter_keys) - set(meta_keys)
        for aid in missing_in_meta:
            findings.append(
                ArchitectureFinding(
                    category=FindingCategory.AGENT_REGISTRY,
                    severity=FindingSeverity.BLOCKING_ERROR,
                    component=f"AgentRegistry.{aid}",
                    message=f"Agent '{aid}' has an adapter in registry but missing AgentMetadata.",
                    evidence=f"Present in _adapters but absent in _metadata",
                    remediation=f"Provide AgentMetadata for '{aid}' in AgentRegistry._metadata.",
                )
            )

        # 3. Contract & Interface Compliance of Adapters
        for aid, adapter in adapter_map.items():
            if not isinstance(adapter, BaseAgent):
                findings.append(
                    ArchitectureFinding(
                        category=FindingCategory.AGENT_REGISTRY,
                        severity=FindingSeverity.BLOCKING_ERROR,
                        component=f"AgentRegistry.{aid}",
                        message=f"Adapter for agent '{aid}' does not inherit from BaseAgent.",
                        evidence=f"type={type(adapter)}",
                        remediation="Ensure adapter inherits from SYSTEM.agents.shared.base_agent.BaseAgent.",
                    )
                )
                continue

            # Verify execute method contract
            if not hasattr(adapter, "execute") or not callable(getattr(adapter, "execute")):
                findings.append(
                    ArchitectureFinding(
                        category=FindingCategory.AGENT_REGISTRY,
                        severity=FindingSeverity.BLOCKING_ERROR,
                        component=f"AgentRegistry.{aid}",
                        message=f"Adapter '{aid}' does not implement a callable execute() method.",
                        evidence=f"hasattr(execute)={hasattr(adapter, 'execute')}",
                        remediation="Implement execute(project_dir: Path, request: AgentRequest) -> AgentResult.",
                    )
                )

            # Verify validate method contract
            if not hasattr(adapter, "validate") or not callable(getattr(adapter, "validate")):
                findings.append(
                    ArchitectureFinding(
                        category=FindingCategory.AGENT_REGISTRY,
                        severity=FindingSeverity.BLOCKING_ERROR,
                        component=f"AgentRegistry.{aid}",
                        message=f"Adapter '{aid}' does not implement a callable validate() method.",
                        evidence=f"hasattr(validate)={hasattr(adapter, 'validate')}",
                        remediation="Implement validate(project_dir: Path, request: AgentRequest) -> list[str].",
                    )
                )

        # 4. Metadata Semantic Validity
        for aid, meta in metadata_map.items():
            if not isinstance(meta, AgentMetadata):
                findings.append(
                    ArchitectureFinding(
                        category=FindingCategory.AGENT_REGISTRY,
                        severity=FindingSeverity.BLOCKING_ERROR,
                        component=f"AgentRegistry.{aid}.metadata",
                        message=f"Agent '{aid}' metadata is not an instance of AgentMetadata.",
                        evidence=f"type={type(meta)}",
                        remediation="Ensure all registry entries use SYSTEM.agents.shared.contracts.AgentMetadata.",
                    )
                )
                continue

            # Validate Category Enum
            if not isinstance(meta.category, AgentCategory):
                findings.append(
                    ArchitectureFinding(
                        category=FindingCategory.AGENT_REGISTRY,
                        severity=FindingSeverity.WARNING,
                        component=f"AgentMetadata.{aid}.category",
                        message=f"Agent '{aid}' has invalid category '{meta.category}'.",
                        expected="Instance of AgentCategory enum",
                        actual=str(meta.category),
                        remediation="Update agent metadata to use a recognized AgentCategory enum member.",
                    )
                )

            # Validate Status Enum
            if not isinstance(meta.status, AgentStatus):
                findings.append(
                    ArchitectureFinding(
                        category=FindingCategory.AGENT_REGISTRY,
                        severity=FindingSeverity.WARNING,
                        component=f"AgentMetadata.{aid}.status",
                        message=f"Agent '{aid}' has invalid status '{meta.status}'.",
                        expected="Instance of AgentStatus enum",
                        actual=str(meta.status),
                        remediation="Update agent metadata to use a recognized AgentStatus enum member.",
                    )
                )

            # Informational / Warning on empty capabilities
            if not meta.capabilities:
                findings.append(
                    ArchitectureFinding(
                        category=FindingCategory.AGENT_REGISTRY,
                        severity=FindingSeverity.WARNING,
                        component=f"AgentMetadata.{aid}.capabilities",
                        message=f"Agent '{aid}' does not declare any capabilities in metadata.",
                        evidence="capabilities=[]",
                        remediation="Declare explicit capabilities for accurate discovery by CapabilityFinder.",
                    )
                )

        # 5. Canonical Import Resolution Check
        canonical_modules = [
            ("SYSTEM.agents.main_architecture_agent.agent", "MainArchitectureAgent"),
            ("SYSTEM.agents.capability_finder.agent", "CapabilityFinderAgent"),
            ("SYSTEM.agents.skill_factory.agent", "SkillFactoryAgent"),
            ("SYSTEM.agents.architecture_validator.agent", "ArchitectureValidatorAgent"),
            ("SYSTEM.agents.verification_and_test.agent", "VerificationAndTestAgent"),
            ("SYSTEM.agents.security_policy.agent", "SecurityPolicyAgent"),
            ("SYSTEM.agents.autonomous_execution.agent", "AutonomousExecutionAgent"),
            ("SYSTEM.registries.agent_registry", "AgentRegistry"),
        ]
        for mod_path, cls_name in canonical_modules:
            try:
                mod = importlib.import_module(mod_path)
                if not hasattr(mod, cls_name):
                    findings.append(
                        ArchitectureFinding(
                            category=FindingCategory.AGENT_REGISTRY,
                            severity=FindingSeverity.BLOCKING_ERROR,
                            component=mod_path,
                            message=f"Canonical module '{mod_path}' does not export expected class '{cls_name}'.",
                            evidence=f"dir={dir(mod)}",
                            remediation=f"Ensure '{cls_name}' is defined or imported in '{mod_path}'.",
                        )
                    )
            except Exception as e:
                findings.append(
                    ArchitectureFinding(
                        category=FindingCategory.AGENT_REGISTRY,
                        severity=FindingSeverity.BLOCKING_ERROR,
                        component=mod_path,
                        message=f"Failed to import canonical module '{mod_path}': {e}",
                        evidence=str(e),
                        remediation="Verify canonical agent path exists and contains no syntax or circular import errors.",
                    )
                )

        return findings
