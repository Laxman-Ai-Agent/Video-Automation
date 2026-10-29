"""Canonical LLM Gateway & Model Routing Service.

Consolidates all LLM calls across the multi-agent pipeline into a single,
resilient, auditable entry point with:
1. Typed request/response envelopes with correlation and execution tracking.
2. Logical model routing (fast_structured, reasoning_review, code_generation).
3. Bounded retry policy with exponential backoff on transient errors.
4. Bounded JSON repair retry on malformed model responses.
5. Fail-closed error handling and secret-safe telemetry logging.
6. Automatic integration with llm_usage tracking and project communication audit log.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

from SYSTEM.core import llm_client
from SYSTEM.observability import llm_usage
from SYSTEM.core.resilience import circuit_breaker, sanitize_secrets, calculate_backoff

logger = logging.getLogger("llm_gateway")

# In-flight active LLM requests tracking
_ACTIVE_REQUESTS: dict[str, dict[str, Any]] = {}
_ACTIVE_LOCK = threading.Lock()


def get_active_requests(project_id: str | None = None) -> list[dict[str, Any]]:
    """Returns currently running LLM requests, optionally filtered by project_id."""
    with _ACTIVE_LOCK:
        reqs = list(_ACTIVE_REQUESTS.values())
    if project_id:
        return [r for r in reqs if r.get("project_id") == project_id]
    return reqs


def is_request_active(project_id: str | None = None) -> bool:
    """Returns True if an LLM request is currently in-flight."""
    return len(get_active_requests(project_id)) > 0


LlmPurpose = Literal["decision", "generation", "review", "repair"]
ModelProfile = Literal["fast_structured", "reasoning_review", "code_generation", "default"]
GatewayStatus = Literal["passed", "blocked", "failed", "needs_review"]

# How long an answer of each profile may take. ONE definition: a request that does not set its own timeout gets its profile's
# (a 60 s cut-off was applied to every call, so generating a scene's TSX - a few hundred lines - always timed out and, after three
# scenes, opened the provider's circuit breaker).
PROFILE_TIMEOUT: dict[str, int] = {"fast_structured": 60, "reasoning_review": 300, "code_generation": 600, "default": 120}


def profile_timeout(profile: str | None, given: int | None = None) -> int:
    """The timeout for this request: what the caller asked for, else the profile's own."""
    return int(given) if given else PROFILE_TIMEOUT.get(profile or "default", PROFILE_TIMEOUT["default"])


# Profile to model preference mapping per provider
PROFILE_ROUTING: dict[str, dict[ModelProfile, str]] = {
    "gemini": {
        "fast_structured": "gemini-3.1-flash-lite",
        "reasoning_review": "gemini-3.5-flash",
        "code_generation": "gemini-3.5-flash",
        "default": "gemini-3.5-flash",
    },
    "anthropic": {
        "fast_structured": "claude-3-5-haiku-20241022",
        "reasoning_review": "claude-3-5-sonnet-20241022",
        "code_generation": "claude-3-5-sonnet-20241022",
        "default": "claude-3-5-sonnet-20241022",
    },
    "openai": {
        "fast_structured": "gpt-4o-mini",
        "reasoning_review": "gpt-4o",
        "code_generation": "gpt-4o-mini",
        "default": "gpt-4o-mini",
    },
    "claude_cli": {
        "fast_structured": "claude-code",
        "reasoning_review": "claude-code",
        "code_generation": "claude-code",
        "default": "claude-code",
    },
    "groq": {
        "fast_structured": "qwen/qwen3.8-27b",
        "reasoning_review": "openai/gpt-oss-120b",
        "code_generation": "openai/gpt-oss-120b",
        "default": "openai/gpt-oss-120b",
    },
    "deepseek": {
        "fast_structured": "deepseek-chat",
        "reasoning_review": "deepseek-chat",
        "code_generation": "deepseek-chat",
        "default": "deepseek-chat",
    },
    "ollama": {
        "fast_structured": "llama3.2",
        "reasoning_review": "llama3.2",
        "code_generation": "llama3.2",
        "default": "llama3.2",
    },
    "custom": {
        "fast_structured": "default",
        "reasoning_review": "default",
        "code_generation": "default",
        "default": "default",
    },
}


