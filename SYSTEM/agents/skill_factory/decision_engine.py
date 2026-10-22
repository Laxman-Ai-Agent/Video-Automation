"""Reuse / Adapt / Create Decision Engine for Skill Factory.

Enforces:
1. Priority order: REUSE -> ADAPT -> CREATE.
2. Prevention of duplicate skill creation when an approved compatible skill exists.
3. Adaptation versioning preserving base skills without clobbering.
4. Seamless integration with SkillRegistry and CapabilityRegistry.
"""
from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from SYSTEM.agents.skill_factory.specification import SkillSpecification
from SYSTEM.registries.capability_registry import get_capability_registry
from SYSTEM.registries.skill_registry import SkillRecord, get_skill_registry

logger = logging.getLogger("skill_factory.decision_engine")

DecisionAction = Literal["REUSE", "ADAPT", "COMPOSE", "CREATE", "CLARIFY"]


@dataclass
class SkillDecision:
    """Outcome of evaluating whether to reuse, adapt, or create a skill."""
    action: DecisionAction
    skill_id: str
    version: str
    reason: str
    base_skill_id: str | None = None
    base_version: str | None = None
    matched_capabilities: list[str] = field(default_factory=list)
    alternatives: list[str] = field(default_factory=list)
    composed_skills: list[str] = field(default_factory=list)
    clarification_needed: str | None = None
    confidence: float = 1.0
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


try:
    from SYSTEM.agents.capability_finder.discovery.semantic_index import SEMANTIC_SYNONYMS
except ImportError:
    SEMANTIC_SYNONYMS = {
        "motion": ["animation", "animate", "movement", "kinetic", "transition", "dynamics"],
        "kinetic_typography": ["text_animation", "animated_text", "kinetic_text", "typography_motion", "word_highlight", "typography_layout", "readability_optimization"],
        "audio": ["sound", "speech", "voice", "acoustic", "narration"],
        "transcribe": ["transcription", "speech_to_text", "asr", "subtitles", "captions", "whisper"],
        "visual": ["scene", "artwork", "composition", "image", "asset"],
    }


def _get_synonyms(term: str) -> set[str]:
    """Retrieves domain synonyms and related terms for a given capability token."""
    cleaned = term.lower().replace("-", "_").strip()
    syns = {cleaned, term.lower().replace("_", "-").strip()}
    for key, values in SEMANTIC_SYNONYMS.items():
        all_group = [key] + values
        if cleaned in all_group or any(v in cleaned for v in all_group):
            for v in all_group:
                syns.add(v.replace("_", "-"))
                syns.add(v.replace("-", "_"))
    return syns


