"""Production-Quality Development LLM Usage & Estimated Cost Monitor.

Tracks real LLM usage and estimated costs for this repository from:
1. Claude Code development sessions recorded in ~/.claude/metrics/costs.jsonl
2. Claude Code project transcripts in ~/.claude/projects/
3. Backend pipeline & LLM Gateway calls (Gemini, OpenAI, Anthropic, Claude CLI, Groq, DeepSeek, Ollama)

Key Invariants:
- High accuracy: calculates costs as Estimated API-Equivalent Cost using model-specific
  pricing and configurable USD-to-INR conversion.
- Distinguishes actual recorded metadata (from provider tokens) vs estimated tokens.
- Treats flat-rate Claude Code subscription usage separately from pay-per-token API expenditures.
- Fully persistent, deduplicated, idempotent, and resilient to missing files or corrupted lines.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("llm_usage")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
USAGE_STORAGE_FILE = CONFIG_DIR / "llm_usage.json"
CLAUDE_METRICS_PATH = Path(os.path.expanduser("~/.claude/metrics/costs.jsonl"))
CLAUDE_PROJECTS_DIR = Path(os.path.expanduser("~/.claude/projects"))

# Configurable default USD to INR exchange rate
DEFAULT_USD_TO_INR = 86.0

# Pricing in USD per 1,000,000 tokens (Standard published rates)
DEFAULT_MODEL_PRICING: dict[str, dict[str, float]] = {
    # Anthropic / Claude Code
    "claude-sonnet-5-5": {"input": 3.0, "output": 15.0, "cache_read": 0.30, "cache_write": 3.75},
    "claude-3-5-sonnet": {"input": 3.0, "output": 15.0, "cache_read": 0.30, "cache_write": 3.75},
    "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0, "cache_read": 0.30, "cache_write": 3.75},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.0, "cache_read": 0.08, "cache_write": 1.00},
    "claude-3-5-haiku": {"input": 0.80, "output": 4.0, "cache_read": 0.08, "cache_write": 1.00},
    "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.0, "cache_read": 0.08, "cache_write": 1.00},
    "claude-opus-5-5": {"input": 15.0, "output": 75.0, "cache_read": 1.50, "cache_write": 18.75},
    "claude-3-opus": {"input": 15.0, "output": 75.0, "cache_read": 1.50, "cache_write": 18.75},
    "claude-code": {"input": 3.0, "output": 15.0, "cache_read": 0.30, "cache_write": 3.75},

    # Google Gemini
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40, "cache_read": 0.025, "cache_write": 0.0},
    "gemini-2.0-flash-exp": {"input": 0.10, "output": 0.40, "cache_read": 0.025, "cache_write": 0.0},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30, "cache_read": 0.01875, "cache_write": 0.0},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.0, "cache_read": 0.3125, "cache_write": 0.0},

    # OpenAI
    "gpt-4o-mini": {"input": 0.15, "output": 0.60, "cache_read": 0.075, "cache_write": 0.0},
    "gpt-4o": {"input": 2.50, "output": 10.0, "cache_read": 1.25, "cache_write": 0.0},

    # DeepSeek
    "deepseek-chat": {"input": 0.14, "output": 0.28, "cache_read": 0.014, "cache_write": 0.0},

    # Groq
    "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79, "cache_read": 0.0, "cache_write": 0.0},

    # Ollama / Local
    "llama3.2": {"input": 0.0, "output": 0.0, "cache_read": 0.0, "cache_write": 0.0},
    "ollama": {"input": 0.0, "output": 0.0, "cache_read": 0.0, "cache_write": 0.0},
}

DEFAULT_FALLBACK_PRICING = {"input": 1.0, "output": 3.0, "cache_read": 0.1, "cache_write": 1.0}

SUBSCRIPTION_DISCLAIMER = (
    "Claude Code development usage represents estimated API-equivalent value for sessions "
    "worked in this repository under subscription (flat rate, not billed per token). "
    "Direct API calls reflect pay-per-token usage."
)

_lock = threading.Lock()


def get_model_pricing(model: str) -> dict[str, float]:
    """Retrieve pricing for a given model, with fuzzy prefix matching."""
    m_clean = (model or "").lower().strip()
    storage_pricing = load_storage().get("settings", {}).get("model_pricing_overrides", {})
    if m_clean in storage_pricing:
        return storage_pricing[m_clean]

    if m_clean in DEFAULT_MODEL_PRICING:
        return DEFAULT_MODEL_PRICING[m_clean]

    for key, pricing in DEFAULT_MODEL_PRICING.items():
        if key in m_clean or m_clean in key:
            return pricing

    return DEFAULT_FALLBACK_PRICING


def estimate_cost_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    """Calculate estimated cost in USD based on model pricing table."""
    pricing = get_model_pricing(model)
    cost = (
        (input_tokens * pricing["input"])
        + (output_tokens * pricing["output"])
        + (cache_read_tokens * pricing.get("cache_read", 0.0))
        + (cache_write_tokens * pricing.get("cache_write", 0.0))
    ) / 1_000_000.0
    return round(cost, 6)


def load_storage() -> dict[str, Any]:
    """Load persistent usage records and settings."""
    if USAGE_STORAGE_FILE.exists():
        try:
            data = json.loads(USAGE_STORAGE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {
        "settings": {
            "usd_to_inr": DEFAULT_USD_TO_INR,
            "model_pricing_overrides": {},
        },
        "backend_records": [],
        "last_synced_at": None,
    }


def save_storage(data: dict[str, Any]) -> None:
    """Persist usage records and settings safely with atomic write."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        tmp = USAGE_STORAGE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(USAGE_STORAGE_FILE)
    except Exception as e:
        logger.warning(f"Failed to persist llm_usage.json: {e}")


