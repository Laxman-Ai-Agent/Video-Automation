"""Unified LLM client supporting multiple providers:
Google Gemini, OpenAI, Anthropic (API & CLI), Groq, DeepSeek, Ollama, and OpenAI-compatible endpoints.
Configuration is stored in config/llm_settings.json and can be managed via API/UI or environment variables.
"""
import contextlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

import httpx

_AGY_LOCK = threading.RLock()
_ACTIVE_GENERATION_COUNT = 0
_GENERATION_LOCK = threading.Lock()


def is_generation_active() -> bool:
    """Returns True if any heavy LLM text generation is actively in progress."""
    with _GENERATION_LOCK:
        return _ACTIVE_GENERATION_COUNT > 0

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
    "antigravity": "gemini-3.8-flash-high",
    "gemini": "gemini-3.5-flash",       # gemini-2.0-flash and 1.5 were retired by Google (404 "no longer available"); check https://ai.google.dev/gemini-api/docs/models when this one is retired too
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-sonnet-20241022",
    "groq": "llama-3.3-70b-versatile",
    "deepseek": "deepseek-chat",
    "ollama": "llama3.2",
    "claude_cli": "claude-code",
    "custom": "default",
}

# Models a provider offers as a pick-list on the LLM page (providers not listed take a typed model name).
# claude_cli: the ids `claude --model` accepts; an alias (sonnet/opus/haiku) always follows that family's latest model.
PROVIDER_MODELS: dict[str, list[dict[str, str]]] = {
    "antigravity": [
        {"id": "gemini-3.8-flash-high", "name": "Gemini 3.8 Flash (High)"},
        {"id": "gemini-3.8-flash-medium", "name": "Gemini 3.8 Flash (Medium)"},
        {"id": "gemini-3.8-flash-low", "name": "Gemini 3.8 Flash (Low)"},
        {"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6 (Thinking)"},
        {"id": "claude-opus-4-6", "name": "Claude Opus 4.6 (Thinking)"},
        {"id": "gpt-oss-120b", "name": "GPT-OSS 120B (Medium)"},
    ],
    "claude_cli": [
        {"id": "claude-code", "name": "Claude Code default (the model the CLI itself is set to)"},
        {"id": "sonnet", "name": "Sonnet (latest)"},
        {"id": "opus", "name": "Opus (latest)"},
        {"id": "haiku", "name": "Haiku (latest)"},
        {"id": "claude-sonnet-5-5", "name": "Sonnet 5.5"},
        {"id": "claude-opus-5-5", "name": "Opus 5.5"},
        {"id": "claude-haiku-5-5", "name": "Haiku 5.5"},
        {"id": "claude-fable-5-1", "name": "Fable 5.1"},
    ],
}

AUTH_METHODS: dict[str, str] = {
    "antigravity": "ide_session",
    "gemini": "api_key",
    "openai": "api_key",
    "anthropic": "api_key",
    "groq": "api_key",
    "deepseek": "api_key",
    "claude_cli": "cli_subscription",
    "ollama": "local_daemon",
    "custom": "custom_endpoint",
}

AUTH_METHOD_NAMES: dict[str, str] = {
    "ide_session": "Antigravity Active Session",
    "api_key": "API Key",
    "cli_subscription": "CLI Subscription",
    "local_daemon": "Local Daemon",
    "custom_endpoint": "Custom Endpoint",
}

DEFAULT_BASE_URLS: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "deepseek": "https://api.deepseek.com",
    "ollama": "http://localhost:11434/v1",
}

