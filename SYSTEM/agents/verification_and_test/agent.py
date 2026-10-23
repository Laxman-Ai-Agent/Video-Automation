"""Canonical Verification & Test Agent for LAXMAN-AUTONOMOUS MASTER SYSTEM.

Responsible for:
1. Change and requirement verification with component mapping.
2. Controlled test execution, output bounding, and result capture.
3. Diagnostic root-cause attribution without automatic code modification (strictly read-only).
4. Evidence-based verdicts (PASS, FAIL, BLOCKED, CONDITIONAL).
5. Integration with Main Architecture Agent and system registries.

Canonically located at: SYSTEM/agents/verification_and_test/agent.py
"""
from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path
from typing import Any

from SYSTEM.agents.shared.base_agent import BaseAgent
from SYSTEM.agents.shared.contracts import (
    AgentCategory,
    AgentMetadata,
    AgentRequest,
    AgentResult,
    AgentStatus,
)
from SYSTEM.agents.verification_and_test.component_mapper import ComponentMapper
from SYSTEM.agents.verification_and_test.contracts import (
    CheckResult,
    FailureCategory,
    TestExecutionStatus,
    VerificationReport,
    VerificationVerdict,
)
from SYSTEM.agents.verification_and_test.diagnostician import Diagnostician
from SYSTEM.agents.verification_and_test.test_executor import TestExecutor

logger = logging.getLogger("verification_and_test.agent")

SUPPORTED_ACTIONS: set[str] = {
    "verify",
    "run_tests",
    "diagnose_failure",
    "verify_regression",
    "status",
}


