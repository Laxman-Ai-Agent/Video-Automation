"""Capability Gap Analysis and Recommendation Engine for Capability Finder.

Answers:
1. What capability is required?
2. Which existing agent, skill, or tool provides it?
3. Where is the implementation located and what evidence exists?
4. What constraints or requirements remain unsatisfied?
5. Should the capability be REUSED, ADAPTED, CREATED via SkillFactory, or require a NEW AGENT?
6. Are runtime prerequisites (FFmpeg, local models) satisfied?
"""
from __future__ import annotations

import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from .matcher import CapabilityMatch
from .requirement_parser import ParsedRequirement

RecommendedAction = Literal[
    "REUSE",
    "ADAPT",
    "COMPOSE",
    "REGISTER_EXISTING",
    "RESOLVE_PREREQUISITES",
    "CREATE_SKILL",
    "CREATE_AGENT",
]


@dataclass
class GapAnalysisReport:
    """Structured report detailing capability fulfillment, missing elements, and recommended actions."""
    query: str
    primary_capability_needed: str
    overall_status: Literal["satisfied", "partial", "missing"]
    gap_category: str = "none"  # "none", "missing_capability", "unregistered_code", "missing_prerequisites", "constraint_mismatch", "composable_partial"
    severity: str = "info"  # "info", "warning", "critical"
    confidence: float = 1.0
    satisfied_capabilities: list[CapabilityMatch] = field(default_factory=list)
    partial_capabilities: list[CapabilityMatch] = field(default_factory=list)
    unregistered_capabilities: list[CapabilityMatch] = field(default_factory=list)
    reusable_components: list[dict[str, Any]] = field(default_factory=list)
    missing_requirements: list[str] = field(default_factory=list)
    recommended_action: RecommendedAction = "REUSE"
    action_rationale: str = ""
    suggested_delegate_id: str | None = None
    delegate_agent: str | None = None
    prerequisites_satisfied: bool = True
    unmet_prerequisites: list[str] = field(default_factory=list)
    evidence_summary: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "primary_capability_needed": self.primary_capability_needed,
            "overall_status": self.overall_status,
            "gap_category": self.gap_category,
            "severity": self.severity,
            "confidence": self.confidence,
            "satisfied_capabilities": [c.to_dict() for c in self.satisfied_capabilities],
            "partial_capabilities": [c.to_dict() for c in self.partial_capabilities],
            "unregistered_capabilities": [c.to_dict() for c in self.unregistered_capabilities],
            "reusable_components": self.reusable_components,
            "missing_requirements": self.missing_requirements,
            "recommended_action": self.recommended_action,
            "action_rationale": self.action_rationale,
            "suggested_delegate_id": self.suggested_delegate_id,
            "delegate_agent": self.delegate_agent or self.suggested_delegate_id,
            "prerequisites_satisfied": self.prerequisites_satisfied,
            "unmet_prerequisites": self.unmet_prerequisites,
            "evidence_summary": self.evidence_summary,
        }