PROVIDER_NAMES: dict[str, str] = {
    "antigravity": "Google Antigravity (Active Coding Model)",
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
    # If provider changed but model was not explicitly specified, update to new provider's default model
    if "provider" in new_settings and "model" not in new_settings and new_settings["provider"] in DEFAULT_MODELS:
        current["model"] = DEFAULT_MODELS[new_settings["provider"]]
    CONFIG_FILE.write_text(json.dumps(current, indent=2), encoding="utf-8")
    if changed and STATUS_FILE.exists():
        try:
            STATUS_FILE.unlink()
        except Exception:
            pass
    return current


def resolve_provider_config(override_provider: str | None = None, override_model: str | None = None, override_key: str | None = None) -> tuple[str, str, str, str]:
    """Resolves the locked (provider, model, api_key, base_url).
    
    Eliminates all silent fallbacks: if a provider is configured, the system strictly
    locks to that provider. If credentials are missing, it does NOT silently switch to
    Claude CLI or any other provider.
    """
    cfg = load_settings()
    prov = (override_provider or cfg.get("provider") or os.environ.get("LLM_PROVIDER") or "auto").strip().lower()
    
    # Auto-detection only applies if provider is explicitly set to 'auto'.
    if prov == "auto":
        # same order as detect_options: Claude Code, Antigravity, an API key, then the recommended default
        if shutil.which("claude"):
            prov = "claude_cli"
        elif os.environ.get("ANTIGRAVITY_AGENT") or _find_agy_exe():
            prov = "antigravity"
        else:
            with_key = [p for p in ENV_KEYS if _env_key(p) or (cfg.get("provider") == p and cfg.get("api_key"))]
            prov = with_key[0] if with_key else "gemini"  # Default recommended provider

    # Resolve API Key
    key = (override_key or "").strip() or cfg.get("api_key", "").strip() or os.environ.get("LLM_API_KEY", "").strip()
    if not key:
        key = _env_key(prov)

    # Note: Silent fallback to local claude CLI when an API key is missing is strictly disabled
    # per Active Model Lock requirements. The system must report the missing key directly.

    # Resolve Model
    if override_model:
        model = override_model.strip()
    elif override_provider and override_provider.lower() != (cfg.get("provider") or "").lower():
        model = DEFAULT_MODELS.get(prov, "default")
    else:
        model = (cfg.get("model") or os.environ.get("LLM_MODEL") or "").strip() or DEFAULT_MODELS.get(prov, "default")

    # Resolve Base URL
    base_url = (cfg.get("base_url") or os.environ.get("LLM_BASE_URL") or "").strip()
    if not base_url:
        base_url = DEFAULT_BASE_URLS.get(prov, "")

    return prov, model, key, base_url


def get_active_model_config() -> dict[str, Any]:
    """Authoritative Active Model Configuration object.
    
    Single source of truth for the selected provider, exact model identifier,
    authentication method, connection health, and model lock status.
    """
    prov, model, key, base_url = resolve_provider_config()
    raw = load_settings()
    auth_method = AUTH_METHODS.get(prov, "api_key")
    auth_method_name = AUTH_METHOD_NAMES.get(auth_method, "API Key")

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
        if prov in ("gemini", "openai", "anthropic", "groq", "deepseek") and not key:
            connection_status = "offline"
            status_message = f"API key is missing for {PROVIDER_NAMES.get(prov, prov)}. [Active Model Lock: Silent fallback disabled]"
        elif prov == "antigravity" and not _find_agy_exe():
            connection_status = "offline"
            status_message = "Google Antigravity CLI binary ('agy') is not installed or not found."
        elif prov == "claude_cli" and not shutil.which("claude"):
            connection_status = "offline"
            status_message = "Claude Code CLI binary is not installed or not in PATH."

    return {
        "model_locked": True,
        "active_provider": prov,
        "active_provider_name": PROVIDER_NAMES.get(prov, prov),
        "active_model": model,
        "auth_method": auth_method,
        "auth_method_name": auth_method_name,
        "base_url": base_url,
        "has_credentials": bool(key) if auth_method == "api_key" else (bool(_find_agy_exe()) if auth_method == "ide_session" else (bool(shutil.which("claude")) if auth_method == "cli_subscription" else True)),
        "has_api_key": bool(key),
        "api_key_masked": _mask_key(key),
        "configured_provider": raw.get("provider", "auto"),
        "configured_model": raw.get("model", ""),
        "connection_status": connection_status,
        "status_message": status_message,
        "latency_ms": latency_ms,
        "last_verified_at": last_verified_at,
    }


def get_public_settings() -> dict[str, Any]:
    """Returns safe settings for frontend UI display, including Active Model Configuration."""
    active_cfg = get_active_model_config()
    return {
        **active_cfg,
        "available_providers": [
            {
                "id": k,
                "name": v,
                "default_model": DEFAULT_MODELS.get(k, ""),
                "auth_method": AUTH_METHODS.get(k, "api_key"),
                "auth_method_name": AUTH_METHOD_NAMES.get(AUTH_METHODS.get(k, "api_key"), "API Key"),
                "needs_key": k not in ("antigravity", "claude_cli", "ollama"),
                "models": PROVIDER_MODELS.get(k, []),
            }
            for k, v in PROVIDER_NAMES.items()
        ],
        "antigravity_installed": bool(_find_agy_exe()),
        "claude_cli_installed": bool(shutil.which("claude")),
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

    max_toks = 1500 if provider_name.lower() == "groq" else 4096
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": max_toks,
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
        if res.status_code != 200:
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


def _find_agy_exe() -> str | None:
    exe = shutil.which("agy")
    if exe:
        return exe
    candidate = Path.home() / ".gemini" / "bin" / "agy.exe"
    if candidate.exists():
        return str(candidate)
    return None


def normalize_antigravity_model(model: str | None) -> str:
    """Map model slug or identifier to exact model name recognized by Google Antigravity CLI ('agy')."""
    if not model:
        return "Gemini 3.8 Flash (High)"
    raw = str(model).strip()
    m = raw.lower().replace("_", "-").replace(" ", "-")
    if "flash" in m and "high" in m:
        return "Gemini 3.8 Flash (High)"
    if "flash" in m and "medium" in m:
        return "Gemini 3.8 Flash (Medium)"
    if "flash" in m and "low" in m:
        return "Gemini 3.8 Flash (Low)"
    if "flash" in m:
        return "Gemini 3.8 Flash (High)"
    if "sonnet" in m:
        return "Claude Sonnet 4.6 (Thinking)"
    if "opus" in m:
        return "Claude Opus 4.6 (Thinking)"
    if "gpt" in m or "oss" in m:
        return "GPT-OSS 120B (Medium)"
    valid_exact = {
        "Gemini 3.8 Flash (High)",
        "Gemini 3.8 Flash (Medium)",
        "Gemini 3.8 Flash (Low)",
        "Claude Sonnet 4.6 (Thinking)",
        "Claude Opus 4.6 (Thinking)",
        "GPT-OSS 120B (Medium)",
    }
    if raw in valid_exact:
        return raw
    return "Gemini 3.8 Flash (High)"


@contextlib.contextmanager
def _interprocess_agy_lock(timeout: float = 120.0):
    """File lock across OS processes on Windows so multiple scripts/servers do not collide on agy daemon."""
    lockfile_path = Path(tempfile.gettempdir()) / "agy_cli_interprocess.lock"
    start = time.time()
    try:
        import msvcrt
        f = open(lockfile_path, "a+b")
        acquired = False
        while time.time() - start < timeout:
            try:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                acquired = True
                break
            except (OSError, IOError):
                time.sleep(0.1)
        if not acquired:
            try:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
                acquired = True
            except Exception:
                pass
        try:
            yield
        finally:
            if acquired:
                try:
                    f.seek(0)
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                except Exception:
                    pass
            try:
                f.close()
            except Exception:
                pass
    except ImportError:
        yield


def _call_antigravity_cli(user: str, system: str, timeout: int, model: str = "gemini-3.8-flash-high") -> str:
    exe = _find_agy_exe()
    if not exe:
        raise LlmError("The Google Antigravity CLI ('agy') was not found on this machine.")
    
    # Direct directive preventing autonomous agent loops or file inspections
    direct_directive = (
        "CRITICAL SYSTEM DIRECTIVE: You are executing as a direct text completion engine. "
        "DO NOT call any tools or skills. DO NOT read files, do not execute terminal commands, and do not inspect workspace directories. "
        "Output ONLY the direct completion/response to the user prompt immediately."
    )
    content = f"{system.strip()}\n\n{user.strip()}" if system.strip() else user.strip()
    full_prompt = f"{direct_directive}\n\n{content}"
    agy_model = normalize_antigravity_model(model)
    cmd = [
        exe, "-p", full_prompt,
        "--model", agy_model,
        "--output-format", "text",
        "--disable-slash-commands",
        "--dangerously-skip-permissions",
    ]
    with _AGY_LOCK:
        with _interprocess_agy_lock(timeout=float(timeout)):
            try:
                r = subprocess.run(
                    cmd,
                    capture_output=True,
                    stdin=subprocess.DEVNULL,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout,
                    cwd=tempfile.gettempdir()
                )
            except subprocess.TimeoutExpired as e:
                raise LlmError(f"Antigravity CLI did not answer within {timeout} s") from e
            if r.returncode != 0:
                err = (r.stderr or r.stdout or "Antigravity CLI error").strip()
                raise LlmError(f"Antigravity CLI error: {err[:300]}")
            return r.stdout.strip()


def _call_claude_cli(user: str, system: str, timeout: int, model: str | None = None, images: list[str] | None = None) -> str:
    """images: picture files the model must look at. The CLI then gets the Read tool (and nothing else) for the folders those files are in; without images it gets no tool and one turn."""
    exe = shutil.which("claude")
    if not exe:
        raise LlmError("The Claude CLI was not found on this machine. Select Gemini or OpenAI in LLM Settings, or install Claude Code.")
    cli_default = DEFAULT_MODELS["claude_cli"]   # the label for "no --model": the CLI uses its own default
    model = model if model and model != cli_default else os.environ.get("PROMPTGEN_MODEL")
    cmd = [
        exe, "-p", "--output-format", "json", "--max-turns", "6" if images else "1",
        "--tools", "Read" if images else "", "--setting-sources", "", "--disable-slash-commands",
        "--strict-mcp-config", "--no-session-persistence"
    ]
    if system.strip():
        cmd.extend(["--system-prompt", system])
    if model:
        cmd.extend(["--model", model])
    if images:
        paths = [str(Path(p).resolve()) for p in images]
        user = f"{user}\n\nThe pictures to look at are these files; open every one with the Read tool before you answer:\n" + "\n".join(paths)
        cmd.extend(["--allowedTools", "Read"])
        for folder in sorted({str(Path(p).parent) for p in paths}):
            cmd.extend(["--add-dir", folder])

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
                llm_usage.record_backend_usage("claude_cli", model or cli_default, inp, out, is_subscription=True, prompt_snippet=user[:64])
            except Exception:
                pass

    return str(data["result"])


VISION_TIMEOUT_S = 240                       # a call that looks at pictures takes longer (the CLI reads each file first)


def can_look(provider: str | None = None) -> bool:
    """Whether the (active) provider is set up to look at picture files: only Claude Code is."""
    return (provider or resolve_provider_config()[0]) == "claude_cli"


def generate_text(user: str, system: str = "", timeout: int = 180, provider: str | None = None, model: str | None = None, images: list[str] | None = None) -> str:
    """Central text generation dispatch for any configured LLM. Returns the text response.
    images: picture files the model must look at; only Claude Code (claude_cli) is wired to show them, any other provider raises LlmError so the caller can fall back to text."""
    global _ACTIVE_GENERATION_COUNT
    with _GENERATION_LOCK:
        _ACTIVE_GENERATION_COUNT += 1
    try:
        prov, mdl, key, base_url = resolve_provider_config(override_provider=provider, override_model=model)

        if images and not can_look(prov):
            raise LlmError(f"{prov} is not set up to look at pictures here: choose Claude Code on the LLM page")
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
        elif prov == "antigravity":
            return _call_antigravity_cli(user, system, timeout, mdl)
        elif prov == "claude_cli":
            return _call_claude_cli(user, system, timeout, model=mdl, images=images)
        else:
            raise LlmError(f"Unknown or unsupported LLM provider: '{prov}'. Choose gemini, antigravity, openai, anthropic, or claude_cli.")
    finally:
        with _GENERATION_LOCK:
            _ACTIVE_GENERATION_COUNT = max(0, _ACTIVE_GENERATION_COUNT - 1)


def _cache_status(ok: bool, provider: str, model: str, latency_ms: int, message: str) -> None:
    save_status({
        "status": "active" if ok else "offline",
        "provider": provider,
        "model": model,
        "latency_ms": latency_ms,
        "message": message,
        "timestamp": time.time(),
    })


def test_connection(provider: str | None = None, model: str | None = None, api_key: str | None = None, base_url: str | None = None, force: bool = False) -> dict[str, Any]:
    """Test connection with the specified or active LLM."""
    prov, mdl, key, url = resolve_provider_config(override_provider=provider, override_model=model, override_key=api_key)
    if base_url is not None:
        url = base_url.strip()

    # Fast-path for background health probes: return verified active status if tested within 60s
    if not force and provider is None and model is None and api_key is None and base_url is None:
        cached = load_status()
        if cached and cached.get("provider") == prov and cached.get("model") == mdl and cached.get("status") == "active":
            if time.time() - float(cached.get("timestamp", 0)) < 60.0:
                return {
                    "ok": True,
                    "provider": prov,
                    "provider_name": PROVIDER_NAMES.get(prov, prov),
                    "model": mdl,
                    "latency_ms": cached.get("latency_ms", 0),
                    "message": cached.get("message", "Connected"),
                    "cached": True,
                }

    if prov in ("gemini", "openai", "anthropic", "groq", "deepseek") and not key:
        err_msg = f"API key is missing for {PROVIDER_NAMES.get(prov, prov)}. [Active Model Lock: Silent fallback disabled]"
        _cache_status(False, prov, mdl, 0, err_msg)
        return {
            "ok": False,
            "provider": prov,
            "provider_name": PROVIDER_NAMES.get(prov, prov),
            "model": mdl,
            "latency_ms": 0,
            "message": err_msg,
        }

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
        elif prov == "antigravity":
            resp = _call_antigravity_cli(prompt, "", timeout=30, model=mdl)
        elif prov == "claude_cli":
            resp = _call_claude_cli(prompt, "", timeout=30, model=mdl)
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
    if shutil.which("claude"):
        found.append({"id": "claude_cli", "name": PROVIDER_NAMES["claude_cli"], "model": DEFAULT_MODELS["claude_cli"], "source": "Claude Code installed on this computer"})
    if _find_agy_exe():
        found.append({"id": "antigravity", "name": PROVIDER_NAMES["antigravity"], "model": DEFAULT_MODELS["antigravity"], "source": "Google Antigravity active session on this computer"})
    for prov in ENV_KEYS:
        if _env_key(prov):
            source = "API key in the environment"
        elif cfg.get("provider") == prov and cfg.get("api_key"):
            source = "API key saved in LLM settings"
        else:
            continue
        found.append({"id": prov, "name": PROVIDER_NAMES[prov], "model": DEFAULT_MODELS[prov], "source": source})
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
