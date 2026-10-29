"""The one generic LLM reviewer call of the Agent System: a fail-closed structured review of any prompt.

Domain projects build their own review prompts and gates on top of it (the video project's stage gate is SYSTEM/policies/llm_review.py).
An unavailable LLM or a malformed answer is never a pass: it is status 'blocked' with a blocker finding.
"""
from __future__ import annotations

import time
from typing import Any, Literal, TypedDict

from SYSTEM.core import llm_client, llm_gateway

LlmReviewStatus = Literal["passed", "needs_review", "blocked", "failed"]


class LlmFinding(TypedDict, total=False):
    severity: Literal["blocker", "error", "warning", "info"]
    category: str
    message: str
    scene_id: str | int | None
    recommendation: str | None


def ask_reviewer(
    *,
    project_id: str,
    stage_id: str,
    agent_id: str,
    system_prompt: str,
    user_prompt: str,
    timeout: int = 60,
    input_fingerprint: str | None = None,
    artifact_refs: list[dict[str, str]] | None = None,
    metadata: dict[str, Any] | None = None,
    images: list[str] | None = None,
) -> dict[str, Any]:
    """The one LLM reviewer call: returns status, score, summary, findings, provider, model, latency_ms, error.
    images: picture files the reviewer must look at (only a provider that can see accepts them: llm_client.can_look).
    Fails closed: an unavailable LLM or a malformed answer is status='blocked' with a blocker finding."""
    t0 = time.perf_counter()
    structured_schema = {
        "status": "passed | needs_review | blocked | failed",
        "score": 0.85,
        "summary": "review summary",
        "findings": [
            {
                "severity": "blocker | error | warning | info",
                "category": "quality | technical | narrative",
                "message": "finding description",
                "scene_id": "optional scene number",
                "recommendation": "optional action recommendation",
            }
        ],
    }

    def unavailable(err_msg: str, provider: str | None, model: str | None, latency: float) -> dict[str, Any]:
        return {
            "status": "blocked",
            "score": 0.0,
            "summary": f"LLM review unavailable or failed: {err_msg}",
            "findings": [{
                "severity": "blocker",
                "category": "llm_unavailable",
                "message": f"LLM review failed: {err_msg}. Nothing can be approved without a successful LLM review.",
            }],
            "provider": provider,
            "model": model,
            "latency_ms": latency,
            "error": err_msg,
        }

    req = llm_gateway.LlmGatewayRequest(
        project_id=project_id,
        stage_id=stage_id,
        agent_id=agent_id,
        purpose="review",
        user_prompt=user_prompt,
        system_prompt=system_prompt,
        model_profile="reasoning_review",
        structured_schema=structured_schema,
        timeout=timeout,
        input_fingerprint=input_fingerprint,
        input_artifact_refs=artifact_refs or [],
        metadata=metadata or {},
        images=images or [],
    )
    try:
        resp = llm_gateway.get_gateway().execute(req)
    except Exception as e:
        prov, mdl, _, _ = llm_client.resolve_provider_config()
        return unavailable(str(e), prov, mdl, round((time.perf_counter() - t0) * 1000))
    if resp.error or not resp.structured_data:
        return unavailable(resp.error or "LLM returned invalid or malformed structured JSON response", resp.provider, resp.model, resp.latency_ms)

    data = resp.structured_data
    status_val: LlmReviewStatus = data.get("status", "needs_review")
    if status_val not in ("passed", "needs_review", "blocked", "failed"):
        status_val = "needs_review"
    score = float(data.get("score", 0.8 if status_val == "passed" else 0.4))
    findings: list[LlmFinding] = [
        {
            "severity": f.get("severity", "warning"),
            "category": str(f.get("category", "quality")),
            "message": str(f.get("message", "")),
            "scene_id": f.get("scene_id"),
            "recommendation": f.get("recommendation"),
        }
        for f in data.get("findings", []) if isinstance(f, dict)
    ]
    # Fail-closed guard: blockers or errors must never be marked passed
    if any(f.get("severity") == "blocker" for f in findings):
        status_val = "blocked"
    elif any(f.get("severity") == "error" for f in findings) and status_val == "passed":
        status_val = "needs_review"
    return {
        "status": status_val,
        "score": score,
        "summary": str(data.get("summary", f"{stage_id} LLM review completed")),
        "findings": findings,
        "provider": resp.provider,
        "model": resp.model,
        "latency_ms": resp.latency_ms,
        "error": resp.error,
    }
