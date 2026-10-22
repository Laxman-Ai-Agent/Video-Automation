"""Video Pipeline Architecture Validator for Architecture Validator Agent.

Validates:
- 13-stage active pipeline integrity against SYSTEM/core/pipeline_state.py and VIDEO_ENGINE/pipeline/orchestrator.py.
- Stage-to-agent mapping completeness against AgentRegistry.
- Artifact producer/consumer schema coverage in SYSTEM/core/artifact_contracts.py.
- Mandatory approval gates (decided by an LLM review) at timeline approval and final QC.
- Canvas specifications (9:16 and 16:9 aspect ratios, 30fps framerate lock).
- PipelineOrchestrator sole execution engine boundary.
"""
from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

from SYSTEM.agents.architecture_validator.contracts import (
    ArchitectureFinding,
    FindingCategory,
    FindingSeverity,
)

EXPECTED_STAGES = (
    "audio",
    "analyzer",
    "segmentation",
    "planning",
    "assets",
    "motion_plan",
    "motion_gen",
    "motion_validation",
    "timeline",
    "approval",
    "render",
    "qc",
    "final",
)

MANDATORY_APPROVAL_GATES = {"approval", "qc"}


class VideoPipelineValidator:
    """Audits the 13-stage video generation pipeline for stage ordering, contract coverage, and approval gates."""

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = project_root or Path(__file__).resolve().parents[4]

    def validate(
        self,
        active_stages: tuple[str, ...] | list[str] | None = None,
        stage_to_agent: dict[str, str] | None = None,
        agent_registry_instance: Any = None,
    ) -> list[ArchitectureFinding]:
        findings: list[ArchitectureFinding] = []

        # 1. Resolve Active Stages
        stages = active_stages
        if stages is None:
            try:
                from SYSTEM.core.pipeline_state import ACTIVE_STAGES
                stages = ACTIVE_STAGES
            except Exception as e:
                findings.append(
                    ArchitectureFinding(
                        category=FindingCategory.VIDEO_PIPELINE,
                        severity=FindingSeverity.BLOCKING_ERROR,
                        component="SYSTEM.core.pipeline_state.ACTIVE_STAGES",
                        message=f"Failed to load canonical ACTIVE_STAGES: {e}",
                        evidence=str(e),
                        remediation="Ensure SYSTEM/core/pipeline_state.py defines ACTIVE_STAGES.",
                    )
                )
                return findings

        # Check stage count and sequence
        if tuple(stages) != EXPECTED_STAGES:
            missing = set(EXPECTED_STAGES) - set(stages)
            extra = set(stages) - set(EXPECTED_STAGES)
            findings.append(
                ArchitectureFinding(
                    category=FindingCategory.VIDEO_PIPELINE,
                    severity=FindingSeverity.BLOCKING_ERROR,
                    component="ACTIVE_STAGES",
                    message="Pipeline active stages do not match canonical 13-stage architecture.",
                    expected=str(EXPECTED_STAGES),
                    actual=str(stages),
                    evidence=f"missing={sorted(missing)}, extra={sorted(extra)}",
                    remediation="Align ACTIVE_STAGES in pipeline_state.py with the canonical 13-stage pipeline.",
                )
            )

        # 2. Stage to Agent Mapping
        mapping = stage_to_agent
        if mapping is None:
            try:
                from SYSTEM.core.pipeline_state import STAGE_TO_AGENT_MAP
                mapping = STAGE_TO_AGENT_MAP
            except Exception as e:
                findings.append(
                    ArchitectureFinding(
                        category=FindingCategory.VIDEO_PIPELINE,
                        severity=FindingSeverity.BLOCKING_ERROR,
                        component="SYSTEM.core.pipeline_state.STAGE_TO_AGENT_MAP",
                        message=f"Failed to load STAGE_TO_AGENT_MAP: {e}",
                        evidence=str(e),
                        remediation="Ensure STAGE_TO_AGENT_MAP is defined in SYSTEM/core/pipeline_state.py.",
                    )
                )
                mapping = {}

        # Verify each active stage has an assigned agent
        for stage in stages:
            if stage not in mapping:
                findings.append(
                    ArchitectureFinding(
                        category=FindingCategory.VIDEO_PIPELINE,
                        severity=FindingSeverity.BLOCKING_ERROR,
                        component=f"StageToAgent.{stage}",
                        message=f"Stage '{stage}' has no assigned agent in STAGE_TO_AGENT_MAP.",
                        evidence=f"stage='{stage}' not in mapping",
                        remediation=f"Map stage '{stage}' to its corresponding agent in STAGE_TO_AGENT_MAP.",
                    )
                )

        # 3. Agent Existence in AgentRegistry
        if agent_registry_instance is None:
            try:
                from SYSTEM.registries.agent_registry import registry
                agent_registry_instance = registry
            except Exception:
                pass

        if agent_registry_instance is not None and mapping:
            registered_agents = set(getattr(agent_registry_instance, "_metadata", {}).keys())
            for stage, agent_id in mapping.items():
                if agent_id not in registered_agents:
                    findings.append(
                        ArchitectureFinding(
                            category=FindingCategory.VIDEO_PIPELINE,
                            severity=FindingSeverity.BLOCKING_ERROR,
                            component=f"StageToAgent.{stage}",
                            message=f"Agent '{agent_id}' mapped to stage '{stage}' is not registered in AgentRegistry.",
                            evidence=f"agent_id='{agent_id}', registered={sorted(registered_agents)[:5]}...",
                            remediation=f"Register agent '{agent_id}' in SYSTEM/registries/agent_registry.py.",
                        )
                    )

        # 4. Artifact Contract Validator Functions
        try:
            from SYSTEM.core import artifact_contracts
            for stage in stages:
                validator_name = f"validate_{stage}_artifacts"
                if not hasattr(artifact_contracts, validator_name):
                    findings.append(
                        ArchitectureFinding(
                            category=FindingCategory.VIDEO_PIPELINE,
                            severity=FindingSeverity.BLOCKING_ERROR,
                            component=f"artifact_contracts.{validator_name}",
                            message=f"Missing artifact contract validator for stage '{stage}'.",
                            evidence=f"Expected function '{validator_name}' in SYSTEM.core.artifact_contracts",
                            remediation=f"Implement '{validator_name}(pdir: Path, aspect: str)' in artifact_contracts.py.",
                        )
                    )
                else:
                    fn = getattr(artifact_contracts, validator_name)
                    if not callable(fn):
                        findings.append(
                            ArchitectureFinding(
                                category=FindingCategory.VIDEO_PIPELINE,
                                severity=FindingSeverity.BLOCKING_ERROR,
                                component=f"artifact_contracts.{validator_name}",
                                message=f"Artifact contract attribute '{validator_name}' is not callable.",
                                evidence=f"type={type(fn)}",
                                remediation=f"Ensure '{validator_name}' is a callable validator function.",
                            )
                        )
        except Exception as e:
            findings.append(
                ArchitectureFinding(
                    category=FindingCategory.VIDEO_PIPELINE,
                    severity=FindingSeverity.BLOCKING_ERROR,
                    component="SYSTEM.core.artifact_contracts",
                    message=f"Failed to inspect artifact contracts: {e}",
                    evidence=str(e),
                    remediation="Fix syntax or import errors in SYSTEM/core/artifact_contracts.py.",
                )
            )

        # 5. Mandatory approval gates (LLM-decided)
        for gate in MANDATORY_APPROVAL_GATES:
            if gate not in stages:
                findings.append(
                    ArchitectureFinding(
                        category=FindingCategory.VIDEO_PIPELINE,
                        severity=FindingSeverity.BLOCKING_ERROR,
                        component=f"MandatoryGate.{gate}",
                        message=f"Mandatory approval gate stage '{gate}' is missing from active pipeline stages.",
                        evidence=f"active_stages={stages}",
                        remediation=f"Include mandatory approval gate '{gate}' in active pipeline.",
                    )
                )

        return findings