class DecisionEngine:
    """Evaluates requirements against registered skills to determine Reuse vs Adapt vs Compose vs Create vs Clarify."""

    def __init__(self) -> None:
        self._skill_registry = get_skill_registry()
        self._cap_registry = get_capability_registry()

    def evaluate(
        self,
        spec: SkillSpecification | dict[str, Any],
        allow_adapt: bool = True,
        preferred_action: str | None = None,
    ) -> SkillDecision:
        """Evaluates a requirement against existing skills and returns a deterministic SkillDecision."""
        if isinstance(spec, dict):
            spec_obj = SkillSpecification.from_dict(spec)
        else:
            spec_obj = spec

        # -------------------------------------------------------------
        # 0. Ambiguity / Insufficient Specification Check (CLARIFY)
        # -------------------------------------------------------------
        ambiguities = getattr(spec_obj, "ambiguities", [])
        if not ambiguities and hasattr(spec_obj, "purpose"):
            from SYSTEM.agents.skill_factory.specification import detect_ambiguity
            ambiguities = detect_ambiguity(spec_obj.purpose, spec_obj)

        if any("conflicting" in a.lower() or "vague" in a.lower() or "too brief" in a.lower() for a in ambiguities):
            return SkillDecision(
                action="CLARIFY",
                skill_id=spec_obj.skill_id,
                version=spec_obj.version or "1.0.0",
                reason=f"Specification contains critical ambiguities: {'; '.join(ambiguities)}. Clarification required before authoring.",
                clarification_needed="; ".join(ambiguities),
                confidence=0.3,
                provenance={"ambiguity_findings": ambiguities},
            )

        self._skill_registry.initialize()
        approved_skills = self._skill_registry.list_skills(status="approved")

        target_caps = set(c.lower().strip() for c in spec_obj.capabilities)
        target_domain = spec_obj.domain.lower().strip()

        # -------------------------------------------------------------
        # 1. Check for Exact or High-Relevance REUSE
        # -------------------------------------------------------------
        exact_match: SkillRecord | None = None
        best_overlap_skill: SkillRecord | None = None
        max_overlap_count = 0

        for candidate in approved_skills:
            cand_caps = set(c.lower().strip() for c in candidate.capabilities)
            overlap = target_caps.intersection(cand_caps)

            # Check if candidate covers ALL required capabilities
            if target_caps and target_caps.issubset(cand_caps):
                exact_match = candidate
                break

            # Check if skill_id or name matches exactly
            if candidate.skill_id.lower() == spec_obj.skill_id.lower():
                exact_match = candidate
                break

            if len(overlap) > max_overlap_count:
                max_overlap_count = len(overlap)
                best_overlap_skill = candidate

        if exact_match is not None and preferred_action != "ADAPT":
            return SkillDecision(
                action="REUSE",
                skill_id=exact_match.skill_id,
                version=exact_match.version,
                reason=(
                    f"Approved compatible skill '{exact_match.skill_id}' (v{exact_match.version}) "
                    f"in domain '{exact_match.domain}' fully covers required capabilities."
                ),
                matched_capabilities=list(target_caps.intersection(set(c.lower() for c in exact_match.capabilities))),
                alternatives=[s.skill_id for s in approved_skills if s.skill_id != exact_match.skill_id][:3],
                provenance={
                    "source": exact_match.source,
                    "content_sha256": exact_match.content_sha256,
                    "license": exact_match.license,
                },
            )

        # -------------------------------------------------------------
        # 1.1 Check for Parameterized Variant REUSE
        # -------------------------------------------------------------
        if preferred_action != "ADAPT":
            for candidate in approved_skills:
                variants = set(v.lower().strip() for v in candidate.metadata.get("supported_variants", []))
                input_contracts = candidate.input_contracts or {}
                for param_name, param_spec in input_contracts.items():
                    if isinstance(param_spec, dict) and "options" in param_spec:
                        variants.update(str(opt).lower().strip() for opt in param_spec["options"])

                matched_variants = target_caps.intersection(variants)
                spec_inputs = spec_obj.inputs or {}
                for k, v in spec_inputs.items():
                    if str(v).lower().strip() in variants:
                        matched_variants.add(str(v).lower().strip())

                if matched_variants:
                    logger.info(
                        f"Variant match detected: candidate '{candidate.skill_id}' "
                        f"supports requested variant(s): {matched_variants}"
                    )
                    return SkillDecision(
                        action="REUSE",
                        skill_id=candidate.skill_id,
                        version=candidate.version,
                        reason=(
                            f"Approved parameterized skill '{candidate.skill_id}' (v{candidate.version}) "
                            f"natively supports requested variant(s) '{', '.join(sorted(matched_variants))}' "
                            f"through input configuration contracts. Reuse prevents redundant skill duplication."
                        ),
                        matched_capabilities=list(matched_variants),
                        alternatives=[s.skill_id for s in approved_skills if s.skill_id != candidate.skill_id][:3],
                        provenance={
                            "source": candidate.source,
                            "content_sha256": candidate.content_sha256,
                            "license": candidate.license,
                            "variant_matched": list(matched_variants),
                        },
                    )

        # -------------------------------------------------------------
        # 1.2 Check for Semantic & Synonym REUSE (Duplicate Prevention)
        # -------------------------------------------------------------
        if preferred_action != "ADAPT":
            for candidate in approved_skills:
                cand_caps = set(c.lower().strip() for c in candidate.capabilities)
                cand_pool = set(cand_caps)
                for c in cand_caps:
                    cand_pool.update(_get_synonyms(c))

                # Also add tokens from skill_id and name
                cand_pool.update(re.findall(r"[a-z0-9]+", candidate.skill_id.lower()))
                cand_pool.update(re.findall(r"[a-z0-9]+", candidate.name.lower()))

                # If all target capabilities have direct or synonym coverage in candidate
                if target_caps and all(
                    any(t_syn in cand_pool for t_syn in _get_synonyms(tc))
                    for tc in target_caps
                ):
                    logger.info(
                        f"Semantic synonym match: candidate '{candidate.skill_id}' "
                        f"covers requested capabilities '{target_caps}'"
                    )
                    return SkillDecision(
                        action="REUSE",
                        skill_id=candidate.skill_id,
                        version=candidate.version,
                        reason=(
                            f"Approved skill '{candidate.skill_id}' (v{candidate.version}) semantically satisfies "
                            f"required capabilities ({', '.join(sorted(target_caps))}) via verified domain synonyms. "
                            f"Reuse prevents duplicate skill creation from alternative phrasing."
                        ),
                        matched_capabilities=list(target_caps),
                        alternatives=[s.skill_id for s in approved_skills if s.skill_id != candidate.skill_id][:3],
                        confidence=0.92,
                        provenance={
                            "source": candidate.source,
                            "content_sha256": candidate.content_sha256,
                            "license": candidate.license,
                            "match_type": "semantic_synonym_equivalence",
                        },
                    )

        # -------------------------------------------------------------
        # 1.3 Check for Multi-Skill COMPOSE
        # -------------------------------------------------------------
        if len(target_caps) >= 2 and preferred_action != "ADAPT":
            covered_caps: set[str] = set()
            composing_skills: list[SkillRecord] = []
            for candidate in approved_skills:
                cand_caps = set(c.lower().strip() for c in candidate.capabilities)
                overlap = target_caps.intersection(cand_caps)
                # If this candidate adds coverage not yet covered
                if overlap - covered_caps:
                    composing_skills.append(candidate)
                    covered_caps.update(overlap)
                    if target_caps.issubset(covered_caps):
                        break

            if target_caps.issubset(covered_caps) and len(composing_skills) >= 2:
                skill_names = [s.skill_id for s in composing_skills]
                return SkillDecision(
                    action="COMPOSE",
                    skill_id=f"composed.{spec_obj.skill_id.split('.')[-1]}",
                    version="1.0.0",
                    composed_skills=skill_names,
                    reason=(
                        f"Requirement spans multiple distinct capabilities ({', '.join(sorted(target_caps))}) "
                        f"satisfied across existing skills: {', '.join(skill_names)}. "
                        f"Composing existing skills avoids creating a redundant composite implementation."
                    ),
                    matched_capabilities=list(covered_caps),
                    alternatives=[s.skill_id for s in approved_skills if s.skill_id not in skill_names][:3],
                    provenance={"mode": "skill_composition", "components": skill_names},
                )

        # -------------------------------------------------------------
        # 2. Check for ADAPT Opportunities
        # -------------------------------------------------------------
        if allow_adapt:
            adapt_candidate: SkillRecord | None = None
            if best_overlap_skill and max_overlap_count > 0:
                adapt_candidate = best_overlap_skill
            else:
                for cand in approved_skills:
                    if cand.domain.lower() == target_domain and cand.license in (
                        "Apache-2.0",
                        "MIT",
                        "BSD-3-Clause",
                        "CC-BY-4.0",
                    ):
                        adapt_candidate = cand
                        break

            if adapt_candidate is not None:
                base_ver = adapt_candidate.version
                suggested_ver = self._increment_minor_version(base_ver)

                return SkillDecision(
                    action="ADAPT",
                    skill_id=spec_obj.skill_id or f"{adapt_candidate.skill_id}.adapted",
                    version=suggested_ver,
                    base_skill_id=adapt_candidate.skill_id,
                    base_version=base_ver,
                    reason=(
                        f"Existing approved skill '{adapt_candidate.skill_id}' (v{base_ver}) in domain "
                        f"'{adapt_candidate.domain}' partially satisfies requirements. "
                        f"Adapting as version {suggested_ver} while preserving active v{base_ver}."
                    ),
                    matched_capabilities=list(
                        target_caps.intersection(set(c.lower() for c in adapt_candidate.capabilities))
                    ),
                    alternatives=[s.skill_id for s in approved_skills if s.skill_id != adapt_candidate.skill_id][:3],
                    provenance={
                        "base_skill_id": adapt_candidate.skill_id,
                        "base_version": base_ver,
                        "license": adapt_candidate.license,
                    },
                )

        # -------------------------------------------------------------
        # 3. Fallback to CREATE
        # -------------------------------------------------------------
        return SkillDecision(
            action="CREATE",
            skill_id=spec_obj.skill_id,
            version=spec_obj.version or "1.0.0",
            reason=(
                f"No existing approved skill covers capabilities: {', '.join(sorted(target_caps))} in domain "
                f"'{spec_obj.domain}'. Creating new canonical skill is justified."
            ),
            alternatives=[s.skill_id for s in approved_skills[:3]],
            provenance={"mode": "new_skill_authoring"},
        )

    def _increment_minor_version(self, ver_str: str) -> str:
        """Increments minor version (e.g. 1.0.0 -> 1.1.0)."""
        parts = ver_str.split(".")
        if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
            major = int(parts[0])
            minor = int(parts[1]) + 1
            return f"{major}.{minor}.0"
        return f"{ver_str}.1"


# Default singleton instance
decision_engine = DecisionEngine()
