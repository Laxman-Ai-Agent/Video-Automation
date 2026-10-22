"""Canonical alias for SYSTEM.agents.shared.base_agent during Phase 2 migration."""
import sys
import SYSTEM.agents.shared.base_agent as _canonical
sys.modules[__name__] = _canonical