class VerificationAndTestAgent(BaseAgent):
    """System agent specialized in evidence-driven verification, test execution, and failure diagnosis."""

    def __init__(self, metadata: AgentMetadata | None = None, project_root: Path | None = None) -> None:
        if metadata is None:
            metadata = AgentMetadata(
                agent_id="verification_and_test",
                name="Verification & Test Agent",
                version="1.0.0",
                category=AgentCategory.SYSTEM_SUBAGENT,
                status=AgentStatus.IMPLEMENTED,
                purpose="Executes evidence-driven verification, component-mapped testing, failure diagnosis, and regression protection for the video automation system.",
                capabilities=[
                    "change-verification",
                    "component-test-mapping",
                    "test-execution",
                    "result-capture",
                    "failure-diagnosis",
                    "regression-protection",
                    "evidence-based-verdict",
                ],
                allowed_tools=[
                    "pytest_runner",
                    "hash_verifier",
                    "agent_registry",
                    "component_mapper",
                    "diagnostician",
                ],
                owner="system-core",
            )
        super().__init__(metadata)
        self.project_root = project_root or Path(__file__).resolve().parents[3]
        self.component_mapper = ComponentMapper(self.project_root)
        self.test_executor = TestExecutor(self.project_root)
        self.diagnostician = Diagnostician()

    def validate(self, project_dir: Path, request: AgentRequest) -> list[str]:
        """Validates that the verification request specifies a supported action and valid parameters."""
        action = request.parameters.get("action", "verify")
        if action not in SUPPORTED_ACTIONS:
            return [f"Unknown verification action '{action}'. Supported actions: {sorted(SUPPORTED_ACTIONS)}"]

        if action == "run_tests":
            targets = request.parameters.get("targets")
            components = request.parameters.get("components")
            changed_files = request.parameters.get("changed_files")
            if not targets and not components and not changed_files:
                return ["Action 'run_tests' requires at least one of 'targets', 'components', or 'changed_files'."]

        return []

    def execute(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        """Executes verification, test running, failure diagnosis, or hash validation."""
        action = request.parameters.get("action", "verify")

        if action == "status":
            return self._handle_status(request)
        elif action == "diagnose_failure":
            return self._handle_diagnose_failure(request)
        elif action == "run_tests":
            return self._handle_run_tests(request)
        elif action == "verify_regression":
            return self._handle_verify_regression(request)
        elif action == "verify":
            return self._handle_verify(request)
        else:
            return AgentResult(
                agent_id=self.agent_id,
                status="failed",
                error=f"Unsupported verification action: '{action}'",
            )

    # -------------------------------------------------------------------------
    # Handlers
    # -------------------------------------------------------------------------

    def _handle_status(self, request: AgentRequest) -> AgentResult:
        return AgentResult(
            agent_id=self.agent_id,
            status="succeeded",
            summary="Verification & Test Agent active and operational.",
            metadata={
                "agent_id": self.agent_id,
                "status": "ready",
                "capabilities": self.metadata.capabilities,
                "allowed_tools": self.metadata.allowed_tools,
                "supported_actions": sorted(SUPPORTED_ACTIONS),
            },
        )

    def _handle_run_tests(self, request: AgentRequest) -> AgentResult:
        targets: list[str] = request.parameters.get("targets", [])
        components: list[str] = request.parameters.get("components", [])
        changed_files: list[str] = request.parameters.get("changed_files", [])
        timeout_seconds: int = request.parameters.get("timeout_seconds", 60)

        # Resolve targets if not explicitly given
        if not targets:
            targets = self.component_mapper.resolve_test_targets(components, changed_files)

        checks: list[CheckResult] = []

        for target in targets:
            checks.append(self.test_executor.execute_pytest_target(target, timeout_seconds=timeout_seconds))

        diagnoses = self.diagnostician.diagnose_failures(checks)
        verdict = self._determine_verdict(checks, unverified_reqs=[])

        report = VerificationReport(
            request_id=request.correlation_id or f"req_{uuid.uuid4().hex[:8]}",
            project_id=request.project_id or "system",
            correlation_id=request.correlation_id or "",
            revision=self._get_git_revision(),
            components_covered=list({c.component for c in checks}),
            requirements_verified=[f"Execute test target '{t}'" for t in targets],
            unverified_requirements=[],
            checks=checks,
            failure_diagnoses=diagnoses,
            verdict=verdict,
            verdict_explanation=f"Executed {len(checks)} check(s): {sum(1 for c in checks if c.is_successful)} passed, {sum(1 for c in checks if not c.is_successful)} failed.",
        )

        return AgentResult(
            agent_id=self.agent_id,
            status="succeeded" if verdict == VerificationVerdict.PASS else "failed",
            summary=f"Test run completed with verdict {verdict.value}: {report.verdict_explanation}",
            error=None if verdict == VerificationVerdict.PASS else report.verdict_explanation,
            metadata={"report": report.to_dict()},
        )

    def _handle_verify_regression(self, request: AgentRequest) -> AgentResult:
        """Runs authoritative core system regression targets."""
        regression_targets = [
            "tests/test_phase1_system_agents_restructuring.py",
            "tests/test_agent_architecture_reorg.py",
            "tests/test_phase5_architecture_validator.py",
        ]
        request.parameters["targets"] = regression_targets
        return self._handle_run_tests(request)

    def _handle_diagnose_failure(self, request: AgentRequest) -> AgentResult:
        """Processes previous failure output or error messages and attributes root causes."""
        stdout = request.parameters.get("stdout", "")
        stderr = request.parameters.get("stderr", "")
        component = request.parameters.get("component", "unknown")
        check_id = request.parameters.get("check_id", "diagnostic_check")

        mock_check = CheckResult(
            check_id=check_id,
            component=component,
            check_type="pytest",
            status=TestExecutionStatus.EXECUTED,
            exit_code=1,
            stdout=stdout,
            stderr=stderr,
            failed_count=1,
        )
        diagnoses = self.diagnostician.diagnose_failures([mock_check])
        primary_diag = diagnoses[0] if diagnoses else None

        return AgentResult(
            agent_id=self.agent_id,
            status="succeeded",
            summary=f"Diagnosis completed: category '{primary_diag.category.value if primary_diag else 'NONE'}'",
            metadata={
                "diagnoses": [d.to_dict() for d in diagnoses],
                "primary_diagnosis": primary_diag.to_dict() if primary_diag else None,
            },
        )

    def _handle_verify(self, request: AgentRequest) -> AgentResult:
        """Comprehensive verification of changes, requirements, and acceptance criteria."""
        requirements = request.parameters.get("requirements", [])
        acceptance_criteria = request.parameters.get("acceptance_criteria", [])
        changed_files = request.parameters.get("changed_files", [])
        components = request.parameters.get("components", [])
        timeout_seconds = request.parameters.get("timeout_seconds", 60)

        # 1. Analyze Requirements and detect unverified/unsupported requirements
        all_reqs = list(requirements) + list(acceptance_criteria)
        verifiable_reqs, unverified_reqs = self.component_mapper.analyze_requirements(
            all_reqs, self.metadata.allowed_tools
        )

        # 2. Map affected components
        inferred_comps = self.component_mapper.map_changed_files_to_components(changed_files)
        target_components = list(set(components) | inferred_comps)
        if not target_components and not changed_files:
            # Default to agent registry and architecture validator regression checks
            target_components = ["agent_registry"]

        # 3. Resolve test targets
        test_targets = self.component_mapper.resolve_test_targets(target_components, changed_files)

        # 4. Execute test targets
        checks: list[CheckResult] = []

        for target in test_targets:
            checks.append(self.test_executor.execute_pytest_target(target, timeout_seconds=timeout_seconds))

        # 5. Diagnose failures if any
        diagnoses = self.diagnostician.diagnose_failures(checks)

        # 6. Determine final evidence-based verdict
        verdict = self._determine_verdict(checks, unverified_reqs)

        explanation = self._generate_verdict_explanation(verdict, checks, unverified_reqs)

        report = VerificationReport(
            request_id=request.correlation_id or f"verif_{uuid.uuid4().hex[:8]}",
            project_id=request.project_id or "system",
            correlation_id=request.correlation_id or "",
            revision=self._get_git_revision(),
            components_covered=target_components,
            requirements_verified=verifiable_reqs,
            unverified_requirements=unverified_reqs,
            checks=checks,
            failure_diagnoses=diagnoses,
            verdict=verdict,
            verdict_explanation=explanation,
        )

        return AgentResult(
            agent_id=self.agent_id,
            status="succeeded" if verdict in (VerificationVerdict.PASS, VerificationVerdict.CONDITIONAL) else "failed",
            summary=f"Verification completed with verdict {verdict.value}: {explanation}",
            error=None if verdict in (VerificationVerdict.PASS, VerificationVerdict.CONDITIONAL) else explanation,
            metadata={"report": report.to_dict()},
        )

    # -------------------------------------------------------------------------
    # Verdict Calculation
    # -------------------------------------------------------------------------

    def _determine_verdict(
        self, checks: list[CheckResult], unverified_reqs: list[str]
    ) -> VerificationVerdict:
        if not checks:
            return VerificationVerdict.BLOCKED

        # Any check that could not run due to environment/dependency blocker -> BLOCKED
        has_blocked = any(c.status == TestExecutionStatus.BLOCKED for c in checks)
        if has_blocked:
            return VerificationVerdict.BLOCKED

        # Any execution failure -> FAIL
        has_failures = any(not c.is_successful for c in checks)
        if has_failures:
            return VerificationVerdict.FAIL

        # If unverified manual or external requirements remain but all automated checks pass -> CONDITIONAL
        if unverified_reqs:
            return VerificationVerdict.CONDITIONAL

        return VerificationVerdict.PASS

    def _generate_verdict_explanation(
        self,
        verdict: VerificationVerdict,
        checks: list[CheckResult],
        unverified_reqs: list[str],
    ) -> str:
        passed = sum(1 for c in checks if c.is_successful)
        failed = sum(1 for c in checks if not c.is_successful)

        if verdict == VerificationVerdict.PASS:
            return f"All {passed} verification check(s) passed with evidence."
        elif verdict == VerificationVerdict.FAIL:
            return f"Verification failed: {failed} check(s) failed."
        elif verdict == VerificationVerdict.BLOCKED:
            return "Verification blocked due to unavailable test targets or execution timeout."
        elif verdict == VerificationVerdict.CONDITIONAL:
            return f"All {passed} automated check(s) passed, but {len(unverified_reqs)} requirement(s) require manual/external sign-off."
        return "Verification completed."

    def _get_git_revision(self) -> str:
        try:
            head_file = self.project_root / ".git" / "HEAD"
            if head_file.exists():
                ref = head_file.read_text(encoding="utf-8").strip()
                if ref.startswith("ref: "):
                    ref_path = self.project_root / ".git" / ref[5:]
                    if ref_path.exists():
                        return ref_path.read_text(encoding="utf-8").strip()[:8]
                return ref[:8]
        except Exception:
            pass
        return "workspace_head"