def is_repo_path(path_str: str) -> bool:
    """Check if transcript path belongs to this repository."""
    s = (path_str or "").lower().replace("/", "\\")
    targets = [
        "audio-to-video",
        "video_generation_agent",
        "video-generation-agent",
    ]
    return any(t in s for t in targets)


def read_claude_code_sessions(metrics_file: Path | None = None) -> list[dict[str, Any]]:
    """Parse ~/.claude/metrics/costs.jsonl, filtering for this repository and deduplicating by session."""
    p = metrics_file or CLAUDE_METRICS_PATH
    if not p.exists():
        return []

    # Map session_id -> list of snapshots
    sessions: dict[str, list[dict[str, Any]]] = {}
    try:
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    d = json.loads(line)
                    tp = d.get("transcript_path", "")
                    if is_repo_path(tp):
                        sid = d.get("session_id") or "unknown_session"
                        sessions.setdefault(sid, []).append(d)
                except Exception:
                    continue
    except Exception as e:
        logger.warning(f"Error reading Claude metrics file: {e}")
        return []

    results = []
    usd_to_inr = load_storage().get("settings", {}).get("usd_to_inr", DEFAULT_USD_TO_INR)

    for sid, snapshots in sessions.items():
        # Sort by timestamp to select the final cumulative snapshot for this session
        snapshots.sort(key=lambda x: str(x.get("timestamp", "")))
        latest = snapshots[-1]

        model = latest.get("model") or "claude-sonnet-5-5"
        inp = int(latest.get("input_tokens") or 0)
        out = int(latest.get("output_tokens") or 0)
        cr = int(latest.get("cache_read_tokens") or 0)
        cw = int(latest.get("cache_write_tokens") or 0)

        # Use recorded estimated_cost_usd or compute if missing
        cost_usd = float(latest.get("estimated_cost_usd") or 0.0)
        if cost_usd <= 0 and (inp > 0 or out > 0):
            cost_usd = estimate_cost_usd(model, inp, out, cr, cw)

        cost_inr = round(cost_usd * usd_to_inr, 2)
        has_actual_tokens = inp > 0 or out > 0

        results.append({
            "id": f"claude_code_{sid}",
            "session_id": sid,
            "timestamp": latest.get("timestamp", ""),
            "source": "claude_code",
            "provider": "anthropic",
            "provider_name": "Anthropic (Claude Code)",
            "model": model,
            "is_subscription": True,
            "tracking_mode": "actual_recorded" if has_actual_tokens else "estimated",
            "input_tokens": inp,
            "output_tokens": out,
            "cache_read_tokens": cr,
            "cache_write_tokens": cw,
            "total_tokens": inp + out,
            "cost_usd": round(cost_usd, 4),
            "cost_inr": cost_inr,
            "task": "Claude Code Interactive Development",
        })

    return results


