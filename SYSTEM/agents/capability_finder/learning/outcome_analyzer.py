"""Downstream Outcome Attribution and Causality Analyzer for Capability Finder.

Distinguishes:
1. Discovery succeeded vs Downstream task succeeded.
2. Capability discovery error vs Environmental/data error.
3. Attributable failure vs Inconclusive outcome.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from .case_collector import LearningCase


@dataclass
class OutcomeAttribution:
    """Detailed attribution analysis linking a downstream outcome to the capability decision."""
    case_id: str = ""
    is_attributable: bool = False
    attribution_category: str = "inconclusive"
    confidence: float = 0.5
    explanation: str = ""
    discovery_succeeded: bool = True
    task_succeeded: bool = True
    primary_failure_category: str = "NONE"
    recommended_remediation: dict[str, Any] = field(default_factory=dict)
    suggested_synonyms: dict[str, str] = field(default_factory=dict)
    suggested_routing_boost: dict[str, Any] = field(default_factory=dict)
    llm_diagnosis: str = ""
    is_llm_analyzed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class OutcomeAnalyzer:
    """Analyzes downstream task execution results and reviewer feedback to determine attribution."""

    ENVIRONMENTAL_PATTERNS = [
        "not found in path",
        "binary not found",
        "timeout",
        "out of memory",
        "connection refused",
        "disk full",
        "permission denied",
        "device unavailable",
    ]

    INPUT_DEFECT_PATTERNS = [
        "file not found",
        "corrupt",
        "header",
        "invalid wav",
        "unsupported codec",
        "zero bytes",
        "missing input audio",
    ]

    def _attempt_llm_diagnosis(
        self,
        query: str,
        capability: str,
        action: str,
        delegate_id: str,
        err: str,
    ) -> dict[str, Any] | None:
        """Attempts fast LLM root-cause diagnosis via LlmGateway with bounded timeout."""
        try:
            from SYSTEM.core.llm_gateway import LlmGatewayRequest, get_gateway
            prompt = (
                f"You are an expert root-cause diagnosis engine for an AI capability discovery system.\n"
                f"Analyze this downstream failure and suggest concrete self-learning remediations.\n\n"
                f"User Requirement / Query: {query}\n"
                f"Selected Capability: {capability}\n"
                f"Recommended Action: {action}\n"
                f"Delegate ID: {delegate_id}\n"
                f"Downstream Execution Error: {err}\n\n"
                f"Respond with ONLY a valid JSON object in this exact format:\n"
                f"{{\n"
                f'  "is_capability_fault": true,\n'
                f'  "root_cause": "Detailed explanation of why this capability failed",\n'
                f'  "suggested_synonyms": {{"synonym_key": "target_capability_token"}},\n'
                f'  "suggested_routing_boost": {{"domain": "motion", "preferred_delegate_id": "{delegate_id}", "boost_score": 0.25}},\n'
                f'  "recommended_action": "{action}"\n'
                f"}}"
            )
            req = LlmGatewayRequest(
                prompt=prompt,
                model_profile="fast_structured",
                system_instruction="You are a strict JSON diagnosis engine. Return only JSON.",
                timeout_seconds=12,
            )
            res = get_gateway().execute(req)
            if res.status == "succeeded" and res.text:
                text = res.text.strip()
                if text.startswith("```"):
                    text = re.sub(r"^```(?:json)?\s*", "", text)
                    text = re.sub(r"\s*```$", "", text)
                return json.loads(text)
        except Exception:
            pass
        return None

    def analyze_outcome(
        self,
        case: LearningCase | None = None,
        task_error: str | None = None,
        task_status: str = "succeeded",
        discovery_result: dict[str, Any] | None = None,
        execution_outcome: dict[str, Any] | None = None,
        execution_error: str | None = None,
        environment_info: dict[str, Any] | None = None,
        enable_llm_diagnosis: bool = False,
    ) -> OutcomeAttribution:
        """Determines if a task outcome is attributable to the capability discovery decision."""
        cid = case.case_id if case else ""
        err = execution_error or task_error or ""
        err_lower = err.lower()

        # Determine overall task status
        if execution_outcome:
            status = execution_outcome.get("status", "failed" if err else "completed")
            is_task_success = status in ("completed", "succeeded") and not err
        else:
            is_task_success = (task_status == "succeeded") and not err

        if is_task_success:
            return OutcomeAttribution(
                case_id=cid,
                is_attributable=True,
                attribution_category="execution_succeeded",
                confidence=1.0,
                explanation="Downstream task executed successfully using the selected capability and delegate.",
                discovery_succeeded=True,
                task_succeeded=True,
                primary_failure_category="NONE",
            )

        # Check for environmental non-attributable failures
        if any(p in err_lower for p in self.ENVIRONMENTAL_PATTERNS):
            return OutcomeAttribution(
                case_id=cid,
                is_attributable=False,
                attribution_category="unrelated_environmental",
                confidence=0.90,
                explanation=f"Failure appears to be environmental ({err}) rather than a capability discovery error.",
                discovery_succeeded=True,
                task_succeeded=False,
                primary_failure_category="ENVIRONMENTAL",
            )

        # Check for input defects
        if any(p in err_lower for p in self.INPUT_DEFECT_PATTERNS):
            return OutcomeAttribution(
                case_id=cid,
                is_attributable=False,
                attribution_category="input_defect",
                confidence=0.85,
                explanation=f"Failure appears to be caused by an input defect ({err}).",
                discovery_succeeded=True,
                task_succeeded=False,
                primary_failure_category="INPUT_DEFECT",
            )

        # Capability mismatches (delegate could not perform task, or action was unsupported)
        mismatch_tokens = [
            "unsupported action",
            "action not implemented",
            "missing capability",
            "does not support",
            "attributeerror",
            "not implemented",
        ]
        if any(p in err_lower for p in mismatch_tokens):
            del_id = (case.suggested_delegate_id if case else (discovery_result.get("suggested_delegate_id") if discovery_result else "unknown"))
            cand_cap = discovery_result.get("primary_capability_needed", "") if discovery_result else ""
            rec_act = discovery_result.get("recommended_action", "ADAPT") if discovery_result else "ADAPT"
            query_str = case.parsed_requirement.get("query", "") if case and case.parsed_requirement else (discovery_result.get("query", "") if discovery_result else "")

            llm_diag_data = None
            if enable_llm_diagnosis and err:
                llm_diag_data = self._attempt_llm_diagnosis(
                    query=query_str,
                    capability=cand_cap,
                    action=rec_act,
                    delegate_id=del_id,
                    err=err,
                )

            return OutcomeAttribution(
                case_id=cid,
                is_attributable=True,
                attribution_category="capability_mismatch",
                confidence=0.95,
                explanation=f"Delegate '{del_id}' failed due to unsupported action or capability mismatch: {err}",
                discovery_succeeded=False,
                task_succeeded=False,
                primary_failure_category="CAPABILITY_MISMATCH",
                recommended_remediation=llm_diag_data or {},
                suggested_synonyms=llm_diag_data.get("suggested_synonyms", {}) if llm_diag_data else {},
                suggested_routing_boost=llm_diag_data.get("suggested_routing_boost", {}) if llm_diag_data else {},
                llm_diagnosis=llm_diag_data.get("root_cause", "") if llm_diag_data else "",
                is_llm_analyzed=bool(llm_diag_data),
            )

        # Constraint failure (e.g. aspect ratio mismatch, font missing)
        if "aspect ratio" in err_lower or "language" in err_lower or "font" in err_lower:
            return OutcomeAttribution(
                case_id=cid,
                is_attributable=True,
                attribution_category="missing_constraint",
                confidence=0.85,
                explanation=f"Task failed due to unmet constraint: {err}",
                discovery_succeeded=False,
                task_succeeded=False,
                primary_failure_category="MISSING_CONSTRAINT",
            )

        # If error detail is vague or missing
        return OutcomeAttribution(
            case_id=cid,
            is_attributable=False,
            attribution_category="inconclusive",
            confidence=0.40,
            explanation=f"Insufficient evidence to attribute error '{err}' to capability finder.",
            discovery_succeeded=False,
            task_succeeded=False,
            primary_failure_category="INCONCLUSIVE",
        )


outcome_analyzer = OutcomeAnalyzer()