class GapAnalyzer:
    """Evaluates candidate matches against requirements to compute gaps and recommended actions."""

    def analyze(
        self,
        req: ParsedRequirement,
        matches: list[CapabilityMatch],
        project_dir: Path | None = None,
    ) -> GapAnalysisReport:
        """Performs structured gap analysis on candidate matches."""
        satisfied: list[CapabilityMatch] = []
        partial: list[CapabilityMatch] = []
        unregistered: list[CapabilityMatch] = []
        missing_reqs: list[str] = []

        # 1. Prerequisite verification
        unmet_prereqs: list[str] = []
        for dep in req.runtime_dependencies:
            dep_clean = dep.lower().strip()
            if dep_clean == "ffmpeg" and not shutil.which("ffmpeg"):
                unmet_prereqs.append("Missing FFmpeg binary in system PATH")
            elif dep_clean == "ffprobe" and not shutil.which("ffprobe"):
                unmet_prereqs.append("Missing FFprobe binary in system PATH")
            elif dep_clean in ("faster_whisper", "whisper"):
                try:
                    from SYSTEM.core import config
                    models_dir = config.PROJECT_ROOT / "models"
                    if not ((models_dir / "hf").exists() or any(models_dir.glob("*.bin"))):
                        unmet_prereqs.append("Local Whisper model weights not detected in models/ directory")
                except Exception:
                    unmet_prereqs.append("Unable to verify local Whisper model directory")

        prereqs_ok = len(unmet_prereqs) == 0

        # 2. Partition matches into satisfied, partial, and unregistered AST symbols
        multi_func = len(req.functional_requirements) > 1
        for m in matches:
            if m.source_type == "ast_discovered":
                if m.score >= 0.35:
                    unregistered.append(m)
                continue

            covers_all_funcs = True
            if multi_func:
                c_str = f"{m.capability_id} {m.source_id} {m.record}".lower()
                for fn in req.functional_requirements:
                    fn_tokens = [p for p in fn.lower().split("_") if len(p) > 3]
                    if fn_tokens and not all(t in c_str for t in fn_tokens):
                        covers_all_funcs = False
                        break

            if (
                covers_all_funcs
                and (m.match_type == "exact" or (m.score >= 0.75 and "primary_capability" in m.matched_by))
                and len(m.constraints_unmet) == 0
            ):
                satisfied.append(m)
            elif m.score >= 0.40:
                partial.append(m)

        reusable_comps: list[dict[str, Any]] = [
            {"id": m.capability_id, "source": m.source_id, "score": m.score, "type": m.source_type}
            for m in (satisfied + partial + unregistered)
        ]

        # 3. Determine overall status, gap category, and recommended action
        if not prereqs_ok and (satisfied or partial):
            overall_status: Literal["satisfied", "partial", "missing"] = "partial" if partial and not satisfied else "satisfied"
            top_cand = (satisfied or partial)[0]
            recommended_action: RecommendedAction = "RESOLVE_PREREQUISITES"
            gap_category = "missing_prerequisites"
            severity = "warning"
            confidence = 0.95
            suggested_delegate = top_cand.source_id
            rationale = (
                f"Capability '{req.primary_capability}' is implemented by {top_cand.source_type} '{top_cand.source_id}', "
                f"but runtime dependencies are missing: {'; '.join(unmet_prereqs)}."
            )
        elif satisfied and prereqs_ok:
            overall_status = "satisfied"
            top_match = satisfied[0]
            recommended_action = "REUSE"
            gap_category = "none"
            severity = "info"
            confidence = top_match.score
            suggested_delegate = top_match.source_id
            rationale = (
                f"Capability '{req.primary_capability}' is fully satisfied by existing {top_match.source_type} "
                f"'{top_match.source_id}' with all required constraints met."
            )
        elif unregistered and not satisfied and (not partial or unregistered[0].score > (partial[0].score if partial else 0.0)):
            overall_status = "partial"
            top_ast = unregistered[0]
            recommended_action = "REGISTER_EXISTING"
            gap_category = "unregistered_code"
            severity = "warning"
            confidence = top_ast.score
            suggested_delegate = "skill_factory" if "skill" in top_ast.source_path.lower() else "main_architecture_agent"
            rationale = (
                f"Capability '{req.primary_capability}' was discovered in source file '{top_ast.source_path}' "
                f"as symbol '{top_ast.source_id}', but is not yet registered in CapabilityRegistry. "
                f"Recommended action is to REGISTER_EXISTING implementation."
            )
        elif (
            len(req.functional_requirements) > 1
            and len(partial) >= 2
            and req.domain in ("motion", "visual", "composition", "audio")
        ):
            overall_status = "partial"
            top_partial = partial[0]
            recommended_action = "COMPOSE"
            gap_category = "composable_partial"
            severity = "info"
            confidence = 0.80
            suggested_delegate = "skill_factory"
            for p in partial:
                missing_reqs.extend(p.constraints_unmet)
            missing_reqs = list(dict.fromkeys(missing_reqs))
            rationale = (
                f"Found {len(partial)} partial capabilities covering distinct aspects of '{req.primary_capability}'. "
                f"Recommended action is to COMPOSE them into an integrated pipeline skill."
            )
        elif partial:
            overall_status = "partial"
            top_partial = partial[0]
            suggested_delegate = top_partial.source_id
            missing_reqs.extend(top_partial.constraints_unmet)
            gap_category = "constraint_mismatch" if top_partial.constraints_unmet else "partial_match"
            severity = "warning"
            confidence = top_partial.score

            if top_partial.source_type == "skill" or req.domain in ("motion", "visual"):
                recommended_action = "ADAPT"
                rationale = (
                    f"Existing skill/agent '{top_partial.source_id}' partially matches "
                    f"(score {top_partial.score:.2f}) but has unmet constraints: {'; '.join(top_partial.constraints_unmet)}. "
                    f"Recommended action is to ADAPT the existing skill configuration."
                )
            else:
                recommended_action = "ADAPT"
                rationale = (
                    f"Found partial capability in {top_partial.source_type} '{top_partial.source_id}', "
                    f"requiring adaptation or parameter tuning."
                )
        else:
            overall_status = "missing"
            gap_category = "missing_capability"
            severity = "critical"
            confidence = 1.0
            missing_reqs.append(f"No existing capability found for '{req.primary_capability}' in domain '{req.domain}'")
            for k, v in req.constraints.items():
                missing_reqs.append(f"Unsatisfied constraint: {k}={v}")

            # Decide between CREATE_SKILL vs CREATE_AGENT
            if req.domain in ("motion", "visual", "styling", "audio") and not req.primary_capability.startswith("core_"):
                recommended_action = "CREATE_SKILL"
                suggested_delegate = "skill_factory"
                rationale = (
                    f"Capability '{req.primary_capability}' is missing. Since it represents a declarative or "
                    f"stylistic capability in the '{req.domain}' domain, it can be synthesized by SkillFactoryAgent."
                )
            else:
                recommended_action = "CREATE_AGENT"
                suggested_delegate = "main_architecture_agent"
                rationale = (
                    f"Capability '{req.primary_capability}' is completely missing and requires core architectural "
                    f"agent implementation under SYSTEM/agents/."
                )

        # Gather evidence refs
        evidence_summary: list[dict[str, Any]] = []
        for m in (satisfied + partial + unregistered)[:5]:
            evidence_summary.extend(m.evidence_refs)

        return GapAnalysisReport(
            query=req.raw_query,
            primary_capability_needed=req.primary_capability,
            overall_status=overall_status,
            gap_category=gap_category,
            severity=severity,
            confidence=round(confidence, 3),
            satisfied_capabilities=satisfied,
            partial_capabilities=partial,
            unregistered_capabilities=unregistered,
            reusable_components=reusable_comps,
            missing_requirements=missing_reqs,
            recommended_action=recommended_action,
            action_rationale=rationale,
            suggested_delegate_id=suggested_delegate,
            delegate_agent=suggested_delegate,
            prerequisites_satisfied=prereqs_ok,
            unmet_prerequisites=unmet_prereqs,
            evidence_summary=evidence_summary,
        )


gap_analyzer = GapAnalyzer()
