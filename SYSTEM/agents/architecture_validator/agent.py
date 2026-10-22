"""Architecture Validator System Agent (Canonical).

Responsible for:
1. Agent Registry structural consistency and contract verification.
2. Skill Registry and Capability Registry integrity, artifact presence, and path confinement.
3. Dependency graph integrity, cycle detection, and reachability.
4. Video pipeline 12-stage ordering, artifact contracts, and the mandatory LLM-decided approval gates.
5. Interface and contract schema compliance.
6. Architecture and security boundary enforcement (sole execution engine, frozen file SHA-256).
7. Read-only audit execution by default.

Canonical Location: SYSTEM/agents/architecture_validator/agent.py
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from SYSTEM.agents.architecture_validator.contracts import (
    ArchitectureFinding,
    AuditResult,
    FindingCategory,
    FindingSeverity,
    ValidationMode,
)
from SYSTEM.agents.architecture_validator.validators import (
    AgentRegistryValidator,
    CapabilityRegistryValidator,
    ContractValidator,
    DependencyGraphValidator,
    SecurityBoundaryValidator,
)
from SYSTEM.agents.shared.base_agent import BaseAgent
from SYSTEM.core import integrations
from SYSTEM.agents.shared.contracts import (
    AgentCategory,
    AgentMetadata,
    AgentRequest,
    AgentResult,
    AgentStatus,
)

logger = logging.getLogger("architecture_validator.agent")

SUPPORTED_ACTIONS: set[str] = {
    "full_architecture_audit",
    "agent_registry_audit",
    "capability_registry_audit",
    "dependency_graph_audit",
    "video_pipeline_audit",
    "contract_audit",
    "security_boundary_audit",
    "targeted_audit",
}


class _NoPipelineValidator:
    """No domain project is connected: it has no pipeline, so there is nothing to validate."""

    def validate(self, *args, **kwargs) -> list:
        return []


class ArchitectureValidatorAgent(BaseAgent):
    """System agent specialized in evidence-based architecture validation and integrity audits."""

    def __init__(self, metadata: AgentMetadata | None = None) -> None:
        if metadata is None:
            metadata = AgentMetadata(
                agent_id="architecture_validator",
                name="Architecture Validator Agent",
                version="1.0.0",
                category=AgentCategory.SYSTEM_SUBAGENT,
                status=AgentStatus.IMPLEMENTED,
                purpose="Audits architectural consistency, agent and capability registries, dependency graphs, video pipeline integrity, and security boundaries.",
                capabilities=[
                    "agent-registry-validation",
                    "capability-registry-validation",
                    "dependency-graph-validation",
                    "video-pipeline-validation",
                    "contract-validation",
                    "security-boundary-validation",
                    "full-architecture-audit",
                ],
                allowed_tools=[
                    "agent_registry",
                    "skill_registry",
                    "capability_registry",
                    "ast_scanner",
                    "hash_verifier",
                ],
                owner="system-core",
            )
        super().__init__(metadata)
        self.agent_validator = AgentRegistryValidator()
        self.capability_validator = CapabilityRegistryValidator()
        self.dependency_validator = DependencyGraphValidator()
        self.contract_validator = ContractValidator()
        self.security_validator = SecurityBoundaryValidator()

    @property
    def pipeline_validator(self):
        """The connected domain project's pipeline validator (the video project's), looked up on use so a project that connects later is honoured;
        with none connected there is no pipeline to validate."""
        validator_cls = integrations.get("pipeline_validator")
        return validator_cls() if validator_cls is not None else _NoPipelineValidator()

    def validate(self, project_dir: Path, request: AgentRequest) -> list[str]:
        """Validates that the incoming request specifies a supported audit action."""
        action = request.parameters.get("action", "full_architecture_audit")
        if action not in SUPPORTED_ACTIONS:
            return [
                f"Unknown architecture validation action '{action}'. "
                f"Supported actions: {', '.join(sorted(SUPPORTED_ACTIONS))}"
            ]
        return []

    def execute(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        """Executes the requested architecture validation audit in read-only mode."""
        start_time = time.time()
        action: ValidationMode = request.parameters.get("action", "full_architecture_audit")
        audit_res = AuditResult(action=action)

        findings: list[ArchitectureFinding] = []

        try:
            if action == "agent_registry_audit":
                findings.extend(self.agent_validator.validate())
            elif action == "capability_registry_audit":
                findings.extend(self.capability_validator.validate())
            elif action == "dependency_graph_audit":
                findings.extend(self.dependency_validator.validate())
            elif action == "video_pipeline_audit":
                findings.extend(self.pipeline_validator.validate())
            elif action == "contract_audit":
                findings.extend(self.contract_validator.validate())
            elif action == "security_boundary_audit":
                findings.extend(self.security_validator.validate())
            elif action == "targeted_audit":
                target = request.parameters.get("target", "all")
                findings.extend(self._execute_targeted_audit(target, request.parameters))
            elif action == "full_architecture_audit":
                findings.extend(self.agent_validator.validate())
                findings.extend(self.capability_validator.validate())
                findings.extend(self.dependency_validator.validate())
                findings.extend(self.pipeline_validator.validate())
                findings.extend(self.contract_validator.validate())
                findings.extend(self.security_validator.validate())
            else:
                findings.append(
                    ArchitectureFinding(
                        category=FindingCategory.CONTRACT,
                        severity=FindingSeverity.BLOCKING_ERROR,
                        component="ArchitectureValidatorAgent",
                        message=f"Unsupported audit action '{action}'.",
                        remediation=f"Use one of: {', '.join(sorted(SUPPORTED_ACTIONS))}",
                    )
                )
        except Exception as e:
            logger.exception("Unexpected exception during architecture audit execution")
            findings.append(
                ArchitectureFinding(
                    category=FindingCategory.SECURITY_BOUNDARY,
                    severity=FindingSeverity.BLOCKING_ERROR,
                    component="ArchitectureValidatorAgent",
                    message=f"Validator internal failure during audit: {e}",
                    evidence=str(e),
                    remediation="Inspect validator stack trace and fix unexpected runtime exception.",
                )
            )

        duration_ms = (time.time() - start_time) * 1000.0
        audit_res.findings = findings
        audit_res.duration_ms = duration_ms
        audit_res.finalize_status()

        # Build concise narrative summary
        b_count = audit_res.blocking_error_count
        w_count = audit_res.warning_count
        i_count = audit_res.info_count

        if b_count > 0:
            summary = (
                f"Architecture audit '{action}' FAILED with {b_count} blocking error(s) "
                f"and {w_count} warning(s) in {duration_ms:.1f}ms."
            )
            result_status = "failed"
            error_msg = "; ".join(
                f"[{f.component}] {f.message}"
                for f in findings
                if f.severity == FindingSeverity.BLOCKING_ERROR
            )
        elif w_count > 0:
            summary = (
                f"Architecture audit '{action}' completed with {w_count} warning(s) "
                f"and 0 blocking errors in {duration_ms:.1f}ms."
            )
            result_status = "succeeded"
            error_msg = None
        else:
            summary = (
                f"Architecture audit '{action}' PASSED: all checks verified clean "
                f"({i_count} info observations) in {duration_ms:.1f}ms."
            )
            result_status = "succeeded"
            error_msg = None

        audit_res.summary = summary

        return AgentResult(
            agent_id=self.agent_id,
            stage_id=request.stage_id or "system",
            project_id=request.project_id or "system",
            status=result_status,
            summary=summary,
            error=error_msg,
            metadata={
                "audit_result": audit_res.to_dict(),
                "action": action,
                "status": audit_res.status,
                "duration_ms": duration_ms,
                "blocking_error_count": b_count,
                "warning_count": w_count,
                "info_count": i_count,
            },
        )

    def _execute_targeted_audit(self, target: str, parameters: dict[str, Any]) -> list[ArchitectureFinding]:
        """Executes targeted audits on specific components."""
        findings: list[ArchitectureFinding] = []
        if target in ("agent_registry", "agents"):
            findings.extend(self.agent_validator.validate())
        elif target in ("capability_registry", "skills", "capabilities"):
            findings.extend(self.capability_validator.validate())
        elif target in ("dependency_graph", "dependencies", "cycles"):
            findings.extend(self.dependency_validator.validate())
        elif target in ("video_pipeline", "pipeline", "stages"):
            findings.extend(self.pipeline_validator.validate())
        elif target in ("contracts", "schemas"):
            findings.extend(self.contract_validator.validate())
        elif target in ("security_boundary", "frozen_files"):
            findings.extend(self.security_validator.validate())
        else:
            findings.append(
                ArchitectureFinding(
                    category=FindingCategory.CONTRACT,
                    severity=FindingSeverity.WARNING,
                    component=f"TargetedAudit.{target}",
                    message=f"Target '{target}' not recognized; fell back to full architecture audit.",
                    remediation="Specify a valid target: agents, skills, dependencies, pipeline, contracts, or security_boundary.",
                )
            )
            findings.extend(self.agent_validator.validate())
            findings.extend(self.capability_validator.validate())
            findings.extend(self.dependency_validator.validate())
            findings.extend(self.pipeline_validator.validate())
            findings.extend(self.contract_validator.validate())
            findings.extend(self.security_validator.validate())
        return findings
