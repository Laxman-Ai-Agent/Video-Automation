"""Skill Generation and Adaptation Engine for Skill Factory.

Integrates with SYSTEM.core.llm_gateway to generate or adapt SKILL.md packages.
Fails safely when the LLM provider is unavailable, and provides a deterministic
structured synthesis fallback when explicitly requested.
"""
from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from SYSTEM.agents.skill_factory.specification import SkillSpecification, validate_specification

logger = logging.getLogger("skill_factory.generator")


class SkillGenerationError(Exception):
    """Raised when skill generation fails."""
    pass


class GenerationProviderUnavailableError(SkillGenerationError):
    """Raised when the LLM provider is unavailable or unconfigured."""
    pass


FailureCategory = Literal[
    "SYNTAX_ERROR",
    "SCHEMA_ERROR",
    "TYPE_ERROR",
    "BEHAVIORAL_TEST_FAILURE",
    "SECURITY_VIOLATION",
    "DEPENDENCY_ERROR",
    "ENVIRONMENT_FAULT",
    "UNKNOWN",
]


def classify_failure(error_msg: str, diagnostics: dict[str, Any] | None = None) -> FailureCategory:
    """Classifies an error or diagnostic output into a deterministic failure category."""
    lower_err = error_msg.lower()
    if any(k in lower_err for k in ["security", "injection", "prohibited", "tamper", "escape", "dangerous", "violation"]):
        return "SECURITY_VIOLATION"
    if any(k in lower_err for k in ["syntax", "syntaxerror", "parse error", "unexpected token"]):
        return "SYNTAX_ERROR"
    if any(k in lower_err for k in ["type error", "typeerror", "error ts", "ts2"]):
        return "TYPE_ERROR"
    if any(k in lower_err for k in ["test", "assertionerror", "exit code", "failed test", "contract_schema", "heading_structure"]):
        return "BEHAVIORAL_TEST_FAILURE"
    if any(k in lower_err for k in ["schema", "semver", "semantic version", "required and cannot be empty", "missing leading frontmatter"]):
        return "SCHEMA_ERROR"
    if any(k in lower_err for k in ["no module named", "cannot find module", "import error", "importerror"]):
        return "DEPENDENCY_ERROR"
    if any(k in lower_err for k in ["timeout", "timed out", "out of memory", "oom", "connection refused"]):
        return "ENVIRONMENT_FAULT"
    return "UNKNOWN"


@dataclass
class SkillDraft:
    """Represents a generated or adapted candidate skill draft."""
    skill_id: str
    version: str
    filename: str
    content: str
    specification: SkillSpecification
    mode: str = "generated"  # "generated" or "adapted"
    base_skill_id: str | None = None
    repair_attempts: int = 0
    failure_history: list[dict[str, Any]] = field(default_factory=list)
    previous_candidates: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "version": self.version,
            "filename": self.filename,
            "content": self.content,
            "specification": self.specification.to_dict(),
            "mode": self.mode,
            "base_skill_id": self.base_skill_id,
            "repair_attempts": self.repair_attempts,
            "failure_history": self.failure_history,
            "diagnostics": self.diagnostics,
            "created_at": self.created_at,
        }


