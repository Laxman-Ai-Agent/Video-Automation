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
    VideoPipelineValidator,
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
    "VideoPipelineValidator",
]
