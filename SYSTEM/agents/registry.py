"""Canonical alias for SYSTEM.registries.agent_registry during Phase 2 migration."""
import sys
import SYSTEM.registries.agent_registry as _canonical
sys.modules[__name__] = _canonical
