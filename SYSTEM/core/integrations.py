"""Optional integrations: how a domain project (video generation, ...) plugs capabilities into the Agent Building System.

The Agent System never imports a domain project. It asks for a named capability with `get(name)`; a domain project provides it with
`register(name, provider)` (or lazily with `factory=`) when it is installed. A capability nobody provides is a normal state: `get` returns
None and the caller degrades gracefully. Domain projects can also be named in AGENT_SYSTEM_INTEGRATIONS (comma-separated module paths):
each module's `register()` is called on the first lookup, and a module that cannot load is recorded in `failures()`, never raised.

Capabilities in use:
  stage_dependencies     {stage: (stage, ...)} for the dependency-graph validator
  pipeline_orchestrator  the sole execution engine class, for the security-boundary validator
  system_capabilities    callable returning what the domain runtime needs (browser, ffmpeg...), for evaluation
  jobs                   background-job adapter with is_running(project_id) / current(project_id), to reconcile orphaned runs
"""
from __future__ import annotations

import importlib
import os
import threading
from typing import Any, Callable

ENV_MODULES = "AGENT_SYSTEM_INTEGRATIONS"
_MISSING = object()

_lock = threading.RLock()
_providers: dict[str, Any] = {}
_factories: dict[str, Callable[[], Any]] = {}
_failures: dict[str, str] = {}
_configured_loaded = False


def register(name: str, provider: Any = _MISSING, *, factory: Callable[[], Any] | None = None) -> None:
    """Provide a capability: the object itself, or a factory called once on first use (so registering imports nothing heavy)."""
    if (provider is _MISSING) == (factory is None):
        raise ValueError("register() needs exactly one of provider or factory")
    with _lock:
        _providers.pop(name, None)
        _factories.pop(name, None)
        if factory is not None:
            _factories[name] = factory
        else:
            _providers[name] = provider


def unregister(name: str) -> None:
    with _lock:
        _providers.pop(name, None)
        _factories.pop(name, None)


def get(name: str, default: Any = None) -> Any:
    """The provider of a capability, or `default` when no domain project provides it (or its factory fails: see failures())."""
    _load_configured()
    with _lock:
        if name in _providers:
            return _providers[name]
        factory = _factories.get(name)
        if factory is None:
            return default
        try:
            _providers[name] = factory()
        except Exception as e:      # an absent or broken domain project must not stop the Agent System
            _failures[name] = f"{type(e).__name__}: {e}"
            return default
        del _factories[name]
        return _providers[name]


def available() -> list[str]:
    with _lock:
        return sorted(set(_providers) | set(_factories))


def failures() -> dict[str, str]:
    """Integrations (module paths or capability names) that could not be loaded, with the reason."""
    with _lock:
        return dict(_failures)


def _load_configured() -> None:
    global _configured_loaded
    with _lock:
        if _configured_loaded:
            return
        _configured_loaded = True
    for module in (m.strip() for m in os.environ.get(ENV_MODULES, "").split(",")):
        if not module:
            continue
        try:
            hook = getattr(importlib.import_module(module), "register", None)
            if callable(hook):
                hook()
        except Exception as e:
            with _lock:
                _failures[module] = f"{type(e).__name__}: {e}"
