"""Canonical Architecture Validator System Agent Package.

Provides:
- ArchitectureValidatorAgent
- FindingSeverity, FindingCategory, ArchitectureFinding, AuditResult
- Specialized validators
"""
from __future__ import annotations

from .agent import ArchitectureValidatorAgent
from .contracts import (
    ArchitectureFinding,
    AuditResult,
    FindingCategory,
    FindingSeverity,
    ValidationMode,
)
from .validators import (
    AgentRegistryValidator,
    CapabilityRegistryValidator,
    ContractValidator,
    DependencyGraphValidator,
    SecurityBoundaryValidator,
)

__all__ = [
    "ArchitectureValidatorAgent",
    "ArchitectureFinding",
    "AuditResult",
    "FindingCategory",
    "FindingSeverity",
    "ValidationMode",
    "AgentRegistryValidator",
    "CapabilityRegistryValidator",
    "ContractValidator",
    "DependencyGraphValidator",
    "SecurityBoundaryValidator",
]


def __getattr__(name: str):
    """VideoPipelineValidator belongs to the video project: it is available here only while that project is connected."""
    if name == "VideoPipelineValidator":
        from SYSTEM.core import integrations
        cls = integrations.get("pipeline_validator")
        if cls is not None:
            return cls
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
