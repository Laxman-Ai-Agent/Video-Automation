"""Unit tests for DependencyGraphValidator."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from SYSTEM.agents.architecture_validator.contracts import FindingSeverity
from SYSTEM.agents.architecture_validator.validators.dependency_graph_validator import (
    DependencyGraphValidator,
)


def test_acyclic_graph_passes():
    validator = DependencyGraphValidator()
    # A -> B -> C (A runs before B, B runs before C)
    dag = {
        "A": (),
        "B": ("A",),
        "C": ("B",),
    }
    findings = validator.validate(
        agent_registry_instance=MagicMock(_metadata={}),
        custom_pipeline_deps=dag,
    )
    blocking = [f for f in findings if f.severity == FindingSeverity.BLOCKING_ERROR]
    assert len(blocking) == 0


def test_forbidden_cycle_detected():
    validator = DependencyGraphValidator()
    # Cycle: A depends on C, B depends on A, C depends on B
    cyclic_graph = {
        "A": ("C",),
        "B": ("A",),
        "C": ("B",),
    }
    findings = validator.validate(
        agent_registry_instance=MagicMock(_metadata={}),
        custom_pipeline_deps=cyclic_graph,
    )
    blocking = [f for f in findings if f.severity == FindingSeverity.BLOCKING_ERROR]
    assert any("Forbidden cycle detected" in f.message for f in blocking)
    # Check cycle path reported
    cycle_finding = next(f for f in blocking if "Forbidden cycle detected" in f.message)
    assert "A -> B -> C -> A" in cycle_finding.evidence or "B -> C -> A -> B" in cycle_finding.evidence


def test_detects_unknown_dependency_target():
    validator = DependencyGraphValidator()
    graph_with_unknown = {
        "A": (),
        "B": ("non_existent_stage_xyz",),
    }
    findings = validator.validate(
        agent_registry_instance=MagicMock(_metadata={}),
        custom_pipeline_deps=graph_with_unknown,
    )
    blocking = [f for f in findings if f.severity == FindingSeverity.BLOCKING_ERROR]
    assert any("depends on non-existent stage" in f.message for f in blocking)


def test_cycle_detector_terminates_on_bounded_complex_graphs():
    validator = DependencyGraphValidator()
    # Graph with 20 nodes in linear chain
    chain = {f"node_{i}": (f"node_{i-1}",) if i > 0 else () for i in range(20)}
    cycles = validator._find_cycles(chain)
    assert cycles == []

    # Inject loop between node_15 and node_10
    chain["node_10"] = ("node_15",)
    cycles = validator._find_cycles(chain)
    assert len(cycles) > 0
