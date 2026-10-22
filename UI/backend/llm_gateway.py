"""Canonical alias for SYSTEM.core.llm_gateway during Phase 2 migration."""
import sys
import SYSTEM.core.llm_gateway as _canonical
sys.modules[__name__] = _canonical
