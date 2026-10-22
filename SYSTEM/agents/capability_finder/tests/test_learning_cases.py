"""Unit tests for CaseCollector and OutcomeAnalyzer."""
import json
import tempfile
from pathlib import Path
import pytest

from SYSTEM.agents.capability_finder.learning.case_collector import CaseCollector, LearningCase
from SYSTEM.agents.capability_finder.learning.outcome_analyzer import OutcomeAnalyzer, OutcomeAttribution


def test_case_collector_recording_and_sanitization(tmp_path: Path):
    storage_file = tmp_path / "cases.jsonl"
    collector = CaseCollector(storage_file=storage_file)

    raw_case = LearningCase(
        task_id="task_test_01",
        parsed_requirement={"domain": "audio", "query": "api_key=sk-1234567890abcdef1234567890abcdef"},
        discovery_result={"token": "Bearer ghp_abcdefghijklmnopqrstuvwxyz123456"},
        execution_outcome={"status": "failed", "error": "password=SuperSecretPassword123!"},
        environment_state={"env_var": "aws_secret_key=secret"},
    )

    case_id = collector.record_case(raw_case)
    assert case_id.startswith("lcase_") or case_id.startswith("case_")

    # Verify JSONL content on disk is sanitized
    with open(storage_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    assert len(lines) == 1
    stored = json.loads(lines[0])

    assert "sk-1234567890abcdef1234567890abcdef" not in lines[0]
    assert "SuperSecretPassword123!" not in lines[0]
    assert "[REDACTED" in lines[0]

    retrieved = collector.get_case(case_id)
    assert retrieved is not None
    assert retrieved.task_id == "task_test_01"


def test_outcome_analyzer_attributions():
    analyzer = OutcomeAnalyzer()

    # 1. Successful execution
    attr_success = analyzer.analyze_outcome(
        discovery_result={"recommended_action": "REUSE", "suggested_delegate_id": "test_skill"},
        execution_outcome={"status": "completed", "output": {"duration": 10.0}},
        execution_error=None,
    )
    assert attr_success.discovery_succeeded is True
    assert attr_success.task_succeeded is True
    assert attr_success.primary_failure_category == "NONE"

    # 2. Environmental failure (missing binary)
    attr_env = analyzer.analyze_outcome(
        discovery_result={"recommended_action": "REUSE", "suggested_delegate_id": "ffmpeg_tool"},
        execution_outcome={"status": "failed"},
        execution_error="FileNotFoundError: ffmpeg binary not found in PATH",
    )
    assert attr_env.discovery_succeeded is True
    assert attr_env.task_succeeded is False
    assert attr_env.primary_failure_category == "ENVIRONMENTAL"

    # 3. Input defect
    attr_input = analyzer.analyze_outcome(
        discovery_result={"recommended_action": "REUSE", "suggested_delegate_id": "audio_tool"},
        execution_outcome={"status": "failed"},
        execution_error="Corrupt media file header or unsupported codec",
    )
    assert attr_input.primary_failure_category == "INPUT_DEFECT"

    # 4. Capability mismatch
    attr_mismatch = analyzer.analyze_outcome(
        discovery_result={"recommended_action": "REUSE", "suggested_delegate_id": "wrong_delegate"},
        execution_outcome={"status": "failed"},
        execution_error="AttributeError: delegate does not support required method generate_subtitles",
    )
    assert attr_mismatch.discovery_succeeded is False
    assert attr_mismatch.task_succeeded is False
    assert attr_mismatch.primary_failure_category == "CAPABILITY_MISMATCH"
