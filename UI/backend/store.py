"""Canonical alias for SYSTEM.memory.store during Phase 2 migration."""
import sys
import SYSTEM.memory.store as _canonical
sys.modules[__name__] = _canonical
