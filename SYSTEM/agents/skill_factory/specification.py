"""Skill Specification and Validation Schema for Skill Factory.

Defines:
1. Strongly-typed SkillSpecification dataclass with strict field validation.
2. Canonical YAML frontmatter parsing and serialization.
3. SemVer validation and risk-level classification.
4. Input and output contract validation.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

logger = logging.getLogger("skill_factory.specification")

SkillRiskLevel = Literal["low", "medium", "high", "critical"]

ALLOWED_RISK_LEVELS: set[str] = {"low", "medium", "high", "critical"}
SEMVER_REGEX = re.compile(r"^\d+\.\d+\.\d+(-[a-zA-Z0-9_.-]+)?$")
SKILL_ID_REGEX = re.compile(r"^[a-z0-9][a-z0-9_.-]*[a-z0-9]$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SkillSpecification:
    """Canonical specification defining a skill requirement or draft package."""
    skill_id: str
    name: str
    purpose: str
    domain: str
    version: str = "1.0.0"
    tags: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    entrypoint: str = ""
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    compatible_agents: list[str] = field(default_factory=list)
    compatible_project_modes: list[str] = field(default_factory=lambda: ["motion_only"])
    risk_level: SkillRiskLevel = "low"
    license: str = "Apache-2.0"
    license_evidence: str = ""
    provenance: str = "skill_factory"
    rationale: str = ""
    test_requirements: list[dict[str, Any]] = field(default_factory=list)
    instructions_markdown: str = ""
    code_content: str = ""
    target_agent_id: str | None = None
    language: str = "markdown"  # "markdown", "python", "typescript", "tsx"
    acceptance_criteria: list[str] = field(default_factory=list)
    ambiguities: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillSpecification:
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    def to_yaml_manifest(self) -> str:
        """Serializes the specification into canonical SKILL.md format (YAML frontmatter + Markdown)."""
        frontmatter_dict: dict[str, Any] = {
            "skill_id": self.skill_id,
            "name": self.name,
            "domain": self.domain,
            "version": self.version,
            "summary": self.purpose,
            "status": self.metadata.get("status", "draft"),
            "source": self.metadata.get("source", "local"),
            "license": self.license,
            "license_evidence": self.license_evidence or f"Authored via Skill Factory: {self.provenance}",
            "risk_level": self.risk_level,
            "capabilities": self.capabilities,
            "tags": self.tags,
            "dependencies": self.dependencies,
            "compatible_agents": self.compatible_agents,
            "compatible_project_modes": self.compatible_project_modes,
        }
        if self.target_agent_id:
            frontmatter_dict["target_agent_id"] = self.target_agent_id
        if self.inputs:
            frontmatter_dict["input_contracts"] = self.inputs
        if self.outputs:
            frontmatter_dict["output_contracts"] = self.outputs

        if yaml is not None:
            yaml_str = yaml.safe_dump(frontmatter_dict, sort_keys=False, default_flow_style=False).strip()
        else:
            # Fallback simple yaml serializer if pyyaml is missing
            lines = []
            for k, v in frontmatter_dict.items():
                if isinstance(v, list):
                    lines.append(f"{k}:")
                    for item in v:
                        lines.append(f"  - {item}")
                elif isinstance(v, dict):
                    lines.append(f"{k}:")
                    for subk, subv in v.items():
                        lines.append(f"  {subk}: {subv}")
                else:
                    lines.append(f"{k}: {v}")
            yaml_str = "\n".join(lines)

        body = self.instructions_markdown.strip()
        if not body:
            body = (
                f"# {self.name}\n\n"
                f"## Purpose\n{self.purpose}\n\n"
                f"## Core Rules\n1. Enforce constraints declared in specification.\n"
            )

        return f"---\n{yaml_str}\n---\n\n{body}\n"

    @classmethod
    def from_yaml_manifest(cls, raw_content: str) -> SkillSpecification:
        """Parses a SKILL.md content block containing YAML frontmatter and Markdown body."""
        content = raw_content.strip()
        if not content.startswith("---"):
            raise ValueError("Invalid SKILL.md: Missing leading frontmatter delimiter ('---').")

        parts = content.split("---", 2)
        if len(parts) < 3:
            raise ValueError("Invalid SKILL.md: Frontmatter is not closed by trailing '---'.")

        frontmatter_text = parts[1].strip()
        markdown_body = parts[2].strip()

        meta: dict[str, Any] = {}
        if yaml is not None:
            meta = yaml.safe_load(frontmatter_text) or {}
        else:
            # Simple fallback parser for basic key-value frontmatter
            for line in frontmatter_text.splitlines():
                if ":" in line and not line.strip().startswith("-"):
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip().strip("'\"")

        skill_id = meta.get("skill_id", "")
        name = meta.get("name", skill_id)
        purpose = meta.get("summary") or meta.get("purpose", "")
        domain = meta.get("domain", "general")
        version = str(meta.get("version", "1.0.0"))
        capabilities = meta.get("capabilities", [])
        if isinstance(capabilities, str):
            capabilities = [capabilities]
        tags = meta.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        deps = meta.get("dependencies", [])
        agents = meta.get("compatible_agents", [])
        modes = meta.get("compatible_project_modes", ["motion_only"])
        risk = meta.get("risk_level", "low")
        license_name = meta.get("license", "Apache-2.0")
        license_ev = meta.get("license_evidence", "")
        target_agent = meta.get("target_agent_id")

        return cls(
            skill_id=skill_id,
            name=name,
            purpose=purpose,
            domain=domain,
            version=version,
            tags=tags,
            capabilities=capabilities,
            entrypoint=meta.get("entrypoint", ""),
            inputs=meta.get("input_contracts") or meta.get("inputs", {}),
            outputs=meta.get("output_contracts") or meta.get("outputs", {}),
            dependencies=deps,
            compatible_agents=agents,
            compatible_project_modes=modes,
            risk_level=risk if risk in ALLOWED_RISK_LEVELS else "low",
            license=license_name,
            license_evidence=license_ev,
            instructions_markdown=markdown_body,
            target_agent_id=target_agent,
            metadata={"raw_meta": meta},
        )


def validate_specification(spec: SkillSpecification) -> list[str]:
    """Validates a SkillSpecification against integrity and security requirements.

    Returns a list of validation error descriptions. An empty list signifies success.
    """
    errors: list[str] = []

    # 1. Skill ID checks
    if not spec.skill_id:
        errors.append("skill_id is required and cannot be empty.")
    elif not SKILL_ID_REGEX.match(spec.skill_id):
        errors.append(
            f"skill_id '{spec.skill_id}' is invalid. Must contain only lowercase letters, digits, "
            f"dots, hyphens, and underscores, and cannot start or end with a symbol."
        )
    elif ".." in spec.skill_id:
        errors.append("Path traversal characters ('..') disallowed in skill_id.")

    # 2. Name & Purpose
    if not spec.name or not spec.name.strip():
        errors.append("Skill name is required.")
    if not spec.purpose or not spec.purpose.strip():
        errors.append("Skill purpose/summary is required.")

    # 3. Version checks
    if not spec.version or not SEMVER_REGEX.match(spec.version):
        errors.append(f"version '{spec.version}' is not a valid Semantic Version (e.g. '1.0.0').")

    # 4. Domain & Capabilities
    if not spec.domain or not spec.domain.strip():
        errors.append("Skill domain is required.")
    if not spec.capabilities:
        errors.append("Skill must declare at least one capability in 'capabilities'.")
    elif not all(isinstance(c, str) and c.strip() for c in spec.capabilities):
        errors.append("All items in 'capabilities' must be non-empty strings.")

    # 5. Risk level
    if spec.risk_level not in ALLOWED_RISK_LEVELS:
        errors.append(
            f"risk_level '{spec.risk_level}' is invalid. Allowed: {', '.join(sorted(ALLOWED_RISK_LEVELS))}."
        )

    # 6. Entrypoint path traversal check
    if spec.entrypoint:
        if ".." in spec.entrypoint or spec.entrypoint.startswith("/") or spec.entrypoint.startswith("\\"):
            errors.append(f"entrypoint path '{spec.entrypoint}' contains illegal traversal or absolute paths.")

    # 7. Contracts validation
    if not isinstance(spec.inputs, dict):
        errors.append("inputs must be a dictionary representing input contracts.")
    if not isinstance(spec.outputs, dict):
        errors.append("outputs must be a dictionary representing output contracts.")

    # 8. Target Agent ID check
    if spec.target_agent_id is not None:
        if not isinstance(spec.target_agent_id, str) or not spec.target_agent_id.strip():
            errors.append("target_agent_id must be a non-empty string when specified.")
        elif not re.match(r"^[a-z0-9_.-]+$", spec.target_agent_id):
            errors.append(f"target_agent_id '{spec.target_agent_id}' contains invalid characters.")
        else:
            try:
                from SYSTEM.registries.agent_registry import registry as agent_registry
                if agent_registry.get(spec.target_agent_id) is None:
                    errors.append(f"target_agent_id '{spec.target_agent_id}' is not registered in AgentRegistry.")
            except Exception:
                pass

    return errors


# =====================================================================
# Ambiguity Detection and LLM / Deterministic Requirement Intake
# =====================================================================

VAGUE_PATTERNS = [
    r"\bmake\s+it\s+better\b",
    r"\bfix\s+everything\b",
    r"\bdo\s+something\b",
    r"\bstandard\s+(stuff|things)\b",
    r"\bjust\s+work\b",
    r"\bany\s+animation\b",
]

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "motion": ["motion", "animation", "kinetic", "typography", "spring", "easing", "particles", "transition", "remotion"],
    "audio": ["audio", "speech", "voice", "clarity", "noise", "dsp", "volume", "sound", "whisper", "music"],
    "visual": ["visual", "scene", "layout", "palette", "theme", "color", "graphic", "image", "overlay"],
    "validation": ["validation", "guard", "check", "verify", "aspect", "bounds", "invariant", "schema"],
    "timeline": ["timeline", "cut", "sync", "sequence", "duration", "fps", "frame", "stitching"],
}


def detect_ambiguity(text: str, spec: SkillSpecification | None = None) -> list[str]:
    """Detects ambiguities, conflicting constraints, or severe underspecification in skill requirements."""
    ambiguities: list[str] = []
    lower_text = text.lower().strip()

    # 1. Vague phrases
    for pat in VAGUE_PATTERNS:
        if re.search(pat, lower_text):
            ambiguities.append(f"Requirement contains vague directive matching '{pat}'. Concrete behavior must be specified.")

    # 2. Insufficient length / content
    if len(lower_text) < 10:
        ambiguities.append("Requirement description is too brief (< 10 chars) to deduce reliable skill behavior.")

    # 3. Conflicting orientation / aspect constraints
    has_portrait = bool(re.search(r"\b(9:16|portrait|vertical)\b", lower_text))
    has_landscape = bool(re.search(r"\b(16:9|landscape|horizontal)\b", lower_text))
    if has_portrait and has_landscape and "both supported" not in lower_text and "responsive mode" not in lower_text:
        ambiguities.append("Requirement specifies conflicting aspect ratios (portrait 9:16 vs landscape 16:9) without declaring responsive adaptation mode.")

    # 4. Check parsed specification consistency if provided
    if spec is not None:
        if spec.domain == "general" and not any(k in lower_text for k in ["general", "utility"]):
            ambiguities.append("Target domain could not be definitively classified (defaulted to 'general').")
        if not spec.capabilities:
            ambiguities.append("No actionable capabilities extracted from requirement.")

    return ambiguities


def parse_requirement_deterministic(text: str) -> SkillSpecification:
    """Extracts a SkillSpecification from free-form text using deterministic rules and pattern extraction."""
    lower_text = text.lower().strip()

    # Determine domain
    matched_domain = "general"
    for dom, kws in DOMAIN_KEYWORDS.items():
        if any(kw in lower_text for kw in kws):
            matched_domain = dom
            break

    # Determine language
    language = "markdown"
    if any(k in lower_text for k in ["remotion", "tsx", "react component", "typescript", ".tsx"]):
        language = "tsx"
    elif any(k in lower_text for k in ["python", "script", "algorithm", "function", ".py"]):
        language = "python"

    # Extract clean slug for skill_id
    words = re.findall(r"[a-z0-9]+", lower_text)
    meaningful_words = [w for w in words if w not in {"a", "an", "the", "for", "with", "and", "or", "to", "in", "create", "make", "build", "skill"}][:3]
    slug = "_".join(meaningful_words) if meaningful_words else "unnamed_skill"
    skill_id = f"{matched_domain}.{slug}"

    # Extract capabilities
    capabilities: list[str] = []
    for dom_kws in DOMAIN_KEYWORDS.values():
        for kw in dom_kws:
            if kw in lower_text and kw not in capabilities:
                capabilities.append(kw)
    if not capabilities:
        capabilities.append(slug.replace("_", "-"))

    # Extract tags
    tags = list(set([matched_domain] + capabilities[:4] + ([language] if language != "markdown" else [])))

    purpose = text.strip()
    if len(purpose) > 200:
        purpose = purpose[:197] + "..."

    spec = SkillSpecification(
        skill_id=skill_id,
        name=slug.replace("_", " ").title(),
        purpose=purpose,
        domain=matched_domain,
        version="1.0.0",
        capabilities=capabilities,
        tags=tags,
        language=language,
        inputs={"context": "dict"},
        outputs={"result": "dict"},
        risk_level="low",
    )
    return spec


def parse_requirement_llm(requirement_text: str, timeout: float = 15.0) -> SkillSpecification:
    """Interprets a natural-language requirement using LLM gateway into a structured SkillSpecification."""
    try:
        from SYSTEM.core.llm_gateway import LlmGatewayRequest, llm_gateway
    except ImportError:
        logger.warning("LLM gateway not importable; falling back to deterministic requirement parser.")
        return parse_requirement_deterministic(requirement_text)

    system_prompt = (
        "You are an expert system skill architect. Convert the user's natural language requirement into a "
        "strict JSON object representing a SkillSpecification. The JSON must have:\n"
        "{\n"
        '  "skill_id": "domain.sub_capability",\n'
        '  "name": "Human Readable Title",\n'
        '  "purpose": "Precise summary of behavior",\n'
        '  "domain": "motion|audio|visual|validation|timeline|general",\n'
        '  "version": "1.0.0",\n'
        '  "capabilities": ["cap-one", "cap-two"],\n'
        '  "tags": ["tag1", "tag2"],\n'
        '  "language": "markdown|python|tsx",\n'
        '  "inputs": {"param1": "type"},\n'
        '  "outputs": {"output1": "type"},\n'
        '  "dependencies": [],\n'
        '  "risk_level": "low|medium|high",\n'
        '  "acceptance_criteria": ["Criteria 1", "Criteria 2"]\n'
        "}\n"
        "Output ONLY valid JSON. Do not include markdown code block formatting or explanations."
    )

    req = LlmGatewayRequest(
        project_id="system",
        stage_id="skill_factory",
        agent_id="skill_factory",
        purpose="spec_intake",
        user_prompt=requirement_text,
        system_prompt=system_prompt,
        model_profile="fast_structured",
        timeout_seconds=timeout,
    )

    try:
        resp = llm_gateway.execute(req)
        if resp.status == "succeeded" and resp.raw_text:
            cleaned = resp.raw_text.strip()
            if cleaned.startswith("```"):
                lines = cleaned.splitlines()
                cleaned = "\n".join([line for line in lines if not line.strip().startswith("```")]).strip()
            data = json.loads(cleaned)
            spec = SkillSpecification.from_dict(data)
            spec.metadata["parsed_via_llm"] = True
            errs = validate_specification(spec)
            if not errs:
                return spec
            logger.warning(f"LLM specification failed validation: {errs}; falling back to deterministic parser.")
    except Exception as e:
        logger.warning(f"LLM requirement parsing failed: {e}; falling back to deterministic parser.")

    return parse_requirement_deterministic(requirement_text)


def intake_specification(
    raw_input: str | dict[str, Any] | SkillSpecification,
    use_llm: bool = True,
) -> tuple[SkillSpecification, list[str]]:
    """Normalizes and validates incoming requirements (natural-language string, dict, or SkillSpecification).

    Returns:
        tuple[SkillSpecification, list[str]]: The parsed specification and any detected ambiguity warnings.
    """
    if isinstance(raw_input, SkillSpecification):
        spec = raw_input
        raw_text = spec.purpose or spec.name
    elif isinstance(raw_input, dict):
        spec = SkillSpecification.from_dict(raw_input)
        raw_text = spec.purpose or spec.name or json.dumps(raw_input)
    elif isinstance(raw_input, str):
        raw_text = raw_input
        # Check if it is a YAML manifest
        if raw_input.strip().startswith("---"):
            try:
                spec = SkillSpecification.from_yaml_manifest(raw_input)
            except Exception:
                spec = parse_requirement_llm(raw_input) if use_llm else parse_requirement_deterministic(raw_input)
        else:
            spec = parse_requirement_llm(raw_input) if use_llm else parse_requirement_deterministic(raw_input)
    else:
        raise ValueError(f"Unsupported specification input type: {type(raw_input)}")

    ambiguities = detect_ambiguity(raw_text, spec)
    spec.ambiguities = ambiguities
    return spec, ambiguities

