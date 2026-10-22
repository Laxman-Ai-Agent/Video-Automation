"""API routes for LLM configuration, provider selection, and live connection testing."""
from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import llm_client

router = APIRouter(prefix="/llm", tags=["llm"])


class LlmSettingsUpdate(BaseModel):
    provider: str | None = None
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None


class LlmTestRequest(BaseModel):
    provider: str | None = None
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None


@router.get("/active")
def get_active_llm_requests(project_id: str | None = None) -> list[dict[str, Any]]:
    """Retrieve currently executing LLM requests with safe telemetry."""
    try:
        from SYSTEM.core.llm_gateway import get_active_requests
        return get_active_requests(project_id=project_id)
    except Exception:
        return []


@router.get("/settings")
def get_settings() -> dict[str, Any]:
    """Retrieve current public LLM configuration and available providers."""
    return llm_client.get_public_settings()


@router.post("/settings")
def update_settings(body: LlmSettingsUpdate) -> dict[str, Any]:
    """Update active LLM provider, model, API key, and custom endpoint."""
    if body.provider is not None and body.provider != "auto" and body.provider not in llm_client.PROVIDER_NAMES:
        raise HTTPException(status_code=422, detail=f"Unknown provider '{body.provider}'. Choose auto or one of: {', '.join(llm_client.PROVIDER_NAMES)}.")
    updates = {}
    if body.provider is not None:
        updates["provider"] = body.provider
    if body.model is not None:
        updates["model"] = body.model
    if body.api_key is not None:
        updates["api_key"] = body.api_key
    if body.base_url is not None:
        updates["base_url"] = body.base_url

    llm_client.save_settings(updates)
    _mark_health_stale()
    return llm_client.get_public_settings()


@router.get("/detect")
def detect_llm_options() -> dict[str, Any]:
    """What this computer can connect to (API keys found in the environment, Claude Code, Ollama). Never returns a key."""
    return {"options": llm_client.detect_options()}


@router.post("/auto-connect")
def auto_connect_llm() -> dict[str, Any]:
    """Try each detected option in order and keep the first one that answers."""
    result = llm_client.auto_connect()
    if result["connected"]:
        _record_health({"ok": True, **{k: result[k] for k in ("provider", "provider_name", "model", "latency_ms", "message")}})
    return result


import threading
import time

_LLM_HEALTH_LOCK = threading.Lock()
_CURRENT_LLM_HEALTH: dict[str, Any] = {
    "ok": False,
    "provider": None,
    "model": None,
    "latency_ms": 0,
    "message": "Probing LLM connectivity...",
    "checked_at": 0.0,
    "in_progress": False
}


def _record_health(res: dict[str, Any], latency_ms: int | None = None) -> None:
    """What the header shows: the outcome of the latest check of the active connection."""
    global _CURRENT_LLM_HEALTH
    with _LLM_HEALTH_LOCK:
        _CURRENT_LLM_HEALTH = {
            "ok": bool(res.get("ok")),
            "provider": res.get("provider"),
            "provider_name": res.get("provider_name"),
            "model": res.get("model"),
            "latency_ms": res.get("latency_ms") or latency_ms or 0,
            "message": res.get("message", ""),
            "checked_at": time.time(),
            "in_progress": False
        }


def _mark_health_stale() -> None:
    """The settings changed: the next /llm/health call probes again instead of waiting out the 15 s cache."""
    with _LLM_HEALTH_LOCK:
        _CURRENT_LLM_HEALTH["checked_at"] = 0.0


def trigger_llm_health_probe() -> None:
    """Executes live probe in worker thread to prevent event-loop stalls."""
    global _CURRENT_LLM_HEALTH
    with _LLM_HEALTH_LOCK:
        if _CURRENT_LLM_HEALTH.get("in_progress"):
            return
        _CURRENT_LLM_HEALTH["in_progress"] = True

    try:
        t0 = time.time()
        res = llm_client.test_connection()
        _record_health(res, round((time.time() - t0) * 1000))
    except Exception as e:
        with _LLM_HEALTH_LOCK:
            _CURRENT_LLM_HEALTH = {
                "ok": False,
                "provider": None,
                "model": None,
                "latency_ms": 0,
                "message": str(e),
                "checked_at": time.time(),
                "in_progress": False
            }


@router.post("/test")
def test_connection(body: LlmTestRequest) -> dict[str, Any]:
    """Test connection with the specified or active LLM."""
    res = llm_client.test_connection(
        provider=body.provider,
        model=body.model,
        api_key=body.api_key,
        base_url=body.base_url,
    )
    if body.provider is None and body.model is None and body.api_key is None and body.base_url is None:
        _record_health(res)     # a re-check of the active connection is what the header pill shows
    return res


@router.get("/health")
def get_llm_health(force: bool = False) -> dict[str, Any]:
    """Live connectivity probe for the active configured LLM."""
    now = time.time()
    # Trigger background probe if stale (> 15 seconds) or initial
    if force or (now - _CURRENT_LLM_HEALTH["checked_at"] > 15.0):
        if not _CURRENT_LLM_HEALTH.get("in_progress"):
            threading.Thread(target=trigger_llm_health_probe, daemon=True).start()

    with _LLM_HEALTH_LOCK:
        return dict(_CURRENT_LLM_HEALTH)


@router.get("/usage")
def get_usage(refresh: bool = False) -> dict[str, Any]:
    """Retrieve development LLM usage summary and estimated API-equivalent costs."""
    from SYSTEM.observability import llm_usage
    return llm_usage.get_usage_summary(force_refresh=refresh)


@router.post("/usage/refresh")
def refresh_usage() -> dict[str, Any]:
    """Force re-synchronization of Claude Code and development metrics."""
    from SYSTEM.observability import llm_usage
    return llm_usage.get_usage_summary(force_refresh=True)


class LlmUsageSettingsUpdate(BaseModel):
    usd_to_inr: float | None = None
    model_pricing_overrides: dict[str, dict[str, float]] | None = None


@router.get("/usage/history")
def get_usage_history(
    limit: int = 50,
    offset: int = 0,
    source: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    """Retrieve paginated and filtered historical LLM usage events."""
    from SYSTEM.observability import llm_usage
    return llm_usage.get_usage_history(
        limit=limit,
        offset=offset,
        source=source,
        provider=provider,
        model=model,
        search=search,
    )


@router.post("/usage/settings")
def update_usage_settings(body: LlmUsageSettingsUpdate) -> dict[str, Any]:
    """Update user-configurable exchange rate or model pricing overrides."""
    from SYSTEM.observability import llm_usage
    return llm_usage.update_usage_settings(
        usd_to_inr=body.usd_to_inr,
        model_pricing_overrides=body.model_pricing_overrides,
    )


