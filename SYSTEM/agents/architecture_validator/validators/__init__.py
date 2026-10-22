"""Validators package for Architecture Validator Agent."""
from __future__ import annotations

from .agent_registry_validator import AgentRegistryValidator
from .capability_registry_validator import CapabilityRegistryValidator
from .contract_validator import ContractValidator
from .dependency_graph_validator import DependencyGraphValidator
from .security_boundary_validator import SecurityBoundaryValidator

__all__ = [
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
