"""Canonical alias for SYSTEM.agents.shared.contracts during Phase 2 migration."""
import sys
import SYSTEM.agents.shared.contracts as _canonical
sys.modules[__name__] = _canonical
