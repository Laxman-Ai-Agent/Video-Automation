"""`backend` is the compatibility name of `UI.backend`: UI/backend holds the bridge modules that point `backend.<x>` at the canonical SYSTEM / VIDEO_ENGINE modules.
System and engine modules still import through it, so the alias must exist in every process that imports them (the API, the CLI, the tests).
`install()` registers it once; SYSTEM, VIDEO_ENGINE and UI call it when they are first imported."""
from __future__ import annotations

import importlib
import importlib.util
import sys
from importlib.abc import Loader, MetaPathFinder
from importlib.machinery import ModuleSpec

_find_spec = importlib.util.find_spec


class _AliasLoader(Loader):
    def __init__(self, target: str):
        self.target = target

    def create_module(self, spec):
        # The target module object itself, so `backend.x` and `UI.backend.x` are one module (a bridge module replaces itself in sys.modules).
        module = importlib.import_module(self.target)
        return sys.modules.get(self.target, module)

    def exec_module(self, module):
        pass


class BackendAliasFinder(MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname == "backend":
            target_name = "UI.backend"
        elif fullname.startswith("backend."):
            target_name = "UI." + fullname
        else:
            return None
        try:
            target_spec = _find_spec(target_name)
        except (ImportError, ValueError):
            return None
        if target_spec is None:
            return None
        is_package = target_spec.submodule_search_locations is not None
        spec = ModuleSpec(fullname, _AliasLoader(target_name), is_package=is_package)
        if is_package:
            spec.submodule_search_locations = list(target_spec.submodule_search_locations)
        return spec


def install() -> None:
    if not any(isinstance(finder, BackendAliasFinder) for finder in sys.meta_path):
        sys.meta_path.insert(0, BackendAliasFinder())
