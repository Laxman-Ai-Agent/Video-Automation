"""Skill Factory System Agent (Canonical).

Responsible for:
1. Intake and normalization of SkillSpecifications.
2. Reuse / Adapt / Create decision resolution.
3. Synthesizing or adapting candidate skills adhering to standard SKILL.md format.
4. Static security and AST audit detecting injection, secret leakage, and frozen file tampering.
5. Isolated behavioral testing with strict timeouts and zero side-effects.
6. Approval engine integration and anti-spoofing verification.
7. Atomic versioned promotion to SYSTEM/skills/ and automatic CapabilityRegistry synchronization.
8. Controlled rollback of published skills to prior valid versions.

Canonical Location: SYSTEM/agents/skill_factory/agent.py
"""
from __future__ import annotations

import logging
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
from SYSTEM.agents.skill_factory.decision_engine import decision_engine
from SYSTEM.agents.skill_factory.generator import (
    GenerationProviderUnavailableError,
    SkillGenerationError,
    skill_generator,
)
from SYSTEM.agents.skill_factory.learning import skill_learning_engine
from SYSTEM.agents.skill_factory.lifecycle import SkillLifecycle
from SYSTEM.agents.skill_factory.publisher import (
    PromotionError,
    RollbackError,
    skill_publisher,
)
from SYSTEM.agents.skill_factory.security_validator import security_validator
from SYSTEM.agents.skill_factory.specification import (
    SkillSpecification,
    intake_specification,
    validate_specification,
)
from SYSTEM.agents.skill_factory.test_runner import skill_test_runner
from SYSTEM.registries.capability_registry import get_capability_registry
from SYSTEM.registries.skill_registry import (
    SkillSecurityError,
    get_skill_registry,
    registry as skill_registry,
)

logger = logging.getLogger("skill_factory.agent")

SUPPORTED_ACTIONS = {
    # Backward compatible
    "audit",
    "stage",
    "promote",
    # Phase 4 Production Hardened Actions
    "spec_intake",
    "decision",
    "generate_skill",
    "adapt_skill",
    "audit_skill",
    "test_skill",
    "request_approval",
    "promote_skill",
    "rollback_skill",
    "sync_registries",
    "create_or_adapt_flow",
    "evaluate_learning",
    "evaluate_quality",
}


