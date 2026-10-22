"""Canonical alias for SYSTEM.observability.evaluation during Phase 2 migration."""
import sys
import SYSTEM.observability.evaluation as _canonical
sys.modules[__name__] = _canonical
