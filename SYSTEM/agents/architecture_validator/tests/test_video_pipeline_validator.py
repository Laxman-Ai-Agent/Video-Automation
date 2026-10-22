"""Unit tests for VideoPipelineValidator."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from SYSTEM.agents.architecture_validator.contracts import FindingSeverity
from SYSTEM.agents.architecture_validator.validators.video_pipeline_validator import (
    EXPECTED_STAGES,
    VideoPipelineValidator,
)


def test_canonical_13_stages_pass():
    validator = VideoPipelineValidator()
    # Real 13 stages
    findings = validator.validate()
    blocking = [f for f in findings if f.severity == FindingSeverity.BLOCKING_ERROR]
    assert len(blocking) == 0, f"Unexpected blocking errors: {[f.message for f in blocking]}"


def test_detects_a_stage_list_that_is_not_canonical():
    validator = VideoPipelineValidator()
    # Missing stages
    incomplete_stages = ("audio", "analyzer", "segmentation")
    findings = validator.validate(active_stages=incomplete_stages)
    blocking = [f for f in findings if f.severity == FindingSeverity.BLOCKING_ERROR]
    assert any("do not match canonical 13-stage architecture" in f.message for f in blocking)


def test_detects_missing_mandatory_human_gate():
    validator = VideoPipelineValidator()
    # all stages but replace approval and qc
    tampered_stages = list(EXPECTED_STAGES)
    tampered_stages[tampered_stages.index("approval")] = "auto_approve"
    tampered_stages[tampered_stages.index("qc")] = "auto_qc"

    findings = validator.validate(active_stages=tuple(tampered_stages))
    blocking = [f for f in findings if f.severity == FindingSeverity.BLOCKING_ERROR]
    assert any("Mandatory approval gate stage 'approval' is missing" in f.message for f in blocking)
    assert any("Mandatory approval gate stage 'qc' is missing" in f.message for f in blocking)


def test_detects_missing_stage_to_agent_mapping():
    validator = VideoPipelineValidator()
    tampered_map = {"audio": "audio_input"}  # missing 11 stages
    findings = validator.validate(stage_to_agent=tampered_map)
    blocking = [f for f in findings if f.severity == FindingSeverity.BLOCKING_ERROR]
    assert any("has no assigned agent in STAGE_TO_AGENT_MAP" in f.message for f in blocking)