def record_backend_usage(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    task: str = "",
    is_subscription: bool = False,
    prompt_snippet: str = "",
    tracking_mode: str = "actual_recorded",
) -> dict[str, Any] | None:
    """Record an LLM usage event from the backend with deterministic deduplication."""
    if input_tokens <= 0 and output_tokens <= 0:
        return None

    prov = (provider or "unknown").lower()
    mdl = model or "default"
    usd_to_inr = load_storage().get("settings", {}).get("usd_to_inr", DEFAULT_USD_TO_INR)
    cost_usd = estimate_cost_usd(mdl, input_tokens, output_tokens)
    cost_inr = round(cost_usd * usd_to_inr, 2)

    # Unique fingerprint to prevent duplicate recording of identical runs
    fingerprint = hashlib.sha256(
        f"{prov}:{mdl}:{task}:{input_tokens}:{output_tokens}:{prompt_snippet[:64]}".encode("utf-8")
    ).hexdigest()[:16]

    ts = datetime.now(timezone.utc).isoformat()
    record = {
        "id": f"be_{fingerprint}",
        "session_id": fingerprint,
        "timestamp": ts,
        "source": "backend_api",
        "provider": prov,
        "provider_name": _get_provider_display_name(prov),
        "model": mdl,
        "task": task or "Pipeline LLM Execution",
        "is_subscription": is_subscription or (prov == "claude_cli"),
        "tracking_mode": tracking_mode,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "total_tokens": input_tokens + output_tokens,
        "cost_usd": round(cost_usd, 6),
        "cost_inr": cost_inr,
    }

    with _lock:
        storage = load_storage()
        records = storage.setdefault("backend_records", [])

        # Deduplicate: if an event with the same ID occurred recently (or identical task run)
        existing_ids = {r.get("id") for r in records}
        if record["id"] in existing_ids:
            return None

        records.append(record)
        save_storage(storage)

    return record


def _get_provider_display_name(provider: str) -> str:
    names = {
        "gemini": "Google Gemini",
        "openai": "OpenAI",
        "anthropic": "Anthropic Claude (API)",
        "claude_cli": "Claude Code (CLI)",
        "groq": "Groq",
        "deepseek": "DeepSeek",
        "ollama": "Ollama (Local)",
        "custom": "Custom OpenAI-Compatible",
    }
    return names.get(provider.lower(), provider.title())


def get_all_records() -> list[dict[str, Any]]:
    """Retrieve all unified usage records sorted by timestamp descending."""
    claude_sessions = read_claude_code_sessions()
    backend_records = load_storage().get("backend_records", [])
    all_recs = claude_sessions + backend_records
    all_recs.sort(key=lambda x: str(x.get("timestamp", "")), reverse=True)
    return all_recs


