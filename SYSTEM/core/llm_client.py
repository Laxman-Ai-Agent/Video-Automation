"""Unified LLM client supporting multiple providers:
Google Gemini, OpenAI, Anthropic (API & CLI), Groq, DeepSeek, Ollama, and OpenAI-compatible endpoints.
Configuration is stored in config/llm_settings.json and can be managed via API/UI or environment variables.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"
CONFIG_FILE = CONFIG_DIR / "llm_settings.json"
STATUS_FILE = CONFIG_DIR / "llm_status.json"


def load_status() -> dict[str, Any] | None:
    """Load cached connection status if available."""
    if STATUS_FILE.exists():
        try:
            data = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return None


def save_status(status_data: dict[str, Any]) -> None:
    """Persist verified connection status so live status is zero-cost on polling."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        STATUS_FILE.write_text(json.dumps(status_data, indent=2), encoding="utf-8")
    except Exception:
        pass


DEFAULT_MODELS: dict[str, str] = {
    "gemini": "gemini-3.5-flash",       # gemini-2.0-flash and 1.5 were retired by Google (404 "no longer available"); check https://ai.google.dev/gemini-api/docs/models when this one is retired too
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-sonnet-20241022",
    "groq": "llama-3.3-70b-versatile",
    "deepseek": "deepseek-chat",
    "ollama": "llama3.2",
    "claude_cli": "claude-code",
    "custom": "default",
}

DEFAULT_BASE_URLS: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "deepseek": "https://api.deepseek.com",
    "ollama": "http://localhost:11434/v1",
}

PROVIDER_NAMES: dict[str, str] = {
    "gemini": "Google Gemini",
    "openai": "OpenAI (ChatGPT)",
    "anthropic": "Anthropic Claude (API)",
    "claude_cli": "Claude Code (Local CLI)",
    "groq": "Groq (High-Speed LLM)",
    "deepseek": "DeepSeek",
    "ollama": "Ollama (Local LLM)",
    "custom": "Custom OpenAI-Compatible",
}

# Providers that sign in with an API key, in the order `auto` tries them, and the environment variables that can hold that key.
ENV_KEYS: dict[str, tuple[str, ...]] = {
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "openai": ("OPENAI_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY",),
    "groq": ("GROQ_API_KEY",),
    "deepseek": ("DEEPSEEK_API_KEY",),
}


def _env_key(provider: str) -> str:
    for name in ENV_KEYS.get(provider, ()):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


class LlmError(RuntimeError):
    """Raised when an LLM provider cannot be reached, lacks credentials, or returns an error."""


def _mask_key(key: str | None) -> str:
    if not key or len(key) < 8:
        return "••••••••" if key else ""
    return f"{key[:4]}••••{key[-4:]}"


def load_settings() -> dict[str, Any]:
    """Load settings from config/llm_settings.json or return defaults."""
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {
        "provider": os.environ.get("LLM_PROVIDER", "auto"),
        "model": os.environ.get("LLM_MODEL", ""),
        "api_key": os.environ.get("LLM_API_KEY", ""),
        "base_url": os.environ.get("LLM_BASE_URL", ""),
    }


