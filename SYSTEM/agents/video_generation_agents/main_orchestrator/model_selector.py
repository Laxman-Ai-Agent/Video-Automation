"""Adaptive Model Selection and Budget Manager for Main Orchestrator Agent.

Selects appropriate model profiles based on task complexity:
- fast_structured: Quick plan extraction, simple decision evaluations, status summaries.
- reasoning_review: Deep failure diagnosis, root-cause analysis, lesson synthesis.

Enforces bounded token limits, tracks execution latency, and interfaces with
SYSTEM.core.llm_gateway and SYSTEM.observability.llm_usage.
"""
from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

try:
    from SYSTEM.core import llm_gateway
except ImportError:
    from backend import llm_gateway

try:
    from SYSTEM.observability import llm_usage
except ImportError:
    from backend import llm_usage

logger = logging.getLogger("orchestrator.model_selector")

TaskComplexity = Literal["simple", "moderate", "complex", "diagnostic"]


@dataclass
class ModelSelectionPolicy:
    task_type: str
    complexity: TaskComplexity
    preferred_profile: llm_gateway.ModelProfile
    max_tokens: int
    temperature: float
    timeout_seconds: float
    retry_limit: int = 2


DEFAULT_POLICIES: dict[str, ModelSelectionPolicy] = {
    "plan": ModelSelectionPolicy(
        task_type="plan",
        complexity="moderate",
        preferred_profile="fast_structured",
        max_tokens=1500,
        temperature=0.2,
        timeout_seconds=25.0,
        retry_limit=2,
    ),
    "diagnose": ModelSelectionPolicy(
        task_type="diagnose",
        complexity="diagnostic",
        preferred_profile="reasoning_review",
        max_tokens=2048,
        temperature=0.1,
        timeout_seconds=35.0,
        retry_limit=2,
    ),
    "reflect": ModelSelectionPolicy(
        task_type="reflect",
        complexity="complex",
        preferred_profile="reasoning_review",
        max_tokens=2048,
        temperature=0.2,
        timeout_seconds=30.0,
        retry_limit=1,
    ),
    "decide": ModelSelectionPolicy(
        task_type="decide",
        complexity="simple",
        preferred_profile="fast_structured",
        max_tokens=800,
        temperature=0.0,
        timeout_seconds=15.0,
        retry_limit=1,
    ),
}


@dataclass
class CallMetrics:
    call_id: str
    task_type: str
    model_profile: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_seconds: float = 0.0
    status: str = "succeeded"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class OrchestratorModelSelector:
    """Manages adaptive LLM routing, token budgeting, and cost tracking for orchestrator tasks."""

    def __init__(self) -> None:
        self.call_history: list[CallMetrics] = []

    def get_policy(self, task_type: str) -> ModelSelectionPolicy:
        """Returns the configured model selection policy for the specified task type."""
        return DEFAULT_POLICIES.get(
            task_type,
            ModelSelectionPolicy(
                task_type=task_type,
                complexity="moderate",
                preferred_profile="fast_structured",
                max_tokens=1000,
                temperature=0.2,
                timeout_seconds=20.0,
            ),
        )

    def execute_call(
        self,
        task_type: str,
        system_instruction: str,
        user_prompt: str,
        project_id: str = "orchestrator",
        output_schema: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> tuple[dict[str, Any] | None, CallMetrics]:
        """Dispatches an LLM call through the central llm_gateway with adaptive model routing.
        
        Returns:
            (parsed_json_dict | None, call_metrics)
        """
        policy = self.get_policy(task_type)
        start_time = time.time()
        call_id = f"orch_call_{int(start_time * 1000)}"

        req = llm_gateway.LlmGatewayRequest(
            project_id=project_id,
            stage_id="pipeline",
            agent_id="main_orchestrator",
            purpose="decision" if task_type in ("plan", "decide") else "repair",
            model_profile=policy.preferred_profile,
            system_prompt=system_instruction,
            user_prompt=user_prompt,
            structured_schema=output_schema,
            timeout=int(policy.timeout_seconds),
            correlation_id=correlation_id or call_id,
        )

        try:
            gw = llm_gateway.get_gateway()
            resp = gw.execute(req)
            latency = time.time() - start_time
            parsed_data = resp.structured_data
            if parsed_data is None and resp.raw_text:
                try:
                    import json
                    parsed_data = json.loads(resp.raw_text)
                except Exception:
                    pass

            usage = resp.token_usage or {}
            in_tokens = usage.get("input", usage.get("prompt_tokens", len(user_prompt) // 4))
            out_tokens = usage.get("output", usage.get("completion_tokens", len(resp.raw_text or "") // 4))
            tot_tokens = usage.get("total", in_tokens + out_tokens)

            pricing = getattr(llm_usage, "DEFAULT_MODEL_PRICING", {}).get(resp.model, {"input": 1.0, "output": 3.0})
            cost_usd = (in_tokens / 1_000_000 * pricing.get("input", 1.0)) + (
                out_tokens / 1_000_000 * pricing.get("output", 3.0)
            )

            metrics = CallMetrics(
                call_id=call_id,
                task_type=task_type,
                model_profile=policy.preferred_profile,
                provider=resp.provider or "gateway",
                prompt_tokens=in_tokens,
                completion_tokens=out_tokens,
                total_tokens=tot_tokens,
                cost_usd=round(cost_usd, 6),
                latency_seconds=round(latency, 3),
                status=resp.status,
            )
            self.call_history.append(metrics)
            return parsed_data, metrics

        except Exception as err:
            latency = time.time() - start_time
            logger.warning(f"Orchestrator LLM call failed for task '{task_type}': {err}. Yielding None.")
            metrics = CallMetrics(
                call_id=call_id,
                task_type=task_type,
                model_profile=policy.preferred_profile,
                provider="fallback",
                latency_seconds=round(latency, 3),
                status="failed",
            )
            self.call_history.append(metrics)
            return None, metrics

    def record_call_metrics(self, metrics: CallMetrics) -> None:
        """Records an external or simulated call metric for testing and spend telemetry."""
        self.call_history.append(metrics)

    def get_total_spend(self) -> dict[str, Any]:
        """Returns aggregated tokens, costs, and call counts for this orchestrator session."""
        total_tokens = sum(m.total_tokens for m in self.call_history)
        total_cost = sum(m.cost_usd for m in self.call_history)
        calls_count = len(self.call_history)
        return {
            "calls_count": calls_count,
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 6),
            "total_cost_inr": round(total_cost * 86.0, 4),
        }


model_selector = OrchestratorModelSelector()