def get_usage_summary(force_refresh: bool = False) -> dict[str, Any]:
    """Compile aggregated usage metrics, model breakdowns, data quality, and INR/USD totals."""
    with _lock:
        storage = load_storage()
        usd_to_inr = storage.get("settings", {}).get("usd_to_inr", DEFAULT_USD_TO_INR)

        # Parse Claude Code metrics
        claude_sessions = read_claude_code_sessions()
        backend_records = storage.get("backend_records", [])

        storage["last_synced_at"] = datetime.now(timezone.utc).isoformat()
        save_storage(storage)

    all_records = claude_sessions + backend_records
    # Sort descending by timestamp
    all_records.sort(key=lambda x: str(x.get("timestamp", "")), reverse=True)

    total_input = 0
    total_output = 0
    total_cache_read = 0
    total_cache_write = 0
    total_cost_usd = 0.0

    actual_tokens = 0
    estimated_tokens = 0

    by_provider: dict[str, dict[str, Any]] = {}
    by_model: dict[str, dict[str, Any]] = {}
    by_source: dict[str, dict[str, Any]] = {
        "claude_code": {
            "source": "claude_code",
            "label": "Claude Code (Subscription)",
            "is_subscription": True,
            "disclaimer": SUBSCRIPTION_DISCLAIMER,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0.0,
            "cost_inr": 0.0,
            "sessions_count": len(claude_sessions),
        },
        "backend_api": {
            "source": "backend_api",
            "label": "Backend Pipeline & Agent API",
            "is_subscription": False,
            "disclaimer": "Direct API calls executed by the pipeline and LLM agents.",
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0.0,
            "cost_inr": 0.0,
            "calls_count": len(backend_records),
        },
    }

    for r in all_records:
        inp = int(r.get("input_tokens") or 0)
        out = int(r.get("output_tokens") or 0)
        cr = int(r.get("cache_read_tokens") or 0)
        cw = int(r.get("cache_write_tokens") or 0)
        c_usd = float(r.get("cost_usd") or 0.0)
        src = r.get("source", "backend_api")
        prov = r.get("provider", "unknown")
        prov_name = r.get("provider_name") or _get_provider_display_name(prov)
        mdl = r.get("model", "unknown")
        is_sub = bool(r.get("is_subscription", False))
        t_mode = r.get("tracking_mode", "actual_recorded")

        toks = inp + out
        total_input += inp
        total_output += out
        total_cache_read += cr
        total_cache_write += cw
        total_cost_usd += c_usd

        if t_mode == "actual_recorded":
            actual_tokens += toks
        else:
            estimated_tokens += toks

        # By Source
        if src in by_source:
            by_source[src]["input_tokens"] += inp
            by_source[src]["output_tokens"] += out
            by_source[src]["total_tokens"] += toks
            by_source[src]["cost_usd"] += c_usd

        # By Provider
        if prov not in by_provider:
            by_provider[prov] = {
                "provider": prov,
                "provider_name": prov_name,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cost_usd": 0.0,
                "cost_inr": 0.0,
                "is_subscription": is_sub,
                "count": 0,
            }
        by_provider[prov]["input_tokens"] += inp
        by_provider[prov]["output_tokens"] += out
        by_provider[prov]["total_tokens"] += toks
        by_provider[prov]["cost_usd"] += c_usd
        by_provider[prov]["count"] += 1

        # By Model
        if mdl not in by_model:
            by_model[mdl] = {
                "model": mdl,
                "provider": prov,
                "provider_name": prov_name,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cost_usd": 0.0,
                "cost_inr": 0.0,
                "is_subscription": is_sub,
                "count": 0,
            }
        by_model[mdl]["input_tokens"] += inp
        by_model[mdl]["output_tokens"] += out
        by_model[mdl]["total_tokens"] += toks
        by_model[mdl]["cost_usd"] += c_usd
        by_model[mdl]["count"] += 1

    # Round currency values and compute INR
    for src_data in by_source.values():
        src_data["cost_usd"] = round(src_data["cost_usd"], 2)
        src_data["cost_inr"] = round(src_data["cost_usd"] * usd_to_inr, 2)

    for prov_data in by_provider.values():
        prov_data["cost_usd"] = round(prov_data["cost_usd"], 2)
        prov_data["cost_inr"] = round(prov_data["cost_usd"] * usd_to_inr, 2)

    for mdl_data in by_model.values():
        mdl_data["cost_usd"] = round(mdl_data["cost_usd"], 2)
        mdl_data["cost_inr"] = round(mdl_data["cost_usd"] * usd_to_inr, 2)

    total_cost_usd_rounded = round(total_cost_usd, 2)
    total_cost_inr = round(total_cost_usd_rounded * usd_to_inr, 2)
    total_tokens = total_input + total_output

    return {
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_cache_read_tokens": total_cache_read,
        "total_cache_write_tokens": total_cache_write,
        "total_tokens": total_tokens,
        "total_cost_usd": total_cost_usd_rounded,
        "total_cost_inr": total_cost_inr,
        "usd_to_inr_rate": usd_to_inr,
        "last_updated_at": datetime.now(timezone.utc).isoformat(),
        "records_count": len(all_records),
        "data_quality": {
            "actual_recorded_tokens": actual_tokens,
            "estimated_tokens": estimated_tokens,
            "actual_percentage": round((actual_tokens / max(1, total_tokens)) * 100, 1),
            "sources": [
                {
                    "source": "claude_code",
                    "name": "Claude Code Metrics",
                    "path": "~/.claude/metrics/costs.jsonl",
                    "available": CLAUDE_METRICS_PATH.exists(),
                    "sessions_count": len(claude_sessions),
                },
                {
                    "source": "gemini",
                    "name": "Google Gemini API",
                    "metadata_field": "usageMetadata",
                    "available": True,
                },
                {
                    "source": "openai",
                    "name": "OpenAI API",
                    "metadata_field": "usage",
                    "available": True,
                },
                {
                    "source": "anthropic",
                    "name": "Anthropic Claude API",
                    "metadata_field": "usage",
                    "available": True,
                },
            ],
        },
        "by_provider": by_provider,
        "by_model": by_model,
        "by_source": by_source,
        "subscription_disclaimer": SUBSCRIPTION_DISCLAIMER,
        "pricing_reference": {
            k: {
                "input_per_m": v["input"],
                "output_per_m": v["output"],
                "cache_read_per_m": v.get("cache_read", 0.0),
                "cache_write_per_m": v.get("cache_write", 0.0),
            }
            for k, v in DEFAULT_MODEL_PRICING.items()
        },
        "recent_sessions": all_records[:10],
    }