def save_settings(new_settings: dict[str, Any]) -> dict[str, Any]:
    """Save updated settings to config/llm_settings.json."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    current = load_settings()
    changed = False
    for key, val in new_settings.items():
        if key == "api_key" and val == "":
            # keep existing key if empty string was passed in update
            continue
        if current.get(key) != val:
            changed = True
        current[key] = val
    CONFIG_FILE.write_text(json.dumps(current, indent=2), encoding="utf-8")
    if changed and STATUS_FILE.exists():
        try:
            STATUS_FILE.unlink()
        except Exception:
            pass
    return current


def resolve_provider_config(override_provider: str | None = None, override_model: str | None = None, override_key: str | None = None) -> tuple[str, str, str, str]:
    """Resolves the effective (provider, model, api_key, base_url). `override_key` (a key typed in for a test) counts before the Claude CLI fallback."""
    cfg = load_settings()
    prov = (override_provider or cfg.get("provider") or os.environ.get("LLM_PROVIDER") or "auto").strip().lower()
    
    # Auto-detection: the first provider that has a key (in the environment, or the one saved for it), then the local Claude CLI
    if prov == "auto":
        with_key = [p for p in ENV_KEYS if _env_key(p) or (cfg.get("provider") == p and cfg.get("api_key"))]
        if with_key:
            prov = with_key[0]
        elif shutil.which("claude"):
            prov = "claude_cli"
        else:
            prov = "gemini"  # Default recommended provider

    # Resolve API Key
    key = (override_key or "").strip() or cfg.get("api_key", "").strip() or os.environ.get("LLM_API_KEY", "").strip()
    if not key:
        key = _env_key(prov)

    # Fallback to local claude CLI if key is missing for remote API provider
    if prov in ("gemini", "openai", "anthropic", "groq", "deepseek") and not key:
        if shutil.which("claude"):
            prov = "claude_cli"
            model = DEFAULT_MODELS["claude_cli"]

    # Resolve Model
    model = (override_model or cfg.get("model") or os.environ.get("LLM_MODEL") or "").strip()
    if not model or prov == "claude_cli":
        model = DEFAULT_MODELS.get(prov, "default")

    # Resolve Base URL
    base_url = (cfg.get("base_url") or os.environ.get("LLM_BASE_URL") or "").strip()
    if not base_url:
        base_url = DEFAULT_BASE_URLS.get(prov, "")

    return prov, model, key, base_url


def get_public_settings() -> dict[str, Any]:
    """Returns safe settings for frontend UI display."""
    prov, model, key, base_url = resolve_provider_config()
    raw = load_settings()

    cached = load_status()
    connection_status = "unknown"
    status_message = "Connection has not been verified"
    latency_ms = None
    last_verified_at = None

    if cached and cached.get("provider") == prov and cached.get("model") == model:
        connection_status = cached.get("status", "unknown")
        status_message = cached.get("message", "")
        latency_ms = cached.get("latency_ms")
        last_verified_at = cached.get("timestamp")
    else:
        # If credentials are completely missing for an API provider and no CLI fallback:
        if prov in ("gemini", "openai", "anthropic", "groq", "deepseek") and not key:
            connection_status = "offline"
            status_message = f"API key is missing for {PROVIDER_NAMES.get(prov, prov)}."
        elif prov == "claude_cli" and not shutil.which("claude"):
            connection_status = "offline"
            status_message = "Claude Code CLI binary is not installed or not in PATH."

    return {
        "active_provider": prov,
        "active_provider_name": PROVIDER_NAMES.get(prov, prov),
        "active_model": model,
        "base_url": base_url,
        "has_api_key": bool(key),
        "api_key_masked": _mask_key(key),
        "configured_provider": raw.get("provider", "auto"),
        "available_providers": [
            {"id": k, "name": v, "default_model": DEFAULT_MODELS.get(k, ""), "needs_key": k not in ("claude_cli", "ollama")}
            for k, v in PROVIDER_NAMES.items()
        ],
        "claude_cli_installed": bool(shutil.which("claude")),
        "connection_status": connection_status,
        "status_message": status_message,
        "latency_ms": latency_ms,
        "last_verified_at": last_verified_at,
    }


def _call_gemini(user: str, system: str, model: str, api_key: str, timeout: int) -> str:
    if not api_key:
        raise LlmError("Google Gemini API key is missing. Set it in LLM Settings or via GEMINI_API_KEY.")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    contents = [{"role": "user", "parts": [{"text": user}]}]
    payload: dict[str, Any] = {"contents": contents}
    if system.strip():
        payload["system_instruction"] = {"parts": [{"text": system.strip()}]}
    
    with httpx.Client(timeout=timeout) as client:
        try:
            res = client.post(url, json=payload, headers={"Content-Type": "application/json"})
        except Exception as e:
            raise LlmError(f"Failed to connect to Gemini API: {e}") from e

    if res.status_code != 200:
        err_msg = res.text[:300]
        try:
            err_json = res.json()
            err_msg = err_json.get("error", {}).get("message", err_msg)
        except Exception:
            pass
        raise LlmError(f"Gemini API error ({res.status_code}): {err_msg}")

    try:
        data = res.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise LlmError("Gemini returned empty candidate list.")
        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        usage_meta = data.get("usageMetadata", {})
        inp = int(usage_meta.get("promptTokenCount") or 0)
        out = int(usage_meta.get("candidatesTokenCount") or 0)
        if inp > 0 or out > 0:
            try:
                from . import llm_usage
                llm_usage.record_backend_usage("gemini", model, inp, out, prompt_snippet=user[:64])
            except Exception:
                pass
        return text
    except Exception as e:
        raise LlmError(f"Failed to parse Gemini response: {e}") from e


def _call_openai_compatible(user: str, system: str, model: str, api_key: str, base_url: str, timeout: int, provider_name: str = "OpenAI") -> str:
    if not api_key and provider_name.lower() not in ("ollama", "local"):
        raise LlmError(f"{provider_name} API key is missing. Set it in LLM Settings or via environment.")
    
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    messages = []
    if system.strip():
        messages.append({"role": "system", "content": system.strip()})
    messages.append({"role": "user", "content": user})

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
    }

    with httpx.Client(timeout=timeout) as client:
        try:
            res = client.post(endpoint, json=payload, headers=headers)
        except Exception as e:
            raise LlmError(f"Failed to connect to {provider_name} at {endpoint}: {e}") from e

    if res.status_code != 200:
        err_msg = res.text[:300]
        try:
            err_json = res.json()
            err_msg = err_json.get("error", {}).get("message", err_msg)
        except Exception:
            pass
        raise LlmError(f"{provider_name} API error ({res.status_code}): {err_msg}")

    try:
        data = res.json()
        choices = data.get("choices", [])
        if not choices:
            raise LlmError(f"{provider_name} returned empty choices.")
        usage = data.get("usage", {})
        inp = int(usage.get("prompt_tokens") or 0)
        out = int(usage.get("completion_tokens") or 0)
        if inp > 0 or out > 0:
            try:
                from . import llm_usage
                llm_usage.record_backend_usage(provider_name.lower(), model, inp, out, prompt_snippet=user[:64])
            except Exception:
                pass
        return choices[0].get("message", {}).get("content", "")
    except Exception as e:
        raise LlmError(f"Failed to parse {provider_name} response: {e}") from e


def _call_anthropic(user: str, system: str, model: str, api_key: str, timeout: int) -> str:
    if not api_key:
        raise LlmError("Anthropic API key is missing. Set it in LLM Settings or via ANTHROPIC_API_KEY.")
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": user}],
    }
    if system.strip():
        payload["system"] = system.strip()

    with httpx.Client(timeout=timeout) as client:
        try:
            res = client.post(url, json=payload, headers=headers)
        except Exception as e:
            raise LlmError(f"Failed to connect to Anthropic API: {e}") from e

    if res.status_code != 200:
        err_msg = res.text[:300]
        try:
            err_json = res.json()
            err_msg = err_json.get("error", {}).get("message", err_msg)
        except Exception:
            pass
        raise LlmError(f"Anthropic API error ({res.status_code}): {err_msg}")

    try:
        data = res.json()
        content = data.get("content", [])
        if not content:
            raise LlmError("Anthropic returned empty content.")
        usage = data.get("usage", {})
        inp = int(usage.get("input_tokens") or 0)
        out = int(usage.get("output_tokens") or 0)
        if inp > 0 or out > 0:
            try:
                from . import llm_usage
                llm_usage.record_backend_usage("anthropic", model, inp, out, prompt_snippet=user[:64])
            except Exception:
                pass
        return content[0].get("text", "")
    except Exception as e:
        raise LlmError(f"Failed to parse Anthropic response: {e}") from e


def _call_claude_cli(user: str, system: str, timeout: int) -> str:
    exe = shutil.which("claude")
    if not exe:
        raise LlmError("The Claude CLI was not found on this machine. Select Gemini or OpenAI in LLM Settings, or install Claude Code.")
    cmd = [
        exe, "-p", "--output-format", "json", "--max-turns", "1",
        "--tools", "", "--setting-sources", "", "--disable-slash-commands",
        "--strict-mcp-config", "--no-session-persistence"
    ]
    if system.strip():
        cmd.extend(["--system-prompt", system])
    if os.environ.get("PROMPTGEN_MODEL"):
        cmd.extend(["--model", os.environ["PROMPTGEN_MODEL"]])

    try:
        r = subprocess.run(
            cmd,
            input=user,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            cwd=tempfile.gettempdir()
        )
    except subprocess.TimeoutExpired as e:
        raise LlmError(f"The Claude CLI did not answer within {timeout} s") from e

    data = None
    for line in reversed(r.stdout.splitlines()):
        if line.startswith("{"):
            try:
                data = json.loads(line)
            except ValueError:
                continue
            break

    if data is None:
        raise LlmError((r.stderr or r.stdout or "The Claude CLI returned nothing").strip()[:300])
    if data.get("is_error") or not str(data.get("result", "")).strip():
        raise LlmError(str(data.get("result") or "The Claude CLI returned an error").strip()[:300])

    if isinstance(data, dict):
        usage = data.get("usage") or {}
        inp = int(usage.get("input_tokens") or 0)
        out = int(usage.get("output_tokens") or 0)
        if inp > 0 or out > 0:
            try:
                from . import llm_usage
                llm_usage.record_backend_usage("claude_cli", "claude-code", inp, out, is_subscription=True, prompt_snippet=user[:64])
            except Exception:
                pass

    return str(data["result"])


def generate_text(user: str, system: str = "", timeout: int = 180, provider: str | None = None, model: str | None = None) -> str:
    """Central text generation dispatch for any configured LLM. Returns the text response."""
    prov, mdl, key, base_url = resolve_provider_config(override_provider=provider, override_model=model)

    if prov == "gemini":
        return _call_gemini(user, system, mdl, key, timeout)
    elif prov == "openai":
        url = base_url or DEFAULT_BASE_URLS["openai"]
        return _call_openai_compatible(user, system, mdl, key, url, timeout, "OpenAI")
    elif prov == "groq":
        url = base_url or DEFAULT_BASE_URLS["groq"]
        return _call_openai_compatible(user, system, mdl, key, url, timeout, "Groq")
    elif prov == "deepseek":
        url = base_url or DEFAULT_BASE_URLS["deepseek"]
        return _call_openai_compatible(user, system, mdl, key, url, timeout, "DeepSeek")
    elif prov == "ollama":
        url = base_url or DEFAULT_BASE_URLS["ollama"]
        return _call_openai_compatible(user, system, mdl, "", url, timeout, "Ollama")
    elif prov == "custom":
        if not base_url:
            raise LlmError("Base URL is required for custom OpenAI-compatible provider.")
        return _call_openai_compatible(user, system, mdl, key, base_url, timeout, "Custom Provider")
    elif prov == "anthropic":
        return _call_anthropic(user, system, mdl, key, timeout)
    elif prov == "claude_cli":
        return _call_claude_cli(user, system, timeout)
    else:
        raise LlmError(f"Unknown or unsupported LLM provider: '{prov}'. Choose gemini, openai, anthropic, or claude_cli.")


def _cache_status(ok: bool, provider: str, model: str, latency_ms: int, message: str) -> None:
    save_status({
        "status": "active" if ok else "offline",
        "provider": provider,
        "model": model,
        "latency_ms": latency_ms,
        "message": message,
        "timestamp": time.time(),
    })


def test_connection(provider: str | None = None, model: str | None = None, api_key: str | None = None, base_url: str | None = None) -> dict[str, Any]:
    """Test connection with the specified or active LLM."""
    prov, mdl, key, url = resolve_provider_config(override_provider=provider, override_model=model, override_key=api_key)
    if base_url is not None:
        url = base_url.strip()

    t0 = time.perf_counter()
    prompt = "Respond with exactly: LLM connection successful!"
    try:
        if prov == "gemini":
            resp = _call_gemini(prompt, "", mdl, key, timeout=30)
        elif prov == "openai":
            resp = _call_openai_compatible(prompt, "", mdl, key, url or DEFAULT_BASE_URLS["openai"], timeout=30, provider_name="OpenAI")
        elif prov == "groq":
            resp = _call_openai_compatible(prompt, "", mdl, key, url or DEFAULT_BASE_URLS["groq"], timeout=30, provider_name="Groq")
        elif prov == "deepseek":
            resp = _call_openai_compatible(prompt, "", mdl, key, url or DEFAULT_BASE_URLS["deepseek"], timeout=30, provider_name="DeepSeek")
        elif prov == "ollama":
            resp = _call_openai_compatible(prompt, "", mdl, "", url or DEFAULT_BASE_URLS["ollama"], timeout=30, provider_name="Ollama")
        elif prov == "custom":
            resp = _call_openai_compatible(prompt, "", mdl, key, url, timeout=30, provider_name="Custom Provider")
        elif prov == "anthropic":
            resp = _call_anthropic(prompt, "", mdl, key, timeout=30)
        elif prov == "claude_cli":
            resp = _call_claude_cli(prompt, "", timeout=30)
        else:
            return {"ok": False, "provider": prov, "model": mdl, "message": f"Unsupported provider: {prov}", "latency_ms": 0}

        latency = round((time.perf_counter() - t0) * 1000)
        res = {
            "ok": True,
            "provider": prov,
            "provider_name": PROVIDER_NAMES.get(prov, prov),
            "model": mdl,
            "latency_ms": latency,
            "message": f"Successfully connected to {PROVIDER_NAMES.get(prov, prov)} ({mdl}) in {latency} ms!",
            "sample_reply": resp.strip()[:100],
        }
        _cache_status(True, prov, mdl, latency, res["message"])
        return res
    except Exception as e:
        latency = round((time.perf_counter() - t0) * 1000)
        res = {
            "ok": False,
            "provider": prov,
            "provider_name": PROVIDER_NAMES.get(prov, prov),
            "model": mdl,
            "latency_ms": latency,
            "message": str(e),
        }
        _cache_status(False, prov, mdl, latency, str(e))
        return res


def _ollama_reachable() -> bool:
    """True when an Ollama server answers on this computer (it is never installed or started here)."""
    try:
        return httpx.get(DEFAULT_BASE_URLS["ollama"].removesuffix("/v1") + "/api/tags", timeout=1.0).status_code == 200
    except httpx.HTTPError:
        return False


def detect_options() -> list[dict[str, str]]:
    """What this computer can connect to right now, in the order `auto` tries it. Says where each came from; never returns a key."""
    cfg = load_settings()
    found = []
    for prov in ENV_KEYS:
        if _env_key(prov):
            source = "API key in the environment"
        elif cfg.get("provider") == prov and cfg.get("api_key"):
            source = "API key saved in LLM settings"
        else:
            continue
        found.append({"id": prov, "name": PROVIDER_NAMES[prov], "model": DEFAULT_MODELS[prov], "source": source})
    if shutil.which("claude"):
        found.append({"id": "claude_cli", "name": PROVIDER_NAMES["claude_cli"], "model": DEFAULT_MODELS["claude_cli"], "source": "Claude Code installed on this computer"})
    if _ollama_reachable():
        found.append({"id": "ollama", "name": PROVIDER_NAMES["ollama"], "model": DEFAULT_MODELS["ollama"], "source": "Ollama running on this computer"})
    return found


def auto_connect() -> dict[str, Any]:
    """Try each detected option in order and keep the first one that answers. Nothing is saved unless one answers."""
    results = []
    for opt in detect_options():
        # that provider's own default model and URL: a model or URL saved for another provider must not leak into the test
        res = test_connection(provider=opt["id"], model=opt["model"], base_url="")
        results.append({"id": opt["id"], "name": opt["name"], "source": opt["source"], "ok": bool(res["ok"]), "message": res["message"], "latency_ms": res["latency_ms"]})
        if res["ok"]:
            save_settings({"provider": opt["id"], "model": opt["model"], "base_url": ""})
            _cache_status(True, opt["id"], opt["model"], res["latency_ms"], res["message"])   # saving a changed provider clears the cached status
            return {"connected": True, "provider": opt["id"], "provider_name": opt["name"], "model": opt["model"],
                    "latency_ms": res["latency_ms"], "message": res["message"], "results": results}
    if results:
        message = f"Found {len(results)} option(s), but none answered. See the reasons below, or fill in the manual form."
    else:
        message = ("No API key was found in the environment and Claude Code is not installed. Install Claude Code and sign in, "
                   "or fill in the manual form with an API key.")
    return {"connected": False, "provider": None, "provider_name": None, "model": None, "latency_ms": None, "message": message, "results": results}
