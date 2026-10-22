"""Unit tests for CapabilityRegistryValidator."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from SYSTEM.agents.architecture_validator.contracts import FindingSeverity
from SYSTEM.agents.architecture_validator.validators.capability_registry_validator import (
    CapabilityRegistryValidator,
)
from SYSTEM.registries.capability_registry import CapabilityRecord, CapabilityRegistry


def test_detects_path_traversal_in_skill_entrypoint(tmp_path):
    # Setup temporary skills dir with catalog
    skills_dir = tmp_path / "SYSTEM" / "skills"
    skills_dir.mkdir(parents=True)
    catalog_path = skills_dir / "catalog.json"

    catalog_data = {
        "version": 1,
        "skills": {
            "traversal.skill": {
                "skill_id": "traversal.skill",
                "name": "Traversal Skill",
                "status": "approved",
                "domain": "video",
                "entrypoint": "../../../outside/secret.py",
            }
        },
    }
    catalog_path.write_text(json.dumps(catalog_data), encoding="utf-8")

    validator = CapabilityRegistryValidator(project_root=tmp_path)
    mock_cap_reg = MagicMock()
    mock_cap_reg.list_all.return_value = []

    findings = validator.validate(capability_registry_instance=mock_cap_reg)
    blocking = [f for f in findings if f.severity == FindingSeverity.BLOCKING_ERROR]
    assert any("Path traversal detected" in f.message for f in blocking)


def test_detects_missing_artifact_for_approved_production_skill(tmp_path):
    skills_dir = tmp_path / "SYSTEM" / "skills"
    skills_dir.mkdir(parents=True)
    catalog_path = skills_dir / "catalog.json"

    catalog_data = {
        "version": 1,
        "skills": {
            "prod.missing_artifact": {
                "skill_id": "prod.missing_artifact",
                "name": "Missing Artifact Skill",
                "status": "approved",
                "domain": "production_video",
                "entrypoint": "nonexistent/SKILL.md",
            }
        },
    }
    catalog_path.write_text(json.dumps(catalog_data), encoding="utf-8")

    validator = CapabilityRegistryValidator(project_root=tmp_path)
    mock_cap_reg = MagicMock()
    mock_cap_reg.list_all.return_value = []

    findings = validator.validate(capability_registry_instance=mock_cap_reg)
    blocking = [f for f in findings if f.severity == FindingSeverity.BLOCKING_ERROR]
    assert any("missing its physical artifact file on disk" in f.message for f in blocking)


def test_detects_orphaned_capability_referencing_nonexistent_skill():
    validator = CapabilityRegistryValidator()
    mock_cap_reg = MagicMock()
    orphan_cap = CapabilityRecord(
        capability_id="orphan_skill_cap",
        name="Orphan",
        description="References ghost skill",
        source_type="skill",
        source_id="nonexistent.ghost.skill",
    )
    mock_cap_reg.list_all.return_value = [orphan_cap]

    findings = validator.validate(capability_registry_instance=mock_cap_reg)
    blocking = [f for f in findings if f.severity == FindingSeverity.BLOCKING_ERROR]
    assert any("references non-existent skill source" in f.message for f in blocking)