@dataclass
class LlmGatewayRequest:
    """Standardized request envelope for LLM invocations."""
    project_id: str
    stage_id: str
    agent_id: str
    purpose: LlmPurpose
    user_prompt: str
    system_prompt: str = ""
    model_profile: ModelProfile = "default"
    structured_schema: dict[str, Any] | None = None
    timeout: int = 0                                     # 0 = the timeout of the model profile (PROFILE_TIMEOUT); a caller may set its own
    max_retries: int = 2
    correlation_id: str = field(default_factory=lambda: f"corr_{uuid.uuid4().hex[:12]}")
    request_id: str = field(default_factory=lambda: f"req_{uuid.uuid4().hex[:12]}")
    input_artifact_refs: list[dict[str, str]] = field(default_factory=list)
    input_fingerprint: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    images: list[str] = field(default_factory=list)      # files (paths) the model must look at; only a provider that can see pictures accepts them (llm_client.generate_text)


@dataclass
class LlmGatewayResponse:
    """Standardized response envelope returned by the gateway."""
    request_id: str
    correlation_id: str
    project_id: str
    stage_id: str
    agent_id: str
    purpose: str
    status: GatewayStatus
    raw_text: str
    structured_data: dict[str, Any] | None
    model_profile: str
    provider: str
    model: str
    latency_ms: int
    attempt_count: int
    error: str | None = None
    input_fingerprint: str = ""
    output_fingerprint: str = ""
    token_usage: dict[str, int] = field(default_factory=lambda: {"input": 0, "output": 0, "total": 0})
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LlmGatewayError(RuntimeError):
    """Raised when an unrecoverable LLM Gateway failure occurs."""


