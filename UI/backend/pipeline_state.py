"""Canonical alias for SYSTEM.core.pipeline_state during Phase 2 migration."""
import sys
import SYSTEM.core.pipeline_state as _canonical
sys.modules[__name__] = _canonical
