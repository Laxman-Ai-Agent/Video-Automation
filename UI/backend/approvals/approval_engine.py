"""Canonical alias for SYSTEM.approvals.approval_engine during Phase 2 migration."""
import sys
import SYSTEM.approvals.approval_engine as _canonical
sys.modules[__name__] = _canonical
