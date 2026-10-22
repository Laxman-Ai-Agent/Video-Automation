"""Canonical alias for SYSTEM.observability.llm_usage during Phase 2 migration."""
import sys
import SYSTEM.observability.llm_usage as _canonical
sys.modules[__name__] = _canonical