class LlmGateway:
    """Canonical LLM Gateway managing invocation, model routing, retries, and structured reviews."""

    def __init__(self, client_module: Any = None) -> None:
        self._client_module = client_module

    @property
    def client(self) -> Any:
        return self._client_module if self._client_module is not None else llm_client

    @client.setter
    def client(self, val: Any) -> None:
        self._client_module = val

    def resolve_model_for_profile(self, provider: str, profile: ModelProfile, configured_model: str = "") -> str:
        """Resolves target model based on logical profile and active provider configuration.
        
        When Model Lock is active and a model is explicitly configured, that exact model
        is strictly enforced across all profiles. Silent substitution to other models is disabled.
        """
        prov_key = (provider or "auto").lower()
        if configured_model:
            return configured_model

        routing_table = PROFILE_ROUTING.get(prov_key, {})
        target_model = routing_table.get(profile) or routing_table.get("default")
        if target_model:
            return target_model

        return self.client.DEFAULT_MODELS.get(prov_key, "default")

    def execute(self, req: LlmGatewayRequest) -> LlmGatewayResponse:
        """Executes an LLM request with bounded retries, error normalization, and structured parsing."""
        t0 = time.perf_counter()
        prov, configured_mdl, key, base_url = self.client.resolve_provider_config()
        effective_mdl = self.resolve_model_for_profile(prov, req.model_profile, configured_mdl)

        # Check circuit breaker before dispatch
        can_exec, cb_status = circuit_breaker.can_execute(prov, effective_mdl)
        if not can_exec:
            latency = round((time.perf_counter() - t0) * 1000)
            logger.warning(f"[{req.correlation_id}] Request blocked by circuit breaker: {cb_status}")
            resp = LlmGatewayResponse(
                request_id=req.request_id,
                correlation_id=req.correlation_id,
                project_id=req.project_id,
                stage_id=req.stage_id,
                agent_id=req.agent_id,
                purpose=req.purpose,
                status="blocked",
                raw_text="",
                structured_data=None,
                model_profile=req.model_profile,
                provider=prov,
                model=effective_mdl,
                latency_ms=latency,
                attempt_count=0,
                error=sanitize_secrets(cb_status),
                input_fingerprint=req.input_fingerprint,
            )
            self._record_telemetry(req, resp)
            return resp

        active_entry = {
            "request_id": req.request_id,
            "project_id": req.project_id,
            "stage_id": req.stage_id,
            "agent_id": req.agent_id,
            "provider": prov,
            "model": effective_mdl,
            "purpose": req.purpose,
            "started_at": time.time(),
            "status": "running",
        }
        with _ACTIVE_LOCK:
            _ACTIVE_REQUESTS[req.request_id] = active_entry

        try:
            last_error: str | None = None
            attempt = 0
            raw_text = ""
            structured_data: dict[str, Any] | None = None
            current_user_prompt = req.user_prompt
            current_system_prompt = req.system_prompt

            while attempt <= req.max_retries:
                attempt += 1
                try:
                    raw_text = self.client.generate_text(
                        user=current_user_prompt,
                        system=current_system_prompt,
                        timeout=profile_timeout(req.model_profile, req.timeout),
                        provider=prov,
                        model=effective_mdl,
                        **({"images": req.images} if req.images else {}),
                    )

                    # If structured schema is expected, parse JSON
                    if req.structured_schema is not None:
                        structured_data = self._parse_json_response(raw_text)
                        if structured_data is None:
                            # Bounded JSON repair attempt
                            if attempt <= req.max_retries:
                                logger.warning(
                                    f"[{req.correlation_id}] Failed to parse structured JSON on attempt {attempt}. Retrying with repair prompt..."
                                )
                                current_user_prompt = (
                                    f"{req.user_prompt}\n\n"
                                    f"IMPORTANT: Your previous response was not valid JSON:\n"
                                    f"```\n{raw_text[:500]}\n```\n"
                                    f"You must return ONLY a strictly valid JSON object matching this schema with no markdown formatting:\n"
                                    f"{json.dumps(req.structured_schema)}"
                                )
                                time.sleep(0.5 * attempt)
                                continue
                            else:
                                raise ValueError(f"Model returned invalid JSON after {attempt} attempts: {raw_text[:200]}")

                    # Success - record in circuit breaker
                    circuit_breaker.record_success(prov, effective_mdl)
                    latency = round((time.perf_counter() - t0) * 1000)
                    status: GatewayStatus = "passed"
                    if structured_data and isinstance(structured_data, dict):
                        raw_status = structured_data.get("status")
                        if raw_status in ("passed", "needs_review", "blocked", "failed"):
                            status = raw_status

                    est_in_tokens = max(1, int(len(current_user_prompt + current_system_prompt) / 4))
                    est_out_tokens = max(1, int(len(raw_text) / 4)) if raw_text else 0
                    tokens = {
                        "input": est_in_tokens,
                        "output": est_out_tokens,
                        "total": est_in_tokens + est_out_tokens,
                    }
                    try:
                        llm_usage.record_backend_usage(
                            provider=prov,
                            model=effective_mdl,
                            input_tokens=est_in_tokens,
                            output_tokens=est_out_tokens,
                            task=f"{req.stage_id}:{req.purpose}",
                            is_subscription=(prov == "claude_cli"),
                            prompt_snippet=req.user_prompt[:64],
                        )
                    except Exception:
                        pass

                    resp = LlmGatewayResponse(
                        request_id=req.request_id,
                        correlation_id=req.correlation_id,
                        project_id=req.project_id,
                        stage_id=req.stage_id,
                        agent_id=req.agent_id,
                        purpose=req.purpose,
                        status=status,
                        raw_text=raw_text,
                        structured_data=structured_data,
                        model_profile=req.model_profile,
                        provider=prov,
                        model=effective_mdl,
                        latency_ms=latency,
                        attempt_count=attempt,
                        error=None,
                        input_fingerprint=req.input_fingerprint,
                        token_usage=tokens,
                    )
                    self._record_telemetry(req, resp)
                    return resp

                except Exception as e:
                    last_error = sanitize_secrets(str(e))
                    is_rate_limit = any(k in last_error.lower() for k in ("429", "rate limit", "too many requests", "tpm", "rpm"))
                    is_quota = any(k in last_error.lower() for k in ("exceeded your current quota", "tokens per day", "tpd", "quota exceeded", "insufficient_quota", "credit balance"))
                    if not is_rate_limit and not is_quota:
                        circuit_breaker.record_failure(prov, effective_mdl, error=last_error)
                    
                    # Fail fast on non-retryable authentication, missing credentials, or quota exhaustion
                    if any(k in last_error.lower() for k in ("missing", "invalid api key", "unauthorized", "401", "403", "forbidden")) or is_quota:
                        logger.error(f"[{req.correlation_id}] Non-retryable LLM error (or quota exhaustion): {last_error}")
                        break

                    if attempt <= req.max_retries:
                        # If error contains explicit retry-after seconds or milliseconds (e.g. "try again in 21.9s" or "try again in 82.5ms")
                        m_wait_ms = re.search(r"try again in (\d+(?:\.\d+)?)ms", last_error)
                        m_wait_s = re.search(r"try again in (\d+(?:\.\d+)?)s", last_error)
                        is_network_error = any(k in last_error.lower() for k in ("getaddrinfo", "connection", "connect", "timeout", "timed out"))
                        if m_wait_ms:
                            wait_s = min(float(m_wait_ms.group(1)) / 1000.0 + 0.5, 30.0)
                            backoff = wait_s
                        elif m_wait_s:
                            wait_s = min(float(m_wait_s.group(1)) + 1.0, 30.0)
                            backoff = wait_s
                        elif is_rate_limit:
                            backoff = min(12.0 * attempt, 35.0)
                        elif is_network_error:
                            backoff = min(3.0 * attempt, 15.0)
                        else:
                            backoff = calculate_backoff(attempt, base_seconds=1.0, max_seconds=5.0, jitter=True)
                        logger.warning(f"[{req.correlation_id}] Transient LLM error (attempt {attempt}): {last_error}. Retrying in {backoff:.2f}s...")
                        time.sleep(backoff)
                    else:
                        logger.error(f"[{req.correlation_id}] LLM call failed after {attempt} attempts: {last_error}")

            # Failed / Blocked closed response
            latency = round((time.perf_counter() - t0) * 1000)
            resp = LlmGatewayResponse(
                request_id=req.request_id,
                correlation_id=req.correlation_id,
                project_id=req.project_id,
                stage_id=req.stage_id,
                agent_id=req.agent_id,
                purpose=req.purpose,
                status="blocked",
                raw_text=raw_text,
                structured_data=None,
                model_profile=req.model_profile,
                provider=prov,
                model=effective_mdl,
                latency_ms=latency,
                attempt_count=attempt,
                error=sanitize_secrets(last_error) if last_error else None,
                input_fingerprint=req.input_fingerprint,
            )
            self._record_telemetry(req, resp)
            return resp
        finally:
            with _ACTIVE_LOCK:
                _ACTIVE_REQUESTS.pop(req.request_id, None)

    def _parse_json_response(self, text: str) -> dict[str, Any] | None:
        """Extracts and parses JSON object from model response text."""
        cleaned = text.strip()
        # Remove markdown code fences
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", cleaned)
            cleaned = re.sub(r"\n```$", "", cleaned).strip()

        # Find first balanced JSON object
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if m:
            cleaned = m.group(0)

        try:
            val = json.loads(cleaned)
            return val if isinstance(val, dict) else None
        except Exception:
            return None

    def _record_telemetry(self, req: LlmGatewayRequest, resp: LlmGatewayResponse) -> None:
        """Publishes audit log event to project communications without exposing sensitive data."""
        if not req.project_id:
            return

        try:
            from SYSTEM.agents.shared import communication
            from SYSTEM.agents.shared.contracts import ArtifactRef

            event_type = "tool_result" if req.purpose != "review" else "review_feedback"
            msg = (
                f"LLM Gateway [{req.purpose}] executed for stage '{req.stage_id}' by agent '{req.agent_id}'. "
                f"Status: {resp.status}, Model: {resp.provider}/{resp.model} ({resp.model_profile}), Latency: {resp.latency_ms}ms"
            )
            if resp.error:
                msg += f", Error: {resp.error}"

            communication.publish_message(
                project_id=req.project_id,
                stage_id=req.stage_id,
                sender_agent_id=req.agent_id or "main_orchestrator",
                message_type=event_type,
                content=msg,
                correlation_id=req.correlation_id,
                artifact_refs=[
                    ArtifactRef(path=r.get("path", ""), description=r.get("description", ""))
                    for r in req.input_artifact_refs
                ],
                metadata={
                    "request_id": req.request_id,
                    "purpose": req.purpose,
                    "model_profile": req.model_profile,
                    "provider": resp.provider,
                    "model": resp.model,
                    "latency_ms": resp.latency_ms,
                    "attempt_count": resp.attempt_count,
                    "status": resp.status,
                    "error": resp.error,
                    "token_usage": resp.token_usage,
                },
            )
        except Exception as e:
            logger.debug(f"Telemetry logging failed: {e}")