class SkillGenerator:
    """Generates and adapts skill definitions adhering to standard SKILL.md format with bounded self-repair."""

    def __init__(self) -> None:
        pass

    def generate(
        self,
        spec: SkillSpecification,
        allow_template_fallback: bool = False,
    ) -> SkillDraft:
        """Generates a new skill draft from specification."""
        errs = validate_specification(spec)
        if errs:
            raise SkillGenerationError(f"Cannot generate skill from invalid specification: {'; '.join(errs)}")

        lang = getattr(spec, "language", "markdown")
        user_prompt = (
            f"Generate a canonical SKILL.md file for the following skill specification:\n\n"
            f"Skill ID: {spec.skill_id}\n"
            f"Name: {spec.name}\n"
            f"Domain: {spec.domain}\n"
            f"Language Target: {lang}\n"
            f"Version: {spec.version}\n"
            f"Purpose: {spec.purpose}\n"
            f"Capabilities: {', '.join(spec.capabilities)}\n"
            f"Tags: {', '.join(spec.tags)}\n"
            f"Risk Level: {spec.risk_level}\n"
            f"Inputs: {spec.inputs}\n"
            f"Outputs: {spec.outputs}\n"
            f"Dependencies: {', '.join(spec.dependencies)}\n\n"
            f"FORMAT REQUIREMENT:\n"
            f"Output must begin with '---' YAML frontmatter and contain markdown sections: "
            f"'# Title', '## Purpose', '## Core Rules', '## Visual Hierarchy / Contracts', '## Safe Zones / Bounds'."
        )
        if lang in ("tsx", "typescript"):
            user_prompt += (
                "\n\nCODE REQUIREMENT:\n"
                "Include a clean ```tsx code block implementing a Remotion animation component. "
                "Use React.FC with typed props, useCurrentFrame(), interpolate() or spring(), and <AbsoluteFill>."
            )
        elif lang == "python":
            user_prompt += (
                "\n\nCODE REQUIREMENT:\n"
                "Include a clean ```python code block implementing the core logic with type annotations and error handling."
            )

        try:
            content = self._invoke_llm(user_prompt, system_prompt="You are an expert system skill author.")
        except Exception as e:
            if not allow_template_fallback:
                raise GenerationProviderUnavailableError(
                    f"LLM generation provider is unavailable: {e}. Safe failure enforced."
                ) from e
            logger.info("LLM provider unavailable; utilizing deterministic structured template synthesis.")
            content = self._synthesize_structured_template(spec)

        filename = f"{spec.skill_id.replace('.', '_')}.md"
        return SkillDraft(
            skill_id=spec.skill_id,
            version=spec.version,
            filename=filename,
            content=content,
            specification=spec,
            mode="generated",
        )

    def generate_with_repair(
        self,
        spec: SkillSpecification,
        validator_fn: Any | None = None,
        test_runner_fn: Any | None = None,
        max_retries: int = 3,
        allow_template_fallback: bool = False,
    ) -> SkillDraft:
        """Generates candidate skill with a bounded self-correction loop targeting compiler, security, and test failures."""
        draft = self.generate(spec, allow_template_fallback=allow_template_fallback)

        if validator_fn is None and test_runner_fn is None:
            return draft

        failure_history: list[dict[str, Any]] = []
        previous_candidates: list[str] = [draft.content]

        for attempt in range(1, max_retries + 1):
            # 1. Run Security / Contract Validation
            validation_passed = True
            validation_errors: list[str] = []
            if validator_fn is not None:
                try:
                    val_res = validator_fn(draft.content, filename=draft.filename)
                    validation_passed = getattr(val_res, "passed", True)
                    validation_errors = getattr(val_res, "findings", [])
                except Exception as e:
                    validation_passed = False
                    validation_errors = [f"Validator exception: {e}"]

            if not validation_passed:
                cat = classify_failure("; ".join(validation_errors))
                # Never allow LLM to bypass critical security rules like frozen-file tamper or prompt injection
                if cat == "SECURITY_VIOLATION" and any("frozen" in e.lower() or "injection" in e.lower() for e in validation_errors):
                    logger.warning(f"Unrecoverable critical security violation in draft: {validation_errors}")
                    draft.failure_history.append({
                        "attempt": attempt,
                        "category": cat,
                        "errors": validation_errors,
                        "status": "unrecoverable_security_block",
                    })
                    break

                failure_info = {
                    "attempt": attempt,
                    "category": cat,
                    "stage": "validation",
                    "errors": validation_errors,
                }
                failure_history.append(failure_info)
                logger.info(f"Self-correction triggered (attempt {attempt}/{max_retries}) for {cat}: {validation_errors}")

                # Attempt targeted LLM repair
                try:
                    repaired_content = self._attempt_repair(spec, draft.content, cat, validation_errors, attempt)
                    previous_candidates.append(draft.content)
                    draft.content = repaired_content
                    draft.repair_attempts = attempt
                    continue
                except Exception as e:
                    logger.warning(f"Self-correction attempt {attempt} failed: {e}")
                    if allow_template_fallback:
                        draft.content = self._synthesize_structured_template(spec)
                    break

            # 2. Run Isolated Behavioral Testing (if validation passed)
            if test_runner_fn is not None:
                try:
                    test_res = test_runner_fn(spec, draft.content)
                    tests_passed = getattr(test_res, "passed", True)
                    status = getattr(test_res, "status", "unknown")
                    diags = getattr(test_res, "diagnostics", [])
                except Exception as e:
                    tests_passed = False
                    status = "exception"
                    diags = [f"Test runner error: {e}"]

                if not tests_passed:
                    cat = classify_failure("; ".join(diags) or f"Test failed with status {status}")
                    failure_info = {
                        "attempt": attempt,
                        "category": cat,
                        "stage": "behavioral_testing",
                        "status": status,
                        "errors": diags,
                    }
                    failure_history.append(failure_info)
                    logger.info(f"Behavioral test repair triggered (attempt {attempt}/{max_retries}) for {cat}")

                    try:
                        repaired_content = self._attempt_repair(spec, draft.content, cat, diags, attempt)
                        previous_candidates.append(draft.content)
                        draft.content = repaired_content
                        draft.repair_attempts = attempt
                        continue
                    except Exception as e:
                        logger.warning(f"Self-correction repair failed: {e}")
                        break
                else:
                    # Both validation and tests passed!
                    break

        draft.failure_history = failure_history
        draft.previous_candidates = previous_candidates
        return draft

    def _attempt_repair(
        self,
        spec: SkillSpecification,
        current_content: str,
        failure_category: FailureCategory,
        diagnostics: list[str],
        attempt_num: int,
    ) -> str:
        """Executes a targeted LLM self-correction prompt based on exact failure diagnostics."""
        diag_text = "\n".join(f"- {d}" for d in diagnostics) if diagnostics else "- Unknown failure detected"
        repair_prompt = (
            f"The previous draft for skill '{spec.skill_id}' failed {failure_category} during validation:\n\n"
            f"DIAGNOSTIC EVIDENCE:\n{diag_text}\n\n"
            f"PREVIOUS DRAFT (Lines 1-120):\n"
            f"```markdown\n{current_content[:3500]}\n```\n\n"
            f"REPAIR DIRECTIVES (Attempt {attempt_num}):\n"
            f"1. Fix the specific {failure_category} shown above.\n"
            f"2. Do NOT remove required tests, frontmatter fields, or weaken security boundaries.\n"
            f"3. Maintain strict YAML frontmatter enclosed in '---'.\n"
            f"4. If code is embedded, ensure it conforms to safety rules (no prohibited imports, no shell=True, no path traversal).\n"
            f"Output the complete corrected SKILL.md file starting with '---'."
        )
        return self._invoke_llm(repair_prompt, system_prompt="You are an expert system skill repair architect.")

    def adapt(
        self,
        spec: SkillSpecification,
        base_skill_id: str,
        base_content: str,
        allow_template_fallback: bool = False,
    ) -> SkillDraft:
        """Adapts an existing skill into a new versioned candidate without clobbering base."""
        errs = validate_specification(spec)
        if errs:
            raise SkillGenerationError(f"Cannot adapt skill from invalid specification: {'; '.join(errs)}")

        user_prompt = (
            f"Adapt the following existing skill '{base_skill_id}' to meet new requirements:\n\n"
            f"BASE SKILL CONTENT:\n"
            f"```markdown\n{base_content[:3000]}\n```\n\n"
            f"NEW REQUIREMENTS:\n"
            f"Target Skill ID: {spec.skill_id}\n"
            f"Target Version: {spec.version}\n"
            f"Additional Capabilities: {', '.join(spec.capabilities)}\n"
            f"Updated Purpose: {spec.purpose}\n\n"
            f"FORMAT REQUIREMENT:\n"
            f"Output must begin with '---' YAML frontmatter and document adaptation provenance."
        )

        try:
            content = self._invoke_llm(user_prompt, system_prompt="You are an expert system skill author.")
        except Exception as e:
            if not allow_template_fallback:
                raise GenerationProviderUnavailableError(
                    f"LLM generation provider is unavailable: {e}. Safe failure enforced."
                ) from e
            logger.info("LLM provider unavailable; utilizing structured adaptation synthesis.")
            content = self._synthesize_adaptation_template(spec, base_skill_id, base_content)

        filename = f"{spec.skill_id.replace('.', '_')}_v{spec.version}.md"
        return SkillDraft(
            skill_id=spec.skill_id,
            version=spec.version,
            filename=filename,
            content=content,
            specification=spec,
            mode="adapted",
            base_skill_id=base_skill_id,
        )

    def _invoke_llm(self, user_prompt: str, system_prompt: str = "") -> str:
        """Attempts invocation via SYSTEM.core.llm_gateway."""
        try:
            from SYSTEM.core.llm_gateway import LlmGatewayRequest, llm_gateway
        except ImportError:
            raise GenerationProviderUnavailableError("llm_gateway is not importable.")

        req = LlmGatewayRequest(
            project_id="system",
            stage_id="skill_factory",
            agent_id="skill_factory",
            purpose="generation",
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            model_profile="code_generation",
        )
        resp = llm_gateway.execute(req)
        if resp.status == "failed" or not resp.raw_text:
            raise GenerationProviderUnavailableError(f"LLM gateway execution failed: {resp.error}")
        return resp.raw_text

    def _synthesize_structured_template(self, spec: SkillSpecification) -> str:
        """Generates a rich, deterministic, structured SKILL.md template from specification supporting Markdown, Python, and Remotion TSX."""
        rules_list = []
        for i, cap in enumerate(spec.capabilities, 1):
            rules_list.append(f"{i}. **{cap.replace('-', ' ').title()}**: Implement strict adherence to {cap} specification constraints.")

        rules_body = "\n".join(rules_list)
        lang = getattr(spec, "language", "markdown")
        comp_name = "".join(part.capitalize() for part in re.findall(r"[a-zA-Z0-9]+", spec.name)) or "CustomComponent"

        code_block = ""
        if lang in ("tsx", "typescript") or "remotion" in spec.tags or "remotion" in spec.domain:
            code_block = (
                f"\n\n## Remotion Implementation\n\n"
                f"```tsx\n"
                f"import React from 'react';\n"
                f"import {{ AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate, spring }} from 'remotion';\n\n"
                f"export interface {comp_name}Props {{\n"
                f"    title?: string;\n"
                f"    accentColor?: string;\n"
                f"}}\n\n"
                f"export const {comp_name}: React.FC<{comp_name}Props> = ({{\n"
                f"    title = '{spec.name}',\n"
                f"    accentColor = '#3B82F6',\n"
                f"}}) => {{\n"
                f"    const frame = useCurrentFrame();\n"
                f"    const {{ fps }} = useVideoConfig();\n\n"
                f"    const scale = spring({{\n"
                f"        frame,\n"
                f"        fps,\n"
                f"        config: {{ damping: 12, mass: 0.5 }},\n"
                f"    }});\n\n"
                f"    const opacity = interpolate(frame, [0, 15], [0, 1], {{\n"
                f"        extrapolateRight: 'clamp',\n"
                f"    }});\n\n"
                f"    return (\n"
                f"        <AbsoluteFill style={{{{ justifyContent: 'center', alignItems: 'center', backgroundColor: '#0F172A' }}}}>\n"
                f"            <h1 style={{{{ color: accentColor, opacity, transform: `scale(${{scale}})` }}}}>\n"
                f"                {{title}}\n"
                f"            </h1>\n"
                f"        </AbsoluteFill>\n"
                f"    );\n"
                f"}};\n\n"
                f"export default {comp_name};\n"
                f"```\n"
            )
        elif lang == "python":
            func_name = re.sub(r"[^a-z0-9_]+", "_", spec.skill_id.replace(".", "_")).strip("_")
            code_block = (
                f"\n\n## Python Implementation\n\n"
                f"```python\n"
                f"from typing import Any, Dict\n\n"
                f"def {func_name}(context: Dict[str, Any]) -> Dict[str, Any]:\n"
                f'    """Implements {spec.name} ({spec.purpose})."""\n'
                f"    if not isinstance(context, dict):\n"
                f'        raise ValueError("Context must be a dictionary.")\n'
                f"    # Process verified capabilities: {', '.join(spec.capabilities)}\n"
                f"    result = {{'status': 'success', 'applied_capabilities': {spec.capabilities}}}\n"
                f"    return result\n"
                f"```\n"
            )

        markdown_body = (
            f"# {spec.name}\n\n"
            f"## Purpose\n"
            f"{spec.purpose}\n\n"
            f"## Core Rules\n"
            f"{rules_body}\n\n"
            f"## Input and Output Contracts\n"
            f"- Declared Inputs: `{list(spec.inputs.keys())}`\n"
            f"- Declared Outputs: `{list(spec.outputs.keys())}`\n\n"
            f"## Constraints & Governance\n"
            f"- Risk Level: `{spec.risk_level}`\n"
            f"- Target Mode: `{spec.compatible_project_modes}`\n"
            f"- Dependencies: `{spec.dependencies}`"
            f"{code_block}"
        )
        spec.instructions_markdown = markdown_body
        return spec.to_yaml_manifest()

    def _synthesize_adaptation_template(
        self,
        spec: SkillSpecification,
        base_skill_id: str,
        base_content: str,
    ) -> str:
        """Synthesizes an adapted SKILL.md preserving base content context with provenance."""
        spec.license_evidence = f"Adapted from base skill '{base_skill_id}'. License: {spec.license}."
        spec.provenance = f"adapted:{base_skill_id}"

        # Extract base rules if available
        base_rules_snippet = ""
        if "## Core Rules" in base_content:
            parts = base_content.split("## Core Rules", 1)
            base_rules_snippet = parts[1].split("##", 1)[0].strip()

        rules_list = [f"1. **Inherited Baseline**: Retains verified behavioral rules from `{base_skill_id}`."]
        for i, cap in enumerate(spec.capabilities, 2):
            rules_list.append(f"{i}. **Extended Capability ({cap})**: Enforce extended constraints for {cap}.")

        markdown_body = (
            f"# {spec.name} (Adapted v{spec.version})\n\n"
            f"## Provenance\n"
            f"Adapted from `{base_skill_id}` to satisfy extended requirements.\n\n"
            f"## Purpose\n"
            f"{spec.purpose}\n\n"
            f"## Extended Rules\n"
            f"{chr(10).join(rules_list)}\n\n"
            f"## Inherited Rules from Base Skill\n"
            f"{base_rules_snippet or 'Standard domain safety and pacing rules apply.'}\n"
        )
        spec.instructions_markdown = markdown_body
        return spec.to_yaml_manifest()


# Authoritative singleton
skill_generator = SkillGenerator()
