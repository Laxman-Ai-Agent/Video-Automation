"""Canonical alias for SYSTEM.agents.shared.communication during Phase 2 migration."""
import sys
import SYSTEM.agents.shared.communication as _canonical
sys.modules[__name__] = _canonical