_gateway_instance: LlmGateway | None = None


def get_gateway() -> LlmGateway:
    """Returns the singleton LLM Gateway instance."""
    global _gateway_instance
    if _gateway_instance is None:
        _gateway_instance = LlmGateway()
    return _gateway_instance


gateway: LlmGateway = get_gateway()


@dataclass
class GatewayRequest:
    prompt: str = ""
    system_prompt: str | None = None
    stage_id: str = "general"
    purpose: str = "generation"
    model_profile: str = "fast_structured"
    correlation_id: str | None = None
    caller_agent_id: str = "agent"
    metadata: dict[str, Any] = field(default_factory=dict)
    timeout: int = 0                                     # 0 = the timeout of the model profile (PROFILE_TIMEOUT), like LlmGatewayRequest
    max_retries: int = 4
    user_prompt: str = ""
    project_id: str = ""
    agent_id: str = ""


@dataclass
class GatewayResponse:
    status: str = "passed"
    raw_output: str = ""
    raw_text: str = ""
    provider: str = "anthropic"
    model: str = "claude-3-5-haiku-20241022"
    profile: str = "fast_structured"
    purpose: str = "generation"
    stage_id: str = "general"
    error_message: str | None = None
    error: str | None = None
    structured_data: dict[str, Any] | None = None
    token_usage: dict[str, int] = field(default_factory=dict)


