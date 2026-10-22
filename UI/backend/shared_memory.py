"""Canonical alias for SYSTEM.memory.shared_memory during Phase 2 migration."""
import sys
import SYSTEM.memory.shared_memory as _canonical
sys.modules[__name__] = _canonical
