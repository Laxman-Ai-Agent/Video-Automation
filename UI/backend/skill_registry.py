"""Canonical alias for SYSTEM.registries.skill_registry during Phase 2 migration."""
import sys
import SYSTEM.registries.skill_registry as _canonical
sys.modules[__name__] = _canonical