def execute_llm_gateway_call(req: Any) -> GatewayResponse:
    """Executes an LLM call through the canonical LLM Gateway singleton."""
    gw = get_gateway()
    if isinstance(req, LlmGatewayRequest):
        res = gw.execute(req)
        return GatewayResponse(
            status=res.status,
            raw_output=res.raw_text,
            raw_text=res.raw_text,
            provider=res.provider,
            model=res.model,
            profile=res.model_profile,
            purpose=res.purpose,
            stage_id=res.stage_id,
            error_message=res.error,
            error=res.error,
            structured_data=res.structured_data,
            token_usage=res.token_usage,
        )

    user_prompt = getattr(req, "prompt", "") or getattr(req, "user_prompt", "")
    sys_prompt = getattr(req, "system_prompt", "") or ""
    stage_id = getattr(req, "stage_id", "general")
    agent_id = getattr(req, "caller_agent_id", "") or getattr(req, "agent_id", "agent")
    purpose = getattr(req, "purpose", "generation")
    model_profile = getattr(req, "model_profile", "fast_structured")
    meta = getattr(req, "metadata", {}) or {}
    proj_id = meta.get("project_id", "") or getattr(req, "project_id", "")

    legacy_req = LlmGatewayRequest(
        project_id=proj_id,
        stage_id=stage_id,
        agent_id=agent_id,
        purpose=purpose,
        user_prompt=user_prompt,
        system_prompt=sys_prompt,
        model_profile=model_profile,
        correlation_id=getattr(req, "correlation_id", None) or f"corr_{uuid.uuid4().hex[:12]}",
        metadata=meta,
        timeout=getattr(req, "timeout", None) or 0,                   # the caller's timeout is kept; 0 lets the model profile decide (PROFILE_TIMEOUT)
    )
    res = gw.execute(legacy_req)
    return GatewayResponse(
        status=res.status,
        raw_output=res.raw_text,
        raw_text=res.raw_text,
        provider=res.provider,
        model=res.model,
        profile=res.model_profile,
        purpose=res.purpose,
        stage_id=res.stage_id,
        error_message=res.error,
        error=res.error,
        structured_data=res.structured_data,
        token_usage=res.token_usage,
    )


def __getattr__(name: str):
    if name == "gateway":
        return get_gateway()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