class SkillFactoryAgent(BaseAgent):
    """System agent specialized in skill authoring, security auditing, testing, and lifecycle promotion."""

    def __init__(self, metadata: AgentMetadata | None = None) -> None:
        if metadata is None:
            metadata = AgentMetadata(
                agent_id="skill_factory",
                name="Skill Factory Agent",
                version="4.0.0",
                category=AgentCategory.SYSTEM_SUBAGENT,
                status=AgentStatus.IMPLEMENTED,
                purpose="Creates, adapts, validates, tests, and registers versioned skills with central registries and rollback protection.",
                capabilities=[
                    "skill-authoring",
                    "security-audit",
                    "skill-staging",
                    "version-registration",
                    "skill-lifecycle",
                    "isolated-testing",
                    "skill-rollback",
                    "capability-sync",
                ],
                allowed_tools=[
                    "skill_registry",
                    "static_auditor",
                    "file_storage",
                    "capability_registry",
                    "approval_engine",
                ],
                owner="system-core",
            )
        super().__init__(metadata)

    def validate(self, project_dir: Path, request: AgentRequest) -> list[str]:
        action = request.parameters.get("action", "audit")
        if action not in SUPPORTED_ACTIONS:
            return [
                f"Unsupported action '{action}' for SkillFactory. "
                f"Allowed: {', '.join(sorted(SUPPORTED_ACTIONS))}."
            ]
        return []

    def execute(self, project_dir: Path, request: AgentRequest) -> AgentResult:
        action = request.parameters.get("action", "audit")
        stage_id = request.stage_id or "system"
        project_id = request.project_id or "system"

        try:
            # ---------------------------------------------------------
            # 1. Backward-Compatible "audit" / "audit_skill"
            # ---------------------------------------------------------
            if action in ("audit", "audit_skill"):
                content = request.parameters.get("content", "")
                filename = request.parameters.get("filename", "SKILL.md")
                meta = request.parameters.get("metadata", {})
                audit_res = security_validator.audit(content, filename=filename, metadata=meta)
                is_safe = audit_res.passed
                issues = audit_res.findings
                status = "succeeded" if is_safe else "blocked"
                summary = (
                    "Skill security audit passed."
                    if is_safe
                    else f"Security violations detected ({audit_res.risk_level.upper()}): {'; '.join(issues)}"
                )
                return AgentResult(
                    agent_id=self.agent_id,
                    stage_id=stage_id,
                    project_id=project_id,
                    status=status,
                    summary=summary,
                    metadata={
                        "is_safe": is_safe,
                        "issues": issues,
                        "audit_result": audit_res.to_dict(),
                    },
                )

            # ---------------------------------------------------------
            # 2. Backward-Compatible "stage"
            # ---------------------------------------------------------
            elif action == "stage":
                content = request.parameters.get("content", "")
                filename = request.parameters.get("filename", "SKILL.md")
                meta = request.parameters.get("metadata", {})
                candidate = skill_registry.stage_external_candidate(
                    filename=filename,
                    raw_content=content,
                    metadata=meta,
                )
                return AgentResult(
                    agent_id=self.agent_id,
                    stage_id=stage_id,
                    project_id=project_id,
                    status="succeeded",
                    summary=f"Skill staged as candidate in staging/ (passed={candidate.get('audit', {}).get('passed')}).",
                    metadata={"candidate": candidate},
                )

            # ---------------------------------------------------------
            # 3. Specification Intake and Normalization
            # ---------------------------------------------------------
            elif action == "spec_intake":
                spec_input = request.parameters.get("specification") or request.parameters.get("requirement") or request.parameters
                use_llm = request.parameters.get("use_llm", True)
                try:
                    spec, ambiguities = intake_specification(spec_input, use_llm=use_llm)
                except Exception as e:
                    return AgentResult(
                        agent_id=self.agent_id,
                        stage_id=stage_id,
                        project_id=project_id,
                        status="failed",
                        error=f"Specification intake error: {e}",
                    )

                errors = validate_specification(spec)
                if errors:
                    return AgentResult(
                        agent_id=self.agent_id,
                        stage_id=stage_id,
                        project_id=project_id,
                        status="failed",
                        summary=f"Specification validation failed: {'; '.join(errors)}",
                        metadata={"errors": errors, "specification": spec.to_dict(), "ambiguities": ambiguities},
                    )

                return AgentResult(
                    agent_id=self.agent_id,
                    stage_id=stage_id,
                    project_id=project_id,
                    status="succeeded",
                    summary=f"Skill specification '{spec.skill_id}' normalized and validated successfully.",
                    metadata={"specification": spec.to_dict(), "ambiguities": ambiguities},
                )

            # ---------------------------------------------------------
            # 4. Reuse / Adapt / Create Decision
            # ---------------------------------------------------------
            elif action == "decision":
                spec_data = request.parameters.get("specification", request.parameters)
                allow_adapt = request.parameters.get("allow_adapt", True)
                decision = decision_engine.evaluate(spec_data, allow_adapt=allow_adapt)
                return AgentResult(
                    agent_id=self.agent_id,
                    stage_id=stage_id,
                    project_id=project_id,
                    status="succeeded",
                    summary=f"Decision: {decision.action} for skill '{decision.skill_id}' (v{decision.version}). {decision.reason}",
                    metadata={"decision": decision.to_dict()},
                )

            # ---------------------------------------------------------
            # 5. Generate Skill Draft (with Bounded Self-Repair)
            # ---------------------------------------------------------
            elif action == "generate_skill":
                spec_dict = request.parameters.get("specification", request.parameters)
                spec = SkillSpecification.from_dict(spec_dict) if isinstance(spec_dict, dict) else spec_dict
                allow_fallback = request.parameters.get("allow_template_fallback", False)
                use_repair = request.parameters.get("use_repair", True)
                max_retries = int(request.parameters.get("max_retries", 3))

                if use_repair:
                    draft = skill_generator.generate_with_repair(
                        spec,
                        validator_fn=security_validator.audit,
                        test_runner_fn=skill_test_runner.run_tests,
                        max_retries=max_retries,
                        allow_template_fallback=allow_fallback,
                    )
                else:
                    draft = skill_generator.generate(spec, allow_template_fallback=allow_fallback)

                skill_learning_engine.record_authoring_outcome(
                    skill_id=draft.skill_id,
                    domain=spec.domain,
                    decision_action="CREATE",
                    repair_attempts=draft.repair_attempts,
                    failure_categories=[f.get("category", "") for f in draft.failure_history],
                    passed=True,
                    duration_ms=0.0,
                )

                return AgentResult(
                    agent_id=self.agent_id,
                    stage_id=stage_id,
                    project_id=project_id,
                    status="succeeded",
                    summary=f"Generated draft for skill '{draft.skill_id}' v{draft.version} (repairs: {draft.repair_attempts}).",
                    metadata={"draft": draft.to_dict()},
                )

            # ---------------------------------------------------------
            # 6. Adapt Existing Skill
            # ---------------------------------------------------------
            elif action == "adapt_skill":
                spec_dict = request.parameters.get("specification", request.parameters)
                spec = SkillSpecification.from_dict(spec_dict) if isinstance(spec_dict, dict) else spec_dict
                base_id = request.parameters.get("base_skill_id", "")
                base_content = request.parameters.get("base_content", "")
                if not base_content and base_id:
                    try:
                        _, base_content = skill_registry.get_skill(base_id, load_content=True)
                    except Exception as e:
                        return AgentResult(
                            agent_id=self.agent_id,
                            stage_id=stage_id,
                            project_id=project_id,
                            status="failed",
                            error=f"Cannot load base skill '{base_id}' for adaptation: {e}",
                        )

                allow_fallback = request.parameters.get("allow_template_fallback", False)
                draft = skill_generator.adapt(spec, base_id, base_content, allow_template_fallback=allow_fallback)
                return AgentResult(
                    agent_id=self.agent_id,
                    stage_id=stage_id,
                    project_id=project_id,
                    status="succeeded",
                    summary=f"Adapted skill '{draft.skill_id}' v{draft.version} from base '{base_id}'.",
                    metadata={"draft": draft.to_dict()},
                )

            # ---------------------------------------------------------
            # 7. Isolated Behavioral Testing
            # ---------------------------------------------------------
            elif action == "test_skill":
                spec_dict = request.parameters.get("specification", request.parameters)
                spec = SkillSpecification.from_dict(spec_dict) if isinstance(spec_dict, dict) else spec_dict
                content = request.parameters.get("content", spec.instructions_markdown)
                timeout_s = float(request.parameters.get("timeout_seconds", 5.0))
                backend = request.parameters.get("isolation_backend")
                test_res = skill_test_runner.run_tests(
                    spec,
                    content,
                    timeout_seconds=timeout_s,
                    isolation_backend=backend,
                )
                status = "blocked" if test_res.status == "blocked_isolation" else ("succeeded" if test_res.passed else "failed")
                return AgentResult(
                    agent_id=self.agent_id,
                    stage_id=stage_id,
                    project_id=project_id,
                    status=status,
                    summary=(
                        f"Isolated tests {test_res.status.upper()}: {test_res.tests_passed}/{test_res.tests_run} "
                        f"passed in {test_res.duration_ms}ms ({test_res.isolation_strategy})."
                    ),
                    metadata={"test_result": test_res.to_dict()},
                )

            # ---------------------------------------------------------
            # 8. Promote Skill (Atomic & Concurrency-Safe)
            # ---------------------------------------------------------
            elif action in ("promote", "promote_skill"):
                spec_dict = request.parameters.get("specification", request.parameters)
                spec = SkillSpecification.from_dict(spec_dict) if isinstance(spec_dict, dict) else spec_dict
                content = request.parameters.get("content", "")
                operator_id = request.parameters.get("operator_id")
                role = request.parameters.get("role")
                app_req_id = request.parameters.get("approval_request_id")
                test_result_param = request.parameters.get("test_result")

                lifecycle = SkillLifecycle(skill_id=spec.skill_id, version=spec.version, current_state="APPROVED")

                target_agent = request.parameters.get("target_agent_id", getattr(spec, "target_agent_id", None))

                res = skill_publisher.promote_skill(
                    spec=spec,
                    content=content,
                    lifecycle=lifecycle,
                    operator_id=operator_id,
                    role=role,
                    approval_request_id=app_req_id,
                    test_result=test_result_param,
                    target_agent_id=target_agent,
                )
                return AgentResult(
                    agent_id=self.agent_id,
                    stage_id=stage_id,
                    project_id=project_id,
                    status="succeeded",
                    summary=f"Skill '{res.skill_id}' v{res.version} promoted to active library by {res.operator_attribution}.",
                    metadata={"promotion_result": res.to_dict(), "lifecycle": lifecycle.to_dict()},
                )

            # ---------------------------------------------------------
            # 9. Rollback Skill
            # ---------------------------------------------------------
            elif action == "rollback_skill":
                skill_id = request.parameters.get("skill_id", "")
                reason = request.parameters.get("reason", "Manual operator rollback")
                target_ver = request.parameters.get("target_version")
                operator_id = request.parameters.get("operator_id")
                role = request.parameters.get("role")

                rb_res = skill_publisher.rollback_skill(
                    skill_id=skill_id,
                    reason=reason,
                    operator_id=operator_id,
                    role=role,
                    approval_request_id=request.parameters.get("approval_request_id"),
                    target_version=target_ver,
                )
                return AgentResult(
                    agent_id=self.agent_id,
                    stage_id=stage_id,
                    project_id=project_id,
                    status="succeeded",
                    summary=f"Skill '{skill_id}' rolled back from v{rb_res.rolled_back_version} to {rb_res.restored_version or 'deprecated'}.",
                    metadata={"rollback_result": rb_res.to_dict()},
                )

            # ---------------------------------------------------------
            # 10. Synchronize Registries
            # ---------------------------------------------------------
            elif action == "sync_registries":
                cap_reg = get_capability_registry()
                report = cap_reg.sync_with_registries()
                return AgentResult(
                    agent_id=self.agent_id,
                    stage_id=stage_id,
                    project_id=project_id,
                    status="succeeded",
                    summary=f"Registries synchronized: {report.get('skills_synced', 0)} skills indexed.",
                    metadata={"sync_report": report},
                )

            # ---------------------------------------------------------
            # 10.1 Video Quality Evaluation
            # ---------------------------------------------------------
            elif action == "evaluate_quality":
                spec_dict = request.parameters.get("specification", {})
                spec = SkillSpecification.from_dict(spec_dict) if isinstance(spec_dict, dict) else spec_dict
                output_data = request.parameters.get("output_data", {})
                kwargs = request.parameters.get("evaluation_kwargs", {})

                q_res = skill_test_runner.evaluate_video_domain_quality(spec, output_data, **kwargs)
                return AgentResult(
                    agent_id=self.agent_id,
                    stage_id=stage_id,
                    project_id=project_id,
                    status="succeeded" if q_res.passed else "failed",
                    summary=(
                        f"Quality evaluation for '{spec.skill_id}' ({q_res.domain}): "
                        f"{q_res.checks_passed}/{q_res.checks_run} checks passed. "
                        f"{'; '.join(q_res.findings) if q_res.findings else 'All invariants verified.'}"
                    ),
                    metadata={"quality_report": q_res.to_dict()},
                )

            # ---------------------------------------------------------
            # 11. End-to-End Skill Flow
            # ---------------------------------------------------------
            elif action == "create_or_adapt_flow":
                spec_dict = request.parameters.get("specification", request.parameters)
                spec = SkillSpecification.from_dict(spec_dict) if isinstance(spec_dict, dict) else spec_dict
                allow_fallback = request.parameters.get("allow_template_fallback", True)

                lifecycle = SkillLifecycle(skill_id=spec.skill_id, version=spec.version, current_state="DRAFT")

                # Step 1: Decision
                decision = decision_engine.evaluate(spec)
                if decision.action == "CLARIFY":
                    return AgentResult(
                        agent_id=self.agent_id,
                        stage_id=stage_id,
                        project_id=project_id,
                        status="blocked",
                        summary=f"Clarification required for '{spec.skill_id}': {decision.clarification_needed}",
                        metadata={"decision": decision.to_dict(), "action_taken": "CLARIFY"},
                    )
                elif decision.action == "COMPOSE":
                    return AgentResult(
                        agent_id=self.agent_id,
                        stage_id=stage_id,
                        project_id=project_id,
                        status="succeeded",
                        summary=f"Composition recommended across existing skills: {', '.join(decision.composed_skills)}.",
                        metadata={"decision": decision.to_dict(), "action_taken": "COMPOSE"},
                    )
                elif decision.action == "REUSE":
                    return AgentResult(
                        agent_id=self.agent_id,
                        stage_id=stage_id,
                        project_id=project_id,
                        status="succeeded",
                        summary=f"Reuse recommended for existing skill '{decision.skill_id}'. No new creation needed.",
                        metadata={"decision": decision.to_dict(), "action_taken": "REUSE"},
                    )

                # Step 2: Generation / Adaptation with Bounded Repair
                lifecycle.transition("VALIDATING", actor=self.agent_id, reason="Validating and auditing draft.")
                if decision.action == "ADAPT":
                    _, base_content = skill_registry.get_skill(decision.base_skill_id, load_content=True)
                    draft = skill_generator.adapt(
                        spec, decision.base_skill_id, base_content, allow_template_fallback=allow_fallback
                    )
                else:
                    draft = skill_generator.generate_with_repair(
                        spec,
                        validator_fn=security_validator.audit,
                        test_runner_fn=skill_test_runner.run_tests,
                        max_retries=3,
                        allow_template_fallback=allow_fallback,
                    )

                # Step 3: Security Audit
                audit_res = security_validator.audit(draft.content, filename=draft.filename)
                if not audit_res.passed:
                    next_st = "QUARANTINED" if audit_res.quarantine_required else "FAILED_VALIDATION"
                    lifecycle.transition(next_st, actor=self.agent_id, reason=f"Security audit failed: {'; '.join(audit_res.findings)}")
                    return AgentResult(
                        agent_id=self.agent_id,
                        stage_id=stage_id,
                        project_id=project_id,
                        status="blocked",
                        summary=f"Skill draft blocked by security audit: {'; '.join(audit_res.findings)}",
                        metadata={"audit": audit_res.to_dict(), "lifecycle": lifecycle.to_dict()},
                    )

                # Step 4: Testing
                lifecycle.transition("TESTING", actor=self.agent_id, reason="Executing isolated behavioral tests.")
                test_res = skill_test_runner.run_tests(spec, draft.content)
                if not test_res.passed:
                    target_st = "BLOCKED_ISOLATION" if test_res.status == "blocked_isolation" else "FAILED_TESTS"
                    lifecycle.transition(
                        target_st,
                        actor=self.agent_id,
                        reason=f"Behavioral tests {test_res.status}: {'; '.join(test_res.diagnostics)}",
                        evidence={"test_result": test_res.to_dict()},
                    )
                    return AgentResult(
                        agent_id=self.agent_id,
                        stage_id=stage_id,
                        project_id=project_id,
                        status="blocked" if test_res.status == "blocked_isolation" else "failed",
                        summary=f"Skill draft behavioral testing {test_res.status}: {'; '.join(test_res.diagnostics)}",
                        metadata={"test_result": test_res.to_dict(), "lifecycle": lifecycle.to_dict()},
                    )

                # Step 5: Approval Transition
                lifecycle.transition(
                    "AWAITING_APPROVAL",
                    actor=self.agent_id,
                    reason="Passed security and behavioral tests; awaiting operator promotion.",
                    evidence={"test_result": test_res.to_dict()},
                )

                # Record learning outcome
                skill_learning_engine.record_authoring_outcome(
                    skill_id=spec.skill_id,
                    domain=spec.domain,
                    decision_action=decision.action,
                    repair_attempts=draft.repair_attempts,
                    failure_categories=[f.get("category", "") for f in draft.failure_history],
                    passed=True,
                    duration_ms=0.0,
                )

                return AgentResult(
                    agent_id=self.agent_id,
                    stage_id=stage_id,
                    project_id=project_id,
                    status="succeeded",
                    summary=f"Skill candidate '{spec.skill_id}' successfully synthesized, audited, and tested. Ready for promotion.",
                    metadata={
                        "draft": draft.to_dict(),
                        "audit": audit_res.to_dict(),
                        "test_result": test_res.to_dict(),
                        "lifecycle": lifecycle.to_dict(),
                    },
                )

            # ---------------------------------------------------------
            # 12. Self-Learning Benchmark Evaluation
            # ---------------------------------------------------------
            elif action == "evaluate_learning":
                candidates = skill_learning_engine.propose_candidate_lessons()
                promoted = []
                for c in candidates:
                    if skill_learning_engine.validate_lesson_against_benchmark(c):
                        promoted.extend(skill_learning_engine.promote_lessons([c]))
                active = skill_learning_engine.get_active_lessons()
                return AgentResult(
                    agent_id=self.agent_id,
                    stage_id=stage_id,
                    project_id=project_id,
                    status="succeeded",
                    summary=f"Learning evaluation complete: {len(promoted)} lessons promoted. {len(active)} active lessons in knowledge base.",
                    metadata={"promoted_lessons": [p.to_dict() for p in promoted], "active_lessons": [a.to_dict() for a in active]},
                )

            else:
                return AgentResult(
                    agent_id=self.agent_id,
                    stage_id=stage_id,
                    project_id=project_id,
                    status="failed",
                    error=f"Unrecognized action '{action}'",
                )

        except (SkillSecurityError, GenerationProviderUnavailableError, PromotionError, RollbackError) as e:
            logger.warning(f"SkillFactory operation '{action}' rejected: {e}")
            return AgentResult(
                agent_id=self.agent_id,
                stage_id=stage_id,
                project_id=project_id,
                status="blocked",
                error=str(e),
                summary=f"SkillFactory blocked: {e}",
            )
        except Exception as e:
            logger.error(f"SkillFactory unhandled error during '{action}': {e}", exc_info=True)
            return AgentResult(
                agent_id=self.agent_id,
                stage_id=stage_id,
                project_id=project_id,
                status="failed",
                error=str(e),
                summary=f"SkillFactory error: {e}",
            )
