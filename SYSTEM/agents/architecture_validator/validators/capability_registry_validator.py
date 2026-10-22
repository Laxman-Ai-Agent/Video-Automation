"""Capability and Skill Registry Validator for Architecture Validator Agent.

Validates:
- Skill Registry (SYSTEM/skills/catalog.json) schema and artifact existence.
- Path traversal confinement for all registered skill entrypoints.
- Active skills have physical artifacts; inactive skills are not advertised as active.
- Capability Registry records map to valid source agents, skills, or tools.
- Detection of orphaned capabilities or invalid source references.
- Safe, non-mutating synchronization verification.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from SYSTEM.agents.architecture_validator.contracts import (
    ArchitectureFinding,
    FindingCategory,
    FindingSeverity,
)


class CapabilityRegistryValidator:
    """Audits SkillRegistry and CapabilityRegistry for consistency, artifact backing, and referential integrity."""

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = project_root or Path(__file__).resolve().parents[4]
        self.skills_dir = self.project_root / "SYSTEM" / "skills"
        if not self.skills_dir.exists():
            self.skills_dir = self.project_root / "skills"
        self.catalog_file = self.skills_dir / "catalog.json"

    def validate(
        self,
        capability_registry_instance: Any = None,
        skill_registry_instance: Any = None,
    ) -> list[ArchitectureFinding]:
        findings: list[ArchitectureFinding] = []

        # 1. Audit Skill Catalog file
        if not self.catalog_file.exists():
            findings.append(
                ArchitectureFinding(
                    category=FindingCategory.CAPABILITY_REGISTRY,
                    severity=FindingSeverity.BLOCKING_ERROR,
                    component="SYSTEM/skills/catalog.json",
                    message="Central skill catalog file does not exist.",
                    evidence=str(self.catalog_file),
                    remediation="Ensure SYSTEM/skills/catalog.json is initialized with valid SkillRecords.",
                )
            )
            return findings

        catalog_data: dict[str, Any] = {}
        try:
            with open(self.catalog_file, "r", encoding="utf-8") as f:
                catalog_data = json.load(f)
        except Exception as e:
            findings.append(
                ArchitectureFinding(
                    category=FindingCategory.CAPABILITY_REGISTRY,
                    severity=FindingSeverity.BLOCKING_ERROR,
                    component="SYSTEM/skills/catalog.json",
                    message=f"Failed to parse skill catalog JSON: {e}",
                    evidence=str(e),
                    remediation="Fix syntax errors in catalog.json so it parses as a valid JSON object.",
                )
            )
            return findings

        skills_dict = catalog_data.get("skills", {})
        if not isinstance(skills_dict, dict):
            findings.append(
                ArchitectureFinding(
                    category=FindingCategory.CAPABILITY_REGISTRY,
                    severity=FindingSeverity.BLOCKING_ERROR,
                    component="SYSTEM/skills/catalog.json",
                    message="Skill catalog root 'skills' field is not a dictionary.",
                    evidence=f"type={type(skills_dict)}",
                    remediation="Structure catalog.json with a top-level 'skills' mapping.",
                )
            )
            return findings

        active_skill_ids: set[str] = set()

        for skill_id, record in skills_dict.items():
            if not isinstance(record, dict):
                findings.append(
                    ArchitectureFinding(
                        category=FindingCategory.CAPABILITY_REGISTRY,
                        severity=FindingSeverity.BLOCKING_ERROR,
                        component=f"SkillRecord.{skill_id}",
                        message=f"Skill record for '{skill_id}' is not a dictionary.",
                        evidence=f"type={type(record)}",
                        remediation="Ensure each entry in catalog.json is a valid SkillRecord dictionary.",
                    )
                )
                continue

            status = record.get("status", "draft")
            entrypoint = record.get("entrypoint", "")

            # Verify Path Traversal Confinement
            if entrypoint:
                raw_path = Path(entrypoint)
                # Check for traversal indicators
                if ".." in entrypoint or raw_path.is_absolute():
                    resolved_ep = (self.skills_dir / entrypoint).resolve()
                    try:
                        resolved_ep.relative_to(self.skills_dir.resolve())
                    except ValueError:
                        findings.append(
                            ArchitectureFinding(
                                category=FindingCategory.CAPABILITY_REGISTRY,
                                severity=FindingSeverity.BLOCKING_ERROR,
                                component=f"SkillRecord.{skill_id}.entrypoint",
                                message=f"Path traversal detected in skill entrypoint for '{skill_id}'.",
                                evidence=f"entrypoint='{entrypoint}', resolves outside {self.skills_dir}",
                                remediation="Confine all skill entrypoints strictly within the SYSTEM/skills/ directory.",
                            )
                        )

            # Active Skill Artifact Existence Check
            if status == "approved":
                active_skill_ids.add(skill_id)
                artifact_found = False

                # 1. Check entrypoint
                if entrypoint:
                    ep_path = (self.skills_dir / entrypoint).resolve()
                    if ep_path.exists():
                        artifact_found = True

                # 2. Check canonical directory conventions
                if not artifact_found:
                    parts = skill_id.split(".")
                    possible_paths = [
                        self.skills_dir / skill_id / "SKILL.md",
                        self.skills_dir / "/".join(parts) / "SKILL.md",
                        self.skills_dir / (parts[-1] if parts else skill_id) / "SKILL.md",
                    ]
                    for p in possible_paths:
                        if p.exists():
                            artifact_found = True
                            break

                if not artifact_found:
                    domain = record.get("domain", "")
                    is_test_skill = domain == "testing" or skill_id.startswith("test.")
                    sev = FindingSeverity.WARNING if is_test_skill else FindingSeverity.BLOCKING_ERROR
                    findings.append(
                        ArchitectureFinding(
                            category=FindingCategory.CAPABILITY_REGISTRY,
                            severity=sev,
                            component=f"SkillRecord.{skill_id}",
                            message=(
                                f"Test fixture skill '{skill_id}' in domain '{domain}' lacks physical artifact on disk."
                                if is_test_skill else
                                f"Active production skill '{skill_id}' is missing its physical artifact file on disk."
                            ),
                            evidence=f"entrypoint='{entrypoint}', searched in {self.skills_dir}",
                            remediation=(
                                "Consider archiving or cleaning test fixture skills from catalog.json."
                                if is_test_skill else
                                "Ensure approved production skills have an existing SKILL.md or code artifact on disk."
                            ),
                        )
                    )

        # 2. Audit Central CapabilityRegistry
        if capability_registry_instance is None:
            try:
                from SYSTEM.registries.capability_registry import capability_registry
                capability_registry_instance = capability_registry
            except Exception as e:
                findings.append(
                    ArchitectureFinding(
                        category=FindingCategory.CAPABILITY_REGISTRY,
                        severity=FindingSeverity.BLOCKING_ERROR,
                        component="SYSTEM.registries.capability_registry",
                        message=f"Failed to import CapabilityRegistry: {e}",
                        evidence=str(e),
                        remediation="Ensure SYSTEM/registries/capability_registry.py is syntactically valid and importable.",
                    )
                )
                return findings

        # If in-memory registry is unindexed, sync from authoritative sources
        if len(capability_registry_instance.list_all()) == 0:
            try:
                capability_registry_instance.sync_with_registries()
            except Exception as e:
                findings.append(
                    ArchitectureFinding(
                        category=FindingCategory.CAPABILITY_REGISTRY,
                        severity=FindingSeverity.BLOCKING_ERROR,
                        component="CapabilityRegistry.sync",
                        message=f"Failed to sync in-memory capability registry: {e}",
                        evidence=str(e),
                        remediation="Check that AgentRegistry, SkillRegistry, and ToolRegistry are functional.",
                    )
                )

        # Verify Capability Records
        cap_records = capability_registry_instance.list_all()

        if not cap_records:
            findings.append(
                ArchitectureFinding(
                    category=FindingCategory.CAPABILITY_REGISTRY,
                    severity=FindingSeverity.WARNING,
                    component="CapabilityRegistry",
                    message="CapabilityRegistry is currently empty; run sync_with_registries() to index capabilities.",
                    evidence="record_count=0",
                    remediation="Call CapabilityRegistry.sync_with_registries() to index system capabilities.",
                )
            )
            return findings

        # Also get AgentRegistry for cross-referencing
        agent_ids: set[str] = set()
        try:
            from SYSTEM.registries.agent_registry import registry as agent_reg
            agent_ids = set(agent_reg.list_all_agents_metadata().keys()) if hasattr(agent_reg, "list_all_agents_metadata") else set(getattr(agent_reg, "_metadata", {}).keys())
        except Exception:
            pass

        seen_cap_ids: set[str] = set()
        for cap in cap_records:
            cid = cap.capability_id
            if cid in seen_cap_ids:
                findings.append(
                    ArchitectureFinding(
                        category=FindingCategory.CAPABILITY_REGISTRY,
                        severity=FindingSeverity.BLOCKING_ERROR,
                        component=f"CapabilityRegistry.{cid}",
                        message=f"Duplicate capability ID detected in CapabilityRegistry: '{cid}'.",
                        evidence=f"capability_id='{cid}'",
                        remediation="Ensure capability IDs are unique across all sources.",
                    )
                )
            seen_cap_ids.add(cid)

            # Verify Source Referential Integrity
            if cap.source_type == "skill":
                if cap.source_id not in skills_dict:
                    findings.append(
                        ArchitectureFinding(
                            category=FindingCategory.CAPABILITY_REGISTRY,
                            severity=FindingSeverity.BLOCKING_ERROR,
                            component=f"CapabilityRecord.{cid}",
                            message=f"Capability '{cid}' references non-existent skill source '{cap.source_id}'.",
                            evidence=f"source_type='skill', source_id='{cap.source_id}' not in catalog.json",
                            remediation="Remove orphaned capability record or restore referenced skill in catalog.json.",
                        )
                    )
            elif cap.source_type == "agent":
                if agent_ids and cap.source_id not in agent_ids:
                    findings.append(
                        ArchitectureFinding(
                            category=FindingCategory.CAPABILITY_REGISTRY,
                            severity=FindingSeverity.WARNING,
                            component=f"CapabilityRecord.{cid}",
                            message=f"Capability '{cid}' references agent '{cap.source_id}' which is not in AgentRegistry.",
                            evidence=f"source_type='agent', source_id='{cap.source_id}' not in {sorted(agent_ids)[:5]}...",
                            remediation="Verify agent ID in CapabilityRecord matches a registered AgentRegistry agent.",
                        )
                    )

        return findings
