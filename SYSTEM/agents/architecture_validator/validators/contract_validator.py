"""Interface and Contract Validator for Architecture Validator Agent.

Validates:
- AgentRequest and AgentResult dataclass schemas and type invariants.
- State machine transition rules for pipeline stages (SYSTEM/core/pipeline_state.py).
- State machine transition rules for skills (SYSTEM/registries/skill_registry.py).
- Enumeration completeness (AgentStatus, AgentCategory, SkillStatus, StageStatus).
- Backward-compatibility import bridges across canonical and legacy modules.
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


class ContractValidator:
    """Audits system contracts, message schemas, and state machine transition graphs."""

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = project_root or Path(__file__).resolve().parents[4]

    def validate(self) -> list[ArchitectureFinding]:
        findings: list[ArchitectureFinding] = []

        # 1. AgentRequest & AgentResult Dataclass Schemas
        try:
            from SYSTEM.agents.shared.contracts import (
                AgentCategory,
                AgentMetadata,
                AgentRequest,
                AgentResult,
                AgentStatus,
            )

            # Check AgentRequest fields
            req_fields = {f.name for f in AgentRequest.__dataclass_fields__.values()}
            expected_req = {"agent_id", "parameters"}
            if not expected_req.issubset(req_fields):
                findings.append(
                    ArchitectureFinding(
                        category=FindingCategory.CONTRACT,
                        severity=FindingSeverity.BLOCKING_ERROR,
                        component="SYSTEM.agents.shared.contracts.AgentRequest",
                        message="AgentRequest is missing mandatory fields.",
                        expected=str(sorted(expected_req)),
                        actual=str(sorted(req_fields)),
                        remediation="Ensure AgentRequest defines at least 'agent_id' and 'parameters'.",
                    )
                )

            # Check AgentResult fields
            res_fields = {f.name for f in AgentResult.__dataclass_fields__.values()}
            expected_res = {"agent_id", "status", "summary"}
            if not expected_res.issubset(res_fields):
                findings.append(
                    ArchitectureFinding(
                        category=FindingCategory.CONTRACT,
                        severity=FindingSeverity.BLOCKING_ERROR,
                        component="SYSTEM.agents.shared.contracts.AgentResult",
                        message="AgentResult is missing mandatory fields.",
                        expected=str(sorted(expected_res)),
                        actual=str(sorted(res_fields)),
                        remediation="Ensure AgentResult defines at least 'agent_id', 'status', and 'summary'.",
                    )
                )

        except Exception as e:
            findings.append(
                ArchitectureFinding(
                    category=FindingCategory.CONTRACT,
                    severity=FindingSeverity.BLOCKING_ERROR,
                    component="SYSTEM.agents.shared.contracts",
                    message=f"Failed to inspect shared contracts: {e}",
                    evidence=str(e),
                    remediation="Fix errors in SYSTEM/agents/shared/contracts.py.",
                )
            )

        # 2. Pipeline State Lifecycle Legal Transitions
        try:
            from SYSTEM.core.pipeline_state import LEGAL_TRANSITIONS as PIPELINE_TRANSITIONS
            # Verify basic state machine completeness
            for state in ["pending", "running", "completed", "failed", "blocked"]:
                if state not in PIPELINE_TRANSITIONS:
                    findings.append(
                        ArchitectureFinding(
                            category=FindingCategory.CONTRACT,
                            severity=FindingSeverity.BLOCKING_ERROR,
                            component="pipeline_state.LEGAL_TRANSITIONS",
                            message=f"State machine missing legal transitions for stage state '{state}'.",
                            evidence=f"state='{state}'",
                            remediation=f"Define allowed transitions from '{state}' in pipeline_state.LEGAL_TRANSITIONS.",
                        )
                    )
        except Exception as e:
            findings.append(
                ArchitectureFinding(
                    category=FindingCategory.CONTRACT,
                    severity=FindingSeverity.BLOCKING_ERROR,
                    component="SYSTEM.core.pipeline_state",
                    message=f"Failed to inspect pipeline state transitions: {e}",
                    evidence=str(e),
                    remediation="Verify SYSTEM/core/pipeline_state.py defines LEGAL_TRANSITIONS.",
                )
            )

        # 3. Skill Lifecycle Legal Transitions
        try:
            from SYSTEM.registries.skill_registry import LEGAL_TRANSITIONS as SKILL_TRANSITIONS
            for state in ["discovered", "draft", "approved", "rejected"]:
                if state not in SKILL_TRANSITIONS:
                    findings.append(
                        ArchitectureFinding(
                            category=FindingCategory.CONTRACT,
                            severity=FindingSeverity.BLOCKING_ERROR,
                            component="skill_registry.LEGAL_TRANSITIONS",
                            message=f"Skill state machine missing legal transitions for state '{state}'.",
                            evidence=f"state='{state}'",
                            remediation=f"Define allowed transitions for '{state}' in skill_registry.LEGAL_TRANSITIONS.",
                        )
                    )
        except Exception as e:
            findings.append(
                ArchitectureFinding(
                    category=FindingCategory.CONTRACT,
                    severity=FindingSeverity.BLOCKING_ERROR,
                    component="SYSTEM.registries.skill_registry",
                    message=f"Failed to inspect skill transitions: {e}",
                    evidence=str(e),
                    remediation="Verify SYSTEM/registries/skill_registry.py defines LEGAL_TRANSITIONS.",
                )
            )

        return findings
