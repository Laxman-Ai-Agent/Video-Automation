"""Canonical alias for SYSTEM.approvals.guard during Phase 2 migration."""
import sys
import SYSTEM.approvals.guard as _canonical
sys.modules[__name__] = _canonical
