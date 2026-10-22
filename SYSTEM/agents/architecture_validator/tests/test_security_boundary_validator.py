"""Unit tests for SecurityBoundaryValidator."""
from __future__ import annotations

from pathlib import Path

import pytest
from SYSTEM.agents.architecture_validator.contracts import FindingSeverity
from SYSTEM.agents.architecture_validator.validators.security_boundary_validator import (
    FROZEN_ALGORITHM_HASHES,
    SecurityBoundaryValidator,
)


def test_frozen_algorithm_hashes_match_baseline():
    validator = SecurityBoundaryValidator()
    findings = validator.validate()
    blocking = [f for f in findings if f.severity == FindingSeverity.BLOCKING_ERROR]
    assert len(blocking) == 0, f"Frozen algorithm hashes mismatch: {[f.message for f in blocking]}"


def test_detects_tampered_frozen_file(tmp_path):
    # Create fake frozen file with tampered content
    fake_stage = tmp_path / "VIDEO_ENGINE" / "stages"
    fake_stage.mkdir(parents=True)
    (fake_stage / "transcribe.py").write_text("# tampered code", encoding="utf-8")
    (fake_stage / "transcript_review.py").write_text("# tampered code", encoding="utf-8")
    (fake_stage / "scene_segmentation.py").write_text("# tampered code", encoding="utf-8")

    validator = SecurityBoundaryValidator(project_root=tmp_path)
    findings = validator.validate()
    blocking = [f for f in findings if f.severity == FindingSeverity.BLOCKING_ERROR]
    assert len(blocking) >= 1
    assert any("has been modified (SHA-256 mismatch)" in f.message for f in blocking)


def test_detects_missing_frozen_file(tmp_path):
    empty_root = tmp_path
    validator = SecurityBoundaryValidator(project_root=empty_root)
    findings = validator.validate()
    blocking = [f for f in findings if f.severity == FindingSeverity.BLOCKING_ERROR]
    assert len(blocking) == 3
    assert all("is missing" in f.message for f in blocking)