def get_usage_history(
    limit: int = 50,
    offset: int = 0,
    source: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    """Retrieve paginated and filtered historical LLM usage events."""
    records = get_all_records()

    if source:
        s_lower = source.lower()
        records = [r for r in records if r.get("source", "").lower() == s_lower]

    if provider:
        p_lower = provider.lower()
        records = [r for r in records if r.get("provider", "").lower() == p_lower]

    if model:
        m_lower = model.lower()
        records = [r for r in records if m_lower in r.get("model", "").lower()]

    if search:
        q = search.lower()
        records = [
            r for r in records
            if q in r.get("session_id", "").lower()
            or q in r.get("model", "").lower()
            or q in r.get("task", "").lower()
            or q in r.get("provider_name", "").lower()
        ]

    total_count = len(records)
    paged = records[offset : offset + limit]

    return {
        "items": paged,
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
    }


def update_usage_settings(
    usd_to_inr: float | None = None,
    model_pricing_overrides: dict[str, dict[str, float]] | None = None,
) -> dict[str, Any]:
    """Update user-configurable exchange rate or pricing overrides."""
    with _lock:
        storage = load_storage()
        settings = storage.setdefault("settings", {})

        if usd_to_inr is not None and usd_to_inr > 0:
            settings["usd_to_inr"] = round(float(usd_to_inr), 2)

        if model_pricing_overrides is not None:
            overrides = settings.setdefault("model_pricing_overrides", {})
            for m_key, rates in model_pricing_overrides.items():
                if isinstance(rates, dict):
                    overrides[m_key.lower().strip()] = {
                        "input": float(rates.get("input", 1.0)),
                        "output": float(rates.get("output", 3.0)),
                    }

        save_storage(storage)

    return get_usage_summary(force_refresh=True)
